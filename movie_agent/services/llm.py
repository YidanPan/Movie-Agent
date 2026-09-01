"""OpenAI-compatible ModelScope API client for creative-agent text generation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Protocol

from movie_agent.config import Settings


class CreativeLLM(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...


class ModelScopeLLM:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + "\n只返回合法 JSON，不要 Markdown 代码块或解释。"},
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"ModelScope API 请求失败（HTTP {error.code}）。") from error
        except urllib.error.URLError as error:
            raise RuntimeError("无法连接 ModelScope API。") from error
        try:
            content = result["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("ModelScope API 返回格式不符合预期。") from error
        return _parse_json_object(content)


def build_creative_llm(settings: Settings) -> CreativeLLM | None:
    if settings.model_provider == "mock":
        return None
    if settings.model_provider != "modelscope":
        raise ValueError(f"不支持的 MODEL_PROVIDER：{settings.model_provider}")
    if not settings.modelscope_api_key:
        raise ValueError("MODEL_PROVIDER=modelscope 时必须配置 MODELSCOPE_API_KEY。")
    return ModelScopeLLM(settings.modelscope_api_key, settings.modelscope_api_base, settings.modelscope_model)


def _parse_json_object(content: str) -> dict[str, Any]:
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = normalized.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(normalized)
    except json.JSONDecodeError as error:
        raise ValueError("模型没有返回合法 JSON。") from error
    if not isinstance(value, dict):
        raise ValueError("模型返回的 JSON 顶层必须是对象。")
    return value
