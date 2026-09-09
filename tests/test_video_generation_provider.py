from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import json

from movie_agent.agents.generation import GenerationAgent
from movie_agent.config import Settings
from movie_agent.models import MovieProject, Shot
from movie_agent.services.comfyui import ComfyUIError
from movie_agent.services.video_generation import (
    ComfyUIVideoProvider,
    DashScopeVideoProvider,
    HTTPResponse,
    MockVideoProvider,
    NormalizedVideoRequest,
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


class _ResumableFakeProvider(_FakeVideoProvider):
    model = "fake-model"

    def __init__(self, output: Path):
        super().__init__(output)
        self.calls: list[str] = []

    def generate(self, **kwargs):
        self.calls.append("generate")
        return super().generate(**kwargs)

    def resume_task(self, task_id, **kwargs):
        self.calls.append(f"resume:{task_id}")
        return VideoGenerationResult(
            provider=self.name,
            task_id=task_id,
            status="COMPLETED",
            video_path=self.output,
            model=self.model,
            metadata={"source_path": str(self.output)},
        )


class _FingerprintFakeProvider(_ResumableFakeProvider):
    """Offline provider that exposes the exact-request identity contract."""

    name = "fingerprint-remote"

    def __init__(self, output: Path):
        super().__init__(output)
        self.provider_seed_offset = 0
        self.submits = 0

    def normalize_request(self, *, prompt, seed, duration_seconds, reference_images, metadata):
        self.last_normalized_request = NormalizedVideoRequest(
            model=self.model,
            prompt=prompt,
            negative_prompt=str(metadata.get("negative_prompt") or ""),
            duration=int(round(duration_seconds)),
            resolution=str(metadata.get("target_resolution") or "1080p").upper(),
            ratio=str(metadata.get("aspect") or "16:9"),
            seed=int(seed) + self.provider_seed_offset if seed is not None else None,
            canonical_seed=int(seed) if seed is not None else None,
        )
        return self.last_normalized_request

    def generate(self, **kwargs):
        self.submits += 1
        assert kwargs["metadata"]["expected_provider_request_fingerprint"] == self.normalize_request(
            prompt=kwargs["prompt"],
            seed=kwargs["seed"],
            duration_seconds=kwargs["duration_seconds"],
            reference_images=kwargs["reference_images"],
            metadata=kwargs["metadata"],
        ).fingerprint
        kwargs["on_progress"]({"status": "SUBMITTED", "provider": self.name, "task_id": "fake-task-1"})
        return VideoGenerationResult(
            provider=self.name,
            task_id="fake-task-1",
            status="COMPLETED",
            video_path=self.output,
            model=self.model,
            metadata={"source_path": str(self.output)},
        )


def _fingerprint_project(shot: Shot) -> MovieProject:
    return MovieProject(
        "film-a1b2c3d4",
        "offline exact request identity test",
        2,
        "cinematic",
        "render_ready",
        {},
        {},
        {},
        [shot],
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


def test_remote_task_identity_is_persisted_for_exact_request():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "video.mp4"
        output.write_bytes(b"real-video")
        provider = _ResumableFakeProvider(output)
        agent = GenerationAgent(_settings(root), provider=provider)
        shot = _reference_shot("")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("movie_agent.agents.generation.asset_record", lambda *args, **kwargs: kwargs)
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
        task = shot.media_generation
        assert task["provider_task_id"] == "fake-task-1"
        assert task["provider_task_status"] == "COMPLETED"
        assert task["provider_task_revision"] == shot.revision
        assert task["provider_task_request_hash"] == shot.generation_input_hash
        assert task["provider_task_provider"] == provider.name
        assert task["provider_task_model"] == provider.model
        assert task["provider_task_submitted_at"]


def test_remote_task_is_resumed_only_for_the_same_revision_and_request():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "video.mp4"
        output.write_bytes(b"real-video")
        provider = _ResumableFakeProvider(output)
        agent = GenerationAgent(_settings(root), provider=provider)
        shot = _reference_shot("")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("movie_agent.agents.generation.asset_record", lambda *args, **kwargs: kwargs)
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
            shot.status = "generating"
            shot.media_generation["generation_status"] = "RUNNING"
            shot.media_generation["provider_task_status"] = "RUNNING"
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
        assert provider.calls == ["generate", "resume:fake-task-1"]


def test_remote_task_from_another_revision_is_not_resumed():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "video.mp4"
        output.write_bytes(b"real-video")
        provider = _ResumableFakeProvider(output)
        agent = GenerationAgent(_settings(root), provider=provider)
        shot = _reference_shot("")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("movie_agent.agents.generation.asset_record", lambda *args, **kwargs: kwargs)
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
            shot.status = "generating"
            shot.media_generation["generation_status"] = "RUNNING"
            shot.media_generation["provider_task_status"] = "RUNNING"
            shot.revision += 1
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
        assert provider.calls == ["generate", "generate"]
        assert shot.media_generation["provider_task_revision"] == shot.revision
        assert shot.media_generation["provider_task_request_hash"] == shot.generation_input_hash


def test_remote_task_with_changed_request_hash_is_not_resumed():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "video.mp4"
        output.write_bytes(b"real-video")
        provider = _ResumableFakeProvider(output)
        agent = GenerationAgent(_settings(root), provider=provider)
        shot = _reference_shot("")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("movie_agent.agents.generation.asset_record", lambda *args, **kwargs: kwargs)
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
            shot.status = "generating"
            shot.media_generation["generation_status"] = "RUNNING"
            shot.media_generation["provider_task_status"] = "RUNNING"
            shot.prompt = "different shot delta"
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
        assert provider.calls == ["generate", "generate"]


@pytest.mark.parametrize("completed_status", ["SUCCEEDED", "COMPLETED"])
def test_completed_remote_task_recovers_without_resubmitting(completed_status):
    with TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "video.mp4"
        output.write_bytes(b"real-video")
        provider = _ResumableFakeProvider(output)
        agent = GenerationAgent(_settings(root), provider=provider)
        shot = _reference_shot("")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("movie_agent.agents.generation.asset_record", lambda *args, **kwargs: kwargs)
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
            # Simulate a process crash after the provider completed but before
            # the local source asset was finalized.
            shot.status = "generating"
            shot.output_placeholder = str(root / "not-downloaded-yet.mp4")
            shot.media_assets = {}
            shot.media_generation["generation_status"] = completed_status
            shot.media_generation["provider_task_status"] = completed_status
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
        assert provider.calls == ["generate", "resume:fake-task-1"]
        assert any(
            item["event"] == "RECOVERED_COMPLETED_TASK"
            and item["provider_task_id"] == "fake-task-1"
            for item in shot.media_generation["provider_task_history"]
        )


def test_superseded_remote_task_remains_in_history():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "video.mp4"
        output.write_bytes(b"real-video")
        provider = _ResumableFakeProvider(output)
        agent = GenerationAgent(_settings(root), provider=provider)
        shot = _reference_shot("")
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("movie_agent.agents.generation.asset_record", lambda *args, **kwargs: kwargs)
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
            shot.status = "generating"
            shot.media_generation["generation_status"] = "RUNNING"
            shot.media_generation["provider_task_status"] = "RUNNING"
            shot.prompt = "replanned shot delta"
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"scene_lock": "home", "character_lock": "hero", "cinematography_lock": "camera"},
            )
        assert any(item["event"] == "SUPERSEDED_TASK" for item in shot.media_generation["provider_task_history"])


