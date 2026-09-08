from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

import server
from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.pipeline.jobs import JobLedger


def test_audio_upload_rejects_unsupported_type_before_writing(monkeypatch):
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        settings = Settings(
            "http://127.0.0.1:8188", 900, root / "workflows", 9071, root / "projects", True,
            outputs_dir=root / "outputs", max_upload_mb=1,
        )
        orchestrator = MovieOrchestrator(settings)
        project = orchestrator.create_project("A night watchman follows a signal beyond the moon.", 48, "film sci-fi")
        monkeypatch.setattr(server, "orchestrator", orchestrator)
        monkeypatch.setattr(server, "settings", settings)
        monkeypatch.setattr(server, "job_ledger", JobLedger(settings.projects_dir))

        response = TestClient(server.app).post(
            f"/api/projects/{project.project_id}/audio/upload",
            content=b"not audio",
            headers={"x-filename": "payload.exe"},
        )
        assert response.status_code == 415
        assert not (root / "outputs" / project.project_id / "audio").exists()


def test_audio_upload_rejects_declared_oversize(monkeypatch):
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        settings = Settings(
            "http://127.0.0.1:8188", 900, root / "workflows", 9071, root / "projects", True,
            outputs_dir=root / "outputs", max_upload_mb=1,
        )
        orchestrator = MovieOrchestrator(settings)
        project = orchestrator.create_project("A night watchman follows a signal beyond the moon.", 48, "film sci-fi")
        monkeypatch.setattr(server, "orchestrator", orchestrator)
        monkeypatch.setattr(server, "settings", settings)
        monkeypatch.setattr(server, "job_ledger", JobLedger(settings.projects_dir))

        response = TestClient(server.app).post(
            f"/api/projects/{project.project_id}/audio/upload",
            content=b"x" * (1024 * 1024 + 1),
            headers={"x-filename": "oversize.wav"},
        )
        assert response.status_code == 413
