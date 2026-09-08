"""Movie Agent frontend: FastAPI + SSE, reusing the full MovieOrchestrator pipeline.

Run locally or on Spark:
    python server.py
Then visit http://127.0.0.1:9071 (port follows the PORT env variable).

The Gradio app.py remains a fallback entry point; this server delivers the
complete three-act experience.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
import hashlib
import json
import mimetypes
import os
import re
import shutil
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ValidationError, field_validator

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.services.errors import error_info, record_failure
from movie_agent.services.subtitles import render_srt, render_vtt, script_subtitle_track
from movie_agent.services.media_quality import best_master_path, best_screening_path, quality_snapshot
from movie_agent.pipeline.diagnostics import delivery_preflight, diagnostics_snapshot
from movie_agent.services.readiness import PRODUCTION_ACTION_CONTRACT, PRODUCTION_ACTIONS, ProductionBlockedError, ensure_action_ready, production_readiness
from movie_agent.pipeline.jobs import JobAlreadyRunning, JobLedger
from movie_agent.state import shot_previewable
from movie_agent.services.cache_cleanup import clean_working_cache, storage_summary
from movie_agent.services.reference_generation import ReferenceImageRequest, generate_reference_image
from movie_agent.storage.reference_bank import ReferenceBankStore
from movie_agent.services.state_ledger import validate_state_delta_shape
from movie_agent.services.change_impact import SHOT_EDITABLE_FIELDS
from movie_agent.api.evaluator import router as evaluator_router

settings = Settings.from_env()
orchestrator = MovieOrchestrator(settings)
job_ledger = JobLedger(settings.projects_dir)

STATIC_DIR = Path(__file__).parent / "static"
# Rendering and media mutation is serialized per project, not globally.  A
# long ComfyUI job for one film must not block an unrelated project's edit.
project_locks: dict[str, threading.Lock] = {}
project_locks_guard = threading.Lock()
JOB_HEARTBEAT_INTERVAL_SECONDS = 45


def project_lock(project_id: str) -> threading.Lock:
    """Return the stable lock for one project (kept process-local for MVP)."""

    key = str(project_id)
    with project_locks_guard:
        return project_locks.setdefault(key, threading.Lock())

app = FastAPI(title="Movie-Agent · AI Film Studio")
app.include_router(evaluator_router)


def _directory_ready(path: Path) -> bool:
    """Check whether a directory exists or can be created by the service."""

    candidate = Path(path)
    if candidate.exists():
        return candidate.is_dir() and os.access(candidate, os.W_OK)
    parent = candidate
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    return parent.is_dir() and os.access(parent, os.W_OK)


def _binary_ready(binary: str) -> bool:
    """Resolve a configured executable without running arbitrary commands."""

    value = str(binary or "").strip()
    if not value:
        return False
    return bool(shutil.which(value) or (Path(value).is_file() and os.access(value, os.X_OK)))


def runtime_checks() -> dict[str, dict[str, Any]]:
    """Return non-invasive readiness checks for the current runtime.

    This deliberately reports capability booleans only.  It never performs a
    network request and never includes API keys, host credentials, or paths in
    the response, making it safe to expose through the public health endpoint.
    """

    video_mode = str(settings.video_generation_mode or "mock").lower()
    provider = str(settings.model_provider or "mock").lower()
    workflow = settings.workflows_dir / settings.comfy_workflow_template
    checks = {
        "projects_storage": {"ok": _directory_ready(settings.projects_dir), "required": True},
        "outputs_storage": {"ok": _directory_ready(settings.outputs_dir), "required": True},
        "ffmpeg": {"ok": _binary_ready(settings.ffmpeg_bin), "required": True},
        "ffprobe": {"ok": _binary_ready(settings.ffprobe_bin), "required": True},
        "model_provider": {
            "ok": provider != "modelscope" or bool(str(settings.modelscope_api_key or "").strip()),
            "required": provider == "modelscope",
        },
        "comfyui_workflow": {
            "ok": video_mode != "comfyui" or workflow.is_file(),
            "required": video_mode == "comfyui",
        },
    }
    return checks


def runtime_ready(checks: dict[str, dict[str, Any]] | None = None) -> bool:
    checks = checks or runtime_checks()
    return all(bool(item.get("ok")) for item in checks.values() if item.get("required", True))


@app.middleware("http")
async def prevent_stale_frontend_cache(request: Request, call_next):
    """Keep the single-page console and its assets in sync after deployments."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
    return response


class CreateProjectPayload(BaseModel):
    idea: str = Field(min_length=10, max_length=2_000)
    duration: int = Field(ge=30, le=80)
    visual_style: str = Field(min_length=2, max_length=80)

    @field_validator("idea", "visual_style")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Must not be empty.")
        return cleaned


class UpdateShotPayload(BaseModel):
    """Editable fields exposed by the expanded Shot Workspace."""

    duration_seconds: int | None = Field(default=None, ge=1, le=80)
    desired_duration: float | None = Field(default=None, ge=1, le=80)
    timing_mode: Literal["native", "trim", "extend", "hold_last_frame", "slow_motion"] | None = None
    framing: str | None = Field(default=None, min_length=1, max_length=120)
    image_description: str | None = Field(default=None, min_length=1, max_length=4_000)
    action: str | None = Field(default=None, min_length=1, max_length=2_000)
    sound_design: str | None = Field(default=None, min_length=1, max_length=2_000)
    generation_mode: str | None = Field(default=None, min_length=1, max_length=20)
    prompt: str | None = Field(default=None, min_length=1, max_length=12_000)
    narrative_purpose: str | None = Field(default=None, min_length=1, max_length=1_000)
    starting_state: str | None = Field(default=None, min_length=1, max_length=1_000)
    main_action: str | None = Field(default=None, min_length=1, max_length=2_000)
    secondary_action: str | None = Field(default=None, min_length=1, max_length=2_000)
    environment_reaction: str | None = Field(default=None, min_length=1, max_length=2_000)
    character_reaction: str | None = Field(default=None, min_length=1, max_length=1_000)
    ending_state: str | None = Field(default=None, min_length=1, max_length=1_000)
    transition_hook: str | None = Field(default=None, min_length=1, max_length=1_000)
    scene_id: str | None = Field(default=None, min_length=1, max_length=120)
    character_ids: list[str] | None = Field(default=None, max_length=12)
    prop_ids: list[str] | None = Field(default=None, max_length=12)
    story_function: str | None = Field(default=None, min_length=1, max_length=120)
    information_gain: float | None = Field(default=None, ge=0, le=1)
    emotional_shift: str | None = Field(default=None, min_length=1, max_length=500)
    visual_motif: str | None = Field(default=None, min_length=1, max_length=500)
    transition_type: Literal["CONTINUOUS", "HARD_CUT", "MATCH_CUT", "AUDIO_BRIDGE", "ACTION_MATCH", "ELLIPSIS", "FADE", "DISSOLVE"] | None = None
    speech_policy: Literal["SILENT", "DIALOGUE", "NARRATION", "VOICE_OVER", "SYSTEM_VOICE", "AMBIENCE_ONLY"] | None = None
    shot_complexity: Literal["LOW", "MEDIUM", "HIGH"] | None = None
    state_delta: dict[str, Any] | None = None

    @field_validator("state_delta")
    @classmethod
    def validate_state_delta_payload(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        errors = validate_state_delta_shape(value)
        if errors:
            raise ValueError("; ".join(errors))
        return value

    @field_validator(
        "framing",
        "image_description",
        "action",
        "sound_design",
        "generation_mode",
        "prompt",
        "narrative_purpose",
        "starting_state",
        "main_action",
        "secondary_action",
        "environment_reaction",
        "character_reaction",
        "ending_state",
        "transition_hook",
        "scene_id",
        "story_function",
        "emotional_shift",
        "visual_motif",
    )
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Cannot save empty text.")
        return cleaned


class GenerateReferencePayload(BaseModel):
    """Async Phase A/B image request; media is never approved by generation."""

    kind: Literal["character", "scene", "shot_keyframe"]
    name: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=10, max_length=12_000)
    negative_prompt: str = Field(default="", max_length=4_000)
    character_id: str = Field(default="", max_length=120)
    character_ids: list[str] = Field(default_factory=list, max_length=12)
    scene_id: str = Field(default="", max_length=120)
    shot_number: int | None = Field(default=None, ge=1, le=999)
    revision: int = Field(default=1, ge=1, le=999)
    seed: int | None = Field(default=None, ge=1)

    @field_validator("name", "prompt", "negative_prompt", "character_id", "scene_id")
    @classmethod
    def strip_reference_text(cls, value: str) -> str:
        return value.strip()


