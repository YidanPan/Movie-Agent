"""Revision metadata and dependency invalidation for production assets.

The project intentionally keeps JSON persistence and local media files.  This
module gives that small architecture the same safety property as a larger
pipeline: an upstream edit marks dependent outputs stale, but never destroys a
previous render.  New renders replace the current pointer only after they have
passed their stage's checks.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from movie_agent.services.render_input import (
    RENDERER_MANIFEST_VERSION,
    GenerationInputFingerprint,
    RendererContractUnavailable,
    build_generation_input_fingerprint,
    compile_renderer_input,
)


DEPENDENCY_GRAPH: dict[str, tuple[str, ...]] = {
    "script": (
        "storyboard",
        "shot_media",
        "qc",
        "voice",
        "subtitles",
        "rough_cut",
        "final_cut",
        "final_look",
        "export",
    ),
    # Dialogue/Subtitle edits do not rewrite the visual storyboard.  They
    # invalidate the sound and editorial derivatives while preserving already
    # approved shot media.
    "dialogue": ("voice", "subtitles", "rough_cut", "final_cut", "final_look", "export"),
    "storyboard": (
        "shot_media",
        "qc",
        "voice",
        "subtitles",
        "rough_cut",
        "final_cut",
        "final_look",
        "export",
    ),
    "shot": (
        "shot_media",
        "qc",
        "rough_cut",
        "final_cut",
        "final_look",
        "export",
    ),
    "shot_timing": (
        "voice",
        "subtitles",
        "rough_cut",
        "final_cut",
        "final_look",
        "export",
    ),
    "voice": ("subtitles", "rough_cut", "final_cut", "final_look", "export"),
    "audio": ("rough_cut", "final_cut", "final_look", "export"),
    "rough_cut": ("final_cut", "final_look", "export"),
    "final_cut": ("final_look", "export"),
    "final_look": ("export",),
}


def utc_now() -> str:
    """Return a stable, JSON-friendly UTC timestamp."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def hash_shot_prompt(shot: Any) -> str:
    """Hash all renderer-facing shot inputs, not only the short Shot Delta."""

    payload = {
        "prompt": str(getattr(shot, "prompt", "") or ""),
        "image_description": str(getattr(shot, "image_description", "") or ""),
        "action": str(getattr(shot, "action", "") or ""),
        "narrative_purpose": str(getattr(shot, "narrative_purpose", "") or ""),
        "framing": str(getattr(shot, "framing", "") or ""),
        "sound_design": str(getattr(shot, "sound_design", "") or ""),
        "generation_mode": str(getattr(shot, "generation_mode", "") or ""),
        "starting_state": str(getattr(shot, "starting_state", "") or ""),
        "main_action": str(getattr(shot, "main_action", "") or ""),
        "character_reaction": str(getattr(shot, "character_reaction", "") or ""),
        "ending_state": str(getattr(shot, "ending_state", "") or ""),
        "transition_hook": str(getattr(shot, "transition_hook", "") or ""),
        "secondary_action": str(getattr(shot, "secondary_action", "") or ""),
        "environment_reaction": str(getattr(shot, "environment_reaction", "") or ""),
        "beat_id": str(getattr(shot, "beat_id", "") or ""),
        "scene_id": str(getattr(shot, "scene_id", "") or ""),
        "character_ids": list(getattr(shot, "character_ids", []) or []),
        "prop_ids": list(getattr(shot, "prop_ids", []) or []),
        "story_function": str(getattr(shot, "story_function", "") or ""),
        "information_gain": getattr(shot, "information_gain", 0.0),
        "emotional_shift": str(getattr(shot, "emotional_shift", "") or ""),
        "visual_motif": str(getattr(shot, "visual_motif", "") or ""),
        "continuity_from": str(getattr(shot, "continuity_from", "") or ""),
        "continuity_to": str(getattr(shot, "continuity_to", "") or ""),
        "transition_type": str(getattr(shot, "transition_type", "") or ""),
        "state_delta": getattr(shot, "state_delta", {}) or {},
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def hash_generation_input(
    shot: Any,
    context: Any | None = None,
    *,
    workflow_identity: str = "verified-comfyui-workflow",
) -> str:
    """Compatibility wrapper around the canonical renderer compiler.

    New render/reconcile code must call ``compile_renderer_input`` directly.
    Keeping this wrapper prevents old project migrations and integrations from
    retaining a second fingerprint algorithm.
    """

    from types import SimpleNamespace

    project = SimpleNamespace(
        project_id="ad-hoc-project",
        visual_bible={},
        story_world={},
        film_language="en",
    )
    workflow_path = Path(__file__).resolve().parents[2] / "workflows" / "minimax_h3_t2v_api.json"
    manifest = compile_renderer_input(
        project,
        shot,
        None,
        context or {},
        workflow_path,
        workflow_identity=workflow_identity,
        film_language="en",
    )
    return manifest.fingerprint()[:24]


def _shot_has_current_source(shot: Any) -> bool:
    """Return whether a shot has a current renderer output worth invalidating."""

    assets = getattr(shot, "media_assets", {}) or {}
    source = assets.get("source") if isinstance(assets, dict) else None
    if isinstance(source, dict) and source.get("stale") is not True:
        if any(source.get(key) for key in ("path", "media_path", "source_path", "url")):
            return True
    status = str(getattr(shot, "status", "") or "")
    output = str(getattr(shot, "output_placeholder", "") or "")
    return status.startswith(("generated", "approved")) and bool(output)


def diff_renderer_contract(source_asset: Any, expected_manifest: Any) -> dict[str, str] | None:
    """Explain the first renderer-contract fact that differs from a source asset."""

    if not isinstance(source_asset, dict):
        return None
    expected = expected_manifest.audit_dict() if hasattr(expected_manifest, "audit_dict") else dict(expected_manifest or {})
    comparisons = (
        (
            "compiled_prompt_digest",
            "PROMPT_CHANGED",
            "Current compiled visual prompt differs from rendered source.",
        ),
        (
            "submitted_workflow_digest",
            "WORKFLOW_CHANGED",
            "Submitted renderer workflow differs from rendered source.",
        ),
        (
            "workflow_template_digest",
            "WORKFLOW_CHANGED",
            "Renderer workflow template differs from rendered source.",
        ),
        (
            "derived_seed",
            "SEED_CHANGED",
            "Derived renderer seed differs from rendered source.",
        ),
        (
            "source_duration_seconds",
            "SOURCE_DURATION_CHANGED",
            "Native source duration differs from rendered source.",
        ),
        (
            "renderer_manifest_version",
            "RENDERER_VERSION_CHANGED",
            "Renderer manifest version differs from rendered source.",
        ),
        (
            "external_input_digests",
            "EXTERNAL_REFERENCE_CHANGED",
            "External renderer references differ from rendered source.",
        ),
    )
    for field, reason, detail in comparisons:
        if field in source_asset and source_asset.get(field) != expected.get(field):
            return {"reason": reason, "detail": detail}
    return None


def reconcile_generation_fingerprints(
    project: Any,
    *,
    workflow_identity: str = "verified-comfyui-workflow",
    workflow_path: Path | str | None = None,
) -> dict[str, Any]:
    """Recompute renderer contracts and compare them with source asset facts."""

    from movie_agent.services.shot_context import resolve_shot_context
    from movie_agent.services.state_ledger import build_state_ledger, state_record_for_shot

    build_state_ledger(project)
    if workflow_path is None:
        candidate = Path(str(workflow_identity or ""))
        if candidate.is_file():
            workflow_path = candidate
        else:
            workflow_path = Path(__file__).resolve().parents[2] / "workflows" / "minimax_h3_t2v_api.json"
    shots = sorted(list(getattr(project, "storyboard", []) or []), key=lambda item: int(getattr(item, "number", 0) or 0))
    contexts: list[tuple[Any, Any, Any, Any]] = []
    previous = None
    for shot in shots:
        number = int(getattr(shot, "number", 0) or 0)
        record = state_record_for_shot(project, number)
        context = resolve_shot_context(
            shot,
            getattr(project, "visual_bible", {}) or {},
            getattr(project, "story_world", {}) or {},
            previous,
            entity_state_before=record.get("before"),
            entity_state_delta=record.get("delta"),
            entity_state_after=record.get("after"),
        )
        source_record = (getattr(shot, "media_assets", {}) or {}).get("source")
        provider = str(getattr(shot, "provider", "") or (source_record or {}).get("provider") or "comfyui").lower()
        if provider != "comfyui":
            from movie_agent.agents.generation import build_continuity_prompt
            from movie_agent.services.continuity import derive_shot_seed

            seed = getattr(shot, "seed", None)
            if seed is None:
                seed = derive_shot_seed(
                    str(getattr(project, "project_id", "ad-hoc-project") or "ad-hoc-project"),
                    str((getattr(project, "visual_bible", {}) or {}).get("reference_seed") or "42"),
                    number,
                )
            # ``compiled_generation_prompt`` is an audit record of the last
            # render, never the current expected input. Recompile after every
            # project/shot change so reconciliation cannot miss drift.
            prompt = build_continuity_prompt(
                shot,
                getattr(project, "visual_bible", {}) or {},
                previous,
                project_id=str(getattr(project, "project_id", "ad-hoc-project") or "ad-hoc-project"),
                film_language=str(getattr(project, "film_language", "en") or "en"),
                context=context,
                story_world=getattr(project, "story_world", {}) or {},
            )
            manifest = build_generation_input_fingerprint(
                provider=provider,
                model=str(getattr(shot, "model", "") or (source_record or {}).get("model") or provider),
                generation_mode=str(getattr(shot, "generation_mode", "") or ""),
                compiled_prompt=prompt,
                seed=seed,
                source_duration_seconds=getattr(shot, "source_duration_seconds", 0) or getattr(shot, "duration_seconds", 0),
                reference_digests=(source_record or {}).get("external_input_digests") if isinstance(source_record, dict) else {},
                shot_revision=getattr(shot, "revision", 1),
                target_resolution=str(getattr(project, "target_resolution", "") or ""),
                aspect_ratio="16:9",
                negative_prompt=(
                    "existing film or TV characters, titles, logos, brands, real-person likenesses, "
                    "copyrighted designs, subtitles, watermarks, language other than English"
                ),
                master_fps=int(getattr(project, "target_fps", 24) or 24),
            )
        else:
            try:
                manifest = compile_renderer_input(
                    project,
                    shot,
                    previous,
                    context,
                    workflow_path,
                    workflow_identity=workflow_identity,
                    film_language=str(getattr(project, "film_language", "en") or "en"),
                )
            except RendererContractUnavailable as error:
                project.renderer_contract = {
                    "status": error.status,
                    "valid": False,
                    "errors": list(error.errors),
                }
                return {
                    "affected_shots": [],
                    "old_hashes": {},
                    "new_hashes": {},
                    "event": None,
                    "contract_status": error.status,
                    "contract_errors": list(error.errors),
                }
        contexts.append((shot, previous, context, manifest))
        previous = shot

    project.renderer_contract = {"status": "READY", "valid": True, "errors": []}
    previous = None
    changed: list[int] = []
    old_hashes: dict[str, str] = {}
    new_hashes: dict[str, str] = {}
    contract_diffs: dict[str, dict[str, str]] = {}
    for shot, previous, context, manifest in contexts:
        new_hash = manifest.fingerprint if isinstance(manifest, GenerationInputFingerprint) else manifest.fingerprint()
        number = int(getattr(shot, "number", 0) or 0)
        new_hashes[str(number)] = new_hash
        source_record = (getattr(shot, "media_assets", {}) or {}).get("source")
        rendered_hash = source_record.get("generation_input_hash") if isinstance(source_record, dict) else ""
        if isinstance(manifest, GenerationInputFingerprint):
            if _shot_has_current_source(shot) and isinstance(source_record, dict):
                if not rendered_hash:
                    source_record["renderer_verification_status"] = "UNVERIFIED_LEGACY"
                elif rendered_hash != new_hash:
                    diff = {"reason": "RENDERER_INPUT_CHANGED", "detail": "Provider-neutral generation input differs from rendered source."}
                    source_record["renderer_verification_status"] = "STALE"
                    old_hashes[str(number)] = str(rendered_hash)
                    contract_diffs[str(number)] = diff
                    changed.append(number)
                    if not bool(getattr(shot, "stale", False)):
                        mark_shot_stale(shot, diff["reason"])
                    else:
                        shot.qc_status = "STALE"
                else:
                    source_record["renderer_verification_status"] = "VERIFIED"
            shot.generation_input_hash = new_hash
            previous = shot
            continue
        if _shot_has_current_source(shot):
            required_manifest_fields = (
                "generation_input_hash",
                "renderer_manifest_version",
                "compiled_prompt_digest",
                "workflow_template_digest",
                "submitted_workflow_digest",
                "derived_seed",
                "source_duration_seconds",
            )
            if not isinstance(source_record, dict) or not rendered_hash or not all(field in source_record for field in required_manifest_fields):
                if isinstance(source_record, dict):
                    source_record["renderer_verification_status"] = "UNVERIFIED_LEGACY"
            elif rendered_hash != new_hash or diff_renderer_contract(source_record, manifest):
                diff = diff_renderer_contract(source_record, manifest) or {
                    "reason": "RENDERER_INPUT_CHANGED",
                    "detail": "Renderer input differs from rendered source.",
                }
                source_record["renderer_verification_status"] = "STALE"
                old_hashes[str(number)] = str(rendered_hash)
                contract_diffs[str(number)] = diff
                changed.append(number)
                if not bool(getattr(shot, "stale", False)):
                    mark_shot_stale(shot, diff["reason"])
                else:
                    shot.qc_status = "STALE"
            else:
                source_record["renderer_verification_status"] = "VERIFIED"
        # This field remains a useful expected-value diagnostic for old API
        # clients, but it is never used as the rendered source's authority.
        shot.generation_input_hash = new_hash
        previous = shot

    event = None
    if changed:
        event = {
            "source": "generation_fingerprint",
            "source_shot": min(changed),
            "source_shots": sorted(changed),
            "affected_shots": sorted(changed),
            "reason": "generation_input_fingerprint_changed",
            "old_hashes": old_hashes,
            "new_hashes": {str(number): new_hashes[str(number)] for number in changed},
            "contract_diffs": contract_diffs,
            "created_at": utc_now(),
        }
        if not isinstance(getattr(project, "invalidation_events", None), list):
            project.invalidation_events = []
        project.invalidation_events.append(event)
    return {
        "affected_shots": sorted(changed),
        "old_hashes": old_hashes,
        "new_hashes": new_hashes,
        "event": event,
        "contract_status": "READY",
        "contract_diffs": contract_diffs,
    }


def ensure_shot_metadata(
    shot: Any,
    *,
    provider: str = "mock",
    model: str = "mock",
    seed: int | None = None,
    created_at: str | None = None,
) -> Any:
    """Backfill metadata on old projects without changing their revision."""

    try:
        shot.revision = max(1, int(getattr(shot, "revision", 1) or 1))
    except (TypeError, ValueError):
        shot.revision = 1
    shot.prompt_hash = hash_shot_prompt(shot)
    if not getattr(shot, "generation_input_hash", ""):
        shot.generation_input_hash = hash_generation_input(shot)
    if not getattr(shot, "provider", ""):
        shot.provider = str(provider or "mock")
    if not getattr(shot, "model", ""):
        shot.model = str(model or "mock")
    if seed is not None:
        shot.seed = int(seed)
        shot.generation_seed = int(seed)
    elif getattr(shot, "seed", None) is None and getattr(shot, "generation_seed", None) is not None:
        shot.seed = int(shot.generation_seed)
    if not getattr(shot, "created_at", ""):
        shot.created_at = created_at or utc_now()
    if not getattr(shot, "qc_status", ""):
        shot.qc_status = "PENDING"
    if not isinstance(getattr(shot, "asset_history", None), list):
        shot.asset_history = []
    if not isinstance(getattr(shot, "stale", False), bool):
        shot.stale = bool(shot.stale)
    return shot


def _stale_record(record: Any, *, reason: str, revision: int, now: str) -> dict[str, Any] | Any:
    if not isinstance(record, dict):
        return record
    stale = deepcopy(record)
    stale["stale"] = True
    stale["stale_at"] = now
    stale["stale_reason"] = reason
    stale["source_revision"] = int(record.get("revision", revision) or revision)
    return stale


def mark_shot_stale(shot: Any, reason: str, *, increment_revision: bool = True) -> Any:
    """Mark current shot media and QC stale while retaining rollback history."""

    ensure_shot_metadata(shot)
    if increment_revision:
        shot.revision = max(1, int(shot.revision or 1)) + 1
    now = utc_now()
    current_assets = getattr(shot, "media_assets", {}) or {}
    if isinstance(current_assets, dict):
        stale_assets = {
            key: _stale_record(value, reason=reason, revision=shot.revision, now=now)
            for key, value in current_assets.items()
        }
        # Keep the current records visible for diagnostics, and also append a
        # frozen snapshot so a future renderer can offer rollback/comparison.
        if stale_assets:
            history = getattr(shot, "asset_history", None)
            if not isinstance(history, list):
                history = []
                shot.asset_history = history
            history.append(
                {
                    "revision": max(1, int(shot.revision or 1) - 1),
                    "invalidated_at": now,
                    "invalidated_reason": reason,
                    "assets": deepcopy(stale_assets),
                }
            )
        shot.media_assets = stale_assets
    shot.stale = True
    shot.qc_status = "STALE"
    flags = [str(flag).upper() for flag in (getattr(shot, "qc_flags", None) or [])]
    if "STALE" not in flags:
        flags.append("STALE")
    shot.qc_flags = flags
    # A stale source must not be mistaken for an approved render on resume.
    if str(getattr(shot, "status", "")).startswith(("approved", "generated", "generating")):
        shot.status = "replanned"
    shot.prompt_hash = hash_shot_prompt(shot)
    return shot


def mark_current_assets_stale(project: Any, reason: str, *, source: str = "pipeline") -> list[dict[str, Any]]:
    """Mark project-level edit assets stale and return the snapshot."""

    now = utc_now()
    assets = getattr(project, "video_assets", {}) or {}
    if not isinstance(assets, dict):
        return []
    stale_assets: dict[str, Any] = {}
    snapshot: list[dict[str, Any]] = []
    for key, record in assets.items():
        stale = _stale_record(record, reason=reason, revision=1, now=now)
        stale_assets[key] = stale
        snapshot.append({"key": key, "asset": deepcopy(stale), "source": source})
    project.video_assets = stale_assets
    if snapshot:
        history = getattr(project, "video_asset_history", None)
        if not isinstance(history, list):
            history = []
            project.video_asset_history = history
        history.append({"invalidated_at": now, "reason": reason, "source": source, "assets": snapshot})
    return snapshot


def invalidate_downstream(
    project: Any,
    source: str,
    reason: str,
    *,
    shot: Any | None = None,
    mark_shot: bool = False,
) -> dict[str, Any]:
    """Propagate an upstream change through the persisted production graph.

    ``mark_shot`` is false for timeline-only edits: the original shot media is
    still valid, while every editorial derivative is stale.  Prompt and visual
    edits set it true so QC and media cannot be reused accidentally.
    """

    source_key = str(source or "pipeline").strip().lower()
    downstream = list(DEPENDENCY_GRAPH.get(source_key, ()))
    if mark_shot and shot is not None:
        mark_shot_stale(shot, reason)
    if "shot_media" in downstream and shot is None:
        for item in getattr(project, "storyboard", []) or []:
            mark_shot_stale(item, reason)
    snapshot = mark_current_assets_stale(project, reason, source=source_key)
    if getattr(project, "edit_plan", None):
        old_plan = deepcopy(project.edit_plan)
        old_plan["stale"] = True
        old_plan["stale_reason"] = reason
        old_plan["invalidated_at"] = utc_now()
        history = getattr(project, "edit_plan_history", None)
        if not isinstance(history, list):
            history = []
            project.edit_plan_history = history
        history.append(old_plan)
    project.edit_plan = {}
    # Audio records can contain generated voice/music files.  They are kept
    # for inspection but cannot silently be reused after source changes.
    if source_key in {"script", "shot_timing", "voice", "audio", "storyboard", "shot"}:
        for track in (getattr(project, "audio_tracks", {}) or {}).values():
            if isinstance(track, dict) and track.get("media_path"):
                track["stale"] = True
                track["stale_reason"] = reason
    # Final Look is a derivative of the previous final cut.  Resetting its
    # active pointer is safe; history remains in the invalidation event.
    look = getattr(project, "final_look", None)
    if isinstance(look, dict) and look:
        look["stale"] = True
        look["stale_reason"] = reason
    project.final_output_placeholder = None
    project.rough_cut_placeholder = None
    if not isinstance(getattr(project, "invalidation_events", None), list):
        project.invalidation_events = []
    event = {
        "source": source_key,
        "reason": reason,
        "created_at": utc_now(),
        "downstream": downstream,
        "shot_number": getattr(shot, "number", None),
        "stale_assets": [item.get("key") for item in snapshot],
    }
    project.invalidation_events.append(event)
    shots = getattr(project, "storyboard", []) or []
    shots_ready = bool(shots) and all(str(getattr(item, "status", "")).startswith("approved") and not getattr(item, "stale", False) for item in shots)
    if shots_ready:
        project.status = "ready_for_ai_edit"
    elif str(getattr(project, "status", "")) not in {"planning_live", "rendering", "rendering_comfyui", "generating_video_mock"}:
        project.status = "render_ready"
    return event


def ensure_project_revision_metadata(project: Any, *, provider: str = "mock", model: str = "mock") -> Any:
    """Backfill metadata for a project loaded from a pre-P2 JSON file."""

    shots = list(getattr(project, "storyboard", []) or [])
    for shot in shots:
        ensure_shot_metadata(shot, provider=provider, model=model)
        media_assets = getattr(shot, "media_assets", {}) or {}
        if isinstance(media_assets, dict):
            for record in media_assets.values():
                _ensure_asset_metadata(record, shot, provider=provider, model=model)
    project_assets = getattr(project, "video_assets", {}) or {}
    if isinstance(project_assets, dict):
        project_revision = max((int(getattr(shot, "revision", 1) or 1) for shot in shots), default=1)
        for record in project_assets.values():
            _ensure_asset_metadata(record, None, provider=provider, model=model, revision=project_revision)
    if not isinstance(getattr(project, "video_asset_history", None), list):
        project.video_asset_history = []
    if not isinstance(getattr(project, "edit_plan_history", None), list):
        project.edit_plan_history = []
    if not isinstance(getattr(project, "invalidation_events", None), list):
        project.invalidation_events = []
    try:
        project.schema_version = max(2, int(getattr(project, "schema_version", 2) or 2))
    except (TypeError, ValueError):
        project.schema_version = 2
    return project


def _ensure_asset_metadata(
    record: Any,
    shot: Any | None,
    *,
    provider: str,
    model: str,
    revision: int | None = None,
) -> Any:
    """Add the P2 audit fields to legacy asset records without probing media."""

    if not isinstance(record, dict):
        return record
    shot_revision = int(revision or getattr(shot, "revision", 1) or 1)
    record.setdefault("revision", max(1, shot_revision))
    record.setdefault("prompt_hash", str(getattr(shot, "prompt_hash", "") or ""))
    record.setdefault("generation_input_hash", str(getattr(shot, "generation_input_hash", "") or ""))
    record.setdefault("provider", str(getattr(shot, "provider", "") or provider or ""))
    record.setdefault("model", str(getattr(shot, "model", "") or model or ""))
    seed = getattr(shot, "seed", None) if shot is not None else None
    if seed is None and shot is not None:
        seed = getattr(shot, "generation_seed", None)
    record.setdefault("seed", int(seed) if seed is not None else None)
    record.setdefault("created_at", str(getattr(shot, "created_at", "") or utc_now()))
    record.setdefault("qc_status", "PENDING")
    record.setdefault("workflow_template_digest", "")
    record.setdefault("submitted_workflow_digest", "")
    record.setdefault("compiled_prompt_digest", "")
    record.setdefault("derived_seed", int(seed) if seed is not None else None)
    record.setdefault("source_duration_seconds", getattr(shot, "source_duration_seconds", None) if shot is not None else None)
    record.setdefault("renderer_manifest_version", RENDERER_MANIFEST_VERSION if record.get("generation_input_hash") else "")
    record.setdefault("renderer_contract_status", "")
    record.setdefault(
        "renderer_verification_status",
        "UNVERIFIED_LEGACY" if record.get("tier") == "source" and record.get("generation_input_hash") else "",
    )
    record.setdefault("external_input_digests", {})
    if "source_resolution" not in record:
        width, height = record.get("width"), record.get("height")
        record["source_resolution"] = f"{width}x{height}" if width and height else getattr(shot, "source_resolution", None)
    record.setdefault("source_fps", record.get("fps", getattr(shot, "source_fps", None)))
    record.setdefault("source_duration", record.get("duration_seconds", getattr(shot, "source_duration", None)))
    record.setdefault("stale", bool(getattr(shot, "stale", False)) if shot is not None else False)
    return record


def dependency_chain(source: str) -> tuple[str, ...]:
    """Public read-only view used by diagnostics and regression tests."""

    return tuple(DEPENDENCY_GRAPH.get(str(source or "").lower(), ()))
