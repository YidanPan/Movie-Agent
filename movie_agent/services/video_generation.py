"""Provider-neutral video generation contracts.

The production pipeline owns shot context, continuity, review, and asset
metadata.  This module owns only the provider boundary.  Importing it is
side-effect free: no network request, model loading, or media generation is
performed until a caller explicitly invokes a provider.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from math import ceil
from pathlib import Path
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from movie_agent.services.comfyui import (
    ComfyUIClient,
    ComfyUIError,
    WorkflowOverrides,
    load_verified_workflow,
)


class VideoGenerationError(RuntimeError):
    """A safe, provider-neutral video generation failure."""

    def __init__(self, message: str, *, code: str = "VIDEO_GENERATION_FAILED", provider: str = "") -> None:
        super().__init__(message)
        self.error_code = code
        self.provider = provider


@dataclass(frozen=True)
class VideoGenerationResult:
    """Normalized result returned after a provider has produced real media."""

    provider: str
    task_id: str
    status: str
    video_path: Path
    model: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


ProgressCallback = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class HTTPResponse:
    """Small transport result that keeps the provider easy to test offline."""

    status_code: int
    headers: dict[str, str]
    body: bytes


class HTTPTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None = None,
        timeout: float,
    ) -> HTTPResponse:
        ...


class UrllibHTTPTransport:
    """Dependency-free HTTP transport used only after generation is requested."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None = None,
        timeout: float,
    ) -> HTTPResponse:
        request = Request(url, data=body, headers=headers, method=method.upper())
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is explicit provider config
                return HTTPResponse(
                    status_code=int(response.status),
                    headers={str(key).lower(): str(value) for key, value in response.headers.items()},
                    body=response.read(),
                )
        except HTTPError as error:
            return HTTPResponse(
                status_code=int(error.code),
                headers={str(key).lower(): str(value) for key, value in error.headers.items()},
                body=error.read(),
            )
        except URLError as error:
            raise VideoGenerationError(
                f"Remote video service could not be reached: {error.reason}",
                code="VIDEO_PROVIDER_NETWORK_ERROR",
                provider="dashscope",
            ) from error


class VideoGenerationProvider(Protocol):
    """The only video contract visible to the generation stage."""

    name: str
    # Providers must declare the renderer modes they can actually execute.
    # An empty set is a deliberate fail-closed capability declaration.
    supported_modes: frozenset[str]

    def is_available(self) -> bool:
        ...

    def generate(
        self,
        *,
        prompt: str,
        seed: int | None,
        duration_seconds: float,
        reference_images: list[Path],
        output_dir: Path,
        metadata: dict[str, Any],
        on_progress: ProgressCallback | None = None,
    ) -> VideoGenerationResult:
        ...


class MockVideoProvider:
    """Explicitly disabled media provider used by mock project orchestration.

    Mock mode is allowed to exercise state transitions, but it must never
    invent an MP4 or claim that a placeholder is real video.
    """

    name = "mock"
    supported_modes = frozenset({"T2V"})

    def is_available(self) -> bool:
        return True

    def generate(self, **_: Any) -> VideoGenerationResult:
        raise VideoGenerationError(
            "Mock video generation does not create media files; use the mock pipeline state flow.",
            code="VIDEO_GENERATION_DISABLED",
            provider=self.name,
        )


