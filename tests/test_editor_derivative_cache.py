from pathlib import Path

from movie_agent.agents.editor import EditorAgent
from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator


def _editor_project(tmp_path: Path):
    settings = Settings(
        "http://127.0.0.1:8188",
        900,
        tmp_path / "workflows",
        9071,
        tmp_path / "projects",
        True,
        outputs_dir=tmp_path / "outputs",
    )
    project = MovieOrchestrator(settings).create_project(
        "A quiet signal crosses the midnight city.", 48, "film sci-fi"
    )
    project.storyboard = [project.storyboard[0]]
    return project, EditorAgent(settings)


def _fake_asset_record(path: Path, *, tier: str, **kwargs):
    return {
        "path": str(path),
        "tier": tier,
        "stale": False,
        "native_resolution": kwargs.get("native_resolution") or "608x352",
        "source_resolution": "1920x1080" if tier == "final_master" else "608x352",
        "source_fps": 24.0,
        "source_duration": 4.0,
        "generation_input_hash": kwargs.get("generation_input_hash", ""),
        "revision": kwargs.get("revision", 1),
    }


def _prepare_source(project, tmp_path: Path, *, revision: int = 1, generation_hash: str = "render-a"):
    shot = project.storyboard[0]
    source = tmp_path / "shots" / "shot-01.mp4"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"source")
    shot.output_placeholder = str(source)
    shot.revision = revision
    shot.generation_input_hash = generation_hash
    shot.media_assets["source"] = {
        "path": str(source),
        "tier": "source",
        "revision": revision,
        "generation_input_hash": generation_hash,
        "native_resolution": "608x352",
    }
    return shot, source


def test_normalized_cache_requires_current_revision_and_generation_hash(tmp_path, monkeypatch):
    project, editor = _editor_project(tmp_path)
    shot, source = _prepare_source(project, tmp_path, revision=2, generation_hash="render-b")
    output = tmp_path / "outputs" / project.project_id / "normalized" / "shots" / "shot-01-1080p-mezzanine.mov"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"old derivative")
    shot.media_assets["final_master"] = {
        "path": str(output),
        "tier": "final_master",
        "revision": 1,
        "generation_input_hash": "render-a",
        "derivative_kind": "resolution_normalize",
        "derivative_input_fingerprint": "old-fingerprint",
        "original_path": str(source),
        "stale": False,
    }
    calls = []

    def fake_run(command_prefix, target):
        calls.append(list(command_prefix))
        target.write_bytes(b"new derivative")
        return "test_mezzanine"

    monkeypatch.setattr("movie_agent.agents.editor.asset_record", _fake_asset_record)
    monkeypatch.setattr(editor, "_run_mezzanine", fake_run)

    editor.normalize_resolution(project)
    assert len(calls) == 1
    assert shot.media_assets["final_master"]["generation_input_hash"] == "render-b"
    assert shot.media_assets["final_master"]["derivative_input_fingerprint"]

    editor.normalize_resolution(project)
    assert len(calls) == 1

    shot.revision = 3
    shot.generation_input_hash = "render-c"
    shot.media_assets["source"]["revision"] = 3
    shot.media_assets["source"]["generation_input_hash"] = "render-c"
    editor.normalize_resolution(project)
    assert len(calls) == 2


def test_timing_cache_requires_persisted_fingerprint(tmp_path, monkeypatch):
    project, editor = _editor_project(tmp_path)
    shot, source = _prepare_source(project, tmp_path, revision=1, generation_hash="render-a")
    shot.source_duration_seconds = 4
    shot.duration_seconds = 6
    shot.timing_mode = "extend"
    target = tmp_path / "outputs" / project.project_id / "timing" / "shot-01-extend-6s-mezzanine.mov"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"old timing derivative")
    calls = []

    def fake_run(command_prefix, output):
        calls.append(list(command_prefix))
        output.write_bytes(b"new timing derivative")
        return "test_mezzanine"

    monkeypatch.setattr(editor, "_run_mezzanine", fake_run)

    assert editor._materialized_shot_paths(project) == [target]
    assert len(calls) == 1
    assert shot.media_assets["timing"]["tier"] == "timing_intermediate"
    assert shot.media_assets["timing"]["generation_input_hash"] == "render-a"

    assert editor._materialized_shot_paths(project) == [target]
    assert len(calls) == 1

    shot.revision = 2
    shot.generation_input_hash = "render-b"
    assert editor._materialized_shot_paths(project) == [target]
    assert len(calls) == 2


def test_legacy_timing_file_without_identity_is_not_reused(tmp_path, monkeypatch):
    project, editor = _editor_project(tmp_path)
    shot, source = _prepare_source(project, tmp_path, revision=1, generation_hash="render-a")
    shot.source_duration_seconds = 4
    shot.duration_seconds = 6
    shot.timing_mode = "slow_motion"
    target = tmp_path / "outputs" / project.project_id / "timing" / "shot-01-slow_motion-6s-mezzanine.mov"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"legacy derivative")
    calls = []

    def fake_run(command_prefix, output):
        calls.append(list(command_prefix))
        output.write_bytes(b"replacement")
        return "test_mezzanine"

    monkeypatch.setattr(editor, "_run_mezzanine", fake_run)
    editor._materialized_shot_paths(project)

    assert len(calls) == 1
    assert shot.media_assets["timing"]["derivative_input_fingerprint"]
