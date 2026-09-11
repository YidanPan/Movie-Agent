"""HTTP-level Public Demo regression coverage.

These tests keep the real ModelScope planning code path (the configured
provider is ``modelscope``) while replacing only the network LLM exchange with
the deterministic structured test double.  Media remains explicitly mocked.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import server
from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.pipeline.jobs import JobLedger
from tests.test_mock_e2e_pipeline import FakeStructuredLLM


def _settings(root: Path) -> Settings:
    return Settings(
        "http://127.0.0.1:8188",
        900,
        root / "workflows",
        7860,
        root / "projects",
        True,
        model_provider="modelscope",
        modelscope_api_key="test-only-modelscope-key",
        image_generation_mode="mock",
        video_generation_mode="mock",
        tts_provider="none",
        public_demo_mode=True,
        app_access_token=None,
        public_max_projects=100,
        max_active_jobs=2,
        outputs_dir=root / "outputs",
    )


def _install(monkeypatch, root: Path, *, silent: bool = False) -> MovieOrchestrator:
    settings = _settings(root)
    fake = FakeStructuredLLM(silent=silent)
    monkeypatch.setattr("movie_agent.orchestrator.build_creative_llm", lambda _settings: fake)
    orchestrator = MovieOrchestrator(settings)
    monkeypatch.setattr(server, "settings", settings)
    monkeypatch.setattr(server, "orchestrator", orchestrator)
    monkeypatch.setattr(server, "job_ledger", JobLedger(settings.projects_dir))
    monkeypatch.setattr(server, "rate_limiter", server.RequestRateLimiter())
    with server.sessions_guard:
        server.sessions.clear()
    with server.project_creation_guard:
        server.project_creation_reservations.clear()
    with server.project_locks_guard:
        server.project_locks.clear()
    return orchestrator


def _events(response_text: str) -> list[dict]:
    events: list[dict] = []
    for chunk in response_text.split("\n\n"):
        data = next((line[6:] for line in chunk.splitlines() if line.startswith("data: ")), None)
        if data:
            events.append(json.loads(data))
    return events


def _create_project(client: TestClient) -> tuple[str, dict]:
    landing = client.get("/")
    assert landing.status_code == 200
    visitor = client.cookies.get(server.ANONYMOUS_VISITOR_COOKIE)
    assert visitor
    response = client.post(
        "/api/projects/stream",
        json={
            "idea": "A courier discovers that a silent city is waiting for one human answer.",
            "duration": 48,
            "visual_style": "restrained near-future cinema",
        },
    )
    assert response.status_code == 200, response.text
    events = _events(response.text)
    done = next((event for event in reversed(events) if event.get("type") == "done"), None)
    assert done and done.get("project", {}).get("project_id")
    project = done["project"]
    project_id = project["project_id"]
    assert client.get(f"/api/projects/{project_id}").status_code == 200
    return project_id, project


def _run_edit_to_completion(client: TestClient, project_id: str) -> dict:
    locked = client.post(f"/api/projects/{project_id}/script/lock")
    assert locked.status_code == 200, locked.text
    assert locked.json()["script"]["dialogue_locked"] is True

    audio_replan = client.post(f"/api/projects/{project_id}/audio/tracks/music/replan")
    assert audio_replan.status_code == 200, audio_replan.text

    rough_response = client.post(f"/api/projects/{project_id}/edit/stream", json={"music_mode": "ai"})
    assert rough_response.status_code == 200, rough_response.text
    rough_events = _events(rough_response.text)
    rough_done = next((event for event in reversed(rough_events) if event.get("type") == "done"), None)
    assert rough_done and rough_done.get("project", {}).get("status") == "rough_cut_ready"

    approved = client.post(f"/api/projects/{project_id}/edit/approve", json={"subtitle_mode": "soft"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "final_cut_approved"

    completed = client.post(f"/api/projects/{project_id}/final-master/generate")
    assert completed.status_code == 200, completed.text
    project = completed.json()
    assert project["status"] == "completed_mock"
    assert project["edit_plan"]["approved"] is True
    output_dir = server.settings.outputs_dir / project_id
    assert (output_dir / "subtitles.srt").is_file()
    assert (output_dir / "subtitles.vtt").is_file()
    assert not (output_dir / "final-cut.mp4").exists()
    return project


def test_anonymous_public_demo_dialogue_flow_end_to_end(tmp_path, monkeypatch):
    _install(monkeypatch, tmp_path)
    client = TestClient(server.app)

    project_id, created = _create_project(client)
    persisted_created = server.orchestrator.store.load(project_id)
    assert persisted_created.owner_id == client.cookies.get(server.ANONYMOUS_VISITOR_COOKIE)
    assert created["brief"]
    assert created["script"]["story"]
    assert created["visual_bible"]
    assert created["story_beats"]
    assert created["story_world"]
    assert created["storyboard"]
    assert created["script"]["dialogue_book"]
    assert created["script"]["subtitle_track"]
    assert len(created["script"]["speech_policy_by_shot"]) == len(created["storyboard"])
    assert created["status"] == "ready_for_ai_edit"

    persisted = client.get(f"/api/projects/{project_id}").json()
    assert persisted["project_id"] == project_id
    completed = _run_edit_to_completion(client, project_id)
    assert completed["status"] == "completed_mock"
    assert client.get(f"/api/projects/{project_id}").json()["status"] == completed["status"]


def test_anonymous_public_demo_silent_flow_end_to_end(tmp_path, monkeypatch):
    _install(monkeypatch, tmp_path, silent=True)
    client = TestClient(server.app)
    project_id, created = _create_project(client)

    assert created["script"]["dialogue_book"] == []
    assert created["script"]["subtitle_track"] == []
    assert set(created["script"]["speech_policy_by_shot"].values()) == {"SILENT"}
    completed = _run_edit_to_completion(client, project_id)
    assert completed["status"] == "completed_mock"


def test_anonymous_visitors_are_isolated(tmp_path, monkeypatch):
    orchestrator = _install(monkeypatch, tmp_path)
    client_a = TestClient(server.app)
    client_b = TestClient(server.app)
    project_id, _ = _create_project(client_a)
    visitor_a = client_a.cookies.get(server.ANONYMOUS_VISITOR_COOKIE)
    visitor_b = client_b.get("/").cookies.get(server.ANONYMOUS_VISITOR_COOKIE)
    assert visitor_a and visitor_b and visitor_a != visitor_b

    assert project_id in client_a.get("/api/projects").json()["projects"]
    assert project_id not in client_b.get("/api/projects").json()["projects"]
    assert client_b.get(f"/api/projects/{project_id}").status_code == 404
    assert client_b.post(f"/api/projects/{project_id}/script/lock").status_code == 404
    visitor_b_project_id, _ = _create_project(client_b)
    assert visitor_b_project_id != project_id
    assert visitor_b_project_id in client_b.get("/api/projects").json()["projects"]
    assert visitor_b_project_id not in client_a.get("/api/projects").json()["projects"]
    assert orchestrator.store.load(project_id).owner_id == visitor_a


def test_public_demo_replan_allowed_but_media_render_denied(tmp_path, monkeypatch):
    _install(monkeypatch, tmp_path)
    client = TestClient(server.app)
    project_id, _ = _create_project(client)

    shot_replan = client.post(f"/api/projects/{project_id}/shots/1/regenerate")
    assert shot_replan.status_code == 200, shot_replan.text
    recovered = shot_replan.json()
    assert recovered["status"] == "ready_for_ai_edit"
    assert recovered["storyboard"][0]["status"] == "approved_mock"
    assert recovered["storyboard"][0]["stale"] is False
    assert all(shot["status"] == "approved_mock" and shot["stale"] is False for shot in recovered["storyboard"])

    audio_replan = client.post(f"/api/projects/{project_id}/audio/tracks/music/replan")
    assert audio_replan.status_code == 200, audio_replan.text

    for path in (
        f"/api/projects/{project_id}/shots/1/render",
        f"/api/projects/{project_id}/render/stream",
        f"/api/projects/{project_id}/references/generate",
        f"/api/projects/{project_id}/audio/tracks/voice/generate",
        f"/api/projects/{project_id}/audio/tracks/music/render",
        f"/api/projects/{project_id}/audio/upload",
    ):
        response = client.post(path, json={} if path.endswith("references/generate") else None)
        assert response.status_code == 403, (path, response.status_code, response.text)
        assert response.json()["error_code"] == "PUBLIC_DEMO_PROVIDER_DISABLED"

    completed = _run_edit_to_completion(client, project_id)
    assert completed["status"] == "completed_mock"


def test_public_demo_survives_reload(tmp_path, monkeypatch):
    orchestrator = _install(monkeypatch, tmp_path)
    settings = server.settings
    client = TestClient(server.app)
    project_id, _ = _create_project(client)
    completed = _run_edit_to_completion(client, project_id)

    restarted = MovieOrchestrator(settings)
    monkeypatch.setattr(server, "orchestrator", restarted)
    reloaded = client.get(f"/api/projects/{project_id}")
    assert reloaded.status_code == 200
    project = reloaded.json()
    assert restarted.store.load(project_id).owner_id == client.cookies.get(server.ANONYMOUS_VISITOR_COOKIE)
    assert project["script"]["dialogue_locked"] is True
    assert project["storyboard"]
    assert project["edit_plan"]["approved"] is True
    assert project["status"] == completed["status"]
    assert restarted.store.load(project_id).status == completed["status"]
    assert orchestrator.store.load(project_id).status == completed["status"]


def test_modelscope_embedded_public_demo_keeps_visitor_cookie(tmp_path, monkeypatch):
    _install(monkeypatch, tmp_path)
    client = TestClient(server.app, base_url="https://luckypan-movie-agent.ms.show")

    response = client.get("/")

    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie
    assert "samesite=none" in cookie
