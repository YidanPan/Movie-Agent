from pathlib import Path
from tempfile import TemporaryDirectory

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.services.readiness import ensure_action_ready, production_blockers, production_readiness


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