UPDATE_SHOT_FIELDS = frozenset(UpdateShotPayload.model_fields)
if UPDATE_SHOT_FIELDS != SHOT_EDITABLE_FIELDS:
    raise RuntimeError("UpdateShotPayload and SHOT_EDITABLE_FIELDS are out of sync.")


class UpdateDialoguePayload(BaseModel):
    """Editable writer output kept separate from visual shot fields."""

    dialogue_book: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    subtitle_track: list[dict[str, Any]] | None = Field(default=None, max_length=20)


class ApproveEditPayload(BaseModel):
    subtitle_mode: Literal["none", "soft", "burned"] = "burned"


class AudioDesignPayload(BaseModel):
    music_mode: Literal["ai", "library", "upload"] = "ai"
    music_intensity: float | None = Field(default=None, ge=0, le=1)
    smart_ducking: bool = True
    music_asset_name: str = Field(default="", max_length=240)
    track_enabled: dict[str, bool] = Field(default_factory=dict)
    track_params: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @field_validator("music_asset_name")
    @classmethod
    def strip_asset_name(cls, value: str) -> str:
        return re.split(r"[\\/]", value.strip())[-1][:240] if value else ""


class FinalLookPayload(BaseModel):
    preset: Literal[
        "original",
        "film_narrative",
        "cool_gray_future",
        "dream_surreal",
        "documentary_desaturated",
        "cyber_night",
    ] = "original"
    intensity: float = Field(default=0.72, ge=0, le=1)
    grain: float = Field(default=0, ge=0, le=1)
    vignette: float = Field(default=0, ge=0, le=1)
    highlight_soften: float = Field(default=0, ge=0, le=1)
    scope: Literal["whole_film", "current_scene", "current_shot"] = "whole_film"
    apply: bool = True


class ExportVideoPayload(BaseModel):
    container: Literal["mp4", "mov", "webm"] = "mp4"
    resolution: Literal["720p", "1080p"] = "1080p"
    aspect: Literal["16:9", "9:16", "1:1"] = "16:9"
    subtitle_mode: Literal["none", "soft", "burned"] = "burned"


class NormalizeResolutionPayload(BaseModel):
    resolution: Literal["720p", "1080p"] = "1080p"
    method: Literal["resolution_normalize", "ai_upscale"] = "resolution_normalize"


