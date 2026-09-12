from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
APP = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
MODULE_STATE = (ROOT / "static" / "js" / "state.js").read_text(encoding="utf-8")
MODULE_DELIVER = (ROOT / "static" / "js" / "deliver.js").read_text(encoding="utf-8")
MODULE_STORYBOARD = (ROOT / "static" / "js" / "storyboard.js").read_text(encoding="utf-8")
MODULE_THEME = (ROOT / "static" / "js" / "theme.js").read_text(encoding="utf-8")
MODULE_MOTION = (ROOT / "static" / "js" / "motion.js").read_text(encoding="utf-8")
MODULE_PRODUCTION_ACTIONS = (ROOT / "static" / "js" / "production-actions.js").read_text(encoding="utf-8")
MOTION_CSS = (ROOT / "static" / "css" / "motion.css").read_text(encoding="utf-8")
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
    layout = (ROOT / "static" / "css" / "layout.css").read_text(encoding="utf-8")
    assert "--content-max: 1240px" in layout
    assert "width: min(100%, var(--content-max))" in layout
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
    assert "--manual-content-width: min(100%, 980px)" in BIBLE
    assert "max-width: var(--manual-content-width)" in BIBLE
    assert "font-family: var(--sans)" in BIBLE
    assert "font-size: var(--manual-body-size)" in BIBLE
    assert "line-height: var(--manual-body-leading)" in BIBLE
    assert "box-shadow: none" in BIBLE
    assert ".visual-summary-grid" in BIBLE
    assert ".visual-assets-section" in BIBLE
    assert ".visual-spec-details" in BIBLE
    assert ".manual-document .tab-body" not in REFINEMENT


def test_production_bible_summary_separates_title_and_logline():
    assert 'brief["片名"] || brief["标题"] || "未命名短片"' in APP
    assert 'class="manual-project-logline"' in APP
    assert 'label: "DELIVER / AI EDIT"' not in APP
    assert 'label: "PREVIS / LOCKED"' in APP


def test_dialogue_lock_keeps_silent_projects_lockable_and_surfaces_backend_errors():
    assert "const lockDisabled = !dialogue.length && !allSilent;" in APP
    assert "function projectHasOnlySilentSpeech" in APP
    assert "if (assets.dialogueBook.length || !silentOnly)" in APP
    assert "payload.error || `HTTP ${response.status}`" in APP


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


def test_public_demo_capability_contract_gates_media_controls_but_keeps_replan():
    assert 'function publicCapabilityAllowed(capability)' in APP
    assert 'publicCapabilityAllowed("shot_render")' in APP
    assert 'publicCapabilityAllowed("audio_render")' in APP
    assert 'publicCapabilityAllowed("audio_upload")' in APP
    assert 'publicCapabilityAllowed("audio_replan")' in APP
    assert 'capabilities' in (ROOT / "server.py").read_text(encoding="utf-8")


def test_sound_console_timeline_is_media_synced_and_semantically_sized():
    assert "syncAudioTimeline(media.currentTime" in APP
    assert "setAudioTimelinePlaybackState(true)" in APP
    assert "setAudioTimelinePlaybackState(false)" in APP
    assert "audio-timeline-stage" in CSS
    assert "min-height: 176px" in CSS
    assert "min-height: 258px" in CSS
    assert "{ length: 48 }" in APP


def test_edit_timeline_labels_have_separate_flexible_regions():
    assert 'class="timeline-shot-no"' in APP
    assert 'class="timeline-mode"' in APP
    assert 'class="timeline-resize-handle"' in APP
    assert ".timeline-segment > .timeline-shot-no" in CSS
    assert "flex: 0 0 auto" in CSS
    assert ".timeline-segment > .timeline-mode" in CSS
    assert "text-overflow: ellipsis" in CSS
    assert "white-space: nowrap" in CSS


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
    assert 'class="crew-identity"' in APP
    assert '<h3 class="crew-name">' in APP
    assert '<span class="crew-en type-system-meta">' in APP
    assert '${esc(def.index)} / NODE' not in APP
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
    assert "writing-mode: horizontal-tb" in CREW
    assert "word-break: break-all" not in CREW
    assert "overflow-wrap: anywhere" not in CREW
    assert ".crew-flow .crew-card.done { opacity: 0.72" not in CSS
    assert ".crew-flow .crew-card .crew-en" not in CSS
    assert 'body[data-design="archive-console"] .crew-flow .crew-card .crew-indexline' not in CSS


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
    assert "grid-template-columns: minmax(190px, max-content) minmax(0, 1fr) max-content;" in CSS
    assert ".header-left { justify-self: start" in CSS
    assert ".header-center" in CSS and "justify-self: stretch" in CSS
    assert "overflow: hidden;" in CSS
    assert "max-width: 100%;" in CSS
    assert "flex-wrap: nowrap;" in CSS
    assert "body[data-design=\"archive-console\"] .header-center { display: none; }" in CSS
    assert "min-width: 72px" in CSS
    assert "min-width: 92px" in CSS
    assert "flex: 0 0 138px" in CSS
    assert 'body[data-view="landing"] .pipeline { visibility: hidden' in CSS


