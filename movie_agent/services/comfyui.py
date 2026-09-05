"""Safe client for submitting verified ComfyUI API workflow templates."""

from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ComfyUIError(RuntimeError):
    """A ComfyUI request failed or returned an unusable payload."""


@dataclass(frozen=True)
class WorkflowOverrides:
    """Only the values explicitly allowed to vary between generation jobs."""

    prompt: str
    seed: int
    duration_seconds: int | None = None


class ComfyUIClient:
    """Calls a local ComfyUI service without constructing node graphs dynamically."""

    def __init__(self, base_url: str, timeout_seconds: int = 900) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        try:
            self._get_json("/system_stats", timeout=5)
        except ComfyUIError:
            return False
        return True

    def submit(self, workflow: dict[str, Any]) -> str:
        response = self._post_json("/prompt", {"prompt": workflow})
        prompt_id = response.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyUIError("ComfyUI 响应中没有 prompt_id。")
        return prompt_id

    def queue(self) -> dict[str, Any]:
        return self._get_json("/queue")

    def history(self, prompt_id: str) -> dict[str, Any]:
        return self._get_json(f"/history/{prompt_id}")

    def wait_for_completion(self, prompt_id: str, poll_seconds: float = 2.0) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            history = self.history(prompt_id)
            if prompt_id in history:
                return history[prompt_id]
            time.sleep(poll_seconds)
        raise ComfyUIError(f"任务 {prompt_id} 在 {self.timeout_seconds} 秒内未完成。")

    def _get_json(self, path: str, timeout: int | None = None) -> dict[str, Any]:
        request = Request(f"{self.base_url}{path}", method="GET")
        return self._send(request, timeout or self.timeout_seconds)

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return self._send(request, self.timeout_seconds)

    @staticmethod
    def _send(request: Request, timeout: int) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=timeout) as response:  # nosec B310: endpoint is explicit config
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ComfyUIError(f"ComfyUI 请求失败：{error}") from error
        if not isinstance(payload, dict):
            raise ComfyUIError("ComfyUI 返回了非对象 JSON。")
        return payload


def load_verified_workflow(template_path: Path, overrides: WorkflowOverrides) -> dict[str, Any]:
    """Load an exported API workflow and change only manifest-approved input nodes.

    The template must contain a top-level `_movie_agent` manifest. It is removed
    before submission so ComfyUI only receives its own API workflow nodes.
    """

    raw = json.loads(template_path.read_text(encoding="utf-8"))
    manifest = raw.pop("_movie_agent", None)
    if not isinstance(manifest, dict):
        raise ComfyUIError("工作流缺少 _movie_agent 配置清单。")

    workflow = copy.deepcopy(raw)
    _set_input(
        workflow,
        manifest.get("prompt_node"),
        _manifest_field(manifest, "prompt_field", "text"),
        overrides.prompt,
    )
    _set_input(
        workflow,
        manifest.get("seed_node"),
        _manifest_field(manifest, "seed_field", "noise_seed"),
        overrides.seed,
    )
    if overrides.duration_seconds is not None and manifest.get("duration_node"):
        _set_input(
            workflow,
            manifest["duration_node"],
            _manifest_field(manifest, "duration_field", "duration_seconds"),
            _duration_value(manifest, overrides.duration_seconds),
        )
    return workflow


def _manifest_field(manifest: dict[str, Any], name: str, default: str) -> str:
    field = manifest.get(name, default)
    if not isinstance(field, str) or not field:
        raise ComfyUIError(f"工作流清单的 {name} 必须是非空字符串。")
    return field


def _duration_value(manifest: dict[str, Any], seconds: int) -> int:
    """Translate seconds only when a verified workflow explicitly requests it."""
    transform = manifest.get("duration_transform", "seconds")
    if transform == "seconds":
        return seconds
    if transform == "minimax_h3_frames":
        frames = max(5, round(seconds * 24))
        return frames + (5 - frames % 17) % 17
    raise ComfyUIError(f"不支持的工作流时长转换方式：{transform!r}。")


def _set_input(workflow: dict[str, Any], node_id: Any, field: str, value: Any) -> None:
    if not isinstance(node_id, str) or node_id not in workflow:
        raise ComfyUIError(f"工作流清单引用了不存在的节点：{node_id!r}。")
    node = workflow[node_id]
    if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
        raise ComfyUIError(f"节点 {node_id} 没有可修改的 inputs。")
    if field not in node["inputs"]:
        raise ComfyUIError(f"节点 {node_id} 不包含输入字段 {field!r}。")
    node["inputs"][field] = value
