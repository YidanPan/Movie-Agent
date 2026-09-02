"""Writer agent: creates a concise screenplay and narration."""

from typing import Any

from movie_agent.services.llm import CreativeLLM


def _as_text(value: Any) -> str:
    """Flatten structured model output (list/dict) into readable prose."""

    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, (list, tuple)):
        parts = [_as_text(item) for item in value]
        return "；".join(part for part in parts if part)
    return str(value)


class WriterAgent:
    def __init__(self, llm: CreativeLLM | None = None) -> None:
        self.llm = llm

    def write(self, idea: str, brief: dict[str, str]) -> dict[str, str]:
        if self.llm:
            result = self.llm.complete_json(
                "你是科幻短片编剧。故事必须原创、简洁、可拆成 4–8 秒的镜头，避免现有影视 IP。",
                f"创意：{idea}\n导演设定：{brief}\n"
                "根据导演设定写一个 30–80 秒短片。返回键：story、narration。"
                "story 与 narration 都必须是连贯中文段落，不要返回列表或 JSON 片段。",
            )
            return {"story": _as_text(result["story"]), "narration": _as_text(result["narration"])}
        return {
            "story": (
                f"主角置身于一个安静而高度自动化的空间。{idea} "
                "他先把异常当成系统噪声，随后发现那个细小变化正迫使自己作出选择。"
                "结尾不解释所有答案，只留下一个与开场形成呼应的动作。"
            ),
            "narration": "未来最难被自动化的，也许不是工作，而是决定何时相信自己。",
        }