def test_provider_capability_rejects_unsupported_generation_mode():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        provider = _FakeVideoProvider(root / "video.mp4")
        agent = GenerationAgent(_settings(root), provider=provider)
        shot = Shot(1, 6, "medium", "image", "action", "sound", "I2V", "delta", "shot.mp4")
        with pytest.raises(VideoGenerationError) as error:
            agent.generate("film-a1b2c3d4", shot, visual_bible={"cinematography_lock": "camera"})
        assert error.value.error_code == "VIDEO_GENERATION_MODE_UNSUPPORTED"


def test_dashscope_normalized_request_rejects_silent_duration_clamp():
    with TemporaryDirectory() as directory:
        provider = DashScopeVideoProvider(_settings(Path(directory), "remote"))
        with pytest.raises(VideoGenerationError) as error:
            provider.normalize_request(prompt="shot", duration_seconds=16)
        assert error.value.error_code == "VIDEO_PROVIDER_DURATION_UNSUPPORTED"


@pytest.mark.parametrize(
    ("seed", "provider_seed"),
    [
        (None, None),
        (0, 0),
        (1, 1),
        (2_147_483_647, 2_147_483_647),
        (1_242_568_112_720_127_198, 2_011_768_030),
    ],
)
def test_dashscope_normalizes_canonical_seed_at_provider_boundary(seed, provider_seed):
    with TemporaryDirectory() as directory:
        provider = DashScopeVideoProvider(_settings(Path(directory), "remote"))
        normalized = provider.normalize_request(prompt="shot", seed=seed, duration_seconds=2)
        assert normalized.seed == provider_seed
        assert normalized.provider_seed == provider_seed
        assert normalized.canonical_seed == seed


