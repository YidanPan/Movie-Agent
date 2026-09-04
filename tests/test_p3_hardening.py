import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from movie_agent.agents.editor import EditorAgent
from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.services.errors import classify_error, clear_failure, error_info, record_failure
from movie_agent.storage.project_store import ProjectStore


def make_orchestrator(root: Path) -> MovieOrchestrator:
    settings = Settings(
        "http://127.0.0.1:8188",
        900,
        root / "workflows",
        9071,
        root / "projects",
        True,
        outputs_dir=root / "outputs",
    )
    return MovieOrchestrator(settings)


def test_structured_failure_is_safe_and_retryable():
    error = RuntimeError("ModelScope API key=super-secret timed out")
    code, recoverable = classify_error(error, stage="generation")
    assert code == "SERVICE_TIMEOUT"
    assert recoverable is True
    info = error_info(error, stage="generation", retry_count=2)
    assert info["retry_count"] == 2
    assert "super-secret" not in info["error_message"]
    assert "REDACTED" in info["error_message"]


def test_failure_metadata_can_be_cleared_without_losing_attempt_count():
    with TemporaryDirectory() as temporary_directory:
        project = make_orchestrator(Path(temporary_directory)).create_project(
            "A night watchman follows a signal beyond the moon.", 48, "film sci-fi"
        )
        shot = project.storyboard[0]
        record_failure(shot, TimeoutError("ComfyUI timed out"), stage="generation")
        assert shot.error_code == "SERVICE_TIMEOUT"
        assert shot.retry_count == 1
        clear_failure(shot)
        assert shot.error_code == ""
        assert shot.retry_count == 1
        assert shot.last_error == {}


def test_project_store_recovers_from_a_corrupt_primary_snapshot():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = make_orchestrator(root)
        project = orchestrator.create_project(
            "A night watchman follows a signal beyond the moon.", 48, "film sci-fi"
        )
        store = ProjectStore(root / "projects")
        target = root / "projects" / project.project_id / "project.json"
        project.logs.append("new mutation")
        store.save(project)
        backup = target.with_name("project.json.bak")
        assert backup.is_file()
        assert json.loads(backup.read_text(encoding="utf-8"))["project_id"] == project.project_id
        target.write_text("{ this is not valid json", encoding="utf-8")
        recovered = store.load(project.project_id)
        assert recovered.project_id == project.project_id
        assert "new mutation" not in recovered.logs
        recovered.logs.append("recovery save")
        store.save(recovered)
        target.write_text("{ still corrupt", encoding="utf-8")
        assert "new mutation" not in store.load(project.project_id).logs


def test_delivery_export_never_promotes_a_rough_cut_to_master():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = make_orchestrator(root)
        project = orchestrator.create_project(
            "A night watchman follows a signal beyond the moon.", 48, "film sci-fi"
        )
        project.status = "completed_mock"
        project.script["dialogue_locked"] = True
        rough = root / "rough-cut.mp4"
        rough.write_bytes(b"proxy")
        project.rough_cut_placeholder = str(rough)
        project.video_assets = {"screening_preview": {"path": str(rough), "stale": False}}
        with pytest.raises(RuntimeError, match="Final Cut has not been rendered"):
            EditorAgent(orchestrator.settings).export_variant(project)


def test_health_checks_are_capability_only():
    import server

    checks = server.runtime_checks()
    assert {"projects_storage", "outputs_storage", "ffmpeg", "ffprobe", "model_provider", "comfyui_workflow"} <= set(checks)
    assert all(set(item) >= {"ok", "required"} for item in checks.values())
