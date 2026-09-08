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


def test_job_ledger_idempotency_returns_same_operation_for_duplicate_key():
    with TemporaryDirectory() as temporary_directory:
        ledger = JobLedger(Path(temporary_directory) / "projects")
        first = ledger.start(
            "film-1234abcd",
            kind="export",
            stage="export",
            mutates_project=False,
            idempotency_key="export-001",
            project_revision="rev-7",
            expected_input_hash="hash-7",
        )
        replay = ledger.start(
            "film-1234abcd",
            kind="export",
            stage="export",
            mutates_project=False,
            idempotency_key="export-001",
            project_revision="rev-7",
            expected_input_hash="hash-7",
        )
        assert replay["idempotent_replay"] is True
        assert replay["job_id"] == first["job_id"]
        assert replay["operation_id"] == first["operation_id"]
        assert replay["project_revision"] == "rev-7"
        assert replay["expected_input_hash"] == "hash-7"


def test_job_ledger_lease_expiry_is_recoverable_and_not_active():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory) / "projects"
        ledger = JobLedger(root)
        job = ledger.start("film-1234abcd", kind="generation", stage="generation", lease_seconds=30)
        path = root / "film-1234abcd" / "job.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["lease_expires_at"] = "2000-01-01T00:00:00Z"
        path.write_text(json.dumps(payload), encoding="utf-8")
        restarted = JobLedger(root)
        summary = restarted.summary("film-1234abcd")
        assert summary["status"] == "recoverable_failed"
        assert summary["recovery_state"] == "RECOVERABLE_FAILED"
        assert restarted.runtime_state("film-1234abcd") == {"active_jobs": []}
        assert job["lease_expires_at"] != summary["lease_expires_at"]


def test_long_running_job_heartbeat_extends_lease():
    with TemporaryDirectory() as temporary_directory:
        ledger = JobLedger(Path(temporary_directory) / "projects")
        job = ledger.start("film-1234abcd", kind="generation", stage="generation", lease_seconds=30)
        before = job["lease_expires_at"]
        heartbeat = ledger.heartbeat("film-1234abcd", job["job_id"], lease_seconds=90)
        assert heartbeat is not None
        assert heartbeat["heartbeat_at"]
        assert heartbeat["lease_expires_at"] != before
        assert heartbeat["status"] == "running"


def test_job_ledger_persists_target_scope_for_runtime_readiness():
    with TemporaryDirectory() as temporary_directory:
        ledger = JobLedger(Path(temporary_directory) / "projects")
        job = ledger.start("film-1234abcd", kind="audio_track", stage="audio", track_key="music")
        assert job["track_key"] == "music"
        assert job["shot_number"] is None
        runtime = ledger.runtime_state("film-1234abcd")
        assert runtime["active_jobs"][0]["track_key"] == "music"


def test_readiness_runtime_ignores_non_mutating_job():
    with TemporaryDirectory() as temporary_directory:
        ledger = JobLedger(Path(temporary_directory) / "projects")
        job = ledger.start("film-1234abcd", kind="verification", stage="delivery", mutates_project=False)
        assert job["mutates_project"] is False
        assert ledger.runtime_state("film-1234abcd") == {"active_jobs": []}


def test_new_process_marks_a_stale_running_job_recoverable_and_keeps_resume_history():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        first = JobLedger(root / "projects")
        job = first.start("film-1234abcd", kind="generation", stage="generation")
        first.append("film-1234abcd", job["job_id"], {"type": "render_progress", "completed": 1, "total": 6})

        restarted = JobLedger(root / "projects")
        snapshot = restarted.snapshot("film-1234abcd", after=0)
        assert snapshot["job"]["status"] == "recoverable_failed"
        assert snapshot["job"]["recoverable"] is True
        assert snapshot["events"][0]["completed"] == 1


