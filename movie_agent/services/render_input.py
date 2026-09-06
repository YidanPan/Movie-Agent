"""Canonical renderer input manifests.

The generation service and reconciliation service must fingerprint the same
thing: the prompt, seed, duration, resolved context, and workflow payload that
the renderer actually receives.  This module is deliberately small so that a
new renderer input cannot be added to one code path and forgotten in the
other.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


RENDERER_MANIFEST_VERSION = "1"
DEFAULT_WORKFLOW_IDENTITY = "verified-comfyui-workflow"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    """Return a full SHA-256 digest for a JSON-compatible value."""

    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def workflow_template_digest(workflow_path: Path | str | None) -> str:
    """Digest the complete verified template, including its Movie-Agent manifest."""

    if workflow_path is None:
        return ""
    path = Path(workflow_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return canonical_digest(raw)


def submitted_workflow_digest(workflow: dict[str, Any] | None) -> str:
    """Digest the exact ComfyUI graph after Movie-Agent overrides."""

    return canonical_digest(workflow or {})


@dataclass(frozen=True)
class RendererInputManifest:
    project_id: str
    shot_number: int
    compiled_prompt: str
    derived_seed: int
    source_duration_seconds: int
    generation_mode: str
    workflow_template_digest: str
    submitted_workflow_digest: str
    workflow_identity: str
    context_digest: str

    @property
    def renderer_manifest_version(self) -> str:
        return RENDERER_MANIFEST_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "renderer_manifest_version": self.renderer_manifest_version,
        }

    def fingerprint(self) -> str:
        return canonical_digest(self.to_dict())


def _context_payload(context: Any) -> dict[str, Any]:
    if hasattr(context, "to_dict"):
        value = context.to_dict()
    else:
        value = context or {}
    return value if isinstance(value, dict) else {"value": value}


def _workflow_identity(workflow_path: Path | str | None, requested: str | None) -> str:
    """Keep a filename from becoming the workflow version contract."""

    identity = str(requested or "").strip()
    if identity and not identity.lower().endswith(".json") and "/" not in identity and "\\" not in identity:
        return identity
    if workflow_path is not None:
        try:
            raw = json.loads(Path(workflow_path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        manifest = raw.get("_movie_agent") if isinstance(raw, dict) else None
        if isinstance(manifest, dict):
            for key in ("workflow_identity", "workflow_id"):
                value = manifest.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return DEFAULT_WORKFLOW_IDENTITY


def _default_prompt(project: Any, shot: Any, previous_shot: Any, context: Any) -> str:
    # Lazy import avoids a generation -> render_input -> generation cycle while
    # keeping direct compiler calls identical to GenerationAgent's prompt.
    from movie_agent.agents.generation import build_continuity_prompt

    return build_continuity_prompt(
        shot,
        getattr(project, "visual_bible", {}) or {},
        previous_shot,
        project_id=str(getattr(project, "project_id", "ad-hoc-project") or "ad-hoc-project"),
        context=context,
        story_world=getattr(project, "story_world", {}) or {},
    )


def compile_renderer_input(
    project: Any,
    shot: Any,
    previous_shot: Any | None,
    context: Any,
    workflow_path: Path | str | None,
    *,
    compiled_prompt: str | None = None,
    derived_seed: int | None = None,
    submitted_workflow: dict[str, Any] | None = None,
    workflow_identity: str | None = None,
) -> RendererInputManifest:
    """Compile the single renderer contract used by render and reconciliation."""

    if derived_seed is None:
        from movie_agent.services.continuity import derive_shot_seed

        visual_bible = getattr(project, "visual_bible", {}) or {}
        reference_seed = str(visual_bible.get("reference_seed") or "42")
        derived_seed = derive_shot_seed(
            str(getattr(project, "project_id", "ad-hoc-project") or "ad-hoc-project"),
            reference_seed,
            int(getattr(shot, "number", 0) or 0),
        )
    if compiled_prompt is None:
        compiled_prompt = _default_prompt(project, shot, previous_shot, context)

    if submitted_workflow is None and workflow_path is not None and Path(workflow_path).is_file():
        from movie_agent.services.comfyui import WorkflowOverrides, load_verified_workflow

        submitted_workflow = load_verified_workflow(
            Path(workflow_path),
            WorkflowOverrides(
                prompt=compiled_prompt,
                seed=int(derived_seed),
                duration_seconds=int(
                    getattr(shot, "source_duration_seconds", 0)
                    or getattr(shot, "duration_seconds", 0)
                    or 0
                ),
            ),
        )

    return RendererInputManifest(
        project_id=str(getattr(project, "project_id", "") or ""),
        shot_number=int(getattr(shot, "number", 0) or 0),
        compiled_prompt=str(compiled_prompt or ""),
        derived_seed=int(derived_seed),
        source_duration_seconds=int(
            getattr(shot, "source_duration_seconds", 0)
            or getattr(shot, "duration_seconds", 0)
            or 0
        ),
        generation_mode=str(getattr(shot, "generation_mode", "") or ""),
        workflow_template_digest=workflow_template_digest(workflow_path),
        submitted_workflow_digest=submitted_workflow_digest(submitted_workflow),
        workflow_identity=_workflow_identity(workflow_path, workflow_identity),
        context_digest=canonical_digest(_context_payload(context)),
    )
