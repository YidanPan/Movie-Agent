from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import time

from fastapi.testclient import TestClient

import server
from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.pipeline.jobs import JobLedger
from movie_agent.services.errors import error_info


ACCESS_TOKEN = "test-app-access-token"


def _settings(root: Path, **overrides) -> Settings:
    base = Settings(
        "http://127.0.0.1:8188",
        900,
        root / "workflows",
        9071,
        root / "projects",
        True,
        outputs_dir=root / "outputs",
        tts_provider="none",
        app_access_token=ACCESS_TOKEN,
    )
    return replace(base, **overrides)


def _install(monkeypatch, root: Path, settings: Settings) -> MovieOrchestrator:
    orchestrator = MovieOrchestrator(settings)
    monkeypatch.setattr(server, "settings", settings)
    monkeypatch.setattr(server, "orchestrator", orchestrator)
    monkeypatch.setattr(server, "job_ledger", JobLedger(settings.projects_dir))
    monkeypatch.setattr(server, "rate_limiter", server.RequestRateLimiter())
    with server.sessions_guard:
        server.sessions.clear()
    with server.project_creation_guard:
        server.project_creation_reservations.clear()
    return orchestrator


def _login(client: TestClient) -> None:
    response = client.post("/auth/login", json={"access_token": ACCESS_TOKEN})
    assert response.status_code == 200
    assert response.json() == {"authenticated": True}
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" not in cookie


def test_application_gate_health_and_cookie_session(monkeypatch):
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = _install(monkeypatch, root, _settings(root))
        project = orchestrator.create_project("A courier follows a signal beyond the moon.", 48, "film sci-fi")
        client = TestClient(server.app)

        health = client.get("/health")
        assert health.status_code == 200
        assert ACCESS_TOKEN not in health.text
        assert "projects_dir" not in health.text
        assert health.headers["x-content-type-options"] == "nosniff"
        assert health.headers["referrer-policy"] == "same-origin"
        assert "frame-ancestors 'self'" in health.headers["content-security-policy"]
        assert "X-Frame-Options" not in health.headers
        assert client.get("/").status_code == 401
        assert client.get("/api/projects").json()["error_code"] == "AUTH_REQUIRED"
        assert client.post("/auth/login", json={"access_token": "wrong-token"}).status_code == 401

        _login(client)
        assert client.get("/api/projects").status_code == 200
        mutation = client.patch(
            f"/api/projects/{project.project_id}/shots/1",
            json={"duration_seconds": 8},
            headers={"Origin": "http://testserver"},
        )
        assert mutation.status_code == 200
        csrf_rejected = client.patch(
            f"/api/projects/{project.project_id}/shots/1",
            json={"duration_seconds": 8},
        )
        assert csrf_rejected.status_code == 403
        assert csrf_rejected.json()["error_code"] == "CSRF_ORIGIN_REJECTED"

        assert client.post("/auth/logout").status_code == 200
        assert client.get("/api/projects").status_code == 401


