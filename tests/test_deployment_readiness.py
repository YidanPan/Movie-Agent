from pathlib import Path

from fastapi.testclient import TestClient

from server import app


def test_health_probe_is_lightweight_and_available_at_standard_path():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "REMOTE_VIDEO_API_KEY" not in response.text
    assert "Authorization" not in response.text


def test_mock_release_fails_closed_before_video_generation(monkeypatch):
    import server
    from dataclasses import replace

    server_settings = replace(server.settings, video_generation_mode="mock")
    # Keep this a route-boundary test even when a developer's local .env uses
    # a real renderer for separate, explicitly approved work.
    monkeypatch.setattr(server, "settings", server_settings)
    response = TestClient(app).post("/api/projects/nonexistent/render/stream")

    assert response.status_code == 400
    assert "mock mode" in response.json()["error"].lower()


def test_root_and_static_frontend_are_served_same_origin():
    client = TestClient(app)

    root = client.get("/")
    asset = client.get("/static/js/app.js")
    api_module = client.get("/static/js/api.js")

    assert root.status_code == 200
    assert "__MOVIE_AGENT_BUILD_VALUE__" not in root.text
    assert "/static/js/app.js" in root.text
    assert asset.status_code == 200
    assert api_module.status_code == 200
    assert "/api/projects/" in api_module.text


def test_dockerignore_excludes_runtime_secrets_and_media():
    dockerignore = Path(__file__).resolve().parents[1] / ".dockerignore"
    text = dockerignore.read_text(encoding="utf-8")

    for entry in (".env", "outputs", "projects", "*.mp4", "*.mov"):
        assert entry in text
