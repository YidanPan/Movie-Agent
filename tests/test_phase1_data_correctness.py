from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from movie_agent.agents.storyboard import StoryboardAgent, _normalise_state_delta, _normalise_transition_types
from movie_agent.agents.visual_bible import UI_PALETTE_FALLBACK, VisualBibleAgent, normalise_ui_palette, validate_ui_palette
from movie_agent.config import Settings
from movie_agent.models import MovieProject, Shot
from movie_agent.orchestrator import MovieOrchestrator
from movie_agent.services.change_impact import SHOT_EDITABLE_FIELDS
from movie_agent.services.revisions import reconcile_generation_fingerprints
from movie_agent.services.state_ledger import validate_state_delta
from movie_agent.services.story_world import canonicalize_story_world_references
from server import UpdateShotPayload


def _shot(number: int, *, state_delta=None) -> Shot:
    return Shot(
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
        state_delta=state_delta or {},
    )


class _StoryboardLLM:
    def __init__(self) -> None:
        self.prompt = ""

    def complete_json(self, system: str, prompt: str) -> dict:
        self.prompt = f"{system}\n{prompt}"
        return {
            "shots": [
                {
                    "duration_seconds": 4,
                    "framing": "medium shot",
                    "image_description": "A consistent room.",
                    "action": "The character notices the signal.",
                    "sound_design": "Room tone.",
                    "generation_mode": "T2V",
                    "prompt": "Continue the shot delta.",
                    "beat_id": f"beat-{index + 1:02d}",
                    "scene_id": "home",
                    "character_ids": ["hero"],
                    "prop_ids": ["terminal"],
                    "state_delta": {"hero": {"emotion": "alert"}} if index == 2 else {},
                }
                for index in range(6)
            ]
        }


