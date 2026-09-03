"""Structured data produced by the planning agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from movie_agent.services.subtitles import ensure_dialogue_assets, normalise_subtitle_mode
from movie_agent.services.audio import DEFAULT_MUSIC_INTENSITY, normalise_music_intensity, normalise_music_mode
from movie_agent.services.final_look import ensure_final_look


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

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
            storyboard=[Shot(**shot) for shot in data["storyboard"]],
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
        )
        # Older project JSON files predate the sound department. Migrate them
        # in memory so the next save exposes the same audio contract.
        if not project.music_brief or not project.audio_tracks or not project.smart_ducking:
            from movie_agent.services.audio import ensure_audio_design

            ensure_audio_design(project)
        ensure_final_look(project)
        return project

    def brief_as_markdown(self) -> str:
        return "\n".join(["## 项目设定"] + [f"- **{key}**：{value}" for key, value in self.brief.items()])

    def script_as_markdown(self) -> str:
        dialogue = self.script.get("dialogue_book") or []
        subtitles = self.script.get("subtitle_track") or []
        dialogue_lines = [
            f"- 镜头 {item.get('shot', index + 1)} · {item.get('speaker', '旁白')}：{item.get('text', '')}"
            for index, item in enumerate(dialogue)
            if isinstance(item, dict)
        ]
        subtitle_lines = [
            f"- {item.get('start_seconds', 0):.2f}s–{item.get('end_seconds', 0):.2f}s · 镜头 {item.get('shot', index + 1)}：{item.get('text', '')}"
            for index, item in enumerate(subtitles)
            if isinstance(item, dict)
        ]
        parts = [
            "## 短剧本\n" + str(self.script.get("story", "")),
            "## 旁白\n> " + str(self.script.get("narration", "")),
            "## 台词本 / Dialogue Book\n" + ("\n".join(dialogue_lines) or "暂无台词。"),
            "## 字幕轨 / Subtitle Track\n" + ("\n".join(subtitle_lines) or "暂无字幕。"),
            f"字幕状态：{'已锁定' if self.script.get('dialogue_locked') else '待锁定'} · 输出模式：{self.subtitle_mode}",
        ]
        return "\n\n".join(parts)

    def visual_bible_as_markdown(self) -> str:
        return "## 视觉设定\n" + "\n".join(
            f"- **{key}**：{value}" for key, value in self.visual_bible.items()
        )

    def audio_as_markdown(self) -> str:
        """Export the sound department plan alongside the movie plan."""

        brief = self.music_brief or {}
        rows = [
            "## 声音设计 / Sound Department",
            f"- **配乐模式**：{self.music_mode}",
            f"- **音乐强度**：{int(round(self.music_intensity * 100))}% · {brief.get('volume_db', (self.audio_tracks or {}).get('music', {}).get('volume_db', '·'))} dB",
            f"- **Music Brief**：{brief.get('style', '待生成')} · {brief.get('bpm', '·')} BPM",
            f"- **乐器**：{' · '.join(str(item) for item in (brief.get('instruments') or [])) or '待规划'}",
            f"- **进入 / 高潮 / 淡出**：{brief.get('entry_seconds', 0)}s / {brief.get('peak_seconds', '·')}s / {brief.get('fade_out_seconds', '·')}s",
            f"- **Smart Ducking**：{'开启' if self.smart_ducking.get('enabled') else '关闭'} · {self.smart_ducking.get('amount_db', -8)} dB",
            "",
            "| 音轨 | 状态 | 来源 | 音量 |",
            "| --- | --- | --- | --- |",
        ]
        for key in ("voice", "music", "sfx", "ambience"):
            track = (self.audio_tracks or {}).get(key, {})
            rows.append(
                f"| {track.get('label', key.upper())} | {track.get('status', '待规划')} | {track.get('source', '·')} | {track.get('volume_db', '·')} dB |"
            )
        arc = brief.get("emotional_arc") or []
        if arc:
            rows.extend(["", "**Emotional Arc**：" + " → ".join(str(item.get("emotion", "arc")) for item in arc)])
        return "\n".join(rows)

    def final_look_as_markdown(self) -> str:
        look = self.final_look or {}
        return "\n".join(
            [
                "## 最终润色 / Final Look",
                f"- **Look**：{look.get('label', '原片')} · {look.get('english', 'ORIGINAL')}",
                f"- **Intensity**：{look.get('intensity', 0.72)} · Grain {look.get('grain', 0)} · Vignette {look.get('vignette', 0)} · Highlight Softening {look.get('highlight_soften', 0)}",
                f"- **Scope**：{look.get('scope', 'whole_film')} · **Status**：{look.get('status', 'READY TO FINISH')}",
            ]
        )

    def storyboard_as_markdown(self) -> str:
        rows = [
            "## 分镜表",
            "| 镜头 | 时长 | 景别 | 生成方式 | 状态 | 画面与动作 | 声音 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for shot in self.storyboard:
            rows.append(
                f"| {shot.number} | {shot.duration_seconds}s | {shot.framing} | {shot.generation_mode} | {shot.status} | "
                f"{shot.image_description}；{shot.action} | {shot.sound_design} |"
            )
        return "\n".join(rows)

    def project_as_markdown(self) -> str:
        """Portable production brief for judges, collaborators, or later rendering."""
        prompts = [
            "## 最终视频提示词",
            *[f"### 镜头 {shot.number}\n{shot.prompt}" for shot in self.storyboard],
        ]
        return "\n\n".join(
            [
                f"# Movie-Agent 项目：{self.project_id}",
                f"**创意**：{self.idea}\n\n**目标时长**：{self.duration_seconds} 秒\n\n**视觉风格**：{self.visual_style}",
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
        return "## 任务日志\n" + "\n".join(f"- {entry}" for entry in self.logs)
