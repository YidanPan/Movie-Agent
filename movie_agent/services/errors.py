"""Structured, user-safe failure metadata for long-running film jobs.

The UI needs to distinguish a retryable provider outage from an invalid edit
or a manual-review quality failure.  This module keeps that contract small and
JSON friendly so it works for both synchronous endpoints and SSE workers.
"""

from __future__ import annotations

import re
from typing import Any

from movie_agent.services.revisions import utc_now


_SECRET_PATTERN = re.compile(
    r"(?i)(authorization|api[\s_-]?key|access[\s_-]?token|password|secret|token)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"
)


def _safe_message(error: BaseException) -> str:
    message = str(error).strip() or error.__class__.__name__
    message = _SECRET_PATTERN.sub(lambda match: f"{match.group(1)}=[REDACTED]", message)
    return message[:1_000]


def classify_error(error: BaseException, *, stage: str = "pipeline") -> tuple[str, bool]:
    """Return a stable error code and whether retrying may help."""

    text = _safe_message(error).lower()
    if isinstance(error, (PermissionError,)):
        return "PERMISSION_DENIED", False
    if isinstance(error, (ValueError, TypeError)):
        return "INVALID_INPUT", False
    if isinstance(error, FileNotFoundError) or "not found" in text or "cannot find" in text:
        return "MEDIA_NOT_FOUND", True
    if isinstance(error, TimeoutError) or "timeout" in text or "timed out" in text:
        return "SERVICE_TIMEOUT", True
    if "comfyui" in text or "comfy ui" in text:
        return "COMFYUI_UNAVAILABLE", True
    if "provider" in text or "modelscope" in text or "edge-tts" in text:
        return "PROVIDER_UNAVAILABLE", True
    if "quality" in text or "consistency" in text or "copyright" in text:
        return "QC_FAILED", True
    stage_code = re.sub(r"[^A-Z0-9]+", "_", str(stage or "pipeline").upper()).strip("_") or "PIPELINE"
    return f"{stage_code}_FAILED", True


def error_info(
    error: BaseException,
    *,
    stage: str = "pipeline",
    retry_count: int = 0,
    recoverable: bool | None = None,
) -> dict[str, Any]:
    code, default_recoverable = classify_error(error, stage=stage)
    try:
        safe_retry_count = max(0, int(retry_count or 0))
    except (TypeError, ValueError):
        safe_retry_count = 0
    return {
        "error_code": code,
        "error_message": _safe_message(error),
        "stage": str(stage or "pipeline"),
        "retry_count": safe_retry_count,
        "recoverable": default_recoverable if recoverable is None else bool(recoverable),
        "created_at": utc_now(),
    }


def record_failure(
    target: Any,
    error: BaseException,
    *,
    stage: str = "pipeline",
    recoverable: bool | None = None,
    increment_retry: bool = True,
) -> dict[str, Any]:
    """Persist a failure on a Shot or MovieProject-like object."""

    try:
        current_count = max(0, int(getattr(target, "retry_count", 0) or 0))
    except (TypeError, ValueError):
        current_count = 0
    retry_count = current_count + 1 if increment_retry else current_count
    info = error_info(error, stage=stage, retry_count=retry_count, recoverable=recoverable)
    target.error_code = info["error_code"]
    target.error_message = info["error_message"]
    target.retry_count = retry_count
    target.recoverable = info["recoverable"]
    target.last_error_at = info["created_at"]
    target.last_error = dict(info)
    return info


def clear_failure(target: Any) -> Any:
    """Clear the active error while retaining the retry counter for audit."""

    target.error_code = ""
    target.error_message = ""
    target.recoverable = True
    target.last_error_at = ""
    target.last_error = {}
    return target


__all__ = ["classify_error", "clear_failure", "error_info", "record_failure"]