def test_public_demo_provider_lock_and_readiness_fail_closed(monkeypatch):
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        settings = _settings(root, public_demo_mode=True, video_generation_mode="remote", remote_video_api_key="do-not-return")
        _install(monkeypatch, root, settings)
        monkeypatch.setattr(server, "_directory_ready", lambda path: True)
        monkeypatch.setattr(server, "_binary_ready", lambda binary: True)

        checks = server.runtime_checks()
        assert checks["public_demo_provider_lock"]["ok"] is False
        assert server.runtime_ready(checks) is False
        health = TestClient(server.app).get("/api/health/ready")
        assert health.status_code == 503
        assert "do-not-return" not in health.text

        client = TestClient(server.app)
        _login(client)
        response = client.post(
            "/api/projects/film-1234abcd/render/stream",
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 503
        assert response.json() == server.PUBLIC_DEMO_PROVIDER_ERROR


def test_public_demo_mock_lock_is_ready_and_disables_expensive_routes(monkeypatch):
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        settings = _settings(root, public_demo_mode=True, max_active_jobs=9, max_upload_mb=50)
        _install(monkeypatch, root, settings)
        monkeypatch.setattr(server, "_directory_ready", lambda path: True)
        monkeypatch.setattr(server, "_binary_ready", lambda binary: True)

        checks = server.runtime_checks()
        assert checks["public_demo_provider_lock"]["ok"] is True
        assert checks["public_demo_auth"]["ok"] is True
        assert server.runtime_ready(checks) is True
        assert server.effective_max_active_jobs() == 2
        assert server.effective_max_upload_mb() == 10

        client = TestClient(server.app)
        _login(client)
        response = client.post(
            "/api/projects/film-1234abcd/shots/1/render",
            headers={"Origin": "http://testserver"},
        )
        assert response.status_code == 403
        assert response.json()["error_code"] == "PUBLIC_DEMO_PROVIDER_DISABLED"
        upload = client.post(
            "/api/projects/film-1234abcd/audio/upload",
            headers={"Origin": "http://testserver", "X-Filename": "score.mp3"},
            content=b"not-written",
        )
        assert upload.status_code == 403
        assert upload.json()["error_code"] == "PUBLIC_DEMO_PROVIDER_DISABLED"

        created = client.post(
            "/api/projects/stream",
            json={"idea": "A courier follows a signal beyond the moon.", "duration": 48, "visual_style": "film sci-fi"},
            headers={"Origin": "http://testserver"},
        )
        assert created.status_code == 200
        assert '"type": "done"' in created.text
        for _ in range(100):
            if server.job_ledger.active_count() == 0:
                break
            time.sleep(0.01)
        assert server.job_ledger.active_count() == 0


def test_mutation_rate_limit_and_public_project_cap(monkeypatch):
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        settings = _settings(root)
        orchestrator = _install(monkeypatch, root, settings)
        client = TestClient(server.app)
        _login(client)
        monkeypatch.setitem(server.RATE_LIMITS, "mutation", (2, 60))
        headers = {"Origin": "http://testserver"}
        for _ in range(2):
            assert client.post("/api/projects/film-1234abcd/script/lock", headers=headers).status_code == 404
        limited = client.post("/api/projects/film-1234abcd/script/lock", headers=headers)
        assert limited.status_code == 429
        assert limited.json()["error_code"] == "RATE_LIMITED"

        project = orchestrator.create_project("A courier follows a signal beyond the moon.", 48, "film sci-fi")
        public_settings = replace(settings, public_demo_mode=True, public_max_projects=1)
        monkeypatch.setattr(server, "settings", public_settings)
        response = client.post(
            "/api/projects/stream",
            json={"idea": "A second courier follows a signal beyond the moon.", "duration": 48, "visual_style": "film sci-fi"},
            headers=headers,
        )
        assert response.status_code == 429
        assert response.json()["error_code"] == "PROJECT_CAPACITY_REACHED"
        assert project.project_id in orchestrator.store.list_project_ids()


def test_upload_limit_path_isolation_and_error_redaction(monkeypatch):
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        settings = _settings(root, max_upload_mb=1)
        orchestrator = _install(monkeypatch, root, settings)
        project = orchestrator.create_project("A courier follows a signal beyond the moon.", 48, "film sci-fi")
        client = TestClient(server.app)
        _login(client)

        oversized = client.post(
            f"/api/projects/{project.project_id}/audio/upload",
            headers={"Origin": "http://testserver", "X-Filename": "score.mp3", "Content-Length": str(2 * 1024 * 1024)},
            content=b"x",
        )
        assert oversized.status_code == 413
        assert client.get("/api/projects/%2e%2e%2fetc%2fpasswd").status_code in {400, 404}

        info = error_info(
            RuntimeError("Authorization: Bearer SECRET_VALUE at C:\\Users\\admin\\private.txt via https://10.0.0.1/internal"),
            stage="storage",
        )
        assert "SECRET_VALUE" not in info["error_message"]
        assert "C:\\Users" not in info["error_message"]
        assert "10.0.0.1" not in info["error_message"]
        assert "https://" not in info["error_message"]
        sanitized = server._sanitize_public_payload({"app_access_token": ACCESS_TOKEN, "safe": "ok"})
        assert sanitized == {"safe": "ok"}
