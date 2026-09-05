"""Durable, resumable job ledgers for long-running production stages.

The browser's SSE connection is only a view onto a job.  A render or AI Edit
must keep its last safe events when the tab is refreshed, the tunnel drops, or
the process is restarted.  This small JSON ledger intentionally stores status
and progress metadata only; it never stores prompts, media paths, or full
project payloads.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from movie_agent.services.errors import error_info


_PROJECT_ID = re.compile(r"film-[0-9a-f]{8}")
_SENSITIVE = re.compile(
    r"(?i)(authorization|api[\s_-]?key|access[\s_-]?token|password|secret|token)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"
)
_ACTIVE = {"queued", "running"}
_TERMINAL = {"succeeded", "failed", "cancelled", "orphaned"}
_EVENT_KEYS = {
    "type",
    "agent",
    "stage",
    "status",
    "description",
    "message",
    "completed",
    "total",
    "shot",
    "error_code",
    "error_message",
    "recoverable",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = _SENSITIVE.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    return text[:limit]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


class JobAlreadyRunning(RuntimeError):
    """Raised when a second request tries to run the same project stage."""

    def __init__(self, snapshot: dict[str, Any]):
        self.snapshot = snapshot
        super().__init__("A production job is already running for this project.")


class JobLedger:
    """Persist one bounded event journal per project.

    The ledger uses the project's ignored directory, atomic replacement and a
    process-local lock.  A fresh process treats a persisted ``running`` job as
    ``orphaned`` so the UI can offer a truthful resume action instead of
    spinning forever on a dead SSE connection.
    """

    def __init__(self, projects_root: Path, *, max_events: int = 120) -> None:
        self.root = Path(projects_root)
        self.max_events = max(20, int(max_events))
        self._lock = threading.RLock()
        self._active: set[str] = set()

    def _path(self, project_id: str) -> Path:
        value = str(project_id or "")
        if not _PROJECT_ID.fullmatch(value):
            raise ValueError("项目 ID 格式无效。")
        return self.root / value / "job.json"

    def _read_locked(self, project_id: str) -> dict[str, Any] | None:
        path = self._path(project_id)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            # A corrupt job journal must never make the project unavailable.
            # The next request can start a fresh job and replace it safely.
            return None
        return payload if isinstance(payload, dict) else None

    def _write_locked(self, project_id: str, payload: dict[str, Any]) -> None:
        path = self._path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)

    @staticmethod
    def _new_job(project_id: str, kind: str, stage: str, job_id: str | None = None) -> dict[str, Any]:
        timestamp = _now()
        return {
            "schema_version": 1,
            "job_id": job_id or f"job-{uuid.uuid4().hex[:12]}",
            "project_id": project_id,
            "kind": _safe_text(kind, 80) or "pipeline",
            "stage": _safe_text(stage, 80) or _safe_text(kind, 80) or "pipeline",
            "status": "running",
            "started_at": timestamp,
            "updated_at": timestamp,
            "finished_at": "",
            "event_seq": 0,
            "last_event_type": "",
            "last_description": "",
            "progress": {"completed": 0, "total": 0},
            "error": None,
            "recoverable": True,
            "events": [],
        }

    def start(self, project_id: str, *, kind: str = "pipeline", stage: str | None = None) -> dict[str, Any]:
        """Start a job, rejecting duplicate active submissions safely."""

        with self._lock:
            current = self._read_locked(project_id)
            if current and str(current.get("status")) in _ACTIVE:
                current_job = str(current.get("job_id") or "")
                if current_job in self._active:
                    raise JobAlreadyRunning(self._public(current, include_events=False))
                # The previous process disappeared.  Preserve its events in a
                # bounded history only through the next job's metadata, while
                # making the new run explicit and resumable.
                current["status"] = "orphaned"
                current["updated_at"] = _now()
                current["finished_at"] = current.get("updated_at", _now())
                current["recoverable"] = True
                self._write_locked(project_id, current)
            job = self._new_job(project_id, kind, stage or kind)
            self._active.add(job["job_id"])
            self._write_locked(project_id, job)
            return self._public(job, include_events=False)

    def _event(self, payload: dict[str, Any], sequence: int) -> dict[str, Any]:
        event_type = _safe_text(payload.get("type"), 60) or "event"
        event: dict[str, Any] = {
            "event_id": sequence,
            "at": _now(),
            "type": event_type,
        }
        for key in _EVENT_KEYS - {"type", "completed", "total", "shot", "recoverable"}:
            if key in payload:
                value = _safe_text(payload.get(key), 500)
                if value:
                    event[key] = value
        if "completed" in payload:
            event["completed"] = _safe_int(payload.get("completed"))
        if "total" in payload:
            event["total"] = _safe_int(payload.get("total"))
        if isinstance(payload.get("shot"), dict):
            shot = payload["shot"]
            event["shot"] = {
                "number": _safe_int(shot.get("number")),
                "status": _safe_text(shot.get("status"), 80),
            }
        elif payload.get("shot") is not None:
            event["shot"] = _safe_int(payload.get("shot"))
        if "recoverable" in payload:
            event["recoverable"] = bool(payload.get("recoverable"))
        if event.get("error_message"):
            safe = error_info(RuntimeError(event["error_message"]), stage=event.get("stage") or "pipeline")
            event["error_message"] = safe["error_message"]
            event.setdefault("error_code", safe["error_code"])
        return event

    def append(self, project_id: str, job_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Append a safe event and return its public event envelope."""

        with self._lock:
            job = self._read_locked(project_id)
            if not job or str(job.get("job_id")) != str(job_id):
                return None
            sequence = _safe_int(job.get("event_seq")) + 1
            event = self._event(payload, sequence)
            events = [item for item in (job.get("events") or []) if isinstance(item, dict)]
            events.append(event)
            job["events"] = events[-self.max_events :]
            job["event_seq"] = sequence
            job["updated_at"] = event["at"]
            job["last_event_type"] = event["type"]
            job["last_description"] = _safe_text(
                event.get("description") or event.get("message") or event.get("error_message"),
                500,
            )
            if "completed" in event or "total" in event:
                progress = dict(job.get("progress") or {})
                if "completed" in event:
                    progress["completed"] = event["completed"]
                if "total" in event:
                    progress["total"] = event["total"]
                job["progress"] = progress
            if event.get("error_code") or event.get("error_message"):
                job["error"] = {
                    "error_code": _safe_text(event.get("error_code"), 100) or "PIPELINE_FAILED",
                    "error_message": _safe_text(event.get("error_message"), 500),
                    "recoverable": bool(event.get("recoverable", True)),
                }
            self._write_locked(project_id, job)
            return {"job_id": str(job_id), **event}

    def finish(
        self,
        project_id: str,
        job_id: str,
        *,
        status: str = "succeeded",
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Mark a job terminal while retaining its recent event journal."""

        with self._lock:
            job = self._read_locked(project_id)
            if not job or str(job.get("job_id")) != str(job_id):
                self._active.discard(str(job_id))
                return None
            terminal = str(status or "succeeded").lower()
            if terminal not in _TERMINAL:
                terminal = "succeeded"
            timestamp = _now()
            job["status"] = terminal
            job["updated_at"] = timestamp
            job["finished_at"] = timestamp
            if error:
                safe = error_info(
                    RuntimeError(_safe_text(error.get("error_message"), 500)),
                    stage=_safe_text(error.get("stage"), 80) or str(job.get("stage") or "pipeline"),
                    retry_count=_safe_int(error.get("retry_count")),
                )
                job["error"] = {
                    "error_code": _safe_text(error.get("error_code"), 100) or safe["error_code"],
                    "error_message": safe["error_message"],
                    "recoverable": bool(error.get("recoverable", True)),
                }
                job["recoverable"] = bool(error.get("recoverable", True))
            else:
                job["error"] = None
            self._active.discard(str(job_id))
            self._write_locked(project_id, job)
            return self._public(job, include_events=False)

    def _public(self, job: dict[str, Any], *, include_events: bool, after: int = 0, limit: int = 50) -> dict[str, Any]:
        status = str(job.get("status") or "unknown")
        job_id = str(job.get("job_id") or "")
        if status in _ACTIVE and job_id not in self._active:
            status = "orphaned"
        events = [item for item in (job.get("events") or []) if isinstance(item, dict)]
        public: dict[str, Any] = {
            "job_id": job_id,
            "project_id": str(job.get("project_id") or ""),
            "kind": _safe_text(job.get("kind"), 80),
            "stage": _safe_text(job.get("stage"), 80),
            "status": status,
            "started_at": _safe_text(job.get("started_at"), 80),
            "updated_at": _safe_text(job.get("updated_at"), 80),
            "finished_at": _safe_text(job.get("finished_at"), 80),
            "event_seq": _safe_int(job.get("event_seq")),
            "event_count": len(events),
            "last_event_type": _safe_text(job.get("last_event_type"), 60),
            "last_description": _safe_text(job.get("last_description"), 500),
            "progress": {
                "completed": _safe_int((job.get("progress") or {}).get("completed")),
                "total": _safe_int((job.get("progress") or {}).get("total")),
            },
            "error": job.get("error") if isinstance(job.get("error"), dict) else None,
            "recoverable": bool(job.get("recoverable", True)),
        }
        if include_events:
            safe_after = max(0, _safe_int(after))
            safe_limit = min(120, max(1, _safe_int(limit, 50)))
            public["events"] = [event for event in events if _safe_int(event.get("event_id")) > safe_after][:safe_limit]
            public["next_cursor"] = _safe_int(job.get("event_seq"))
            public["has_more"] = any(_safe_int(event.get("event_id")) > safe_after + safe_limit for event in events)
        return public

    def summary(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._read_locked(project_id)
            return self._public(job, include_events=False) if job else None

    def snapshot(self, project_id: str, *, after: int = 0, limit: int = 50) -> dict[str, Any]:
        with self._lock:
            job = self._read_locked(project_id)
            if not job:
                return {"job": None, "events": [], "next_cursor": 0, "has_more": False}
            public = self._public(job, include_events=True, after=after, limit=limit)
            events = public.pop("events", [])
            return {"job": public, "events": events, "next_cursor": public.pop("next_cursor", 0), "has_more": public.pop("has_more", False)}


__all__ = ["JobAlreadyRunning", "JobLedger"]
