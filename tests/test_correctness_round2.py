from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

from movie_agent.agents.generation import GenerationAgent, build_continuity_prompt
from movie_agent.agents.reviewer import normalise_visual_review
from movie_agent.config import Settings
from movie_agent.models import Shot
from movie_agent.services.continuity import resolve_prop_locks
from movie_agent.services.narrative import allocate_two_stage_durations
from movie_agent.services.quality import ContinuityQualityGate
from movie_agent.services.revisions import hash_generation_input
from movie_agent.services.shot_context import resolve_shot_context
from movie_agent.services.storyboard_quality import StoryboardRelevanceGate
from movie_agent.services.voice_timeline import compose_voice_timeline
from movie_agent.storage.reference_bank import ReferenceBankStore
from movie_agent.agents.visual_bible import VisualBibleAgent, validate_visual_bible_bindings


def shot(number: int, **changes) -> Shot:
    value = Shot(number, 6, "medium shot", "A stable scene", "The subject acts", "room tone", "T2V", "A shot delta long enough for the renderer.", f"shot-{number}.mp4", scene_id="home", character_ids=["hero"], prop_ids=["terminal"], narrative_purpose="advance", starting_state="ready", main_action="acts", ending_state=f"state {number}", transition_hook=f"hook {number}")
    for key, item in changes.items():
        setattr(value, key, item)
    return value


