from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import wave
import unittest

from movie_agent.agents.generation import build_continuity_prompt
from movie_agent.agents.reviewer import ReviewerAgent
from movie_agent.config import Settings
from movie_agent.models import MovieProject, Shot
from movie_agent.services.alignment import PROPORTIONAL, WORD_LEVEL
from movie_agent.services.cache_cleanup import clean_working_cache, storage_summary
from movie_agent.services.shot_context import resolve_shot_context
from movie_agent.services.state_ledger import build_state_ledger, rebuild_state_ledger_from_shot
from movie_agent.services.voice import ContinuousVoiceService
from movie_agent.services.voice_timeline import compose_voice_timeline


def make_shot(number: int, **changes) -> Shot:
    shot = Shot(
        number,
        4,
        "medium shot",
        f"Shot {number}",
        "The character acts.",
        "Room tone",
        "T2V",
        "A concise shot delta.",
        f"shot-{number}.mp4",
        scene_id="home",
        character_ids=["hero"],
        prop_ids=["terminal"],
        ending_state=f"state {number}",
        transition_hook=f"hook {number}",
    )
    for key, value in changes.items():
        setattr(shot, key, value)
    return shot


class _VoiceProvider:
    def __init__(self) -> None:
        self.calls = []

    def synthesize(self, text: str, output_path: Path, voice_profile: dict) -> Path:
        self.calls.append((text, dict(voice_profile)))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(8000)
            handle.writeframes(b"\x01\x00" * 8000)
        return output_path


class _Vision:
    def __init__(self) -> None:
        self.prompt = ""

    def complete_vision_json(self, system: str, prompt: str, images: list[Path]) -> dict:
        self.prompt = prompt
        return {"verdict": "pass", "scores": {key: 90 for key in ("character_identity", "costume", "face_hair", "scene_geometry", "props", "palette", "lighting", "camera_language", "film_texture", "narrative_state")}, "copyright_risk": "low", "drift_flags": []}


