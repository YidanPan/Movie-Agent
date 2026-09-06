"""Visual-bible agent: locks character, setting, style, and sound rules."""

import re
from typing import Any

from movie_agent.services.llm import CreativeLLM
from movie_agent.services.story_world import story_world_prompt, world_entities, normalise_story_world


UI_PALETTE_FALLBACK = {
    "dominant": "#6B665B",
    "accent": "#A88752",
    "temperature": "neutral",
    "luminance": 0.5,
}
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def validate_ui_palette(value: Any) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {"dominant": [], "accent": [], "temperature": [], "luminance": []}
    if not isinstance(value, dict):
        return {"palette": ["ui_palette must be an object"]}
    for key in ("dominant", "accent"):
        if not isinstance(value.get(key), str) or not _HEX_COLOR.fullmatch(value[key].strip()):
            errors[key].append("must be a #RRGGBB color")
    if str(value.get("temperature", "")).lower() not in {"warm", "neutral", "cool"}:
        errors["temperature"].append("must be warm, neutral, or cool")
    try:
        luminance = float(value.get("luminance"))
        if not 0 <= luminance <= 1:
            errors["luminance"].append("must be between 0 and 1")
    except (TypeError, ValueError):
        errors["luminance"].append("must be between 0 and 1")
    return {key: value for key, value in errors.items() if value}


def normalise_ui_palette(value: Any) -> dict[str, Any]:
    """Return a safe machine-readable palette; malformed model output is neutral."""

    if validate_ui_palette(value):
        return dict(UI_PALETTE_FALLBACK)
    return {
        "dominant": str(value["dominant"]).upper(),
        "accent": str(value["accent"]).upper(),
        "temperature": str(value["temperature"]).lower(),
        "luminance": round(float(value["luminance"]), 3),
    }