class CorrectnessRoundTwoTests(unittest.TestCase):
    def test_previous_reference_requires_immediate_previous_shot_and_revision(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "old.jpg"
            current = root / "current.jpg"
            old.touch(); current.touch()
            store = ReferenceBankStore(root / "outputs")
            store.register_file("film", old, kind="previous_approved_shot_ending_frame", source="qc", approved=True, shot_number=1, revision=1)
            current_shot = shot(3, revision=1)
            previous = shot(2, revision=2)
            refs = store.generation_reference_paths("film", current_shot, previous)
            self.assertEqual(refs["previous_frame"], [])
            self.assertIn("MISSING_PREVIOUS_ENDING_REFERENCE", refs["reference_flags"])

    def test_hard_cut_suppresses_previous_visual_context(self):
        previous = shot(1)
        current = shot(2, transition_type="HARD_CUT", scene_id="hospital")
        context = resolve_shot_context(current, {"scene_lock": "hospital", "character_lock": "hero", "cinematography_lock": "camera"}, previous_shot=previous)
        prompt = build_continuity_prompt(current, {"scene_lock": "hospital", "character_lock": "hero", "cinematography_lock": "camera"}, previous)
        self.assertEqual(context.previous_context_mode, "NARRATIVE_ONLY")
        self.assertNotIn("PREVIOUS SHOT ENDING STATE\nstate 1", prompt)

    def test_audio_bridge_keeps_narrative_hook_but_not_visual_state(self):
        current = shot(2, transition_type="AUDIO_BRIDGE")
        context = resolve_shot_context(current, {}, previous_shot=shot(1))
        self.assertEqual(context.previous_context_mode, "NARRATIVE_ONLY")
        self.assertFalse(context.previous_visual_reference_allowed)

    def test_match_cut_uses_composition_only_context(self):
        current = shot(2, transition_type="MATCH_CUT", scene_id="hospital")
        context = resolve_shot_context(current, {}, previous_shot=shot(1))
        self.assertEqual(context.previous_context_mode, "COMPOSITION_ONLY")
        self.assertTrue(context.previous_visual_reference_allowed)

    def test_continuous_scene_change_is_transition_conflict(self):
        with self.assertRaisesRegex(ValueError, "TRANSITION_CONFLICT"):
            ContinuityQualityGate().review(
                visual_bible={"character_lock": "hero", "scene_lock": "world", "cinematography_lock": "camera"},
                storyboard=[shot(1), shot(2, scene_id="hospital", transition_type="CONTINUOUS")],
                continuity_lock={"status": "LOCKED"},
            )
        review = StoryboardRelevanceGate().review_storyboard([shot(1), shot(2, scene_id="hospital", transition_type="CONTINUOUS")], [])
        self.assertEqual(review["decision"], "REVIEW")

    def test_mock_visual_bible_has_usable_prop_lock(self):
        world = {"characters": {"hero": {"name": "Hero"}}, "scenes": {"home": {"name": "Home"}}, "props": {"terminal": {"name": "Terminal"}}}
        bible = VisualBibleAgent().create("grounded", {}, {}, story_world=world)
        self.assertFalse(validate_visual_bible_bindings(bible, world)["missing_prop_locks"])
        self.assertTrue(resolve_prop_locks(bible, ["terminal"])[0]["lock"])

    def test_visual_review_normalizes_legacy_dimensions_to_canonical_scores(self):
        review = normalise_visual_review({"verdict": "pass", "character_consistency": 90, "dimensions": {"props": 84}})
        self.assertEqual(review["scores"]["character_identity"], 90)
        self.assertEqual(review["scores"]["props"], 84)
        self.assertIn("narrative_state", review["scores"])

    def test_generation_input_hash_changes_with_context(self):
        value = shot(1)
        first = hash_generation_input(value, resolve_shot_context(value, {"scene_lock": "home"}))
        changed = shot(1, scene_id="hospital")
        second = hash_generation_input(changed, resolve_shot_context(changed, {"scene_lock": "hospital"}))
        self.assertNotEqual(first, second)

    def test_generation_agent_passes_previous_shot_to_reference_resolver(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            workflow = root / "workflows" / "verified.json"
            workflow.parent.mkdir(parents=True); workflow.write_text("{}", encoding="utf-8")
            source = root / "source.mp4"; source.write_bytes(b"source")
            settings = Settings("http://127.0.0.1:8188", 900, root / "workflows", 9071, root / "projects", True, outputs_dir=root / "outputs", comfy_workflow_template="verified.json")

            class Client:
                def is_available(self): return True
                def submit(self, workflow): return "prompt-1"
                def wait_for_completion(self, prompt_id): return {"outputs": {}}

            agent = GenerationAgent(settings, client=Client())
            current = shot(2)
            previous = shot(1)
            with patch.object(agent.reference_bank, "generation_reference_paths", return_value={"character": [], "scene": [], "prop": [], "previous_frame": [], "palette": [], "cinematography": [], "reference_flags": []}) as resolver, patch("movie_agent.agents.generation.load_verified_workflow", return_value={}), patch.object(agent, "_resolve_video", return_value=source):
                agent.generate("film-test", current, visual_bible={"reference_seed": "42", "scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"}, previous_shot=previous)
            self.assertIs(resolver.call_args.args[2], previous)

    def test_two_stage_budget_reflects_weight_magnitude_and_preserves_interleaved_order(self):
        beats = [{"beat_id": "a", "duration_weight": 10, "importance": 1}, {"beat_id": "b", "duration_weight": 1, "importance": 1}]
        durations = allocate_two_stage_durations(["a", "b"], beats, 12)
        self.assertGreater(durations[0], durations[1])
        interleaved = allocate_two_stage_durations(["a", "b", "a"], beats, 18)
        self.assertEqual(len(interleaved), 3)
        self.assertEqual(sum(interleaved), 18)

    def test_sparse_voice_track_preserves_silent_shot_gap_and_film_duration(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "voice.wav"
            with wave.open(str(raw), "wb") as handle:
                handle.setnchannels(1); handle.setsampwidth(2); handle.setframerate(8000); handle.writeframes(b"\x01\x00" * 8000)
            project = SimpleNamespace(
                duration_seconds=12,
                storyboard=[shot(1, duration_seconds=6, speech_policy="SILENT"), shot(2, duration_seconds=6, speech_policy="NARRATION")],
                script={"speech_policy_by_shot": {"1": "SILENT", "2": "NARRATION"}, "dialogue_book": [{"shot": 2, "text": "The signal remains."}]},
            )
            result = compose_voice_timeline(project, raw, 1.0)
            self.assertEqual(result["duration_seconds"], 12.0)
            self.assertGreaterEqual(result["cues"][0]["timeline_start_seconds"], 6.0)
            with wave.open(result["media_path"], "rb") as handle:
                self.assertEqual(handle.getnframes(), 12 * 8000)


if __name__ == "__main__":
    unittest.main()
