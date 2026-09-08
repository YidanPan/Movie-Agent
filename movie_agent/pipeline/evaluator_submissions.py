"""Durable idempotency index for evaluator submissions.

The evaluator endpoint is retried by external harnesses.  The project ledger
prevents duplicate work for one project, but a retry creates a new project id
unless the submission key is indexed independently.  This file stores only a
hashed key and the original job identity; prompts, credentials, and media are
never copied here.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class EvaluatorSubmissionIndex:
    """Single-process, atomically persisted evaluator idempotency index."""

    _registry_guard = threading.Lock()
    _registry: dict[str, threading.RLock] = {}

    def __init__(self, projects_root: Path) -> None:
        self.root = Path(projects_root)
        self.path = self.root / "evaluator-submissions.json"
        key = str(self.path.resolve())
        with self._registry_guard:
            self._lock = self._registry.setdefault(key, threading.RLock())

    @staticmethod
    def _key_hash(key: str) -> str:
        return hashlib.sha256(str(key or "").strip().encode("utf-8")).hexdigest()

    def _read_locked(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        entries = payload.get("entries") if isinstance(payload, dict) else None
        return entries if isinstance(entries, dict) else {}

    def _write_locked(self, entries: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        payload = {"schema_version": 2, "entries": entries}
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(self.path)

    @contextmanager
    def claim_lock(self) -> Iterator[None]:
        """Serialize lookup plus creation for the in-process API workers."""

        with self._lock:
            yield

    def get(self, key: str) -> dict[str, Any] | None:
        key_hash = self._key_hash(key)
        if not key_hash or not str(key or "").strip():
            return None
        with self._lock:
            entry = self._read_locked().get(key_hash)
            return dict(entry) if isinstance(entry, dict) else None

    def reserve(self, key: str, *, project_id: str, job_id: str, request_fingerprint: str = "") -> dict[str, Any]:
        """Return the original entry, or persist this submission atomically."""

        raw = str(key or "").strip()
        if not raw:
            raise ValueError("An evaluator idempotency key is required.")
        key_hash = self._key_hash(raw)
        with self._lock:
            entries = self._read_locked()
            existing = entries.get(key_hash)
            if isinstance(existing, dict):
                existing_fingerprint = str(existing.get("request_fingerprint") or "")
                if existing_fingerprint and request_fingerprint and existing_fingerprint != str(request_fingerprint):
                    raise IdempotencyKeyConflict(dict(existing))
                return dict(existing)
            entry = {
                "key_hash": key_hash,
                "project_id": str(project_id),
                "job_id": str(job_id),
                "status": "running",
                "request_fingerprint": str(request_fingerprint or ""),
            }
            entries[key_hash] = entry
            self._write_locked(entries)
            return dict(entry)


class IdempotencyKeyConflict(RuntimeError):
    """Raised when one idempotency key is reused for different input."""

    def __init__(self, existing: dict[str, Any]):
        self.existing = existing
        super().__init__("This idempotency key was already used for a different payload.")


__all__ = ["EvaluatorSubmissionIndex", "IdempotencyKeyConflict"]
