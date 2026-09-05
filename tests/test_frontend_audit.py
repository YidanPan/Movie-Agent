from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
MODULE_STATE = (ROOT / "static" / "js" / "state.js").read_text(encoding="utf-8")
MODULE_DELIVER = (ROOT / "static" / "js" / "deliver.js").read_text(encoding="utf-8")
MODULE_STORYBOARD = (ROOT / "static" / "js" / "storyboard.js").read_text(encoding="utf-8")
MODULE_THEME = (ROOT / "static" / "js" / "theme.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
REFINEMENT = (ROOT / "static" / "css" / "interaction-refinement.css").read_text(encoding="utf-8")
BIBLE = (ROOT / "static" / "css" / "production-bible.css").read_text(encoding="utf-8")
CREW = (ROOT / "static" / "css" / "crew.css").read_text(encoding="utf-8")


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


def test_theme_toggle_names_and_icons_describe_the_destination_mode():
    theme = MODULE_THEME
    assert 'const next = isLight ? "Screening Room" : "Production Desk";' in theme
    assert 'const nextShort = isLight ? "SCREENING" : "DESK";' in theme
    assert 'aria-label", `Switch to ${next}`' in theme
    assert 'icon.dataset.target = isLight ? "screening" : "desk"' in theme
    assert ".theme-toggle-icon[data-target=\"screening\"]" in CSS
    assert ".theme-toggle-icon[data-target=\"desk\"]" in CSS
    assert ".theme-toggle:hover" in CSS
    assert ".theme-toggle:focus-visible" in CSS
    assert "box-shadow: none" in CSS
    assert "theme-toggle-knob" not in CSS
    assert "data-theme-action" not in CSS
    assert "data-theme-action" not in theme
    assert "is-sun" not in theme
    assert "🌞" not in INDEX and "🌙" not in INDEX


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


def test_workspace_scroll_reveal_never_blurs_or_scales_information_panels():
    assert "@keyframes workspace-scroll-reveal" in CSS
    assert "animation-range: entry 0% cover 20%" in CSS
    assert "workspace .panel" in REFINEMENT
    assert "filter: none !important" in REFINEMENT
    assert "backdrop-filter: none !important" in REFINEMENT
    assert "translate: 0 0" in REFINEMENT
    assert "animation-timeline: auto !important" in REFINEMENT

    workspace_keyframes = CSS.split("@keyframes workspace-scroll-reveal", 1)[1].split("@supports", 1)[0]
    assert "filter:" not in workspace_keyframes
    assert "scale(" not in workspace_keyframes

    shared_scroll_support = CSS.split("@supports (animation-timeline: view())", 1)[1].split("}", 1)[0]
    assert ".workspace .panel" not in shared_scroll_support


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


def test_landing_focus_word_is_gold_before_hero_motion_starts():
    assert 'id="critical-hero-accent"' in INDEX
    assert "--hero-accent-first-paint: #d0a04a" in INDEX
    assert "html[data-theme=\"light\"] { --hero-accent-first-paint: #9b6c31; }" in INDEX
    assert ".landing-line--focus em { color: var(--accent-token); }" in CSS
    assert "animation: title-ember" not in CSS
    assert "@keyframes title-ember" not in CSS
    assert "0%, 48% { color: var(--text)" not in CSS
    assert "style.color" not in APP


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


def test_production_bible_is_a_quiet_reading_workspace():
    assert 'class="manual-reading-grid"' in INDEX
    assert 'class="manual-navigation"' in INDEX
    assert 'data-manual-nav-tab="brief"' in INDEX
    assert 'data-manual-nav-tab="quality"' in INDEX
    assert 'data-manual-nav-tab="visual"' in INDEX
    assert 'production-bible.css?v=' in INDEX
    assert ".manual-reading-grid" in BIBLE
    assert "--manual-content-width: 860px" in BIBLE
    assert "max-width: var(--manual-content-width)" in BIBLE
    assert "font-family: var(--sans)" in BIBLE
    assert "font-size: var(--manual-body-size)" in BIBLE
    assert "line-height: var(--manual-body-leading)" in BIBLE
    assert "box-shadow: none" in BIBLE
    assert ".manual-document .tab-body" not in REFINEMENT


def test_production_bible_summary_separates_title_and_logline():
    assert 'brief["片名"] || brief["标题"] || "未命名短片"' in APP
    assert 'class="manual-project-logline"' in APP
    assert 'label: "DELIVER / AI EDIT"' not in APP
    assert 'label: "PREVIS / LOCKED"' in APP


def test_frontend_assets_are_versioned_and_not_cached():
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    assert "/static/style.css?v=" in INDEX
    assert "/static/js/app.js?v=" in INDEX
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
    assert 'data-audio-advanced-toggle' in INDEX
    assert "SHOW MIX CONTROLS" in INDEX
    assert "MASTER · -14 LUFS" in APP


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
    assert "ORIGIN</span><span class=\"feature-stage-kind mono\">GREENLIGHT" in INDEX
    assert "HANDOFF</span><span class=\"feature-stage-kind mono\">CREW ASSEMBLY" in INDEX
    assert "MASTER</span><span class=\"feature-stage-kind mono\">DELIVERY" in INDEX
    assert INDEX.count('class="feature-card production-stage-card reveal"') == 3
    assert "marquee-group" not in INDEX
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in CSS
    assert "grid-auto-rows: 1fr" in CSS
    assert "min-height: 438px" in CSS
    assert "production-ruler-line" in CSS


def test_production_route_node_cards_use_readable_three_part_layout():
    assert 'class="crew-card-header"' in APP
    assert 'class="crew-card-main"' in APP
    assert 'class="crew-card-footer"' in APP
    assert 'class="crew-artifact-preview artifact-preview"' in APP
    assert 'class="artifact-action type-control"' in APP
    assert 'card.setAttribute("role", "group")' in APP
    assert 'card.dataset.inspectorOpen = "false"' in APP
    assert 'card.dataset.inspectorOpen = "true"' in APP
    assert 'crew-card[aria-expanded="true"]' not in APP
    assert 'crew-card[aria-expanded="true"]' not in CSS
    assert "min-height: 340px" in CREW
    assert "overflow: visible" in CREW
    assert "margin-top: auto" in CREW
    assert "-webkit-line-clamp: 2" in CREW
    assert "artifact-action" in CREW


def test_production_route_summaries_are_structured_and_metadata_is_not_truncated():
    assert "headline:" in APP
    assert "primary:" in APP
    assert "secondary:" in APP
    assert "function renderCrewSummary" in APP
    for route_token in ("IDEA", "BRIEF", "SCRIPT", "VISUAL", "SHOTS", "QC", "MEDIA", "FINAL"):
        assert f'input: "{route_token}"' in APP or f'output: "{route_token}"' in APP
    for role_copy in ("主题 · 叙事", "剧本 · 台词 · 字幕", "角色 · 场景 · 风格", "镜头 · 调度", "连续性 · 风险", "生成 · 重试", "粗剪 · 混音 · 交付"):
        assert role_copy in APP
    assert "剧本 · 台词本 · 字幕" not in APP
    assert "角色 · 场景 · 风格 · 声音" not in APP
    assert "READY TO RUN" not in APP
    assert "NEXT IN LINE" not in APP
    assert "NEXT · RENDER QUEUE" not in APP
    assert 'IN · ${esc(def.input)}' not in APP
    assert 'OUT · ${esc(def.output)}' not in APP
    assert "SCRIPT / ${" not in APP
    assert "STYLE / ${" not in APP
    assert "overflow: visible" in CREW
    assert "text-overflow: clip" in CREW
    assert ".crew-summary.is-natural .crew-summary-secondary" in CREW


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
    assert 'if (finalApproved) states.deliver = "done";' in MODULE_STATE


def test_light_screening_room_keeps_content_sharp_and_monitor_readable():
    assert 'html[data-theme="light"] body[data-design="archive-console"] .screening-panel' in CSS
    assert ".screening-panel .rough-cut-placeholder" in CSS
    assert "background: var(--desk-monitor-surface)" in CSS
    assert "background-image: none" in CSS
    assert "filter: none" in CSS
    assert "backdrop-filter: none" in CSS
    assert "text-shadow: none" in CSS
    assert "FINAL CUT NOT GENERATED" in INDEX
    assert "media-quality-20260904" in INDEX


def test_video_quality_tiers_keep_screening_preview_separate_from_final_master():
    assert 'id="deliver-quality-readout"' in INDEX
    assert 'id="btn-normalize-resolution"' in INDEX
    assert 'screening-preview' in MODULE_DELIVER
    assert "function renderMediaQuality" in APP
    assert "Final Export 只使用 Final Master" in APP
    assert "/api/projects/{project_id}/screening-preview" in (ROOT / "server.py").read_text(encoding="utf-8")
    assert "LOW RES SOURCE" in (ROOT / "movie_agent/services/media_quality.py").read_text(encoding="utf-8")
    assert 'data-quality-mode="auto"' in INDEX
    assert 'data-quality-mode="proxy"' in INDEX
    assert 'data-quality-mode="screening"' in INDEX
    assert 'data-quality-mode="original"' in INDEX
    assert "object-fit: contain" in REFINEMENT
    assert "transform: none !important" in REFINEMENT
    assert "filter: none !important" in REFINEMENT


def test_frontend_domain_modules_own_migrated_logic_and_legacy_waits_for_them():
    assert "createThemeController" in MODULE_THEME
    assert "formatShotDuration" in MODULE_STORYBOARD
    assert "MovieAgentModules.storyboard.shotReady" in APP
    assert "MovieAgentModules.theme.createThemeController" in APP
    assert "MovieAgentModules.api.requestJSON" in APP
    assert "document.addEventListener(\"DOMContentLoaded\", init" in APP
    assert 'await import("../app.js?v=ui-20260905-p5")' in (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert '<script src="/static/app.js?v=ui-20260905-p2"></script>' not in INDEX


def test_frontend_consumes_backend_pipeline_state_and_saved_event():
    assert "pipeline_state?.pipeline" in MODULE_STATE
    assert "function canonicalProjectState" in MODULE_STATE
    assert 'event.type === "project_saved"' in APP
    assert 'appendCrewStatus("system", "SAVED"' in APP


def test_disconnect_safe_job_ledger_is_visible_without_replacing_sse():
    assert 'id="crew-recovery-readout"' in INDEX
    assert 'id="export-preflight"' in INDEX
    assert "function refreshJobStatus" in APP
    assert "function scheduleJobPolling" in APP
    assert "/api/projects/${encodeURIComponent(requestedProject)}/job" in APP
    assert "RESUME AVAILABLE" in APP
    assert "p5-20260904" in INDEX
