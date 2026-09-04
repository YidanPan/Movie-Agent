"""Structured data produced by the planning agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from movie_agent.services.subtitles import ensure_dialogue_assets, normalise_subtitle_mode
from movie_agent.services.audio import DEFAULT_MUSIC_INTENSITY, normalise_music_intensity, normalise_music_mode
from movie_agent.services.final_look import ensure_final_look
from movie_agent.services.continuity import build_continuity_lock
from movie_agent.state import describe_status


@dataclass
class Shot:
    number: int
    duration_seconds: int
    framing: str
    image_description: str
    action: str
    sound_design: str
    generation_mode: str
    prompt: str
    output_placeholder: str
    status: str = "planned"
    attempts: int = 0
    narrative_purpose: str = ""
    starting_state: str = ""
    main_action: str = ""
    character_reaction: str = ""
    ending_state: str = ""
    transition_hook: str = ""
    desired_duration: float = 0
    # Native generation length stays separate from the editorial timeline
    # length. This lets an editor trim, hold, or slow a shot without asking
    # ComfyUI to regenerate the whole film.
    source_duration_seconds: int = 0
    timing_mode: str = "native"
    qc_flags: list[str] = field(default_factory=list)
    # Media contracts stay attached to the shot so the UI can distinguish a
    # disposable proxy from a viewer copy and the original/master source.
    media_assets: dict[str, Any] = field(default_factory=dict)
    # The storyboard keeps ``prompt`` concise (a Shot Delta).  Generation
    # compiles the full continuity context at render time and stores it here
    # for review/debugging without overwriting the editorial prompt.
    compiled_generation_prompt: str = ""
    generation_seed: int | None = None

    def __post_init__(self) -> None:
        if self.source_duration_seconds <= 0:
            self.source_duration_seconds = int(self.duration_seconds)
        if not self.desired_duration:
            self.desired_duration = float(self.duration_seconds)

    @property
    def edit_duration_seconds(self) -> int:
        """Explicit name for the current editorial/timeline duration."""

        return int(self.duration_seconds)

    @edit_duration_seconds.setter
    def edit_duration_seconds(self, value: int) -> None:
        self.duration_seconds = int(value)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # ``duration_seconds`` is retained for API compatibility; this alias
        # makes the Source-vs-Edit distinction explicit to new consumers.
        payload["edit_duration_seconds"] = self.edit_duration_seconds
        return payload


@dataclass
class MovieProject:
    project_id: str
    idea: str
    duration_seconds: int
    visual_style: str
    status: str
    brief: dict[str, str]
    script: dict[str, Any]
    visual_bible: dict[str, str]
    storyboard: list[Shot]
    quality_report: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    final_output_placeholder: str | None = None
    rough_cut_placeholder: str | None = None
    subtitle_mode: str = "burned"
    edit_plan: dict[str, Any] = field(default_factory=dict)
    # Sound department outputs are kept as JSON metadata so mock projects and
    # Spark projects share the same review/edit contract.
    music_mode: str = "ai"
    music_intensity: float = DEFAULT_MUSIC_INTENSITY
    music_asset_name: str = ""
    music_brief: dict[str, Any] = field(default_factory=dict)
    audio_tracks: dict[str, dict[str, Any]] = field(default_factory=dict)
    smart_ducking: dict[str, Any] = field(default_factory=dict)
    mix_state: dict[str, Any] = field(default_factory=dict)
    final_look: dict[str, Any] = field(default_factory=dict)
    story_beats: list[dict[str, Any]] = field(default_factory=list)
    film_language: str = "en"
    continuity_lock: dict[str, Any] = field(default_factory=dict)
    voice_profile: dict[str, Any] = field(default_factory=dict)
    target_resolution: str = "1080p"
    target_fps: int = 24
    video_assets: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Keep the legacy ``status`` field while exposing one canonical state
        # interpretation for the frontend and external API clients.
        payload["pipeline_state"] = describe_status(self.status)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MovieProject":
        project = cls(
            project_id=data["project_id"],
            idea=data["idea"],
            duration_seconds=data["duration_seconds"],
            visual_style=data["visual_style"],
            status=data["status"],
            brief=data["brief"],
            script=ensure_dialogue_assets(
                data.get("script") or {},
                duration_seconds=int(data.get("duration_seconds", 48)),
                shot_count=len(data.get("storyboard") or []) or None,
            ),
            visual_bible=data["visual_bible"],
            storyboard=[
                Shot(**{key: value for key, value in shot.items() if key != "edit_duration_seconds"})
                for shot in data["storyboard"]
            ],
            quality_report=data.get("quality_report", []),
            logs=data.get("logs", []),
            final_output_placeholder=data.get("final_output_placeholder"),
            rough_cut_placeholder=data.get("rough_cut_placeholder"),
            subtitle_mode=normalise_subtitle_mode(
                data.get("subtitle_mode") or (data.get("script") or {}).get("subtitle_mode") or "burned"
            ),
            edit_plan=data.get("edit_plan") or {},
            music_mode=normalise_music_mode(data.get("music_mode") or "ai"),
            music_intensity=normalise_music_intensity(
                data.get("music_intensity", (data.get("music_brief") or {}).get("intensity", DEFAULT_MUSIC_INTENSITY))
            ),
            music_asset_name=str(data.get("music_asset_name") or ""),
            music_brief=data.get("music_brief") or {},
            audio_tracks=data.get("audio_tracks") or {},
            smart_ducking=data.get("smart_ducking") or {},
            mix_state=data.get("mix_state") or {},
            final_look=data.get("final_look") or {},
            story_beats=data.get("story_beats") or [],
            film_language=str(data.get("film_language") or "en").lower(),
            continuity_lock=data.get("continuity_lock") or {},
            voice_profile=data.get("voice_profile") or {},
            target_resolution=str(data.get("target_resolution") or "1080p").lower(),
            target_fps=int(data.get("target_fps") or 24),
            video_assets=data.get("video_assets") or {},
        )
        # Older project JSON files predate the sound department. Migrate them
        # in memory so the next save exposes the same audio contract.
        if not project.music_brief or not project.audio_tracks or not project.smart_ducking:
            from movie_agent.services.audio import ensure_audio_design

            ensure_audio_design(project)
        # Migrate Chinese visual bible keys to English equivalents.
        _vb_aliases = {"角色卡": "character_card", "场景卡": "scene_card", "风格卡": "style_card", "声音卡": "sound_card"}
        migrated_vb = {}
        for key, value in project.visual_bible.items():
            english_key = _vb_aliases.get(key, key)
            migrated_vb[english_key] = value
        project.visual_bible = migrated_vb
        ensure_final_look(project)
        if not project.continuity_lock:
            project.continuity_lock = build_continuity_lock(project.visual_bible, project.film_language)
        return project

    def brief_as_markdown(self) -> str:
        return "\n".join(["## Project Brief"] + [f"- **{key}**: {value}" for key, value in self.brief.items()])

    def script_as_markdown(self) -> str:
        dialogue = self.script.get("dialogue_book") or []
        subtitles = self.script.get("subtitle_track") or []
        dialogue_lines = [
            f"- Shot {item.get('shot', index + 1)} · {item.get('speaker', 'NARRATOR')}: {item.get('text', '')}"
            for index, item in enumerate(dialogue)
            if isinstance(item, dict)
        ]
        subtitle_lines = [
            f"- {item.get('start_seconds', 0):.2f}s–{item.get('end_seconds', 0):.2f}s · Shot {item.get('shot', index + 1)}: {item.get('text', '')}"
            for index, item in enumerate(subtitles)
            if isinstance(item, dict)
        ]
        locked = "Locked" if self.script.get("dialogue_locked") else "Pending"
        parts = [
            "## Screenplay\n" + str(self.script.get("story", "")),
            "## Narration\n> " + str(self.script.get("narration", "")),
            "## Dialogue Book\n" + ("\n".join(dialogue_lines) or "No dialogue."),
            "## Subtitle Track\n" + ("\n".join(subtitle_lines) or "No subtitles."),
            f"Dialogue status: {locked} · Output mode: {self.subtitle_mode}",
        ]
        return "\n\n".join(parts)

    def visual_bible_as_markdown(self) -> str:
        return "## Visual Bible\n" + "\n".join(
            f"- **{key}**: {value}" for key, value in self.visual_bible.items()
        )

    def audio_as_markdown(self) -> str:
        """Export the sound department plan alongside the movie plan."""

        brief = self.music_brief or {}
        ducking_on = "ON" if self.smart_ducking.get("enabled") else "OFF"
        rows = [
            "## Sound Department",
            f"- **Music Mode**: {self.music_mode}",
            f"- **Music Intensity**: {int(round(self.music_intensity * 100))}% · {brief.get('volume_db', (self.audio_tracks or {}).get('music', {}).get('volume_db', '·'))} dB",
            f"- **Music Brief**: {brief.get('style', 'pending')} · {brief.get('bpm', '·')} BPM",
            f"- **Instruments**: {' · '.join(str(item) for item in (brief.get('instruments') or [])) or 'pending'}",
            f"- **Entry / Peak / Fade Out**: {brief.get('entry_seconds', 0)}s / {brief.get('peak_seconds', '·')}s / {brief.get('fade_out_seconds', '·')}s",
            f"- **Smart Ducking**: {ducking_on} · {self.smart_ducking.get('amount_db', -8)} dB",
            "",
            "| Track | Status | Source | Volume |",
            "| --- | --- | --- | --- |",
        ]
        for key in ("voice", "music", "sfx", "ambience"):
            track = (self.audio_tracks or {}).get(key, {})
            rows.append(
                f"| {track.get('label', key.upper())} | {track.get('status', 'pending')} | {track.get('source', '·')} | {track.get('volume_db', '·')} dB |"
            )
        arc = brief.get("emotional_arc") or []
        if arc:
            rows.extend(["", "**Emotional Arc**: " + " → ".join(str(item.get("emotion", "arc")) for item in arc)])
        return "\n".join(rows)

    def final_look_as_markdown(self) -> str:
        look = self.final_look or {}
        return "\n".join(
            [
                "## Final Look",
                f"- **Look**: {look.get('label', 'Original')} · {look.get('english', 'ORIGINAL')}",
                f"- **Intensity**: {look.get('intensity', 0.72)} · Grain {look.get('grain', 0)} · Vignette {look.get('vignette', 0)} · Highlight Softening {look.get('highlight_soften', 0)}",
                f"- **Scope**: {look.get('scope', 'whole_film')} · **Status**: {look.get('status', 'READY TO FINISH')}",
            ]
        )

    def storyboard_as_markdown(self) -> str:
        rows = [
            "## Storyboard",
            "| Shot | Duration | Framing | Narrative Purpose | Mode | Status | Visuals & Action | Sound |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for shot in self.storyboard:
            rows.append(
                f"| {shot.number} | {shot.duration_seconds}s | {shot.framing} | {shot.narrative_purpose or '—'} | {shot.generation_mode} | {shot.status} | "
                f"{shot.image_description}; {shot.action} | {shot.sound_design} |"
            )
        return "\n".join(rows)

    def project_as_markdown(self) -> str:
        """Portable production brief for judges, collaborators, or later rendering."""
        prompts = [
            "## Final Video Prompts",
            *[f"### Shot {shot.number}\n{shot.prompt}" for shot in self.storyboard],
        ]
        return "\n\n".join(
            [
                f"# Movie-Agent Project: {self.project_id}",
                f"**Idea**: {self.idea}\n\n**Target Duration**: {self.duration_seconds} seconds\n\n**Visual Style**: {self.visual_style}",
                self.brief_as_markdown(),
                self.script_as_markdown(),
                self.visual_bible_as_markdown(),
                self.audio_as_markdown(),
                self.final_look_as_markdown(),
                self.storyboard_as_markdown(),
                "\n".join(prompts),
                self.log_as_markdown(),
            ]
        )

    def log_as_markdown(self) -> str:
        return "## Task Log\n" + "\n".join(f"- {entry}" for entry in self.logs)
