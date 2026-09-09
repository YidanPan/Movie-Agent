from pathlib import Path

import pytest

from movie_agent.agents.editor import EditorAgent
from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator


def _editor_project(tmp_path: Path):
    settings = Settings(
        "http://127.0.0.1:8188",
        900,
        tmp_path / "workflows",
        9071,
        tmp_path / "projects",
        True,
        outputs_dir=tmp_path / "outputs",
    )
    project = MovieOrchestrator(settings).create_project(
        "A quiet signal crosses the midnight city.", 48, "film sci-fi"
    )
    project.script["dialogue_locked"] = True
    return project, EditorAgent(settings)


def _authoritative_cut(project, editor: EditorAgent, data: bytes = b"MIXED-AUDIO-AUTHORITATIVE"):
    rough_path = editor._output_dir(project) / "rough-cut-mezzanine.mov"
    rough_path.write_bytes(data)
    project.mix_state = {
        "media_mixed": True,
        "loudness_status": "NORMALIZED",
        "limiter": "ACTIVE",
        "ducking_status": "ACTIVE",
    }
    return rough_path


def _stub_mix_and_register(monkeypatch, editor: EditorAgent):
    def keep_mix(project, picture_path):
        return picture_path

    def register(project, source, *, include_master):
        project.video_assets["final_master"] = {
            "path": str(source),
            "tier": "final_master",
        }

    monkeypatch.setattr(editor, "_mix_audio", keep_mix)
    monkeypatch.setattr(editor, "_register_cut_assets", register)


def test_burned_subtitle_success_uses_authoritative_rough_cut(tmp_path, monkeypatch):
    project, editor = _editor_project(tmp_path)
    rough_path = _authoritative_cut(project, editor)
    _stub_mix_and_register(monkeypatch, editor)
    seen = {}

    def render(command_prefix, target):
        seen["command"] = command_prefix
        target.write_bytes(b"BURNED-FINAL-CUT")
        return "test_mezzanine"

    monkeypatch.setattr(editor, "_run_mezzanine", render)
    monkeypatch.setattr(editor, "_concat_media", lambda *_: pytest.fail("subtitle path must not concat shots"))

    editor.assemble(project, subtitle_mode="burned")

    final_cut = Path(project.final_output_placeholder)
    assert final_cut.is_file()
    assert final_cut.read_bytes() == b"BURNED-FINAL-CUT"
    assert str(rough_path) in seen["command"]
    assert "-map" in seen["command"]
    assert "0:a?" in seen["command"]
    delivery = project.edit_plan["subtitle_delivery"]
    assert delivery["requested_mode"] == "burned"
    assert delivery["delivered_mode"] == "burned"
    assert delivery["fallback"] is False


def test_burned_subtitle_failure_preserves_mixed_rough_cut(tmp_path, monkeypatch):
    project, editor = _editor_project(tmp_path)
    rough_path = _authoritative_cut(project, editor)
    _stub_mix_and_register(monkeypatch, editor)

    def failed_render(_command_prefix, target):
        target.write_bytes(b"PARTIAL-BURN")
        raise RuntimeError("font renderer unavailable")

    monkeypatch.setattr(editor, "_run_mezzanine", failed_render)
    monkeypatch.setattr(editor, "_concat_media", lambda *_: pytest.fail("burn fallback must not concat shots"))

    result = editor.assemble(project, subtitle_mode="burned")

    final_cut = Path(project.final_output_placeholder)
    assert final_cut.read_bytes() == rough_path.read_bytes()
    assert "delivered clean Final Cut" in result
    delivery = project.edit_plan["subtitle_delivery"]
    assert delivery["requested_mode"] == "burned"
    assert delivery["delivered_mode"] == "none"
    assert delivery["status"] == "FALLBACK"
    assert delivery["fallback"] is True
    assert delivery["reason"] == "burn_in_failed"
    assert Path(delivery["srt_path"]).is_file()
    assert Path(delivery["vtt_path"]).is_file()
    assert project.video_assets["final_master"]["path"] == str(final_cut)
    assert project.mix_state["media_mixed"] is True
    assert project.mix_state["loudness_status"] == "NORMALIZED"


