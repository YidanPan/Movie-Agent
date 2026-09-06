"""Canonical entities shared by screenplay, visual, storyboard, and QC stages."""

from __future__ import annotations

import re
from typing import Any, Iterable

from movie_agent.services.llm import CreativeLLM


ENTITY_KINDS = ("characters", "scenes", "props")
_ID_RE = re.compile(r"[^a-z0-9]+")


def canonical_entity_id(value: Any, *, fallback: str, index: int) -> str:
    """Return a stable, lower-kebab-free ASCII identifier for an entity."""

    text = str(value or "").strip().lower()
    text = _ID_RE.sub("_", text).strip("_")
    return text or f"{fallback}_{index + 1:02d}"


def _as_entity_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        result: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, dict):
                result.append({"id": key, **item})
            else:
                result.append({"id": key, "name": item})
        return result
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _normalise_entities(value: Any, *, kind: str) -> dict[str, dict[str, Any]]:
    prefix = kind[:-1] if kind.endswith("s") else kind
    entities: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(_as_entity_list(value)):
        name = str(raw.get("name") or raw.get("label") or raw.get("id") or "").strip()
        entity_id = canonical_entity_id(
            raw.get("character_id") or raw.get("scene_id") or raw.get("prop_id") or raw.get("id") or name,
            fallback=prefix,
            index=index,
        )
        if entity_id in entities:
            entity_id = f"{entity_id}_{index + 1:02d}"
        item = dict(raw)
        item.pop("id", None)
        item["name"] = name or entity_id.replace("_", " ").title()
        item[f"{prefix}_id"] = entity_id
        item["entity_type"] = prefix
        entities[entity_id] = item
    return entities


def normalise_story_world(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize list/map model output while preserving descriptive fields."""

    payload = raw or {}
    return {
        "schema_version": max(1, int(payload.get("schema_version") or 1)),
        "characters": _normalise_entities(payload.get("characters"), kind="characters"),
        "scenes": _normalise_entities(payload.get("scenes"), kind="scenes"),
        "props": _normalise_entities(payload.get("props"), kind="props"),
    }


def entity_ids(world: dict[str, Any] | None, kind: str) -> set[str]:
    value = (world or {}).get(kind) or {}
    if isinstance(value, dict):
        return {str(key) for key in value}
    return {str(item.get(f"{kind[:-1]}_id") or item.get("id")) for item in value if isinstance(item, dict)}


def world_entities(world: dict[str, Any] | None, kind: str) -> list[dict[str, Any]]:
    value = (world or {}).get(kind) or {}
    if isinstance(value, dict):
        return [dict(item, **{f"{kind[:-1]}_id": key}) for key, item in value.items() if isinstance(item, dict)]
    return [item for item in value if isinstance(item, dict)]


def story_world_prompt(world: dict[str, Any] | None) -> str:
    """Format only canonical IDs for downstream model prompts."""

    return (
        "Available canonical characters: " + ", ".join(sorted(entity_ids(world, "characters")) or ["none"]) + "\n"
        "Available canonical scenes: " + ", ".join(sorted(entity_ids(world, "scenes")) or ["none"]) + "\n"
        "Available canonical props: " + ", ".join(sorted(entity_ids(world, "props")) or ["none"])
    )


def validate_story_world_references(
    value: Iterable[dict[str, Any]] | dict[str, Any] | None,
    world: dict[str, Any] | None,
) -> dict[str, list[str]]:
    """Find unknown scene/character/prop IDs without silently falling back."""

    if isinstance(value, dict):
        items: list[dict[str, Any]] = []
        for key in ("beats", "shots"):
            nested = value.get(key)
            if isinstance(nested, list):
                items.extend(item for item in nested if isinstance(item, dict))
    else:
        items = [item for item in (value or []) if isinstance(item, dict)]
    known_characters = entity_ids(world, "characters")
    known_scenes = entity_ids(world, "scenes")
    known_props = entity_ids(world, "props")
    unknown_characters: set[str] = set()
    unknown_scenes: set[str] = set()
    unknown_props: set[str] = set()
    for item in items:
        scene_id = str(item.get("scene_id") or "").strip()
        if scene_id and scene_id not in known_scenes:
            unknown_scenes.add(scene_id)
        characters = item.get("character_ids") or []
        if isinstance(characters, str):
            characters = [part.strip() for part in characters.split(",") if part.strip()]
        unknown_characters.update(str(char) for char in characters if str(char) not in known_characters)
        props = item.get("prop_ids") or []
        if isinstance(props, str):
            props = [part.strip() for part in props.split(",") if part.strip()]
        unknown_props.update(str(prop) for prop in props if str(prop) not in known_props)
    return {
        "unknown_characters": sorted(unknown_characters),
        "unknown_scenes": sorted(unknown_scenes),
        "unknown_props": sorted(unknown_props),
    }


def extract_story_world(
    idea: str,
    brief: dict[str, Any],
    script: dict[str, Any],
    llm: CreativeLLM | None = None,
) -> dict[str, Any]:
    """Extract what exists in the film, separate from how it looks."""

    if llm:
        result = llm.complete_json(
            "You are a story-world analyst. Extract only canonical entities that exist in this original short film. "
            "Do not design visual style. IDs must be stable lowercase snake_case identifiers and must be reused exactly downstream. "
            "Return JSON only.",
            f"Idea: {idea}\nBrief: {brief}\nScreenplay: {script.get('story', '')}\nOutline: {script.get('outline', '')}\n"
            "Return {characters:[{character_id,name,role}], scenes:[{scene_id,name,story_role}], "
            "props:[{prop_id,name,story_role}]}. Include only named or narratively important entities.",
        )
        return normalise_story_world(result)

    # Mock mode keeps a deliberately small, stable world. Descriptive locks
    # belong to Visual Bible, not this registry.
    return normalise_story_world(
        {
            "characters": [{"character_id": "protagonist", "name": "Protagonist", "role": "protagonist"}],
            "scenes": [{"scene_id": "primary", "name": "Primary Story Space", "story_role": "main setting"}],
            "props": [],
        }
    )


__all__ = [
    "ENTITY_KINDS",
    "canonical_entity_id",
    "entity_ids",
    "extract_story_world",
    "normalise_story_world",
    "story_world_prompt",
    "validate_story_world_references",
    "world_entities",
]
