"""Persistent visual references used by generation and continuity QC."""

from __future__ import annotations

import json
import re
import shutil
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from movie_agent.services.continuity import should_use_previous_frame
from movie_agent.services.shot_context import ResolvedShotContext


REFERENCE_KINDS = {
    "character_hero",
    "character",
    "scene",
    "palette",
    "prop",
    "cinematography",
    "review_keyframe",
    "shot_keyframe",
    "approved_keyframe",
    "previous_approved_shot_ending_frame",
}


@dataclass
class ReferenceAsset:
    reference_id: str
    kind: str
    path: str
    source: str
    approved: bool = False
    shot_number: int | None = None
    revision: int = 1
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    # Explicit selectors keep reference choice addressable for future I2V/R2V
    # conditioning while remaining compatible with older manifests.
    character_id: str = ""
    character_ids: list[str] = field(default_factory=list)
    scene_id: str = ""
    role: str = ""


@dataclass
class ReferenceBank:
    project_id: str
    assets: list[ReferenceAsset] = field(default_factory=list)
    schema_version: int = 1


class ReferenceBankStore:
    """Index real reference files below ``outputs/<project>/references``."""

    _slug_pattern = re.compile(r"[^a-zA-Z0-9._-]+")
    _registry_guard = threading.Lock()
    _registry: dict[str, threading.RLock] = {}

    def __init__(self, outputs_root: Path) -> None:
        self.outputs_root = Path(outputs_root)
        key = str(self.outputs_root.resolve())
        with self._registry_guard:
            self._lock = self._registry.setdefault(key, threading.RLock())

    def project_dir(self, project_id: str) -> Path:
        return self.outputs_root / project_id / "references"

    def manifest_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "reference-bank.json"

    def load(self, project_id: str) -> ReferenceBank:
        with self._lock:
            path = self.manifest_path(project_id)
            if not path.is_file():
                return ReferenceBank(project_id=project_id)
            payload = json.loads(path.read_text(encoding="utf-8"))
            assets: list[ReferenceAsset] = []
            for item in payload.get("assets", []):
                if not isinstance(item, dict):
                    continue
                record = dict(item)
                character_ids = record.get("character_ids")
                if isinstance(character_ids, str):
                    character_ids = [value.strip() for value in character_ids.split(",") if value.strip()]
                if not character_ids and record.get("character_id"):
                    character_ids = [str(record["character_id"])]
                record["character_ids"] = character_ids or []
                assets.append(ReferenceAsset(**record))
            return ReferenceBank(
                project_id=str(payload.get("project_id") or project_id),
                assets=assets,
                schema_version=max(1, int(payload.get("schema_version") or 1)),
            )

    def save(self, bank: ReferenceBank) -> Path:
        with self._lock:
            directory = self.project_dir(bank.project_id)
            directory.mkdir(parents=True, exist_ok=True)
            path = self.manifest_path(bank.project_id)
            temporary = path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(asdict(bank), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(path)
            return path

    def get(self, project_id: str, reference_id: str) -> ReferenceAsset:
        """Return one persisted reference or raise a stable not-found error."""

        bank = self.load(project_id)
        for asset in bank.assets:
            if asset.reference_id == str(reference_id):
                return asset
        raise FileNotFoundError(f"Reference {reference_id} was not found.")

    def _set_approval(self, project_id: str, reference_id: str, approved: bool) -> ReferenceAsset:
        """Persist an explicit human approval decision for one reference."""

        bank = self.load(project_id)
        for asset in bank.assets:
            if asset.reference_id != str(reference_id):
                continue
            if approved:
                if bool((asset.metadata or {}).get("stale")):
                    raise ValueError("A stale reference cannot be approved.")
                if not Path(asset.path).is_file():
                    raise FileNotFoundError(f"Reference {reference_id} media is missing.")
            asset.approved = bool(approved)
            asset.metadata["review_status"] = "APPROVED" if approved else "REJECTED"
            self.save(bank)
            return asset
        raise FileNotFoundError(f"Reference {reference_id} was not found.")

    def set_approval(self, project_id: str, reference_id: str, approved: bool) -> ReferenceAsset:
        with self._lock:
            return self._set_approval(project_id, reference_id, approved)

    def _register_file(
        self,
        project_id: str,
        source_path: Path,
        *,
        kind: str,
        source: str,
        approved: bool = False,
        shot_number: int | None = None,
        revision: int = 1,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
        character_id: str = "",
        character_ids: list[str] | None = None,
        scene_id: str = "",
        role: str = "",
    ) -> ReferenceAsset:
        if kind not in REFERENCE_KINDS:
            raise ValueError(f"Unsupported reference kind: {kind}")
        source_path = Path(source_path)
        if not source_path.is_file():
            raise FileNotFoundError(f"Reference file does not exist: {source_path}")
        bank = self.load(project_id)
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        current_revision = max(1, int(revision or 1))
        if approved and shot_number is not None:
            for existing in bank.assets:
                if existing.shot_number == shot_number and existing.revision != current_revision:
                    existing.metadata["stale"] = True
        reference_id = f"ref-{len(bank.assets) + 1:04d}"
        safe_name = self._slug_pattern.sub("-", name or f"{kind}-{reference_id}").strip("-.") or reference_id
        suffix = source_path.suffix.lower() or ".webp"
        # Reference records are historical evidence.  Include the stable
        # record id and revision in the stored filename so a later asset with
        # the same display name can never replace its bytes.
        target = self.project_dir(project_id) / f"{safe_name}-{reference_id}-r{current_revision}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
        resolved_character_ids = [str(item).strip() for item in (character_ids or []) if str(item).strip()]
        resolved_character_id = str(character_id or (resolved_character_ids[0] if resolved_character_ids else "") or (metadata or {}).get("character_id") or "")
        if not resolved_character_ids and resolved_character_id:
            resolved_character_ids = [resolved_character_id]
        asset_metadata = dict(metadata or {})
        for key, value in (("character_id", resolved_character_id), ("character_ids", resolved_character_ids), ("scene_id", scene_id), ("role", role or kind)):
            if value:
                asset_metadata.setdefault(key, value)
        asset = ReferenceAsset(
            reference_id=reference_id,
            kind=kind,
            path=str(target),
            source=str(source),
            approved=bool(approved),
            shot_number=shot_number,
            revision=current_revision,
            created_at=timestamp,
            metadata=asset_metadata,
            character_id=resolved_character_id,
            character_ids=resolved_character_ids,
            scene_id=str(scene_id or (metadata or {}).get("scene_id") or ""),
            role=str(role or (metadata or {}).get("role") or kind),
        )
        bank.assets.append(asset)
        self.save(bank)
        return asset

    def register_file(self, project_id: str, source_path: Path, **kwargs: Any) -> ReferenceAsset:
        with self._lock:
            return self._register_file(project_id, source_path, **kwargs)

    def _promote_shot_references(self, project_id: str, shot_number: int, revision: int) -> int:
        """Promote only this shot's review frames after manual approval."""

        bank = self.load(project_id)
        promoted = 0
        current_revision = max(1, int(revision or 1))
        for existing in bank.assets:
            if existing.shot_number == shot_number and existing.revision != current_revision:
                existing.metadata["stale"] = True
        candidates = [
            asset
            for asset in bank.assets
            if asset.shot_number == shot_number
            and asset.revision == current_revision
            and asset.kind == "review_keyframe"
        ]
        ending = next(
            (asset for asset in reversed(candidates) if asset.role == "transition_ending_frame" or (asset.metadata or {}).get("role") == "transition_ending_frame"),
            candidates[-1] if candidates else None,
        )
        for asset in candidates:
            asset.kind = "previous_approved_shot_ending_frame" if asset is ending else "approved_keyframe"
            asset.approved = True
            promoted += 1
        if promoted:
            self.save(bank)
        return promoted

    def promote_shot_references(self, project_id: str, shot_number: int, revision: int) -> int:
        with self._lock:
            return self._promote_shot_references(project_id, shot_number, revision)

    def mark_stale(self, project_id: str, reference_id: str, *, reason: str = "INPUT_CHANGED") -> ReferenceAsset:
        """Mark an asynchronously generated asset stale without promoting it."""

        with self._lock:
            bank = self.load(project_id)
            for asset in bank.assets:
                if asset.reference_id != str(reference_id):
                    continue
                asset.approved = False
                asset.metadata["stale"] = True
                asset.metadata["stale_reason"] = str(reason)
                asset.metadata["review_status"] = "STALE"
                self.save(bank)
                return asset
        raise FileNotFoundError(f"Reference {reference_id} was not found.")

    def qc_reference_paths(
        self,
        project_id: str,
        shot_number: int | Any,
        previous_shot: Any | None = None,
        *,
        context: ResolvedShotContext | None = None,
    ) -> dict[str, list[Path]]:
        """Resolve persistent, approved inputs for a shot's visual review."""

        is_shot = not isinstance(shot_number, (int, str))
        requested_scene = str((context.scene_id if context else getattr(shot_number, "scene_id", "")) or "")
        requested_characters = set(context.character_ids if context else [str(item) for item in (getattr(shot_number, "character_ids", []) or [])])
        requested_props = set(context.prop_ids if context else [str(item) for item in (getattr(shot_number, "prop_ids", []) or [])])
        shot_number = int(getattr(shot_number, "number", shot_number) or 0)
        bank = self.load(project_id)
        usable = [
            asset
            for asset in bank.assets
            if asset.approved
            and not bool((asset.metadata or {}).get("stale"))
            and Path(asset.path).is_file()
        ]
        def field(asset: ReferenceAsset, key: str) -> str:
            value = getattr(asset, key, "") or (asset.metadata or {}).get(key) or ""
            if isinstance(value, list):
                return ",".join(str(item) for item in value)
            return str(value)

        # Approved shot keyframes are evidence for a shot/transition, not
        # identity references. A wide environment frame must never silently
        # become a character hero reference.
        character = [asset for asset in usable if asset.kind in {"character_hero", "character"}]
        reference_flags: list[str] = []
        if requested_characters:
            character = [
                asset for asset in character
                if requested_characters.intersection(set(field(asset, "character_ids").split(",")))
                or field(asset, "character_id") in requested_characters
            ]
            if not character:
                reference_flags.append("MISSING_CHARACTER_REFERENCE")
        scene = [asset for asset in usable if asset.kind in {"scene", "palette", "cinematography"}]
        if requested_scene:
            scene = [asset for asset in scene if field(asset, "scene_id") == requested_scene]
            if not scene:
                reference_flags.append("MISSING_SCENE_REFERENCE")
        prop = [asset for asset in usable if asset.kind == "prop"]
        if requested_props:
            prop = [
                asset for asset in prop
                if requested_props.intersection(set(field(asset, "prop_ids").split(",")))
                or field(asset, "prop_id") in requested_props
            ]
            if not prop:
                reference_flags.append("MISSING_PROP_REFERENCE")
        previous = []
        requires_previous = context.previous_visual_reference_allowed if context else should_use_previous_frame(shot_number, previous_shot)
        if requires_previous and (previous_shot is not None or not is_shot):
            previous = [
                asset
                for asset in usable
                if asset.kind == "previous_approved_shot_ending_frame"
                and asset.shot_number is not None
                and (
                    not is_shot
                    or (
                        previous_shot is not None
                        and asset.shot_number == int(getattr(previous_shot, "number", 0) or 0)
                        and asset.revision == int(getattr(previous_shot, "revision", 1) or 1)
                    )
                )
            ]
        latest_previous: dict[int, ReferenceAsset] = {}
        for asset in previous:
            if asset.shot_number is None:
                continue
            current = latest_previous.get(asset.shot_number)
            if current is None or (asset.revision, asset.created_at) > (current.revision, current.created_at):
                latest_previous[asset.shot_number] = asset
        if requires_previous and is_shot and previous_shot is not None and not latest_previous:
            reference_flags.append("MISSING_PREVIOUS_ENDING_REFERENCE")
        return {
            "character_hero": [Path(asset.path) for asset in character[:2]],
            "current_scene": [Path(asset.path) for asset in scene[:3]],
            "prop": [Path(asset.path) for asset in prop[:3]],
            "previous_approved_shot_ending_frame": [Path(asset.path) for asset in latest_previous.values()][-1:] if latest_previous else [],
            "reference_flags": reference_flags,
        }

    def generation_reference_paths(
        self,
        project_id: str,
        shot: Any,
        previous_shot: Any | None = None,
        *,
        context: ResolvedShotContext | None = None,
    ) -> dict[str, list[Path]]:
        """Resolve references for one shot without claiming T2V consumes images.

        The returned contract is deliberately provider-neutral.  T2V stores
        these inputs for audit and uses the textual locks; an I2V/R2V provider
        can later bind the same paths to actual conditioning inputs.
        """

        is_shot = not isinstance(shot, (int, str))
        shot_number = int(getattr(shot, "number", shot) or 0)
        scene_id = str((context.scene_id if context else getattr(shot, "scene_id", "")) or "")
        character_ids = set(context.character_ids if context else [str(item) for item in (getattr(shot, "character_ids", []) or [])])
        prop_ids = set(context.prop_ids if context else [str(item) for item in (getattr(shot, "prop_ids", []) or [])])
        bank = self.load(project_id)
        usable = [
            asset for asset in bank.assets
            if asset.approved
            and not bool((asset.metadata or {}).get("stale"))
            and Path(asset.path).is_file()
        ]

        def field(asset: ReferenceAsset, key: str) -> str:
            value = getattr(asset, key, "") or (asset.metadata or {}).get(key) or ""
            if isinstance(value, list):
                return ",".join(str(item) for item in value)
            return str(value)

        character_assets = [asset for asset in usable if asset.kind in {"character", "character_hero"}]
        reference_flags: list[str] = []
        if character_ids:
            character_assets = [
                asset for asset in character_assets
                if character_ids.intersection(set(field(asset, "character_ids").split(",")))
                or field(asset, "character_id") in character_ids
            ]
            if not character_assets:
                reference_flags.append("MISSING_CHARACTER_REFERENCE")
        scene_assets = [asset for asset in usable if asset.kind == "scene"]
        if scene_id:
            scene_assets = [asset for asset in scene_assets if field(asset, "scene_id") == scene_id]
            if not scene_assets:
                reference_flags.append("MISSING_SCENE_REFERENCE")
        prop_assets = [asset for asset in usable if asset.kind == "prop"]
        if prop_ids:
            prop_assets = [
                asset for asset in prop_assets
                if prop_ids.intersection(set(field(asset, "prop_ids").split(",")))
                or field(asset, "prop_id") in prop_ids
            ]
            if not prop_assets:
                reference_flags.append("MISSING_PROP_REFERENCE")
        previous = []
        requires_previous = context.previous_visual_reference_allowed if context else should_use_previous_frame(shot, previous_shot)
        if requires_previous and (previous_shot is not None or not is_shot):
            previous = [
                asset for asset in usable
                if asset.kind == "previous_approved_shot_ending_frame"
                and asset.shot_number is not None
                and (
                    not is_shot
                    or (
                        previous_shot is not None
                        and asset.shot_number == int(getattr(previous_shot, "number", 0) or 0)
                        and asset.revision == int(getattr(previous_shot, "revision", 1) or 1)
                    )
                )
            ]
        previous.sort(key=lambda asset: (int(asset.shot_number or 0), int(asset.revision or 1), asset.created_at))
        palette = [asset for asset in usable if asset.kind == "palette"]
        cinematography = [asset for asset in usable if asset.kind == "cinematography"]
        if requires_previous and is_shot and previous_shot is not None and not previous:
            reference_flags.append("MISSING_PREVIOUS_ENDING_REFERENCE")
        return {
            "character": [Path(asset.path) for asset in character_assets[:3]],
            "scene": [Path(asset.path) for asset in scene_assets[:2]],
            "prop": [Path(asset.path) for asset in prop_assets[:3]],
            "previous_frame": [Path(previous[-1].path)] if previous else [],
            "palette": [Path(asset.path) for asset in palette[:1]],
            "cinematography": [Path(asset.path) for asset in cinematography[:1]],
            "reference_flags": reference_flags,
        }

    def approved_generation_inputs(
        self,
        project_id: str,
        shot: Any,
        previous_shot: Any | None = None,
        *,
        context: ResolvedShotContext | None = None,
        require_keyframe: bool = False,
    ) -> dict[str, list[Path]]:
        """Resolve every real-generation input through one approval gate.

        Character/scene/prop references are already filtered by
        ``generation_reference_paths``.  A shot keyframe is additionally
        matched to the persisted Reference Bank record, current shot revision,
        and shot number; a file existing on disk is never sufficient.
        """

        inputs = self.generation_reference_paths(project_id, shot, previous_shot, context=context)
        shot_number = int(getattr(shot, "number", 0) or 0)
        shot_revision = max(1, int(getattr(shot, "revision", 1) or 1))
        keyframe_value = str((getattr(shot, "media_generation", {}) or {}).get("keyframe_path") or "").strip()
        keyframe_path = Path(keyframe_value) if keyframe_value else None
        if keyframe_path is None:
            if require_keyframe:
                raise ValueError(
                    f"REFERENCE_REVIEW_REQUIRED: Shot {shot_number} requires an approved current keyframe."
                )
            return inputs

        bank = self.load(project_id)
        matching = next(
            (
                asset
                for asset in bank.assets
                if Path(asset.path).resolve() == keyframe_path.resolve()
                and asset.approved
                and not bool((asset.metadata or {}).get("stale"))
                and Path(asset.path).is_file()
                and int(asset.revision or 1) == shot_revision
                and int(asset.shot_number or 0) == shot_number
            ),
            None,
        )
        if matching is None:
            if not require_keyframe:
                flags = list(inputs.get("reference_flags") or [])
                flags.append("KEYFRAME_PENDING_OR_STALE_OMITTED")
                inputs["reference_flags"] = flags
                return inputs
            raise ValueError(
                f"REFERENCE_REVIEW_REQUIRED: Shot {shot_number} keyframe is pending, stale, or from another revision."
            )
        inputs["keyframe"] = [Path(matching.path)]
        return inputs
