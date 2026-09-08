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
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from movie_agent.services.errors import error_info


_PROJECT_ID = re.compile(r"film-[0-9a-f]{8}")
_SENSITIVE = re.compile(
    r"(?i)(authorization|api[\s_-]?key|access[\s_-]?token|password|secret|token)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"
)
_ACTIVE = {"queued", "running"}
_TERMINAL = {"succeeded", "failed", "cancelled", "orphaned", "recoverable_failed"}
_DEFAULT_LEASE_SECONDS = 180
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
    ``recoverable_failed`` so the UI can offer a truthful resume action instead
    of spinning forever on a dead SSE connection.
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
        job_id = str(payload.get("job_id") or "")
        if re.fullmatch(r"job-[0-9a-f]{12}", job_id):
            history_dir = path.parent / "jobs"
            history_dir.mkdir(parents=True, exist_ok=True)
            history_path = history_dir / f"{job_id}.json"
            history_tmp = history_path.with_suffix(".json.tmp")
            with history_tmp.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
                handle.flush()
                os.fsync(handle.fileno())
            history_tmp.replace(history_path)

    def _reconcile_process_state_locked(self, project_id: str, job: dict[str, Any]) -> bool:
        """Persist the truth when a new process observes a dead active job."""

        if str(job.get("status") or "").lower() not in _ACTIVE:
            return False
        if self._recover_expired_locked(job):
            self._write_locked(project_id, job)
            return True
        job_id = str(job.get("job_id") or "")
        if job_id in self._active:
            return False
        timestamp = _now()
        job["status"] = "recoverable_failed"
        job["updated_at"] = timestamp
        job["finished_at"] = timestamp
        job["recovery_state"] = "RECOVERABLE_FAILED"
        job["recoverable"] = True
        job["error"] = {
            "error_code": "JOB_PROCESS_LOST",
            "error_message": "The production process stopped before this job completed.",
            "recoverable": True,
        }
        self._write_locked(project_id, job)
        return True

    @staticmethod
    def _lease_expires_at(seconds: int = _DEFAULT_LEASE_SECONDS) -> str:
        return (datetime.now(timezone.utc) + timedelta(seconds=max(30, int(seconds)))).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _expired(value: Any) -> bool:
        if not value:
            return False
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return False
        return parsed <= datetime.now(timezone.utc)

    @classmethod
    def _recover_expired_locked(cls, job: dict[str, Any]) -> bool:
        if str(job.get("status") or "").lower() not in _ACTIVE or not cls._expired(job.get("lease_expires_at")):
            return False
        timestamp = _now()
        job["status"] = "recoverable_failed"
        job["updated_at"] = timestamp
        job["finished_at"] = timestamp
        job["recovery_state"] = "RECOVERABLE_FAILED"
        job["recoverable"] = True
        job["error"] = {
            "error_code": "JOB_LEASE_EXPIRED",
            "error_message": "The production job lease expired before completion.",
            "recoverable": True,
        }
        return True

    @staticmethod
    def _new_job(
        project_id: str,
        kind: str,
        stage: str,
        job_id: str | None = None,
        *,
        shot_number: int | None = None,
        track_key: str | None = None,
        mutates_project: bool = True,
        operation_id: str | None = None,
        idempotency_key: str | None = None,
        project_revision: str | int | None = None,
        expected_input_hash: str | None = None,
        lease_seconds: int = _DEFAULT_LEASE_SECONDS,
    ) -> dict[str, Any]:
        timestamp = _now()
        return {
            "schema_version": 1,
            "job_id": job_id or f"job-{uuid.uuid4().hex[:12]}",
            "operation_id": operation_id or f"op-{uuid.uuid4().hex[:16]}",
            "idempotency_key": _safe_text(idempotency_key, 180),
            "project_id": project_id,
            "project_revision": _safe_text(project_revision, 120),
            "expected_input_hash": _safe_text(expected_input_hash, 128),
            "kind": _safe_text(kind, 80) or "pipeline",
            "stage": _safe_text(stage, 80) or _safe_text(kind, 80) or "pipeline",
            "shot_number": _safe_int(shot_number) if shot_number is not None else None,
            "track_key": _safe_text(track_key, 40).lower() or None,
            "mutates_project": bool(mutates_project),
            "status": "running",
            "started_at": timestamp,
            "updated_at": timestamp,
            "finished_at": "",
            "heartbeat_at": timestamp,
            "lease_expires_at": JobLedger._lease_expires_at(lease_seconds),
            "recovery_state": "ACTIVE",
            "event_seq": 0,
            "last_event_type": "",
            "last_description": "",
            "progress": {"completed": 0, "total": 0},
            "error": None,
            "recoverable": True,
            "events": [],
        }

    def start(
        self,
        project_id: str,
        *,
        kind: str = "pipeline",
        stage: str | None = None,
        shot_number: int | None = None,
        track_key: str | None = None,
        mutates_project: bool = True,
        operation_id: str | None = None,
        idempotency_key: str | None = None,
        project_revision: str | int | None = None,
        expected_input_hash: str | None = None,
        lease_seconds: int = _DEFAULT_LEASE_SECONDS,
    ) -> dict[str, Any]:
        """Start a job, rejecting duplicate active submissions safely."""

        with self._lock:
            current = self._read_locked(project_id)
            if current and str(current.get("status")) in _ACTIVE:
                self._reconcile_process_state_locked(project_id, current)
            requested_key = _safe_text(idempotency_key, 180)
            if current and requested_key and requested_key == _safe_text(current.get("idempotency_key"), 180):
                replay = self._public(current, include_events=False)
                replay["idempotent_replay"] = True
                return replay
            if current and str(current.get("status")) in _ACTIVE:
                if str(current.get("job_id") or "") in self._active:
                    raise JobAlreadyRunning(self._public(current, include_events=False))
            if not requested_key:
                target = f"shot:{shot_number}" if shot_number is not None else f"track:{track_key}" if track_key else "project"
                requested_key = f"{project_id}:{kind}:{target}"
            job = self._new_job(
                project_id,
                kind,
                stage or kind,
                shot_number=shot_number,
                track_key=track_key,
                mutates_project=mutates_project,
                operation_id=operation_id,
                idempotency_key=requested_key,
                project_revision=project_revision,
                expected_input_hash=expected_input_hash,
                lease_seconds=lease_seconds,
            )
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
            job["heartbeat_at"] = timestamp
            job["lease_expires_at"] = timestamp
            job["recovery_state"] = terminal.upper()
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
        events = [item for item in (job.get("events") or []) if isinstance(item, dict)]
        public: dict[str, Any] = {
            "job_id": job_id,
            "operation_id": _safe_text(job.get("operation_id"), 100),
            "idempotency_key": _safe_text(job.get("idempotency_key"), 180),
            "project_id": str(job.get("project_id") or ""),
            "project_revision": _safe_text(job.get("project_revision"), 120),
            "expected_input_hash": _safe_text(job.get("expected_input_hash"), 128),
            "kind": _safe_text(job.get("kind"), 80),
            "stage": _safe_text(job.get("stage"), 80),
            "shot_number": _safe_int(job.get("shot_number")) if job.get("shot_number") is not None else None,
            "track_key": _safe_text(job.get("track_key"), 40).lower() or None,
            "mutates_project": bool(job.get("mutates_project", True)),
            "status": status,
            "started_at": _safe_text(job.get("started_at"), 80),
            "updated_at": _safe_text(job.get("updated_at"), 80),
            "finished_at": _safe_text(job.get("finished_at"), 80),
            "heartbeat_at": _safe_text(job.get("heartbeat_at"), 80),
            "lease_expires_at": _safe_text(job.get("lease_expires_at"), 80),
            "recovery_state": _safe_text(job.get("recovery_state"), 40) or ("ACTIVE" if status in _ACTIVE else "TERMINAL"),
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
            available = [event for event in events if _safe_int(event.get("event_id")) > safe_after]
            page = available[:safe_limit]
            public["events"] = page
            public["next_cursor"] = _safe_int(page[-1].get("event_id")) if page else safe_after
            public["has_more"] = len(available) > len(page)
        return public

    def summary(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._read_locked(project_id)
            if job:
                self._reconcile_process_state_locked(project_id, job)
            return self._public(job, include_events=False) if job else None

    def active_count(self) -> int:
        """Count active jobs across projects for the public evaluator cap."""

        count = 0
        with self._lock:
            for path in self.root.glob("film-*/job.json"):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if not isinstance(payload, dict) or str(payload.get("status") or "").lower() not in _ACTIVE:
                    continue
                project_id = str(payload.get("project_id") or "")
                try:
                    if self._reconcile_process_state_locked(project_id, payload):
                        if str(payload.get("status") or "").lower() not in _ACTIVE:
                            continue
                    count += 1
                except ValueError:
                    continue
        return count

    def find_job(self, job_id: str) -> dict[str, Any] | None:
        """Find a public job snapshot without exposing the ledger path."""

        requested = str(job_id or "").strip()
        if not re.fullmatch(r"job-[0-9a-f]{12}", requested):
            return None
        with self._lock:
            candidates = list(self.root.glob("film-*/job.json")) + list(self.root.glob("film-*/jobs/job-*.json"))
            for path in candidates:
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if isinstance(payload, dict) and str(payload.get("job_id") or "") == requested:
                    project_id = str(payload.get("project_id") or "")
                    if path.name == "job.json":
                        try:
                            self._reconcile_process_state_locked(project_id, payload)
                        except ValueError:
                            return None
                    elif str(payload.get("status") or "").lower() in _ACTIVE and requested not in self._active:
                        # Historical active records should only occur after an
                        # interrupted write. Reconcile that copy without
                        # replacing the project's current-job pointer.
                        timestamp = _now()
                        payload["status"] = "recoverable_failed"
                        payload["updated_at"] = timestamp
                        payload["finished_at"] = timestamp
                        payload["recovery_state"] = "RECOVERABLE_FAILED"
                        payload["recoverable"] = True
                        payload["error"] = {
                            "error_code": "JOB_PROCESS_LOST",
                            "error_message": "The production process stopped before this job completed.",
                            "recoverable": True,
                        }
                        temporary = path.with_suffix(".json.tmp")
                        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                        temporary.replace(path)
                    return self._public(payload, include_events=False)
        return None

    def heartbeat(self, project_id: str, job_id: str, *, lease_seconds: int = _DEFAULT_LEASE_SECONDS) -> dict[str, Any] | None:
        """Extend a live operation lease and persist its heartbeat."""

        with self._lock:
            job = self._read_locked(project_id)
            if not job or str(job.get("job_id")) != str(job_id) or str(job.get("status")) not in _ACTIVE:
                return None
            timestamp = _now()
            job["heartbeat_at"] = timestamp
            job["updated_at"] = timestamp
            job["lease_expires_at"] = self._lease_expires_at(lease_seconds)
            self._write_locked(project_id, job)
            return self._public(job, include_events=False)

    def mark_recoverable_failed(self, project_id: str, job_id: str, *, message: str = "The production job requires recovery.") -> dict[str, Any] | None:
        """Close a job explicitly without claiming that its output is valid."""

        with self._lock:
            job = self._read_locked(project_id)
            if not job or str(job.get("job_id")) != str(job_id):
                return None
            timestamp = _now()
            job["status"] = "recoverable_failed"
            job["updated_at"] = timestamp
            job["finished_at"] = timestamp
            job["recovery_state"] = "RECOVERABLE_FAILED"
            job["recoverable"] = True
            job["error"] = {"error_code": "RECOVERABLE_JOB", "error_message": _safe_text(message), "recoverable": True}
            self._active.discard(str(job_id))
            self._write_locked(project_id, job)
            return self._public(job, include_events=False)

    def runtime_state(self, project_id: str) -> dict[str, Any]:
        """Return only active target metadata for readiness evaluation."""

        with self._lock:
            job = self._read_locked(project_id)
            if not job:
                return {"active_jobs": []}
            self._reconcile_process_state_locked(project_id, job)
            public = self._public(job, include_events=False)
            if public.get("status") not in _ACTIVE or public.get("mutates_project") is not True:
                return {"active_jobs": []}
            return {"active_jobs": [public]}

    def assert_input_current(
        self,
        project_id: str,
        job_id: str,
        *,
        project_revision: str | int | None = None,
        expected_input_hash: str | None = None,
    ) -> bool:
        """Check the optimistic input fence before a worker commits output.

        A missing expected value is intentionally treated as unconstrained for
        backwards compatibility.  When a caller supplied a fence, both
        values must still match the durable job record.
        """

        with self._lock:
            job = self._read_locked(project_id)
            if not job or str(job.get("job_id")) != str(job_id):
                return False
            if project_revision is not None and _safe_text(project_revision, 120) != _safe_text(job.get("project_revision"), 120):
                return False
            if expected_input_hash is not None and _safe_text(expected_input_hash, 128) != _safe_text(job.get("expected_input_hash"), 128):
                return False
            return True

    def snapshot(self, project_id: str, *, after: int = 0, limit: int = 50) -> dict[str, Any]:
        with self._lock:
            job = self._read_locked(project_id)
            if not job:
                return {"job": None, "events": [], "next_cursor": 0, "has_more": False}
            self._reconcile_process_state_locked(project_id, job)
            public = self._public(job, include_events=True, after=after, limit=limit)
            events = public.pop("events", [])
            return {"job": public, "events": events, "next_cursor": public.pop("next_cursor", 0), "has_more": public.pop("has_more", False)}

    @contextmanager
    def keepalive(
        self,
        project_id: str,
        job_id: str,
        *,
        interval_seconds: float = 45,
        lease_seconds: int = _DEFAULT_LEASE_SECONDS,
    ):
        """Renew a lease while a worker performs a blocking operation."""

        stop = threading.Event()

        def pulse() -> None:
            while not stop.wait(max(0.1, float(interval_seconds))):
                self.heartbeat(project_id, job_id, lease_seconds=lease_seconds)

        thread = threading.Thread(target=pulse, name=f"heartbeat-{job_id}", daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=max(1.0, min(5.0, float(interval_seconds))))


__all__ = ["JobAlreadyRunning", "JobLedger"]
