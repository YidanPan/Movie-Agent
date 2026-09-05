"""JSON persistence for movie planning projects."""

from __future__ import annotations

import json
from pathlib import Path

from movie_agent.models import MovieProject


class ProjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, project: MovieProject) -> Path:
        target_dir = self.root / project.project_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "project.json"
        target.write_text(json.dumps(project.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return target
