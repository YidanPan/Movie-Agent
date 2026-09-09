"""Small, asynchronous evaluator API built on the existing production core."""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

from movie_agent.services.errors import error_info, safe_error_message
from movie_agent.services.media_quality import best_master_path, best_screening_path
from movie_agent.pipeline.evaluator_submissions import EvaluatorSubmissionIndex
from movie_agent.pipeline.jobs import JobCapacityReached


router = APIRouter(prefix="/api/v1", tags=["evaluator"])
PLANNING_PROGRESS_AGENTS = frozenset({"director", "writer", "story_world", "story_beats", "visual_bible", "storyboard", "quality"})


class EvaluatorGeneratePayload(BaseModel):
    idea: str = Field(min_length=10, max_length=2_000)
    duration: int = Field(ge=30, le=80)
    visual_style: str = Field(min_length=2, max_length=80)

    @field_validator("idea", "visual_style")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Must not be empty.")
        return value


def _runtime() -> tuple[Any, Any, Any, Any]:
    """Resolve server globals lazily so TestClient patches and startup stay safe."""

    import server

    return server.orchestrator, server.job_ledger, server.settings, server.serialized_project


def _authorize(settings: Any, authorization: str | None) -> None:
    expected = str(getattr(settings, "evaluator_api_token", "") or "").strip()
    if not expected:
        return
    scheme, _, token = str(authorization or "").partition(" ")
    if scheme.lower() != "bearer" or token.strip() != expected:
        raise HTTPException(status_code=401, detail="Evaluator authorization required.")


def _public_job(ledger: Any, job_id: str) -> dict[str, Any]:
    job = ledger.find_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id": job["job_id"],
        "project_id": job["project_id"],
        "status": job["status"],
        "stage": job["stage"],
        "progress": job.get("progress") or {"completed": 0, "total": 0},
        "updated_at": job.get("updated_at"),
        "error": job.get("error"),
    }