def sse_chunk(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def project_not_found(project_id: str) -> JSONResponse:
    return JSONResponse({"error": f"Project {project_id} not found."}, status_code=404)


def invalid_project_id(error: ValueError) -> JSONResponse:
    return JSONResponse({"error": str(error)}, status_code=400)


def invalid_payload(error: ValidationError) -> JSONResponse:
    first = error.errors()[0]
    field = ", ".join(str(part) for part in first.get("loc", ()))
    return JSONResponse(
        {"error": f"Invalid submission: {field} {first.get('msg', 'invalid')}"}, status_code=400
    )


def structured_error_response(error: BaseException, *, status_code: int, stage: str) -> JSONResponse:
    """Return a redacted, machine-readable error for synchronous API calls."""

    info = error_info(error, stage=stage)
    return JSONResponse({"error": info["error_message"], **info}, status_code=status_code)


def serialized_project(project) -> dict[str, Any]:
    """Expose persisted data plus fresh, read-only quality and recovery views."""

    payload = project.to_dict()
    payload = _sanitize_public_payload(payload)
    # Audio providers persist an absolute media path for the editor, while
    # browsers should always use the guarded project-scoped preview endpoint.
    for key, track in (payload.get("audio_tracks") or {}).items():
        if isinstance(track, dict) and track.get("media_path") and Path(str(track["media_path"])).is_file():
            track.setdefault("preview_url", f"/api/projects/{project.project_id}/audio/tracks/{key}")
    payload["video_quality"] = _sanitize_public_payload(quality_snapshot(project, settings.ffprobe_bin))
    payload["screening_preview_url"] = f"/api/projects/{project.project_id}/screening-preview"
    # Diagnostics contain only status, counts, redacted errors and media
    # availability.  Paths and prompts remain inside the project payload's
    # existing compatibility fields and are never copied into this view.
    runtime_state = job_ledger.runtime_state(project.project_id)
    # Always evaluate the public contract against the same persisted Job
    # Ledger snapshot.  This keeps diagnostics, readiness and action guards
    # on one runtime truth even when the snapshot has no active jobs.
    readiness = production_readiness(project, settings, runtime_state=runtime_state)
    diagnostics = diagnostics_snapshot(
        project,
        ffprobe_bin=settings.ffprobe_bin,
        outputs_dir=settings.outputs_dir,
        settings=settings,
        readiness=readiness,
    )
    diagnostics["job"] = job_ledger.summary(project.project_id)
    payload["diagnostics"] = diagnostics
    payload["readiness"] = readiness
    payload["production_action_contract"] = PRODUCTION_ACTION_CONTRACT
    # Compatibility for older clients; new clients consume the versioned envelope.
    payload["production_actions"] = PRODUCTION_ACTIONS
    payload["delivery_preflight"] = delivery_preflight(
        project,
        ffmpeg_ready=_binary_ready(settings.ffmpeg_bin),
        ffprobe_bin=settings.ffprobe_bin,
        outputs_dir=settings.outputs_dir,
    )
    payload["job"] = job_ledger.summary(project.project_id)
    return payload


_INTERNAL_PATH_KEYS = {
    "path",
    "media_path",
    "raw_media_path",
    "root",
    "absolute_path",
    "output_placeholder",
    "video_path",
    "image_path",
    "keyframe_path",
    "ending_frame_path",
    "source_path",
    "character_references",
    "scene_reference",
    "previous_shot_reference",
    "reference_inputs",
    "renderer_manifest",
    "workflow_path",
}


def _sanitize_public_payload(value: Any) -> Any:
    """Remove server filesystem paths while retaining browser-safe metadata."""

    if isinstance(value, list):
        return [_sanitize_public_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        if str(key) in _INTERNAL_PATH_KEYS:
            continue
        result[str(key)] = _sanitize_public_payload(item)
    return result


@app.get("/api/projects/{project_id}/storage")
def get_project_storage(project_id: str) -> dict[str, Any]:
    project = _load_project_or_http(project_id)
    return storage_summary(project, settings.outputs_dir)


@app.post("/api/projects/{project_id}/storage/clean")
def clean_project_working_cache(project_id: str) -> dict[str, Any]:
    with project_lock(project_id):
        project = _load_project_or_http(project_id)
        result = clean_working_cache(project, settings.outputs_dir)
        project.logs.append(f"Media Cache: Cleaned {result['removed_files']} derived working files; original sources preserved.")
        orchestrator.store.save(project)
    return result


def _job_fence(
    request: Request | None,
    project_id: str,
    *,
    kind: str,
    shot_number: int | None = None,
    track_key: str | None = None,
) -> dict[str, str | None]:
    """Build a redacted optimistic fence for a user-submitted operation."""

    idempotency_key = request.headers.get("idempotency-key") if request is not None else None
    try:
        project = orchestrator.store.load(project_id)
        revision = str(getattr(project, "updated_at", "") or "")
    except (FileNotFoundError, ValueError, RuntimeError):
        revision = ""
    fingerprint = json.dumps(
        {"project_revision": revision, "kind": kind, "shot_number": shot_number, "track_key": track_key},
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return {
        "idempotency_key": idempotency_key,
        "project_revision": revision,
        "expected_input_hash": hashlib.sha256(fingerprint).hexdigest(),
    }


def run_with_sse(
    request: Request,
    work: Callable[[Callable[[dict], None]], None],
    *,
    project_id: str | None = None,
    stage: str = "pipeline",
    job_kind: str | None = None,
    shot_number: int | None = None,
    track_key: str | None = None,
) -> StreamingResponse | JSONResponse:
    """Run a blocking call while persisting a reconnectable event ledger.

    SSE is intentionally treated as a disposable transport.  The durable job
    record continues receiving progress after a browser or SSH tunnel drops,
    and a second submission is rejected while the same project is active.
    """
    job_id: str | None = None
    resolved_project_id = project_id
    fence = _job_fence(request, project_id, kind=job_kind or stage, shot_number=shot_number, track_key=track_key) if project_id else {}
    if project_id:
        try:
            started = job_ledger.start(
                project_id,
                kind=job_kind or stage,
                stage=stage,
                shot_number=shot_number,
                track_key=track_key,
                operation_id=None,
                idempotency_key=fence.get("idempotency_key"),
                project_revision=fence.get("project_revision"),
                expected_input_hash=fence.get("expected_input_hash"),
            )
        except JobAlreadyRunning as conflict:
            return JSONResponse(
                {
                    "error": "A production job is already running for this project.",
                    "error_code": "JOB_ALREADY_RUNNING",
                    "stage": stage,
                    "job": conflict.snapshot,
                },
                status_code=409,
            )
        if started.get("idempotent_replay"):
            return JSONResponse({"job": started, "idempotent_replay": True}, status_code=200)
        job_id = started["job_id"]

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    heartbeat_stop = threading.Event()

    def heartbeat_loop() -> None:
        """Keep a live lease during provider calls that emit no progress."""

        while not heartbeat_stop.wait(JOB_HEARTBEAT_INTERVAL_SECONDS):
            if job_id and resolved_project_id:
                job_ledger.heartbeat(resolved_project_id, job_id)

    def emit(payload: dict) -> None:
        """Persist a redacted event before handing it to the live stream."""

        nonlocal job_id, resolved_project_id
        event_payload = dict(payload)
        if resolved_project_id is None:
            resolved_project_id = str(
                event_payload.get("project_id")
                or (event_payload.get("project") or {}).get("project_id")
                or ""
            ) or None
        if job_id is None and resolved_project_id:
            try:
                started = job_ledger.start(
                    resolved_project_id,
                    kind=job_kind or stage,
                    stage=stage,
                    shot_number=shot_number,
                    track_key=track_key,
                    idempotency_key=fence.get("idempotency_key"),
                    project_revision=fence.get("project_revision"),
                    expected_input_hash=fence.get("expected_input_hash"),
                )
                if started.get("idempotent_replay"):
                    event_payload = {"type": "job_replay", "job": started}
                else:
                    job_id = started["job_id"]
            except JobAlreadyRunning as conflict:
                # A create stream can only reach this branch if a client
                # submitted the same newly-created project twice.  Surface the
                # conflict to the caller without leaking the full project.
                event_payload = {
                    "type": "error",
                    "error_code": "JOB_ALREADY_RUNNING",
                    "error_message": "A production job is already running for this project.",
                    "stage": stage,
                    "job": conflict.snapshot,
                }
        if job_id and resolved_project_id:
            persisted = job_ledger.append(resolved_project_id, job_id, event_payload)
            job_ledger.heartbeat(resolved_project_id, job_id)
            event_payload["job_id"] = job_id
            if persisted:
                event_payload["job_event_id"] = persisted["event_id"]
            if event_payload.get("type") == "done":
                finished = job_ledger.finish(resolved_project_id, job_id, status="succeeded")
                if finished:
                    event_payload["job_status"] = finished["status"]
        try:
            loop.call_soon_threadsafe(queue.put_nowait, event_payload)
        except RuntimeError:
            # The request loop may close after a disconnect while the worker
            # is finishing.  The ledger remains authoritative in that case.
            pass

    def worker() -> None:
        heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            name=f"heartbeat-{resolved_project_id or 'pending'}",
            daemon=True,
        )
        heartbeat_thread.start()
        try:
            work(emit)
            if job_id and resolved_project_id:
                job_ledger.finish(resolved_project_id, job_id, status="succeeded")
        except Exception as error:  # noqa: BLE001 - surface every failure to the stream
            info = error_info(error, stage=stage)
            snapshot = None
            if resolved_project_id:
                try:
                    project = orchestrator.store.load(resolved_project_id)
                    # Orchestrator stages may already have recorded a more
                    # specific failure (for example a per-shot retry). Keep
                    # that metadata and avoid incrementing it twice here.
                    existing = getattr(project, "last_error", {}) or {}
                    if getattr(error, "error_code", "") == "PRODUCTION_BLOCKED":
                        info = error_info(error, stage=stage)
                    elif existing.get("error_code") and existing.get("error_message"):
                        info = {
                            **info,
                            **{
                                key: existing[key]
                                for key in (
                                    "error_code",
                                    "error_message",
                                    "stage",
                                    "retry_count",
                                    "recoverable",
                                    "created_at",
                                )
                                if key in existing
                            },
                        }
                    else:
                        info = record_failure(project, error, stage=stage)
                    project.logs.append(
                        f"{stage.replace('_', ' ').title()}: {info['error_code']} · {info['error_message']}"
                    )
                    orchestrator.store.save(project)
                    snapshot = serialized_project(project)
                except Exception:  # noqa: BLE001 - the stream must still close safely
                    snapshot = None
            payload = {"type": "error", **info}
            if snapshot is not None:
                payload["project"] = snapshot
            if job_id and resolved_project_id:
                finished = job_ledger.finish(resolved_project_id, job_id, status="failed", error=info)
                if finished:
                    payload["job_status"] = finished["status"]
            emit(payload)
        finally:
            heartbeat_stop.set()

    threading.Thread(target=worker, daemon=True).start()

    async def stream():
        while True:
            if await request.is_disconnected():
                break
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue
            yield sse_chunk(payload)
            if payload.get("type") in {"done", "error"}:
                break

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/health")
def health() -> dict:
    checks = runtime_checks()
    return {
        "status": "ok",
        "ready": runtime_ready(checks),
        "checks": checks,
        "text_mode": "modelscope" if orchestrator.using_creative_llm else "mock",
        "video_mode": settings.video_generation_mode,
    }


@app.get("/api/health/ready")
def health_ready() -> JSONResponse:
    """Kubernetes-style readiness probe for Spark and hosted deployments."""

    checks = runtime_checks()
    ready = runtime_ready(checks)
    payload = {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "checks": checks,
    }
    return JSONResponse(payload, status_code=200 if payload["ready"] else 503)


@app.get("/api/projects")
def list_projects() -> dict:
    return {
        "projects": orchestrator.store.list_project_ids(),
        "text_mode": "modelscope" if orchestrator.using_creative_llm else "mock",
        "video_mode": settings.video_generation_mode,
    }


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict:
    try:
        return serialized_project(orchestrator.store.load(project_id))
    except FileNotFoundError:
        return project_not_found(project_id)  # type: ignore[return-value]
    except ValueError as error:
        return invalid_project_id(error)  # type: ignore[return-value]
    except RuntimeError as error:
        return structured_error_response(error, status_code=503, stage="storage")  # type: ignore[return-value]


@app.get("/api/projects/{project_id}/diagnostics")
def get_project_diagnostics(project_id: str) -> dict:
    """Return a resumability snapshot without exposing project media paths."""

    try:
        project = orchestrator.store.load(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)  # type: ignore[return-value]
    except ValueError as error:
        return invalid_project_id(error)  # type: ignore[return-value]
    except RuntimeError as error:
        return structured_error_response(error, status_code=503, stage="storage")  # type: ignore[return-value]
    snapshot = diagnostics_snapshot(
        project,
        ffprobe_bin=settings.ffprobe_bin,
        outputs_dir=settings.outputs_dir,
        settings=settings,
    )
    snapshot["job"] = job_ledger.summary(project.project_id)
    return snapshot


@contextmanager
def keep_job_heartbeat(project_id: str, job_id: str):
    """Renew a ledger lease around a blocking non-SSE operation."""

    stop = threading.Event()

    def pulse() -> None:
        while not stop.wait(JOB_HEARTBEAT_INTERVAL_SECONDS):
            job_ledger.heartbeat(project_id, job_id)

    thread = threading.Thread(target=pulse, name=f"heartbeat-{job_id}", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()


@app.get("/api/projects/{project_id}/delivery-preflight")
def get_delivery_preflight(
    project_id: str,
    resolution: Literal["720p", "1080p"] = "1080p",
    aspect: Literal["16:9", "9:16", "1:1"] = "16:9",
    subtitle_mode: Literal["none", "soft", "burned"] = "burned",
) -> dict:
    """Explain export blockers before the user starts a long encode."""

    try:
        project = orchestrator.store.load(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)  # type: ignore[return-value]
    except ValueError as error:
        return invalid_project_id(error)  # type: ignore[return-value]
    except RuntimeError as error:
        return structured_error_response(error, status_code=503, stage="storage")  # type: ignore[return-value]
    return delivery_preflight(
        project,
        resolution=resolution,
        aspect=aspect,
        subtitle_mode=subtitle_mode,
        ffmpeg_ready=_binary_ready(settings.ffmpeg_bin),
        ffprobe_bin=settings.ffprobe_bin,
        outputs_dir=settings.outputs_dir,
    )


@app.get("/api/projects/{project_id}/job")
def get_project_job(project_id: str, after: int = 0, limit: int = 50) -> dict:
    """Return the persisted job status and events after a client cursor."""

    try:
        orchestrator.store.load(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)  # type: ignore[return-value]
    except ValueError as error:
        return invalid_project_id(error)  # type: ignore[return-value]
    except RuntimeError as error:
        return structured_error_response(error, status_code=503, stage="storage")  # type: ignore[return-value]
    return job_ledger.snapshot(project_id, after=after, limit=limit)


@app.post("/api/projects/stream")
async def create_project_stream(request: Request) -> StreamingResponse:
    try:
        payload = CreateProjectPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)  # type: ignore[return-value]
        return JSONResponse({"error": "Request must be valid JSON."}, status_code=400)  # type: ignore[return-value]

    def work(emit: Callable[[dict], None]) -> None:
        project = orchestrator.create_project(
            payload.idea, payload.duration, payload.visual_style, event_callback=emit
        )
        emit({"type": "done", "project": serialized_project(project)})

    return run_with_sse(request, work, job_kind="planning", stage="planning")


@app.patch("/api/projects/{project_id}/script")
async def update_script(project_id: str, request: Request):
    try:
        payload = UpdateDialoguePayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "Request must be valid JSON."}, status_code=400)
    try:
        with project_lock(project_id):
            project = orchestrator.update_dialogue(
                project_id,
                dialogue_book=payload.dialogue_book,
                subtitle_track=payload.subtitle_track,
            )
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return serialized_project(project)


