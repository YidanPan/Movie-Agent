"""Persistent visual references used by generation and continuity QC."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REFERENCE_KINDS = {
    "character_hero",
    "character",
    "scene",
    "palette",
    "prop",
    "cinematography",
    "review_keyframe",
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

    def __init__(self, outputs_root: Path) -> None:
        self.outputs_root = Path(outputs_root)

    def project_dir(self, project_id: str) -> Path:
        return self.outputs_root / project_id / "references"

    def manifest_path(self, project_id: str) -> Path:
        return self.project_dir(project_id) / "reference-bank.json"

    def load(self, project_id: str) -> ReferenceBank:
        path = self.manifest_path(project_id)
        if not path.is_file():
            return ReferenceBank(project_id=project_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        assets = [ReferenceAsset(**item) for item in payload.get("assets", []) if isinstance(item, dict)]
        return ReferenceBank(
            project_id=str(payload.get("project_id") or project_id),
            assets=assets,
            schema_version=max(1, int(payload.get("schema_version") or 1)),
        )

    def save(self, bank: ReferenceBank) -> Path:
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

    def register_file(
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
        target = self.project_dir(project_id) / f"{safe_name}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
        asset_metadata = dict(metadata or {})
        for key, value in (("character_id", character_id), ("scene_id", scene_id), ("role", role or kind)):
            if value:
                asset_metadata.setdefault(key, str(value))
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
            character_id=str(character_id or (metadata or {}).get("character_id") or ""),
            scene_id=str(scene_id or (metadata or {}).get("scene_id") or ""),
            role=str(role or (metadata or {}).get("role") or kind),
        )
        bank.assets.append(asset)
        self.save(bank)
        return asset

    def promote_shot_references(self, project_id: str, shot_number: int, revision: int) -> int:
        """Promote only this shot's review frames after manual approval."""

        bank = self.load(project_id)
        promoted = 0
        candidates = [
            asset
            for asset in bank.assets
            if asset.shot_number == shot_number
            and asset.revision == max(1, int(revision or 1))
            and asset.kind == "review_keyframe"
        ]
        for index, asset in enumerate(candidates):
            asset.kind = "previous_approved_shot_ending_frame" if index == len(candidates) - 1 else "approved_keyframe"
            asset.approved = True
            promoted += 1
        if promoted:
            self.save(bank)
        return promoted

    def qc_reference_paths(self, project_id: str, shot_number: int) -> dict[str, list[Path]]:
        """Resolve persistent, approved inputs for a shot's visual review."""

        bank = self.load(project_id)
        usable = [
            asset
            for asset in bank.assets
            if asset.approved
            and not bool((asset.metadata or {}).get("stale"))
            and Path(asset.path).is_file()
        ]
        character = [asset for asset in usable if asset.kind in {"character_hero", "character", "approved_keyframe"}]
        scene = [asset for asset in usable if asset.kind in {"scene", "palette", "cinematography"}]
        previous = [
            asset
            for asset in usable
            if asset.kind == "previous_approved_shot_ending_frame"
            and asset.shot_number is not None
            and asset.shot_number < shot_number
        ]
        latest_previous: dict[int, ReferenceAsset] = {}
        for asset in previous:
            if asset.shot_number is None:
                continue
            current = latest_previous.get(asset.shot_number)
            if current is None or (asset.revision, asset.created_at) > (current.revision, current.created_at):
                latest_previous[asset.shot_number] = asset
        return {
            "character_hero": [Path(asset.path) for asset in character[:2]],
            "current_scene": [Path(asset.path) for asset in scene[:3]],
            "previous_approved_shot_ending_frame": [Path(asset.path) for asset in latest_previous.values()][-1:] if latest_previous else [],
        }

    def generation_reference_paths(self, project_id: str, shot: Any) -> dict[str, list[Path]]:
        """Resolve references for one shot without claiming T2V consumes images.

        The returned contract is deliberately provider-neutral.  T2V stores
        these inputs for audit and uses the textual locks; an I2V/R2V provider
        can later bind the same paths to actual conditioning inputs.
        """

        shot_number = int(getattr(shot, "number", shot) or 0)
        scene_id = str(getattr(shot, "scene_id", "") or "")
        character_ids = {str(item) for item in (getattr(shot, "character_ids", []) or [])}
        bank = self.load(project_id)
        usable = [
            asset for asset in bank.assets
            if asset.approved
            and not bool((asset.metadata or {}).get("stale"))
            and Path(asset.path).is_file()
        ]

        def field(asset: ReferenceAsset, key: str) -> str:
            return str(getattr(asset, key, "") or (asset.metadata or {}).get(key) or "")

        character_assets = [asset for asset in usable if asset.kind in {"character", "character_hero"}]
        if character_ids:
            matched = [asset for asset in character_assets if field(asset, "character_id") in character_ids]
            character_assets = matched or character_assets
        scene_assets = [asset for asset in usable if asset.kind == "scene"]
        if scene_id:
            matched = [asset for asset in scene_assets if field(asset, "scene_id") == scene_id]
            scene_assets = matched or scene_assets
        previous = [
            asset for asset in usable
            if asset.kind == "previous_approved_shot_ending_frame"
            and asset.shot_number is not None
            and asset.shot_number < shot_number
        ]
        previous.sort(key=lambda asset: (int(asset.shot_number or 0), int(asset.revision or 1), asset.created_at))
        palette = [asset for asset in usable if asset.kind == "palette"]
        cinematography = [asset for asset in usable if asset.kind == "cinematography"]
        return {
            "character": [Path(asset.path) for asset in character_assets[:3]],
            "scene": [Path(asset.path) for asset in scene_assets[:2]],
            "previous_frame": [Path(previous[-1].path)] if previous else [],
            "palette": [Path(asset.path) for asset in palette[:1]],
            "cinematography": [Path(asset.path) for asset in cinematography[:1]],
        }
