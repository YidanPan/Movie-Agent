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


def test_audit_record_documents_preserved_and_retired_patterns():
    audit = ROOT / "docs" / "DESIGN_AUDIT.md"
    text = audit.read_text(encoding="utf-8")
    assert "Baseline audit" in text
    assert "Motion rules" in text
    assert "Production Desk" in text


def test_frontend_assets_are_versioned_and_not_cached():
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    assert "/static/style.css?v=" in INDEX
    assert "/static/app.js?v=" in INDEX
    assert "prevent_stale_frontend_cache" in server
    assert 'response.headers["Cache-Control"] = "no-store, max-age=0"' in server
