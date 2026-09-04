"""Visual-bible agent: locks character, setting, style, and sound rules."""

from movie_agent.services.llm import CreativeLLM


class VisualBibleAgent:
    def __init__(self, llm: CreativeLLM | None = None) -> None:
        self.llm = llm

    def create(self, visual_style: str, brief: dict[str, str], script: dict[str, str]) -> dict[str, str]:
        if self.llm:
            result = self.llm.complete_json(
                "You are a film art director. Create reusable consistency specifications for an original sci-fi short film. "
                "The lock cards enforce visual continuity across all shots: every generation prompt must respect these constraints. "
                "Return all cards and on-screen text guidance in English.",
                f"Visual style: {visual_style}\nDirector brief: {brief}\nStory: {script.get('story', '')}\n"
                "Return keys: character_card, scene_card, style_card, sound_card, "
                "character_lock, scene_lock, cinematography_lock, reference_seed.",
            )
            return {key: str(value) for key, value in result.items()}
        return {
            "character_card": "Single protagonist; neutral, restrained clothing; same hairstyle, silhouette, and emotional register across all shots.",
            "scene_card": "Single enclosed near-future space; a few recognisable consoles, window panels, and cool-toned light sources.",
            "style_card": f"{visual_style}; desaturated, limited palette, slow camera movement, close-ups and insert shots drive the narrative.",
            "sound_card": "Ambient room tone, low equipment hum, restrained score; avoid imitating recognisable character voices.",
            "character_lock": "Male, early 30s, short dark hair with slight wave, clean-shaven, lean build. Wears a dark charcoal utility jacket over a muted grey crew-neck shirt, black slim trousers, matte black boots. Distinguishing feature: small scar above left eyebrow. Same appearance in every shot.",
            "scene_lock": "Single enclosed near-future control room. Concrete-grey walls with recessed LED strip lighting (cool 5600K). A curved console with dim amber indicator lights runs along one wall. Large window panel showing a dark cityscape. Props: a handheld scanner, a coffee mug. No other characters present.",
            "cinematography_lock": "Shot on anamorphic-style 35mm equivalent. Shallow depth of field (f/2.0-2.8). Lens preference: 40mm and 65mm primes. Camera movement: slow dolly, subtle push-ins, no handheld shake. Framing: favour centre-weighted compositions with leading lines from console edges. Colour grade: desaturated teal shadows, warm amber highlights, crushed blacks. No lens flares.",
            "reference_seed": "42",
        }