def test_global_header_preserves_full_build_identity_without_rendering_a_long_sha():
    assert "function formatRuntimeBuild(build)" in APP
    assert "fullBuild.slice(0, 7).toUpperCase()" in APP
    assert 'fullBuild.toLowerCase() === "dev"' in APP
    assert "els.runtimeBuild.textContent = `BUILD ${shortBuild}`" in APP
    assert 'els.runtimeBuild.title = `Build ${fullBuild}`' in APP
    assert 'els.runtimeBuild.setAttribute("aria-label", `Build ${fullBuild}`)' in APP
    assert "els.runtimeBuild.textContent = `BUILD ${build.toUpperCase()}`" not in APP
    assert "@media (max-width: 1320px)" in CSS
    assert "body[data-design=\"archive-console\"] .runtime-build { display: none; }" in CSS
    assert "@media (max-width: 1199px)" in CSS


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


def test_final_cut_workspace_owns_responsive_two_column_layout():
    assert 'class="final-player-stage"' in INDEX
    assert 'class="final-preview final-compare"' in INDEX
    assert 'class="deliver-preview-quality"' in INDEX
    assert 'class="final-look-step final-look-disclosure"' in INDEX
    assert 'id="final-look-fine-tune"' in INDEX
    assert 'id="final-look-fine-tune" open' not in INDEX
    deliver = (ROOT / "static" / "css" / "deliver.css").read_text(encoding="utf-8")
    assert "grid-template-columns: minmax(0, 1fr) minmax(340px, 380px);" in deliver
    assert "@media (max-width: 1179px)" in deliver
    assert "grid-template-columns: 1fr;" in deliver
    assert ".final-preview {" in deliver
    assert ".final-player-stage {" in deliver
    assert "aspect-ratio: 16 / 9;" in deliver
    assert "aspect-ratio: auto;" in deliver
    assert "contain: paint;" in deliver
    assert "writing-mode: horizontal-tb;" in deliver
    assert "deliver-screening-layout" not in APP
    assert "deliver-inspector" not in deliver
    assert 'if (finalApproved) states.deliver = "done";' in MODULE_STATE


def test_text_collision_contract_keeps_readable_copy_in_flow():
    layout = (ROOT / "static" / "css" / "layout.css").read_text(encoding="utf-8")
    deliver = (ROOT / "static" / "css" / "deliver.css").read_text(encoding="utf-8")

    assert ".crew-flow .crew-en" in CREW
    assert ".crew-flow .crew-role" in CREW
    assert ".crew-flow .crew-summary-headline" in CREW
    assert "white-space: normal;" in CREW
    assert "max-height: 128px" not in CREW
    assert ".crew-artifact-preview" in CREW and "height: auto;" in CREW
    assert ".crew-node-route" in CREW and ".crew-route-input" in CREW
    assert "flex-wrap: wrap;" in layout
    assert "@media (max-width: 900px)" in layout
    assert ".crew-flow-head > :first-child" in layout
    assert "flex: 0 1 auto;" in layout
    assert "grid-template-columns: minmax(0, 1fr);" in deliver
    assert "max-width: 100%;" in deliver
    assert "position: absolute;" in deliver
    assert "inset: 0;" in deliver


def test_production_bible_nested_values_use_vertical_detail_rows():
    assert ".visual-detail .production-readable-dl .production-readable-dl" in BIBLE
    assert ".visual-detail .production-readable-dl .production-readable-dl > div" in BIBLE
    assert "grid-template-columns: 1fr;" in BIBLE


def test_workspace_layout_does_not_hide_overflow_or_scale_the_document():
    layout = (ROOT / "static" / "css" / "layout.css").read_text(encoding="utf-8")
    assert "html,\nbody { overflow-x: clip; }" not in layout
    assert ".view-studio { overflow-x: clip; }" in layout
    assert "zoom:" not in layout
    assert "transform: scale(" not in layout


def test_crew_route_uses_readable_desktop_breakpoints():
    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in CREW
    assert "@media (max-width: 1199px)" in CREW
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in CREW
    assert "@media (max-width: 899px)" in CREW
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in CREW
    assert "@media (max-width: 599px)" in CREW
    assert "grid-template-columns: repeat(7" not in CREW


