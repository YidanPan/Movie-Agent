from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "style.css").read_text(encoding="utf-8")


def test_design_dials_and_semantic_theme_tokens_are_present():
    assert "--design-variance: 7" in CSS
    assert "--motion-intensity: 7" in CSS
    assert "--visual-density: 5" in CSS
    assert "--screening-surface-0" in CSS
    assert "--desk-surface-0" in CSS
    assert "--screening-text-strong: #f0ebe2" in CSS.lower()
    assert "--desk-text-strong: #352e27" in CSS.lower()
    assert "--desk-border-soft: #d8d0c3" in CSS.lower()
    assert "html[data-theme=\"light\"]" in CSS


def test_page_uses_three_font_roles_and_native_cursor():
    assert '--serif:' in CSS and '--sans:' in CSS and '--mono:' in CSS
    assert "font-family: var(--sans)" in CSS
    assert "font-family: var(--mono)" in CSS
    assert "font-family: var(--serif)" in CSS
    assert "director-cursor" not in INDEX
    assert "initCustomCursor" not in APP
    assert 'body[data-design="archive-console"] .panel-head h2' in CSS
    assert 'body[data-design="archive-console"] .manual-panel .dialogue-book-head h3' in CSS


def test_page_copy_does_not_ship_em_dash_or_glass_backdrop():
    assert "—" not in INDEX
    assert "—" not in APP
    assert "body[data-design=\"archive-console\"] .topbar" in CSS
    assert "body[data-design=\"archive-console\"] .drawer-backdrop" in CSS
    assert "backdrop-filter: none" in CSS
    assert "editorial-scroll-unveil" in CSS


def test_readability_pass_covers_production_surfaces_and_structured_values():
    assert "Typography / alignment polish" in CSS
    assert "productionValueMarkup" in APP
    assert "crew-readable-dl" in APP
    assert ".visual-spec-copy" in CSS
    assert ".crew-radio .radio-msg" in CSS
    assert ".deliver-video-meta strong" in CSS
    assert "width: min(1180px, calc(100vw - 64px))" in CSS
    assert "#26211b" in CSS.lower()
    assert "#5d4930" in CSS.lower()


def test_landing_hero_has_standby_state_and_responsive_proximity_feedback():
    assert "landing-reveal-standby" in INDEX
    assert "MONITOR STANDBY" in INDEX
    assert INDEX.count('class="landing-line') >= 3
    assert "targetTitleFocus" in APP
    assert "targetCtaFocus" in APP
    assert "targetRevealFocus" in APP
    assert "--hero-pointer-presence" in CSS
    assert "--hero-title-focus" in CSS
    assert "--hero-reveal-focus" in CSS
    assert "calc(100dvh - 70px)" in CSS


def test_semantic_micro_type_system_separates_five_small_text_roles():
    for role in ("type-system-meta", "type-ui-label", "type-helper", "type-control", "type-status"):
        assert f".{role}" in CSS
    assert "--type-meta-size: 12px" in CSS
    assert "--type-label-size: 14px" in CSS
    assert "--type-helper-size: 14px" in CSS
    assert "--type-control-size: 14px" in CSS
    assert "--type-status-size: 14px" in CSS
    assert "class=\"idea-console-label type-ui-label\"" in INDEX
    assert "class=\"idea-helper type-helper\"" in INDEX
    assert "class=\"mode-note type-status\"" in INDEX
    assert 'button.className = "style-card type-control"' in APP
    assert "class=\"crew-summary type-helper\"" in APP
    assert "letter-spacing: var(--type-label-track)" in CSS
    assert "letter-spacing: var(--type-helper-track)" in CSS


def test_audit_record_documents_preserved_and_retired_patterns():
    audit = ROOT / "docs" / "DESIGN_AUDIT.md"
    text = audit.read_text(encoding="utf-8")
    assert "Baseline audit" in text
    assert "Motion rules" in text
    assert "Production Desk" in text
    assert "Typography / alignment polish" in text
    assert "Homepage Hero polish" in text


def test_frontend_assets_are_versioned_and_not_cached():
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    assert "/static/style.css?v=" in INDEX
    assert "/static/app.js?v=" in INDEX
    assert "prevent_stale_frontend_cache" in server
    assert 'response.headers["Cache-Control"] = "no-store, max-age=0"' in server
