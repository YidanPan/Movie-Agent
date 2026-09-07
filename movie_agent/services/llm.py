"""OpenAI-compatible ModelScope API client for creative-agent text generation."""

from __future__ import annotations

import json
import base64
import logging
import mimetypes
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Protocol

from movie_agent.config import Settings

LOGGER = logging.getLogger(__name__)


class CreativeLLM(Protocol):
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]: ...


class ModelScopeAPIError(RuntimeError):
    """A safe, user-facing ModelScope failure with no credential material."""

    def __init__(self, message: str, *, error_type: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code


def require_fields(payload: dict[str, Any], fields: tuple[str, ...], *, agent: str) -> None:
    """Fail at the agent boundary with a useful schema error, never a KeyError."""

    missing = [field for field in fields if field not in payload or payload[field] is None]
    if missing:
        raise ValueError(f"{agent} 模型输出缺少必需字段：{', '.join(missing)}。")


class ModelScopeLLM:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 90,
        max_retries: int = 2,
        max_tokens: int = 8192,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(1, max_retries)
        self.max_tokens = max(1024, max_tokens)
        self.request_count = 0
        self.last_request: dict[str, Any] = {}

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "temperature": 0.7,
            "max_tokens": self.max_tokens,
            "extra_body": {"enable_thinking": False},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + "\n只返回合法 JSON，不要 Markdown 代码块或解释。"},
            ],
        }
        return self._complete_payload(payload, agent=_infer_agent(system_prompt))

    def complete_vision_json(
        self,
        system_prompt: str,
        user_prompt: str,
        image_paths: list[Path],
    ) -> dict[str, Any]:
        if not image_paths:
            raise ValueError("视觉审核至少需要一张关键帧。")
        content: list[dict[str, Any]] = [
            {"type": "text", "text": user_prompt + "\n只返回合法 JSON，不要 Markdown 代码块或解释。"}
        ]
        for image_path in image_paths:
            mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
            encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                }
            )
        payload = {
            "model": self.model,
            "temperature": 0.1,
            "max_tokens": self.max_tokens,
            "extra_body": {"enable_thinking": False},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
        }
        return self._complete_payload(payload, agent=_infer_agent(system_prompt, default="vision_reviewer"))

    def _complete_payload(self, payload: dict[str, Any], *, agent: str = "unknown") -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            request = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            self.request_count += 1
            started = time.monotonic()
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                    result = json.load(response)
                    response_request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
                if not isinstance(result, dict):
                    raise ValueError("API response must be a JSON object")
                choices = result.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise ValueError("API response contains no choices")
                message = choices[0].get("message") if isinstance(choices[0], dict) else None
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("API response contains empty message content")
                parsed = _parse_json_object(content)
                self.last_request = {
                    "agent": agent,
                    "status": "success",
                    "latency_ms": round((time.monotonic() - started) * 1000),
                    "request_id": response_request_id,
                    "usage": result.get("usage") if isinstance(result.get("usage"), dict) else None,
                }
                LOGGER.info(
                    "[LLM] provider=modelscope model=%s agent=%s attempt=%s status=success latency_ms=%s output_valid_json=true%s",
                    self.model,
                    agent,
                    attempt,
                    self.last_request["latency_ms"],
                    f" request_id={response_request_id}" if response_request_id else "",
                )
                return parsed
            except urllib.error.HTTPError as error:
                error_type, message = _http_error_details(error.code)
                last_error = ModelScopeAPIError(message, error_type=error_type, status_code=error.code)
                self._log_failure(agent, attempt, started, error_type)
                if not _retryable_http_status(error.code):
                    raise last_error from error
            except urllib.error.URLError as error:
                error_type = "timeout" if _is_timeout_error(error) else "upstream_unavailable"
                message = "ModelScope API 请求超时。" if error_type == "timeout" else "无法连接 ModelScope API。"
                last_error = ModelScopeAPIError(message, error_type=error_type)
                self._log_failure(agent, attempt, started, error_type)
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                last_error = ModelScopeAPIError(
                    "ModelScope API 未返回可用的结构化创作结果（JSON 顶层必须是对象且包含非空 choices.content）。",
                    error_type="invalid_json",
                )
                self._log_failure(agent, attempt, started, "invalid_json")
                raise last_error from error
            except (socket.timeout, TimeoutError) as error:
                last_error = ModelScopeAPIError("ModelScope API 请求超时。", error_type="timeout")
                self._log_failure(agent, attempt, started, "timeout")
            if attempt < self.max_retries:
                time.sleep(0.6 * attempt)
        error_type = getattr(last_error, "error_type", "upstream_unavailable")
        self._log_failure(agent, self.max_retries, started, error_type)
        raise ModelScopeAPIError(
            f"ModelScope 文本生成在 {self.max_retries} 次尝试后仍未成功（{error_type}）。",
            error_type=error_type,
        ) from last_error

    def _log_failure(self, agent: str, attempt: int, started: float, error_type: str) -> None:
        self.last_request = {
            "agent": agent,
            "status": "failed",
            "latency_ms": round((time.monotonic() - started) * 1000),
            "error_type": error_type,
        }
        LOGGER.warning(
            "[LLM] provider=modelscope model=%s agent=%s attempt=%s status=failed error_type=%s latency_ms=%s",
            self.model,
            agent,
            attempt,
            error_type,
            self.last_request["latency_ms"],
        )


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
        max_tokens=settings.modelscope_max_tokens,
    )


