"""Prepare deterministic plan-evaluation fixtures for the Golden Film suite.

This command deliberately stops before video generation.  It produces real,
persisted planning artifacts through the same orchestrator used by the app,
so CI can measure the planning contract without claiming that media exists.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator


def _settings(root: Path, projects_dir: Path) -> Settings:
    return Settings(
        comfy_base_url="http://127.0.0.1:8188",
        comfy_timeout_seconds=30,
        workflows_dir=root / "workflows",
        port=9071,
        projects_dir=projects_dir,
        mock_mode=True,
        model_provider="mock",
        video_generation_mode="comfyui",
        outputs_dir=root / "outputs",
    )


def prepare_golden(projects_dir: Path, golden_dir: Path | None = None) -> list[Path]:
    golden_root = golden_dir or Path(__file__).parent
    projects_dir = Path(projects_dir)
    projects_dir.mkdir(parents=True, exist_ok=True)
    root = projects_dir.parent
    orchestrator = MovieOrchestrator(_settings(root, projects_dir))
    written: list[Path] = []

    for golden_path in sorted(golden_root.glob("golden_project_*.json")):
        golden = json.loads(golden_path.read_text(encoding="utf-8"))
        golden_id = str(golden.get("project_id") or golden_path.stem)
        idea = str(golden.get("idea") or golden.get("title") or "A signal changes a quiet room.")
        expected = golden.get("expected") or {}
        duration = int(expected.get("duration_seconds") or 48)
        visual_style = str(golden.get("visual_style") or "grounded cinematic sci-fi")

        project = orchestrator.create_project(idea, duration, visual_style)
        transient_id = project.project_id
        payload = project.to_dict()
        # Golden fixture IDs are stable human-readable labels, while runtime
        # project IDs retain the film-xxxxxxxx contract.  The evaluator reads
        # these snapshots directly and therefore does not weaken the runtime
        # ID validator.
        payload["project_id"] = golden_id
        target_dir = projects_dir / golden_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "project.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(target)
        transient_dir = projects_dir / transient_id
        if transient_dir != target_dir and transient_dir.is_dir():
            shutil.rmtree(transient_dir)

    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare deterministic Golden Film plan fixtures.")
    parser.add_argument("--mode", choices=("mock",), default="mock")
    parser.add_argument("--projects-dir", type=Path, default=Path("projects"))
    args = parser.parse_args()
    paths = prepare_golden(args.projects_dir)
    print(json.dumps({"mode": args.mode, "projects": [str(path) for path in paths]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
