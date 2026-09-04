import json
from pathlib import Path
from tempfile import TemporaryDirectory

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.pipeline.diagnostics import delivery_preflight, diagnostics_snapshot
from movie_agent.services.errors import record_failure
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


def test_diagnostics_describe_resume_action_without_paths_or_secrets():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        project = make_orchestrator(root).create_project(
            "A night watchman follows a signal beyond the moon.", 48, "film sci-fi"
        )
        snapshot = diagnostics_snapshot(project, outputs_dir=root / "outputs")

        assert snapshot["pipeline_state"]["state"] == "shots_ready"
        assert snapshot["progress"] == {
            "shots_total": 6,
            "shots_ready": 6,
            "shots_failed": 0,
            "shots_stale": 0,
            "shots_pending": 0,
            "percent": 100,
        }
        assert snapshot["recoverability"]["next_action"] == "LOCK_DIALOGUE"
        assert snapshot["dialogue"]["locked"] is False
        encoded = json.dumps(snapshot, ensure_ascii=False)
        assert "outputs/" not in encoded
        assert "api_key" not in encoded.lower()


def test_diagnostics_keep_a_failed_shot_retryable_and_redacted():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        project = make_orchestrator(root).create_project(
            "A night watchman follows a signal beyond the moon.", 48, "film sci-fi"
        )
        shot = project.storyboard[2]
        record_failure(shot, TimeoutError("ComfyUI token=do-not-leak timed out"), stage="generation")
        shot.status = "generation_failed"
        project.status = "render_failed"

        snapshot = diagnostics_snapshot(project, outputs_dir=root / "outputs")
        failed = snapshot["errors"]["shots"]
        assert failed and failed[0]["number"] == shot.number
        assert failed[0]["error"]["error_code"] == "SERVICE_TIMEOUT"
        assert "do-not-leak" not in json.dumps(snapshot)
        assert snapshot["recoverability"]["next_action"] == "RETRY_RENDER"
        assert snapshot["recoverability"]["retryable_failures"] == 1


def test_project_store_recovers_when_primary_snapshot_is_missing():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = make_orchestrator(root)
        project = orchestrator.create_project(
            "A night watchman follows a signal beyond the moon.", 48, "film sci-fi"
        )
        # A second save creates project.json.bak, then simulate an interrupted
        # replacement that removed the primary file.
        project.logs.append("second snapshot")
        orchestrator.store.save(project)
        target_dir = root / "projects" / project.project_id
        (target_dir / "project.json").unlink()
        recovered = ProjectStore(root / "projects").load(project.project_id)
        assert recovered.project_id == project.project_id
        assert "second snapshot" not in recovered.logs


def test_delivery_preflight_requires_current_master_but_allows_unknown_probe_metadata():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        project = make_orchestrator(root).create_project(
            "A night watchman follows a signal beyond the moon.", 48, "film sci-fi"
        )
        project.status = "completed_mock"
        project.script["dialogue_locked"] = True
        master = root / "outputs" / project.project_id / "final-master.mp4"
        master.parent.mkdir(parents=True)
        master.write_bytes(b"test media")
        project.video_assets = {"final_master": {"path": str(master), "stale": False}}

        result = delivery_preflight(project, outputs_dir=root / "outputs", ffmpeg_ready=True)
        assert result["ready"] is True
        assert result["checks"]["final_master"]["ok"] is True
        assert result["output"] == {"width": 1920, "height": 1080, "codec": "H.264"}


def test_delivery_preflight_rejects_low_resolution_master(monkeypatch):
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        project = make_orchestrator(root).create_project(
            "A night watchman follows a signal beyond the moon.", 48, "film sci-fi"
        )
        project.status = "completed_mock"
        project.script["dialogue_locked"] = True
        master = root / "outputs" / project.project_id / "final-master.mp4"
        master.parent.mkdir(parents=True)
        master.write_bytes(b"test media")
        project.video_assets = {"final_master": {"path": str(master), "stale": False}}

        import movie_agent.pipeline.diagnostics as diagnostics

        monkeypatch.setattr(
            diagnostics,
            "probe_media",
            lambda *_args, **_kwargs: {"width": 608, "height": 352, "fps": 24, "duration_seconds": 48, "has_audio": True},
        )
        result = delivery_preflight(project, outputs_dir=root / "outputs", ffmpeg_ready=True)
        assert result["ready"] is False
        assert "resolution" in result["blocking"]
        assert "1080P" in result["blocking_reasons"][0] or any("1080P" in item for item in result["blocking_reasons"])


def test_diagnostics_and_preflight_routes_share_the_project_contract(monkeypatch):
    import server
    from fastapi.testclient import TestClient

    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = make_orchestrator(root)
        project = orchestrator.create_project(
            "A night watchman follows a signal beyond the moon.", 48, "film sci-fi"
        )
        monkeypatch.setattr(server, "orchestrator", orchestrator)
        monkeypatch.setattr(server, "settings", orchestrator.settings)
        response = TestClient(server.app).get(f"/api/projects/{project.project_id}/diagnostics")
        assert response.status_code == 200
        assert response.json()["project_id"] == project.project_id
        preflight = TestClient(server.app).get(
            f"/api/projects/{project.project_id}/delivery-preflight?resolution=1080p&aspect=16:9&subtitle_mode=burned"
        )
        assert preflight.status_code == 200
        assert preflight.json()["ready"] is False
        assert "final_cut" in preflight.json()["blocking"]


def test_export_route_returns_machine_readable_preflight_block(monkeypatch):
    import server
    from fastapi.testclient import TestClient

    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = make_orchestrator(root)
        project = orchestrator.create_project(
            "A night watchman follows a signal beyond the moon.", 48, "film sci-fi"
        )
        monkeypatch.setattr(server, "orchestrator", orchestrator)
        monkeypatch.setattr(server, "settings", orchestrator.settings)
        response = TestClient(server.app).post(
            f"/api/projects/{project.project_id}/export/video",
            json={"container": "mp4", "resolution": "1080p", "aspect": "16:9", "subtitle_mode": "burned"},
        )
        assert response.status_code == 409
        body = response.json()
        assert body["error_code"] == "DELIVERY_NOT_READY"
        assert body["preflight"]["ready"] is False
        assert "final_master" in body["preflight"]["blocking"]