def test_soft_subtitle_success_uses_authoritative_rough_cut(tmp_path, monkeypatch):
    project, editor = _editor_project(tmp_path)
    rough_path = _authoritative_cut(project, editor)
    _stub_mix_and_register(monkeypatch, editor)

    def mux(source, _srt_path, target):
        assert source == rough_path
        target.write_bytes(b"SOFT-SUBTITLE-FINAL-CUT")
        return True

    monkeypatch.setattr(editor, "_mux_soft_subtitles", mux)
    monkeypatch.setattr(editor, "_concat_media", lambda *_: pytest.fail("subtitle path must not concat shots"))

    editor.assemble(project, subtitle_mode="soft")

    delivery = project.edit_plan["subtitle_delivery"]
    assert delivery["requested_mode"] == "soft"
    assert delivery["delivered_mode"] == "soft"
    assert delivery["fallback"] is False
    assert Path(project.final_output_placeholder).read_bytes() == b"SOFT-SUBTITLE-FINAL-CUT"


def test_soft_subtitle_failure_removes_partial_and_preserves_mixed_cut(tmp_path, monkeypatch):
    project, editor = _editor_project(tmp_path)
    rough_path = _authoritative_cut(project, editor, b"VOICE+MUSIC+SFX+AMBIENCE")
    _stub_mix_and_register(monkeypatch, editor)

    def failed_mux(_source, _srt_path, target):
        target.write_bytes(b"PARTIAL-MUX")
        return False

    monkeypatch.setattr(editor, "_mux_soft_subtitles", failed_mux)
    monkeypatch.setattr(editor, "_concat_media", lambda *_: pytest.fail("soft fallback must not concat shots"))

    editor.assemble(project, subtitle_mode="soft")

    final_cut = Path(project.final_output_placeholder)
    assert final_cut.read_bytes() == rough_path.read_bytes()
    delivery = project.edit_plan["subtitle_delivery"]
    assert delivery["delivered_mode"] == "none"
    assert delivery["status"] == "FALLBACK"
    assert delivery["reason"] == "soft_mux_failed"
    assert Path(delivery["srt_path"]).is_file()
    assert Path(delivery["vtt_path"]).is_file()


def test_none_subtitle_mode_copies_authoritative_rough_cut(tmp_path, monkeypatch):
    project, editor = _editor_project(tmp_path)
    rough_path = _authoritative_cut(project, editor)
    _stub_mix_and_register(monkeypatch, editor)
    monkeypatch.setattr(editor, "_concat_media", lambda *_: pytest.fail("none mode must not concat shots"))
    monkeypatch.setattr(editor, "_run_mezzanine", lambda *_: pytest.fail("none mode must not encode"))
    monkeypatch.setattr(editor, "_mux_soft_subtitles", lambda *_: pytest.fail("none mode must not mux"))

    editor.assemble(project, subtitle_mode="none")

    assert Path(project.final_output_placeholder).read_bytes() == rough_path.read_bytes()
    delivery = project.edit_plan["subtitle_delivery"]
    assert delivery["requested_mode"] == "none"
    assert delivery["delivered_mode"] == "none"
    assert delivery["status"] == "READY"
    assert delivery["fallback"] is False


def test_authoritative_rough_cut_missing_is_fatal(tmp_path, monkeypatch):
    project, editor = _editor_project(tmp_path)
    _stub_mix_and_register(monkeypatch, editor)
    monkeypatch.setattr(editor, "_concat_media", lambda *_: (_ for _ in ()).throw(RuntimeError("no picture cut")))

    with pytest.raises(RuntimeError, match="no picture cut"):
        editor.assemble(project, subtitle_mode="burned")

    assert project.final_output_placeholder is None
