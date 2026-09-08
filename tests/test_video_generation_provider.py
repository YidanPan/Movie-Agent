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
    DashScopeVideoProvider,
    HTTPResponse,
    MockVideoProvider,
    VideoGenerationError,
    VideoGenerationResult,
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


def test_dashscope_provider_uses_official_async_submit_poll_download_contract():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        settings = _settings(root, "remote")
        settings = settings.__class__(
            **{
                **settings.__dict__,
                "remote_video_api_base": "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
                "remote_video_model": "wan2.7-t2v",
                "remote_video_api_key": "secret-only-in-test",
                "remote_video_timeout_seconds": 10,
                "remote_video_poll_seconds": 0.5,
            }
        )

        def response(payload: dict, status_code: int = 200) -> HTTPResponse:
            return HTTPResponse(status_code, {"content-type": "application/json"}, json.dumps(payload).encode())

        class Transport:
            def __init__(self):
                self.calls = []
                self.responses = [
                    response({"output": {"task_id": "task-123", "task_status": "PENDING"}}),
                    response({"output": {"task_id": "task-123", "task_status": "RUNNING"}}),
                    response({"output": {"task_id": "task-123", "task_status": "SUCCEEDED", "video_url": "https://cdn.example/shot.mp4"}}),
                    HTTPResponse(200, {"content-type": "video/mp4"}, b"validated-video"),
                ]

            def request(self, method, url, *, headers, body=None, timeout):
                self.calls.append((method, url, headers, body, timeout))
                return self.responses.pop(0)

        transport = Transport()
        provider = DashScopeVideoProvider(
            settings,
            transport=transport,
            sleep_fn=lambda _: None,
            media_validator=lambda path: {"valid": path.read_bytes() == b"validated-video"},
        )
        progress = []
        result = provider.generate(
            prompt="a single cinematic shot",
            seed=7,
            duration_seconds=5,
            reference_images=[],
            output_dir=root / "outputs",
            metadata={"output_filename": "shot-01.mp4", "target_resolution": "720p", "aspect": "16:9", "negative_prompt": "blur"},
            on_progress=progress.append,
        )

        assert result.provider == "dashscope"
        assert result.task_id == "task-123"
        assert result.video_path.read_bytes() == b"validated-video"
        assert [item[0] for item in transport.calls] == ["POST", "GET", "GET", "GET"]
        submit_body = json.loads(transport.calls[0][3].decode())
        assert submit_body["model"] == "wan2.7-t2v"
        assert submit_body["input"]["negative_prompt"] == "blur"
        assert submit_body["parameters"] == {
            "resolution": "720P",
            "ratio": "16:9",
            "prompt_extend": False,
            "watermark": False,
            "duration": 5,
            "seed": 7,
        }
        assert "Authorization" in transport.calls[0][2]
        assert "Authorization" not in transport.calls[-1][2]
        assert [item["status"] for item in progress] == ["SUBMITTED", "RUNNING", "SUCCEEDED", "COMPLETED"]


def test_dashscope_provider_rejects_local_references_instead_of_claiming_i2v():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        settings = _settings(root, "remote")
        settings = settings.__class__(
            **{
                **settings.__dict__,
                "remote_video_api_base": "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
                "remote_video_model": "wan2.7-t2v",
                "remote_video_api_key": "secret-only-in-test",
            }
        )
        provider = DashScopeVideoProvider(settings)
        reference = root / "reference.webp"
        reference.write_bytes(b"image")
        with pytest.raises(VideoGenerationError) as error:
            provider.submit(prompt="shot", reference_images=[reference])
        assert error.value.error_code == "VIDEO_PROVIDER_REFERENCE_UNSUPPORTED"


def test_reference_bank_same_name_keeps_immutable_bytes():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        store = GenerationAgent(_settings(root)).reference_bank
        first = root / "first.webp"
        second = root / "second.webp"
        first.write_bytes(b"first-reference")
        second.write_bytes(b"second-reference")
        one = store.register_file("film-a1b2c3d4", first, kind="character", source="test", name="hero")
        two = store.register_file("film-a1b2c3d4", second, kind="character", source="test", name="hero")
        assert one.path != two.path
        assert Path(one.path).read_bytes() == b"first-reference"
        assert Path(two.path).read_bytes() == b"second-reference"


def test_pending_same_name_reference_cannot_borrow_old_approval():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        store = GenerationAgent(_settings(root)).reference_bank
        approved_source = root / "approved.webp"
        pending_source = root / "pending.webp"
        approved_source.write_bytes(b"approved")
        pending_source.write_bytes(b"pending")
        approved = store.register_file(
            "film-a1b2c3d4", approved_source, kind="shot_keyframe", source="test",
            approved=False, shot_number=1, revision=1, name="linran",
        )
        store.set_approval("film-a1b2c3d4", approved.reference_id, True)
        pending = store.register_file(
            "film-a1b2c3d4", pending_source, kind="shot_keyframe", source="test",
            approved=False, shot_number=1, revision=1, name="linran",
        )
        assert approved.path != pending.path
        shot = _reference_shot(pending.path)
        with pytest.raises(ValueError, match="REFERENCE_REVIEW_REQUIRED"):
            store.approved_generation_inputs("film-a1b2c3d4", shot, require_keyframe=True)


