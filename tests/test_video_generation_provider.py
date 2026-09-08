from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import json

from movie_agent.agents.generation import GenerationAgent
from movie_agent.config import Settings
from movie_agent.models import Shot
from movie_agent.services.comfyui import ComfyUIError
from movie_agent.services.video_generation import (
    ComfyUIVideoProvider,
    MockVideoProvider,
    VideoGenerationError,
    build_video_provider,
)


def _settings(root: Path, mode: str = "mock") -> Settings:
    return Settings(
        "http://127.0.0.1:8188",
        900,
        root / "workflows",
        9071,
        root / "projects",
        True,
        outputs_dir=root / "outputs",
        video_generation_mode=mode,
    )


def test_factory_selects_explicit_provider_and_mock_is_fail_closed():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        assert isinstance(build_video_provider(_settings(root)), MockVideoProvider)
        with pytest.raises(VideoGenerationError, match="does not create media"):
            build_video_provider(_settings(root)).generate()


def test_comfy_provider_returns_normalized_real_media_result():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "comfy-output.mp4"
        source.write_bytes(b"real media")

        class Client:
            def is_available(self):
                return True

            def submit(self, workflow):
                return "prompt-123"

            def wait_for_completion(self, task_id):
                return {"outputs": {}}

        provider = ComfyUIVideoProvider(
            _settings(root, "comfyui"),
            client=Client(),
            video_resolver=lambda _: source,
        )
        result = provider.generate(
            prompt="a shot",
            seed=7,
            duration_seconds=4,
            reference_images=[],
            output_dir=root / "outputs",
            metadata={"workflow": {"node": {}}, "output_filename": "shot-01.mp4"},
        )
        assert result.provider == "comfyui"
        assert result.task_id == "prompt-123"
        assert result.video_path.read_bytes() == b"real media"


def test_pending_keyframe_cannot_enter_a_reference_workflow():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        template = root / "workflows" / "reference-workflow.json"
        template.parent.mkdir(parents=True)
        template.write_text(
            json.dumps({"_movie_agent": {"reference_inputs": {"keyframe": ["input"]}}}),
            encoding="utf-8",
        )
        keyframe = root / "pending.webp"
        keyframe.write_bytes(b"pending")
        settings = _settings(root, "comfyui")
        agent = GenerationAgent(settings, client=object())
        shot = Shot(
            1, 6, "medium", "image", "action", "sound", "T2V", "delta", "shot.mp4",
            media_generation={"keyframe_path": str(keyframe)},
        )

        with pytest.raises(ComfyUIError, match="pending visual review"):
            agent._prepare_workflow_references(template, shot, project_id="film-a1b2c3d4")


def test_approved_current_keyframe_can_enter_a_reference_workflow():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        template = root / "workflows" / "reference-workflow.json"
        template.parent.mkdir(parents=True)
        template.write_text(
            json.dumps({"_movie_agent": {"reference_inputs": {"keyframe": ["input"]}}}),
            encoding="utf-8",
        )
        keyframe = root / "approved.webp"
        keyframe.write_bytes(b"approved")
        settings = _settings(root, "comfyui")

        class Client:
            def upload_image(self, path):
                assert Path(path).is_file()
                return "approved-upload"

        agent = GenerationAgent(settings, client=Client())
        approved = agent.reference_bank.register_file(
            "film-a1b2c3d4", keyframe, kind="shot_keyframe", source="manual_review",
            approved=True, shot_number=1, revision=1,
        )
        shot = Shot(
            1, 6, "medium", "image", "action", "sound", "T2V", "delta", "shot.mp4",
            media_generation={"keyframe_path": approved.path},
        )

        assert agent._prepare_workflow_references(template, shot, project_id="film-a1b2c3d4") == ["approved-upload"]


def test_remote_provider_exposes_fail_closed_async_lifecycle():
    with TemporaryDirectory() as directory:
        provider = build_video_provider(_settings(Path(directory), "remote"))
        assert provider.is_available() is False
        with pytest.raises(VideoGenerationError, match="not configured"):
            provider.submit(prompt="shot")
        with pytest.raises(VideoGenerationError, match="not configured"):
            provider.poll("task-1")
        with pytest.raises(VideoGenerationError, match="not configured"):
            provider.download({}, Path(directory), "shot.mp4")
