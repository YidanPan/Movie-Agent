"""Run the small, repeatable Golden Film Evaluation suite.

The evaluator reports unavailable measurements as ``null`` instead of making
claims about media that has not been rendered or measured.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _project_metrics(project: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    shots = [item for item in project.get("storyboard", []) if isinstance(item, dict)]
    duration = project.get("duration_seconds")
    try:
        duration_error = abs(float(sum(float(item.get("duration_seconds", 0) or 0) for item in shots)) - float(duration)) if shots and duration is not None else None
    except (TypeError, ValueError):
        duration_error = None
    sources = [
        ((item.get("media_assets") or {}).get("source") or {})
        for item in shots
        if isinstance(item.get("media_assets"), dict)
    ]
    source_resolutions = [record.get("native_resolution") or record.get("source_resolution") for record in sources if isinstance(record, dict) and (record.get("native_resolution") or record.get("source_resolution"))]
    final_master = (project.get("video_assets") or {}).get("final_master") or {}
    alignment = (project.get("script") or {}).get("voice_alignment") or {}
    subtitles = [item for item in (project.get("script") or {}).get("subtitle_track", []) if isinstance(item, dict)]
    alignment_error = None
    if alignment.get("media_duration_seconds") is not None and subtitles:
        try:
            alignment_error = round(abs(float(subtitles[-1].get("end_seconds", 0)) - float(alignment["media_duration_seconds"])), 3)
        except (TypeError, ValueError):
            alignment_error = None
    narrative = None
    if shots:
        narrative = round(sum(bool(item.get("narrative_purpose") and item.get("starting_state") is not None and item.get("ending_state") is not None) for item in shots) / len(shots), 3)
    retry_count = sum(int(item.get("retry_count", 0) or 0) for item in shots)
    mix = project.get("mix_state") or {}
    return {
        "Narrative Continuity": narrative,
        "Character Consistency": project.get("continuity_lock", {}).get("character_lock_score"),
        "Scene Consistency": project.get("continuity_lock", {}).get("scene_lock_score"),
        "Subtitle Alignment Error": alignment_error,
        "Duration Error": round(duration_error, 3) if duration_error is not None else None,
        "Native Resolution": source_resolutions[0] if source_resolutions else None,
        "Final Resolution": final_master.get("conformed_resolution") or final_master.get("source_resolution"),
        "LUFS": mix.get("loudness_measured_lufs"),
        "True Peak": mix.get("true_peak_measured_dbtp"),
        "Retry Count": retry_count,
        "Generation Time": project.get("generation_time_seconds"),
        "API Calls": project.get("api_calls"),
        "Estimated Cost": project.get("estimated_cost"),
        "Alignment Method": alignment.get("method") or expected.get("alignment_method"),
        "Availability": "RENDERED" if final_master.get("path") else "PLAN ONLY",
    }


def evaluate_projects(projects_dir: Path, output_dir: Path, golden_dir: Path | None = None) -> dict[str, Any]:
    golden_root = golden_dir or Path(__file__).parent
    entries = []
    for golden_path in sorted(golden_root.glob("golden_project_*.json")):
        golden = _load_json(golden_path)
        project_id = str(golden.get("project_id") or golden_path.stem)
        project_path = Path(projects_dir) / project_id / "project.json"
        project = _load_json(project_path) if project_path.is_file() else {}
        entries.append(
            {
                "project_id": project_id,
                "title": golden.get("title", project_id),
                "project_file": str(project_path) if project_path.is_file() else None,
                "metrics": _project_metrics(project, golden.get("expected") or {}),
            }
        )
    report = {"suite": "golden-film-evaluation", "version": 1, "projects": entries}
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "eval-report.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Golden Film Evaluation", "", f"Projects: {len(entries)}", ""]
    for entry in entries:
        lines.extend([f"## {entry['title']} ({entry['project_id']})", "", "| Metric | Value |", "|---|---:|"])
        for key, value in entry["metrics"].items():
            lines.append(f"| {key} | {value if value is not None else 'NOT AVAILABLE'} |")
        lines.append("")
    (output_dir / "eval-report.md").write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the three fixed golden film projects.")
    parser.add_argument("--projects-dir", type=Path, default=Path("projects"))
    parser.add_argument("--outputs-dir", type=Path, default=Path("evals"))
    args = parser.parse_args()
    evaluate_projects(args.projects_dir, args.outputs_dir)


if __name__ == "__main__":
    main()
