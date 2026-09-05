"""Movie Agent frontend: FastAPI + SSE, reusing the full MovieOrchestrator pipeline.

Run locally or on Spark:
    python server.py
Then visit http://127.0.0.1:9071 (port follows the PORT env variable).

The Gradio app.py remains a fallback entry point; this server delivers the
complete three-act experience.
"""

from __future__ import annotations

import asyncio
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
from movie_agent.pipeline.jobs import JobAlreadyRunning, JobLedger

settings = Settings.from_env()
orchestrator = MovieOrchestrator(settings)
job_ledger = JobLedger(settings.projects_dir)

STATIC_DIR = Path(__file__).parent / "static"
# Rendering and media mutation is serialized per project, not globally.  A
# long ComfyUI job for one film must not block an unrelated project's edit.
project_locks: dict[str, threading.Lock] = {}
project_locks_guard = threading.Lock()


def project_lock(project_id: str) -> threading.Lock:
    """Return the stable lock for one project (kept process-local for MVP)."""

    key = str(project_id)
    with project_locks_guard:
        return project_locks.setdefault(key, threading.Lock())

app = FastAPI(title="Movie-Agent · AI Film Studio")


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
    character_reaction: str | None = Field(default=None, min_length=1, max_length=1_000)
    ending_state: str | None = Field(default=None, min_length=1, max_length=1_000)
    transition_hook: str | None = Field(default=None, min_length=1, max_length=1_000)

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
        "character_reaction",
        "ending_state",
        "transition_hook",
    )
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Cannot save empty text.")
        return cleaned


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
    # Audio providers persist an absolute media path for the editor, while
    # browsers should always use the guarded project-scoped preview endpoint.
    for key, track in (payload.get("audio_tracks") or {}).items():
        if isinstance(track, dict) and track.get("media_path") and Path(str(track["media_path"])).is_file():
            track.setdefault("preview_url", f"/api/projects/{project.project_id}/audio/tracks/{key}")
    payload["video_quality"] = quality_snapshot(project, settings.ffprobe_bin)
    payload["screening_preview_url"] = f"/api/projects/{project.project_id}/screening-preview"
    # Diagnostics contain only status, counts, redacted errors and media
    # availability.  Paths and prompts remain inside the project payload's
    # existing compatibility fields and are never copied into this view.
    diagnostics = diagnostics_snapshot(
        project,
        ffprobe_bin=settings.ffprobe_bin,
        outputs_dir=settings.outputs_dir,
    )
    diagnostics["job"] = job_ledger.summary(project.project_id)
    payload["diagnostics"] = diagnostics
    payload["delivery_preflight"] = delivery_preflight(
        project,
        ffmpeg_ready=_binary_ready(settings.ffmpeg_bin),
        ffprobe_bin=settings.ffprobe_bin,
        outputs_dir=settings.outputs_dir,
    )
    payload["job"] = job_ledger.summary(project.project_id)
    return payload


def run_with_sse(
    request: Request,
    work: Callable[[Callable[[dict], None]], None],
    *,
    project_id: str | None = None,
    stage: str = "pipeline",
    job_kind: str | None = None,
) -> StreamingResponse | JSONResponse:
    """Run a blocking call while persisting a reconnectable event ledger.

    SSE is intentionally treated as a disposable transport.  The durable job
    record continues receiving progress after a browser or SSH tunnel drops,
    and a second submission is rejected while the same project is active.
    """
    job_id: str | None = None
    resolved_project_id = project_id
    if project_id:
        try:
            started = job_ledger.start(
                project_id,
                kind=job_kind or stage,
                stage=stage,
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
        job_id = started["job_id"]

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

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
                )
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
                    if existing.get("error_code") and existing.get("error_message"):
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
    )
    snapshot["job"] = job_ledger.summary(project.project_id)
    return snapshot


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


@app.post("/api/projects/{project_id}/audio/tracks/{track_key}/regenerate")
def regenerate_audio_track(project_id: str, track_key: str):
    try:
        with project_lock(project_id):
            project = orchestrator.regenerate_audio_track(project_id, track_key)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    return serialized_project(project)


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
            body = await request.body()
            if not body:
                return JSONResponse({"error": "Upload file is empty."}, status_code=400)
            if len(body) > 120 * 1024 * 1024:
                return JSONResponse({"error": "Audio file must not exceed 120 MB."}, status_code=413)
            audio_dir = settings.outputs_dir / project_id / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            target = audio_dir / filename
            target.write_bytes(body)
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
            project = orchestrator.approve_edit(project_id, payload.subtitle_mode)
    except FileNotFoundError:
        return project_not_found(project_id)
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
    try:
        with project_lock(project_id):
            project = orchestrator.normalize_resolution(project_id, payload.resolution)
            if payload.method == "ai_upscale":
                project.logs.append("Media Pipeline: AI Upscale requested; deterministic Resolution Normalize used until an upscaler is configured.")
                orchestrator.store.save(project)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except RuntimeError as error:
        return structured_error_response(error, status_code=409, stage="media")
    return serialized_project(project)