class CorrectnessRoundThreeTests(unittest.TestCase):
    def test_narrative_only_context_preserves_previous_hook_without_visual_reference(self) -> None:
        previous = make_shot(1)
        current = make_shot(2, transition_type="AUDIO_BRIDGE")
        context = resolve_shot_context(current, {}, {}, previous)
        self.assertTrue(context.inherit_previous_narrative_context)
        self.assertFalse(context.allow_previous_visual_reference)
        self.assertEqual(context.previous_narrative_hook, "hook 1")
        prompt = build_continuity_prompt(current, {}, previous, context=context)
        self.assertIn("PREVIOUS NARRATIVE HOOK\nhook 1", prompt)
        self.assertIn("PREVIOUS VISUAL CONTEXT\nnone", prompt)

    def test_hard_cut_has_narrative_context_without_visual_identity(self) -> None:
        previous = make_shot(1, scene_id="home")
        current = make_shot(2, scene_id="hospital", transition_type="HARD_CUT")
        context = resolve_shot_context(current, {}, {}, previous)
        self.assertTrue(context.inherit_previous_narrative_context)
        self.assertFalse(context.allow_previous_visual_reference)
        self.assertEqual(context.previous_visual_reference_role, "NONE")

    def test_runtime_context_rejects_unknown_entities_and_reports_missing_locks(self) -> None:
        current = make_shot(1, scene_id="hospital", character_ids=["mother"], prop_ids=["phone"])
        world = {"scenes": {"home": {}}, "characters": {"hero": {}}, "props": {"terminal": {}}}
        context = resolve_shot_context(current, {"scene_lock": "legacy"}, world)
        self.assertEqual(context.missing_entities, {"scenes": ["hospital"], "characters": ["mother"], "props": ["phone"]})
        self.assertIn("UNKNOWN_SCENE_ID", context.context_flags)

        known = make_shot(1)
        world = {"scenes": {"home": {}}, "characters": {"hero": {}}, "props": {"terminal": {}}}
        context = resolve_shot_context(known, {"scenes": [{"scene_id": "home", "lock": ""}]}, world)
        self.assertIn("MISSING_SCENE_LOCK", context.context_flags)

    def test_state_ledger_rebuilds_after_upstream_shot_change(self) -> None:
        first = make_shot(1, state_delta={"terminal": {"status": "active"}})
        second = make_shot(2, state_delta={"terminal": {"status": "expired"}})
        project = MovieProject("film-ledger", "idea", 8, "style", "planned", {}, {}, {}, [first, second])
        ledger = build_state_ledger(project)
        self.assertEqual(ledger["shots"]["2"]["before"]["terminal"]["status"], "active")
        first.state_delta = {"terminal": {"status": "restored"}}
        rebuilt = rebuild_state_ledger_from_shot(project, 1)
        self.assertEqual(rebuilt["shots"]["2"]["before"]["terminal"]["status"], "restored")

    def test_generation_prompt_contains_machine_state(self) -> None:
        current = make_shot(2, state_delta={"terminal": {"status": "expired"}})
        context = resolve_shot_context(current, {}, None, make_shot(1), entity_state_before={"terminal": {"status": "active"}})
        prompt = build_continuity_prompt(current, {}, make_shot(1), context=context)
        self.assertIn("CURRENT ENTITY STATE\nterminal: status = active", prompt)
        self.assertIn("EXPECTED END STATE\nterminal: status = expired", prompt)

    def test_reviewer_receives_expected_entity_state(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            vision = _Vision()
            reviewer = ReviewerAgent(Settings("http://127.0.0.1:8188", 900, root, 9071, root, True, outputs_dir=root), vision_llm=vision)
            current = make_shot(2, state_delta={"terminal": {"status": "expired"}})
            context = resolve_shot_context(current, {}, None, make_shot(1), entity_state_before={"terminal": {"status": "active"}})
            reviewer._review_visual_consistency("film", current, {}, [], context=context)
            self.assertIn('"status": "active"', vision.prompt)
            self.assertIn('"status": "expired"', vision.prompt)

    def test_word_boundaries_drive_voice_segment_cut(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "voice.wav"
            with wave.open(str(raw), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(100)
                handle.writeframes(b"\x01\x00" * 300)
            project = SimpleNamespace(duration_seconds=4, storyboard=[make_shot(1)], script={"dialogue_book": [{"shot": 1, "line_id": "L1", "text": "The signal is here."}]})
            result = compose_voice_timeline(project, raw, 3.0, word_boundaries=[{"word": "The", "start_time": 0, "end_time": .3}, {"word": "signal", "start_time": .35, "end_time": .8}, {"word": "is", "start_time": .85, "end_time": 1.0}, {"word": "here.", "start_time": 1.05, "end_time": 1.5}])
            self.assertEqual(result["alignment_method"], WORD_LEVEL)
            self.assertEqual(result["cues"][0]["raw_start_seconds"], 0)
            self.assertEqual(result["cues"][0]["raw_end_seconds"], 1.5)

    def test_word_boundary_alignment_falls_back_to_proportional(self) -> None:
        from movie_agent.services.subtitles import align_script_to_audio

        result = align_script_to_audio({"dialogue_book": [{"shot": 1, "text": "The signal is here."}]}, 2.0, word_boundaries=[{"word": "unrelated", "start_time": 0, "end_time": 1}])
        self.assertEqual(result["voice_alignment"]["method"], PROPORTIONAL)

    def test_voice_segment_is_not_cut_mid_word(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "voice.wav"
            with wave.open(str(raw), "wb") as handle:
                handle.setnchannels(1); handle.setsampwidth(2); handle.setframerate(100); handle.writeframes(b"\x01\x00" * 300)
            project = SimpleNamespace(duration_seconds=4, storyboard=[make_shot(1)], script={"dialogue_book": [{"shot": 1, "text": "One two."}]})
            result = compose_voice_timeline(project, raw, 3.0, word_boundaries=[{"word": "One", "start_time": 0, "end_time": 1}, {"word": "two.", "start_time": 1.2, "end_time": 2}])
            self.assertEqual(result["cues"][0]["raw_end_seconds"], 2.0)

    def test_multi_speaker_voice_uses_stable_distinct_profiles(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings("http://127.0.0.1:8188", 900, root / "workflows", 9071, root / "projects", True, outputs_dir=root, tts_provider="none")
            project = MovieProject("film-voice", "idea", 8, "style", "planned", {}, {"dialogue_locked": True, "dialogue_book": [{"shot": 1, "speaker": "Lin Ran", "text": "Stay with me."}, {"shot": 2, "speaker": "Mother", "text": "I am here."}]}, {}, [make_shot(1), make_shot(2)])
            provider = _VoiceProvider()
            result = ContinuousVoiceService(settings, provider=provider).synthesize(project)
            self.assertEqual(result.status, "READY")
            self.assertEqual(len(provider.calls), 2)
            self.assertNotEqual(provider.calls[0][1]["voice_id"], provider.calls[1][1]["voice_id"])

    def test_storage_public_contract_does_not_expose_paths(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings("http://127.0.0.1:8188", 900, root / "workflows", 9071, root / "projects", True, outputs_dir=root / "outputs")
            project = MovieProject("film-storage", "idea", 8, "style", "planned", {}, {}, {}, [])
            summary = storage_summary(project, settings.outputs_dir)
            self.assertNotIn("root", summary)
            cleaned = clean_working_cache(project, settings.outputs_dir)
            self.assertNotIn("removed", cleaned)


if __name__ == "__main__":
    unittest.main()
