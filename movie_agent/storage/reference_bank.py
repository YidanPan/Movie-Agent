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
    ) -> ReferenceAsset:
        if kind not in REFERENCE_KINDS:
            raise ValueError(f"Unsupported reference kind: {kind}")
        source_path = Path(source_path)
        if not source_path.is_file():
            raise FileNotFoundError(f"Reference file does not exist: {source_path}")
        bank = self.load(project_id)
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        reference_id = f"ref-{len(bank.assets) + 1:04d}"
        safe_name = self._slug_pattern.sub("-", name or f"{kind}-{reference_id}").strip("-.") or reference_id
        suffix = source_path.suffix.lower() or ".webp"
        target = self.project_dir(project_id) / f"{safe_name}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
        asset = ReferenceAsset(
            reference_id=reference_id,
            kind=kind,
            path=str(target),
            source=str(source),
            approved=bool(approved),
            shot_number=shot_number,
            revision=max(1, int(revision or 1)),
            created_at=timestamp,
            metadata=dict(metadata or {}),
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
        usable = [asset for asset in bank.assets if asset.approved and Path(asset.path).is_file()]
        character = [asset for asset in usable if asset.kind in {"character_hero", "character", "approved_keyframe"}]
        scene = [asset for asset in usable if asset.kind in {"scene", "palette", "cinematography"}]
        previous = [
            asset
            for asset in usable
            if asset.kind == "previous_approved_shot_ending_frame"
            and asset.shot_number is not None
            and asset.shot_number < shot_number
        ]
        return {
            "character_hero": [Path(asset.path) for asset in character[:2]],
            "current_scene": [Path(asset.path) for asset in scene[:3]],
            "previous_approved_shot_ending_frame": [Path(previous[-1].path)] if previous else [],
        }
