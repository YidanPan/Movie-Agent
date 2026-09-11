import inspect
import json
from dataclasses import replace
from types import SimpleNamespace

from scripts import stage5a_runtime_check as runtime_check


def test_fixed_media_binaries_execute_without_arbitrary_command(monkeypatch, capsys):
    calls = []

    monkeypatch.setattr(runtime_check.shutil, "which", lambda name: f"/usr/bin/{name}")

    def fake_run(command, **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=f"{command[0]} version 7.0\n")

    monkeypatch.setattr(runtime_check.subprocess, "run", fake_run)

    assert runtime_check.check_binaries() is True
    assert calls == [["ffmpeg", "-version"], ["ffprobe", "-version"]]
    assert len(inspect.signature(runtime_check.main).parameters) == 0
    assert "super-secret" not in capsys.readouterr().out


def test_workspace_creates_marker_and_temporary_write_is_clean(tmp_path, capsys):
    assert runtime_check.check_workspace(tmp_path) is True

    marker = tmp_path / runtime_check.MARKER_NAME
    assert json.loads(marker.read_text(encoding="utf-8")) == runtime_check.MARKER_PAYLOAD
    assert not (tmp_path / runtime_check.TEMP_NAME).exists()
    output = capsys.readouterr().out
    assert "persistence_marker_previous=ABSENT" in output
    assert "workspace_write_read=PASS" in output


def test_workspace_existing_marker_proves_restart_survival(tmp_path, capsys):
    assert runtime_check.check_workspace(tmp_path) is True
    capsys.readouterr()

    assert runtime_check.check_workspace(tmp_path) is True
    output = capsys.readouterr().out
    assert "persistence_marker_previous=PRESENT" in output
    assert "persistence_survived_restart=PASS" in output
    assert "persistence_marker_created=PASS" not in output


def test_application_self_check_uses_real_fastapi_contract(capsys):
    from server import app

    assert runtime_check.check_application(app) is True
    output = capsys.readouterr().out
    for evidence in (
        "endpoint_root=200",
        "endpoint_health=200",
        "endpoint_api_health=200",
        "endpoint_projects=200",
        "frontend_html=PASS",
        "frontend_css=PASS",
        "frontend_js=PASS",
        "frontend_same_origin=PASS",
    ):
        assert evidence in output


def test_application_self_check_accepts_configured_app_auth(monkeypatch, capsys):
    import server

    monkeypatch.setattr(server, "settings", replace(server.settings, app_access_token="stage5a-test-secret"))

    assert runtime_check.check_application(server.app) is True
    output = capsys.readouterr().out
    for evidence in (
        "endpoint_root=401",
        "endpoint_health=200",
        "endpoint_api_health=200",
        "endpoint_health_ready=200",
        "endpoint_projects=401",
        "auth_boundary=PASS",
        "access_screen=PASS",
        "project_auth_boundary=PASS",
        "frontend_html=PASS",
        "frontend_css=PASS",
        "frontend_js=PASS",
        "frontend_same_origin=PASS",
    ):
        assert evidence in output
    assert "stage5a-test-secret" not in output


def test_application_self_check_accepts_public_demo_auth_contract(monkeypatch, capsys):
    import server

    monkeypatch.setattr(
        server,
        "settings",
        replace(
            server.settings,
            app_access_token="stage5a-public-test-secret",
            public_demo_mode=True,
            model_provider="mock",
            image_generation_mode="mock",
            video_generation_mode="mock",
            tts_provider="none",
        ),
    )

    assert runtime_check.check_application(server.app) is True
    output = capsys.readouterr().out
    assert "endpoint_root=401" in output
    assert "endpoint_projects=401" in output
    assert "auth_boundary=PASS" in output
    assert "project_auth_boundary=PASS" in output
    assert "stage5a-public-test-secret" not in output


def test_application_self_check_rejects_unexpected_server_errors(capsys):
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    broken = FastAPI()

    @broken.get("/")
    def broken_root():
        return JSONResponse({"error": "internal"}, status_code=500)

    @broken.get("/health")
    def broken_health():
        return {"status": "ok"}

    @broken.get("/api/health")
    def broken_api_health():
        return {"status": "ok"}

    @broken.get("/api/health/ready")
    def broken_health_ready():
        return {"ready": True}

    @broken.get("/api/projects")
    def broken_projects():
        return JSONResponse({"error": "internal"}, status_code=503)

    assert runtime_check.check_application(broken) is False
    output = capsys.readouterr().out
    assert "endpoint_root=500" in output
    assert "endpoint_projects=503" in output
    assert "auth_boundary=FAIL" in output
    assert "project_auth_boundary=FAIL" in output
    assert "internal" not in output


def test_self_check_evidence_does_not_print_environment_secrets(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("REMOTE_VIDEO_API_KEY", "super-secret")
    monkeypatch.setenv("MODELSCOPE_API_KEY", "another-secret")

    assert runtime_check.check_workspace(tmp_path) is True
    output = capsys.readouterr().out
    assert "super-secret" not in output
    assert "another-secret" not in output
    assert "os.environ" not in output
