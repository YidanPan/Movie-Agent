import time
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

import server
from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.pipeline.jobs import JobLedger


def _orchestrator(root: Path) -> MovieOrchestrator:
    settings = Settings(
        "http://127.0.0.1:8188",
        900,
        root / "workflows",
        9071,
        root / "projects",
        True,
        outputs_dir=root / "outputs",
        max_active_jobs=2,
    )
    return MovieOrchestrator(settings)


def test_evaluator_api_starts_async_job_and_exposes_safe_views(monkeypatch):
    with TemporaryDirectory() as temporary_directory:
        orchestrator = _orchestrator(Path(temporary_directory))
        monkeypatch.setattr(server, "orchestrator", orchestrator)
        monkeypatch.setattr(server, "settings", orchestrator.settings)
        monkeypatch.setattr(server, "job_ledger", JobLedger(orchestrator.settings.projects_dir))

        client = TestClient(server.app)
        response = client.post(
            "/api/v1/generate",
            json={
                "idea": "A society where memory becomes subscription based.",
                "duration": 45,
                "visual_style": "cold cinematic sci-fi",
            },
        )
        assert response.status_code == 202
        submission = response.json()
        assert submission["status"] == "running"

        job = None
        for _ in range(100):
            job_response = client.get(f"/api/v1/jobs/{submission['job_id']}")
            assert job_response.status_code == 200
            job = job_response.json()
            if job["status"] not in {"queued", "running"}:
                break
            time.sleep(0.05)
        assert job is not None
        assert job["status"] == "succeeded"
        project_response = client.get(f"/api/v1/projects/{submission['project_id']}")
        assert project_response.status_code == 200
        project_payload = project_response.json()
        assert project_payload["project_id"] == submission["project_id"]
        assert "diagnostics" in project_payload
        assert "job" in project_payload["diagnostics"]
        assert "outputs_dir" not in str(project_payload)

        result = client.get(f"/api/v1/projects/{submission['project_id']}/result")
        assert result.status_code == 200
        assert result.json()["status"] == "not_ready"


def test_evaluator_idempotency_key_reuses_original_project_and_job(monkeypatch):
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = _orchestrator(root)
        monkeypatch.setattr(server, "orchestrator", orchestrator)
        monkeypatch.setattr(server, "settings", orchestrator.settings)
        monkeypatch.setattr(server, "job_ledger", JobLedger(orchestrator.settings.projects_dir))
        client = TestClient(server.app)
        request = {
            "idea": "A society where memory becomes subscription based.",
            "duration": 45,
            "visual_style": "cold cinematic sci-fi",
        }
        headers = {"Idempotency-Key": "round2-submit-001"}
        first = client.post("/api/v1/generate", json=request, headers=headers)
        assert first.status_code == 202
        replay = client.post("/api/v1/generate", json=request, headers=headers)
        assert replay.status_code == 200
        assert replay.json()["idempotent_replay"] is True
        assert replay.json()["project_id"] == first.json()["project_id"]
        assert replay.json()["job_id"] == first.json()["job_id"]
        for _ in range(100):
            if client.get(f"/api/v1/jobs/{first.json()['job_id']}").json()["status"] not in {"queued", "running"}:
                break
            time.sleep(0.05)
        index = root / "projects" / "evaluator-submissions.json"
        contents = index.read_text(encoding="utf-8")
        assert "round2-submit-001" not in contents