@app.post("/api/projects/{project_id}/script/lock")
def lock_script(project_id: str):
    try:
        with project_lock(project_id):
            project = orchestrator.lock_dialogue(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return serialized_project(project)


@app.post("/api/projects/{project_id}/script/unlock")
def unlock_script(project_id: str):
    try:
        with project_lock(project_id):
            project = orchestrator.unlock_dialogue(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return serialized_project(project)


@app.post("/api/projects/{project_id}/edit/stream")
async def create_rough_cut_stream(project_id: str, request: Request) -> StreamingResponse:
    try:
        raw_payload = await request.json()
        payload = AudioDesignPayload.model_validate(raw_payload or {})
    except (ValidationError, ValueError):
        payload = AudioDesignPayload()
    try:
        orchestrator.store.load(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return invalid_project_id(error)

    def work(emit: Callable[[dict], None]) -> None:
        with project_lock(project_id):
            def on_progress(description: str) -> None:
                try:
                    snapshot = serialized_project(orchestrator.store.load(project_id))
                except Exception:  # noqa: BLE001 - snapshot is best-effort
                    snapshot = None
                emit({"type": "edit_progress", "description": description, "project": snapshot})

            project = orchestrator.create_rough_cut(
                project_id,
                progress_callback=on_progress,
                music_mode=payload.music_mode,
                music_intensity=payload.music_intensity,
                smart_ducking=payload.smart_ducking,
                music_asset_name=payload.music_asset_name,
                track_enabled=payload.track_enabled,
                track_params=payload.track_params,
            )
            emit({"type": "done", "project": serialized_project(project)})

    return run_with_sse(request, work, project_id=project_id, stage="ai_edit", job_kind="ai_edit")


@app.patch("/api/projects/{project_id}/audio/design")
async def update_audio_design(project_id: str, request: Request):
    try:
        payload = AudioDesignPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "Request must be valid JSON."}, status_code=400)
    try:
        with project_lock(project_id):
            project = orchestrator.set_audio_design(
                project_id,
                music_mode=payload.music_mode,
                music_intensity=payload.music_intensity,
                smart_ducking=payload.smart_ducking,
                music_asset_name=payload.music_asset_name,
                track_enabled=payload.track_enabled,
                track_params=payload.track_params,
            )
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return serialized_project(project)


@app.patch("/api/projects/{project_id}/final-look")
async def update_final_look(project_id: str, request: Request):
    try:
        payload = FinalLookPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "Request must be valid JSON."}, status_code=400)
    try:
        with project_lock(project_id):
            project = orchestrator.set_final_look(
                project_id,
                preset=payload.preset,
                intensity=payload.intensity,
                grain=payload.grain,
                vignette=payload.vignette,
                highlight_soften=payload.highlight_soften,
                scope=payload.scope,
                apply=payload.apply,
            )
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except RuntimeError as error:
        return structured_error_response(error, status_code=409, stage="final_look")
    return serialized_project(project)


def _run_audio_track_action(project_id: str, track_key: str, action: str, request: Request | None = None):
    started_job = None
    try:
        with project_lock(project_id):
            project = orchestrator.store.load(project_id)
            ensure_action_ready(
                project,
                settings,
                action,
                track_key=track_key,
                runtime_state=job_ledger.runtime_state(project_id),
            )
            fence = _job_fence(request, project_id, kind="audio_track", track_key=track_key)
            started_job = job_ledger.start(
                project_id,
                kind="audio_track",
                stage="audio",
                track_key=track_key,
                idempotency_key=fence["idempotency_key"],
                project_revision=fence["project_revision"],
                expected_input_hash=fence["expected_input_hash"],
            )
            if started_job.get("idempotent_replay"):
                return JSONResponse({"job": started_job, "idempotent_replay": True}, status_code=200)
            with keep_job_heartbeat(project_id, started_job["job_id"]):
                if action == "REPLAN_AUDIO_TRACK":
                    project = orchestrator.replan_audio_track(project_id, track_key)
                else:
                    project = orchestrator.render_audio_track(project_id, track_key)
            job_ledger.finish(project_id, started_job["job_id"], status="succeeded")
    except FileNotFoundError:
        return project_not_found(project_id)
    except JobAlreadyRunning as error:
        return JSONResponse({"error": str(error), "error_code": "JOB_ALREADY_RUNNING", "job": error.snapshot}, status_code=409)
    except ProductionBlockedError as error:
        return structured_error_response(error, status_code=409, stage="audio")
    except ValueError as error:
        if started_job:
            job_ledger.finish(project_id, started_job["job_id"], status="failed", error=error_info(error, stage="audio"))
        return JSONResponse({"error": str(error)}, status_code=400)
    except Exception as error:  # noqa: BLE001 - keep the durable job truthful
        if started_job:
            job_ledger.finish(project_id, started_job["job_id"], status="failed", error=error_info(error, stage="audio"))
        return structured_error_response(error, status_code=502, stage="audio")
    return serialized_project(project)


