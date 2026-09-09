from pathlib import Path

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator


def _mock_settings(tmp_path: Path) -> Settings:
    return Settings(
        "http://127.0.0.1:8188",
        900,
        tmp_path / "workflows",
        7860,
        tmp_path / "projects",
        True,
        model_provider="mock",
        video_generation_mode="mock",
        tts_provider="none",
        outputs_dir=tmp_path / "outputs",
    )


def test_fresh_mock_production_survives_reload_to_final_approval(tmp_path):
    settings = _mock_settings(tmp_path)
    idea = "A commuter discovers that every human emotion in his city now requires a monthly subscription."

    first = MovieOrchestrator(settings)
    project = first.create_project(idea, 36, "near-future social sci-fi")
    assert project.status == "ready_for_ai_edit"
    assert project.storyboard
    assert all(shot.status == "approved_mock" and not shot.stale for shot in project.storyboard)

    project_id = project.project_id
    initial_shot_snapshot = [
        (shot.number, shot.revision, shot.generation_input_hash, shot.status)
        for shot in project.storyboard
    ]

    locked = first.lock_dialogue(project_id)
    assert locked.script["dialogue_locked"] is True
    assert locked.status == "ready_for_ai_edit"

    rough = first.create_rough_cut(project_id)
    assert rough.status == "rough_cut_ready"
    assert rough.rough_cut_placeholder == f"outputs/{project_id}/rough-cut-screening.mp4"
    assert rough.final_output_placeholder is None
    assert rough.mix_state["media_mixed"] is False

    approved = first.approve_edit(project_id, "soft")
    assert approved.status == "final_cut_approved"
    assert approved.subtitle_mode == "soft"
    assert approved.edit_plan["approved"] is True

    # A fresh orchestrator models a process restart. Continue from the saved
    # approval rather than reusing the in-memory project instance.
    restarted = MovieOrchestrator(settings)
    reloaded = restarted.store.load(project_id)
    assert reloaded.script["dialogue_locked"] is True
    assert reloaded.subtitle_mode == "soft"
    assert [
        (shot.number, shot.revision, shot.generation_input_hash, shot.status)
        for shot in reloaded.storyboard
    ] == initial_shot_snapshot
    assert reloaded.edit_plan["approved"] is True

    completed = restarted.generate_final_master(project_id)
    assert completed.status == "completed_mock"
    assert completed.final_output_placeholder == f"outputs/{project_id}/final-cut.mp4"
    assert completed.edit_plan["status"] == "final_approved"
    assert completed.edit_plan["approved"] is True

    output_root = tmp_path / "outputs" / project_id
    assert (output_root / "subtitles.srt").is_file()
    assert (output_root / "subtitles.vtt").is_file()
    # Mock mode is explicit: the path is a review placeholder, not a fake
    # claim that a rendered Final Cut exists.
    assert not Path(completed.final_output_placeholder).is_file()

    final_reload = restarted.store.load(project_id)
    assert final_reload.status == "completed_mock"
    assert final_reload.final_output_placeholder == completed.final_output_placeholder
    assert final_reload.subtitle_mode == "soft"
    assert final_reload.edit_plan["approved"] is True
