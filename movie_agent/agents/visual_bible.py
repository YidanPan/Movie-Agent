"""Visual-bible agent: locks character, setting, style, and sound rules."""

from movie_agent.services.llm import CreativeLLM


class VisualBibleAgent:
    def __init__(self, llm: CreativeLLM | None = None) -> None:
        self.llm = llm

    def create(self, visual_style: str, brief: dict[str, str], script: dict[str, str]) -> dict[str, str]:
        if self.llm:
            result = self.llm.complete_json(
                "你是电影美术指导。为原创科幻短片制定可复用的一致性规范。",
                f"视觉风格：{visual_style}\n导演设定：{brief}\n剧本：{script.get('story', '')}\n"
                "返回键：角色卡、场景卡、风格卡、声音卡。",
            )
            return {key: str(value) for key, value in result.items()}
        return {
            "角色卡": "单一主角；中性、克制的服装；所有镜头保持同一发型、服饰轮廓和情绪状态。",
            "场景卡": "单一封闭近未来空间；少量可重复识别的控制台、窗面与冷色光源。",
            "风格卡": f"{visual_style}；低饱和、有限色板、慢镜头运动、以特写和空镜推进叙事。",
            "声音卡": "环境底噪、设备低鸣、克制配乐；避免模仿可识别人物音色。",
        }
