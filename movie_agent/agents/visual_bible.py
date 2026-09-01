"""Visual-bible agent: locks character, setting, style, and sound rules."""


class VisualBibleAgent:
    def create(self, visual_style: str) -> dict[str, str]:
        return {
            "角色卡": "单一主角；中性、克制的服装；所有镜头保持同一发型、服饰轮廓和情绪状态。",
            "场景卡": "单一封闭近未来空间；少量可重复识别的控制台、窗面与冷色光源。",
            "风格卡": f"{visual_style}；低饱和、有限色板、慢镜头运动、以特写和空镜推进叙事。",
            "声音卡": "环境底噪、设备低鸣、克制配乐；避免模仿可识别人物音色。",
        }
