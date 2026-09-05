from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from movie_agent.agents.generation import build_continuity_prompt
from movie_agent.agents.reviewer import ReviewerAgent
from movie_agent.agents.writer import WriterAgent
from movie_agent.config import Settings
from movie_agent.models import MovieProject, Shot
from movie_agent.services.continuity import derive_shot_seed
from movie_agent.services.subtitles import _wrap_cue_text, align_script_to_shots, render_srt
from movie_agent.state import ProjectState, describe_status, state_for_status


def make_shot(number: int, *, duration: int = 6) -> Shot:
    return Shot(
        number,
        duration,
        "medium shot",
        f"A locked visual for shot {number}",
        f"The protagonist completes action {number}",
        "Room tone",
        "T2V",
        f"Delta event {number}",
        f"shot-{number:02d}.mp4",
        "approved_mock",
        narrative_purpose=f"Purpose {number}",
        starting_state=f"Start state {number}",
        main_action=f"Main action {number}",
        character_reaction=f"Reaction {number}",
        ending_state=f"Ending state {number}",
        transition_hook=f"Hook {number}",
    )


class ContinuityPipelineTests(unittest.TestCase):
    def test_visual_continuity_seed_is_deterministic(self) -> None:
        first = derive_shot_seed("film-abcd1234", "42", 3)
        self.assertEqual(first, derive_shot_seed("film-abcd1234", "42", 3))
        self.assertNotEqual(first, derive_shot_seed("film-abcd1234", "42", 4))
        self.assertNotEqual(first, derive_shot_seed("film-other", "42", 3))
        self.assertGreaterEqual(first, 1)

    def test_generation_prompt_uses_previous_shot_state(self) -> None:
        previous = make_shot(1)
        current = make_shot(2)
        prompt = build_continuity_prompt(
            current,
            {
                "reference_seed": "42",
                "character_lock": "Same character lock",
                "scene_lock": "Same scene lock",
                "cinematography_lock": "Same camera lock",
            },
            previous,
            project_id="film-abcd1234",
        )
        self.assertIn("PREVIOUS SHOT ENDING STATE\nEnding state 1", prompt)
        self.assertIn("PREVIOUS SHOT TRANSITION HOOK\nHook 1", prompt)
        self.assertIn("CURRENT SHOT STARTING STATE\nStart state 2", prompt)
        self.assertIn("SHOT DELTA\nDelta event 2", prompt)
        self.assertIn(str(derive_shot_seed("film-abcd1234", "42", 2)), prompt)

    def test_storyboard_supervisor_grounds_mock_dialogue_in_shot_events(self) -> None:
        shots = [make_shot(1), make_shot(2)]
        script = WriterAgent().supervise_storyboard(
            "An original signal arrives.",
            {"theme": "uncertainty"},
            {"story": "A story", "narration": "Old generic line."},
            shots,
            duration_seconds=12,
        )
        self.assertEqual(script["narrative_source"], "storyboard_supervisor")
        self.assertIn("Purpose 1", script["narration"])
        self.assertIn("Main action 2", script["narration"])
        self.assertEqual([item["shot"] for item in script["dialogue_book"]], [1, 2])
        self.assertEqual([item["shot"] for item in script["subtitle_track"]], [1, 2])

    def test_alignment_preserves_more_than_six_storyboard_cues(self) -> None:
        shots = [make_shot(index, duration=8) for index in range(1, 9)]
        script = {
            "narration": "A continuous line.",
            "dialogue_book": [{"shot": index, "text": f"Event {index}"} for index in range(1, 9)],
            "subtitle_track": [{"shot": index, "text": f"Event {index}"} for index in range(1, 9)],
        }
        aligned = align_script_to_shots(script, shots)
        self.assertEqual(len(aligned["dialogue_book"]), 8)
        self.assertEqual(aligned["subtitle_track"][-1]["text"], "Event 8")

    def test_reviewer_uses_source_duration_not_edit_duration(self) -> None:
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings("http://127.0.0.1:8188", 900, Path("workflows"), 9071, root, True)
            reviewer = ReviewerAgent(settings)
            shot = make_shot(1, duration=6)
            shot.duration_seconds = 12
            shot.desired_duration = 12
            shot.status = "generated_comfyui"
            with patch.object(reviewer, "_video_duration", return_value=6.1), patch.object(
                reviewer, "_extract_keyframes", return_value=[root / "frame.jpg"]
            ):
                reviewer.review_generated(shot)
            self.assertEqual(shot.status, "awaiting_visual_review")
            self.assertEqual(shot.qc_status, "AWAITING_VISUAL_REVIEW")
            self.assertEqual(shot.qc_details["next_action"], "APPROVE_SHOT")

    def test_subtitle_export_never_emits_three_lines_and_splits_long_cue(self) -> None:
        long_text = (
            "The protagonist watches the silent console recalibrate while the amber signal travels "
            "through the room and changes the meaning of the opening image."
        )
        wrapped = _wrap_cue_text(long_text)
        self.assertLessEqual(len(wrapped.splitlines()), 2)
        exported = render_srt([{"start_seconds": 0, "end_seconds": 12, "text": long_text}])
        cues = [part for part in exported.strip().split("\n\n") if part]
        self.assertGreaterEqual(len(cues), 2)
        for cue in cues:
            body = cue.split("\n", 2)[-1]
            self.assertLessEqual(len(body.splitlines()), 2)
            self.assertNotIn("\n\n", body)

    def test_subtitle_split_does_not_leave_protected_phrase_at_boundary(self) -> None:
        text = (
            "The operator waits in the control room while the silent console begins to recalibrate "
            "and the amber signal crosses the glass."
        )
        exported = render_srt([{"start_seconds": 0, "end_seconds": 10, "text": text}])
        for cue in exported.strip().split("\n\n"):
            body = cue.split("\n", 2)[-1]
            for line in body.splitlines():
                self.assertNotRegex(line.lower(), r"(?:\bthe|\bin|\bto|\bwith|\bfor|\bis|\bare)$")

    def test_state_machine_maps_legacy_status_and_project_payload(self) -> None:
        self.assertEqual(state_for_status("ready_for_ai_edit"), ProjectState.SHOTS_READY)
        self.assertEqual(state_for_status("completed_comfyui"), ProjectState.FINAL_READY)
        self.assertEqual(describe_status("completed_mock")["stage"], "DELIVER")
        self.assertEqual(describe_status("rendering_comfyui")["pipeline"]["render"], "active")
        self.assertEqual(describe_status("completed_mock")["pipeline"]["deliver"], "ready")
        project = MovieProject(
            "film-state", "An original signal arrives.", 48, "cinematic", "completed_mock", {}, {}, {}, []
        )
        payload = project.to_dict()
        self.assertEqual(payload["pipeline_state"]["state"], "final_ready")
        self.assertFalse(payload["pipeline_state"]["archived"])

    def test_manual_review_gate_blocks_legacy_approved_status(self) -> None:
        shot = make_shot(1)
        shot.qc_status = "AWAITING_VISUAL_REVIEW"
        project = MovieProject(
            "film-gate", "An original signal arrives.", 6, "cinematic", "ready_for_ai_edit", {}, {}, {}, [shot]
        )
        from movie_agent.orchestrator import MovieOrchestrator

        self.assertFalse(MovieOrchestrator._shots_ready(project))


if __name__ == "__main__":
    unittest.main()
