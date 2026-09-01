"""Writer agent: creates a concise screenplay and narration."""

from movie_agent.services.llm import CreativeLLM


class WriterAgent:
    def __init__(self, llm: CreativeLLM | None = None) -> None:
        self.llm = llm

    def write(self, idea: str) -> dict[str, str]:
        if self.llm:
            result = self.llm.complete_json(
                "你是科幻短片编剧。故事必须原创、简洁、可拆成 4–8 秒的镜头，避免现有影视 IP。",
                f"根据这个创意写一个 30–80 秒短片。创意：{idea}\n返回键：story、narration。",
            )
            return {"story": str(result["story"]), "narration": str(result["narration"])}
        return {
            "story": (
                f"主角置身于一个安静而高度自动化的空间。{idea} "
                "他先把异常当成系统噪声，随后发现那个细小变化正迫使自己作出选择。"
                "结尾不解释所有答案，只留下一个与开场形成呼应的动作。"
            ),
            "narration": "未来最难被自动化的，也许不是工作，而是决定何时相信自己。",
        }