@pytest.mark.parametrize("seed", [-1, "not-an-integer", 1.5])
def test_dashscope_rejects_invalid_seed_before_network(seed):
    with TemporaryDirectory() as directory:
        provider = DashScopeVideoProvider(_settings(Path(directory), "remote"))
        with pytest.raises(VideoGenerationError) as error:
            provider.normalize_request(prompt="shot", seed=seed, duration_seconds=2)
        assert error.value.error_code == "VIDEO_PROVIDER_REQUEST_UNSUPPORTED"


def test_dashscope_normalized_request_fingerprint_is_stable_and_changes_with_provider_facts():
    with TemporaryDirectory() as directory:
        provider = DashScopeVideoProvider(_settings(Path(directory), "remote"))
        base = provider.normalize_request(
            prompt="shot", seed=1_242_568_112_720_127_198, duration_seconds=2,
            metadata={"target_resolution": "720p", "aspect": "16:9", "negative_prompt": "no text"},
        )
        same = provider.normalize_request(
            prompt="shot", seed=1_242_568_112_720_127_198, duration_seconds=2,
            metadata={"target_resolution": "720p", "aspect": "16:9", "negative_prompt": "no text"},
        )
        changed_duration = provider.normalize_request(
            prompt="shot", seed=1_242_568_112_720_127_198, duration_seconds=3,
            metadata={"target_resolution": "720p", "aspect": "16:9", "negative_prompt": "no text"},
        )
        changed_ratio = provider.normalize_request(
            prompt="shot", seed=1_242_568_112_720_127_198, duration_seconds=2,
            metadata={"target_resolution": "720p", "aspect": "9:16", "negative_prompt": "no text"},
        )
        assert base.fingerprint == same.fingerprint
        assert base.fingerprint != changed_duration.fingerprint
        assert base.fingerprint != changed_ratio.fingerprint


def test_dashscope_preflight_fingerprint_mismatch_makes_zero_post_calls():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        settings = _settings(root, "remote").__class__(
            **{
                **_settings(root, "remote").__dict__,
                "remote_video_api_base": "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
                "remote_video_model": "wan2.7-t2v",
                "remote_video_api_key": "secret-only-in-test",
            }
        )

        class Transport:
            def __init__(self):
                self.calls = []

            def request(self, method, url, *, headers, body=None, timeout):
                self.calls.append((method, url, headers, body, timeout))
                raise AssertionError("transport must not be called on identity mismatch")

        transport = Transport()
        provider = DashScopeVideoProvider(settings, transport=transport)
        with pytest.raises(VideoGenerationError) as error:
            provider.submit(
                prompt="shot",
                seed=1_242_568_112_720_127_198,
                duration_seconds=2,
                metadata={
                    "target_resolution": "720p",
                    "aspect": "16:9",
                    "expected_provider_request_fingerprint": "0" * 64,
                },
            )
        assert error.value.error_code == "VIDEO_PROVIDER_REQUEST_IDENTITY_MISMATCH"
        assert transport.calls == []


