from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from movie_agent.agents.storyboard import StoryboardAgent
from movie_agent.agents.visual_bible import VisualBibleAgent
from movie_agent.agents.writer import WriterAgent
from movie_agent.agents.reviewer import ReviewerAgent
from movie_agent.config import Settings
from movie_agent.models import Shot
from movie_agent.services.continuity import resolve_character_locks, resolve_scene_lock
from movie_agent.services.narrative import (
    allocate_two_stage_durations,
    allocate_weighted_durations,
    beat_count_for_duration,
    validate_beat_shot_mapping,
)
from movie_agent.services.quality import ContinuityQualityGate
from movie_agent.services.story_world import extract_story_world, validate_story_world_references
from movie_agent.services.storyboard_quality import PLANNING_RELEVANCE_FLAGS, StoryboardRelevanceGate
from movie_agent.storage.reference_bank import ReferenceBankStore


def make_shot(number: int, beat_id: str, **changes: object) -> Shot:
    shot = Shot(
        number,
        6,
        "medium shot",
        "The protagonist watches the signal.",
        "The protagonist reaches toward the console.",
        "Room tone",
        "T2V",
        "Continue the previous shot with one delta.",
        f"shot-{number}.mp4",
        beat_id=beat_id,
        scene_id="home",
        character_ids=["hero"],
        narrative_purpose="Recognise the signal.",
        story_function="RECOGNITION",
        information_gain=0.7,
        starting_state="The signal is idle.",
        main_action="The protagonist reaches toward the console.",
        ending_state="The signal activates.",
        transition_hook="Carry the activated signal into the next shot.",
    )
    for key, value in changes.items():
        setattr(shot, key, value)
    return shot


