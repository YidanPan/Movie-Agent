"""Director agent: turns an idea into project-level creative constraints."""

from movie_agent.services.llm import CreativeLLM


class DirectorAgent:
    def __init__(self, llm: CreativeLLM | None = None) -> None:
        self.llm = llm

    def plan(self, idea: str, duration_seconds: int, visual_style: str) -> dict[str, str]:
        if self.llm:
            result = self.llm.complete_json(
                "你是科幻短片总导演。坚持原创、单人物单空间单事件、避免既有影视 IP。",
                (
                    f"创意：{idea}\n目标时长：{duration_seconds} 秒\n视觉风格：{visual_style}\n"
                    "返回键：主题、叙事尺度、视觉风格、导演意图、合规约束。"
                ),
            )
            result["原始创意"] = idea
            result["目标时长"] = f"{duration_seconds} 秒"
            return {key: str(value) for key, value in result.items()}
        return {
            "原始创意": idea,
            "主题": "人在智能系统包围下重新确认自身选择的意义",
            "叙事尺度": "一个人 + 一个空间 + 一件小事",
            "视觉风格": visual_style,
            "目标时长": f"{duration_seconds} 秒",
            "合规约束": "仅使用原创或已授权素材；不复刻现有影视 IP、角色、台词或肖像。",
        }