class _FakeVideoProvider:
    name = "fake-remote"
    supported_modes = frozenset({"T2V"})

    def __init__(self, output: Path):
        self.output = output
        self.references: list[Path] = []

    def is_available(self):
        return True

    def generate(self, **kwargs):
        self.references = list(kwargs["reference_images"])
        return VideoGenerationResult(
            provider=self.name,
            task_id="fake-task-1",
            status="COMPLETED",
            video_path=self.output,
            model="fake-model",
            metadata={"source_path": str(self.output)},
        )


def _reference_shot(path: str, *, revision: int = 1) -> Shot:
    return Shot(
        1, 6, "medium", "image", "action", "sound", "T2V", "delta", "shot.mp4",
        revision=revision,
        scene_id="home",
        character_ids=["hero"],
        media_generation={"keyframe_path": path},
    )


def test_optional_pending_keyframe_is_omitted_before_fake_provider_receives_inputs():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        pending = root / "pending.webp"
        output = root / "video.mp4"
        pending.write_bytes(b"pending")
        output.write_bytes(b"real-video")
        provider = _FakeVideoProvider(output)
        agent = GenerationAgent(_settings(root), provider=provider)
        asset = agent.reference_bank.register_file(
            "film-a1b2c3d4", pending, kind="shot_keyframe", source="test", approved=False,
            shot_number=1, revision=1, name="keyframe",
        )
        shot = _reference_shot(asset.path)
        agent.generate(
            "film-a1b2c3d4", shot,
            visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
        )
        assert provider.references == []
        assert shot.status == "generated"


def test_pending_keyframe_cannot_enter_any_video_provider():
    test_optional_pending_keyframe_is_omitted_before_fake_provider_receives_inputs()


def test_approved_current_keyframe_is_the_only_keyframe_sent_to_fake_provider():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        keyframe = root / "approved.webp"
        output = root / "video.mp4"
        keyframe.write_bytes(b"approved")
        output.write_bytes(b"real-video")
        provider = _FakeVideoProvider(output)
        agent = GenerationAgent(_settings(root), provider=provider)
        asset = agent.reference_bank.register_file(
            "film-a1b2c3d4", keyframe, kind="shot_keyframe", source="test", approved=True,
            shot_number=1, revision=1, name="keyframe",
        )
        shot = _reference_shot(asset.path)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("movie_agent.agents.generation.asset_record", lambda *args, **kwargs: {"path": str(output), "tier": "source"})
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
        assert provider.references == [Path(asset.path)]
        assert shot.status == "generated"
        assert shot.media_assets["source"]["tier"] == "source"
        assert shot.model == "fake-model"


def test_approved_keyframe_enters_any_video_provider():
    test_approved_current_keyframe_is_the_only_keyframe_sent_to_fake_provider()


@pytest.mark.parametrize(
    ("metadata", "asset_revision", "shot_revision"),
    [
        ({"stale": True}, 1, 1),
        ({}, 2, 1),
    ],
)
def test_stale_or_wrong_revision_keyframe_is_omitted_for_optional_t2v(metadata, asset_revision, shot_revision):
    with TemporaryDirectory() as directory:
        root = Path(directory)
        keyframe = root / "keyframe.webp"
        keyframe.write_bytes(b"keyframe")
        provider = _FakeVideoProvider(root / "video.mp4")
        agent = GenerationAgent(_settings(root), provider=provider)
        asset = agent.reference_bank.register_file(
            "film-a1b2c3d4", keyframe, kind="shot_keyframe", source="test", approved=True,
            shot_number=1, revision=asset_revision, name="keyframe", metadata=metadata,
        )
        shot = _reference_shot(asset.path, revision=shot_revision)
        agent.generate(
            "film-a1b2c3d4", shot,
            visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
        )
        assert provider.references == []


def test_fake_provider_persists_provider_neutral_metadata_without_manifest():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "video.mp4"
        output.write_bytes(b"real-video")
        agent = GenerationAgent(_settings(root), provider=_FakeVideoProvider(output))
        shot = Shot(
            1, 6, "medium", "image", "action", "sound", "T2V", "delta", "shot.mp4",
            scene_id="home", character_ids=["hero"],
        )
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("movie_agent.agents.generation.asset_record", lambda *args, **kwargs: kwargs)
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
        record = shot.media_assets["source"]
        assert record["renderer_contract_status"] == "PROVIDER_REPORTED"
        assert record["renderer_verification_status"] == "PROVIDER_REPORTED"
        assert isinstance(record["external_input_digests"], dict)


def test_provider_capability_rejects_unsupported_generation_mode():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        provider = _FakeVideoProvider(root / "video.mp4")
        agent = GenerationAgent(_settings(root), provider=provider)
        shot = Shot(1, 6, "medium", "image", "action", "sound", "I2V", "delta", "shot.mp4")
        with pytest.raises(VideoGenerationError) as error:
            agent.generate("film-a1b2c3d4", shot, visual_bible={"cinematography_lock": "camera"})
        assert error.value.error_code == "VIDEO_GENERATION_MODE_UNSUPPORTED"