@app.post("/api/projects/{project_id}/audio/tracks/{track_key}/replan")
def replan_audio_track(project_id: str, track_key: str, request: Request):
    return _run_audio_track_action(project_id, track_key, "REPLAN_AUDIO_TRACK", request)


@app.post("/api/projects/{project_id}/audio/tracks/{track_key}/render")
def render_audio_track(project_id: str, track_key: str, request: Request):
    return _run_audio_track_action(project_id, track_key, "RENDER_AUDIO_TRACK", request)


@app.post("/api/projects/{project_id}/audio/tracks/{track_key}/regenerate")
def regenerate_audio_track(project_id: str, track_key: str, request: Request):
    """Legacy route; its canonical operation is now REPLAN_AUDIO_TRACK."""

    return _run_audio_track_action(project_id, track_key, "REPLAN_AUDIO_TRACK", request)


@app.post("/api/projects/{project_id}/audio/tracks/voice/generate")
def generate_voice_track(project_id: str):
    """Generate one continuous English voice asset from the locked script."""

    try:
        with project_lock(project_id):
            project = orchestrator.generate_voice_track(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except RuntimeError as error:
        return structured_error_response(error, status_code=409, stage="voice")
    return serialized_project(project)


@app.post("/api/projects/{project_id}/audio/upload")
async def upload_music(project_id: str, request: Request):
    """Accept a raw browser audio upload without requiring multipart extras.

    The client sends the file bytes with an X-Filename header. Keeping this
    endpoint small makes it usable on Spark and leaves the eventual audio
    renderer free to replace the stored source.
    """

    try:
        with project_lock(project_id):
            project = orchestrator.store.load(project_id)
            filename = Path(request.headers.get("x-filename", "uploaded-score")).name
            filename = re.sub(r"[^\w.\- ]+", "_", filename).strip(" .") or "uploaded-score"
            if len(filename) > 120:
                filename = filename[-120:]
            if Path(filename).suffix.lower() not in {".mp3", ".wav", ".m4a", ".aac", ".flac"}:
                return JSONResponse(
                    {"error": "Audio upload must be .mp3, .wav, .m4a, .aac, or .flac."}, status_code=415
                )
            max_bytes = int(getattr(settings, "max_upload_mb", 50) or 50) * 1024 * 1024
            declared_length = request.headers.get("content-length")
            try:
                if declared_length is not None and int(declared_length) > max_bytes:
                    return JSONResponse({"error": f"Audio file must not exceed {max_bytes // (1024 * 1024)} MB."}, status_code=413)
            except ValueError:
                return JSONResponse({"error": "Content-Length must be a valid integer."}, status_code=400)
            audio_dir = settings.outputs_dir / project_id / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            target = audio_dir / filename
            temporary = target.with_name(f".{target.name}.uploading")
            written = 0
            try:
                with temporary.open("wb") as handle:
                    async for chunk in request.stream():
                        written += len(chunk)
                        if written > max_bytes:
                            return JSONResponse({"error": f"Audio file must not exceed {max_bytes // (1024 * 1024)} MB."}, status_code=413)
                        handle.write(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())
                if written == 0:
                    return JSONResponse({"error": "Upload file is empty."}, status_code=400)
                temporary.replace(target)
            finally:
                if temporary.exists():
                    temporary.unlink()
            project = orchestrator.set_audio_design(
                project_id,
                music_mode="upload",
                smart_ducking=bool((project.smart_ducking or {}).get("enabled", True)),
                music_asset_name=filename,
            )
            project.audio_tracks.setdefault("music", {})["preview_url"] = f"/api/projects/{project_id}/audio/tracks/music"
            project.audio_tracks["music"]["media_path"] = str(target)
            project.audio_tracks["music"]["status"] = "FILE READY"
            project.logs.append(f"Sound Design Agent: Received uploaded score {filename}.")
            orchestrator.store.save(project)
    except FileNotFoundError:
        return project_not_found(project_id)
    return serialized_project(project)


@app.post("/api/projects/{project_id}/edit/approve")
async def approve_edit(project_id: str, request: Request):
    try:
        payload = ApproveEditPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "Request must be valid JSON."}, status_code=400)
    try:
        with project_lock(project_id):
            project = orchestrator.store.load(project_id)
            ensure_action_ready(
                project,
                settings,
                "APPROVE_FINAL_CUT",
                runtime_state=job_ledger.runtime_state(project_id),
            )
            project = orchestrator.approve_edit(project_id, payload.subtitle_mode)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ProductionBlockedError as error:
        return structured_error_response(error, status_code=409, stage="final_cut")
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except RuntimeError as error:
        return structured_error_response(error, status_code=502, stage="final_cut")
    return serialized_project(project)


@app.post("/api/projects/{project_id}/media/normalize")
async def normalize_media_resolution(project_id: str, request: Request):
    """Opt-in source normalization before AI Edit; never normalizes a proxy."""

    try:
        payload = NormalizeResolutionPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "Request must be valid JSON."}, status_code=400)
    if payload.method == "ai_upscale":
        return JSONResponse(
            {
                "error": "AI Upscale provider is not configured; use resolution_normalize for a conform only.",
                "error_code": "AI_UPSCALE_PROVIDER_NOT_CONFIGURED",
            },
            status_code=501,
        )
    try:
        with project_lock(project_id):
            project = orchestrator.normalize_resolution(project_id, payload.resolution)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except RuntimeError as error:
        return structured_error_response(error, status_code=409, stage="media")
    return serialized_project(project)


