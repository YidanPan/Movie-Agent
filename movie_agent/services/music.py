"""Music provider contract.

Only Music is provider-backed at this stage.  SFX and ambience remain brief,
library, or manual-upload tracks until their own real renderers are justified.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Protocol


class MusicProvider(Protocol):
    """Render one complete score from a Music Brief."""

    name: str

    def render(self, brief: dict[str, Any], output_path: Path) -> Path:
        """Write a real audio asset and return its path."""


class FileMusicProvider:
    """Portable provider for an approved library or uploaded score file."""

    name = "file_music_provider"

    def __init__(self, source_path: Path) -> None:
        self.source_path = Path(source_path)

    def render(self, brief: dict[str, Any], output_path: Path) -> Path:
        if not self.source_path.is_file():
            raise FileNotFoundError(f"Music source not found: {self.source_path.name}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.source_path, output_path)
        return output_path


def render_music_asset(
    project: Any,
    provider: MusicProvider,
    output_dir: Path,
) -> dict[str, Any]:
    """Render a score and return metadata suitable for ``audio_tracks.music``."""

    output = Path(output_dir) / "score.wav"
    rendered = Path(provider.render(dict(getattr(project, "music_brief", {}) or {}), output))
    if not rendered.is_file() or rendered.stat().st_size <= 0:
        raise RuntimeError("Music provider returned no real audio asset.")
    return {
        "status": "READY",
        "provider": str(getattr(provider, "name", provider.__class__.__name__)),
        "media_path": str(rendered),
        "preview_url": f"/api/projects/{project.project_id}/audio/tracks/music",
        "source": "MUSIC PROVIDER · EMOTIONAL ARC",
        "brief_status": "AUDIO READY",
    }


__all__ = ["FileMusicProvider", "MusicProvider", "render_music_asset"]
