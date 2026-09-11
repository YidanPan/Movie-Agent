"""Fixed, non-networked runtime evidence for the ModelScope Docker target.

This module deliberately has no command-line arguments and never accepts a
command from a request.  It checks only the two media executables required by
Movie-Agent, the ModelScope workspace contract, and the local FastAPI ASGI
application before the production server starts.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

WORKSPACE_PATH = Path("/mnt/workspace")
MARKER_NAME = "movie-agent-stage5a-runtime-marker.json"
TEMP_NAME = ".stage5a-write-test"
MARKER_PAYLOAD = {
    "marker": "movie-agent-stage5a",
    "created_by": "runtime-self-check",
}
TEMP_PAYLOAD = "movie-agent-stage5a-runtime-write-read"


def _emit(key: str, value: object) -> None:
    print(f"STAGE5A {key}={value}", flush=True)


def _run_fixed_binary(binary: str) -> bool:
    """Run only a fixed ``<binary> -version`` capability check."""

    path = shutil.which(binary)
    _emit(f"{binary}_path", path or "MISSING")
    if not path:
        _emit(f"{binary}_runtime", "FAIL")
        return False

    try:
        result = subprocess.run(
            [binary, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        _emit(f"{binary}_runtime", "FAIL")
        return False

    first_line = next((line.strip() for line in (result.stdout or "").splitlines() if line.strip()), "")
    passed = result.returncode == 0 and bool(first_line)
    _emit(f"{binary}_runtime", "PASS" if passed else "FAIL")
    if passed:
        _emit(f"{binary}_version", first_line[:200])
    return passed


def check_binaries() -> bool:
    """Verify the fixed ffmpeg and ffprobe runtime capabilities."""

    ffmpeg_ok = _run_fixed_binary("ffmpeg")
    ffprobe_ok = _run_fixed_binary("ffprobe")
    return ffmpeg_ok and ffprobe_ok


def check_workspace(workspace: Path = WORKSPACE_PATH) -> bool:
    """Verify workspace access and maintain a harmless restart marker."""

    try:
        workspace.mkdir(parents=True, exist_ok=True)
    except OSError:
        _emit("workspace_exists", "FAIL")
        _emit("workspace_writable", "FAIL")
        return False

    exists = workspace.exists() and workspace.is_dir()
    _emit("workspace_exists", "PASS" if exists else "FAIL")
    if not exists or not os.access(workspace, os.W_OK):
        _emit("workspace_writable", "FAIL")
        return False
    _emit("workspace_writable", "PASS")

    marker = workspace / MARKER_NAME
    marker_ok = True
    if marker.exists():
        try:
            previous = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = None
        if previous != MARKER_PAYLOAD:
            _emit("persistence_marker_previous", "INVALID")
            marker_ok = False
        else:
            _emit("persistence_marker_previous", "PRESENT")
            _emit("persistence_survived_restart", "PASS")
    else:
        _emit("persistence_marker_previous", "ABSENT")
        try:
            marker.write_text(json.dumps(MARKER_PAYLOAD, sort_keys=True) + "\n", encoding="utf-8")
            _emit("persistence_marker_created", "PASS")
        except OSError:
            _emit("persistence_marker_created", "FAIL")
            marker_ok = False

    temporary = workspace / TEMP_NAME
    temporary_created = False
    write_read_ok = False
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            temporary_created = True
            handle.write(TEMP_PAYLOAD)
        write_read_ok = temporary.read_text(encoding="utf-8") == TEMP_PAYLOAD
    except OSError:
        write_read_ok = False
    finally:
        if temporary_created:
            try:
                temporary.unlink()
            except OSError:
                write_read_ok = False
    _emit("workspace_write_read", "PASS" if write_read_ok else "FAIL")
    return marker_ok and write_read_ok


def _asset_paths(html: str, attribute: str, suffix: str) -> list[str]:
    paths = re.findall(rf"<{attribute}[^>]+(?:href|src)=['\"]([^'\"]+)", html, flags=re.IGNORECASE)
    return [path.split("?", 1)[0] for path in paths if path.startswith("/static/") and path.split("?", 1)[0].endswith(suffix)]


def _auth_enabled() -> bool:
    """Read the same loaded application settings used by the auth boundary."""

    import server

    return bool(server._app_access_token() or server._public_demo_mode())


def _health_payload_is_safe(response: Any) -> bool:
    if response.status_code != 200:
        return False
    text = response.text
    forbidden = re.compile(
        r"(?i)(app_access_token|modelscope_api_key|remote_video_api_key|authorization|"
        r"[a-z]:[\\/]|/(?:mnt|home|workspace|tmp|var|opt)/|https?://|\b\d{1,3}(?:\.\d{1,3}){3}\b)"
    )
    return not forbidden.search(text)


def check_application(application: Any) -> bool:
    """Probe the actual FastAPI app through an in-process ASGI client."""

    try:
        from fastapi.testclient import TestClient

        client = TestClient(application)
        auth_enabled = _auth_enabled()
        root = client.get("/")
        health = client.get("/health")
        api_health = client.get("/api/health")
        health_ready = client.get("/api/health/ready")
        projects = client.get("/api/projects")
    except Exception:
        for key in (
            "endpoint_root",
            "endpoint_health",
            "endpoint_api_health",
            "endpoint_health_ready",
            "endpoint_projects",
        ):
            _emit(key, "ERROR")
        return False

    _emit("endpoint_root", root.status_code)
    _emit("endpoint_health", health.status_code)
    _emit("endpoint_api_health", api_health.status_code)
    _emit("endpoint_health_ready", health_ready.status_code)
    _emit("endpoint_projects", projects.status_code)

    auth_root_ok = (
        root.status_code == 401
        and root.headers.get("content-type", "").startswith("text/html")
        and bool(root.text.strip())
        and 'action="/auth/login"' in root.text
    )
    html_ok = root.status_code == 200 and bool(root.text.strip()) and root.headers.get("content-type", "").startswith("text/html")
    project_boundary_ok = projects.status_code in {401, 403} if auth_enabled else projects.status_code == 200
    _emit("auth_boundary", "PASS" if (auth_root_ok if auth_enabled else html_ok) else "FAIL")
    _emit("access_screen", "PASS" if (auth_root_ok if auth_enabled else True) else "FAIL")
    _emit("project_auth_boundary", "PASS" if project_boundary_ok else "FAIL")

    static_index = Path(__file__).resolve().parents[1] / "static" / "index.html"
    try:
        static_html = static_index.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        static_html = ""
    static_html_ok = bool(static_html.strip())
    css_paths = _asset_paths(static_html, "link", ".css")
    js_paths = _asset_paths(static_html, "script", ".js")
    css_responses = [client.get(path) for path in css_paths]
    js_responses = [client.get(path) for path in js_paths]
    css_ok = bool(css_paths) and all(
        response.status_code == 200
        and bool(response.text)
        and response.headers.get("content-type", "").startswith("text/css")
        for response in css_responses
    )
    js_ok = bool(js_paths) and all(
        response.status_code == 200
        and bool(response.text)
        and "javascript" in response.headers.get("content-type", "")
        for response in js_responses
    )
    _emit("frontend_html", "PASS" if static_html_ok else "FAIL")
    _emit("frontend_css", "PASS" if css_ok else "FAIL")
    _emit("frontend_js", "PASS" if js_ok else "FAIL")

    static_dir = static_index.parent
    source_parts: list[str] = [static_html]
    for source in static_dir.rglob("*"):
        if source.is_file() and source.suffix.lower() in {".html", ".js", ".css"}:
            try:
                source_parts.append(source.read_text(encoding="utf-8"))
            except (OSError, UnicodeError):
                pass
    source = "\n".join(source_parts)
    forbidden = re.compile(r"https?://(?:localhost|127\.0\.0\.1)|localhost|127\.0\.0\.1|:9071", re.IGNORECASE)
    declared_assets = css_paths + js_paths
    same_origin = static_html_ok and bool(declared_assets) and all(path.startswith("/static/") for path in declared_assets) and "/api/" in source and not forbidden.search(source)
    _emit("frontend_same_origin", "PASS" if same_origin else "FAIL")

    if health_ready.status_code != 200:
        health_ready_ok = False
    else:
        try:
            health_ready_ok = health_ready.json().get("ready") is True
        except ValueError:
            health_ready_ok = False
    health_ok = all(_health_payload_is_safe(response) for response in (health, api_health, health_ready))
    routes_ok = all(response.status_code not in {500, 502, 503} for response in (root, projects))
    return (
        routes_ok
        and (auth_root_ok if auth_enabled else html_ok)
        and project_boundary_ok
        and static_html_ok
        and css_ok
        and js_ok
        and same_origin
        and health_ok
        and health_ready_ok
    )


def main() -> int:
    """Run the fixed startup checks; no user input or command arguments."""

    passed = check_binaries() and check_workspace()
    try:
        from server import app
    except Exception:
        _emit("application_import", "FAIL")
        return 1
    if not check_application(app):
        passed = False
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