def build_vision_llm(settings: Settings) -> ModelScopeLLM | None:
    """Return a vision-capable client only when the deployment explicitly opts in."""
    if settings.model_provider != "modelscope" or not settings.modelscope_api_key:
        return None
    if not settings.modelscope_vision_model:
        return None
    return ModelScopeLLM(
        settings.modelscope_api_key,
        settings.modelscope_api_base,
        settings.modelscope_vision_model,
        timeout_seconds=settings.modelscope_timeout_seconds,
        max_retries=settings.modelscope_max_retries,
        max_tokens=settings.modelscope_max_tokens,
    )


def _parse_json_object(content: str) -> dict[str, Any]:
    normalized = str(content or "").strip()
    if normalized.startswith("```"):
        lines = normalized.splitlines()
        if lines:
            lines = lines[1:]
        closing = next((index for index, line in enumerate(lines) if line.strip().startswith("```")), None)
        normalized = "\n".join(lines[:closing] if closing is not None else lines).strip()
    candidate = _extract_first_json_object(normalized)
    if candidate != normalized:
        normalized = candidate
    try:
        value = json.loads(normalized)
    except json.JSONDecodeError as error:
        raise ValueError("模型没有返回合法 JSON。") from error
    if not isinstance(value, dict):
        raise ValueError("模型返回的 JSON 顶层必须是对象。")
    return value


def _infer_agent(system_prompt: str, *, default: str = "unknown") -> str:
    text = str(system_prompt).lower()
    for token, agent in (
        ("chief director", "director"),
        ("screenwriter", "writer"),
        ("script supervisor", "story_supervisor"),
        ("story structure analyst", "story_beats"),
        ("story-world analyst", "story_world"),
        ("art director", "visual_bible"),
        ("storyboard artist", "storyboard"),
        ("repairing one flagged storyboard shot", "storyboard_repair"),
        ("copyright and originality reviewer", "copyright_reviewer"),
        ("visual quality inspector", "vision_reviewer"),
    ):
        if token in text:
            return agent
    return default


def _retryable_http_status(status_code: int) -> bool:
    return status_code in {408, 429} or 500 <= status_code < 600


def _http_error_details(status_code: int) -> tuple[str, str]:
    if status_code == 401:
        return "authentication", "ModelScope API 认证失败（HTTP 401）；请检查 MODELSCOPE_API_KEY。"
    if status_code == 403:
        return "permission", "ModelScope API 拒绝访问（HTTP 403）；请检查 Token 权限或模型权限。"
    if status_code == 404:
        return "invalid_model_or_endpoint", "ModelScope API 找不到模型或接口（HTTP 404）；请检查 MODELSCOPE_MODEL 和 MODELSCOPE_API_BASE。"
    if status_code == 408:
        return "timeout", "ModelScope API 请求超时（HTTP 408）。"
    if status_code == 429:
        return "rate_limit", "ModelScope API 触发限流（HTTP 429）。"
    if 500 <= status_code < 600:
        return "upstream_unavailable", f"ModelScope API 上游暂时不可用（HTTP {status_code}）。"
    return "http_error", f"ModelScope API 请求失败（HTTP {status_code}）。"


def _is_timeout_error(error: urllib.error.URLError) -> bool:
    reason = getattr(error, "reason", None)
    return isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in str(reason).lower()


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