def test_generation_persists_exact_provider_fingerprint_with_task_identity():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "video.mp4"
        output.write_bytes(b"real-video")
        provider = _FingerprintFakeProvider(output)
        saved = []
        shot = Shot(1, 2, "wide", "image", "action", "sound", "T2V", "delta", "shot.mp4", source_duration_seconds=2)
        project = _fingerprint_project(shot)
        agent = GenerationAgent(_settings(root), provider=provider, persist=lambda item: saved.append(item.storyboard[0].media_generation.copy()))
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("movie_agent.agents.generation.asset_record", lambda *args, **kwargs: kwargs)
            agent.generate(
                project.project_id,
                shot,
                visual_bible={"reference_seed": "42", "cinematography_lock": "camera"},
                project=project,
            )
        assert len(saved) == 1
        assert saved[0]["provider_task_id"] == "fake-task-1"
        assert saved[0]["provider_task_request_hash"] == shot.generation_input_hash
        assert saved[0]["provider_task_request_fingerprint"] == shot.media_generation["request"]["provider_request_fingerprint"]
        assert saved[0]["provider_task_request_fingerprint"]
        assert saved[0]["provider_seed"] == shot.media_generation["request"]["provider_seed"]
        assert shot.media_assets["source"]["provider_request_fingerprint"] == saved[0]["provider_task_request_fingerprint"]
        assert shot.media_assets["source"]["generation_input_hash"] == shot.generation_input_hash


def test_generation_resumes_same_exact_provider_request_without_second_submit():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "video.mp4"
        output.write_bytes(b"real-video")
        provider = _FingerprintFakeProvider(output)
        shot = Shot(1, 2, "wide", "image", "action", "sound", "T2V", "delta", "shot.mp4", source_duration_seconds=2)
        agent = GenerationAgent(_settings(root), provider=provider)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("movie_agent.agents.generation.asset_record", lambda *args, **kwargs: kwargs)
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"reference_seed": "42", "cinematography_lock": "camera"},
            )
            shot.status = "generating"
            shot.media_generation["generation_status"] = "RUNNING"
            shot.media_generation["provider_task_status"] = "RUNNING"
            agent.generate(
                "film-a1b2c3d4", shot,
                visual_bible={"reference_seed": "42", "cinematography_lock": "camera"},
            )
        assert provider.submits == 1
        assert provider.calls == ["resume:fake-task-1"]
        assert shot.media_assets["source"]["provider_request_fingerprint"] == shot.media_generation["provider_task_request_fingerprint"]


def test_generation_fails_closed_for_inflight_provider_fingerprint_mismatch():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "video.mp4"
        output.write_bytes(b"real-video")
        provider = _FingerprintFakeProvider(output)
        shot = Shot(1, 2, "wide", "image", "action", "sound", "T2V", "delta", "shot.mp4", source_duration_seconds=2)
        agent = GenerationAgent(_settings(root), provider=provider)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("movie_agent.agents.generation.asset_record", lambda *args, **kwargs: kwargs)
            agent.generate("film-a1b2c3d4", shot, visual_bible={"reference_seed": "42", "cinematography_lock": "camera"})
            shot.status = "generating"
            shot.media_generation["generation_status"] = "RUNNING"
            shot.media_generation["provider_task_status"] = "RUNNING"
            provider.provider_seed_offset = 1
            with pytest.raises(VideoGenerationError) as error:
                agent.generate("film-a1b2c3d4", shot, visual_bible={"reference_seed": "42", "cinematography_lock": "camera"})
        assert error.value.error_code == "VIDEO_PROVIDER_TASK_IDENTITY_UNVERIFIED"
        assert provider.submits == 1


