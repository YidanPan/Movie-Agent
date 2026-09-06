from pathlib import Path
from tempfile import TemporaryDirectory

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.services.readiness import (
    ProductionBlockedError,
    action_readiness,
    ensure_action_ready,
    production_blockers,
    production_readiness,
)


def make_orchestrator(root: Path, *, video_mode: str = "mock") -> MovieOrchestrator:
    settings = Settings(
        "http://127.0.0.1:8188",
        900,
        root / "workflows",
        9071,
        root / "projects",
        True,
        video_generation_mode=video_mode,
        outputs_dir=root / "outputs",
    )
    return MovieOrchestrator(settings)


def test_readiness_collects_previs_blocker():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.status = "previs_review_required"
        blockers = production_blockers(project, orchestrator.settings)
        assert any(item.code == "PREVIS_REVIEW_REQUIRED" for item in blockers)


def test_readiness_collects_renderer_contract_blocker():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory), video_mode="comfyui")
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.renderer_contract = {"status": "WORKFLOW_MISSING", "valid": False}
        assert any(item.code == "WORKFLOW_MISSING" for item in production_blockers(project, orchestrator.settings))


def test_readiness_collects_manual_visual_review_blocker():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        shot = project.storyboard[0]
        shot.status = "awaiting_visual_review"
        shot.qc_status = "AWAITING_VISUAL_REVIEW"
        result = production_readiness(project, orchestrator.settings)
        assert result["ready"] is False
        assert any(item["code"] == "MANUAL_VISUAL_REVIEW" for item in result["blockers"])


def test_readiness_collects_audio_timing_blocker():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.script["voice_timeline"] = {"status": "SCRIPT_TIMING_REVIEW", "overflow": False}
        assert any(item.code == "SCRIPT_TIMING_REVIEW" for item in production_blockers(project, orchestrator.settings))


def test_blockers_are_ordered_with_blocking_before_warning():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.storyboard[0].status = "awaiting_visual_review"
        project.storyboard[1].media_assets["source"] = {
            "path": "legacy.mp4",
            "generation_input_hash": "legacy",
            "renderer_verification_status": "UNVERIFIED_LEGACY",
            "stale": False,
        }
        blockers = production_blockers(project, orchestrator.settings)
        assert blockers[0].severity == "BLOCKING"
        assert any(item.code == "UNVERIFIED_LEGACY" and item.severity == "WARNING" for item in blockers)


def test_action_guard_uses_the_same_readiness_contract():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.status = "ready_for_ai_edit"
        project.script["dialogue_locked"] = False
        blockers = production_readiness(project, orchestrator.settings)["blockers"]
        assert any(item["code"] == "DIALOGUE_UNLOCKED" for item in blockers)
        try:
            ensure_action_ready(project, orchestrator.settings, "START_AI_EDIT")
        except ValueError as error:
            assert "DIALOGUE_UNLOCKED" in str(error)
        else:
            raise AssertionError("START_AI_EDIT should use the readiness blocker contract")


def test_stale_shot_does_not_block_start_render():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory), video_mode="comfyui")
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.script["dialogue_locked"] = True
        project.storyboard[0].stale = True
        project.renderer_contract = {"status": "READY", "valid": True}
        assert action_readiness(project, orchestrator.settings, "START_RENDER")["ready"] is True


def test_stale_shot_blocks_ai_edit_and_export():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.script["dialogue_locked"] = True
        project.storyboard[0].stale = True
        assert action_readiness(project, orchestrator.settings, "START_AI_EDIT")["ready"] is False
        assert action_readiness(project, orchestrator.settings, "EXPORT")["ready"] is False


def test_renderer_workflow_missing_blocks_render():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory), video_mode="comfyui")
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.renderer_contract = {"status": "WORKFLOW_MISSING", "valid": False}
        result = action_readiness(project, orchestrator.settings, "START_RENDER")
        assert result["ready"] is False
        assert result["blockers"][0]["code"] == "WORKFLOW_MISSING"


def test_audio_timing_review_allows_rough_cut_but_blocks_final_cut_and_export():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.script["dialogue_locked"] = True
        project.script["voice_timeline"] = {"status": "SCRIPT_TIMING_REVIEW", "overflow": True}
        assert action_readiness(project, orchestrator.settings, "START_AI_EDIT")["ready"] is True
        assert action_readiness(project, orchestrator.settings, "APPROVE_FINAL_CUT")["ready"] is False
        assert action_readiness(project, orchestrator.settings, "EXPORT")["ready"] is False


def test_rough_cut_missing_does_not_block_start_ai_edit():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.status = "rough_cut_ready"
        project.script["dialogue_locked"] = True
        project.rough_cut_placeholder = None
        project.edit_plan = {}
        assert action_readiness(project, orchestrator.settings, "START_AI_EDIT")["ready"] is True
        assert action_readiness(project, orchestrator.settings, "APPROVE_FINAL_CUT")["ready"] is False


def test_final_master_missing_does_not_block_generate_but_blocks_export():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.status = "completed_mock"
        project.script["dialogue_locked"] = True
        project.video_assets = {}
        assert action_readiness(project, orchestrator.settings, "GENERATE_FINAL_MASTER")["ready"] is True
        result = action_readiness(project, orchestrator.settings, "EXPORT")
        assert result["ready"] is False
        assert any(item["code"] == "FINAL_MASTER_MISSING" for item in result["blockers"])


def test_action_guard_raises_structured_production_blocked_error():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.status = "ready_for_ai_edit"
        project.script["dialogue_locked"] = False
        try:
            ensure_action_ready(project, orchestrator.settings, "START_AI_EDIT")
        except ProductionBlockedError as error:
            assert error.error_code == "PRODUCTION_BLOCKED"
            assert error.action == "START_AI_EDIT"
            assert "LOCK_DIALOGUE" in error.next_actions
            assert error.to_dict()["blockers"][0]["code"] == "DIALOGUE_UNLOCKED"
        else:
            raise AssertionError("Expected a structured production blocker")


def test_backend_production_blocked_error_returns_structured_blockers(monkeypatch):
    from fastapi.testclient import TestClient
    import server

    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.status = "ready_for_ai_edit"
        project.script["dialogue_locked"] = False
        orchestrator.store.save(project)
        monkeypatch.setattr(server, "orchestrator", orchestrator)
        monkeypatch.setattr(server, "settings", orchestrator.settings)
        response = TestClient(server.app).post(
            f"/api/projects/{project.project_id}/edit/approve",
            json={"subtitle_mode": "burned"},
        )
        assert response.status_code == 409
        body = response.json()
        assert body["error_code"] == "PRODUCTION_BLOCKED"
        assert body["action"] == "APPROVE_FINAL_CUT"
        assert body["blockers"][0]["code"] == "DIALOGUE_UNLOCKED"
        assert "LOCK_DIALOGUE" in body["next_actions"]


def test_serialized_project_computes_readiness_once(monkeypatch):
    import server

    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        calls = {"count": 0}
        original = server.production_readiness

        def counted(project_value, settings_value):
            calls["count"] += 1
            return original(project_value, settings_value)

        monkeypatch.setattr(server, "production_readiness", counted)
        payload = server.serialized_project(project)
        assert calls["count"] == 1
        assert payload["readiness"] == payload["diagnostics"]["readiness"]
