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
    story_beats = [item for item in project.get("story_beats", []) if isinstance(item, dict)]
    beat_ids = {str(item.get("beat_id")) for item in story_beats if item.get("beat_id")}
    shot_beat_ids = {str(item.get("beat_id")) for item in shots if item.get("beat_id")}
    narrative = round(len(beat_ids & shot_beat_ids) / len(beat_ids), 3) if beat_ids else None
    review = project.get("storyboard_review") or {}
    flag_values = [str(flag).upper() for item in shots for flag in (item.get("qc_flags") or [])]
    speech_policies = (project.get("script") or {}).get("speech_policy_by_shot") or {}
    scores: dict[str, list[float]] = {}
    for item in shots:
        visual = ((item.get("qc_details") or {}).get("visual") or {})
        for key, value in ((visual.get("scores") or {}).items() if isinstance(visual.get("scores"), dict) else []):
            if isinstance(value, (int, float)):
                scores.setdefault(str(key), []).append(float(value))

    def score_summary(key: str) -> tuple[float | None, float | None]:
        values = scores.get(key) or []
        return (round(sum(values) / len(values), 2), min(values)) if values else (None, None)

    missing_visual_locks = []
    world = project.get("story_world") or {}
    bible = project.get("visual_bible") or {}
    for kind, prefix, lock_keys in (
        ("characters", "character", ("appearance_lock", "face_lock", "costume_lock", "lock")),
        ("scenes", "scene", ("environment_lock", "architecture_lock", "lighting_lock", "palette_lock", "lock")),
        ("props", "prop", ("appearance_lock", "material_lock", "color_lock", "state_rules", "lock")),
    ):
        available = {str(item.get(f"{prefix}_id")): item for item in (bible.get(kind) or []) if isinstance(item, dict)}
        world_entities = (world.get(kind) or {}).items() if isinstance(world.get(kind), dict) else []
        for key, entity in world_entities:
            if not any(str(available.get(str(key), {}).get(lock) or "").strip() for lock in lock_keys):
                missing_visual_locks.append(f"{kind}:{key}")
    retry_count = sum(int(item.get("retry_count", 0) or 0) for item in shots)
    mix = project.get("mix_state") or {}
    return {
        "Narrative Continuity": narrative,
        "Beat Coverage": narrative,
        "Storyboard Health": review.get("overall_storyboard_health"),
        "Repair Count": sum("repair" in str(log).lower() for log in project.get("logs", [])),
        "Low Relevance Count": sum(flag == "LOW_RELEVANCE_SHOT" for flag in flag_values),
        "Redundant Count": sum(flag in {"REDUNDANT_SHOT", "REPEATED_INFORMATION", "REPEATED_VISUAL_FUNCTION"} for flag in flag_values),
        "Transition Conflict Count": sum(flag == "TRANSITION_CONFLICT" for flag in flag_values) + len(review.get("transition_conflicts") or []),
        "Speech Density": round(sum(1 for value in speech_policies.values() if str(value).upper() not in {"SILENT", "AMBIENCE_ONLY"}) / len(speech_policies), 3) if speech_policies else None,
        "Silent Shot Ratio": round(sum(1 for value in speech_policies.values() if str(value).upper() in {"SILENT", "AMBIENCE_ONLY"}) / len(speech_policies), 3) if speech_policies else None,
        "Unknown Entity References": project.get("story_world_validation", {}).get("unknown_count") if isinstance(project.get("story_world_validation"), dict) else None,
        "Missing Visual Locks": missing_visual_locks or None,
        "Missing References": sorted({flag for flag in flag_values if flag.startswith("MISSING_")}) or None,
        "Character Identity Avg": score_summary("character_identity")[0],
        "Character Identity Min": score_summary("character_identity")[1],
        "Costume Avg": score_summary("costume")[0],
        "Costume Min": score_summary("costume")[1],
        "Face Hair Avg": score_summary("face_hair")[0],
        "Face Hair Min": score_summary("face_hair")[1],
        "Scene Geometry Avg": score_summary("scene_geometry")[0],
        "Scene Geometry Min": score_summary("scene_geometry")[1],
        "Prop Avg": score_summary("props")[0],
        "Prop Min": score_summary("props")[1],
        "Palette": score_summary("palette")[0],
        "Lighting": score_summary("lighting")[0],
        "Camera Language": score_summary("camera_language")[0],
        "Film Texture": score_summary("film_texture")[0],
        "Narrative State": score_summary("narrative_state")[0],
        "Worst Shot": min((item.get("number") for item in shots if item.get("qc_status") in {"FAILED", "STALE"}), default=None),
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
        "Speech Timeline Accuracy": (project.get("script") or {}).get("voice_timeline", {}).get("status") if isinstance((project.get("script") or {}).get("voice_timeline"), dict) else None,
        "Speech Overflow Count": len((project.get("script") or {}).get("voice_timeline", {}).get("overflow") or []) if isinstance((project.get("script") or {}).get("voice_timeline"), dict) else None,
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
    report = {"suite": "golden-film-evaluation", "version": 2, "projects": entries}
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
