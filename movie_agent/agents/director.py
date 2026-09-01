"""Director agent: turns an idea into project-level creative constraints."""


class DirectorAgent:
    def plan(self, idea: str, duration_seconds: int, visual_style: str) -> dict[str, str]:
        return {
            "原始创意": idea,
            "主题": "人在智能系统包围下重新确认自身选择的意义",
            "叙事尺度": "一个人 + 一个空间 + 一件小事",
            "视觉风格": visual_style,
            "目标时长": f"{duration_seconds} 秒",
            "合规约束": "仅使用原创或已授权素材；不复刻现有影视 IP、角色、台词或肖像。",
        }
