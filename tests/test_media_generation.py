import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from movie_agent.services.media_generation import ModelScopeImageProvider


class _Handler(BaseHTTPRequestHandler):
    calls = []

    def do_POST(self):  # noqa: N802 - stdlib handler API
        self.calls.append((self.command, self.path))
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"task_id": "img-task-1"}).encode())

    def do_GET(self):  # noqa: N802 - stdlib handler API
        self.calls.append((self.command, self.path))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"task_status": "SUCCEED", "output_images": ["https://example.test/image.webp"]}).encode())

    def log_message(self, *_args):
        return


class MediaGenerationTests(unittest.TestCase):
    def setUp(self):
        _Handler.calls = []
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)

    def test_modelscope_image_provider_uses_submit_poll_contract(self):
        provider = ModelScopeImageProvider(
            "secret-is-not-logged",
            base_url=f"http://127.0.0.1:{self.server.server_port}",
            model="test/image-model",
            poll_seconds=0,
            max_polls=1,
        )
        submitted = provider.submit("locked character reference", seed=42)
        completed = provider.wait_for_completion(submitted.task_id)

        self.assertEqual(submitted.task_id, "img-task-1")
        self.assertEqual(completed.status, "SUCCEED")
        self.assertEqual(completed.output_urls, ("https://example.test/image.webp",))
        self.assertEqual([path for _method, path in _Handler.calls], ["/images/generations", "/tasks/img-task-1"])

    def test_download_persists_output_without_exposing_provider_credentials(self):
        class ImageHandler(_Handler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "image/webp")
                self.end_headers()
                self.wfile.write(b"image-bytes")

        old = self.server.RequestHandlerClass
        self.server.RequestHandlerClass = ImageHandler
        try:
            provider = ModelScopeImageProvider(
                "secret-token",
                base_url=f"http://127.0.0.1:{self.server.server_port}",
                model="test/image-model",
            )
            with TemporaryDirectory() as directory:
                destination = provider.download(
                    f"http://127.0.0.1:{self.server.server_port}/image.webp",
                    Path(directory) / "references" / "character.webp",
                )
                self.assertEqual(destination.read_bytes(), b"image-bytes")
        finally:
            self.server.RequestHandlerClass = old


if __name__ == "__main__":
    unittest.main()
