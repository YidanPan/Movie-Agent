"""Provider-neutral video generation contracts.

The production pipeline owns shot context, continuity, review, and asset
metadata.  This module owns only the provider boundary.  Importing it is
side-effect free: no network request, model loading, or media generation is
performed until a caller explicitly invokes a provider.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

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


class VideoGenerationProvider(Protocol):
    """The only video contract visible to the generation stage."""

    name: str

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


class RemoteVideoProvider:
    """Fail-closed lifecycle skeleton for future remote video services.

    The wire protocol is intentionally not guessed here.  A concrete remote
    adapter must implement the three task operations for its provider before
    production can be enabled; merely setting an endpoint must never silently
    turn on a fake or incompatible video API.
    """

    name = "remote"

    def __init__(self, settings: Any) -> None:
        self.base_url = str(getattr(settings, "remote_video_api_base", "") or "").strip()
        self.model = str(getattr(settings, "remote_video_model", "") or "").strip()
        self.api_key = str(getattr(settings, "remote_video_api_key", "") or "").strip()
        # A URL and credential are not enough to claim compatibility.  Keep
        # this false until a provider-specific adapter implements its wire
        # protocol and response validation.
        self.protocol_ready = False

    def is_available(self) -> bool:
        return bool(self.protocol_ready and self.base_url and self.model and self.api_key)

    def submit(self, **_: Any) -> str:
        raise VideoGenerationError(
            "Remote video submit protocol is not configured for this provider.",
            code="VIDEO_PROVIDER_NOT_CONFIGURED",
            provider=self.name,
        )

    def poll(self, task_id: str) -> dict[str, Any]:
        del task_id
        raise VideoGenerationError(
            "Remote video poll protocol is not configured for this provider.",
            code="VIDEO_PROVIDER_NOT_CONFIGURED",
            provider=self.name,
        )

    def download(self, result: dict[str, Any], output_dir: Path, filename: str) -> Path:
        del result, output_dir, filename
        raise VideoGenerationError(
            "Remote video download protocol is not configured for this provider.",
            code="VIDEO_PROVIDER_NOT_CONFIGURED",
            provider=self.name,
        )

    def generate(self, **_: Any) -> VideoGenerationResult:
        raise VideoGenerationError(
            "Remote video provider is not configured.",
            code="VIDEO_PROVIDER_NOT_CONFIGURED",
            provider=self.name,
        )


def build_video_provider(settings: Any) -> VideoGenerationProvider:
    """Build the explicitly selected provider; unknown modes fail closed."""

    mode = str(getattr(settings, "video_generation_mode", "mock") or "mock").strip().lower()
    if mode == "mock":
        return MockVideoProvider()
    if mode == "comfyui":
        return ComfyUIVideoProvider(settings)
    if mode == "remote":
        return RemoteVideoProvider(settings)
    raise ValueError(f"Unsupported VIDEO_GENERATION_MODE: {mode}")


__all__ = [
    "ComfyUIVideoProvider",
    "MockVideoProvider",
    "RemoteVideoProvider",
    "VideoGenerationError",
    "VideoGenerationProvider",
    "VideoGenerationResult",
    "build_video_provider",
]
