"""Phase A/B reference and keyframe generation helpers.

This service is deliberately separate from ``GenerationAgent``.  A reference
image is a production asset and must be persisted in the Reference Bank before
it can be selected by a later shot.  New assets are not auto-approved: a
human or a configured visual reviewer still controls promotion into the
approved bank.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from movie_agent.config import Settings
from movie_agent.services.media_generation import MediaGenerationError, ModelScopeImageProvider
from movie_agent.services.continuity import derive_shot_seed
from movie_agent.storage.reference_bank import ReferenceAsset, ReferenceBankStore


@dataclass(frozen=True)
class ReferenceImageRequest:
    kind: str
    name: str
    prompt: str
    negative_prompt: str = ""
    character_id: str = ""
    character_ids: tuple[str, ...] = ()
    scene_id: str = ""
    shot_number: int | None = None
    revision: int = 1
    seed: int | None = None


def generate_reference_image(
    settings: Settings,
    project_id: str,
    request: ReferenceImageRequest,
    *,
    on_progress: Callable[[Any], None] | None = None,
) -> ReferenceAsset:
    """Generate one Phase A/B image and persist it as pending review.

    ``IMAGE_GENERATION_MODE=modelscope`` is the only real image mode in this
    first slice.  The default remains ``mock`` and fails explicitly instead
    of manufacturing a fake image or silently claiming that a reference is
    ready.
    """

    if str(settings.image_generation_mode or "mock").lower() != "modelscope":
        raise MediaGenerationError(
            "Image generation is disabled. Set IMAGE_GENERATION_MODE=modelscope after the provider is approved.",
            provider="image_generation",
        )
    provider = ModelScopeImageProvider(
        settings.modelscope_api_key or "",
        base_url=settings.modelscope_api_base,
        model=settings.modelscope_image_model or "",
        timeout_seconds=settings.modelscope_timeout_seconds,
        max_retries=settings.modelscope_max_retries,
        poll_seconds=settings.media_poll_seconds,
        max_polls=settings.media_max_polls,
    )
    seed = request.seed
    if seed is None and request.shot_number is not None:
        seed = derive_shot_seed(project_id, getattr(settings, "modelscope_image_model", None) or "42", request.shot_number)
    submitted = provider.submit(
        request.prompt,
        negative_prompt=request.negative_prompt,
        seed=seed,
    )
    completed = (
        submitted
        if submitted.status == "SUCCEED"
        else provider.wait_for_completion(submitted.task_id, on_progress=on_progress)
    )
    if not completed.output_urls:
        raise MediaGenerationError("Image generation completed without an image URL.", provider=provider.name)
    with tempfile.TemporaryDirectory(prefix="movie-agent-reference-") as staging:
        source = provider.download(completed.output_urls[0], Path(staging) / "generated.webp")
        store = ReferenceBankStore(settings.outputs_dir)
        asset = store.register_file(
            project_id,
            source,
            kind=request.kind,
            source=f"{provider.name}:{completed.task_id or 'synchronous'}",
            approved=False,
            shot_number=request.shot_number,
            revision=request.revision,
            name=request.name,
            character_id=request.character_id,
            character_ids=list(request.character_ids),
            scene_id=request.scene_id,
            role=request.kind,
            metadata={
                "provider": provider.name,
                "model": provider.model,
                "provider_task_id": completed.task_id,
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "seed": seed,
                "generation_status": "COMPLETED_PENDING_REVIEW",
                "approved": False,
            },
        )
    return asset


__all__ = ["ReferenceImageRequest", "generate_reference_image"]
