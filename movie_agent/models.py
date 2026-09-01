"""Structured data produced by the planning agents."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


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


@dataclass
class MovieProject:
    project_id: str
    idea: str
    duration_seconds: int
    visual_style: str
    status: str
    brief: dict[str, str]
    script: dict[str, str]
    visual_bible: dict[str, str]
    storyboard: list[Shot]
    quality_report: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    final_output_placeholder: str | None = None

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
            script=data["script"],
            visual_bible=data["visual_bible"],
            storyboard=[Shot(**shot) for shot in data["storyboard"]],
            quality_report=data.get("quality_report", []),
            logs=data.get("logs", []),
            final_output_placeholder=data.get("final_output_placeholder"),
        )

    def brief_as_markdown(self) -> str:
        return "\n".join(["## 项目设定"] + [f"- **{key}**：{value}" for key, value in self.brief.items()])

    def script_as_markdown(self) -> str:
        return "## 短剧本\n" + self.script["story"] + "\n\n## 旁白\n> " + self.script["narration"]

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

    def log_as_markdown(self) -> str:
        return "## 任务日志\n" + "\n".join(f"- {entry}" for entry in self.logs)