@app.post("/api/projects/{project_id}/render/stream")
async def render_project_stream(project_id: str, request: Request) -> StreamingResponse:
    if settings.video_generation_mode == "mock":
        return JSONResponse(
            {"error": "Currently in mock mode. Select an explicitly configured video provider to enable rendering."},
            status_code=400,
        )
    try:
        orchestrator.store.load(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return invalid_project_id(error)

    def work(emit: Callable[[dict], None]) -> None:
        with project_lock(project_id):
            def on_progress(completed: int, total: int, description: str) -> None:
                try:
                    snapshot = serialized_project(orchestrator.store.load(project_id))
                except Exception:  # noqa: BLE001 - snapshot is best-effort
                    snapshot = None
                emit(
                    {
                        "type": "render_progress",
                        "completed": completed,
                        "total": total,
                        "description": description,
                        "project": snapshot,
                    }
                )

            project = orchestrator.render_project(project_id, progress_callback=on_progress)
            emit({"type": "done", "project": serialized_project(project)})

    return run_with_sse(request, work, project_id=project_id, stage="generation", job_kind="generation")


@app.post("/api/projects/{project_id}/references/generate", status_code=202)
async def generate_reference(project_id: str, request: Request):
    """Submit one Phase A/B image task without blocking the browser request."""

    try:
        payload = GenerateReferencePayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "Request must be valid JSON."}, status_code=400)
    if str(settings.image_generation_mode or "mock").lower() != "modelscope":
        return JSONResponse(
            {"error": "Image generation is disabled. Set IMAGE_GENERATION_MODE=modelscope after provider access is confirmed."},
            status_code=400,
        )
    if payload.kind == "shot_keyframe" and payload.shot_number is None:
        return JSONResponse({"error": "shot_keyframe requires shot_number."}, status_code=400)
    try:
        project = orchestrator.store.load(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return invalid_project_id(error)
    if payload.shot_number is not None and not 1 <= payload.shot_number <= len(project.storyboard):
        return JSONResponse(
            {"error": f"Shot number must be between 1 and {len(project.storyboard)}."},
            status_code=400,
        )

    idempotency_key = f"{project_id}:reference:{payload.kind}:{payload.name}:{project.updated_at}"
    try:
        started = job_ledger.start(
            project_id,
            kind="reference_generation",
            stage="references",
            shot_number=payload.shot_number,
            idempotency_key=idempotency_key,
            project_revision=project.updated_at,
        )
    except JobAlreadyRunning as error:
        return JSONResponse({"error": str(error), "error_code": "JOB_ALREADY_RUNNING", "job": error.snapshot}, status_code=409)
    if started.get("idempotent_replay"):
        return JSONResponse({"job": started}, status_code=200)

    def work() -> None:
        try:
            with project_lock(project_id):
                def on_progress(result: Any) -> None:
                    job_ledger.heartbeat(project_id, started["job_id"])
                    job_ledger.append(
                        project_id,
                        started["job_id"],
                        {
                            "type": "media_progress",
                            "stage": "references",
                            "status": str(getattr(result, "status", "RUNNING")),
                            "description": f"{payload.kind} reference task is {getattr(result, 'status', 'running').lower()}",
                        },
                    )

                asset = generate_reference_image(
                    settings,
                    project_id,
                    ReferenceImageRequest(
                        kind=payload.kind,
                        name=payload.name,
                        prompt=payload.prompt,
                        negative_prompt=payload.negative_prompt,
                        character_id=payload.character_id,
                        character_ids=tuple(payload.character_ids),
                        scene_id=payload.scene_id,
                        shot_number=payload.shot_number,
                        revision=payload.revision,
                        seed=payload.seed,
                    ),
                    on_progress=on_progress,
                )
                project = orchestrator.store.load(project_id)
                if payload.kind == "shot_keyframe" and payload.shot_number is not None:
                    shot = project.storyboard[payload.shot_number - 1]
                    shot.media_generation = {
                        **(shot.media_generation or {}),
                        "shot_id": f"shot-{shot.number:02d}",
                        "keyframe_path": asset.path,
                        "image_path": asset.path,
                        "generation_status": "KEYFRAME_READY_PENDING_REVIEW",
                        "provider_task_id": asset.metadata.get("provider_task_id", ""),
                    }
                project.logs.append(
                    f"Reference Bank: {payload.kind} '{payload.name}' generated and stored as pending visual review."
                )
                orchestrator.store.save(project)
                job_ledger.append(
                    project_id,
                    started["job_id"],
                    {"type": "reference_complete", "stage": "references", "status": "PENDING_REVIEW", "description": f"{payload.kind} reference persisted"},
                )
            job_ledger.finish(project_id, started["job_id"], status="succeeded")
        except Exception as error:  # noqa: BLE001 - persisted job reports the safe failure
            job_ledger.finish(
                project_id,
                started["job_id"],
                status="failed",
                error=error_info(error, stage="references"),
            )

    threading.Thread(target=work, name=f"reference-{project_id}", daemon=True).start()
    return JSONResponse({"job": started}, status_code=202)


def _public_reference(asset: Any) -> dict[str, Any]:
    stale = bool((getattr(asset, "metadata", {}) or {}).get("stale"))
    return {
        "reference_id": str(getattr(asset, "reference_id", "")),
        "kind": str(getattr(asset, "kind", "")),
        "source": str(getattr(asset, "source", "")),
        "approved": bool(getattr(asset, "approved", False)) and not stale,
        "review_status": "STALE" if stale else "APPROVED" if getattr(asset, "approved", False) else str((getattr(asset, "metadata", {}) or {}).get("review_status") or "PENDING_REVIEW"),
        "shot_number": getattr(asset, "shot_number", None),
        "revision": int(getattr(asset, "revision", 1) or 1),
        "created_at": str(getattr(asset, "created_at", "") or ""),
        "character_ids": list(getattr(asset, "character_ids", []) or []),
        "scene_id": str(getattr(asset, "scene_id", "") or ""),
        "role": str(getattr(asset, "role", "") or ""),
    }


@app.get("/api/projects/{project_id}/references")
def list_references(project_id: str) -> dict[str, Any]:
    _load_project_or_http(project_id)
    bank = ReferenceBankStore(settings.outputs_dir).load(project_id)
    return {"project_id": project_id, "references": [_public_reference(asset) for asset in bank.assets]}


@app.post("/api/projects/{project_id}/references/{reference_id}/approve")
def approve_reference(project_id: str, reference_id: str) -> dict[str, Any]:
    _load_project_or_http(project_id)
    try:
        asset = ReferenceBankStore(settings.outputs_dir).set_approval(project_id, reference_id, True)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Reference not found.")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"project_id": project_id, "reference": _public_reference(asset)}


@app.post("/api/projects/{project_id}/references/{reference_id}/reject")
def reject_reference(project_id: str, reference_id: str) -> dict[str, Any]:
    _load_project_or_http(project_id)
    try:
        asset = ReferenceBankStore(settings.outputs_dir).set_approval(project_id, reference_id, False)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Reference not found.")
    return {"project_id": project_id, "reference": _public_reference(asset)}


@app.post("/api/projects/{project_id}/shots/{shot_number}/regenerate")
def regenerate_shot(project_id: str, shot_number: int):
    try:
        with project_lock(project_id):
            project = orchestrator.regenerate_shot(project_id, shot_number)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ProductionBlockedError as error:
        return structured_error_response(error, status_code=409, stage="generation")
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return serialized_project(project)


@app.patch("/api/projects/{project_id}/shots/{shot_number}")
async def update_shot(project_id: str, shot_number: int, request: Request):
    try:
        payload = UpdateShotPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "Request must be valid JSON."}, status_code=400)
    try:
        updates = payload.model_dump(exclude_unset=True)
        with project_lock(project_id):
            project = orchestrator.update_shot(project_id, shot_number, updates)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return serialized_project(project)


@app.post("/api/projects/{project_id}/shots/{shot_number}/render")
def render_single_shot(project_id: str, shot_number: int, request: Request):
    if settings.video_generation_mode == "mock":
        return JSONResponse(
            {"error": "Currently in mock mode. Select an explicitly configured video provider to enable shot generation."},
            status_code=400,
        )
    started_job = None
    try:
        with project_lock(project_id):
            project = orchestrator.store.load(project_id)
            ensure_action_ready(
                project,
                settings,
                "RENDER_SHOT",
                shot_number=shot_number,
                runtime_state=job_ledger.runtime_state(project_id),
            )
            fence = _job_fence(request, project_id, kind="generation", shot_number=shot_number)
            started_job = job_ledger.start(
                project_id,
                kind="generation",
                stage="generation",
                shot_number=shot_number,
                idempotency_key=fence["idempotency_key"],
                project_revision=fence["project_revision"],
                expected_input_hash=fence["expected_input_hash"],
            )
            if started_job.get("idempotent_replay"):
                return JSONResponse({"job": started_job, "idempotent_replay": True}, status_code=200)
            project = orchestrator.render_shot(project_id, shot_number)
            job_ledger.finish(project_id, started_job["job_id"], status="succeeded")
    except FileNotFoundError:
        return project_not_found(project_id)
    except JobAlreadyRunning as error:
        return JSONResponse({"error": str(error), "error_code": "JOB_ALREADY_RUNNING", "job": error.snapshot}, status_code=409)
    except ProductionBlockedError as error:
        if started_job:
            job_ledger.finish(project_id, started_job["job_id"], status="failed", error=error_info(error, stage="generation"))
        return structured_error_response(error, status_code=409, stage="generation")
    except ValueError as error:
        if started_job:
            job_ledger.finish(project_id, started_job["job_id"], status="failed", error=error_info(error, stage="generation"))
        return JSONResponse({"error": str(error)}, status_code=400)
    except Exception as error:  # noqa: BLE001 - surface generation failures to the inspector
        if started_job:
            job_ledger.finish(project_id, started_job["job_id"], status="failed", error=error_info(error, stage="generation"))
        return structured_error_response(error, status_code=502, stage="generation")
    return serialized_project(project)


