from pathlib import Path

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator


class FakeStructuredLLM:
    """Deterministic structured model used to exercise the real agent path."""

    def __init__(self, *, silent: bool = False) -> None:
        self.silent = silent

    def complete_json(self, system: str, prompt: str) -> dict:
        if "story-world analyst" in system:
            return {
                "characters": [{"character_id": "protagonist", "name": "Ari", "role": "protagonist"}],
                "scenes": [{"scene_id": "primary", "name": "Control Room", "story_role": "main setting"}],
                "props": [],
            }
        if "chief director" in system:
            return {
                "theme": "Trusting a human choice inside an automated city",
                "narrative_scale": "One character, one room, one decision",
                "visual_style": "restrained near-future cinema",
                "director_intent": "Make the final choice feel quiet but irreversible.",
                "compliance_constraints": "Original story and visual language only.",
            }
        if "sci-fi short film screenwriter" in system:
            return {
                "story": "A courier notices an impossible signal and chooses to answer it.",
                "narration": "The system records every action except the one that matters.",
                "outline": "Routine gives way to a signal. Suspicion becomes resolve. The choice remains human.",
                "dialogue_book": [],
                "subtitle_track": [],
            }
        if "story structure analyst" in system:
            return {"beats": [
                {
                    "beat_id": f"beat-{i:02d}", "beat_number": i, "scene_id": "primary",
                    "character_ids": ["protagonist"], "prop_ids": [], "story_function": ["SETUP", "ROUTINE", "ANOMALY", "RECOGNITION", "CLIMAX"][i - 1],
                    "narrative_purpose": f"Beat {i} changes the situation.", "information_gain": 0.5 + i / 20,
                    "emotional_shift": f"phase {i} changes the pressure", "visual_motif": f"amber signal {i}",
                    "starting_state": f"The room holds phase {max(1, i - 1)}.", "ending_state": f"The signal changes at phase {i}.",
                    "transition_hook": f"The next beat follows phase {i}.", "importance": 0.5 + i / 20,
                    "duration_weight": 1.0,
                }
                for i in range(1, 6)
            ]}
        if "film art director" in system:
            character_lock = "Ari has short dark hair, a charcoal jacket, and a small brow scar."
            scene_lock = "A concrete control room has cool strips and one amber console."
            return {
                "character_card": "One stable protagonist.", "scene_card": "One stable control room.",
                "style_card": "Restrained near-future cinema.", "sound_card": "Low room tone.",
                "character_lock": character_lock, "scene_lock": scene_lock,
                "prop_lock": "The console remains stable.",
                "cinematography_lock": "35mm, slow dolly, restrained contrast.", "reference_seed": "42",
                "characters": [{
                    "character_id": "protagonist", "name": "Ari", "role": "hero",
                    "appearance_lock": character_lock, "face_lock": "same face",
                    "hair_lock": "short dark hair", "costume_lock": "charcoal jacket",
                    "silhouette_lock": "lean silhouette", "prop_lock": "none",
                }],
                "scenes": [{
                    "scene_id": "primary", "name": "Control Room", "environment_lock": scene_lock,
                    "architecture_lock": "concrete control room", "lighting_lock": "cool strips and amber console",
                    "palette_lock": "cool grey and amber", "prop_lock": "stable console",
                    "ui_palette": {"dominant": "#6B665B", "accent": "#A88752", "temperature": "neutral", "luminance": 0.5},
                }],
                "props": [], "cinematography": {"lens_language": "35mm", "camera_motion": "slow dolly", "composition": "quiet", "film_texture": "fine grain", "color_pipeline": "restrained"},
            }
        if "repairing one flagged storyboard shot" in system:
            return {
                "story_function": "RECOGNITION", "narrative_purpose": "The protagonist recognises the signal's consequence.",
                "information_gain": 0.9, "emotional_shift": "unease to resolve", "visual_motif": "the answering amber signal",
                "starting_state": "The signal waits for an answer.", "main_action": "Ari makes one deliberate choice.",
                "secondary_action": "", "environment_reaction": "The console opens a new channel.",
                "character_reaction": "Ari steadies their hand.", "ending_state": "The channel remains open.",
                "transition_hook": "The consequence carries into the next shot.", "transition_type": "CONTINUOUS",
                "shot_complexity": "LOW", "prompt": "Continue the locked control room as Ari makes one deliberate choice and the amber signal opens a new channel.",
                "state_delta": {},
            }
        if "film storyboard artist" in system:
            policy = "SILENT" if self.silent else "DIALOGUE"
            shots = []
            for i in range(1, 7):
                beat = min(i, 5)
                shots.append({
                    "duration_seconds": 8, "framing": "medium close-up", "image_description": ["Ari enters the control room", "Ari reads a sealed panel", "Ari turns a brass dial", "Ari faces the open channel", "Ari reaches toward the console", "Ari leaves the lit room"][i - 1],
                    "action": ["Ari enters the room", "Ari reads the panel", "Ari turns the dial", "Ari opens the channel", "Ari answers the signal", "Ari leaves the room"][i - 1], "sound_design": "Low room tone.", "generation_mode": "T2V",
                    "prompt": f"Continue the locked control room state while beat {i} advances through a distinct action.",
                    "beat_id": f"beat-{beat:02d}", "scene_id": "primary", "character_ids": ["protagonist"], "prop_ids": [],
                    "story_function": ["SETUP", "ROUTINE", "ANOMALY", "RECOGNITION", "CLIMAX", "AFTERMATH"][i - 1], "narrative_purpose": f"Beat {i} creates a new choice.",
                    "information_gain": 0.55 + i / 20, "emotional_shift": f"phase {i} changes the pressure", "visual_motif": f"amber signal {i}",
                    "starting_state": f"The room holds phase {max(1, i - 1)}.", "main_action": ["Ari enters the room", "Ari reads the panel", "Ari turns the dial", "Ari opens the channel", "Ari answers the signal", "Ari leaves the room"][i - 1],
                    "secondary_action": "", "environment_reaction": f"The console records phase {i}.", "character_reaction": f"Ari reacts to phase {i}.",
                    "ending_state": f"Phase {i} is complete and the room records it.", "transition_hook": f"Beat {i + 1} follows phase {i}.",
                    "transition_type": "CONTINUOUS", "speech_policy": policy, "shot_complexity": "LOW", "state_delta": {},
                })
            return {"shots": shots}
        if "script supervisor" in system:
            policy = "SILENT" if self.silent else "DIALOGUE"
            return {
                "narration": "The system records every action except the one that matters.",
                "dialogue_book": [] if self.silent else [{"shot": 1, "speaker": "NARRATOR", "kind": "narration", "text": "The choice remains human."}],
                "subtitle_track": [] if self.silent else [{"shot": 1, "speaker": "NARRATOR", "kind": "narration", "text": "The choice remains human."}],
            }
        if "copyright" in system:
            return {"risk_level": "low", "reasons": [], "rewrite_guidance": "No change required."}
        raise AssertionError(f"Unexpected structured LLM call: {system}")


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


