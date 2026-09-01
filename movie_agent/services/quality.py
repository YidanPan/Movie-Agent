"""Deterministic quality gate for assets that can be checked before rendering."""

from __future__ import annotations

from movie_agent.models import Shot


class PlanningQualityGate:
    """Reject invalid plans early and record readable non-blocking review notes."""

    prohibited_references = ("星球大战", "Star Wars", "漫威", "Marvel", "哈利·波特", "Harry Potter")

    def review(
        self,
        *,
        duration_seconds: int,
        script: dict[str, str],
        visual_bible: dict[str, str],
        storyboard: list[Shot],
    ) -> list[str]:
        errors: list[str] = []
        if not script.get("story") or not script.get("narration"):
            errors.append("剧本或旁白为空。")
        if not {"角色卡", "场景卡", "风格卡"}.issubset(visual_bible):
            errors.append("视觉设定缺少角色卡、场景卡或风格卡。")
        if not 6 <= len(storyboard) <= 10:
            errors.append("分镜数量必须为 6–10 个。")
        if any(not 4 <= shot.duration_seconds <= 8 for shot in storyboard):
            errors.append("每个镜头时长必须为 4–8 秒。")
        if sum(shot.duration_seconds for shot in storyboard) != duration_seconds:
            errors.append("分镜总时长与目标时长不一致。")
        if any(len(shot.prompt.strip()) < 20 for shot in storyboard):
            errors.append("存在过短的最终视频提示词。")
        combined_text = "\n".join(
            [script.get("story", ""), script.get("narration", "")]
            + [shot.image_description + shot.prompt for shot in storyboard]
        ).lower()
        if any(reference.lower() in combined_text for reference in self.prohibited_references):
            errors.append("检测到可能复刻现有影视 IP 的引用。")
        if errors:
            raise ValueError("质量门未通过：" + "；".join(errors))
        return [
            "质检 Agent：镜头数量、时长、提示词完整性检查通过。",
            "质检 Agent：未发现预设的现有影视 IP 引用。",
            "质检 Agent：角色卡、场景卡和风格卡已齐全，可进入视频生成队列。",
        ]
