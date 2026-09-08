from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
STYLE = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
DELIVER = (ROOT / "static" / "css" / "deliver.css").read_text(encoding="utf-8")
BIBLE = (ROOT / "static" / "css" / "production-bible.css").read_text(encoding="utf-8")
REFINEMENT = (ROOT / "static" / "css" / "interaction-refinement.css").read_text(encoding="utf-8")


def test_final_player_stage_owns_the_16_9_media_boundary():
    assert ".final-player-stage {" in DELIVER
    assert "aspect-ratio: 16 / 9;" in DELIVER
    assert "overflow: hidden;" in DELIVER
    assert ".final-player-shell {" in DELIVER
    assert "aspect-ratio: auto;" in DELIVER
    assert "overflow: visible;" in DELIVER


def test_quality_metadata_is_a_normal_flow_sibling_of_the_stage():
    shell_start = INDEX.index('class="final-player-shell"')
    stage_start = INDEX.index('class="final-player-stage"', shell_start)
    quality_start = INDEX.index('class="deliver-preview-quality"', stage_start)
    assert shell_start < stage_start < quality_start
    assert INDEX.rfind("</div>", stage_start, quality_start) > stage_start
    assert ".deliver-preview-quality {" in DELIVER
    assert "border-top: 0;" in DELIVER


def test_deliver_responsive_contract_keeps_progress_and_finish_controls_readable():
    assert "grid-template-columns: minmax(0, 1fr) minmax(320px, 360px);" in DELIVER
    assert "@media (max-width: 1099px)" in DELIVER
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in DELIVER
    assert "@media (max-width: 699px)" in DELIVER
    assert "grid-template-columns: 1fr;" in DELIVER
    assert "@media (max-width: 899px)" in DELIVER
    assert "flex-direction: column;" in DELIVER
    assert "flex: 1 1 360px;" in DELIVER
    assert "flex: 0 1 auto;" in DELIVER


def test_deliver_geometry_has_one_authoritative_module_owner():
    assert ".final-player-shell { position: relative; aspect-ratio: 16 / 9;" not in STYLE
    assert ".screening-panel { overflow: hidden; }" not in STYLE
    assert ".deliver-progress-grid { display: grid;" not in STYLE
    assert "grid-template-columns: minmax(0, 1fr) minmax(340px, 380px);" not in STYLE
    assert "grid-template-columns:" not in REFINEMENT


def test_production_bible_summary_stretches_but_asset_cards_use_natural_flow():
    assert ".visual-summary-grid" in BIBLE
    assert ".visual-assets-grid" in BIBLE
    assert "align-items: stretch;" in BIBLE
    assert "grid-template-rows: auto 1fr auto;" in BIBLE
    summary_start = BIBLE.index(".visual-summary-card")
    summary_end = BIBLE.find("}", summary_start)
    summary_rule = BIBLE[summary_start:summary_end]
    assert "align-self: stretch;" in summary_rule
    assert "height: 100%;" in summary_rule
    asset_start = BIBLE.index(".visual-asset-card")
    asset_end = BIBLE.find("}", asset_start)
    asset_rule = BIBLE[asset_start:asset_end]
    assert "align-self: start;" in asset_rule
    assert "height: auto;" in asset_rule
    assert "height: 100%;" not in asset_rule


def test_visible_layout_repair_uses_balanced_bible_width_and_drops_legacy_spec_height():
    assert "--manual-content-width: min(100%, 980px);" in BIBLE
    assert ".manual-panel .tab-body" in BIBLE
    assert ".manual-panel .visual-spec" in BIBLE
    spec_start = BIBLE.index(".manual-panel .visual-spec {")
    spec_rule = BIBLE[spec_start:BIBLE.index("}", spec_start)]
    assert "min-height: 0;" in spec_rule


def test_crew_cards_clip_their_boundary_without_clipping_content_slots():
    crew = (ROOT / "static" / "css" / "crew.css").read_text(encoding="utf-8")
    card_start = crew.index(".crew-flow .crew-card {")
    card_rule = crew[card_start:crew.index("}", card_start)]
    assert "height: auto;" in card_rule
    assert "overflow: clip;" in card_rule
    for selector in (".crew-card-main", ".crew-summary", ".crew-artifact-preview"):
        start = crew.index(selector)
        rule = crew[start:crew.index("}", start)]
        assert "overflow: visible;" not in rule
    assert "text-overflow: ellipsis;" in crew


def test_screening_room_has_edit_screen_deliver_phases_and_compact_quality_details():
    assert 'class="deliver-phase deliver-phase--edit"' in INDEX
    assert 'class="deliver-phase-heading deliver-phase-heading--screen"' in INDEX
    assert 'class="deliver-phase-heading deliver-phase-heading--deliver"' in INDEX
    assert 'class="deliver-quality-details"' in INDEX
    assert ".deliver-phase-heading" in DELIVER
    assert ".deliver-quality-details" in DELIVER
