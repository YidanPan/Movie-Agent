"""Writer agent: creates a concise screenplay and narration."""


class WriterAgent:
    def write(self, idea: str) -> dict[str, str]:
        return {
            "story": (
                f"主角置身于一个安静而高度自动化的空间。{idea} "
                "他先把异常当成系统噪声，随后发现那个细小变化正迫使自己作出选择。"
                "结尾不解释所有答案，只留下一个与开场形成呼应的动作。"
            ),
            "narration": "未来最难被自动化的，也许不是工作，而是决定何时相信自己。",
        }