def test_job_ledger_pagination_cursor_advances_by_returned_page():
    with TemporaryDirectory() as temporary_directory:
        ledger = JobLedger(Path(temporary_directory) / "projects", max_events=120)
        job = ledger.start("film-1234abcd", kind="generation", stage="generation")
        for number in range(100):
            ledger.append("film-1234abcd", job["job_id"], {"type": "progress", "completed": number + 1, "total": 100})

        cursor = 0
        collected = []
        while True:
            page = ledger.snapshot("film-1234abcd", after=cursor, limit=17)
            collected.extend(event["event_id"] for event in page["events"])
            if not page["has_more"]:
                break
            assert page["next_cursor"] > cursor
            cursor = page["next_cursor"]
        assert collected == list(range(1, 101))


def test_restarted_active_job_is_persistently_recoverable_and_does_not_consume_capacity():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory) / "projects"
        first = JobLedger(root)
        job = first.start("film-1234abcd", kind="generation", stage="generation")
        restarted = JobLedger(root)
        assert restarted.summary("film-1234abcd")["status"] == "recoverable_failed"
        assert restarted.snapshot("film-1234abcd")["job"]["status"] == "recoverable_failed"
        assert restarted.runtime_state("film-1234abcd") == {"active_jobs": []}
        assert restarted.active_count() == 0
        assert restarted.find_job(job["job_id"])["status"] == "recoverable_failed"
        replacement = restarted.start("film-1234abcd", kind="generation", stage="generation")
        assert replacement["job_id"] != job["job_id"]


def test_job_history_keeps_completed_evaluator_lookup_after_a_new_job():
    with TemporaryDirectory() as temporary_directory:
        ledger = JobLedger(Path(temporary_directory) / "projects")
        first = ledger.start("film-1234abcd", kind="planning", stage="planning")
        ledger.finish("film-1234abcd", first["job_id"])
        second = ledger.start("film-1234abcd", kind="planning", stage="planning")
        assert ledger.find_job(first["job_id"])["status"] == "succeeded"
        assert ledger.find_job(second["job_id"])["status"] == "running"


def test_remote_video_provider_is_required_and_not_ready_when_protocol_is_unavailable(monkeypatch):
    import server

    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        settings = Settings(
            "http://127.0.0.1:8188", 900, root / "workflows", 9071,
            root / "projects", True, outputs_dir=root / "outputs",
            video_generation_mode="remote", remote_video_api_base="https://provider.invalid",
            remote_video_model="video-model", remote_video_api_key="secret",
        )
        monkeypatch.setattr(server, "settings", settings)
        checks = server.runtime_checks()
        assert checks["video_provider"]["provider"] == "remote"
        assert checks["video_provider"]["required"] is True
        assert checks["video_provider"]["ok"] is False
        assert server.runtime_ready(checks) is False


def test_serialized_project_restores_guarded_audio_preview_url_after_sanitization(monkeypatch):
    import server

    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = make_orchestrator(root)
        project = orchestrator.create_project("A night watchman follows a signal beyond the moon.", 48, "film sci-fi")
        audio = root / "voice.wav"
        audio.write_bytes(b"audio")
        project.audio_tracks = {"voice": {"media_path": str(audio), "status": "READY"}}
        monkeypatch.setattr(server, "orchestrator", orchestrator)
        monkeypatch.setattr(server, "settings", orchestrator.settings)
        monkeypatch.setattr(server, "job_ledger", JobLedger(root / "projects"))
        serialized = server.serialized_project(project)
        track = serialized["audio_tracks"]["voice"]
        assert "media_path" not in track
        assert track["preview_url"] == f"/api/projects/{project.project_id}/audio/tracks/voice"


def test_progress_events_do_not_embed_full_project_snapshots():
    import server

    source = Path(server.__file__).read_text(encoding="utf-8")
    assert '"type": "render_progress"' in source
    assert '"type": "edit_progress"' in source
    assert '"project": snapshot' not in source


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
