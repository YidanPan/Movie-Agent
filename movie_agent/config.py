"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    comfy_base_url: str
    port: int
    projects_dir: Path
    mock_mode: bool

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            comfy_base_url=os.getenv("COMFY_BASE_URL", "http://127.0.0.1:8188"),
            port=int(os.getenv("PORT", "9071")),
            projects_dir=Path(os.getenv("PROJECTS_DIR", "./projects")),
            mock_mode=os.getenv("MOCK_MODE", "true").lower() == "true",
        )
