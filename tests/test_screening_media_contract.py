from pathlib import Path


ROOT = Path(__file__).parents[1]
APP = (ROOT / "static" / "app.js").read_text(encoding="utf-8")


def test_screening_media_has_identity_guards_for_final_and_rough_cut():
    assert "finalMediaIdentity" in APP
    assert "roughCutMediaIdentity" in APP
    assert "screeningMediaIdentity(project, \"final\", candidate)" in APP
    assert "screeningMediaIdentity(project, \"rough\", roughCutUrl)" in APP
    assert "state.finalMediaIdentity === finalIdentity" in APP
    assert "state.roughCutMediaIdentity === roughIdentity" in APP


def test_screening_media_rejects_stale_async_probe_before_dom_mutation():
    assert APP.count("if (probeRun !== state.finalVideoProbeRun) return;") >= 3
    assert "setScreeningMediaSource(els.finalVideo, candidate, finalIdentity)" in APP
    assert "setScreeningMediaSource(els.roughCutVideo, roughCutUrl, roughIdentity)" in APP


def test_screening_media_does_not_reload_stable_sources_on_each_render():
    assert "if (media.getAttribute(\"src\") === url && media.dataset.mediaIdentity === identity) return;" in APP
    assert "clearScreeningMedia(els.finalVideo);" in APP
    assert "els.finalVideo?.removeAttribute(\"src\");" not in APP
    assert "els.roughCutVideo?.removeAttribute(\"src\");" not in APP