def test_generation_fails_closed_for_legacy_inflight_task_without_provider_fingerprint():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "video.mp4"
        output.write_bytes(b"real-video")
        provider = _FingerprintFakeProvider(output)
        shot = Shot(1, 2, "wide", "image", "action", "sound", "T2V", "delta", "shot.mp4", source_duration_seconds=2)
        agent = GenerationAgent(_settings(root), provider=provider)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("movie_agent.agents.generation.asset_record", lambda *args, **kwargs: kwargs)
            agent.generate("film-a1b2c3d4", shot, visual_bible={"reference_seed": "42", "cinematography_lock": "camera"})
            shot.status = "generating"
            shot.media_generation["generation_status"] = "RUNNING"
            shot.media_generation["provider_task_status"] = "RUNNING"
            shot.media_generation.pop("provider_task_request_fingerprint")
            with pytest.raises(VideoGenerationError) as error:
                agent.generate("film-a1b2c3d4", shot, visual_bible={"reference_seed": "42", "cinematography_lock": "camera"})
        assert error.value.error_code == "VIDEO_PROVIDER_TASK_IDENTITY_UNVERIFIED"
        assert provider.submits == 1


def test_dashscope_poll_retries_transient_failure_without_resubmitting():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        settings = _settings(root, "remote")
        settings = settings.__class__(
            **{
                **settings.__dict__,
                "remote_video_api_base": "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
                "remote_video_model": "wan2.7-t2v",
                "remote_video_api_key": "secret-only-in-test",
                "remote_video_task_timeout_seconds": 10,
                "remote_video_poll_seconds": 0.5,
                "remote_video_poll_retries": 2,
            }
        )

        def response(payload: dict, status_code: int = 200, headers: dict[str, str] | None = None) -> HTTPResponse:
            return HTTPResponse(status_code, headers or {"content-type": "application/json"}, json.dumps(payload).encode())

        class Transport:
            def __init__(self):
                self.calls = []
                self.responses = [
                    response({"output": {"task_id": "task-retry", "task_status": "PENDING"}}),
                    response({}, 503, {"retry-after": "0"}),
                    response({"output": {"task_id": "task-retry", "task_status": "SUCCEEDED", "video_url": "https://cdn.example/a.mp4"}}),
                    HTTPResponse(200, {"content-type": "video/mp4"}, b"video"),
                ]

            def request(self, method, url, *, headers, body=None, timeout):
                self.calls.append((method, url, body, timeout))
                return self.responses.pop(0)

        provider = DashScopeVideoProvider(
            settings,
            transport=Transport(),
            sleep_fn=lambda _: None,
            media_validator=lambda path: {"valid": path.read_bytes() == b"video"},
        )
        result = provider.generate(
            prompt="shot",
            seed=1,
            duration_seconds=5,
            reference_images=[],
            output_dir=root / "outputs",
            metadata={"output_filename": "shot.mp4"},
        )
        assert result.task_id == "task-retry"
        assert [call[0] for call in provider.transport.calls] == ["POST", "GET", "GET", "GET"]


def test_dashscope_resume_task_never_posts_a_second_generation_request():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        settings = _settings(root, "remote")
        settings = settings.__class__(
            **{
                **settings.__dict__,
                "remote_video_api_base": "https://workspace.cn-beijing.maas.aliyuncs.com/api/v1",
                "remote_video_model": "wan2.7-t2v",
                "remote_video_api_key": "secret-only-in-test",
                "remote_video_task_timeout_seconds": 10,
                "remote_video_poll_seconds": 0.5,
            }
        )

        class Transport:
            def __init__(self):
                self.methods = []

            def request(self, method, url, *, headers, body=None, timeout):
                self.methods.append(method)
                if "/tasks/" in url:
                    return HTTPResponse(
                        200,
                        {"content-type": "application/json"},
                        json.dumps({"output": {"task_id": "task-existing", "task_status": "SUCCEEDED", "video_url": "https://cdn.example/a.mp4"}}).encode(),
                    )
                return HTTPResponse(200, {"content-type": "video/mp4"}, b"video")

        transport = Transport()
        provider = DashScopeVideoProvider(
            settings,
            transport=transport,
            sleep_fn=lambda _: None,
            media_validator=lambda path: {"valid": path.read_bytes() == b"video"},
        )
        result = provider.resume_task(
            "task-existing",
            output_dir=root / "outputs",
            filename="shot.mp4",
        )
        assert result.task_id == "task-existing"
        assert transport.methods == ["GET", "GET"]
