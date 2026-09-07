"""Provider-neutral async media jobs used by the V0.3 generation stages.

The planning agents should not know whether a reference image or keyframe was
created by ModelScope, ComfyUI, or a human upload.  This module only owns the
small HTTP contract for an image-generation provider and deliberately keeps
the provider opt-in.  In particular, importing it never performs network I/O.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


class MediaGenerationError(RuntimeError):
    """A safe, user-facing failure from an image/video provider."""

    def __init__(self, message: str, *, provider: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


@dataclass(frozen=True)
class MediaTaskResult:
    """Normalized provider task state; URLs are downloaded before persistence."""

    task_id: str
    status: str
    progress: float | None = None
    output_urls: tuple[str, ...] = ()
    raw: dict[str, Any] | None = None


ProgressCallback = Callable[[MediaTaskResult], None]


class ModelScopeImageProvider:
    """ModelScope API-Inference image task client.

    The public API is asynchronous when ``X-ModelScope-Async-Mode`` is true:
    submit returns a task id, ``/tasks/<id>`` is polled, and the resulting
    image URL is downloaded into the project's persistent Reference Bank.
    """

    name = "modelscope_image_generation"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api-inference.modelscope.cn/v1",
        model: str,
        timeout_seconds: int = 240,
        max_retries: int = 2,
        poll_seconds: float = 5.0,
        max_polls: int = 120,
    ) -> None:
        if not str(api_key or "").strip():
            raise ValueError("ModelScope image generation requires MODELSCOPE_API_KEY.")
        if not str(model or "").strip():
            raise ValueError("ModelScope image generation requires MODELSCOPE_IMAGE_MODEL.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = max(10, int(timeout_seconds))
        self.max_retries = max(1, int(max_retries))
        self.poll_seconds = max(0.5, float(poll_seconds))
        self.max_polls = max(1, int(max_polls))

    def submit(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        reference_urls: list[str] | None = None,
        seed: int | None = None,
    ) -> MediaTaskResult:
        payload: dict[str, Any] = {"model": self.model, "prompt": str(prompt or "")}
        if negative_prompt.strip():
            payload["negative_prompt"] = negative_prompt.strip()
        if reference_urls:
            payload["image_url"] = list(reference_urls)
        if seed is not None:
            payload["seed"] = int(seed)
        response = self._request(
            "POST",
            "/images/generations",
            payload,
            extra_headers={"X-ModelScope-Async-Mode": "true"},
        )
        task_id = response.get("task_id")
        if isinstance(task_id, str) and task_id.strip():
            return MediaTaskResult(task_id=task_id, status="SUBMITTED", raw=response)
        # Some compatible deployments return an image immediately even when
        # async mode is ignored. Treat it as a completed task, not as failure.
        urls = _image_urls(response)
        if urls:
            return MediaTaskResult(task_id="", status="SUCCEED", output_urls=tuple(urls), raw=response)
        raise MediaGenerationError(
            "ModelScope image generation returned neither task_id nor image output.",
            provider=self.name,
        )

    def poll(self, task_id: str) -> MediaTaskResult:
        if not str(task_id or "").strip():
            raise ValueError("An image task id is required for polling.")
        response = self._request(
            "GET",
            f"/tasks/{task_id}",
            None,
            extra_headers={"X-ModelScope-Task-Type": "image_generation"},
        )
        status = str(response.get("task_status") or response.get("status") or "RUNNING").upper()
        progress = _progress(response)
        return MediaTaskResult(
            task_id=task_id,
            status=status,
            progress=progress,
            output_urls=tuple(_image_urls(response)),
            raw=response,
        )

    def wait_for_completion(self, task_id: str, on_progress: ProgressCallback | None = None) -> MediaTaskResult:
        last: MediaTaskResult | None = None
        for _ in range(self.max_polls):
            last = self.poll(task_id)
            if on_progress:
                on_progress(last)
            if last.status in {"SUCCEED", "SUCCESS", "COMPLETED", "DONE"}:
                if not last.output_urls:
                    raise MediaGenerationError(
                        "ModelScope image task completed without an output image.",
                        provider=self.name,
                    )
                return MediaTaskResult(
                    task_id=last.task_id,
                    status="SUCCEED",
                    progress=100.0,
                    output_urls=last.output_urls,
                    raw=last.raw,
                )
            if last.status in {"FAILED", "FAIL", "CANCELLED", "ERROR"}:
                message = _provider_message(last.raw) or "ModelScope image task failed."
                raise MediaGenerationError(message, provider=self.name)
            time.sleep(self.poll_seconds)
        raise MediaGenerationError(
            f"ModelScope image task did not complete after {self.max_polls} polls.",
            provider=self.name,
        )

    def download(self, url: str, destination: Path) -> Path:
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(str(url), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                data = response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, socket.timeout) as error:
            raise MediaGenerationError("ModelScope image output could not be downloaded.", provider=self.name) from error
        if not data:
            raise MediaGenerationError("ModelScope image output was empty.", provider=self.name)
        target.write_bytes(data)
        return target

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **(extra_headers or {}),
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    value = json.loads(response.read().decode("utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("provider response is not an object")
                return value
            except urllib.error.HTTPError as error:
                last_error = error
                # Authentication, request-shape, and missing-model errors are
                # deterministic; retrying them only wastes provider quota.
                if error.code in {400, 401, 403, 404, 422}:
                    raise MediaGenerationError(
                        f"ModelScope image request was rejected (HTTP {error.code}).",
                        provider=self.name,
                        status_code=error.code,
                    ) from error
            except (urllib.error.URLError, TimeoutError, socket.timeout, json.JSONDecodeError, ValueError) as error:
                last_error = error
            if attempt < self.max_retries:
                time.sleep(0.6 * attempt)
        raise MediaGenerationError("ModelScope image request failed after retries.", provider=self.name) from last_error


def _image_urls(payload: dict[str, Any] | None) -> list[str]:
    value = payload or {}
    candidates = value.get("output_images") or value.get("images") or value.get("output_imgs")
    if isinstance(candidates, str):
        candidates = [candidates]
    if not isinstance(candidates, list):
        return []
    urls: list[str] = []
    for item in candidates:
        if isinstance(item, str) and item.strip():
            urls.append(item.strip())
        elif isinstance(item, dict):
            url = item.get("url") or item.get("image_url")
            if isinstance(url, str) and url.strip():
                urls.append(url.strip())
    return urls


def _progress(payload: dict[str, Any] | None) -> float | None:
    value = (payload or {}).get("progress")
    try:
        return max(0.0, min(100.0, float(value))) if value is not None else None
    except (TypeError, ValueError):
        return None


def _provider_message(payload: dict[str, Any] | None) -> str:
    value = payload or {}
    for key in ("message", "error", "task_status_msg", "status_msg"):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()[:300]
        if isinstance(candidate, dict):
            nested = candidate.get("message") or candidate.get("status_msg")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()[:300]
    return ""


__all__ = ["MediaGenerationError", "MediaTaskResult", "ModelScopeImageProvider"]