class ComfyUIVideoProvider:
    """Adapter for the verified, local ComfyUI API workflow."""

    name = "comfyui"
    supported_modes = frozenset({"T2V"})
    accepts_local_reference_images = True

    def __init__(
        self,
        settings: Any,
        client: ComfyUIClient | None = None,
        *,
        workflow_loader: Callable[..., dict[str, Any]] | None = None,
        video_resolver: Callable[[dict[str, Any]], Path] | None = None,
    ) -> None:
        self.settings = settings
        self.client = client or ComfyUIClient(settings.comfy_base_url, settings.comfy_timeout_seconds)
        self.workflow_loader = workflow_loader or load_verified_workflow
        self.video_resolver = video_resolver

    def is_available(self) -> bool:
        return bool(self.client.is_available())

    def generate(
        self,
        *,
        prompt: str,
        seed: int | None,
        duration_seconds: float,
        reference_images: list[Path],
        output_dir: Path,
        metadata: dict[str, Any],
        on_progress: ProgressCallback | None = None,
    ) -> VideoGenerationResult:
        template_path = Path(str(metadata.get("workflow_path") or ""))
        workflow = metadata.get("workflow")
        if not isinstance(workflow, dict):
            if not template_path.is_file():
                raise VideoGenerationError(
                    f"Verified workflow not found: {template_path}.",
                    code="VIDEO_PROVIDER_WORKFLOW_MISSING",
                    provider=self.name,
                )
            uploaded = self._prepare_workflow_references(template_path, reference_images)
            try:
                workflow = self.workflow_loader(
                    template_path,
                    WorkflowOverrides(
                        prompt=prompt,
                        seed=int(seed or 0),
                        duration_seconds=max(1, int(round(duration_seconds))),
                        reference_images=tuple(uploaded),
                    ),
                )
            except (ComfyUIError, OSError, ValueError) as error:
                raise VideoGenerationError(
                    str(error), code="VIDEO_PROVIDER_WORKFLOW_INVALID", provider=self.name
                ) from error
        if not self.is_available():
            raise VideoGenerationError(
                "ComfyUI service is unavailable; please check the local Spark service.",
                code="VIDEO_PROVIDER_UNAVAILABLE",
                provider=self.name,
            )
        if on_progress:
            on_progress({"status": "SUBMITTING", "provider": self.name})
        try:
            task_id = self.client.submit(workflow)
            if on_progress:
                on_progress({"status": "RUNNING", "task_id": task_id, "provider": self.name})
            result = self.client.wait_for_completion(task_id)
            source = self.video_resolver(result) if self.video_resolver else self._resolve_video(result)
            destination_root = Path(output_dir)
            destination_root.mkdir(parents=True, exist_ok=True)
            filename = str(metadata.get("output_filename") or "shot.mp4")
            destination = destination_root / Path(filename).name
            shutil.copy2(source, destination)
        except (ComfyUIError, OSError) as error:
            raise VideoGenerationError(
                str(error), code="VIDEO_PROVIDER_FAILED", provider=self.name
            ) from error
        if on_progress:
            on_progress({"status": "COMPLETED", "task_id": task_id, "provider": self.name})
        return VideoGenerationResult(
            provider=self.name,
            task_id=task_id,
            status="COMPLETED",
            video_path=destination,
            model=str(metadata.get("model") or self.settings.comfy_workflow_template),
            metadata={"source_path": str(source), "workflow_path": str(template_path)},
        )

    def _prepare_workflow_references(self, template_path: Path, reference_images: list[Path]) -> list[str]:
        """Upload only references declared by the verified workflow manifest."""

        if not reference_images:
            return []
        try:
            import json

            raw = json.loads(template_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        manifest = raw.get("_movie_agent") if isinstance(raw, dict) else None
        if not isinstance(manifest, dict) or not manifest.get("reference_inputs"):
            return []
        uploader = getattr(self.client, "upload_image", None)
        if not callable(uploader):
            raise VideoGenerationError(
                "The configured ComfyUI client cannot upload reference images.",
                code="VIDEO_PROVIDER_REFERENCE_UNSUPPORTED",
                provider=self.name,
            )
        return [str(uploader(Path(path))) for path in reference_images]

    def _resolve_video(self, result: dict[str, Any]) -> Path:
        outputs = result.get("outputs")
        if not isinstance(outputs, dict):
            raise ComfyUIError("ComfyUI task returned no output nodes.")
        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            for key in ("images", "videos"):
                files = node_output.get(key)
                if not isinstance(files, list):
                    continue
                for file_info in files:
                    if not isinstance(file_info, dict):
                        continue
                    filename = file_info.get("filename")
                    if not isinstance(filename, str) or not filename.lower().endswith(".mp4"):
                        continue
                    subfolder = file_info.get("subfolder", "")
                    if not isinstance(subfolder, str):
                        continue
                    candidate = Path(self.settings.comfy_output_dir) / subfolder / filename
                    if candidate.is_file():
                        return candidate
        raise ComfyUIError("ComfyUI completed, but no readable MP4 output file was found.")


class DashScopeVideoProvider:
    """Opt-in Wan 2.7 text-to-video adapter for Alibaba Cloud Model Studio.

    The project calls this provider ``remote`` at the configuration boundary
    for backwards compatibility.  The adapter is deliberately T2V-only:
    Model Studio accepts public or temporary media URLs for I2V, while this
    application currently has local reference files and no object-storage
    upload contract.  Silently dropping those files would produce a false
    continuity guarantee, so reference-backed requests fail closed.
    """

    name = "dashscope"
    supported_modes = frozenset({"T2V"})
    accepts_local_reference_images = False
    _synthesis_path = "/api/v1/services/aigc/video-generation/video-synthesis"

    def __init__(
        self,
        settings: Any,
        *,
        transport: HTTPTransport | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        media_validator: Callable[[Path], dict[str, Any]] | None = None,
    ) -> None:
        self.settings = settings
        self.base_url = str(getattr(settings, "remote_video_api_base", "") or "").strip().rstrip("/")
        self.model = str(getattr(settings, "remote_video_model", "") or "").strip()
        self.api_key = str(getattr(settings, "remote_video_api_key", "") or "").strip()
        self.timeout_seconds = max(10.0, float(getattr(settings, "remote_video_timeout_seconds", 900) or 900))
        self.poll_seconds = max(0.5, float(getattr(settings, "remote_video_poll_seconds", 5) or 5))
        self.transport = transport or UrllibHTTPTransport()
        self.sleep_fn = sleep_fn
        self.media_validator = media_validator or self._default_media_validator

    def is_available(self) -> bool:
        """Check only local configuration; never probe or spend credits."""

        parsed = urlparse(self.base_url)
        hostname = str(parsed.hostname or "").lower()
        supported_endpoint = hostname in {
            "dashscope.aliyuncs.com",
            "dashscope-intl.aliyuncs.com",
        } or hostname.endswith(".maas.aliyuncs.com")
        return bool(
            parsed.scheme in {"http", "https"}
            and parsed.netloc
            and supported_endpoint
            and self.model
            and self.api_key
        )

    def _require_configured(self) -> None:
        if not self.is_available():
            raise VideoGenerationError(
                "Remote video provider is not configured. Set REMOTE_VIDEO_API_BASE, "
                "REMOTE_VIDEO_MODEL, and the provider secret before enabling it.",
                code="VIDEO_PROVIDER_NOT_CONFIGURED",
                provider=self.name,
            )

    def _url(self, path: str) -> str:
        self._require_configured()
        base = self.base_url
        if base.endswith("/api/v1"):
            return f"{base}{path.removeprefix('/api/v1')}"
        return f"{base}{path}"

    @staticmethod
    def _response_message(payload: dict[str, Any]) -> str:
        code = str(payload.get("code") or "").strip()
        message = str(payload.get("message") or "").strip()
        if code and message:
            return f"{code}: {message}"[:300]
        return (message or code or "Remote video service returned an error.")[:300]

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        if method.upper() == "POST":
            headers["X-DashScope-Async"] = "enable"
        try:
            response = self.transport.request(
                method,
                self._url(path),
                headers=headers,
                body=body,
                timeout=self.timeout_seconds,
            )
        except VideoGenerationError:
            raise
        except Exception as error:  # noqa: BLE001 - normalize provider boundary
            raise VideoGenerationError(
                f"Remote video request failed: {error}",
                code="VIDEO_PROVIDER_NETWORK_ERROR",
                provider=self.name,
            ) from error
        try:
            decoded = json.loads(response.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError) as error:
            raise VideoGenerationError(
                f"Remote video service returned invalid JSON (HTTP {response.status_code}).",
                code="VIDEO_PROVIDER_INVALID_RESPONSE",
                provider=self.name,
            ) from error
        if not isinstance(decoded, dict):
            raise VideoGenerationError(
                "Remote video service returned an invalid response object.",
                code="VIDEO_PROVIDER_INVALID_RESPONSE",
                provider=self.name,
            )
        if not 200 <= response.status_code < 300:
            raise VideoGenerationError(
                self._response_message(decoded),
                code="VIDEO_PROVIDER_HTTP_ERROR",
                provider=self.name,
            )
        return decoded

    def submit(
        self,
        *,
        prompt: str,
        seed: int | None = None,
        duration_seconds: float = 5,
        reference_images: list[Path] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        self._require_configured()
        if reference_images:
            raise VideoGenerationError(
                "Model Studio I2V requires a public or temporary reference URL; local reference files "
                "are not uploaded by this provider yet.",
                code="VIDEO_PROVIDER_REFERENCE_UNSUPPORTED",
                provider=self.name,
            )
        metadata = metadata or {}
        duration = max(2, min(15, int(round(float(duration_seconds or 5)))))
        resolution = str(metadata.get("target_resolution") or "1080p").strip().upper()
        if resolution not in {"720P", "1080P"}:
            resolution = "1080P"
        ratio = str(metadata.get("aspect") or "16:9").strip()
        if ratio not in {"16:9", "9:16", "1:1", "4:3", "3:4"}:
            ratio = "16:9"
        parameters: dict[str, Any] = {
            "resolution": resolution,
            "ratio": ratio,
            # The prompt is already compiled by Movie-Agent; do not rewrite it
            # behind the user's back and invalidate continuity review.
            "prompt_extend": False,
            "watermark": False,
            "duration": duration,
        }
        if seed is not None:
            parameters["seed"] = max(0, min(2_147_483_647, int(seed)))
        input_payload: dict[str, Any] = {"prompt": str(prompt or "")}
        negative_prompt = str(metadata.get("negative_prompt") or "").strip()
        if negative_prompt:
            input_payload["negative_prompt"] = negative_prompt[:500]
        response = self._request_json(
            "POST",
            self._synthesis_path,
            {"model": self.model, "input": input_payload, "parameters": parameters},
        )
        output = response.get("output")
        task_id = output.get("task_id") if isinstance(output, dict) else None
        if not isinstance(task_id, str) or not task_id.strip():
            raise VideoGenerationError(
                "Remote video service did not return a task_id.",
                code="VIDEO_PROVIDER_INVALID_RESPONSE",
                provider=self.name,
            )
        return task_id.strip()

    def poll(self, task_id: str) -> dict[str, Any]:
        task_id = str(task_id or "").strip()
        if not task_id:
            raise VideoGenerationError(
                "Remote video task_id is empty.",
                code="VIDEO_PROVIDER_INVALID_RESPONSE",
                provider=self.name,
            )
        response = self._request_json("GET", f"/api/v1/tasks/{quote(task_id, safe='')}")
        output = response.get("output")
        if not isinstance(output, dict):
            raise VideoGenerationError(
                "Remote video task response has no output object.",
                code="VIDEO_PROVIDER_INVALID_RESPONSE",
                provider=self.name,
            )
        status = str(output.get("task_status") or "UNKNOWN").upper()
        return {
            "task_id": str(output.get("task_id") or task_id),
            "task_status": status,
            "status": status,
            "video_url": str(output.get("video_url") or "").strip(),
            "error_code": str(output.get("code") or response.get("code") or "").strip(),
            "error_message": str(output.get("message") or response.get("message") or "").strip()[:300],
        }

    def download(self, result: dict[str, Any], output_dir: Path, filename: str) -> Path:
        self._require_configured()
        url = str(result.get("video_url") or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise VideoGenerationError(
                "Remote video task completed without a valid video URL.",
                code="VIDEO_PROVIDER_INVALID_RESPONSE",
                provider=self.name,
            )
        try:
            response = self.transport.request(
                "GET",
                url,
                # Signed result URLs do not need the API key. Avoid forwarding
                # the bearer secret to an object-storage host.
                headers={"Accept": "video/mp4"},
                timeout=self.timeout_seconds,
            )
        except VideoGenerationError:
            raise
        except Exception as error:  # noqa: BLE001 - normalize provider boundary
            raise VideoGenerationError(
                f"Remote video download failed: {error}",
                code="VIDEO_PROVIDER_NETWORK_ERROR",
                provider=self.name,
            ) from error
        if not 200 <= response.status_code < 300 or not response.body:
            raise VideoGenerationError(
                f"Remote video download failed (HTTP {response.status_code}).",
                code="VIDEO_PROVIDER_DOWNLOAD_FAILED",
                provider=self.name,
            )
        destination_root = Path(output_dir)
        destination_root.mkdir(parents=True, exist_ok=True)
        destination = destination_root / Path(filename or "shot.mp4").name
        if destination.suffix.lower() != ".mp4":
            destination = destination.with_suffix(".mp4")
        destination.write_bytes(response.body)
        validation = self.media_validator(destination)
        if not validation.get("valid", False):
            raise VideoGenerationError(
                "Downloaded remote video failed media validation.",
                code="VIDEO_PROVIDER_INVALID_MEDIA",
                provider=self.name,
            )
        return destination

    def _default_media_validator(self, path: Path) -> dict[str, Any]:
        """Require ffprobe-confirmed video metadata when no test hook is used."""

        from movie_agent.services.media_quality import probe_media

        metadata = probe_media(path, str(getattr(self.settings, "ffprobe_bin", "ffprobe") or "ffprobe"))
        return {
            "valid": bool(
                metadata.get("exists")
                and metadata.get("width")
                and metadata.get("height")
                and metadata.get("duration_seconds")
            ),
            **metadata,
        }

    def generate(
        self,
        *,
        prompt: str,
        seed: int | None,
        duration_seconds: float,
        reference_images: list[Path],
        output_dir: Path,
        metadata: dict[str, Any],
        on_progress: ProgressCallback | None = None,
    ) -> VideoGenerationResult:
        task_id = self.submit(
            prompt=prompt,
            seed=seed,
            duration_seconds=duration_seconds,
            reference_images=reference_images,
            metadata=metadata,
        )
        if on_progress:
            on_progress({"status": "SUBMITTED", "provider": self.name, "task_id": task_id})
        max_polls = max(1, int(ceil(self.timeout_seconds / self.poll_seconds)))
        last_result: dict[str, Any] = {}
        for poll_number in range(max_polls):
            last_result = self.poll(task_id)
            status = str(last_result.get("task_status") or "UNKNOWN").upper()
            if on_progress:
                on_progress({
                    "status": status,
                    "provider": self.name,
                    "task_id": task_id,
                    "poll": poll_number + 1,
                    "max_polls": max_polls,
                })
            if status == "SUCCEEDED":
                destination = self.download(
                    last_result,
                    output_dir,
                    str(metadata.get("output_filename") or "shot.mp4"),
                )
                validation = self.media_validator(destination)
                if on_progress:
                    on_progress({"status": "COMPLETED", "provider": self.name, "task_id": task_id})
                return VideoGenerationResult(
                    provider=self.name,
                    task_id=task_id,
                    status="COMPLETED",
                    video_path=destination,
                    model=self.model,
                    metadata={
                        "download_url": str(last_result.get("video_url") or ""),
                        "task_status": status,
                        "media_validation": validation,
                    },
                )
            if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                detail = str(last_result.get("error_message") or last_result.get("error_code") or status)
                raise VideoGenerationError(
                    f"Remote video task {task_id} {status.lower()}: {detail}",
                    code="VIDEO_PROVIDER_TASK_FAILED" if status != "UNKNOWN" else "VIDEO_PROVIDER_TASK_EXPIRED",
                    provider=self.name,
                )
            if poll_number + 1 < max_polls:
                self.sleep_fn(self.poll_seconds)
        raise VideoGenerationError(
            f"Remote video task {task_id} did not complete within the configured timeout.",
            code="VIDEO_PROVIDER_TIMEOUT",
            provider=self.name,
        )


class RemoteVideoProvider(DashScopeVideoProvider):
    """Backward-compatible name for the concrete remote Model Studio adapter."""


def build_video_provider(settings: Any) -> VideoGenerationProvider:
    """Build the explicitly selected provider; unknown modes fail closed."""

    mode = str(getattr(settings, "video_generation_mode", "mock") or "mock").strip().lower()
    if mode == "mock":
        return MockVideoProvider()
    if mode == "comfyui":
        return ComfyUIVideoProvider(settings)
    if mode in {"remote", "dashscope", "modelstudio"}:
        return DashScopeVideoProvider(settings)
    raise ValueError(f"Unsupported VIDEO_GENERATION_MODE: {mode}")


__all__ = [
    "ComfyUIVideoProvider",
    "DashScopeVideoProvider",
    "HTTPResponse",
    "HTTPTransport",
    "MockVideoProvider",
    "RemoteVideoProvider",
    "UrllibHTTPTransport",
    "VideoGenerationError",
    "VideoGenerationProvider",
    "VideoGenerationResult",
    "build_video_provider",
]
