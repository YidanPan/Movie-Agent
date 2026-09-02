"""Pre-render structural and semantic quality gates."""

from __future__ import annotations

from movie_agent.models import Shot
from movie_agent.services.llm import CreativeLLM


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


class SemanticCopyrightReviewer:
    """Use an opt-in LLM to detect lookalike references beyond fixed keywords."""

    def __init__(self, llm: CreativeLLM | None) -> None:
        self.llm = llm

    def review(
        self,
        *,
        idea: str,
        script: dict[str, str],
        visual_bible: dict[str, str],
        storyboard: list[Shot],
    ) -> list[str]:
        if self.llm is None:
            return ["语义版权审核：未配置文本审核模型，已完成规则型 IP 过滤，仍建议人工复核。"]

        result = self.llm.complete_json(
            "你是影视版权与原创性审核员。识别与既有影视 IP、角色、片名、标志性设定、台词或镜头语言的实质性近似。"
            "不要因为一般科幻题材、通用类型元素或公共领域素材而误报。",
            "审核下列原创影视提案，只返回 JSON："
            '{"risk_level":"low|medium|high","reasons":["不超过3条中文理由"],'
            '"rewrite_guidance":"可执行的中文改写建议"}。\n'
            f"原始创意：{idea}\n"
            f"剧本：{script.get('story', '')}\n"
            f"旁白：{script.get('narration', '')}\n"
            f"视觉设定：{'；'.join(f'{key}：{value}' for key, value in visual_bible.items())}\n"
            f"分镜：{'；'.join(f'{shot.number}. {shot.image_description} {shot.action}' for shot in storyboard)}",
        )
        risk_level = str(result.get("risk_level", "")).strip().lower()
        reasons = result.get("reasons", [])
        if not isinstance(reasons, list):
            reasons = [str(reasons)]
        reason_text = "；".join(str(reason).strip() for reason in reasons if str(reason).strip())
        guidance = str(result.get("rewrite_guidance", "")).strip()
        if risk_level == "high":
            detail = reason_text or "存在与既有影视 IP 的高度近似风险。"
            raise ValueError(f"语义版权审核未通过：{detail} {guidance}".strip())
        if risk_level == "medium":
            return [f"语义版权审核：发现可混同风险，建议改写。{reason_text} {guidance}".strip()]
        if risk_level == "low":
            return ["语义版权审核：未发现与既有影视 IP 的实质性近似。"]
        return ["语义版权审核：模型未返回有效风险等级，已保留规则型检查结果，建议人工复核。"]
