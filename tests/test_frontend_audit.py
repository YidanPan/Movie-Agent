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
    assert ".deliver-ready-line strong" in CSS
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


def test_sound_console_uses_progressive_disclosure_and_track_inspector():
    assert 'class="audio-focus-grid"' in INDEX
    assert 'class="audio-brief-disclosure"' in INDEX
    assert 'class="audio-mixer-layout"' in INDEX
    assert 'data-audio-inspector' in INDEX
    assert 'data-deliver-emotional-arc' in INDEX
    assert "function audioTrackParamsPayload()" in APP
    assert "function syncAudioInspectors" in APP
    assert "function handleAudioInspectorInput" in APP
    assert "track_params" in APP
    assert "audio-cue-marker" in APP
    assert "audio-wave-pulse" in CSS
    assert ".audio-timeline.is-playing" in CSS
    assert "font: 600 11px/1.1 var(--mono)" in CSS


def test_sound_console_timeline_is_media_synced_and_semantically_sized():
    assert "syncAudioTimeline(media.currentTime" in APP
    assert "setAudioTimelinePlaybackState(true)" in APP
    assert "setAudioTimelinePlaybackState(false)" in APP
    assert "audio-timeline-stage" in CSS
    assert "min-height: 176px" in CSS
    assert "min-height: 258px" in CSS
    assert "{ length: 48 }" in APP


def test_homepage_production_route_uses_three_equal_semantic_stages():
    assert 'class="production-route"' in INDEX
    assert 'class="production-ruler"' in INDEX
    assert "production-stage-list" in INDEX
    assert 'class="agent-route-mini"' in INDEX
    assert "delivery-output-stack" in INDEX
    assert "INPUT" in INDEX and "PROCESS" in INDEX and "OUTPUT" in INDEX
    assert "GREENLIGHT / INPUT" in INDEX
    assert "CREW ASSEMBLY / PROCESS" in INDEX
    assert "DELIVERY / OUTPUT" in INDEX
    assert INDEX.count('class="feature-card production-stage-card reveal"') == 3
    assert "marquee-group" not in INDEX
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in CSS
    assert "grid-auto-rows: 1fr" in CSS
    assert "min-height: 438px" in CSS
    assert "production-ruler-line" in CSS


def test_global_header_keeps_left_and_right_tracks_stable_when_pipeline_is_hidden():
    assert 'class="global-header-inner"' in INDEX
    assert 'class="header-left"' in INDEX
    assert 'class="header-center"' in INDEX
    assert 'class="header-right"' in INDEX
    assert 'class="sound-toggle mono type-control"' in INDEX
    assert 'class="theme-toggle mono type-control"' in INDEX
    assert 'class="rec-clock mono"' in INDEX
    assert "grid-template-columns: minmax(190px, max-content) minmax(0, 1fr) 334px;" in CSS
    assert ".header-left { justify-self: start" in CSS
    assert ".header-center { justify-self: center" in CSS
    assert ".header-right" in CSS and "justify-self: end" in CSS
    assert "min-width: 72px" in CSS
    assert "min-width: 92px" in CSS
    assert "flex: 0 0 138px" in CSS
    assert 'body[data-view="landing"] .pipeline { visibility: hidden' in CSS


def test_production_desk_monitor_is_embedded_hardware_with_collapsed_activity():
    assert 'class="monitor-hardware"' in INDEX
    assert 'class="monitor-activity"' in INDEX
    assert 'id="monitor-activity-recent"' in INDEX
    assert "--desk-monitor-surface: #28231d" in CSS
    assert "--desk-monitor-surface-deep: #242019" in CSS
    assert "--desk-monitor-frame" in CSS
    assert "--desk-monitor-status-ready" in CSS
    assert 'html[data-theme="light"] body[data-design="archive-console"] .monitor-hardware' in CSS
    assert ".monitor-activity[open] .activity-chevron" in CSS
    assert 'lines.slice(-3).join("\\n")' in APP
    assert ".cta--render:disabled" in CSS
    assert "pointer-events: none" in CSS
    assert "margin: 16px 4px 4px" in CSS
    assert "--desk-monitor-disabled: #b1a493" in CSS


def test_final_cut_workspace_is_clipped_two_column_inspector_and_progressive():
    assert 'class="final-preview final-compare"' in INDEX
    assert 'class="final-look-step final-look-disclosure"' in INDEX
    assert 'id="final-look-fine-tune"' in INDEX
    assert 'id="final-look-fine-tune" open' not in INDEX
    assert "grid-template-columns: minmax(0, 1.7fr) minmax(300px, 1fr);" in CSS
    assert "gap: clamp(24px, 2.2vw, 32px);" in CSS
    assert ".final-preview {" in CSS
    assert "aspect-ratio: 16 / 9;" in CSS
    assert "contain: paint;" in CSS
    assert "const canStartAiEdit = showSummary" in APP
    assert 'if (finalApproved) states.deliver = "done";' in APP
