"""Director agent: turns an idea into project-level creative constraints."""

from movie_agent.services.llm import CreativeLLM


class DirectorAgent:
    def __init__(self, llm: CreativeLLM | None = None) -> None:
        self.llm = llm

    def plan(self, idea: str, duration_seconds: int, visual_style: str) -> dict[str, str]:
        if self.llm:
            result = self.llm.complete_json(
                "You are the chief director of an original sci-fi short film. "
                "Insist on originality, single character / single space / single event, avoid existing film/TV IP.",
                (
                    f"Idea: {idea}\nTarget duration: {duration_seconds} seconds\nVisual style: {visual_style}\n"
                    "Return keys: theme, narrative_scale, visual_style, director_intent, compliance_constraints."
                ),
            )
            result["original_idea"] = idea
            result["target_duration"] = f"{duration_seconds} seconds"
            return {key: str(value) for key, value in result.items()}
        return {
            "original_idea": idea,
            "theme": "A person reconfirms the meaning of their own choice within an intelligent system",
            "narrative_scale": "One character + one space + one small event",
            "visual_style": visual_style,
            "target_duration": f"{duration_seconds} seconds",
            "compliance_constraints": "Use only original or licensed material; do not replicate existing film/TV IP, characters, lines, or likenesses.",
        }
