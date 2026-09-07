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

        def counted(project_value, settings_value, **kwargs):
            calls["count"] += 1
            return original(project_value, settings_value, **kwargs)

        monkeypatch.setattr(server, "production_readiness", counted)
        payload = server.serialized_project(project)
        assert calls["count"] == 1
        assert payload["readiness"] == payload["diagnostics"]["readiness"]
        assert payload["production_action_contract"]["schema_version"] == 3
        assert payload["production_action_contract"]["actions"]["RENDER_SHOT"]["scope"] == "shot"
        assert payload["production_action_contract"]["actions"]["RENDER_SHOT"]["mutates_project"] is True


def test_render_shot_ignores_unrelated_shot_blocker():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory), video_mode="comfyui")
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.renderer_contract = {"status": "READY", "valid": True}
        project.storyboard[0].status = "awaiting_visual_review"
        project.storyboard[0].qc_status = "AWAITING_VISUAL_REVIEW"
        result = action_readiness(project, orchestrator.settings, "RENDER_SHOT", shot_number=2)
        assert result["ready"] is True


def test_render_shot_is_blocked_by_target_blocker():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory), video_mode="comfyui")
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.renderer_contract = {"status": "READY", "valid": True}
        project.storyboard[0].qc_details = {
            "reference_required": True,
            "reference_flags": ["MISSING_SCENE_REFERENCE"],
        }
        result = action_readiness(project, orchestrator.settings, "RENDER_SHOT", shot_number=1)
        assert result["ready"] is False
        assert result["blockers"][0]["shot_number"] == 1


def test_global_renderer_blocker_blocks_every_render_shot():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory), video_mode="comfyui")
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.renderer_contract = {"status": "WORKFLOW_MISSING", "valid": False}
        assert action_readiness(project, orchestrator.settings, "RENDER_SHOT", shot_number=1)["ready"] is False
        assert action_readiness(project, orchestrator.settings, "RENDER_SHOT", shot_number=2)["ready"] is False


def test_replan_shot_does_not_require_renderer():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory), video_mode="comfyui")
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.renderer_contract = {"status": "WORKFLOW_MISSING", "valid": False}
        assert action_readiness(project, orchestrator.settings, "REPLAN_SHOT", shot_number=1)["ready"] is True
        assert action_readiness(project, orchestrator.settings, "REGENERATE_SHOT", shot_number=1)["ready"] is False


def test_action_context_rejects_invalid_shot_before_readiness():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory), video_mode="comfyui")
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        try:
            orchestrator.regenerate_shot(project.project_id, 999)
        except ValueError as error:
            assert "Shot number" in str(error)
        else:
            raise AssertionError("Invalid shot must be rejected before action readiness")


def test_optional_reference_warning_only_applies_to_render_actions():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory), video_mode="comfyui")
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.renderer_contract = {"status": "READY", "valid": True}
        project.storyboard[0].qc_details = {"reference_flags": ["MISSING_SCENE_REFERENCE"]}
        render_result = action_readiness(project, orchestrator.settings, "RENDER_SHOT", shot_number=1)
        edit_result = action_readiness(project, orchestrator.settings, "START_AI_EDIT")
        assert any(item["code"] == "MISSING_SCENE_REFERENCE" for item in render_result["warnings"])
        assert not any(item["code"] == "MISSING_SCENE_REFERENCE" for item in edit_result["warnings"])


def test_production_blocked_error_is_recoverable_when_resolution_exists():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.status = "ready_for_ai_edit"
        project.script["dialogue_locked"] = False
        try:
            ensure_action_ready(project, orchestrator.settings, "START_AI_EDIT")
        except ProductionBlockedError as error:
            assert error.to_dict()["recoverable"] is True
        else:
            raise AssertionError("Expected a recoverable production blocker")


