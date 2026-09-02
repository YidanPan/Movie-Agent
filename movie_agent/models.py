"""Structured data produced by the planning agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from movie_agent.services.subtitles import ensure_dialogue_assets, normalise_subtitle_mode


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MovieProject":
        return cls(
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
        )

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
                self.storyboard_as_markdown(),
                "\n".join(prompts),
                self.log_as_markdown(),
            ]
        )

    def log_as_markdown(self) -> str:
        return "## 任务日志\n" + "\n".join(f"- {entry}" for entry in self.logs)