@app.post("/api/projects/{project_id}/final-master/generate")
def generate_final_master(project_id: str, request: Request):
    """Generate or recover a real Final Master from the approved edit."""

    started_job = None
    try:
        with project_lock(project_id):
            project = orchestrator.store.load(project_id)
            ensure_action_ready(
                project,
                settings,
                "GENERATE_FINAL_MASTER",
                runtime_state=job_ledger.runtime_state(project_id),
            )
            fence = _job_fence(request, project_id, kind="final_master")
            started_job = job_ledger.start(
                project_id,
                kind="final_master",
                stage="final_master",
                idempotency_key=fence["idempotency_key"],
                project_revision=fence["project_revision"],
                expected_input_hash=fence["expected_input_hash"],
            )
            if started_job.get("idempotent_replay"):
                return JSONResponse({"job": started_job, "idempotent_replay": True}, status_code=200)
            with keep_job_heartbeat(project_id, started_job["job_id"]):
                project = orchestrator.generate_final_master(project_id)
            job_ledger.finish(project_id, started_job["job_id"], status="succeeded")
    except FileNotFoundError:
        return project_not_found(project_id)
    except JobAlreadyRunning as error:
        return JSONResponse({"error": str(error), "error_code": "JOB_ALREADY_RUNNING", "job": error.snapshot}, status_code=409)
    except ProductionBlockedError as error:
        if started_job:
            job_ledger.finish(project_id, started_job["job_id"], status="failed", error=error_info(error, stage="final_master"))
        return structured_error_response(error, status_code=409, stage="final_master")
    except ValueError as error:
        if started_job:
            job_ledger.finish(project_id, started_job["job_id"], status="failed", error=error_info(error, stage="final_master"))
        return JSONResponse({"error": str(error)}, status_code=400)
    except Exception as error:  # noqa: BLE001 - keep the durable job truthful
        if started_job:
            job_ledger.finish(project_id, started_job["job_id"], status="failed", error=error_info(error, stage="final_master"))
        return structured_error_response(error, status_code=502, stage="final_master")
    return serialized_project(project)