class NarrativeContractTests(unittest.TestCase):
    def test_mapping_requires_valid_ids_but_allows_multiple_shots_per_beat(self) -> None:
        beats = [{"beat_id": "setup"}, {"beat_id": "climax"}]
        result = validate_beat_shot_mapping(
            [make_shot(1, "setup"), make_shot(2, "climax"), make_shot(3, "climax")],
            beats,
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["covered_beats"], ["setup", "climax"])
        self.assertEqual(result["orphan_shots"], [])

        invalid = validate_beat_shot_mapping([make_shot(1, "missing")], beats)
        self.assertFalse(invalid["valid"])
        self.assertEqual(invalid["uncovered_beats"], ["setup", "climax"])
        self.assertEqual(invalid["orphan_shots"], [1])

    def test_weighted_duration_allocation_preserves_target_and_bounds(self) -> None:
        durations = allocate_weighted_durations([0.5, 1.0, 2.0, 1.5], 24)
        self.assertEqual(sum(durations or []), 24)
        self.assertTrue(all(4 <= value <= 8 for value in (durations or [])))
        self.assertGreater((durations or [0])[2], (durations or [0])[0])

    def test_whole_board_review_reports_planning_problems(self) -> None:
        shots = [make_shot(1, "beat-01"), make_shot(2, "beat-01", shot_complexity="HIGH")]
        review = StoryboardRelevanceGate().review_storyboard(shots, [{"beat_id": "beat-01"}, {"beat_id": "beat-02"}])
        self.assertEqual(review["beat_coverage"], 0.5)
        self.assertEqual(review["complex_shots"], [2])
        self.assertEqual(review["decision"], "REVIEW")

    def test_repair_pass_changes_only_flagged_shots_and_preserves_beat(self) -> None:
        flagged = make_shot(1, "beat-01", information_gain=0.0, main_action="")
        untouched = make_shot(2, "beat-02", information_gain=0.8)
        flagged.qc_flags = ["LOW_RELEVANCE_SHOT"]
        original_untouched = (untouched.beat_id, untouched.information_gain, untouched.prompt, untouched.main_action)
        repaired = StoryboardAgent().repair_shots(
            [flagged, untouched],
            [{"beat_id": "beat-01"}, {"beat_id": "beat-02"}],
        )
        self.assertEqual(repaired[0].beat_id, "beat-01")
        self.assertGreaterEqual(repaired[0].information_gain, 0.65)
        self.assertEqual(
            (repaired[1].beat_id, repaired[1].information_gain, repaired[1].prompt, repaired[1].main_action),
            original_untouched,
        )

    def test_scene_transition_is_not_reported_as_scene_drift(self) -> None:
        first = make_shot(1, "beat-01", scene_id="home")
        second = make_shot(2, "beat-02", scene_id="hospital", transition_type="HARD_CUT")
        notes = ContinuityQualityGate().review(
            visual_bible={"character_lock": "hero", "scene_lock": "world", "cinematography_lock": "camera"},
            storyboard=[first, second],
            continuity_lock={"status": "LOCKED"},
        )
        self.assertFalse(any("SCENE_DRIFT: Shot 2" in note for note in notes))

    def test_structured_visual_bible_fallback_has_scene_and_character_selectors(self) -> None:
        bible = VisualBibleAgent().create("grounded realism", {}, {"story": "A quiet signal."})
        self.assertEqual(bible["characters"][0]["character_id"], "protagonist")
        self.assertEqual(bible["scenes"][0]["scene_id"], "primary")
        self.assertIn("cinematography", bible)

    def test_story_world_extracts_stable_character_scene_prop_ids(self) -> None:
        world = extract_story_world("A watchman finds a terminal.", {}, {"story": "A watchman finds a terminal."})
        self.assertIn("protagonist", world["characters"])
        self.assertIn("primary", world["scenes"])
        self.assertEqual(validate_story_world_references([{"scene_id": "primary", "character_ids": ["protagonist"]}], world), {
            "unknown_characters": [],
            "unknown_scenes": [],
            "unknown_props": [],
        })

    def test_storyboard_rejects_unknown_scene_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "STORY_WORLD_REVIEW_REQUIRED"):
            StoryboardAgent().create(
                "A story with a registered world.",
                36,
                "grounded realism",
                "film-test",
                {},
                {},
                {},
                story_beats=[{"beat_id": "beat-01", "scene_id": "hospital", "character_ids": ["hero"]}],
                story_world={"characters": {"hero": {"name": "Hero"}}, "scenes": {"home": {"name": "Home"}}, "props": {}},
            )

    def test_story_world_references_are_rejected_without_fallback(self) -> None:
        unknown = validate_story_world_references(
            [{"scene_id": "hospital", "character_ids": ["mother"], "prop_ids": ["terminal"]}],
            {"characters": {"hero": {}}, "scenes": {"home": {}}, "props": {}},
        )
        self.assertEqual(unknown["unknown_scenes"], ["hospital"])
        self.assertEqual(unknown["unknown_characters"], ["mother"])
        self.assertEqual(unknown["unknown_props"], ["terminal"])

    def test_lock_resolution_does_not_leak_unrelated_structured_context(self) -> None:
        bible = {
            "character_lock": "global",
            "scene_lock": "global",
            "characters": [
                {"character_id": "mother", "name": "Mother", "costume_lock": "hospital gown"},
                {"character_id": "child", "name": "Child", "costume_lock": "yellow coat"},
            ],
            "scenes": [
                {"scene_id": "home", "environment_lock": "small apartment"},
                {"scene_id": "hospital", "environment_lock": "quiet hospital ward"},
            ],
        }
        self.assertIn("hospital gown", resolve_character_locks(bible, ["mother"])[0]["lock"])
        self.assertNotIn("yellow coat", resolve_character_locks(bible, ["mother"])[0]["lock"])
        self.assertEqual(resolve_scene_lock(bible, "hospital")["lock"], "quiet hospital ward")

    def test_resolved_planning_flags_are_removed_but_visual_flags_survive(self) -> None:
        value = make_shot(1, "beat-01")
        value.qc_flags = ["LOW_RELEVANCE_SHOT", "CHARACTER_DRIFT"]
        value.qc_details = {"visual": {"flags": ["CHARACTER_DRIFT"]}, "planning": {"flags": ["LOW_RELEVANCE_SHOT"]}}
        StoryboardRelevanceGate().annotate([value], [{"beat_id": "beat-01", "story_function": "RECOGNITION"}])
        self.assertNotIn("LOW_RELEVANCE_SHOT", value.qc_flags)
        self.assertIn("CHARACTER_DRIFT", value.qc_flags)
        self.assertFalse(set(value.qc_details["planning"]["flags"]) & PLANNING_RELEVANCE_FLAGS)

    def test_approved_keyframes_are_not_character_fallbacks(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            frame = root / "wide.jpg"
            frame.touch()
            store = ReferenceBankStore(root / "outputs")
            store.register_file("film", frame, kind="approved_keyframe", source="qc", approved=True, scene_id="home")
            refs = store.qc_reference_paths("film", make_shot(2, "beat-01", scene_id="home", character_ids=["hero"]))
            self.assertEqual(refs["character_hero"], [])
            self.assertIn("MISSING_CHARACTER_REFERENCE", refs["reference_flags"])

    def test_transition_ending_frame_is_distinct_and_near_media_end(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            video = root / "shot.mp4"
            video.touch()
            ending = root / "ending.jpg"
            ending.touch()
            settings = Settings("http://127.0.0.1:8188", 900, Path("workflows"), 9071, root, True, outputs_dir=root)
            reviewer = ReviewerAgent(settings)
            shot = make_shot(1, "beat-01")
            shot.output_placeholder = str(video)
            shot.status = "generated_comfyui"
            with patch.object(reviewer, "_video_duration", return_value=6.0), patch.object(
                reviewer, "_extract_keyframes", return_value=[root / "qc-25.jpg", root / "qc-50.jpg"]
            ), patch.object(reviewer, "_extract_ending_frame", return_value=ending):
                # The QC paths need not exist for this contract test; the ending does.
                reviewer.review_generated(shot, project_id="film-test")
            roles = [asset.role for asset in reviewer.reference_bank.load("film-test").assets]
            self.assertEqual(roles, ["transition_ending_frame"])

    def test_manual_approval_promotes_transition_ending_frame(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings("http://127.0.0.1:8188", 900, Path("workflows"), 9071, root, True, outputs_dir=root)
            reviewer = ReviewerAgent(settings)
            frame = root / "ending.jpg"
            frame.touch()
            shot = make_shot(1, "beat-01")
            reviewer._archive_ending_frame("film-test", shot, frame, approved=False)
            shot.status = "awaiting_visual_review"
            shot.qc_status = "AWAITING_VISUAL_REVIEW"
            reviewer.approve_manual(shot, project_id="film-test")
            asset = reviewer.reference_bank.load("film-test").assets[0]
            self.assertEqual(asset.kind, "previous_approved_shot_ending_frame")
            self.assertEqual(asset.metadata["shot_revision"], 1)

    def test_previous_frame_respects_transition_type(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            frame = root / "ending.jpg"
            frame.touch()
            store = ReferenceBankStore(root / "outputs")
            store.register_file("film", frame, kind="previous_approved_shot_ending_frame", source="qc", approved=True, shot_number=1, revision=1, scene_id="home", role="transition_ending_frame")
            previous = make_shot(1, "beat-01", scene_id="home")
            hard_cut = make_shot(2, "beat-02", scene_id="hospital", transition_type="HARD_CUT")
            continuous = make_shot(2, "beat-02", scene_id="home", transition_type="CONTINUOUS")
            self.assertEqual(store.generation_reference_paths("film", hard_cut, previous)["previous_frame"], [])
            self.assertEqual(len(store.generation_reference_paths("film", continuous, previous)["previous_frame"]), 1)

    def test_legacy_reference_manifest_migrates_character_id_to_character_ids(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            store = ReferenceBankStore(root / "outputs")
            manifest_dir = store.project_dir("film")
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "reference-bank.json").write_text(
                '{"project_id":"film","assets":[{"reference_id":"ref-1","kind":"character","path":"/tmp/x","source":"legacy","character_id":"hero"}]}',
                encoding="utf-8",
            )
            self.assertEqual(store.load("film").assets[0].character_ids, ["hero"])

    def test_story_beat_count_is_independent_from_shot_count(self) -> None:
        self.assertEqual(beat_count_for_duration(48), 5)
        self.assertEqual(beat_count_for_duration(72), 7)
        self.assertGreaterEqual(6, beat_count_for_duration(48))

    def test_two_stage_duration_allocation_does_not_multiply_beat_budget(self) -> None:
        beats = [
            {"beat_id": "setup", "duration_weight": 1.0, "importance": 0.5},
            {"beat_id": "climax", "duration_weight": 2.0, "importance": 1.0},
        ]
        durations = allocate_two_stage_durations(["setup", "climax", "climax"], beats, 18)
        self.assertEqual(sum(durations or []), 18)
        self.assertTrue(4 <= (durations or [0])[0] <= 8)
        self.assertTrue(all(4 <= value <= 8 for value in (durations or [])))

    def test_silent_shot_has_no_dialogue_cue_but_keeps_other_speech(self) -> None:
        silent = make_shot(1, "beat-01", speech_policy="SILENT")
        spoken = make_shot(2, "beat-02", speech_policy="NARRATION")
        script = WriterAgent().supervise_storyboard("idea", {}, {}, [silent, spoken], duration_seconds=12)
        self.assertEqual([cue["shot"] for cue in script["dialogue_book"]], [2])
        self.assertEqual(script["speech_policy_by_shot"]["1"], "SILENT")


if __name__ == "__main__":
    unittest.main()