def test_backend_action_contract_has_schema_version():
    from movie_agent.services.readiness import ACTION_CONTRACT_SCHEMA_VERSION, PRODUCTION_ACTION_CONTRACT

    assert PRODUCTION_ACTION_CONTRACT["schema_version"] == ACTION_CONTRACT_SCHEMA_VERSION == 3
    assert PRODUCTION_ACTION_CONTRACT["actions"]["RENDER_SHOT"]["scope"] == "shot"
    assert PRODUCTION_ACTION_CONTRACT["actions"]["REPLAN_AUDIO_TRACK"]["scope"] == "track"
    assert PRODUCTION_ACTION_CONTRACT["actions"]["RENDER_AUDIO_TRACK"]["mutates_project"] is True


def test_track_action_rejects_unknown_track():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        try:
            action_readiness(project, orchestrator.settings, "REGENERATE_AUDIO_TRACK", track_key="master")
        except ValueError as error:
            assert "Invalid audio track" in str(error)
        else:
            raise AssertionError("Unknown audio track must be rejected")


def test_voice_blocker_does_not_block_music_regeneration():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.audio_tracks["voice"]["status"] = "VOICE_PROVIDER_REQUIRED"
        project.audio_tracks["music"]["status"] = "READY"
        result = action_readiness(project, orchestrator.settings, "REGENERATE_AUDIO_TRACK", track_key="music")
        assert result["ready"] is True


def test_music_blocker_does_not_block_voice_regeneration():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        project.audio_tracks["voice"]["status"] = "READY"
        project.audio_tracks["music"]["status"] = "MUSIC_PROVIDER_REQUIRED"
        result = action_readiness(project, orchestrator.settings, "REGENERATE_AUDIO_TRACK", track_key="voice")
        assert result["ready"] is True


def test_same_track_active_job_blocks_conflicting_mutation():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        runtime = {"active_jobs": [{"job_id": "job-1", "kind": "audio_track", "status": "running", "track_key": "music"}]}
        result = action_readiness(project, orchestrator.settings, "REGENERATE_AUDIO_TRACK", track_key="music", runtime_state=runtime)
        assert result["ready"] is False
        assert result["blockers"][0]["code"] == "ACTIVE_PROJECT_MUTATION_JOB"


def test_other_track_job_does_not_block_unrelated_track():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        runtime = {"active_jobs": [{"job_id": "job-1", "kind": "audio_track", "status": "running", "track_key": "music"}]}
        result = action_readiness(project, orchestrator.settings, "REGENERATE_AUDIO_TRACK", track_key="voice", runtime_state=runtime)
        assert result["ready"] is False


def test_other_shot_active_job_does_not_block_review():
    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        runtime = {"active_jobs": [{"job_id": "job-1", "kind": "generation", "status": "running", "shot_number": 4}]}
        result = action_readiness(project, orchestrator.settings, "REVIEW_SHOT", shot_number=2, runtime_state=runtime)
        assert result["ready"] is True


def test_active_project_mutation_blocks_mutations_but_keeps_review_actions_available():
    from movie_agent.services.readiness import PRODUCTION_ACTIONS

    with TemporaryDirectory() as directory:
        orchestrator = make_orchestrator(Path(directory))
        project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
        runtime = {"active_jobs": [{"job_id": "job-1", "kind": "generation", "status": "running", "shot_number": 4, "mutates_project": True}]}
        for action, metadata in PRODUCTION_ACTIONS.items():
            if not metadata.get("mutates_project"):
                continue
            kwargs = {"shot_number": 1} if metadata.get("scope") == "shot" else {}
            kwargs["track_key"] = "music" if metadata.get("scope") == "track" else None
            if kwargs.get("track_key") is None:
                kwargs.pop("track_key")
            assert action_readiness(project, orchestrator.settings, action, runtime_state=runtime, **kwargs)["ready"] is False
        assert action_readiness(project, orchestrator.settings, "REVIEW_SHOT", shot_number=1, runtime_state=runtime)["ready"] is True