class VisualBibleAgent:
    def __init__(self, llm: CreativeLLM | None = None) -> None:
        self.llm = llm

    def create(
        self,
        visual_style: str,
        brief: dict[str, str],
        script: dict[str, str],
        story_world: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        world = normalise_story_world(story_world) if story_world else None
        if self.llm:
            result = self.llm.complete_json(
                "You are a film art director. Create reusable consistency specifications for an original sci-fi short film. "
                "The lock cards enforce visual continuity across all shots: every generation prompt must respect these constraints. "
                "Return all cards and on-screen text guidance in English. "
                "The structured characters and scenes are authoritative selectors, not decorative summaries. "
                "Give every character a stable character_id and every scene a stable scene_id so generation and QC can resolve only the active context.",
                f"Visual style: {visual_style}\nDirector brief: {brief}\nStory: {script.get('story', '')}\n"
                f"{story_world_prompt(world)}\n"
                "Return only JSON with keys: character_card, scene_card, style_card, sound_card, "
                "character_lock, scene_lock, prop_lock, cinematography_lock, reference_seed, "
                "characters, scenes, props, cinematography. "
                "characters must be an array of objects with character_id, name, role, appearance_lock, face_lock, hair_lock, costume_lock, silhouette_lock, prop_lock. "
                "Use exactly the provided character IDs and include every provided character. "
                "scenes must be an array of objects with scene_id, name, environment_lock, architecture_lock, lighting_lock, palette_lock, prop_lock, and optional ui_palette. "
                "ui_palette must be {dominant:#RRGGBB, accent:#RRGGBB, temperature:warm|neutral|cool, luminance:0..1}. "
                "props must be an array of objects with prop_id, name, appearance_lock, material_lock, color_lock, state_rules, screen_language. "
                "Use exactly the provided scene IDs and include every provided scene. "
                "cinematography must be an object with lens_language, camera_motion, composition, film_texture, color_pipeline. "
                "Do not omit structured fields; use an empty string only when a field is genuinely not applicable.",
            )
            structured_keys = {"characters", "scenes", "props", "cinematography"}
            output = {
                key: value if key in structured_keys and isinstance(value, (list, dict)) else str(value)
                for key, value in result.items()
            }
            if world:
                output["characters"] = self._bind_entities(output.get("characters"), world, "characters")
                output["scenes"] = self._bind_entities(output.get("scenes"), world, "scenes")
                output["props"] = self._bind_entities(output.get("props"), world, "props")
                output["scenes"] = [
                    {**scene, "ui_palette": normalise_ui_palette(scene.get("ui_palette"))}
                    for scene in output["scenes"]
                ]
                missing = validate_visual_bible_bindings(output, world)
                if any(missing.values()):
                    raise ValueError(f"VISUAL_BIBLE_REVIEW_REQUIRED: {missing}")
            return output
        character_lock = "Male, early 30s, short dark hair with slight wave, clean-shaven, lean build. Wears a dark charcoal utility jacket over a muted grey crew-neck shirt, black slim trousers, matte black boots. Distinguishing feature: small scar above left eyebrow. Same appearance in every shot."
        scene_lock = "Single enclosed near-future control room. Concrete-grey walls with recessed LED strip lighting (cool 5600K). A curved console with dim amber indicator lights runs along one wall. Large window panel showing a dark cityscape. Props: a handheld scanner, a coffee mug. No other characters present."
        cinematography_lock = "Shot on anamorphic-style 35mm equivalent. Shallow depth of field (f/2.0-2.8). Lens preference: 40mm and 65mm primes. Camera movement: slow dolly, subtle push-ins, no handheld shake. Framing: favour centre-weighted compositions with leading lines from console edges. Colour grade: desaturated teal shadows, warm amber highlights, crushed blacks. No lens flares."
        output = {
            "character_card": "Single protagonist; neutral, restrained clothing; same hairstyle, silhouette, and emotional register across all shots.",
            "scene_card": "Single enclosed near-future space; a few recognisable consoles, window panels, and cool-toned light sources.",
            "style_card": f"{visual_style}; desaturated, limited palette, slow camera movement, close-ups and insert shots drive the narrative.",
            "sound_card": "Ambient room tone, low equipment hum, restrained score; avoid imitating recognisable character voices.",
            "character_lock": character_lock,
            "scene_lock": scene_lock,
            "prop_lock": "Small set of story-critical props; appearance, material, colour, and state remain stable unless a shot delta changes them.",
            "cinematography_lock": cinematography_lock,
            "characters": [{"character_id": "protagonist", "role": "hero", "lock": character_lock}],
            "scenes": [{"scene_id": "primary", "role": "hero_environment", "lock": scene_lock, "ui_palette": dict(UI_PALETTE_FALLBACK)}],
            "props": [],
            "cinematography": {"lock": cinematography_lock, "palette": "desaturated teal shadows, warm amber highlights"},
            "reference_seed": "42",
        }
        if world:
            output["characters"] = [
                {
                    **entity,
                    "character_id": entity.get("character_id"),
                    "appearance_lock": entity.get("appearance_lock") or "Stable original character silhouette and proportions.",
                    "face_lock": entity.get("face_lock") or "Stable facial structure and identifying feature.",
                    "hair_lock": entity.get("hair_lock") or "Stable hairstyle and hair colour.",
                    "costume_lock": entity.get("costume_lock") or "Stable costume silhouette and material palette.",
                    "silhouette_lock": entity.get("silhouette_lock") or "Readable, stable silhouette in every shot.",
                    "lock": entity.get("lock") or "Stable original character identity, face, hair, costume, and silhouette.",
                }
                for entity in world_entities(world, "characters")
            ]
            output["scenes"] = [
                {
                    **entity,
                    "scene_id": entity.get("scene_id"),
                    "environment_lock": entity.get("environment_lock") or "Stable original environment geometry and spatial layout.",
                    "architecture_lock": entity.get("architecture_lock") or "Stable architecture, entrances, and major planes.",
                    "lighting_lock": entity.get("lighting_lock") or "Stable key light direction and practical sources.",
                    "palette_lock": entity.get("palette_lock") or "Stable scene palette with restrained contrast.",
                    "ui_palette": normalise_ui_palette(entity.get("ui_palette")),
                    "lock": entity.get("lock") or "Stable original environment geometry, lighting, and palette.",
                }
                for entity in world_entities(world, "scenes")
            ]
            output["props"] = [
                {
                    **entity,
                    "prop_id": entity.get("prop_id"),
                    "appearance_lock": entity.get("appearance_lock") or "Stable recognisable shape and markings.",
                    "material_lock": entity.get("material_lock") or "Stable material and surface response.",
                    "color_lock": entity.get("color_lock") or "Stable restrained colour treatment.",
                    "state_rules": entity.get("state_rules") or "State changes only when the shot delta explicitly changes it.",
                    "screen_language": entity.get("screen_language") or "English only.",
                    "lock": entity.get("lock") or "Stable original prop appearance, material, colour, and state rules.",
                }
                for entity in world_entities(world, "props")
            ]
        validate = validate_visual_bible_bindings(output, world or {"characters": {}, "scenes": {}, "props": {}})
        if any(validate.values()):
            raise ValueError(f"VISUAL_BIBLE_REVIEW_REQUIRED: {validate}")
        return output

    @staticmethod
    def _bind_entities(value: Any, world: dict[str, Any], kind: str) -> list[dict[str, Any]]:
        prefix = kind[:-1]
        source = value if isinstance(value, list) else []
        by_id = {str(item.get(f"{prefix}_id") or item.get("id")): item for item in source if isinstance(item, dict)}
        result: list[dict[str, Any]] = []
        for entity in world_entities(world, kind):
            entity_id = str(entity.get(f"{prefix}_id") or "")
            result.append({**(by_id.get(entity_id) or {}), **entity, f"{prefix}_id": entity_id})
        return result


def validate_visual_bible_bindings(visual_bible: dict[str, Any], story_world: dict[str, Any]) -> dict[str, list[str]]:
    """Report canonical world entities that do not have usable visual locks."""

    missing: dict[str, list[str]] = {"missing_character_locks": [], "missing_scene_locks": [], "missing_prop_locks": []}
    for kind, lock_fields, output_key in (
        ("characters", ("appearance_lock", "face_lock", "costume_lock", "lock"), "missing_character_locks"),
        ("scenes", ("environment_lock", "architecture_lock", "lighting_lock", "palette_lock", "lock"), "missing_scene_locks"),
        ("props", ("appearance_lock", "material_lock", "color_lock", "state_rules", "lock"), "missing_prop_locks"),
    ):
        prefix = kind[:-1]
        available = {str(item.get(f"{prefix}_id")): item for item in (visual_bible.get(kind) or []) if isinstance(item, dict)}
        for entity in world_entities(story_world, kind):
            entity_id = str(entity.get(f"{prefix}_id") or "")
            value = available.get(entity_id) or {}
            if not any(str(value.get(field) or "").strip() for field in lock_fields):
                missing[output_key].append(entity_id)
    return missing


__all__ = [
    "UI_PALETTE_FALLBACK",
    "VisualBibleAgent",
    "normalise_ui_palette",
    "validate_ui_palette",
    "validate_visual_bible_bindings",
]
