import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.pipeline.jobs import JobAlreadyRunning, JobLedger


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


def test_job_ledger_persists_progress_and_redacts_event_content():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        ledger = JobLedger(root / "projects")
        job = ledger.start("film-1234abcd", kind="generation", stage="generation")
        event = ledger.append(
            "film-1234abcd",
            job["job_id"],
            {
                "type": "render_progress",
                "agent": "generation",
                "completed": 2,
                "total": 6,
                "description": "ComfyUI token=should-not-leak · Shot 02 ready",
            },
        )

        assert event and event["event_id"] == 1
        snapshot = ledger.snapshot("film-1234abcd", after=0)
        assert snapshot["job"]["progress"] == {"completed": 2, "total": 6}
        assert snapshot["events"][0]["description"] == "ComfyUI token=[REDACTED] · Shot 02 ready"
        encoded = json.dumps(snapshot, ensure_ascii=False)
        assert "should-not-leak" not in encoded
        assert (root / "projects" / "film-1234abcd" / "job.json").is_file()

        finished = ledger.finish("film-1234abcd", job["job_id"])
        assert finished and finished["status"] == "succeeded"
        assert ledger.snapshot("film-1234abcd")["job"]["status"] == "succeeded"


def test_job_ledger_rejects_duplicate_active_submission_and_allows_retry_after_finish():
    with TemporaryDirectory() as temporary_directory:
        ledger = JobLedger(Path(temporary_directory) / "projects")
        first = ledger.start("film-1234abcd", kind="ai_edit", stage="ai_edit")
        with pytest.raises(JobAlreadyRunning) as conflict:
            ledger.start("film-1234abcd", kind="ai_edit", stage="ai_edit")
        assert conflict.value.snapshot["job_id"] == first["job_id"]
        ledger.finish("film-1234abcd", first["job_id"])
        second = ledger.start("film-1234abcd", kind="ai_edit", stage="ai_edit")
        assert second["job_id"] != first["job_id"]


def test_new_process_marks_a_stale_running_job_orphaned_and_keeps_resume_history():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        first = JobLedger(root / "projects")
        job = first.start("film-1234abcd", kind="generation", stage="generation")
        first.append("film-1234abcd", job["job_id"], {"type": "render_progress", "completed": 1, "total": 6})

        restarted = JobLedger(root / "projects")
        snapshot = restarted.snapshot("film-1234abcd", after=0)
        assert snapshot["job"]["status"] == "orphaned"
        assert snapshot["job"]["recoverable"] is True
        assert snapshot["events"][0]["completed"] == 1


def test_job_route_and_project_payload_expose_the_same_safe_contract(monkeypatch):
    from fastapi.testclient import TestClient
    import server

    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = make_orchestrator(root)
        project = orchestrator.create_project(
            "A night watchman follows a signal beyond the moon.", 48, "film sci-fi"
        )
        monkeypatch.setattr(server, "orchestrator", orchestrator)
        monkeypatch.setattr(server, "settings", orchestrator.settings)
        monkeypatch.setattr(server, "job_ledger", JobLedger(root / "projects"))
        ledger = server.job_ledger
        job = ledger.start(project.project_id, kind="generation", stage="generation")
        ledger.append(project.project_id, job["job_id"], {"type": "render_progress", "completed": 3, "total": 6})

        client = TestClient(server.app)
        response = client.get(f"/api/projects/{project.project_id}/job?after=0")
        assert response.status_code == 200
        body = response.json()
        assert body["job"]["job_id"] == job["job_id"]
        assert body["events"][0]["completed"] == 3
        project_payload = client.get(f"/api/projects/{project.project_id}").json()
        assert project_payload["job"]["job_id"] == job["job_id"]
        assert project_payload["diagnostics"]["job"]["job_id"] == job["job_id"]