def _run_fake_llm_e2e(tmp_path: Path, monkeypatch, *, silent: bool):
    settings = _mock_settings(tmp_path)
    fake = FakeStructuredLLM(silent=silent)
    monkeypatch.setattr("movie_agent.orchestrator.build_creative_llm", lambda _settings: fake)
    orchestrator = MovieOrchestrator(settings)
    project = orchestrator.create_project("A courier follows a signal beyond the moon.", 48, "film sci-fi")
    assert orchestrator.using_creative_llm is True
    assert project.script["speech_policy_by_shot"]
    if silent:
        assert not project.script["dialogue_book"]
        assert not project.script["subtitle_track"]
    else:
        assert project.script["dialogue_book"]
        assert project.script["subtitle_track"]
    locked = orchestrator.lock_dialogue(project.project_id)
    assert locked.script["dialogue_locked"] is True
    rough = orchestrator.create_rough_cut(project.project_id)
    approved = orchestrator.approve_edit(project.project_id, "soft")
    completed = orchestrator.generate_final_master(project.project_id)
    reloaded = MovieOrchestrator(settings).store.load(project.project_id)
    assert rough.status == "rough_cut_ready"
    assert approved.edit_plan["approved"] is True
    assert completed.status == "completed_text_ai_video_mock"
    assert reloaded.status == "completed_text_ai_video_mock"
    return project


def test_fake_structured_llm_normal_dialogue_reaches_mock_final_master(tmp_path, monkeypatch):
    project = _run_fake_llm_e2e(tmp_path, monkeypatch, silent=False)
    assert project.script["speech_policy_by_shot"]["1"] == "DIALOGUE"


def test_fake_structured_llm_all_silent_reaches_mock_final_master(tmp_path, monkeypatch):
    project = _run_fake_llm_e2e(tmp_path, monkeypatch, silent=True)
    assert set(project.script["speech_policy_by_shot"].values()) == {"SILENT"}


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
