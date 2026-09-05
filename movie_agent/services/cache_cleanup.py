"""Safe cleanup for derived media caches.

The cleanup planner is intentionally allow-listed.  It never removes a
source asset, the current final master, or the two newest source revisions.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


_CACHE_DIRS = {"previews", "proxy", "proxies", "timing", "timing-cache", "normalized", "tmp", "temporary", "temp", "cache"}
_CACHE_MARKERS = ("proxy", "screening", "timing", "normalized", "temporary", "temp", "cache")


def _record_paths(project: Any) -> Iterable[tuple[Path, dict[str, Any]]]:
    for shot in getattr(project, "storyboard", []) or []:
        for record in ((getattr(shot, "media_assets", {}) or {}).values() if isinstance(getattr(shot, "media_assets", {}), dict) else []):
            if isinstance(record, dict) and record.get("path"):
                yield Path(str(record["path"])), record
        for record in getattr(shot, "asset_history", []) or []:
            if isinstance(record, dict) and record.get("path"):
                yield Path(str(record["path"])), record
    for record in (getattr(project, "video_assets", {}) or {}).values():
        if isinstance(record, dict) and record.get("path"):
            yield Path(str(record["path"])), record
    for record in getattr(project, "video_asset_history", []) or []:
        if isinstance(record, dict) and record.get("path"):
            yield Path(str(record["path"])), record


def _protected_paths(project: Any) -> set[Path]:
    protected: set[Path] = set()
    current_sources: dict[int, list[tuple[int, Path]]] = defaultdict(list)
    for shot in getattr(project, "storyboard", []) or []:
        number = int(getattr(shot, "number", 0) or 0)
        records = []
        media = getattr(shot, "media_assets", {}) or {}
        if isinstance(media, dict):
            records.extend(media.values())
        records.extend(getattr(shot, "asset_history", []) or [])
        for record in records:
            if not isinstance(record, dict) or not record.get("path"):
                continue
            path = Path(str(record["path"]))
            tier = str(record.get("tier") or "")
            if tier == "source" or record.get("asset_role") == "source":
                current_sources[number].append((int(record.get("revision", 1) or 1), path))
    for entries in current_sources.values():
        for _, path in sorted(entries, reverse=True)[:2]:
            protected.add(path.resolve())
    for path, record in _record_paths(project):
        if str(record.get("tier") or "") == "source":
            continue
        if record.get("tier") == "final_master" and not record.get("stale"):
            protected.add(path.resolve())
    return protected


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def cleanup_candidates(project: Any, output_root: Path) -> list[Path]:
    root = (Path(output_root) / str(getattr(project, "project_id", ""))).resolve()
    if not root.is_dir():
        return []
    protected = _protected_paths(project)
    stale_paths = {path.resolve() for path, record in _record_paths(project) if record.get("stale") and str(record.get("tier") or "") != "source"}
    candidates: set[Path] = set()
    for path in root.rglob("*"):
        if not path.is_file() or path.resolve() in protected:
            continue
        relative_parts = {part.lower() for part in path.relative_to(root).parts[:-1]}
        name = path.name.lower()
        allowed = bool(relative_parts & _CACHE_DIRS) or path.resolve() in stale_paths
        allowed = allowed or any(marker in name for marker in _CACHE_MARKERS) or name.endswith((".tmp", ".partial"))
        if allowed and _inside(path, root):
            candidates.add(path.resolve())
    return sorted(candidates)


def storage_summary(project: Any, output_root: Path) -> dict[str, Any]:
    root = (Path(output_root) / str(getattr(project, "project_id", ""))).resolve()
    total = sum(path.stat().st_size for path in root.rglob("*") if path.is_file()) if root.is_dir() else 0
    candidates = cleanup_candidates(project, output_root)
    cleanable = sum(path.stat().st_size for path in candidates if path.is_file())
    return {
        "project_id": str(getattr(project, "project_id", "")),
        "root": str(root),
        "total_bytes": total,
        "cleanable_bytes": cleanable,
        "file_count": sum(1 for path in root.rglob("*") if path.is_file()) if root.is_dir() else 0,
        "cleanable_file_count": len(candidates),
        "protected_source_policy": "current source + last 2 source revisions + current final master",
    }


def clean_working_cache(project: Any, output_root: Path) -> dict[str, Any]:
    candidates = cleanup_candidates(project, output_root)
    removed: list[str] = []
    bytes_removed = 0
    for path in candidates:
        try:
            size = path.stat().st_size
            path.unlink()
            bytes_removed += size
            removed.append(str(path))
        except (FileNotFoundError, OSError):
            continue
    summary = storage_summary(project, output_root)
    summary.update({"removed_files": len(removed), "removed_bytes": bytes_removed, "removed": removed})
    return summary


__all__ = ["clean_working_cache", "cleanup_candidates", "storage_summary"]
