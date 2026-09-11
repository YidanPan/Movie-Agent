from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from movie_agent.agents.writer import WriterAgent
from movie_agent.config import Settings
from movie_agent.models import Shot
from movie_agent.orchestrator import MovieOrchestrator


class _SilentSupervisor:
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        del system_prompt, user_prompt
        return {"narration": "", "dialogue_book": [], "subtitle_track": []}


def _settings(root: Path) -> Settings:
    return Settings(
        "http://127.0.0.1:8188",
        900,
        root / "workflows",
        9071,
        root / "projects",
        True,
        outputs_dir=root / "outputs",
        model_provider="mock",
        image_generation_mode="mock",
        video_generation_mode="mock",
        tts_provider="none",
        public_demo_mode=True,
        app_access_token=None,
    )


def _speech_shots(policies: list[str]) -> list[Shot]:
    return [
        Shot(
            number=index,
            duration_seconds=6,
            framing="medium shot",
            image_description=f"Locked visual for shot {index}",
            action=f"Action {index}",
            sound_design="Room tone",
            generation_mode="T2V",
            prompt=f"Shot delta {index}",
            output_placeholder=f"shot-{index:02d}.mp4",
            status="approved_mock",
            speech_policy=policy,
        )
        for index, policy in enumerate(policies, start=1)
    ]


def test_real_llm_style_supervisor_persists_speech_policy_for_every_shot():
    shots = _speech_shots(["SILENT", "AMBIENCE_ONLY"])
    script = WriterAgent(llm=_SilentSupervisor()).supervise_storyboard(
        "A quiet signal arrives.",
        {},
        {"story": "A quiet story", "outline": "A quiet outline"},
        shots,
        duration_seconds=12,
    )

    assert script["dialogue_book"] == []
    assert script["subtitle_track"] == []
    assert script["speech_policy_by_shot"] == {"1": "SILENT", "2": "AMBIENCE_ONLY"}


def test_all_silent_empty_dialogue_and_subtitles_can_be_locked():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = MovieOrchestrator(_settings(root))
        project = orchestrator.create_project("A quiet signal waits beyond the moon.", 48, "film sci-fi")
        for shot in project.storyboard:
            shot.speech_policy = "SILENT"
        project.script.update(
            dialogue_book=[],
            subtitle_track=[],
            speech_policy_by_shot={},
            dialogue_locked=False,
        )
        orchestrator.store.save(project)

        locked = orchestrator.lock_dialogue(project.project_id)

        assert locked.script["dialogue_locked"] is True
        assert locked.script["dialogue_book"] == []
        assert locked.script["subtitle_track"] == []
        assert set(locked.script["speech_policy_by_shot"].values()) == {"SILENT"}


def test_non_silent_empty_dialogue_is_rejected():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = MovieOrchestrator(_settings(root))
        project = orchestrator.create_project("A courier follows a signal beyond the moon.", 48, "film sci-fi")
        project.storyboard[0].speech_policy = "NARRATION"
        for shot in project.storyboard[1:]:
            shot.speech_policy = "SILENT"
        project.script.update(dialogue_book=[], subtitle_track=[], speech_policy_by_shot={})
        orchestrator.store.save(project)

        with pytest.raises(ValueError, match="Dialogue book or subtitle track is empty"):
            orchestrator.lock_dialogue(project.project_id)


def test_dialogue_book_derives_missing_subtitle_track_before_lock():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = MovieOrchestrator(_settings(root))
        project = orchestrator.create_project("A courier follows a signal beyond the moon.", 48, "film sci-fi")
        project.storyboard[0].speech_policy = "NARRATION"
        for shot in project.storyboard[1:]:
            shot.speech_policy = "SILENT"
        project.script.update(
            dialogue_book=[{"shot": 1, "speaker": "NARRATOR", "text": "The signal is still here."}],
            subtitle_track=[],
            speech_policy_by_shot={},
            dialogue_locked=False,
        )
        orchestrator.store.save(project)
        loaded = orchestrator.store.load(project.project_id)
        assert len(loaded.script["dialogue_book"]) == 1
        assert loaded.script["subtitle_track"] == []

        locked = orchestrator.lock_dialogue(project.project_id)

        assert locked.script["dialogue_locked"] is True
        assert len(locked.script["dialogue_book"]) == 1
        assert len(locked.script["subtitle_track"]) == 1
        assert locked.script["subtitle_track"][0]["text"] == "The signal is still here."


def test_mock_dialogue_and_subtitle_assets_still_lock_normally():
    with TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        orchestrator = MovieOrchestrator(_settings(root))
        project = orchestrator.create_project("A courier follows a signal beyond the moon.", 48, "film sci-fi")

        locked = orchestrator.lock_dialogue(project.project_id)

        assert locked.script["dialogue_locked"] is True
        assert locked.script["dialogue_book"]
        assert locked.script["subtitle_track"]
