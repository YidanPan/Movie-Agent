import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from movie_agent.config import Settings
from movie_agent.services.media_generation import MediaTaskResult
from movie_agent.services.reference_generation import (
    ReferenceImageRequest,
    generate_reference_image,
    resolve_image_conditioning_inputs,
)
from movie_agent.storage.reference_bank import ReferenceBankStore


class _FakeProvider:
    name = "modelscope_image_generation"
    model = "test/image-model"

    def __init__(self, *_args, **_kwargs):
        pass

    def submit(self, *_args, **_kwargs):
        return MediaTaskResult(task_id="task-1", status="SUBMITTED")

    def wait_for_completion(self, *_args, **_kwargs):
        return MediaTaskResult(task_id="task-1", status="SUCCEED", output_urls=("https://example.test/ref.webp",))

    def download(self, _url, destination):
        destination = Path(destination)
        destination.write_bytes(b"real-image-output")
        return destination


class ReferenceGenerationTests(unittest.TestCase):
    def test_reference_generation_persists_pending_asset_and_task_metadata(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(
                "http://127.0.0.1:8188", 900, root / "workflows", 9071,
                root / "projects", True, modelscope_api_key="secret",
                image_generation_mode="modelscope", modelscope_image_model="test/image-model",
                outputs_dir=root / "outputs",
            )
            with patch("movie_agent.services.reference_generation.ModelScopeImageProvider", _FakeProvider):
                asset = generate_reference_image(
                    settings,
                    "film-test",
                    ReferenceImageRequest(kind="character", name="character-main", prompt="locked hero"),
                )
            self.assertFalse(asset.approved)
            self.assertEqual(asset.metadata["provider_task_id"], "task-1")
            self.assertTrue(Path(asset.path).is_file())

    def test_default_mock_image_mode_never_claims_a_reference(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings("http://127.0.0.1:8188", 900, root / "workflows", 9071, root / "projects", True, outputs_dir=root / "outputs")
            with self.assertRaisesRegex(RuntimeError, "IMAGE_GENERATION_MODE=modelscope"):
                generate_reference_image(settings, "film-test", ReferenceImageRequest(kind="scene", name="home", prompt="locked room"))

    def test_shot_keyframe_conditioning_defers_local_paths_without_fake_urls(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(
                "http://127.0.0.1:8188", 900, root / "workflows", 9071,
                root / "projects", True, outputs_dir=root / "outputs",
            )
            reference = root / "hero.webp"
            reference.write_bytes(b"approved-reference")
            ReferenceBankStore(settings.outputs_dir).register_file(
                "film-test", reference, kind="character", source="test", approved=True,
                character_id="hero", character_ids=["hero"],
            )
            resolved = resolve_image_conditioning_inputs(
                settings,
                "film-test",
                ReferenceImageRequest(
                    kind="shot_keyframe", name="shot-01", prompt="shot", character_id="hero"
                ),
            )
            self.assertEqual(resolved.status, "DEFERRED_UNSUPPORTED_BY_PROVIDER")
            self.assertEqual(len(resolved.approved_paths), 1)
            self.assertEqual(resolved.reference_urls, ())
            self.assertNotIn("localhost", str(resolved.metadata()))


if __name__ == "__main__":
    unittest.main()
