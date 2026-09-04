"""JSON persistence for movie planning projects."""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from threading import RLock
from pathlib import Path

from movie_agent.models import MovieProject


class ProjectStore:
    project_id_pattern = re.compile(r"film-[0-9a-f]{8}")

    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = RLock()

    def _project_dir(self, project_id: str) -> Path:
        if not self.project_id_pattern.fullmatch(project_id):
            raise ValueError("项目 ID 格式无效。")
        return self.root / project_id

    def save(self, project: MovieProject) -> Path:
        target_dir = self._project_dir(project.project_id)
        with self._lock:
            target_dir.mkdir(parents=True, exist_ok=True)
            now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            if not getattr(project, "created_at", ""):
                project.created_at = now
            project.updated_at = now
            project.schema_version = max(2, int(getattr(project, "schema_version", 2) or 2))
            target = target_dir / "project.json"
            backup = target_dir / "project.json.bak"
            temporary = target.with_suffix(".json.tmp")
            # Keep the last known-good snapshot before replacing the primary.
            # The backup is deliberately local to the project directory and
            # is ignored by Git alongside project JSON/media.
            if target.is_file():
                try:
                    existing_payload = json.loads(target.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Never replace a known-good backup with a corrupt
                    # primary if a recovery save follows a failed read.
                    pass
                else:
                    if isinstance(existing_payload, dict):
                        shutil.copy2(target, backup)
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(project.to_dict(), ensure_ascii=False, indent=2))
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(target)
        return target

    def load(self, project_id: str) -> MovieProject:
        project_dir = self._project_dir(project_id)
        target = project_dir / "project.json"
        if not target.exists():
            raise FileNotFoundError(f"找不到项目 {project_id}。")

        def read_snapshot(path: Path) -> MovieProject:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("snapshot root must be an object")
            return MovieProject.from_dict(payload)

        try:
            return read_snapshot(target)
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError, AttributeError) as primary_error:
            backup = project_dir / "project.json.bak"
            if not backup.is_file():
                raise RuntimeError(
                    f"项目 {project_id} 的 project.json 已损坏，且没有可恢复的备份。"
                ) from primary_error
            try:
                return read_snapshot(backup)
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError, ValueError, AttributeError) as backup_error:
                raise RuntimeError(
                    f"项目 {project_id} 的 project.json 与备份均已损坏，无法恢复。"
                ) from backup_error

    def list_project_ids(self) -> list[str]:
        """Return saved projects newest first without loading every project file."""
        if not self.root.exists():
            return []
        projects = [
            (project_file.stat().st_mtime, project_file.parent.name)
            for project_file in self.root.glob("*/project.json")
            if self.project_id_pattern.fullmatch(project_file.parent.name)
        ]
        return [project_id for _, project_id in sorted(projects, reverse=True)]

    def export(self, project_id: str) -> list[Path]:
        project = self.load(project_id)
        project_dir = self._project_dir(project_id)
        markdown_path = project_dir / "movie-plan.md"
        markdown_path.write_text(project.project_as_markdown(), encoding="utf-8")
        return [project_dir / "project.json", markdown_path]