class PhaseOneDataCorrectnessTests(unittest.TestCase):
    def test_scene_change_with_default_continuous_transition_is_normalized(self) -> None:
        first = _shot(1)
        second = _shot(2)
        second.scene_id = "hospital"
        _normalise_transition_types([first, second])
        self.assertEqual(second.transition_type, "HARD_CUT")
        self.assertIn("TRANSITION_TYPE_NORMALIZED", second.qc_flags)

    def test_state_delta_resolves_active_semantic_placeholders(self) -> None:
        result = _normalise_state_delta(
            {"character": {"emotion": "alert"}, "scene": {"lighting_state": "dim"}},
            {"characters": {"alex": {"name": "Alex"}}, "scenes": {"home": {}}},
            scene_id="home",
            character_ids=["alex"],
        )
        self.assertEqual(set(result), {"alex", "home"})

    def test_state_delta_resolves_plural_active_placeholders(self) -> None:
        result = _normalise_state_delta(
            {"character_ids": {"emotion": "alert"}, "prop_ids": {"status": "open"}},
            {"characters": {"alex": {}}, "props": {"memory_vault": {}}},
            character_ids=["alex"],
            prop_ids=["memory_vault"],
        )
        self.assertEqual(set(result), {"alex", "memory_vault"})

    def test_known_story_world_names_are_canonicalized_but_unknown_names_survive(self) -> None:
        result = canonicalize_story_world_references(
            [{"character_ids": ["Alex", "invented"], "scene_id": "home"}],
            {"characters": {"alex": {"name": "Alex"}}, "scenes": {}, "props": {}},
        )
        self.assertEqual(result[0]["character_ids"], ["alex", "invented"])

    def test_storyboard_schema_requests_state_delta(self) -> None:
        llm = _StoryboardLLM()
        StoryboardAgent(llm=llm).create(
            "A signal changes a quiet room.",
            24,
            "grounded",
            "film-1234abcd",
            {},
            {},
            {},
            story_beats=[{"beat_id": f"beat-{index + 1:02d}", "scene_id": "home"} for index in range(6)],
            story_world={"characters": {"hero": {}}, "scenes": {"home": {}}, "props": {"terminal": {}}},
        )
        self.assertIn('"state_delta":{}', llm.prompt)
        self.assertIn("STATE DELTA RULES", llm.prompt)
        self.assertIn("Return exactly 6 shots", llm.prompt)

    def test_mock_storyboard_has_meaningful_state_delta(self) -> None:
        shots = StoryboardAgent().create(
            "A signal changes a quiet room.",
            48,
            "grounded",
            "film-1234abcd",
            {},
            {},
            {},
            story_world={"characters": {"hero": {}}, "scenes": {"home": {}}, "props": {"terminal": {}}},
        )
        self.assertTrue(any(shot.state_delta for shot in shots))
        self.assertTrue(all(set(shot.state_delta) <= {"hero", "home", "terminal"} for shot in shots))

    def test_state_delta_rejects_unknown_entity(self) -> None:
        result = validate_state_delta({"mother_character": {"emotion": "shocked"}}, {"characters": {"hero": {}}})
        self.assertFalse(result["valid"])
        self.assertEqual(result["unknown_state_entities"], ["mother_character"])

    def test_update_shot_accepts_state_delta_and_rebuilds_ledger(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings("http://127.0.0.1:8188", 900, root / "workflows", 9071, root / "projects", True, outputs_dir=root / "outputs")
            orchestrator = MovieOrchestrator(settings)
            project = orchestrator.create_project("A signal changes a quiet room.", 48, "grounded")
            shot = project.storyboard[0]
            shot.media_assets["source"] = {"path": "source.mp4", "stale": False}
            orchestrator.store.save(project)
            updated = orchestrator.update_shot(
                project.project_id,
                1,
                {"state_delta": {"protagonist": {"emotion": "shocked"}}},
            )
            self.assertEqual(updated.storyboard[0].state_delta["protagonist"]["emotion"], "shocked")
            self.assertFalse(updated.storyboard[0].stale)
            self.assertEqual(updated.continuity_state_ledger["shots"]["1"]["after"]["protagonist"]["emotion"], "shocked")

    def test_editable_field_contract_matches_api_payload(self) -> None:
        self.assertEqual(SHOT_EDITABLE_FIELDS, frozenset(UpdateShotPayload.model_fields))

    def test_legacy_source_is_not_staled_by_renderer_algorithm_migration(self) -> None:
        first = _shot(1, state_delta={"hero": {"emotion": "calm"}})
        second = _shot(2, state_delta={})
        project = MovieProject("film-fingerprint", "idea", 8, "style", "planned", {}, {}, {}, [first, second])
        project.story_world = {"characters": {"hero": {}}, "scenes": {"home": {}}, "props": {"terminal": {}}}
        first.media_assets["source"] = {"path": "first.mp4", "stale": False}
        second.media_assets["source"] = {"path": "second.mp4", "stale": False}
        initial = reconcile_generation_fingerprints(project)
        self.assertEqual(initial["affected_shots"], [])
        first.state_delta = {"hero": {"emotion": "shocked"}}
        result = reconcile_generation_fingerprints(project)
        self.assertEqual(result["affected_shots"], [])
        self.assertFalse(first.stale)
        self.assertFalse(second.stale)
        self.assertEqual(first.media_assets["source"]["renderer_verification_status"], "UNVERIFIED_LEGACY")

    def test_planned_shot_is_not_marked_stale_without_source(self) -> None:
        project = MovieProject("film-planned", "idea", 4, "style", "planned", {}, {}, {}, [_shot(1)])
        project.story_world = {"characters": {"hero": {}}, "scenes": {"home": {}}, "props": {"terminal": {}}}
        project.storyboard[0].generation_input_hash = "old-hash"
        result = reconcile_generation_fingerprints(project)
        self.assertEqual(result["affected_shots"], [])
        self.assertFalse(project.storyboard[0].stale)

    def test_invalid_ui_palette_falls_back_safely(self) -> None:
        self.assertTrue(validate_ui_palette({"dominant": "hospital-blue"}))
        self.assertEqual(normalise_ui_palette({"dominant": "hospital-blue"}), UI_PALETTE_FALLBACK)

    def test_visual_bible_scene_persists_machine_palette(self) -> None:
        world = {"characters": {"hero": {}}, "scenes": {"home": {}}, "props": {}}
        bible = VisualBibleAgent().create(
            "grounded", {}, {}, story_world=world
        )
        self.assertIn("ui_palette", bible["scenes"][0])
        self.assertEqual(bible["scenes"][0]["ui_palette"]["temperature"], "neutral")

    def test_visual_bible_preserves_model_locks_when_binding_world_entities(self) -> None:
        bible = VisualBibleAgent._bind_entities(
            [{"character_id": "Alex", "lock": "stable face and costume"}],
            {"characters": {"alex": {"name": "Alex"}}},
            "characters",
        )
        self.assertEqual(bible[0]["character_id"], "alex")
        self.assertEqual(bible[0]["lock"], "stable face and costume")


if __name__ == "__main__":
    unittest.main()
