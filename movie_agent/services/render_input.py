"""Canonical renderer contracts and truthful renderer-input fingerprints."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


RENDERER_MANIFEST_VERSION = "1"
DEFAULT_WORKFLOW_IDENTITY = "verified-comfyui-workflow"
CONTRACT_READY = "READY"
WORKFLOW_MISSING = "WORKFLOW_MISSING"
WORKFLOW_INVALID = "WORKFLOW_INVALID"
WORKFLOW_COMPILE_FAILED = "WORKFLOW_COMPILE_FAILED"
UNSUPPORTED_GENERATION_MODE = "UNSUPPORTED_GENERATION_MODE"


class RendererContractUnavailable(RuntimeError):
    """The current renderer contract could not be verified or compiled."""

    def __init__(self, status: str, message: str, errors: list[str] | None = None) -> None:
        self.status = str(status)
        self.errors = list(errors or [message])
        super().__init__(message)


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


def _read_workflow_template(workflow_path: Path | str | None) -> dict[str, Any]:
    if workflow_path is None or not Path(workflow_path).is_file():
        raise RendererContractUnavailable(WORKFLOW_MISSING, "The verified renderer workflow is missing.")
    try:
        raw = json.loads(Path(workflow_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RendererContractUnavailable(WORKFLOW_INVALID, "The renderer workflow JSON could not be read.") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("_movie_agent"), dict):
        raise RendererContractUnavailable(WORKFLOW_INVALID, "The renderer workflow lacks a valid _movie_agent manifest.")
    return raw


def workflow_template_digest(workflow_path: Path | str | None) -> str:
    """Digest the complete verified template, including its Movie-Agent manifest."""

    try:
        return canonical_digest(_read_workflow_template(workflow_path))
    except RendererContractUnavailable:
        return ""


def submitted_workflow_digest(workflow: dict[str, Any] | None) -> str:
    """Digest the exact ComfyUI graph after Movie-Agent overrides."""

    return canonical_digest(workflow) if isinstance(workflow, dict) else ""


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
    external_input_digests: dict[str, str] = field(default_factory=dict)
    valid: bool = True
    errors: tuple[str, ...] = ()
    contract_status: str = CONTRACT_READY

    @property
    def renderer_manifest_version(self) -> str:
        return RENDERER_MANIFEST_VERSION

    @property
    def compiled_prompt_digest(self) -> str:
        return canonical_digest(self.compiled_prompt) if self.compiled_prompt else ""

    def audit_dict(self) -> dict[str, Any]:
        """Return human-auditable metadata without duplicating the full prompt."""

        return {
            "project_id": self.project_id,
            "shot_number": self.shot_number,
            "workflow_identity": self.workflow_identity,
            "workflow_template_digest": self.workflow_template_digest,
            "submitted_workflow_digest": self.submitted_workflow_digest,
            "compiled_prompt_digest": self.compiled_prompt_digest,
            "derived_seed": self.derived_seed,
            "source_duration_seconds": self.source_duration_seconds,
            "generation_mode": self.generation_mode,
            "context_digest": self.context_digest,
            "external_input_digests": dict(self.external_input_digests),
            "renderer_manifest_version": self.renderer_manifest_version,
            "valid": bool(self.valid),
            "errors": list(self.errors),
            "contract_status": self.contract_status,
        }

    def fingerprint_payload(self) -> dict[str, Any]:
        """Return only facts that change the submitted renderer execution."""

        return {
            "submitted_workflow_digest": self.submitted_workflow_digest,
            "external_input_digests": dict(sorted(self.external_input_digests.items())),
        }

    def to_dict(self) -> dict[str, Any]:
        """Backward-compatible alias for the compact audit representation."""

        return self.audit_dict()

    def fingerprint(self) -> str:
        if not self.valid or not self.submitted_workflow_digest:
            raise RendererContractUnavailable(
                self.contract_status,
                "Renderer input cannot be fingerprinted because the contract is unavailable.",
                list(self.errors) or ["submitted_workflow_digest is missing"],
            )
        return canonical_digest(self.fingerprint_payload())


def _context_payload(context: Any) -> dict[str, Any]:
    if hasattr(context, "to_dict"):
        value = context.to_dict()
    else:
        value = context or {}
    return value if isinstance(value, dict) else {"value": value}


def _workflow_identity(workflow_path: Path | str | None, requested: str | None, raw: dict[str, Any]) -> str:
    """Keep a filename from becoming the workflow version contract."""

    identity = str(requested or "").strip()
    if identity and not identity.lower().endswith(".json") and "/" not in identity and "\\" not in identity:
        return identity
    manifest = raw.get("_movie_agent") if isinstance(raw, dict) else None
    if isinstance(manifest, dict):
        for key in ("workflow_identity", "workflow_id"):
            value = manifest.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return DEFAULT_WORKFLOW_IDENTITY


def _default_prompt(project: Any, shot: Any, previous_shot: Any, context: Any, film_language: str) -> str:
    # Lazy import avoids a generation -> render_input -> generation cycle while
    # keeping direct compiler calls identical to GenerationAgent's prompt.
    from movie_agent.agents.generation import build_continuity_prompt

    return build_continuity_prompt(
        shot,
        getattr(project, "visual_bible", {}) or {},
        previous_shot,
        project_id=str(getattr(project, "project_id", "ad-hoc-project") or "ad-hoc-project"),
        film_language=film_language,
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
    film_language: str | None = None,
    external_input_digests: dict[str, str] | None = None,
) -> RendererInputManifest:
    """Compile the one renderer contract used by generation and reconciliation."""

    generation_mode = str(getattr(shot, "generation_mode", "") or "")
    if generation_mode != "T2V":
        raise RendererContractUnavailable(
            UNSUPPORTED_GENERATION_MODE,
            f"Renderer contract does not support generation mode {generation_mode!r}.",
        )
    raw = _read_workflow_template(workflow_path)

    if derived_seed is None:
        from movie_agent.services.continuity import derive_shot_seed

        visual_bible = getattr(project, "visual_bible", {}) or {}
        reference_seed = str(visual_bible.get("reference_seed") or "42")
        derived_seed = derive_shot_seed(
            str(getattr(project, "project_id", "ad-hoc-project") or "ad-hoc-project"),
            reference_seed,
            int(getattr(shot, "number", 0) or 0),
        )
    language = str(film_language or getattr(project, "film_language", "en") or "en").lower()
    if compiled_prompt is None:
        compiled_prompt = _default_prompt(project, shot, previous_shot, context, language)

    if submitted_workflow is None:
        from movie_agent.services.comfyui import WorkflowOverrides, load_verified_workflow

        try:
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
        except Exception as error:
            raise RendererContractUnavailable(
                WORKFLOW_COMPILE_FAILED,
                "The renderer workflow could not be compiled with the current shot inputs.",
                [str(error)],
            ) from error
    if not isinstance(submitted_workflow, dict):
        raise RendererContractUnavailable(WORKFLOW_COMPILE_FAILED, "The submitted renderer workflow is not an object.")

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
        generation_mode=generation_mode,
        workflow_template_digest=canonical_digest(raw),
        submitted_workflow_digest=submitted_workflow_digest(submitted_workflow),
        workflow_identity=_workflow_identity(workflow_path, workflow_identity, raw),
        context_digest=canonical_digest(_context_payload(context)),
        external_input_digests=dict(external_input_digests or {}),
    )


__all__ = [
    "CONTRACT_READY",
    "DEFAULT_WORKFLOW_IDENTITY",
    "RENDERER_MANIFEST_VERSION",
    "RendererContractUnavailable",
    "RendererInputManifest",
    "UNSUPPORTED_GENERATION_MODE",
    "WORKFLOW_COMPILE_FAILED",
    "WORKFLOW_INVALID",
    "WORKFLOW_MISSING",
    "canonical_digest",
    "compile_renderer_input",
    "submitted_workflow_digest",
    "workflow_template_digest",
]