@app.post("/api/projects/{project_id}/final-master/verify")
def verify_final_master(project_id: str):
    """Inspect the current Final Master asset instead of merely navigating."""

    try:
        with project_lock(project_id):
            project = orchestrator.verify_final_master(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return serialized_project(project)


@app.post("/api/projects/{project_id}/shots/{shot_number}/approve")
def approve_single_shot(project_id: str, shot_number: int):
    """Explicitly approve a shot after the no-vision manual review gate."""

    try:
        with project_lock(project_id):
            project = orchestrator.store.load(project_id)
            ensure_action_ready(
                project,
                settings,
                "APPROVE_SHOT",
                shot_number=shot_number,
                runtime_state=job_ledger.runtime_state(project_id),
            )
            project = orchestrator.approve_shot(project_id, shot_number)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ProductionBlockedError as error:
        return structured_error_response(error, status_code=409, stage="shot_review")
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return serialized_project(project)


@app.post("/api/projects/{project_id}/previs/approve")
def approve_previs(project_id: str):
    """Explicitly approve a storyboard that remained under PREVIS review."""

    try:
        with project_lock(project_id):
            project = orchestrator.store.load(project_id)
            ensure_action_ready(
                project,
                settings,
                "APPROVE_PREVIS",
                runtime_state=job_ledger.runtime_state(project_id),
            )
            project = orchestrator.approve_previs(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ProductionBlockedError as error:
        return structured_error_response(error, status_code=409, stage="previs")
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return serialized_project(project)


@app.get("/api/projects/{project_id}/export/json")
def export_json(project_id: str):
    try:
        paths = orchestrator.store.export(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return invalid_project_id(error)
    except RuntimeError as error:
        return structured_error_response(error, status_code=503, stage="storage")
    return FileResponse(paths[0], filename=f"{project_id}-project.json", media_type="application/json")


@app.get("/api/projects/{project_id}/export/markdown")
def export_markdown(project_id: str):
    try:
        paths = orchestrator.store.export(project_id)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return invalid_project_id(error)
    except RuntimeError as error:
        return structured_error_response(error, status_code=503, stage="storage")
    return FileResponse(
        paths[1], filename=f"{project_id}-movie-plan.md", media_type="text/markdown"
    )


def _load_project_or_http(project_id: str):
    try:
        return orchestrator.store.load(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        info = error_info(error, stage="storage")
        raise HTTPException(status_code=503, detail=info["error_message"]) from error


def _guard_project_media(project_id: str, path: Path, detail: str) -> Path:
    """Keep browser media reads inside the project's output sandbox."""

    resolved = Path(path).resolve()
    allowed_root = (settings.outputs_dir / project_id).resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=detail) from error
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail=detail)
    return resolved


@app.get("/api/projects/{project_id}/subtitles.srt")
def subtitles_srt(project_id: str):
    project = _load_project_or_http(project_id)
    return Response(
        content=render_srt(script_subtitle_track(project.script)).encode("utf-8"),
        media_type="application/x-subrip; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{project_id}-subtitles.srt"'},
    )


@app.get("/api/projects/{project_id}/subtitles.vtt")
def subtitles_vtt(project_id: str):
    project = _load_project_or_http(project_id)
    return Response(
        content=render_vtt(script_subtitle_track(project.script)).encode("utf-8"),
        media_type="text/vtt",
        headers={"Content-Disposition": f'attachment; filename="{project_id}-subtitles.vtt"'},
    )


def _resolve_final_video(project_id: str) -> Path:
    project = _load_project_or_http(project_id)
    if not str(getattr(project, "status", "")).startswith("completed"):
        raise HTTPException(status_code=404, detail="Final cut has not been approved yet.")
    # Serve only the current, non-stale Final Master contract.  A legacy
    # placeholder is accepted by ``best_master_path`` only when no master
    # record exists; stale pointers are never exposed as a finished film.
    path = best_master_path(project)
    if path is None:
        raise HTTPException(status_code=404, detail="Final Master has not been generated yet.")
    return _guard_project_media(project_id, path, "Final Master has not been generated yet.")


def _video_media_type(path: Path) -> str:
    return {
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".webm": "video/webm",
    }.get(path.suffix.lower(), "application/octet-stream")


def _resolve_rough_cut(project_id: str) -> Path:
    project = _load_project_or_http(project_id)
    if str(getattr(project, "status", "")) not in {"editing_rough_cut", "rough_cut_ready"}:
        raise HTTPException(status_code=404, detail="Rough Cut is not available for this project state.")
    if isinstance(getattr(project, "edit_plan", None), dict) and project.edit_plan.get("stale"):
        raise HTTPException(status_code=404, detail="The current Rough Cut is stale and must be regenerated.")
    path = Path(project.rough_cut_placeholder or "")
    # The editor keeps the Rough Cut as a high-quality mezzanine. Serve the
    # browser-safe Screening Preview for playback when one is available.
    if path.suffix.lower() == ".mov":
        screening = (getattr(project, "video_assets", {}) or {}).get("screening_preview")
        screening_path = Path(str(screening.get("path") or "")) if isinstance(screening, dict) else Path()
        if screening_path.is_file():
            path = screening_path
    return _guard_project_media(project_id, path, "Rough Cut has not been rendered to a real video file yet.")


def _resolve_screening_preview(project_id: str) -> Path:
    project = _load_project_or_http(project_id)
    path = best_screening_path(project)
    if not path:
        raise HTTPException(status_code=404, detail="Screening Preview has not been rendered yet.")
    return _guard_project_media(project_id, path, "Screening Preview has not been rendered yet.")


def _shot_previewable(shot: Any) -> bool:
    """A generated shot may be viewed before it is approved for the edit."""

    return shot_previewable(shot)


def _resolve_shot_video(project_id: str, shot_number: int) -> Path:
    project = _load_project_or_http(project_id)
    if not 1 <= shot_number <= len(project.storyboard):
        raise HTTPException(status_code=400, detail="Shot number out of range.")
    shot = project.storyboard[shot_number - 1]
    if not _shot_previewable(shot):
        raise HTTPException(status_code=404, detail="This shot revision is not ready for playback.")
    assets = getattr(shot, "media_assets", {}) or {}
    has_current_record = False
    for key in ("final_master", "source"):
        record = assets.get(key) if isinstance(assets, dict) else None
        if not isinstance(record, dict):
            continue
        has_current_record = True
        if record.get("stale"):
            continue
        path = Path(str(record.get("path") or ""))
        if path.is_file():
            return _guard_project_media(project_id, path, "This shot video has not been generated yet.")
    # Legacy projects may have no media manifest.  Once a manifest exists,
    # however, an invalid/stale record must not silently fall back to an old
    # output placeholder.
    path = Path(str(getattr(shot, "output_placeholder", "") or ""))
    if has_current_record or not path.is_file():
        raise HTTPException(status_code=404, detail="This shot video has not been generated yet.")
    return _guard_project_media(project_id, path, "This shot video has not been generated yet.")


@app.get("/api/projects/{project_id}/final-video")
def final_video(project_id: str):
    path = _resolve_final_video(project_id)
    return FileResponse(path, media_type=_video_media_type(path))


@app.head("/api/projects/{project_id}/final-video")
def final_video_head(project_id: str):
    _resolve_final_video(project_id)
    return Response(status_code=200)


@app.get("/api/projects/{project_id}/screening-preview")
def screening_preview_video(project_id: str):
    path = _resolve_screening_preview(project_id)
    return FileResponse(path, media_type=_video_media_type(path))


@app.head("/api/projects/{project_id}/screening-preview")
def screening_preview_video_head(project_id: str):
    _resolve_screening_preview(project_id)
    return Response(status_code=200)


@app.post("/api/projects/{project_id}/export/video")
async def export_video(project_id: str, request: Request):
    """Encode a user-selected delivery variant from the approved cut."""

    started_job = None
    try:
        payload = ExportVideoPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "Request must be valid JSON."}, status_code=400)
    try:
        with project_lock(project_id):
            project = orchestrator.store.load(project_id)
            try:
                ensure_action_ready(project, settings, "EXPORT", runtime_state=job_ledger.runtime_state(project_id))
            except ProductionBlockedError as error:
                preflight = delivery_preflight(
                    project,
                    resolution=payload.resolution,
                    aspect=payload.aspect,
                    subtitle_mode=payload.subtitle_mode,
                    ffmpeg_ready=_binary_ready(settings.ffmpeg_bin),
                    ffprobe_bin=settings.ffprobe_bin,
                    outputs_dir=settings.outputs_dir,
                )
                return JSONResponse(
                    {
                        "error": str(error),
                        "error_code": "DELIVERY_NOT_READY",
                        "stage": "export",
                        "preflight": preflight,
                        "readiness": production_readiness(project, settings, runtime_state=job_ledger.runtime_state(project_id)),
                        "action": error.action,
                        "blockers": [item.to_dict() for item in error.blockers],
                        "next_actions": list(error.next_actions),
                    },
                    status_code=409,
                )
            preflight = delivery_preflight(
                project,
                resolution=payload.resolution,
                aspect=payload.aspect,
                subtitle_mode=payload.subtitle_mode,
                ffmpeg_ready=_binary_ready(settings.ffmpeg_bin),
                ffprobe_bin=settings.ffprobe_bin,
                outputs_dir=settings.outputs_dir,
            )
            if not preflight["ready"]:
                return JSONResponse(
                    {
                        "error": "Delivery preflight blocked export.",
                        "error_code": "DELIVERY_NOT_READY",
                        "stage": "export",
                        "preflight": preflight,
                    },
                    status_code=409,
                )
            fence = _job_fence(request, project_id, kind="export")
            started_job = job_ledger.start(
                project_id,
                kind="export",
                stage="export",
                mutates_project=False,
                idempotency_key=fence["idempotency_key"],
                project_revision=fence["project_revision"],
                expected_input_hash=fence["expected_input_hash"],
            )
            if started_job.get("idempotent_replay"):
                return JSONResponse({"job": started_job, "idempotent_replay": True}, status_code=200)
            with keep_job_heartbeat(project_id, started_job["job_id"]):
                path = orchestrator.editor.export_variant(project, **payload.model_dump())
            job_ledger.finish(project_id, started_job["job_id"], status="succeeded")
    except FileNotFoundError:
        return project_not_found(project_id)
    except JobAlreadyRunning as error:
        return JSONResponse({"error": str(error), "error_code": "JOB_ALREADY_RUNNING", "job": error.snapshot}, status_code=409)
    except ProductionBlockedError as error:
        return structured_error_response(error, status_code=409, stage="generation")
    except ValueError as error:
        if started_job:
            job_ledger.finish(project_id, started_job["job_id"], status="failed", error=error_info(error, stage="export"))
        return JSONResponse({"error": str(error)}, status_code=400)
    except RuntimeError as error:
        if started_job:
            job_ledger.finish(project_id, started_job["job_id"], status="failed", error=error_info(error, stage="export"))
        return structured_error_response(error, status_code=409, stage="export")
    media_types = {"mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm"}
    return FileResponse(path, filename=path.name, media_type=media_types[payload.container])


@app.get("/api/projects/{project_id}/rough-cut")
def rough_cut_video(project_id: str):
    path = _resolve_rough_cut(project_id)
    return FileResponse(path, media_type=_video_media_type(path))


@app.head("/api/projects/{project_id}/rough-cut")
def rough_cut_video_head(project_id: str):
    _resolve_rough_cut(project_id)
    return Response(status_code=200)


@app.get("/api/projects/{project_id}/shots/{shot_number}/video")
def shot_video(project_id: str, shot_number: int):
    return FileResponse(_resolve_shot_video(project_id, shot_number), media_type="video/mp4")


@app.head("/api/projects/{project_id}/shots/{shot_number}/video")
def shot_video_head(project_id: str, shot_number: int):
    _resolve_shot_video(project_id, shot_number)
    return Response(status_code=200)


@app.get("/api/projects/{project_id}/audio/tracks/{track_key}")
def audio_track_preview(project_id: str, track_key: str):
    """Stream an uploaded/generated track when a real media path exists."""

    project = _load_project_or_http(project_id)
    track = (project.audio_tracks or {}).get(str(track_key).lower()) or {}
    raw_path = track.get("media_path")
    if not raw_path:
        raise HTTPException(status_code=404, detail="This track has no playable audio file yet.")
    path = Path(raw_path).resolve()
    allowed_root = (settings.outputs_dir / project_id).resolve()
    if allowed_root not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Audio preview file not found.")
    media_type = mimetypes.guess_type(path.name)[0] or "audio/mpeg"
    return FileResponse(path, media_type=media_type, filename=path.name)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
