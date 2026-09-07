from __future__ import annotations

import io
import json
import socket
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from movie_agent.services.llm import ModelScopeAPIError, ModelScopeLLM, _parse_json_object


class _Response:
    def __init__(self, payload: dict, headers: dict[str, str] | None = None) -> None:
        self._body = json.dumps(payload).encode("utf-8")
        self.headers = headers or {}

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, *args: object) -> bytes:
        return self._body


def _success(content: str = '{"status":"ok"}') -> _Response:
    return _Response(
        {
            "model": "test-model",
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 3},
        },
        {"x-request-id": "req-test"},
    )


class ModelScopeLLMTests(unittest.TestCase):
    def make_client(self, retries: int = 2) -> ModelScopeLLM:
        return ModelScopeLLM("test-token", "https://example.test/v1", "test-model", max_retries=retries)

    def test_valid_response_and_observability(self) -> None:
        client = self.make_client()
        with patch("movie_agent.services.llm.urllib.request.urlopen", return_value=_success()):
            self.assertEqual(client.complete_json("You are a chief director.", "Return JSON"), {"status": "ok"})
        self.assertEqual(client.request_count, 1)
        self.assertEqual(client.last_request["status"], "success")
        self.assertEqual(client.last_request["request_id"], "req-test")
        self.assertEqual(client.last_request["usage"]["completion_tokens"], 3)

    def test_fenced_and_explanatory_json_is_parsed(self) -> None:
        self.assertEqual(_parse_json_object('Here is the result:\n```json\n{"status":"ok"}\n```\nDone.'), {"status": "ok"})
        self.assertEqual(_parse_json_object('{"status":"ok"}\nExplanation after JSON.'), {"status": "ok"})

    def test_malformed_json_is_a_non_retryable_structured_error(self) -> None:
        client = self.make_client(retries=3)
        with patch("movie_agent.services.llm.urllib.request.urlopen", return_value=_success("not json")):
            with self.assertRaises(ModelScopeAPIError) as raised:
                client.complete_json("screenwriter", "Return JSON")
        self.assertEqual(raised.exception.error_type, "invalid_json")
        self.assertEqual(client.request_count, 1)

    def test_auth_and_model_errors_are_not_retried(self) -> None:
        for status, error_type in ((401, "authentication"), (403, "permission"), (404, "invalid_model_or_endpoint")):
            client = self.make_client(retries=3)
            error = HTTPError("https://example.test", status, "failure", {}, io.BytesIO(b"{}"))
            with patch("movie_agent.services.llm.urllib.request.urlopen", side_effect=error):
                with self.assertRaises(ModelScopeAPIError) as raised:
                    client.complete_json("screenwriter", "Return JSON")
            self.assertEqual(raised.exception.error_type, error_type)
            self.assertEqual(client.request_count, 1)

    def test_rate_limit_and_upstream_errors_are_finitely_retried(self) -> None:
        for status, error_type in ((429, "rate_limit"), (500, "upstream_unavailable")):
            client = self.make_client(retries=2)
            error = HTTPError("https://example.test", status, "failure", {}, io.BytesIO(b"{}"))
            with patch("movie_agent.services.llm.urllib.request.urlopen", side_effect=[error, error]), patch("movie_agent.services.llm.time.sleep"):
                with self.assertRaises(ModelScopeAPIError) as raised:
                    client.complete_json("screenwriter", "Return JSON")
            self.assertEqual(raised.exception.error_type, error_type)
            self.assertEqual(client.request_count, 2)

    def test_timeout_is_retried_and_is_not_reported_as_auth_error(self) -> None:
        client = self.make_client(retries=2)
        timeout = URLError(socket.timeout("timed out"))
        with patch("movie_agent.services.llm.urllib.request.urlopen", side_effect=[timeout, _success()]), patch("movie_agent.services.llm.time.sleep"):
            self.assertEqual(client.complete_json("storyboard artist", "Return JSON"), {"status": "ok"})
        self.assertEqual(client.request_count, 2)

    def test_empty_choices_are_reported_without_key_error(self) -> None:
        client = self.make_client()
        with patch("movie_agent.services.llm.urllib.request.urlopen", return_value=_Response({"choices": []})):
            with self.assertRaises(ModelScopeAPIError) as raised:
                client.complete_json("screenwriter", "Return JSON")
        self.assertEqual(raised.exception.error_type, "invalid_json")


if __name__ == "__main__":
    unittest.main()
