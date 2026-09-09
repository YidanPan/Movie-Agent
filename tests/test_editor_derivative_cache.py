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
    assert shot.media_assets["final_master"]["source_signature"]
    assert shot.media_assets["final_master"]["input_revision"] == 2
    assert shot.media_assets["final_master"]["input_generation_input_hash"] == "render-b"

    editor.normalize_resolution(project)
    assert len(calls) == 1

    shot.revision = 3
    shot.generation_input_hash = "render-c"
    shot.media_assets["source"]["revision"] = 3
    shot.media_assets["source"]["generation_input_hash"] = "render-c"
    editor.normalize_resolution(project)
    assert len(calls) == 2

    source.write_bytes(b"source replaced by a new generation")
    editor.normalize_resolution(project)
    assert len(calls) == 3


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
    assert shot.media_assets["timing"]["source_signature"]
    assert shot.media_assets["timing"]["input_revision"] == 1
    assert shot.media_assets["timing"]["input_generation_input_hash"] == "render-a"

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


def test_empty_generation_hash_never_becomes_a_cache_wildcard(tmp_path, monkeypatch):
    project, editor = _editor_project(tmp_path)
    shot, source = _prepare_source(project, tmp_path, generation_hash="")
    shot.media_assets["source"]["generation_input_hash"] = ""
    calls = []

    def fake_run(command_prefix, output):
        calls.append(list(command_prefix))
        output.write_bytes(b"derivative")
        return "test_mezzanine"

    monkeypatch.setattr("movie_agent.agents.editor.asset_record", _fake_asset_record)
    monkeypatch.setattr(editor, "_run_mezzanine", fake_run)

    editor.normalize_resolution(project)
    editor.normalize_resolution(project)

    assert len(calls) == 2


def test_malformed_timing_identity_is_a_cache_miss(tmp_path, monkeypatch):
    project, editor = _editor_project(tmp_path)
    shot, source = _prepare_source(project, tmp_path)
    shot.source_duration_seconds = 4
    shot.duration_seconds = 6
    shot.timing_mode = "extend"
    target = tmp_path / "outputs" / project.project_id / "timing" / "shot-01-extend-6s-mezzanine.mov"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"old derivative")
    shot.media_assets["timing"] = {
        "path": str(target),
        "tier": "timing_intermediate",
        "revision": "not-a-number",
        "input_revision": 1,
        "generation_input_hash": "render-a",
        "input_generation_input_hash": "render-a",
        "derivative_kind": "timing",
        "derivative_input_fingerprint": "old-fingerprint",
        "input_path": str(source),
        "timing_mode": "extend",
        "desired_duration": 6,
        "native_duration": 4,
        "source_signature": {"size": source.stat().st_size, "mtime_ns": source.stat().st_mtime_ns},
        "stale": False,
    }
    calls = []

    def fake_run(command_prefix, output):
        calls.append(list(command_prefix))
        output.write_bytes(b"new derivative")
        return "test_mezzanine"

    monkeypatch.setattr(editor, "_run_mezzanine", fake_run)
    editor._materialized_shot_paths(project)

    assert len(calls) == 1
    assert shot.media_assets["timing"]["revision"] == 1