@app.post("/api/projects/{project_id}/render/stream")
async def render_project_stream(project_id: str, request: Request) -> StreamingResponse:
    if settings.video_generation_mode != "comfyui":
        return JSONResponse(
            {"error": "Currently in mock mode. Set VIDEO_GENERATION_MODE=comfyui in Spark's .env to enable rendering."},
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


@app.post("/api/projects/{project_id}/shots/{shot_number}/regenerate")
def regenerate_shot(project_id: str, shot_number: int):
    try:
        with project_lock(project_id):
            project = orchestrator.regenerate_shot(project_id, shot_number)
    except FileNotFoundError:
        return project_not_found(project_id)
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
def render_single_shot(project_id: str, shot_number: int):
    if settings.video_generation_mode != "comfyui":
        return JSONResponse(
            {"error": "Currently in mock mode. Set VIDEO_GENERATION_MODE=comfyui in Spark's .env to enable shot generation."},
            status_code=400,
        )
    try:
        with project_lock(project_id):
            project = orchestrator.render_shot(project_id, shot_number)
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except Exception as error:  # noqa: BLE001 - surface generation failures to the inspector
        return structured_error_response(error, status_code=502, stage="generation")
    return serialized_project(project)


@app.post("/api/projects/{project_id}/shots/{shot_number}/approve")
def approve_single_shot(project_id: str, shot_number: int):
    """Explicitly approve a shot after the no-vision manual review gate."""

    try:
        with project_lock(project_id):
            project = orchestrator.approve_shot(project_id, shot_number)
    except FileNotFoundError:
        return project_not_found(project_id)
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


def _resolve_rough_cut(project_id: str) -> Path:
    project = _load_project_or_http(project_id)
    if str(getattr(project, "status", "")) not in {"editing_rough_cut", "rough_cut_ready"}:
        raise HTTPException(status_code=404, detail="Rough Cut is not available for this project state.")
    if isinstance(getattr(project, "edit_plan", None), dict) and project.edit_plan.get("stale"):
        raise HTTPException(status_code=404, detail="The current Rough Cut is stale and must be regenerated.")
    path = Path(project.rough_cut_placeholder or "")
    return _guard_project_media(project_id, path, "Rough Cut has not been rendered to a real video file yet.")


def _resolve_screening_preview(project_id: str) -> Path:
    project = _load_project_or_http(project_id)
    path = best_screening_path(project)
    if not path:
        raise HTTPException(status_code=404, detail="Screening Preview has not been rendered yet.")
    return _guard_project_media(project_id, path, "Screening Preview has not been rendered yet.")


def _resolve_shot_video(project_id: str, shot_number: int) -> Path:
    project = _load_project_or_http(project_id)
    if not 1 <= shot_number <= len(project.storyboard):
        raise HTTPException(status_code=400, detail="Shot number out of range.")
    shot = project.storyboard[shot_number - 1]
    if bool(getattr(shot, "stale", False)) or not str(getattr(shot, "status", "")).startswith(("generated", "approved")):
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
    return FileResponse(_resolve_final_video(project_id), media_type="video/mp4")


@app.head("/api/projects/{project_id}/final-video")
def final_video_head(project_id: str):
    _resolve_final_video(project_id)
    return Response(status_code=200)


@app.get("/api/projects/{project_id}/screening-preview")
def screening_preview_video(project_id: str):
    return FileResponse(_resolve_screening_preview(project_id), media_type="video/mp4")


@app.head("/api/projects/{project_id}/screening-preview")
def screening_preview_video_head(project_id: str):
    _resolve_screening_preview(project_id)
    return Response(status_code=200)


@app.post("/api/projects/{project_id}/export/video")
async def export_video(project_id: str, request: Request):
    """Encode a user-selected delivery variant from the approved cut."""

    try:
        payload = ExportVideoPayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            return invalid_payload(error)
        return JSONResponse({"error": "Request must be valid JSON."}, status_code=400)
    try:
        with project_lock(project_id):
            project = orchestrator.store.load(project_id)
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
            path = orchestrator.editor.export_variant(project, **payload.model_dump())
    except FileNotFoundError:
        return project_not_found(project_id)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except RuntimeError as error:
        return structured_error_response(error, status_code=409, stage="export")
    media_types = {"mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm"}
    return FileResponse(path, filename=path.name, media_type=media_types[payload.container])


@app.get("/api/projects/{project_id}/rough-cut")
def rough_cut_video(project_id: str):
    return FileResponse(_resolve_rough_cut(project_id), media_type="video/mp4")


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
