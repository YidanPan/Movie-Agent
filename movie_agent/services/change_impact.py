"""Classify Shot edits by the downstream production artifacts they affect."""

TIMING_FIELDS = {"duration_seconds", "desired_duration", "timing_mode"}
VISUAL_FIELDS = {"framing", "image_description", "prompt", "generation_mode", "visual_motif"}
NARRATIVE_FIELDS = {
    "story_function", "narrative_purpose", "starting_state", "main_action", "secondary_action",
    "environment_reaction", "character_reaction", "ending_state", "action", "scene_id", "character_ids",
    "prop_ids", "transition_type",
    "state_delta",
}
SPEECH_FIELDS = {"speech_policy", "sound_design"}


def resolve_change_impact(fields: set[str]) -> dict[str, object]:
    fields = {str(field) for field in fields}
    visual = bool(fields & VISUAL_FIELDS)
    narrative = bool(fields & NARRATIVE_FIELDS)
    timing = bool(fields & TIMING_FIELDS)
    speech = bool(fields & SPEECH_FIELDS)
    if visual or narrative:
        downstream = ["storyboard_review", "script_supervisor", "shot_media", "qc", "voice", "subtitles", "edit"]
    elif timing:
        downstream = ["voice", "subtitles", "rough_cut", "final_cut", "final_look", "export"]
    elif speech:
        downstream = ["dialogue", "voice", "subtitles", "mix", "edit"]
    else:
        downstream = []
    return {
        "fields": sorted(fields),
        "timing": timing,
        "visual": visual,
        "narrative": narrative,
        "speech": speech,
        "downstream": downstream,
    }


__all__ = ["TIMING_FIELDS", "VISUAL_FIELDS", "NARRATIVE_FIELDS", "SPEECH_FIELDS", "resolve_change_impact"]
