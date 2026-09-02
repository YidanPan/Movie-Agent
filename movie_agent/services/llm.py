"""OpenAI-compatible ModelScope API client for creative-agent text generation."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Protocol

from movie_agent.config import Settings


class CreativeLLM(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...


class ModelScopeLLM:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 90,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + "\n只返回合法 JSON，不要 Markdown 代码块或解释。"},
            ],
        }
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            request = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    result = json.load(response)
                content = result["choices"][0]["message"]["content"] or ""
                return _parse_json_object(content)
            except urllib.error.HTTPError as error:
                if error.code not in {408, 429} and not 500 <= error.code < 600:
                    raise RuntimeError(f"ModelScope API 请求失败（HTTP {error.code}）。") from error
                last_error = RuntimeError(f"ModelScope API 暂时不可用（HTTP {error.code}）。")
            except urllib.error.URLError as error:
                last_error = RuntimeError("无法连接 ModelScope API。")
                last_error.__cause__ = error
            except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
                last_error = ValueError("ModelScope API 未返回可用的结构化创作结果。")
                last_error.__cause__ = error
            if attempt < self.max_retries:
                time.sleep(0.6 * attempt)
        raise RuntimeError(f"ModelScope 文本生成在 {self.max_retries} 次尝试后仍未成功。") from last_error


def build_creative_llm(settings: Settings) -> CreativeLLM | None:
    if settings.model_provider == "mock":
        return None
    if settings.model_provider != "modelscope":
        raise ValueError(f"不支持的 MODEL_PROVIDER：{settings.model_provider}")
    if not settings.modelscope_api_key:
        raise ValueError("MODEL_PROVIDER=modelscope 时必须配置 MODELSCOPE_API_KEY。")
    return ModelScopeLLM(
        settings.modelscope_api_key,
        settings.modelscope_api_base,
        settings.modelscope_model,
        timeout_seconds=settings.modelscope_timeout_seconds,
        max_retries=settings.modelscope_max_retries,
    )


def _parse_json_object(content: str) -> dict[str, Any]:
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = normalized.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    if not normalized.startswith("{"):
        normalized = _extract_first_json_object(normalized)
    try:
        value = json.loads(normalized)
    except json.JSONDecodeError as error:
        raise ValueError("模型没有返回合法 JSON。") from error
    if not isinstance(value, dict):
        raise ValueError("模型返回的 JSON 顶层必须是对象。")
    return value


def _extract_first_json_object(content: str) -> str:
    """Extract a balanced JSON object when a model adds a short preamble/suffix."""
    start = content.find("{")
    if start < 0:
        return content
    depth = 0
    in_string = False
    escaped = False
    for index, character in enumerate(content[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return content[start : index + 1]
    return content