def _submission_fingerprint(payload: EvaluatorGeneratePayload) -> str:
    canonical = json.dumps(
        {"idea": payload.idea, "duration": payload.duration, "visual_style": payload.visual_style},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@router.post("/generate", status_code=202)
async def evaluator_generate(
    request: Request,
    authorization: str | None = Header(default=None),
) -> JSONResponse:
    import server

    orchestrator, ledger, settings, _ = _runtime()
    _authorize(settings, authorization)
    try:
        payload = EvaluatorGeneratePayload.model_validate(await request.json())
    except (ValidationError, ValueError) as error:
        if isinstance(error, ValidationError):
            first = error.errors()[0]
            return JSONResponse(
                {"error": f"Invalid submission: {first.get('msg', 'invalid')}"}, status_code=400
            )
        return JSONResponse({"error": "Request must be valid JSON."}, status_code=400)
    idempotency_key = str(request.headers.get("idempotency-key") or "").strip()
    request_fingerprint = _submission_fingerprint(payload)
    submission_index = EvaluatorSubmissionIndex(settings.projects_dir)

    def replay(existing: dict[str, Any]) -> JSONResponse:
        existing_job = ledger.find_job(str(existing.get("job_id") or ""))
        body = {
            "project_id": str(existing.get("project_id") or ""),
            "job_id": str(existing.get("job_id") or ""),
            "status": str((existing_job or {}).get("status") or existing.get("status") or "recoverable_failed"),
            "idempotent_replay": True,
        }
        return JSONResponse(body, status_code=200)

    # The lookup and first job creation share one process-local lock.  This is
    # enough for the current single-worker deployment and prevents two HTTP
    # retries from creating different projects for one key.
    claim_context = submission_index.claim_lock() if idempotency_key else None
    if claim_context is not None:
        claim_context.__enter__()
    try:
        if idempotency_key:
            existing = submission_index.get(idempotency_key)
            if existing:
                existing_fingerprint = str(existing.get("request_fingerprint") or "")
                if existing_fingerprint and existing_fingerprint != request_fingerprint:
                    return JSONResponse(
                        {"error": "Idempotency key was reused for a different payload.", "error_code": "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"},
                        status_code=409,
                    )
                return replay(existing)
        project_id = f"film-{uuid4().hex[:8]}"
        # Keep the raw caller key out of the job ledger too; the dedicated
        # index stores only its SHA-256 digest.
        ledger_key = f"evaluator:{project_id}"
        try:
            job = ledger.start(
                project_id,
                kind="planning",
                stage="planning",
                idempotency_key=ledger_key,
                mutates_project=True,
                max_active_jobs=server.effective_max_active_jobs(settings),
            )
        except JobCapacityReached:
            return JSONResponse(
                {"error": "Evaluator job capacity has been reached.", "error_code": "JOB_CAPACITY_REACHED"},
                status_code=429,
            )
        except Exception as error:  # pragma: no cover - ledger-specific failures are surfaced safely
            return JSONResponse({"error": safe_error_message(error), "error_code": "JOB_START_FAILED"}, status_code=409)
        if idempotency_key:
            reserved = submission_index.reserve(
                idempotency_key,
                project_id=project_id,
                job_id=str(job["job_id"]),
                request_fingerprint=request_fingerprint,
            )
            if str(reserved.get("project_id")) != project_id:
                # This is defensive for future multi-process implementations;
                # the current lock makes this branch unreachable.
                return replay(reserved)
    finally:
        if claim_context is not None:
            claim_context.__exit__(None, None, None)

    completed_agents = 0

    def emit(event: dict[str, Any]) -> None:
        nonlocal completed_agents
        if str(event.get("type") or "") == "agent_done" and str(event.get("agent") or "") in PLANNING_PROGRESS_AGENTS:
            completed_agents += 1
        ledger.append(
            project_id,
            job["job_id"],
            {
                "type": event.get("type", "planning"),
                "agent": event.get("agent", "planning"),
                "description": event.get("type", "planning progress"),
                "completed": completed_agents,
                "total": 7,
            },
        )
        ledger.heartbeat(project_id, job["job_id"])

    def worker() -> None:
        try:
            with ledger.keepalive(project_id, job["job_id"]):
                orchestrator.create_project(
                    payload.idea,
                    payload.duration,
                    payload.visual_style,
                    event_callback=emit,
                    project_id=project_id,
                )
            ledger.finish(project_id, job["job_id"], status="succeeded")
        except Exception as error:  # noqa: BLE001 - persist a safe terminal state
            ledger.finish(
                project_id,
                job["job_id"],
                status="failed",
                error=error_info(error, stage="planning"),
            )

    threading.Thread(target=worker, name=f"evaluator-{project_id}", daemon=True).start()
    return JSONResponse(
        {"project_id": project_id, "job_id": job["job_id"], "status": "running"}, status_code=202
    )


@router.get("/jobs/{job_id}")
def evaluator_job(job_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _, ledger, settings, _ = _runtime()
    _authorize(settings, authorization)
    return _public_job(ledger, job_id)


@router.get("/projects/{project_id}")
def evaluator_project(project_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    orchestrator, _, settings, serialize = _runtime()
    _authorize(settings, authorization)
    try:
        return serialize(orchestrator.store.load(project_id))
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Project not found.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=safe_error_message(error)) from error


@router.get("/projects/{project_id}/result")
def evaluator_result(project_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    orchestrator, _, settings, _ = _runtime()
    _authorize(settings, authorization)
    try:
        project = orchestrator.store.load(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Project not found.") from error
    if not str(getattr(project, "status", "")).startswith("completed"):
        return {"status": "not_ready", "project_id": project_id, "reason": "FINAL_MASTER_MISSING"}
    master = best_master_path(project)
    if not master or not master.is_file():
        return {"status": "not_ready", "project_id": project_id, "reason": "FINAL_MASTER_MISSING"}
    return {
        "status": "completed",
        "project_id": project_id,
        "final_video_url": f"/api/projects/{project_id}/final-video",
        "screening_preview_url": f"/api/projects/{project_id}/screening-preview" if best_screening_path(project) else None,
        "subtitles_srt_url": f"/api/projects/{project_id}/subtitles.srt",
        "subtitles_vtt_url": f"/api/projects/{project_id}/subtitles.vtt",
    }


__all__ = ["router"]