def test_light_screening_room_keeps_content_sharp_and_monitor_readable():
    assert 'html[data-theme="light"] body[data-design="archive-console"] .screening-panel' in CSS
    assert ".screening-panel .rough-cut-placeholder" in CSS
    assert "background: var(--desk-monitor-surface)" in CSS
    assert "background-image: none" in CSS
    assert "filter: none" in CSS
    assert "backdrop-filter: none" in CSS
    assert "text-shadow: none" in CSS
    assert "FINAL CUT NOT GENERATED" in INDEX
    assert 'data-quality-mode="auto"' in INDEX


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
    assert "MovieAgentModules.storyboard.shotCapabilities" in APP
    assert "MovieAgentModules.theme.createThemeController" in APP
    assert "MovieAgentModules.api.requestJSON" in APP
    assert "document.addEventListener(\"DOMContentLoaded\", init" in APP
    assert 'await import(`../app.js?v=${encodeURIComponent(build)}`)' in (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert '<script src="/static/app.js?v=ui-20260905-p2"></script>' not in INDEX


def test_signature_motion_is_state_driven_and_reduced_motion_safe():
    assert 'motion.css?v=__MOVIE_AGENT_BUILD_VALUE__' in INDEX
    assert "MOTION_TOKENS" in MODULE_MOTION
    assert "triggerDarkroomDevelopment" in MODULE_MOTION
    assert "runSharedFrameTransition" in MODULE_MOTION
    assert "sceneAmbientForShot" in MODULE_STORYBOARD
    assert "initFilmGateFocus" in MODULE_STORYBOARD
    assert 'data-shared-frame="shot-frame"' in APP
    assert "triggerDarkroomDevelopment" in APP
    assert "--director-light-intensity" in APP
    assert "--scene-ambient-rgb" in MOTION_CSS
    assert "scroll-snap-type: x proximity" in MOTION_CSS
    assert "filter: blur" not in MOTION_CSS
    assert "@media (prefers-reduced-motion: reduce)" in MOTION_CSS
    assert "@media (hover: none), (pointer: coarse)" in MOTION_CSS


def test_frontend_consumes_backend_pipeline_state_and_saved_event():
    assert "pipeline_state?.pipeline" in MODULE_STATE
    assert "function canonicalProjectState" in MODULE_STATE
    assert 'event.type === "project_saved"' in APP
    assert 'appendCrewStatus("system", "SAVED"' in APP


def test_production_actions_have_a_registered_frontend_contract():
    backend = (ROOT / "movie_agent" / "services" / "readiness.py").read_text(encoding="utf-8")
    server = (ROOT / "server.py").read_text(encoding="utf-8")
    for action in (
        "START_RENDER", "RENDER_SHOT", "REPLAN_SHOT", "START_AI_EDIT", "APPROVE_FINAL_CUT",
        "GENERATE_FINAL_MASTER", "EXPORT", "APPROVE_PREVIS", "REVIEW_SHOT", "REVIEW_VISUAL_BIBLE",
        "OPEN_REFERENCE_BANK", "REVIEW_AUDIO_TIMELINE", "OPEN_SOUND", "OPEN_RENDER_DIAGNOSTICS",
        "REVIEW_RENDER_DIAGNOSTICS", "LOCK_DIALOGUE", "VERIFY_FINAL_MASTER", "REVIEW_DELIVERY_PREFLIGHT",
    ):
        assert f'    {action}:' in APP
        assert f'"{action}"' in backend
    assert "production_action_contract" in server
    assert "productionActionLabel(action, project" in MODULE_PRODUCTION_ACTIONS
    assert "registerProductionActionHandlers" in MODULE_PRODUCTION_ACTIONS
    assert "ACTION_HANDLERS" in MODULE_PRODUCTION_ACTIONS
    assert "scope:" not in MODULE_PRODUCTION_ACTIONS
    assert "kind:" not in MODULE_PRODUCTION_ACTIONS
    assert "ACTION UNAVAILABLE" in MODULE_PRODUCTION_ACTIONS
    assert "/previs/approve" in APP
    assert "shot_actions" in MODULE_STORYBOARD


def test_disconnect_safe_job_ledger_is_visible_without_replacing_sse():
    assert 'id="crew-recovery-readout"' in INDEX
    assert 'id="export-preflight"' in INDEX
    assert "function refreshJobStatus" in APP
    assert "function scheduleJobPolling" in APP
    assert "/api/projects/${encodeURIComponent(requestedProject)}/job" in APP
    assert "RESUME AVAILABLE" in APP
    assert INDEX.count("?v=__MOVIE_AGENT_BUILD_VALUE__") >= 14


def test_refresh_button_reloads_the_studio_page_once():
    assert 'id="btn-refresh"' in INDEX
    assert "function refreshStudioPage()" in APP
    assert APP.count('els.btnRefresh.addEventListener("click", refreshStudioPage);') == 1
    refresh_function = APP.split("function refreshStudioPage()", 1)[1].split("async function loadSelectedProject", 1)[0]
    assert "window.location.reload()" in refresh_function
    assert "fetch(" not in refresh_function
    assert "localStorage" not in refresh_function
    assert "logout" not in refresh_function
