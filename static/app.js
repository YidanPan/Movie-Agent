/* ═══════════════════════════════════════════════════════════════
   Movie-Agent · AI 片场 · 交互层
   第一幕 开机 / 第二幕 剧组集结 / 第三幕 制片工作区
   ═══════════════════════════════════════════════════════════════ */

"use strict";

// The ES modules own pure domain logic; this file remains the DOM adapter.
// The shared object is created before the deferred module boot so both sides
// reference the same registry when the browser reaches DOMContentLoaded.
const MovieAgentModules = window.MovieAgentModules || (window.MovieAgentModules = {});

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const els = {
  clock: $("#clock"),
  viewLanding: $("#view-landing"),
  viewStudio: $("#view-studio"),
  btnEnter: $("#btn-enter"),
  brandHome: $("#brand-home"),
  shutter: $(".shutter"),
  btnSound: $("#btn-sound"),
  themeToggle: $("#theme-toggle"),
  themeWash: $("#theme-transition-wash"),
  themeColor: $("meta[name='theme-color']"),
  monitorTc: $("#monitor-tc"),
  editTimeline: $("#edit-timeline"),
  timelineTotal: $("#timeline-total"),
  creditsRoll: $("#credits-roll"),
  premiere: $("#premiere"),
  premiereTitle: $("#premiere-title"),
  premiereMeta: $("#premiere-meta"),
  btnPremierePlay: $("#btn-premiere-play"),
  btnPremiereSkip: $("#btn-premiere-skip"),
  favicon: $("#favicon"),
  idea: $("#idea"),
  slate: $("#slate"),
  ideaError: $("#idea-error"),
  creationError: $("#creation-error"),
  ideaCounter: $("#idea-counter"),
  engineLamp: $(".engine-lamp"),
  duration: $("#duration"),
  tcValue: $("#tc-value"),
  styleCards: $("#style-cards"),
  styleCurrent: $("#style-current"),
  btnStart: $("#btn-start"),
  modeNote: $("#mode-note"),
  librarySelect: $("#library-select"),
  btnLoad: $("#btn-load"),
  btnRefresh: $("#btn-refresh"),
  actCrew: $("#act-crew"),
  actWorkspace: $("#act-workspace"),
  crewFlow: $("#crew-flow"),
  crewFlowProgress: $("#crew-flow-progress"),
  crewMeta: $("#crew-meta"),
  crewRecoveryReadout: $("#crew-recovery-readout"),
  crewRadioWrap: $(".crew-radio-wrap"),
  crewRadioToggle: $("#crew-radio-toggle"),
  crewRadioSummary: $("#crew-radio-summary"),
  pipeline: $("#pipeline"),
  crewRadio: $("#crew-radio"),
  filmstrip: $("#filmstrip"),
  filmstripViewport: $("#filmstrip-viewport"),
  filmstripMeta: $("#filmstrip-meta"),
  projectIdLabel: $("#project-id-label"),
  shotMap: $("#shot-map"),
  monitorBar: $("#monitor-bar"),
  monitorShot: $("#monitor-shot"),
  monitorPct: $("#monitor-pct"),
  monitorDesc: $("#monitor-desc"),
  renderRec: $("#render-rec"),
  btnRender: $("#btn-render"),
  renderNote: $("#render-note"),
  renderReadiness: $("#render-readiness"),
  shotsReady: $("#shots-ready"),
  btnAiEdit: $("#btn-ai-edit"),
  editStatus: $("#edit-status"),
  logFeed: $("#log-feed"),
  monitorActivityRecent: $("#monitor-activity-recent"),
  manualTabs: $("#manual-tabs"),
  manualNavigation: $(".manual-navigation"),
  manualBody: $("#manual-body"),
  manualSummary: $("#manual-summary"),
  activitySummary: $("#activity-summary"),
  activityBody: $("#activity-body"),
  screen: $("#screen"),
  finalCompare: $("#final-compare"),
  finalVideo: $("#final-video"),
  finalVideoAfter: $("#final-video-after"),
  finalCompareAfter: $("#final-compare-after"),
  finalCompareDivider: $("#final-compare-divider"),
  editConsoleNote: $("#edit-console-note"),
  audioDesignConsole: $("#audio-design-console"),
  audioDesignState: $("#audio-design-state"),
  audioModeSwitch: $("#audio-mode-switch"),
  audioUploadRow: $("#audio-upload-row"),
  musicUpload: $("#music-upload"),
  musicUploadNote: $("#music-upload-note"),
  musicBriefSource: $("#music-brief-source"),
  musicBriefVersion: $("#music-brief-version"),
  musicBriefGrid: $("#music-brief-grid"),
  emotionalArc: $("#emotional-arc"),
  musicBriefDirection: $("#music-brief-direction"),
  musicBriefInstruments: $("#music-brief-instruments"),
  audioTrackList: $("#audio-track-list"),
  smartDuckingToggle: $("#smart-ducking-toggle"),
  smartDuckingCopy: $("#smart-ducking-copy"),
  smartDuckingValue: $("#smart-ducking-value"),
  roughCutStage: $("#rough-cut-stage"),
  roughCutVideo: $("#rough-cut-video"),
  subtitleMode: $("#subtitle-mode"),
  subtitleModeControl: $("#subtitle-mode-control"),
  btnRecut: $("#btn-recut"),
  btnApproveEdit: $("#btn-approve-edit"),
  btnSoundSettings: $("#btn-sound-settings"),
  soundSummary: $("#sound-summary"),
  soundSummaryChips: $("#sound-summary-chips"),
  soundSummaryLabel: $("[data-sound-summary-label]"),
  btnReedit: $("#btn-reedit"),
  btnEditSubtitles: $("#btn-edit-subtitles"),
  btnExportFinal: $("#btn-export-final"),
  btnMoreExport: $("#btn-more-export"),
  moreExportMenu: $("#more-export-menu"),
  deliverRoom: $("#deliver-room"),
  deliverStateTitle: $("#deliver-state-title"),
  deliverStateCopy: $("#deliver-state-copy"),
  deliverStateBadge: $("#deliver-state-badge"),
  deliverQualityReadout: $("#deliver-quality-readout"),
  deliverQualityModes: $("#deliver-quality-modes"),
  deliverQualityMode: $("#deliver-quality-mode"),
  deliverQualitySource: $("#deliver-quality-source"),
  deliverQualityScreening: $("#deliver-quality-screening"),
  deliverQualityMaster: $("#deliver-quality-master"),
  deliverQualityWarning: $("#deliver-quality-warning"),
  deliverSummary: $("#deliver-summary"),
  deliverProjectTitle: $("#deliver-project-title"),
  deliverProjectCopy: $("#deliver-project-copy"),
  deliverShotsReady: $("#deliver-shots-ready"),
  deliverReadyNote: $("#deliver-ready-note"),
  deliverQualityNote: $("#deliver-quality-note"),
  btnNormalizeResolution: $("#btn-normalize-resolution"),
  btnCleanWorkingCache: $("#btn-clean-working-cache"),
  deliverSummarySpecs: $("#deliver-summary-specs"),
  deliverWorkProgress: $("#deliver-work-progress"),
  deliverProgressTitle: $("#deliver-progress-title"),
  deliverProgressPercent: $("#deliver-progress-percent"),
  deliverProgressBar: $("#deliver-progress-bar"),
  deliverProgressGrid: $("#deliver-progress-grid"),
  deliverFinal: $("#deliver-final"),
  finalNotGenerated: $("#final-not-generated"),
  finalPlayerState: $("#final-player-state"),
  deliverMetaDuration: $("#deliver-meta-duration"),
  deliverMetaResolution: $("#deliver-meta-resolution"),
  deliverMetaAspect: $("#deliver-meta-aspect"),
  deliverMetaCodec: $("#deliver-meta-codec"),
  deliverMetaSubtitles: $("#deliver-meta-subtitles"),
  deliverMetaVoiceover: $("#deliver-meta-voiceover"),
  deliverMetaAudio: $("#deliver-meta-audio"),
  deliverShotTimeline: $("#deliver-shot-timeline"),
  deliverTimelineTotal: $("#deliver-timeline-total"),
  deliverAudioPanel: $("#deliver-audio-panel"),
  deliverAudioState: $("#deliver-audio-state"),
  deliverAudioModeSwitch: $("#deliver-audio-mode-switch"),
  deliverAudioUploadRow: $("#deliver-audio-upload-row"),
  deliverMusicUpload: $("#deliver-music-upload"),
  deliverMusicUploadNote: $("#deliver-music-upload-note"),
  deliverMusicIntensity: $("#deliver-music-intensity"),
  deliverMusicIntensityValue: $("#deliver-music-intensity-value"),
  deliverSmartDuckingToggle: $("#deliver-smart-ducking-toggle"),
  deliverSmartDuckingCopy: $("#deliver-smart-ducking-copy"),
  deliverSmartDuckingValue: $("#deliver-smart-ducking-value"),
  deliverMusicBrief: $("#deliver-music-brief"),
  audioTimeline: $("#audio-timeline"),
  audioTimelineEditor: $("#audio-timeline-editor"),
  deliverAudioTrackList: $("#deliver-audio-track-list"),
  finalLookPanel: $("#final-look-panel"),
  finalLookPresetGrid: $("#final-look-preset-grid"),
  finalLookIntensity: $("#final-look-intensity"),
  finalLookIntensityValue: $("#final-look-intensity-value"),
  finalLookGrain: $("#final-look-grain"),
  finalLookGrainValue: $("#final-look-grain-value"),
  finalLookVignette: $("#final-look-vignette"),
  finalLookVignetteValue: $("#final-look-vignette-value"),
  finalLookSoftening: $("#final-look-softening"),
  finalLookSofteningValue: $("#final-look-softening-value"),
  finalLookStatus: $("#final-look-status"),
  finalLookPresetName: $("#final-look-preset-name"),
  finalLookDescription: $("#final-look-description"),
  finalLookApply: $("#btn-apply-final-look"),
  finalLookReset: $("#btn-reset-final-look"),
  finalLookOverlay: $("#final-look-overlay"),
  techSummaryToggle: $("#tech-summary-toggle"),
  techSummaryDetails: $("#tech-summary-details"),
  soundSummaryToggle: $("#sound-summary-toggle"),
  soundSummaryBody: $("#sound-summary-body"),
  soundSummaryStatus: $("#sound-summary-status"),
  exportSheet: $("#export-sheet"),
  btnExportClose: $("#btn-export-close"),
  btnExportRun: $("#btn-export-run"),
  exportSelection: $("#export-selection"),
  exportPreflight: $("#export-preflight"),
  posterTitle: $("#poster-title"),
  posterMeta: $("#poster-meta"),
  exportJson: $("#export-json"),
  exportMd: $("#export-md"),
  exportSrt: $("#export-srt"),
  exportVtt: $("#export-vtt"),
  drawer: $("#drawer"),
  drawerBackdrop: $("#drawer-backdrop"),
  toast: $("#toast"),
};

/* ── 常量 ──────────────────────────────────────────────────── */

const STYLE_OPTIONS = ["写实近未来", "胶片科幻", "极简冷色", "梦境超现实"];

const SAMPLE_IDEAS = [
  "最后一位城市值班员每天点亮空城，直到发现整座城市都在等待他下班。",
  "一颗只在雨天醒来的废弃卫星，开始给地面上的守塔人写信。",
  "回收站的机器人收藏了人类丢弃的最后一封信，决定替她送出去。",
];

const AGENT_DEFS = [
  { id: "director", index: "01", name: "导演", en: "DIRECTOR", role: "主题 · 叙事",
    input: "IDEA", output: "BRIEF",
    summarize: (d) => {
      const concept = String(d.brief?.["主题"] || d.idea || "").trim();
      return {
        headline: d.brief && Object.keys(d.brief).length ? "BRIEF LOCKED" : "BRIEF QUEUED",
        primary: "CORE CONCEPT",
        secondary: concept || "AWAITING DIRECTOR PASS",
        secondaryNatural: Boolean(concept),
      };
    } },
  { id: "writer", index: "02", name: "编剧", en: "WRITER", role: "剧本 · 台词 · 字幕",
    input: "BRIEF", output: "SCRIPT",
    summarize: (d) => {
      const script = d.script || {};
      const hasScript = Boolean(script.story || script.dialogue_book?.length);
      const sceneCount = script.story ? String(script.story).split(/\n+/).filter(Boolean).length || 1 : 0;
      const cueCount = Array.isArray(script.dialogue_book) ? script.dialogue_book.length : 0;
      return {
        headline: hasScript ? "SCRIPT READY" : "SCRIPT QUEUED",
        primary: hasScript ? `${sceneCount} SCENE${sceneCount === 1 ? "" : "S"} · ${cueCount} CUES` : "WAITING FOR SCRIPT",
        secondary: hasScript ? (script.dialogue_locked ? "DIALOGUE LOCKED" : "DIALOGUE REVIEW") : "AWAITING WRITER PASS",
      };
    } },
  { id: "visual_bible", index: "03", name: "美术指导", en: "ART DIRECTOR", role: "角色 · 场景 · 风格",
    input: "SCRIPT", output: "VISUAL",
    summarize: (d) => {
      const bible = d.visual_bible || {};
      const rules = Object.keys(bible).length;
      return {
        headline: rules ? "VISUAL BIBLE" : "VISUAL QUEUED",
        primary: d.visual_style || "CUSTOM",
        secondary: rules ? `${rules} RULES LOCKED` : "AWAITING ART DIRECTION",
      };
    } },
  { id: "storyboard", index: "04", name: "分镜师", en: "STORYBOARD", role: "镜头 · 调度",
    input: "VISUAL", output: "SHOTS",
    summarize: (d) => {
      const shots = d.storyboard || [];
      const runtime = shots.reduce((sum, shot) => sum + Number(shot.duration_seconds || 0), 0);
      return {
        headline: shots.length ? "SHOT LIST" : "SHOT LIST QUEUED",
        primary: shots.length ? `${shots.length} SHOTS · ${runtime}s` : "0 SHOTS · 0s",
        secondary: shots.length ? "LOCKED" : "AWAITING STORYBOARD",
      };
    } },
  { id: "quality", index: "05", name: "质检", en: "QC GATE", role: "连续性 · 风险",
    input: "SHOTS", output: "QC",
    summarize: (d) => {
      const checks = d.quality_report || [];
      const hasRisk = checks.some((item) => /失败|风险|建议改写|未通过|error|fail/i.test(String(item)));
      const issueCount = checks.filter((item) => /失败|风险|建议改写|未通过|error|fail/i.test(String(item))).length;
      return {
        headline: checks.length ? (hasRisk ? "QC REVIEW" : "QC PASSED") : "QC QUEUED",
        primary: `${checks.length} CHECKS`,
        secondary: checks.length ? `${issueCount} ISSUE${issueCount === 1 ? "" : "S"}` : "AWAITING CHECKS",
      };
    } },
  { id: "generation", index: "06", name: "生成调度", en: "GENERATION", role: "生成 · 重试",
    input: "SHOTS", output: "MEDIA",
    summarize: (d) => {
      const shots = d.storyboard || [];
      const approved = shots.filter(isShotReady).length;
      return {
        headline: shots.length ? "READY" : "QUEUE HOLD",
        primary: shots.length ? `${approved} / ${shots.length} SHOTS` : "0 / 0 SHOTS",
        secondary: shots.length ? "QUEUE CLEAR" : "AWAITING SHOTS",
      };
    } },
  { id: "editor", index: "07", name: "剪辑", en: "EDITOR", role: "粗剪 · 混音 · 交付",
    input: "MEDIA", output: "FINAL",
    summarize: (d) => {
      const status = String(d.status || "");
      if (status === "rough_cut_ready" || d.rough_cut_placeholder) return { headline: "ROUGH CUT READY", primary: "PICTURE + MIX", secondary: "REVIEW AVAILABLE" };
      if (status === "editing_rough_cut") return { headline: "ACTIVE", primary: "PICTURE + MIX", secondary: "EDIT IN PROGRESS" };
      if (status.startsWith("completed")) return { headline: "FINAL CUT READY", primary: "MASTER CUT + MIX", secondary: "DELIVERY RECORDED" };
      if (status === "ready_for_ai_edit") return { headline: "READY", primary: "WAITING FOR MEDIA", secondary: "MIX + SUBTITLE" };
      return { headline: "QUEUED", primary: "WAITING FOR MEDIA", secondary: "MEDIA PENDING" };
    } },
];

function isShotReady(shot) {
  return MovieAgentModules.storyboard.shotReady(shot);
}

function normalizeCrewSummary(summary) {
  if (summary && typeof summary === "object") {
    return {
      headline: String(summary.headline || "").trim(),
      primary: String(summary.primary || "").trim(),
      secondary: String(summary.secondary || "").trim(),
      secondaryNatural: Boolean(summary.secondaryNatural),
    };
  }
  return { headline: String(summary || "").trim(), primary: "", secondary: "", secondaryNatural: false };
}

function renderCrewSummary(element, summary) {
  if (!element) return;
  const value = normalizeCrewSummary(summary);
  const headline = element.querySelector(".crew-summary-headline");
  const primary = element.querySelector(".crew-summary-primary");
  const secondary = element.querySelector(".crew-summary-secondary");
  if (headline) headline.textContent = value.headline;
  if (primary) primary.textContent = value.primary;
  if (secondary) secondary.textContent = value.secondary;
  element.classList.toggle("is-natural", value.secondaryNatural);
  element.dataset.summaryHeadline = value.headline;
  element.setAttribute("aria-label", [value.headline, value.primary, value.secondary].filter(Boolean).join(" · "));
}

const AGENT_STATUS_COPY = {
  director: { idle: "QUEUED", next: "QUEUED", ready: "READY", working: "DIRECTING", done: "LOCKED", failed: "FAILED" },
  writer: { idle: "QUEUED", next: "QUEUED", ready: "READY", working: "WRITING", done: "LOCKED", failed: "FAILED" },
  visual_bible: { idle: "QUEUED", next: "QUEUED", ready: "READY", working: "DESIGNING", done: "LOCKED", failed: "FAILED" },
  storyboard: { idle: "QUEUED", next: "QUEUED", ready: "READY", working: "BOARDING", done: "LOCKED", failed: "FAILED" },
  quality: { idle: "QUEUED", next: "QUEUED", ready: "READY", working: "REVIEWING", done: "LOCKED", failed: "FAILED" },
  generation: { idle: "QUEUED", next: "QUEUED", ready: "READY", working: "GENERATING", done: "LOCKED", failed: "FAILED" },
  editor: { idle: "QUEUED", next: "QUEUED", ready: "READY", working: "EDITING", done: "LOCKED", failed: "FAILED" },
};

const CREW_NODE_STATE_COPY = {
  idle: "QUEUED",
  next: "QUEUED",
  ready: "READY",
  working: "ACTIVE",
  done: "LOCKED",
  failed: "FAILED",
};

const CREW_NODE_PROGRESS = {
  idle: 0,
  next: 18,
  ready: 34,
  working: 68,
  done: 100,
  failed: 100,
};

const SHOT_STATUS = {
  planned: "QUEUED",
  replanned: "STALE",
  generating_mock: "ACTIVE",
  generating_comfyui: "ACTIVE",
  generated_comfyui: "ACTIVE",
  awaiting_visual_review: "REVIEW",
  approved_mock: "QC PASS",
  approved_comfyui: "QC PASS",
  generation_failed: "FAILED",
};

const PROJECT_STATUS = {
  planned_mock: "策划完成（mock 文案）",
  planned_text_ai: "策划完成（AI 文案）",
  ready_for_comfyui_render: "待真实生成",
  generating_video_mock: "mock 生成中",
  rendering_comfyui: "真实生成中",
  awaiting_visual_review: "人工视觉审片中",
  render_failed: "生成中断（可续跑）",
  ready_for_ai_edit: "SHOTS READY · 待 AI Edit",
  editing_rough_cut: "AI Edit 粗剪中",
  rough_cut_ready: "Rough Cut 已完成 · 待批准",
  editing_final: "最终成片导出中",
  completed_mock: "mock 流程完成",
  completed_text_ai_video_mock: "AI 文案 + mock 视频流程完成",
  completed_comfyui: "真实成片已交付",
};

const state = {
  project: null,
  assets: {},
  pendingProjectId: null,
  selectedStyle: STYLE_OPTIONS[0],
  health: null,
  busy: false,
  rendering: false,
  editing: false,
  soundEnabled: localStorage.getItem("movie-agent-sound") === "on",
  activeShotNumber: 1,
  renderStartedAt: 0,
  manualTab: "brief",
  manualShotNumber: 1,
  hasFinalVideo: false,
  creditsProjectId: null,
  workingAgent: null,
  assemblyLocked: false,
  crewDetails: {},
  crewMessages: [],
  crewArtifacts: [],
  crewRadioLog: [],
  crewRadioOpen: false,
  viewingHistorical: false,
  drawerType: null,
  activeAgentId: null,
  inspectorExpanded: false,
  exportOptions: { container: "mp4", resolution: "1080p", aspect: "16:9", subtitle_mode: "burned" },
  finalVideoUrl: null,
  finalVideoProbeRun: 0,
  videoQuality: null,
  previewQualityMode: "auto",
  editProgressStep: 0,
  musicMode: "ai",
  musicIntensity: 0.6,
  musicAssetName: "",
  smartDucking: true,
  audioInspectorTrack: "music",
  audioInspectorOpen: false,
  finalLookProjectId: null,
  finalLookDraft: null,
  finalLookDirty: false,
  finalLookSplit: 50,
  deliverShotPreviewMedia: {},
  filmstripDragging: false,
  audioTimelineDuration: 0,
  diagnostics: null,
  exportPreflightRun: 0,
  job: null,
  jobCursor: 0,
};

let manualTypingRun = 0;
let monitorTimecodeTimer = null;
let premiereTimer = null;
let projectorOscillator = null;
let projectorGain = null;
let faviconBlinkTimer = null;
let drawerContentRun = 0;
let drawerHideTimer = null;
let jobPollTimer = null;
let jobPollRun = 0;

/* ── 小工具 ────────────────────────────────────────────────── */

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

const timecode = (seconds) => MovieAgentModules.player.formatTimecode(seconds);

function truncate(text, max = 56) {
  const clean = String(text || "").replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max)}…` : clean;
}

let toastTimer = null;
function toast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.classList.toggle("error", isError);
  els.toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => els.toast.classList.remove("show"), 4200);
}

function setIdeaError(message = "", actionMessage = "") {
  const inputMessage = String(message || "");
  const buttonMessage = String(actionMessage || "");
  if (els.ideaError) els.ideaError.textContent = inputMessage;
  if (els.creationError) els.creationError.textContent = buttonMessage;
  const hasError = Boolean(inputMessage || buttonMessage);
  els.slate?.classList.toggle("has-error", hasError);
  els.idea?.setAttribute("aria-invalid", String(hasError));
}

function updateIdeaCounter() {
  if (!els.ideaCounter || !els.idea) return;
  els.ideaCounter.textContent = `${els.idea.value.length} / 2000`;
}

function validateIdea({ focus = false } = {}) {
  const length = els.idea.value.trim().length;
  if (length < 10) {
    setIdeaError("请先写下至少 10 个字的原创科幻创意。", "开机前需要一条完整的创意句子。");
    if (focus) els.idea.focus();
    return false;
  }
  setIdeaError();
  return true;
}

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

function projectTitle(project = state.project) {
  return truncate((project && project.brief && project.brief["主题"]) || (project && project.idea) || "未命名短片", 28);
}

function manualFilmTitle(project = state.project) {
  const brief = project?.brief || {};
  return String(brief["片名"] || brief["标题"] || "未命名短片").trim() || "未命名短片";
}

function manualProjectLogline(project = state.project) {
  const brief = project?.brief || {};
  return String(brief["主题"] || project?.idea || "").trim();
}

function setBrowserActivity(mode, project = state.project) {
  const projectId = project && project.project_id ? project.project_id : "Movie-Agent";
  document.title = mode === "render"
    ? `● RENDERING ${projectId}`
    : mode === "edit"
      ? `● AI EDIT ${projectId}`
      : `Movie-Agent · ${projectTitle(project)}`;
  clearInterval(faviconBlinkTimer);
  const setFavicon = (dot) => {
    if (!els.favicon) return;
    els.favicon.href = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%2315110b'/%3E%3Ccircle cx='24' cy='8' r='4' fill='${dot}'/%3E%3Crect x='6' y='12' width='5' height='8' fill='%23c28a3e'/%3E%3Crect x='14' y='12' width='5' height='8' fill='%23c28a3e' opacity='.55'/%3E%3C/svg%3E`;
  };
  if (!["render", "edit"].includes(mode)) {
    setFavicon("%23c28a3e");
    return;
  }
  let lit = true;
  setFavicon(mode === "edit" ? "%23c28a3e" : "%23d98b55");
  faviconBlinkTimer = setInterval(() => {
    lit = !lit;
    setFavicon(lit ? (mode === "edit" ? "%23c28a3e" : "%23d98b55") : "%23352b20");
  }, 700);
}

function audioContext() {
  const Context = window.AudioContext || window.webkitAudioContext;
  if (!Context) return null;
  state.audioContext ||= new Context();
  if (state.audioContext.state === "suspended") state.audioContext.resume().catch(() => {});
  return state.audioContext;
}

function playUiSound(kind) {
  if (!state.soundEnabled) return;
  const context = audioContext();
  if (!context) return;
  const now = context.currentTime;
  const tone = (frequency, duration, gain, type = "sine", offset = 0) => {
    const oscillator = context.createOscillator();
    const envelope = context.createGain();
    oscillator.type = type;
    oscillator.frequency.setValueAtTime(frequency, now + offset);
    envelope.gain.setValueAtTime(0.0001, now + offset);
    envelope.gain.exponentialRampToValueAtTime(gain, now + offset + 0.012);
    envelope.gain.exponentialRampToValueAtTime(0.0001, now + offset + duration);
    oscillator.connect(envelope).connect(context.destination);
    oscillator.start(now + offset);
    oscillator.stop(now + offset + duration + 0.02);
  };
  if (kind === "slate") { tone(150, 0.05, 0.08, "square"); tone(72, 0.1, 0.05, "triangle", 0.018); }
  if (kind === "done") { tone(660, 0.08, 0.035); tone(880, 0.13, 0.028, "sine", 0.07); }
  if (kind === "premiere") { tone(262, 0.24, 0.04); tone(392, 0.34, 0.035, "sine", 0.11); tone(523, 0.48, 0.03, "sine", 0.22); }
}

function startProjectorHum() {
  if (!state.soundEnabled || projectorOscillator) return;
  const context = audioContext();
  if (!context) return;
  projectorOscillator = context.createOscillator();
  projectorGain = context.createGain();
  projectorOscillator.type = "sawtooth";
  projectorOscillator.frequency.value = 58;
  projectorGain.gain.value = 0.008;
  projectorOscillator.connect(projectorGain).connect(context.destination);
  projectorOscillator.start();
}

function stopProjectorHum() {
  if (projectorOscillator) projectorOscillator.stop();
  projectorOscillator = null;
  projectorGain = null;
}

/* ── SSE 流读取（fetch + 手动解析） ────────────────────────── */

async function streamPost(url, body, onEvent) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const payload = await response.json();
      if (payload.error) message = payload.error;
    } catch { /* keep default message */ }
    throw new Error(message);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let split;
    while ((split = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        try {
          onEvent(JSON.parse(line.slice(6)));
        } catch (error) {
          console.error("SSE 事件解析失败", error);
        }
      }
    }
  }
}

/* 让 mock 模式下瞬间完成的流水线，以可观看的节奏逐帧呈现 */
function createPacedHandler(onEvent) {
  const delays = { project: 80, agent_start: 260, agent_done: 620, artifact: 360, chat: 280, shot_update: 110, project_saved: 120 };
  const queue = [];
  let draining = false;
  let lastApply = 0;
  function drain() {
    if (draining) return;
    draining = true;
    const step = () => {
      const next = queue.shift();
      if (!next) {
        draining = false;
        return;
      }
      const wait = Math.max(0, lastApply + (delays[next.type] ?? 0) - Date.now());
      setTimeout(() => {
        lastApply = Date.now();
        try {
          onEvent(next);
        } catch (error) {
          console.error("事件处理失败", error);
        }
        step();
      }, wait);
    };
    step();
  }
  return (event) => {
    queue.push(event);
    drain();
  };
}

/* ── 制片轨（顶部四步） ────────────────────────────────────── */

function setPipeline(states = {}) {
  const order = ["plan", "previs", "render", "deliver"];
  const stateLabels = { active: "ACTIVE", review: "REVIEW", failed: "FAILED", stale: "STALE", done: "✓", archived: "", todo: "" };
  const separators = $$("#pipeline .sep");
  const hasExplicitFocus = order.some((key) => ["active", "ready", "review", "failed", "stale"].includes(states[key]));
  const resolvedStates = {};
  let inferredActive = !hasExplicitFocus;
  for (const key of order) {
    const requestedValue = states[key] === "ready" ? "review" : states[key];
    const requested = ["done", "active", "review", "failed", "stale", "archived"].includes(requestedValue) ? requestedValue : "todo";
    if (requested === "todo" && inferredActive) {
      resolvedStates[key] = "active";
      inferredActive = false;
    } else {
      resolvedStates[key] = requested;
    }
  }
  for (const [index, key] of order.entries()) {
    const el = els.pipeline.querySelector(`[data-step="${key}"]`);
    const currentState = resolvedStates[key];
    el.classList.remove("is-active", "is-done", "is-ready", "is-review", "is-failed", "is-stale", "is-archived");
    el.dataset.state = currentState;
    el.setAttribute("aria-label", `${key.toUpperCase()} · ${stateLabels[currentState] || "QUEUED"}`);
    const stateLabel = el.querySelector(".step-state");
    if (stateLabel) stateLabel.textContent = stateLabels[currentState];
    if (currentState === "active") {
      el.classList.add("is-active");
      el.setAttribute("aria-current", "step");
    } else if (currentState === "review") {
      el.classList.add("is-ready", "is-review");
      el.setAttribute("aria-current", "step");
    } else if (currentState === "failed") {
      el.classList.add("is-failed");
      el.setAttribute("aria-current", "step");
    } else if (currentState === "stale") {
      el.classList.add("is-stale");
      el.setAttribute("aria-current", "step");
    } else if (currentState === "done") {
      el.classList.add("is-done");
      el.removeAttribute("aria-current");
    } else if (currentState === "archived") {
      el.classList.add("is-archived");
      el.removeAttribute("aria-current");
    } else {
      el.removeAttribute("aria-current");
    }
    if (separators[index]) {
      const nextState = order[index + 1] ? resolvedStates[order[index + 1]] : "todo";
      separators[index].dataset.state = currentState === "done" || currentState === "archived" ? "done" : ["active", "review", "failed", "stale"].includes(nextState) ? "active" : "todo";
    }
  }
}

function pipelineFromProject(project, hasVideo) {
  return MovieAgentModules.state.pipelineFromProject(project, hasVideo, Boolean(state.viewingHistorical), isShotReady);
}

/* ── 第二幕 · 剧组看板 ─────────────────────────────────────── */

function buildCrewBoard() {
  const container = els.crewFlow;
  if (!container) return;
  container.innerHTML = "";
  AGENT_DEFS.forEach((def, index) => {
    const node = document.createElement("div");
    node.className = "crew-flow-node";
    node.dataset.agent = def.id;
    const card = document.createElement("article");
    card.className = "crew-card idle";
    card.dataset.agent = def.id;
    card.dataset.state = "idle";
    card.dataset.inspectorOpen = "false";
    card.tabIndex = 0;
    card.setAttribute("role", "group");
    card.setAttribute("aria-label", `${def.name} Agent 详情`);
    card.innerHTML = `
      <header class="crew-card-header">
        <div class="crew-indexline type-system-meta"><span class="crew-node-id">${esc(def.index)}</span><span class="crew-node-status type-system-meta" data-node-status="idle">QUEUED</span></div>
        <div class="crew-identity">
          <h3 class="crew-name">${esc(def.name)}</h3>
          <span class="crew-en type-system-meta">${esc(def.en)}</span>
          <p class="crew-role">${esc(def.role)}</p>
        </div>
      </header>
      <div class="crew-card-main">
        <div class="crew-state type-status"><span class="crew-state-icon" aria-hidden="true"></span><span class="crew-state-text">${AGENT_STATUS_COPY[def.id]?.idle || "WAITING"}</span></div>
        <p class="crew-summary type-helper"><strong class="crew-summary-headline"></strong><span class="crew-summary-primary"></span><small class="crew-summary-secondary"></small></p>
        <div class="crew-artifact-preview artifact-preview" hidden aria-live="polite"></div>
      </div>
      <footer class="crew-card-footer">
        <div class="crew-node-route type-system-meta" aria-label="${esc(def.input)} to ${esc(def.output)}"><span class="crew-route-input">${esc(def.input)}</span><span class="crew-route-arrow" aria-hidden="true">→</span><span class="crew-route-output">${esc(def.output)}</span></div>
        <div class="crew-node-progress" aria-hidden="true"><i></i></div>
      </footer>`;
    renderCrewSummary(card.querySelector(".crew-summary"), def.summarize({}));
    card.addEventListener("click", (event) => openCrewDrawer(def.id));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openCrewDrawer(def.id);
      }
    });
    node.appendChild(card);
    if (index < AGENT_DEFS.length - 1) {
      const link = document.createElement("i");
      link.className = "crew-flow-link";
      link.dataset.linkIndex = String(index);
      link.setAttribute("aria-hidden", "true");
      link.innerHTML = "<b></b>";
      node.appendChild(link);
    }
    container.appendChild(node);
  });
  if (state.project) syncCrewBoard(state.project, { silent: true });
  else updateCrewFlowProgress(Object.fromEntries(AGENT_DEFS.map((def) => [def.id, "idle"])));
  refreshCrewConnectors();
  renderCrewRadio();
}

function crewMergedData(agentId, data = {}) {
  const project = state.project || {};
  const details = state.crewDetails[agentId] || {};
  const merged = { ...project, ...details, ...data };
  const hasValue = (value) => value !== undefined && value !== null && (typeof value !== "object" || Object.keys(value).length > 0);
  for (const key of ["brief", "script", "visual_bible", "storyboard", "quality_report"]) {
    merged[key] = hasValue(data[key]) ? data[key] : hasValue(details[key]) ? details[key] : project[key];
  }
  return merged;
}

function crewStatusText(agentId, agentState, data = {}) {
  const copy = AGENT_STATUS_COPY[agentId] || {};
  return copy[agentState] || copy.idle || agentState.toUpperCase();
}

function setAgentState(agentId, agentState, data = {}, { silent = false } = {}) {
  const card = document.querySelector(`.crew-card[data-agent="${agentId}"]`);
  if (!card) return;
  const previousState = card.dataset.state || "idle";
  card.classList.remove("idle", "next", "ready", "working", "done", "failed");
  const resolvedState = ["idle", "next", "ready", "working", "done", "failed"].includes(agentState) ? agentState : "idle";
  card.classList.add(resolvedState);
  card.dataset.state = resolvedState;
  card.style.setProperty("--node-progress", `${CREW_NODE_PROGRESS[resolvedState] ?? 0}%`);
  if (["working", "ready"].includes(resolvedState)) card.setAttribute("aria-current", "step");
  else card.removeAttribute("aria-current");
  const text = card.querySelector(".crew-state-text");
  const nodeStatus = card.querySelector("[data-node-status]");
  const summary = card.querySelector(".crew-summary");
  card.dataset.inspectorOpen = "false";
  if (nodeStatus) {
    nodeStatus.textContent = CREW_NODE_STATE_COPY[resolvedState] || "QUEUED";
    nodeStatus.dataset.state = resolvedState;
  }
  const merged = crewMergedData(agentId, data);
  const def = AGENT_DEFS.find((item) => item.id === agentId);
  const baseSummary = def ? def.summarize(merged) : "";
  renderCrewSummary(summary, baseSummary);
  if (resolvedState === "working") {
    if (previousState !== "working" || !card.dataset.startedAt) card.dataset.startedAt = String(Date.now());
    text.textContent = `${crewStatusText(agentId, resolvedState, merged)} · 00:00`;
  } else if (resolvedState === "done") {
    delete card.dataset.startedAt;
    text.textContent = crewStatusText(agentId, resolvedState, merged);
    renderCrewSummary(summary, baseSummary);
    renderCrewCardExtras(agentId);
    if (!silent && previousState !== "done") playUiSound("done");
  } else if (resolvedState === "ready") {
    delete card.dataset.startedAt;
    text.textContent = crewStatusText(agentId, resolvedState, merged);
    renderCrewSummary(summary, baseSummary);
    renderCrewCardExtras(agentId);
  } else if (resolvedState === "next") {
    delete card.dataset.startedAt;
    text.textContent = crewStatusText(agentId, resolvedState, merged);
    renderCrewSummary(summary, { headline: "QUEUED", primary: "UPSTREAM LOCKED", secondary: "AWAITING THIS PASS" });
  } else if (resolvedState === "failed") {
    delete card.dataset.startedAt;
    text.textContent = crewStatusText(agentId, resolvedState, merged);
    renderCrewSummary(summary, { headline: "FAILED", primary: "INTERRUPTED", secondary: "RETRY AVAILABLE" });
  } else {
    delete card.dataset.startedAt;
    text.textContent = crewStatusText(agentId, resolvedState, merged);
    if (resolvedState === "idle" && !normalizeCrewSummary(baseSummary).headline.match(/QUEUED|AWAITING|HOLD/)) {
      renderCrewSummary(summary, { headline: "QUEUED", primary: "AWAITING UPSTREAM", secondary: "STANDBY" });
    }
  }
  const agentName = AGENT_DEFS.find((item) => item.id === agentId)?.name || agentId;
  card.setAttribute("aria-label", `${agentName} Agent · ${text.textContent}`);
  refreshCrewConnectors();
}

function refreshCrewConnectors() {
  const flow = els.crewFlow;
  if (!flow) return;
  const nodes = Array.from(flow.querySelectorAll(".crew-flow-node"));
  nodes.forEach((node, index) => {
    const left = node.querySelector(".crew-card");
    const right = nodes[index + 1]?.querySelector(".crew-card");
    const link = node.querySelector(".crew-flow-link");
    if (!link || !left || !right) return;
    const leftState = left.dataset.state || "idle";
    const rightState = right.dataset.state || "idle";
    const complete = leftState === "done" && rightState === "done";
    const active = ["working", "ready"].includes(rightState) && ["done", "working", "ready"].includes(leftState);
    link.dataset.state = complete ? "done" : active ? "active" : "waiting";
  });
}

function updateCrewFlowProgress(states = {}) {
  if (!els.crewFlowProgress) return;
  const resolved = AGENT_DEFS.map((def) => states[def.id] || "idle");
  const completed = resolved.filter((item) => item === "done").length;
  const currentIndex = resolved.findIndex((item) => ["working", "ready", "next"].includes(item));
  const current = currentIndex >= 0 ? AGENT_DEFS[currentIndex] : null;
  const suffix = current
    ? ` · ${current.en} ${resolved[currentIndex] === "working" ? "ACTIVE" : "NEXT"}`
    : completed === AGENT_DEFS.length ? " · ROUTE COMPLETE" : " · STANDBY";
  els.crewFlowProgress.textContent = `${completed}/${AGENT_DEFS.length} COMPLETE${suffix}`;
}

function rememberCrewEvent(agentId, event) {
  if (!agentId) return;
  state.crewDetails[agentId] = { ...(state.crewDetails[agentId] || {}), ...event };
}

function crewAgentLabel(agentId) {
  const def = AGENT_DEFS.find((item) => item.id === agentId);
  return def ? `${def.name} / ${def.en}` : String(agentId || "SYSTEM").toUpperCase();
}

function pushCrewRadio(entry) {
  state.crewRadioLog.push({
    ...entry,
    time: entry.time || new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  });
  if (state.crewRadioLog.length > 80) state.crewRadioLog.splice(0, state.crewRadioLog.length - 80);
  renderCrewRadio();
}

function appendCrewStatus(agentId, status, message) {
  pushCrewRadio({ type: "status", agent: agentId, status, message });
}

function renderCrewCardExtras(agentId) {
  const card = document.querySelector(`.crew-card[data-agent="${agentId}"]`);
  if (!card) return;
  const latest = state.crewArtifacts.filter((item) => item.agent === agentId).at(-1);
  const preview = card.querySelector(".crew-artifact-preview");
  if (!preview || !latest) return;
  const actionLabel = agentId === "writer" ? "OPEN DRAFT" : "VIEW ARTIFACT";
  preview.hidden = false;
  preview.innerHTML = `<div class="artifact-preview-head"><span class="artifact-title">${esc(latest.title)}</span><button class="artifact-action type-control" type="button" aria-label="${actionLabel}: ${esc(latest.title)}">${actionLabel}</button></div><p class="artifact-content">${esc(truncate(latest.content, 180))}</p>`;
}

function appendCrewArtifact(event) {
  if (!event.agent || !event.content) return;
  const artifact = {
    agent: event.agent,
    title: event.title || "现场产出",
    content: event.content,
    time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  };
  state.crewArtifacts.push(artifact);
  rememberCrewEvent(event.agent, { artifacts: state.crewArtifacts.filter((item) => item.agent === event.agent) });
  renderCrewCardExtras(event.agent);
  pushCrewRadio({ type: "artifact", agent: artifact.agent, status: "ARTIFACT", title: artifact.title, message: artifact.content, time: artifact.time });
}

function appendCrewMessage(event) {
  if (!event.message) return;
  const message = {
    from: event.from || "crew",
    to: event.to || "all",
    message: event.message,
    time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  };
  state.crewMessages.push(message);
  rememberCrewEvent(event.from, { messages: state.crewMessages.filter((item) => item.from === event.from) });
  pushCrewRadio({ type: "chat", agent: message.from, to: message.to, status: "COMMS", message: message.message, time: message.time });
}

function renderCrewRadio() {
  if (!els.crewRadio) return;
  els.crewRadio.innerHTML = "";
  const entries = (state.crewRadioLog.length ? state.crewRadioLog : [
    ...state.crewMessages.map((item) => ({ type: "chat", agent: item.from, ...item, status: "COMMS" })),
    ...state.crewArtifacts.map((item) => ({ type: "artifact", agent: item.agent, ...item, status: "ARTIFACT", message: item.content })),
  ]).slice(-12);
  if (!entries.length) {
    const emptyCopy = state.project ? "PROJECT SNAPSHOT / NO RADIO TRAFFIC" : "SYSTEM / WAITING FOR PROJECT START";
    els.crewRadio.innerHTML = `<div class="radio-msg radio-system"><span class="radio-time type-system-meta">--:--:--</span><span class="radio-from type-system-meta">SYSTEM</span><span class="radio-status type-status">${esc(emptyCopy)}</span><p class="type-helper">${state.project ? "已载入项目状态；新的 Agent 信号会在这里出现。" : "启动项目后，Agent 状态和中间产出会实时归档。"}</p></div>`;
  } else {
    for (const item of entries) {
      const row = document.createElement("div");
      row.className = `radio-msg ${item.type === "artifact" ? "radio-artifact" : item.type === "status" ? "radio-status-msg" : ""}`;
      const route = item.type === "chat" ? ` → ${crewAgentLabel(item.to || "all")}` : "";
      const title = item.type === "artifact" ? ` · ${item.title || "ARTIFACT"}` : "";
      row.innerHTML = `<div class="radio-line"><span class="radio-time type-system-meta">${esc(item.time || "--:--:--")}</span><span class="radio-from type-system-meta">${esc(crewAgentLabel(item.agent || item.from))}</span><span class="radio-status type-status">${esc(item.status || "SIGNAL")}</span><span class="radio-to type-system-meta">${esc(route || title)}</span></div><p class="type-helper">${esc(truncate(item.message || item.content || "", 180))}</p>`;
      els.crewRadio.appendChild(row);
    }
  }
  const latest = entries.at(-1);
  const latestLabel = latest
    ? `${crewAgentLabel(latest.agent || latest.from)} / ${latest.status || "SIGNAL"}`
    : state.project ? "PROJECT SNAPSHOT" : "STANDBY";
  if (els.crewRadioSummary) {
    els.crewRadioSummary.textContent = `${entries.length} SIGNALS · ${truncate(latestLabel, 34).toUpperCase()}`;
  }
  if (els.crewRadioWrap) els.crewRadioWrap.classList.toggle("is-open", state.crewRadioOpen);
  if (els.crewRadioToggle) els.crewRadioToggle.setAttribute("aria-expanded", String(state.crewRadioOpen));
  if (state.crewRadioOpen) els.crewRadio.scrollTop = els.crewRadio.scrollHeight;
}

/* 集结期间的现场感：给"工作中"的成员卡实时计时 */
let crewTicker = null;

function startCrewTicker() {
  if (crewTicker) return;
  crewTicker = setInterval(() => {
    for (const card of document.querySelectorAll(".crew-card.working[data-started-at]")) {
      const text = card.querySelector(".crew-state-text");
      if (text) {
        const elapsed = (Date.now() - Number(card.dataset.startedAt)) / 1000;
        text.textContent = `${AGENT_STATUS_COPY[card.dataset.agent]?.working || "WORKING"} · ${timecode(elapsed)}`;
      }
    }
  }, 1000);
}

function failWorkingAgent() {
  if (!state.workingAgent) return;
  setAgentState(state.workingAgent, "failed");
  appendCrewStatus(state.workingAgent, "FAILED", "Agent interrupted / retry available");
  state.workingAgent = null;
}

function crewAssetReady(agentId, project) {
  if (!project) return false;
  if (agentId === "director") return Boolean(project.brief && Object.keys(project.brief).length);
  if (agentId === "writer") return Boolean(project.script && (project.script.story || project.script.dialogue_book?.length));
  if (agentId === "visual_bible") return Boolean(project.visual_bible && Object.keys(project.visual_bible).length);
  if (agentId === "storyboard") return Boolean(project.storyboard?.length);
  if (agentId === "quality") return Boolean(project.quality_report?.length);
  if (agentId === "generation") return Boolean(project.storyboard?.length && project.storyboard.every(isShotReady));
  if (agentId === "editor") return ["editing_rough_cut", "rough_cut_ready", "editing_final"].includes(project.status) || String(project.status || "").startsWith("completed") || Boolean(project.rough_cut_placeholder || project.final_output_placeholder);
  return false;
}

function deriveCrewStates(project = state.project) {
  const states = Object.fromEntries(AGENT_DEFS.map((def) => [def.id, "idle"]));
  const status = String(project?.status || "");
  const shots = project?.storyboard || [];
  const allShotsReady = shots.length > 0 && shots.every(isShotReady);
  const explicit = (agentId) => state.crewDetails[agentId]?.status;
  for (const def of AGENT_DEFS) {
    if (["working", "failed"].includes(explicit(def.id))) states[def.id] = explicit(def.id);
    else if (explicit(def.id) === "done") states[def.id] = "done";
    else if (crewAssetReady(def.id, project)) states[def.id] = "done";
  }
  if (status === "render_failed") {
    states.generation = "failed";
    states.editor = "idle";
  }
  if (["generating_video_mock", "rendering_comfyui"].includes(status)) {
    states.generation = "working";
    states.editor = "idle";
  }
  if (["planned_mock", "planned_text_ai", "ready_for_comfyui_render"].includes(status)) {
    states.generation = "ready";
    states.editor = "idle";
  }
  if (status === "editing_rough_cut" || status === "editing_final") {
    states.generation = allShotsReady ? "done" : states.generation;
    states.editor = "working";
  }
  if (status === "rough_cut_ready" || status.startsWith("completed")) {
    states.generation = allShotsReady ? "done" : states.generation;
    states.editor = "done";
  }
  if (status === "ready_for_ai_edit") {
    states.generation = allShotsReady ? "done" : states.generation;
    states.editor = "ready";
  }
  const current = AGENT_DEFS.find((def) => states[def.id] === "working");
  if (!current && status === "planning_live" && !Object.values(states).includes("failed")) {
    const next = AGENT_DEFS.find((def) => states[def.id] === "idle");
    if (next) states[next.id] = "next";
  }
  if (!current && !status && !state.project) states.director = "idle";
  return states;
}

function pipelineFromCrewStates(states) {
  const focus = AGENT_DEFS.findIndex((def) => ["working", "ready", "next"].includes(states[def.id]));
  if (focus <= 1 && focus >= 0) return { plan: "active", previs: "todo", render: "todo", deliver: "todo" };
  if (focus <= 4 && focus >= 0) return { plan: "done", previs: "active", render: "todo", deliver: "todo" };
  if (focus === 5) return { plan: "done", previs: "done", render: "active", deliver: "todo" };
  if (focus === 6) return { plan: "done", previs: "done", render: "done", deliver: "active" };
  const doneCount = AGENT_DEFS.filter((def) => states[def.id] === "done").length;
  return doneCount ? { plan: "done", previs: "done", render: "done", deliver: "todo" } : { plan: "active" };
}

function syncCrewBoard(project = state.project, { silent = true } = {}) {
  if (!project) return;
  const states = deriveCrewStates(project);
  for (const def of AGENT_DEFS) setAgentState(def.id, states[def.id], project, { silent });
  updateCrewFlowProgress(states);
  state.workingAgent = AGENT_DEFS.find((def) => states[def.id] === "working")?.id || null;
  const focus = AGENT_DEFS.find((def) => ["working", "ready", "next"].includes(states[def.id]));
  if (els.crewMeta) {
    const status = String(project.status || "");
    const projectId = String(project.project_id || "").replace(/^film-/, "").toUpperCase();
    if (status === "planning_live") els.crewMeta.textContent = focus ? `LIVE · ${crewAgentLabel(focus.id)} ACTIVE` : `LIVE · PROJECT ${projectId}`;
    else if (status === "ready_for_ai_edit") els.crewMeta.textContent = `READY · DELIVER / AI EDIT · ${projectId}`;
    else if (status.startsWith("completed")) els.crewMeta.textContent = `${state.viewingHistorical ? "ARCHIVED" : "COMPLETED"} · PROJECT ${projectId}`;
    else if (focus) els.crewMeta.textContent = `${focus.en} · ${status.replaceAll("_", " ").toUpperCase()}`;
  }
  refreshCrewConnectors();
  if (state.busy && project.status === "planning_live") setPipeline(pipelineFromCrewStates(states));
  else updatePipelineForProject(project);
}

function hydrateCrewRadio(project) {
  state.crewRadioLog = [];
  const logs = Array.isArray(project?.logs) ? project.logs.slice(-8) : [];
  const aliases = {
    director: ["Director Agent", "导演"],
    writer: ["Writer Agent", "编剧", "Script Supervisor"],
    visual_bible: ["Visual Bible Agent", "美术指导", "Art Director"],
    storyboard: ["Storyboard Agent", "分镜师"],
    quality: ["Quality Agent", "QC Agent", "质检"],
    generation: ["Generation Agent", "生成调度"],
    editor: ["Editor Agent", "剪辑"],
  };
  logs.forEach((line) => {
    const text = String(line);
    const match = AGENT_DEFS.find((def) => (aliases[def.id] || []).some((alias) => text.includes(alias)));
    const status = /fail|error|stale|interrupted/i.test(text)
      ? "ATTENTION"
      : /ready|complete|completed|passed|locked|approved|saved/i.test(text)
        ? "DONE"
        : "LOG";
    pushCrewRadio({ type: "status", agent: match?.id || "system", status, message: text });
  });
}

function eventErrorMessage(event) {
  if (!event) return "服务暂时不可用";
  const code = event.error_code ? `[${event.error_code}] ` : "";
  return `${code}${event.error_message || event.message || "服务暂时不可用"}`;
}

function renderProjectDiagnostics(project = state.project) {
  const diagnostics = project?.diagnostics;
  const job = project?.job;
  state.diagnostics = diagnostics || null;
  state.job = job || null;
  const readout = els.crewRecoveryReadout;
  if (!readout) return;
  readout.classList.remove("is-attention", "is-live");
  const jobStatus = String(job?.status || "").toLowerCase();
  if (job && ["running", "queued", "orphaned"].includes(jobStatus)) {
    const progress = job.progress || {};
    const progressText = progress.total ? ` · ${progress.completed || 0}/${progress.total}` : "";
    readout.classList.toggle("is-attention", jobStatus === "orphaned");
    readout.classList.toggle("is-live", jobStatus === "running" || jobStatus === "queued");
    readout.textContent = `${jobStatus === "orphaned" ? "RESUME AVAILABLE" : "LIVE"} · ${String(job.kind || job.stage || "PIPELINE").toUpperCase()}${progressText}`;
    readout.title = job.last_description || (jobStatus === "orphaned" ? "上次任务未正常结束，可重新提交以恢复。" : "任务仍在后台运行，页面断线不会丢失进度。");
    return;
  }
  if (!diagnostics) {
    readout.textContent = "";
    return;
  }
  const projectError = diagnostics.errors?.project;
  if (projectError) {
    readout.classList.add("is-attention");
    readout.textContent = `${projectError.error_code || "ERROR"} · ${diagnostics.recoverability?.next_action || "OPEN LOG"}`;
    readout.title = projectError.error_message || "项目需要处理";
    return;
  }
  const progress = diagnostics.progress || {};
  const next = diagnostics.recoverability?.next_action;
  const ready = `${progress.shots_ready || 0}/${progress.shots_total || 0} SHOTS`;
  readout.textContent = next ? `${ready} · NEXT ${next}` : ready;
  readout.title = (diagnostics.activity?.recent || []).at(-1) || "项目诊断已同步";
}

function isActiveJob(job = state.job) {
  return ["running", "queued", "orphaned"].includes(String(job?.status || "").toLowerCase());
}

function stopJobPolling() {
  jobPollRun += 1;
  if (jobPollTimer) window.clearTimeout(jobPollTimer);
  jobPollTimer = null;
}

function scheduleJobPolling(projectId) {
  if (!projectId || !isActiveJob(state.job)) {
    stopJobPolling();
    return;
  }
  const run = jobPollRun;
  if (jobPollTimer) window.clearTimeout(jobPollTimer);
  jobPollTimer = window.setTimeout(() => {
    if (run !== jobPollRun) return;
    refreshJobStatus(projectId, { poll: true });
  }, 5000);
}

async function refreshJobStatus(projectId, { poll = true } = {}) {
  if (!projectId) return;
  const requestedProject = String(projectId);
  const after = Number(state.jobCursor || 0);
  try {
    const response = await fetch(`/api/projects/${encodeURIComponent(requestedProject)}/job?after=${after}&limit=40`);
    const payload = await response.json().catch(() => ({}));
    if (String(state.project?.project_id || "") !== requestedProject) return;
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    if (payload.job?.job_id && state.job?.job_id && payload.job.job_id !== state.job.job_id && after > 0) {
      state.jobCursor = 0;
      return refreshJobStatus(requestedProject, { poll });
    }
    state.job = payload.job || null;
    state.project.job = state.job;
    state.jobCursor = Number(payload.next_cursor || state.job?.event_seq || after || 0);
    renderProjectDiagnostics(state.project);
    const events = Array.isArray(payload.events) ? payload.events : [];
    const latest = events[events.length - 1];
    if (latest?.description || latest?.message) {
      appendCrewStatus(latest.agent || "system", String(latest.status || "SYNC"), latest.description || latest.message);
    }
    if (poll && isActiveJob(state.job)) scheduleJobPolling(requestedProject);
    else if (!isActiveJob(state.job)) stopJobPolling();
  } catch (error) {
    if (poll && String(state.project?.project_id || "") === requestedProject) scheduleJobPolling(requestedProject);
  }
}

function syncHistoricalCrew(project) {
  state.workingAgent = null;
  state.crewDetails = {};
  syncCrewBoard(project, { silent: true });
  hydrateCrewRadio(project);
  renderProjectDiagnostics(project);
  state.jobCursor = 0;
  refreshJobStatus(project?.project_id, { poll: true });
}

/* ── 第三幕 · 工作区渲染 ───────────────────────────────────── */

function shotStatusInfo(status) {
  return SHOT_STATUS[status] || status || "QUEUED";
}

const formatShotDuration = (value) => MovieAgentModules.storyboard.formatShotDuration(value);
const timingModeLabel = (shot = {}) => MovieAgentModules.storyboard.timingModeLabel(shot);
const shotStateInfo = (shot = {}) => MovieAgentModules.storyboard.shotStateInfo(shot);

function durationRailShare(value) {
  return `${Math.min(94, Math.max(18, Number(value || 1) / 12 * 100)).toFixed(1)}%`;
}

function bindShotDurationRail(card, project, shot) {
  const rail = card.querySelector(".shot-duration-rail");
  const handle = rail?.querySelector(".shot-duration-handle");
  if (!rail || !handle) return;
  handle.addEventListener("click", (event) => event.stopPropagation());
  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const startDuration = Number(shot.duration_seconds || 1);
    const pixelsPerSecond = Math.max(10, rail.getBoundingClientRect().width / 12);
    handle.setPointerCapture?.(event.pointerId);
    const durationValue = card.querySelector(".shot-duration-value");
    const meta = card.querySelector(".shot-technical-meta");
    const move = (moveEvent) => {
      const delta = Math.round(((moveEvent.clientX - startX) / pixelsPerSecond) * 2) / 2;
      const next = Math.max(1, Math.min(80, startDuration + delta));
      rail.dataset.previewDuration = String(next);
      rail.style.setProperty("--shot-duration-share", durationRailShare(next));
      handle.setAttribute("aria-valuenow", String(next));
      handle.setAttribute("aria-valuetext", `${next.toFixed(1)} 秒`);
      if (durationValue) durationValue.textContent = formatShotDuration(next);
      if (meta) meta.textContent = `REV ${String(shot.revision || 1).padStart(2, "0")} · ${String(shot.generation_mode || "T2V").toUpperCase()} · ${next.toFixed(1)}s · ${timingModeLabel({ timing_mode: next < startDuration ? "trim" : "extend" })}`;
    };
    const finish = async () => {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", finish);
      handle.removeEventListener("pointercancel", finish);
      const next = Number(rail.dataset.previewDuration || startDuration);
      if (next === startDuration) return;
      try {
        const payload = await MovieAgentModules.api.requestJSON(`/api/projects/${project.project_id}/shots/${shot.number}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ desired_duration: next, timing_mode: next < startDuration ? "trim" : "extend" }),
        });
        state.project = payload;
        renderWorkspace(payload, { tab: "storyboard" });
        toast(`镜头 ${shot.number} 已调整为 ${next.toFixed(1)}s，字幕与配乐已重新对齐。`);
      } catch (error) {
        renderWorkspace(project, { tab: "storyboard" });
        toast(`调整镜头时长失败：${error.message}`, true);
      }
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", finish, { once: true });
    handle.addEventListener("pointercancel", finish, { once: true });
  });
}

function renderFilmstrip(project, entranceFrom = Number.POSITIVE_INFINITY) {
  const shots = project.storyboard || [];
  els.filmstripMeta.textContent = `${shots.length} 镜 · 共 ${shots.reduce((sum, s) => sum + (s.duration_seconds || 0), 0)} 秒 · ${esc(project.visual_style)}`;
  els.filmstrip.innerHTML = "";
  if (!shots.length) {
    els.filmstrip.innerHTML = '<p class="empty-note">片场尚未开机。</p>';
    return;
  }
  for (const [index, shot] of shots.entries()) {
    const card = document.createElement("article");
    card.className = `shot-card${index >= entranceFrom ? " card-enter" : ""}${Number(shot.number) === Number(state.activeShotNumber) ? " is-current" : ""}`;
    card.dataset.shot = shot.number;
    card.dataset.status = shot.status || "planned";
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `镜头 ${shot.number} 详情`);
    const stateInfo = shotStateInfo(shot);
    const duration = Number(shot.duration_seconds || 0);
    const revision = Number(shot.revision || shot.attempts || 1);
    card.innerHTML = `
      <header class="shot-head type-system-meta"><span>SHOT ${String(shot.number).padStart(2, "0")}</span><span class="shot-duration-value">${formatShotDuration(duration)}</span></header>
      <div class="shot-frame"><span class="shot-frame-lens" aria-hidden="true"><i class="shot-frame-sketch"></i><i class="shot-frame-color"></i></span><span class="film-stamp type-system-meta">${String(shot.number).padStart(2, "0")} · 24 FPS</span><span class="shot-framing type-control">${esc(shot.framing)}</span><span class="shot-mode type-system-meta">${esc(shot.generation_mode)}</span></div>
      <footer class="shot-foot type-system-meta">
        <span class="shot-status" data-state="${stateInfo.key}"><span class="shot-status-symbol" aria-hidden="true">${stateInfo.symbol}</span><span>${stateInfo.label}</span></span>
        <span class="shot-attempts">${shot.attempts > 0 ? `↻${shot.attempts}` : ""}</span>
        <span class="shot-technical-meta">REV ${String(revision).padStart(2, "0")} · ${String(shot.generation_mode || "T2V").toUpperCase()} · ${duration.toFixed(1)}s · ${timingModeLabel(shot)}</span>
        <span class="shot-duration-rail" style="--shot-duration-share: ${durationRailShare(duration)}" aria-label="拖动修改镜头 ${shot.number} 时长"><button class="shot-duration-handle" type="button" role="slider" aria-label="镜头 ${shot.number} 时长" aria-valuemin="1" aria-valuemax="80" aria-valuenow="${duration}" aria-valuetext="${duration.toFixed(1)} 秒"></button></span>
      </footer>`;
    card.addEventListener("click", () => openDrawer(project, shot.number));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDrawer(project, shot.number);
      }
    });
    bindShotDurationRail(card, project, shot);
    els.filmstrip.appendChild(card);
  }
  attachShotPreviews(project);
  syncInspectorSelection();
}

function renderTimeline(project) {
  const shots = project.storyboard || [];
  const total = shots.reduce((sum, shot) => sum + Number(shot.duration_seconds || 0), 0);
  els.timelineTotal.textContent = shots.length ? `00:00:${String(total).padStart(2, "0")} · ${shots.length} SHOTS` : "等待分镜";
  els.editTimeline.innerHTML = "";
  for (const shot of shots) {
    const segment = document.createElement("button");
    segment.type = "button";
    segment.className = "timeline-segment";
    segment.dataset.shot = shot.number;
    segment.dataset.status = shot.status || "planned";
    segment.style.flexGrow = String(Math.max(1, shot.duration_seconds || 1));
    segment.title = `镜头 ${shot.number} · ${shot.duration_seconds} 秒 · ${shotStateInfo(shot).label}`;
    segment.setAttribute("aria-label", segment.title);
    segment.innerHTML = `<span>${String(shot.number).padStart(2, "0")}</span><span class="timeline-mode">${timingModeLabel(shot)}</span><i class="timeline-resize-handle" title="拖动调整镜头时长" aria-label="拖动调整镜头时长"></i>`;
    segment.addEventListener("click", () => openDrawer(project, shot.number));
    const handle = segment.querySelector(".timeline-resize-handle");
    handle?.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const startX = event.clientX;
      const startDuration = Number(shot.duration_seconds || 1);
      const startTotal = Math.max(1, total);
      handle.setPointerCapture?.(event.pointerId);
      const move = (moveEvent) => {
        const width = Math.max(240, els.editTimeline.getBoundingClientRect().width);
        const delta = Math.round((moveEvent.clientX - startX) / (width / startTotal));
        const next = Math.max(1, Math.min(80, startDuration + delta));
        segment.style.flexGrow = String(next);
        segment.dataset.previewDuration = String(next);
        segment.title = `镜头 ${shot.number} · ${next} 秒 · 拖动中`;
      };
      const up = async () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", up);
        const next = Number(segment.dataset.previewDuration || startDuration);
        if (next === startDuration) return;
        try {
          const response = await fetch(`/api/projects/${project.project_id}/shots/${shot.number}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ desired_duration: next, timing_mode: next < startDuration ? "trim" : "extend" }),
          });
          const payload = await response.json();
          if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
          state.project = payload;
          renderWorkspace(payload, { tab: "storyboard" });
          toast(`镜头 ${shot.number} 已调整为 ${next}s，字幕与配乐已重新对齐。`);
        } catch (error) {
          renderTimeline(project);
          toast(`调整镜头时长失败：${error.message}`, true);
        }
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", up, { once: true });
    });
    els.editTimeline.appendChild(segment);
  }
  syncInspectorSelection();
}

function attachShotPreviews(project) {
  for (const shot of project.storyboard || []) {
    if (!["approved_comfyui", "generated_comfyui"].includes(shot.status)) continue;
    const url = `/api/projects/${project.project_id}/shots/${shot.number}/video`;
    fetch(url, { method: "HEAD" }).then((response) => {
      if (!response.ok) return;
      const card = els.filmstrip.querySelector(`.shot-card[data-shot="${shot.number}"] .shot-frame`);
      if (!card || card.querySelector("video")) return;
      const video = document.createElement("video");
      video.src = url;
      video.muted = true;
      video.loop = true;
      video.playsInline = true;
      video.preload = "metadata";
      card.classList.add("is-developing");
      card.appendChild(video);
      const shotCard = card.closest(".shot-card");
      shotCard.classList.add("has-media");
      window.setTimeout(() => shotCard.classList.remove("is-developing"), REDUCED_MOTION ? 0 : 720);
      shotCard.addEventListener("mouseenter", () => video.play().catch(() => {}));
      shotCard.addEventListener("mouseleave", () => {
        video.pause();
        video.currentTime = 0;
      });
    }).catch(() => {});
  }
}

function renderShotMap(project) {
  els.shotMap.innerHTML = "";
  for (const shot of project.storyboard || []) {
    const cell = document.createElement("i");
    cell.dataset.status = shot.status || "planned";
    cell.title = `镜头 ${shot.number} · ${shotStatusInfo(shot.status)}`;
    els.shotMap.appendChild(cell);
  }
}

function renderLogFeed(project) {
  const lines = (project.logs || []).map((line) => String(line)).filter(Boolean);
  els.logFeed.textContent = lines.join("\n");
  if (els.monitorActivityRecent) {
    els.monitorActivityRecent.textContent = lines.slice(-3).join("\n") || "等待片场信号";
  }
  els.logFeed.scrollTop = els.logFeed.scrollHeight;
}

function setMonitorTimecode(live) {
  clearInterval(monitorTimecodeTimer);
  els.monitorTc.classList.toggle("hidden", !live);
  if (!live) return;
  const tick = () => {
    const elapsed = Math.max(0, performance.now() - state.renderStartedAt);
    const frames = Math.floor((elapsed / 1000) * 24);
    const seconds = Math.floor(frames / 24);
    const ff = String(frames % 24).padStart(2, "0");
    els.monitorTc.textContent = `TC ${timecode(seconds)}:${ff}`;
  };
  tick();
  monitorTimecodeTimer = setInterval(tick, 42);
}

function renderMonitor(project, live = false) {
  els.projectIdLabel.textContent = project.project_id;
  els.renderRec.classList.toggle("live", live);
  const shots = project.storyboard || [];
  const approved = shots.filter(isShotReady).length;
  const allReady = shots.length > 0 && approved === shots.length;
  const finalDelivered = String(project.status || "").startsWith("completed");
  if (els.shotsReady) els.shotsReady.textContent = `${approved}/${shots.length} SHOTS READY`;
  if (els.renderReadiness) {
    els.renderReadiness.classList.toggle("hidden", !allReady || finalDelivered);
  }
  if (els.btnAiEdit) {
    els.btnAiEdit.disabled = state.editing || !allReady;
    els.btnAiEdit.innerHTML = state.editing
      ? "AI Edit 粗剪中…"
      : 'AI 剪辑成片 <span class="cta-arrow" aria-hidden="true">→</span>';
  }
  setMonitorTimecode(live);
  if (live) {
    els.monitorShot.textContent = `SHOT ${approved}/${shots.length}`;
    els.monitorPct.textContent = shots.length ? `${Math.round((approved / shots.length) * 100)}%` : "";
    els.monitorBar.style.width = shots.length ? `${(approved / shots.length) * 100}%` : "0%";
  } else {
    els.monitorShot.textContent = allReady ? `${shots.length}/${shots.length} READY` : "STANDBY";
    els.monitorPct.textContent = allReady ? "100%" : "";
    els.monitorBar.style.width = allReady ? "100%" : "0%";
    els.monitorDesc.textContent = allReady
      ? `${shots.length}/${shots.length} SHOTS READY · DELIVER 当前阶段：点击 AI 剪辑成片进入 Rough Cut。`
      : `${PROJECT_STATUS[project.status] || project.status} · ${shots.length} 个镜头，${approved} 个已通过。`;
  }
}

function typewriteManualBody() {
  const run = ++manualTypingRun;
  const nodes = Array.from(els.manualBody.querySelectorAll(".manual-type, dd, .story p, .narration, .checklist li"));
  let nodeIndex = 0;
  const typeNext = () => {
    if (run !== manualTypingRun || nodeIndex >= nodes.length) return;
    const node = nodes[nodeIndex++];
    const text = node.textContent || "";
    if (!text) {
      typeNext();
      return;
    }
    node.textContent = "";
    node.classList.add("is-typing");
    let index = 0;
    const tick = () => {
      if (run !== manualTypingRun) return;
      index = Math.min(text.length, index + 3);
      node.textContent = text.slice(0, index);
      if (index < text.length) {
        setTimeout(tick, 13);
      } else {
        node.classList.remove("is-typing");
        setTimeout(typeNext, 70);
      }
    };
    tick();
  };
  typeNext();
}

const MANUAL_FIELD_EN = {
  主题: "THEME",
  原始创意: "ORIGINAL IDEA",
  核心冲突: "CORE CONFLICT",
  叙事弧线: "NARRATIVE ARC",
  视觉风格: "VISUAL STYLE",
  目标时长: "TARGET DURATION",
  角色卡: "CHARACTER CARD",
  场景卡: "SCENE CARD",
  风格卡: "STYLE CARD",
  声音卡: "SOUND CARD",
};

function compactDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function manualProductionStatus(project) {
  const status = String(project?.status || "");
  const shots = project?.storyboard || [];
  if (status.startsWith("completed")) return { key: "complete", symbol: "✓", label: "QC PASSED", copy: "制作手册已通过质量门" };
  if (status === "awaiting_visual_review") return { key: "review", symbol: "!", label: "QC REVIEW", copy: "请逐镜批准视觉连续性" };
  if (status === "rough_cut_ready") return { key: "complete", symbol: "✓", label: "QC PASSED", copy: "分镜与连续性检查已通过" };
  if (status === "editing_rough_cut") return { key: "active", symbol: "●", label: "PREVIS / LOCKED", copy: "分镜已锁定，正在整理剪辑" };
  if (status === "ready_for_ai_edit") return { key: "complete", symbol: "✓", label: "PREVIS / LOCKED", copy: "分镜已就绪，可进入后续制作" };
  if (status.includes("render")) return { key: "active", symbol: "●", label: "BIBLE LOCKED", copy: "制作手册已锁定，镜头正在生成" };
  if (shots.length >= 6 && (project?.quality_report || []).length) return { key: "complete", symbol: "✓", label: "QC PASSED", copy: "已通过策划质检" };
  if (shots.length) return { key: "active", symbol: "●", label: "PREVIS / DRAFT", copy: "分镜正在生长" };
  return { key: "active", symbol: "●", label: "BIBLE / DRAFT", copy: "剧组正在策划" };
}

function renderManualSummary(project) {
  if (!project) {
    els.manualSummary.innerHTML = '<p class="empty-note">等待项目进入制作手册。</p>';
    return;
  }
  const shots = project.storyboard || [];
  const total = shots.reduce((sum, shot) => sum + Number(shot.duration_seconds || 0), 0) || Number(project.duration_seconds || 0);
  const status = manualProductionStatus(project);
  const filmId = String(project.project_id || "film-01").replace(/^film-/, "").toUpperCase();
  const filmTitle = manualFilmTitle(project);
  const logline = manualProjectLogline(project);
  els.manualSummary.innerHTML = `
    <div class="manual-project-line">
      <div>
        <span class="manual-project-id type-system-meta">FILM ${esc(filmId)} / ${shots.length ? "CUT 01" : "PREP"}</span>
        <h3>${esc(filmTitle)}</h3>
        ${logline ? `<p class="manual-project-logline">${esc(logline)}</p>` : ""}
      </div>
      <span class="manual-project-status ${status.key} type-status"><i>${status.symbol}</i>${status.label}</span>
    </div>
    <div class="manual-stats" role="list" aria-label="项目摘要">
      <div role="listitem"><span class="type-system-meta">SHOTS</span><strong>${shots.length || "·"}</strong></div>
      <div role="listitem"><span class="type-system-meta">DURATION</span><strong>${shots.length ? compactDuration(total) : "·"}</strong></div>
      <div role="listitem"><span class="type-system-meta">FRAME</span><strong>16:9</strong></div>
      <div role="listitem"><span class="type-system-meta">STATUS</span><strong>${esc(status.copy)}</strong></div>
    </div>`;
}

function uniqueLogEntries(project) {
  const entries = [...(project?.logs || [])];
  if (!entries.length && (project?.quality_report || []).length) entries.push(...project.quality_report);
  const seen = new Set();
  return entries.filter((entry) => {
    const clean = String(entry || "").replace(/\s+/g, " ").trim();
    if (!clean || seen.has(clean)) return false;
    seen.add(clean);
    return true;
  });
}

function renderAgentActivity(project) {
  if (!project) {
    els.activitySummary.textContent = "等待片场信号";
    els.activityBody.innerHTML = '<p class="activity-empty">项目创建后，剧组沟通和检查记录会归档在这里。</p>';
    return;
  }
  const entries = uniqueLogEntries(project);
  const assets = [project.brief, project.script, project.visual_bible, project.storyboard, project.quality_report]
    .filter((value) => (Array.isArray(value) ? value.length : value && Object.keys(value).length)).length;
  const status = String(project.status || "");
  const agentsDone = status.startsWith("completed")
    ? 7
    : Math.min(7, assets + (project.rough_cut_placeholder ? 1 : 0) + (project.final_output_placeholder ? 1 : 0));
  const checks = (project.quality_report || []).length;
  els.activitySummary.textContent = `${checks || 0} CHECKS · ${agentsDone}/7 AGENTS`;
  els.activityBody.innerHTML = entries.length
    ? `<ol class="activity-list">${entries.map((entry) => `<li><span class="activity-mark">✓</span><span>${esc(entry)}</span></li>`).join("")}</ol>`
    : '<p class="activity-empty">暂无活动记录。</p>';
}

function manualFieldLabel(key) {
  return MANUAL_FIELD_EN[key] ? `${MANUAL_FIELD_EN[key]} / ${key}` : String(key).toUpperCase();
}

function shotSceneNumber(number, total) {
  if (!total) return 1;
  return Math.min(3, Math.max(1, Math.ceil((Number(number) / total) * 3)));
}

function shotWorkflowState(status) {
  return shotStateInfo({ status });
}

function shotCameraAngle(shot) {
  return String(shot.framing || "").includes("低机位") ? "LOW ANGLE / 低机位" : "EYE LEVEL / 视线平齐";
}

function shotMovement(shot) {
  const text = `${shot.image_description || ""} ${shot.action || ""} ${shot.prompt || ""}`;
  if (/推进|推近|靠近/.test(text)) return "SLOW PUSH-IN / 缓慢推进";
  if (/拉远|后退/.test(text)) return "SLOW PULL-BACK / 缓慢拉远";
  if (/横移|平移/.test(text)) return "LATERAL TRACK / 横向移动";
  if (/环绕|旋转/.test(text)) return "ORBIT / 环绕";
  return "STABLE HOLD / 稳定保持";
}

function shotChecks(shot) {
  const stateInfo = shotWorkflowState(shot.status);
  const complete = stateInfo.key === "complete";
  const failed = stateInfo.key === "failed";
  const review = stateInfo.key === "review";
  const promptReady = String(shot.prompt || "").trim().length >= 20;
  return [
    { label: "CHARACTER CONSISTENCY", status: failed ? "FAILED" : review ? "REVIEW" : complete ? "COMPLETE" : "QUEUED", symbol: failed || review ? "!" : complete ? "✓" : "○" },
    { label: "SCENE CONSISTENCY", status: failed ? "FAILED" : review ? "REVIEW" : complete ? "COMPLETE" : "QUEUED", symbol: failed || review ? "!" : complete ? "✓" : "○" },
    { label: "PROMPT INTEGRITY", status: promptReady ? "COMPLETE" : "QUEUED", symbol: promptReady ? "✓" : "○" },
    { label: "IP / COPYRIGHT CHECK", status: complete ? "COMPLETE" : "QUEUED", symbol: complete ? "✓" : "○" },
  ];
}

function renderBriefTab(project) {
  const entries = Object.entries(project.brief || {});
  const rows = [
    ["ORIGINAL IDEA", "原始创意", project.idea],
    ["TARGET DURATION", "目标时长", `${project.duration_seconds || "·"} 秒`],
    ["VISUAL STYLE", "视觉风格", project.visual_style],
    ...entries.map(([key, value]) => [manualFieldLabel(key), key, value]),
  ];
  const unique = rows.filter((row, index, list) => row[2] && list.findIndex((item) => item[1] === row[1]) === index);
  return `
    <section class="manual-intro">
      <span class="manual-section-kicker type-system-meta">DIRECTOR'S NOTE / 导演定调</span>
      <h3>先确定这部电影为何存在。</h3>
      <p class="manual-type type-helper">从创意、主题到叙事边界，导演 Agent 将每一个上游决定交给后续剧组。</p>
    </section>
    <div class="brief-sheet">${unique.map(([en, key, value]) => `
      <div class="brief-row"><span class="manual-label type-ui-label">${esc(en)}</span><span class="brief-key">${esc(key)}</span><p class="manual-type type-helper">${esc(value)}</p></div>`).join("") || '<p class="empty-note type-helper">暂无项目设定。</p>'}</div>`;
}

function productionValueMarkup(value, depth = 0) {
  if (depth > 3) return `<p class="visual-spec-copy-line">${esc(String(value ?? ""))}</p>`;
  let normalized = value;
  if (typeof normalized === "string") {
    const candidate = normalized.trim();
    if ((candidate.startsWith("{") && candidate.endsWith("}")) || (candidate.startsWith("[") && candidate.endsWith("]"))) {
      try {
        const parsed = JSON.parse(candidate);
        if (parsed && typeof parsed === "object") normalized = parsed;
      } catch {
        // Natural-language production notes are intentionally left as copy.
      }
    }
  }
  if (Array.isArray(normalized)) {
    return `<ul class="production-readable-list">${normalized.map((item, index) => `<li><span class="production-list-index mono">${String(index + 1).padStart(2, "0")}</span><div>${productionValueMarkup(item, depth + 1)}</div></li>`).join("")}</ul>`;
  }
  if (normalized && typeof normalized === "object") {
    return `<dl class="production-readable-dl">${Object.entries(normalized).map(([key, item]) => `<div><dt>${esc(String(key).replace(/[_-]+/g, " ").toUpperCase())}</dt><dd>${productionValueMarkup(item, depth + 1)}</dd></div>`).join("")}</dl>`;
  }
  const copy = String(normalized ?? "").trim();
  if (!copy) return '<p class="visual-spec-copy-line is-empty">暂无已锁定内容。</p>';
  return copy.split(/\n+/).filter(Boolean).map((line) => `<p class="visual-spec-copy-line">${esc(line.trim())}</p>`).join("");
}

function renderScriptTab(project) {
  const script = project.script || {};
  const story = String(script.story || "").split(/\n+/).filter(Boolean);
  const narration = String(script.narration || "").trim();
  const dialogue = Array.isArray(script.dialogue_book) ? script.dialogue_book : [];
  const subtitles = Array.isArray(script.subtitle_track) ? script.subtitle_track : dialogue;
  const locked = Boolean(script.dialogue_locked);
  const rows = dialogue.map((entry, index) => {
    const cue = subtitles[index] || entry || {};
    const start = Number(entry?.start_seconds ?? cue?.start_seconds ?? 0).toFixed(2);
    const end = Number(entry?.end_seconds ?? cue?.end_seconds ?? 0).toFixed(2);
    return `
      <article class="dialogue-row" data-dialogue-row="${index}">
        <header class="dialogue-row-head"><span class="dialogue-shot type-system-meta">SHOT ${String(entry?.shot || index + 1).padStart(2, "0")}</span><span class="dialogue-time type-system-meta">${start}s · ${end}s</span><span class="dialogue-kind type-system-meta">${esc(entry?.kind || "narration")}</span></header>
        <div class="dialogue-row-fields">
          <label><span class="manual-label type-ui-label">DIALOGUE / 台词本</span><textarea data-dialogue-field="text" rows="2" ${locked ? "disabled" : ""}>${esc(entry?.text || "")}</textarea></label>
          <label><span class="manual-label type-ui-label">SUBTITLE / 字幕轨</span><textarea data-dialogue-field="subtitle" rows="2" ${locked ? "disabled" : ""}>${esc(cue?.text || entry?.text || "")}</textarea></label>
        </div>
        <label class="dialogue-speaker"><span class="manual-label type-ui-label">SPEAKER / 说话人</span><input data-dialogue-field="speaker" value="${esc(entry?.speaker || "旁白")}" ${locked ? "disabled" : ""}></label>
      </article>`;
  }).join("");
  return `
    <section class="screenplay-reader">
      <header class="screenplay-head type-system-meta"><span>SCREENPLAY / DIALOGUE BOOK</span><span>${story.length ? `${story.length} SCENES` : "AWAITING DRAFT"}</span></header>
      <div class="screenplay-body">${story.map((para, index) => `<p><span class="screenplay-line-no type-system-meta">${String(index + 1).padStart(2, "0")}</span><span class="manual-type type-helper">${esc(para)}</span></p>`).join("") || '<p class="empty-note type-helper">暂无剧本。</p>'}</div>
      ${narration ? `<aside class="screenplay-narration"><span class="manual-label type-ui-label">NARRATION / 旁白</span><p class="manual-type type-helper">${esc(narration)}</p></aside>` : ""}
      <section class="dialogue-book" aria-label="台词本与字幕轨">
        <header class="dialogue-book-head"><div><span class="manual-section-kicker type-system-meta">WRITER DELIVERABLE / 编剧正式产物</span><h3>台词本 / 字幕稿</h3><p class="manual-type type-helper">先审阅每一镜的对白与旁白，锁定后才会进入配音、字幕和 AI Edit。</p></div><span class="dialogue-lock-badge ${locked ? "is-locked" : "is-draft"} type-status">${locked ? "LOCKED ✓" : "DRAFT · 待锁定"}</span></header>
        <div class="dialogue-rows">${rows || '<p class="empty-note">编剧完成后，这里会按镜头生成可编辑台词与字幕。</p>'}</div>
        <footer class="dialogue-book-actions"><span class="dialogue-revision type-system-meta">VERSION ${esc(script.dialogue_revision || 1)} · ${dialogue.length} CUES · ${locked ? "DOWNSTREAM LOCKED" : "EDITABLE BEFORE RENDER"}</span><div>${locked ? '<button class="ghost type-control" data-script-unlock type="button">解锁并修改</button>' : `<button class="ghost type-control" data-script-save type="button" ${!dialogue.length ? "disabled" : ""}>保存台词修改</button><button class="cta type-control" data-script-lock type="button" ${!dialogue.length ? "disabled" : ""}>锁定台词本 →</button>`}</div></footer>
      </section>
    </section>`;
}

function renderVisualTab(project) {
  const entries = Object.entries(project.visual_bible || {});
  const palette = [
    ["SHADOW", "#080706"],
    ["PANEL", "#17140f"],
    ["AMBER", "#d7a64a"],
    ["HIGHLIGHT", "#eee8dd"],
  ];
  return `
    <section class="manual-intro visual-intro">
      <span class="manual-section-kicker type-system-meta">ART DEPARTMENT / 美术部门</span>
      <h3>所有镜头共享同一套世界规则。</h3>
      <p class="manual-type type-helper">角色、场景、风格与声音被锁定为可复用的视觉连续性约束。</p>
    </section>
    <div class="visual-board">${entries.map(([key, value]) => `
      <section class="visual-spec"><header><span class="manual-label type-ui-label">${esc(manualFieldLabel(key))}</span><span class="visual-lock type-status">LOCKED ✓</span></header><h4>${esc(String(key).replace(/[_-]+/g, " "))}</h4><div class="visual-spec-copy">${productionValueMarkup(value)}</div></section>`).join("") || '<p class="empty-note type-helper">暂无视觉规范。</p>'}</div>
    <div class="visual-palette"><span class="manual-label type-ui-label">STUDIO PALETTE / 片场参考色</span><div>${palette.map(([label, color]) => `<span class="palette-chip"><i style="--chip:${color}"></i><b class="type-system-meta">${label}</b></span>`).join("")}</div></div>`;
}

function renderShotSheet(project) {
  const shots = project.storyboard || [];
  if (!shots.length) return '<p class="empty-note">分镜师完成拆解后，Shot Sheet 会在这里逐张冲印。</p>';
  if (!shots.some((shot) => shot.number === state.manualShotNumber)) state.manualShotNumber = shots[0].number;
  const active = shots.find((shot) => shot.number === state.manualShotNumber) || shots[0];
  const activeState = shotWorkflowState(active.status);
  const nav = [];
  let lastScene = 0;
  for (const shot of shots) {
    const scene = shotSceneNumber(shot.number, shots.length);
    if (scene !== lastScene) {
      lastScene = scene;
      nav.push(`<div class="shot-scene-label type-system-meta">SCENE ${String(scene).padStart(2, "0")}</div>`);
    }
    const status = shotWorkflowState(shot.status);
      nav.push(`<button class="shot-nav-item type-control${shot.number === active.number ? " is-active" : ""}" type="button" data-manual-shot="${shot.number}" aria-label="打开镜头 ${shot.number}"><span class="shot-nav-no type-system-meta">${String(shot.number).padStart(2, "0")}</span><span class="shot-nav-copy"><b>${esc(truncate(shot.image_description, 30))}</b><small class="type-status">${esc(status.label)}</small></span><span class="shot-nav-duration type-system-meta">${shot.duration_seconds}s</span><span class="shot-nav-state ${status.key}" aria-label="${status.label}">${status.symbol}</span></button>`);
  }
  const qc = shotChecks(active);
  return `
    <div class="shot-sheet">
      <aside class="shot-nav"><header class="shot-nav-head"><span class="manual-label type-ui-label">SHOT LIST</span><span class="type-system-meta">${shots.length} SHOTS</span></header><div class="shot-nav-list">${nav.join("")}</div></aside>
      <article class="shot-detail">
        <header class="shot-detail-head"><div><span class="manual-section-kicker type-system-meta">SCENE ${String(shotSceneNumber(active.number, shots.length)).padStart(2, "0")} / SHOT ${String(active.number).padStart(2, "0")}</span><h3>镜头 ${String(active.number).padStart(2, "0")}</h3><p class="manual-type type-helper">${esc(active.image_description)}</p></div><span class="shot-detail-status ${activeState.key} type-status"><i>${activeState.symbol}</i>${activeState.label}</span></header>
        <div class="shot-facts"><div><span class="manual-label type-ui-label">DURATION</span><strong>${active.duration_seconds}s</strong></div><div><span class="manual-label type-ui-label">FRAMING</span><strong>${esc(active.framing)}</strong></div><div><span class="manual-label type-ui-label">CAMERA</span><strong>${esc(shotCameraAngle(active))}</strong></div><div><span class="manual-label type-ui-label">MOVEMENT</span><strong>${esc(shotMovement(active))}</strong></div></div>
        <div class="shot-detail-grid"><section><span class="manual-label type-ui-label">ACTION / 动作</span><p class="manual-type type-helper">${esc(active.action)}</p></section><section><span class="manual-label type-ui-label">SOUND / 声音</span><p class="manual-type type-helper">${esc(active.sound_design)}</p></section></div>
        <section class="shot-prompt"><header><span class="manual-label type-ui-label">VISUAL PROMPT / 最终提示词</span><span class="type-system-meta">${esc(active.generation_mode)}</span></header><p class="manual-type type-helper">${esc(active.prompt)}</p></section>
         <section class="shot-qc"><header><span class="manual-label type-ui-label">QC GATE / 质检门</span><span class="type-system-meta">${active.attempts ? `TAKE ${active.attempts}` : "TAKE 01"}</span></header><div class="shot-qc-grid">${qc.map((item) => `<div class="shot-qc-item ${item.status === "COMPLETE" ? "complete" : item.status === "FAILED" ? "failed" : item.status === "REVIEW" ? "review" : "queued"}"><i>${item.symbol}</i><span>${item.label}</span><b class="type-status">${item.status}</b></div>`).join("")}</div></section>
      </article>
    </div>`;
}

function renderManual(project, tab = state.manualTab, animate = false) {
  manualTypingRun += 1;
  state.manualTab = tab;
  const liveTabs = {
    brief: Boolean(project && Object.keys(project.brief || {}).length),
    script: Boolean(project && Object.keys(project.script || {}).length),
    visual: Boolean(project && Object.keys(project.visual_bible || {}).length),
    quality: Boolean(project && (project.quality_report || []).length),
  };
  $$("#manual-tabs .tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tab);
    button.classList.toggle("is-live", Boolean(liveTabs[button.dataset.tab]));
    button.setAttribute("aria-selected", String(button.dataset.tab === tab));
  });
  $$("[data-manual-nav-tab]").forEach((button) => button.classList.toggle("is-active", button.dataset.manualNavTab === tab));
  const body = els.manualBody;
  if (!project) {
    body.innerHTML = '<p class="empty-note">制作手册会在项目创建后生成。</p>';
    body.setAttribute("aria-labelledby", "manual-tab-brief");
    renderManualSummary(null);
    renderAgentActivity(null);
    return;
  }
  if (tab === "brief") {
    body.innerHTML = renderBriefTab(project);
  } else if (tab === "script") {
    body.innerHTML = renderScriptTab(project);
  } else if (tab === "visual") {
    body.innerHTML = renderVisualTab(project);
  } else {
    body.innerHTML = renderShotSheet(project);
  }
  body.setAttribute("aria-labelledby", `manual-tab-${tab}`);
  body.classList.remove("is-editorial-reveal");
  if (!REDUCED_MOTION) {
    void body.offsetWidth;
    body.classList.add("is-editorial-reveal");
  }
  renderManualSummary(project);
  renderAgentActivity(project);
  if (animate) typewriteManualBody();
  if (tab === "quality") {
    body.querySelectorAll("[data-manual-shot]").forEach((button) => {
      button.addEventListener("click", () => {
        state.manualShotNumber = Number(button.dataset.manualShot);
        renderManual(project, "quality");
      });
    });
  }
}

const deliverRuntime = (project) => MovieAgentModules.deliver.deliverRuntime(project);

function mediaQualityLabel(record, video = null) {
  const explicit = String(record?.resolution_label || "").toUpperCase();
  if (explicit) return explicit;
  const width = Number(record?.width || video?.videoWidth || 0);
  const height = Number(record?.height || video?.videoHeight || 0);
  if (width && height) {
    if (width < 1280 || height < 720) return "LOW RES SOURCE";
    if (width < 1920 || height < 1080) return "720P";
    return "1080P";
  }
  const quality = String(record?.quality || "").toUpperCase();
  return quality || "QUALITY UNKNOWN";
}

function renderMediaQuality(project, mode = "screening") {
  const snapshot = project?.video_quality || {};
  state.videoQuality = snapshot;
  const requestedMode = state.previewQualityMode !== "auto"
    ? state.previewQualityMode
    : String(mode || "auto").toLowerCase();
  const effectiveMode = requestedMode === "auto"
    ? (state.hasFinalVideo ? "screening" : "proxy")
    : requestedMode;
  const record = effectiveMode === "proxy"
    ? snapshot.working_proxy
    : effectiveMode === "original"
      ? (snapshot.final_master || snapshot.source || snapshot.screening_preview)
      : (snapshot.screening_preview || snapshot.final_master || snapshot.working_proxy);
  const label = mediaQualityLabel(record, state.hasFinalVideo ? els.finalVideo : els.roughCutVideo);
  const prefix = state.previewQualityMode === "auto" ? "AUTO" : effectiveMode.toUpperCase();
  if (els.deliverQualityReadout) {
    els.deliverQualityReadout.textContent = `QUALITY: ${prefix} · ${label}`;
    els.deliverQualityReadout.dataset.quality = label.toLowerCase().replaceAll(" ", "-");
  }
  const lowRes = label === "LOW RES SOURCE" || Boolean(snapshot.source_low_res);
  const native = snapshot.native_resolution || record?.native_resolution || "UNKNOWN";
  const screening = snapshot.screening_preview?.resolution_label || snapshot.screening_preview?.quality || "NOT AVAILABLE";
  const master = snapshot.final_master?.resolution_label || snapshot.final_master?.quality || "NOT AVAILABLE";
  if (els.deliverQualityMode) els.deliverQualityMode.textContent = state.previewQualityMode.toUpperCase();
  els.deliverQualityModes?.querySelectorAll("[data-quality-mode]").forEach((button) => {
    const selected = button.dataset.qualityMode === state.previewQualityMode;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
  if (els.deliverQualitySource) els.deliverQualitySource.textContent = native;
  if (els.deliverQualityScreening) els.deliverQualityScreening.textContent = screening;
  if (els.deliverQualityMaster) els.deliverQualityMaster.textContent = master;
  if (els.deliverQualityWarning) els.deliverQualityWarning.textContent = lowRes ? "LOW RES SOURCE · CONFORM DOES NOT RESTORE DETAIL" : "";
  if (els.deliverQualityNote) {
    els.deliverQualityNote.textContent = lowRes
      ? `SOURCE ${native} · SCREENING ${screening} · MASTER ${master} · LOW RES SOURCE：这代表 conform，不代表恢复真实细节。`
      : `SOURCE ${native} · SCREENING ${screening} · MASTER ${master} · Final Export 只使用 Final Master。`;
  }
  if (els.btnNormalizeResolution) {
    const showNormalize = lowRes && !state.hasFinalVideo && Boolean(project?.storyboard?.length);
    els.btnNormalizeResolution.classList.toggle("hidden", !showNormalize);
    els.btnNormalizeResolution.disabled = state.editing;
  }
}

const canonicalProjectState = (project) => MovieAgentModules.state.canonicalProjectState(project);

function deliverStatus(project) {
  return MovieAgentModules.deliver.deliverStatus(project, state.hasFinalVideo);
}

function subtitleModeLabel(mode) {
  return mode === "soft" ? "SOFT / 可切换" : mode === "none" ? "NONE / 无字幕" : "BURNED / 烧录";
}

const finalVideoCandidate = (project) => MovieAgentModules.deliver.finalVideoCandidate(project);

function renderDeliverSummary(project) {
  const shots = project?.storyboard || [];
  const approved = shots.filter(isShotReady).length;
  const total = deliverRuntime(project);
  const locked = Boolean(project?.script?.dialogue_locked);
  if (els.deliverProjectTitle) els.deliverProjectTitle.textContent = project ? projectTitle(project) : "等待项目进入放映室";
  if (els.deliverProjectCopy) {
    els.deliverProjectCopy.textContent = project
      ? `${project.visual_style || "未设定风格"} · ${total || project.duration_seconds || 0} 秒 · ${locked ? "台词本已锁定" : "台词本待锁定"}`
      : "完成分镜生成后，这里会显示成片状态、镜头就绪度和交付控制。";
  }
  if (els.deliverShotsReady) els.deliverShotsReady.textContent = `${approved}/${shots.length} SHOTS READY`;
  if (els.deliverReadyNote) {
    els.deliverReadyNote.textContent = !shots.length
      ? "尚未收到镜头素材。"
      : approved === shots.length
        ? (locked ? "全部通过质检 · 可启动 AI Edit" : "全部通过质检 · 请先锁定台词本")
        : `${shots.length - approved} 个镜头仍在制作或质检。`;
  }
  if (els.deliverSummarySpecs) {
    const specs = [
      ["RUNTIME", total ? compactDuration(total) : "·"],
      ["FRAME", "16:9"],
      ["DIALOGUE", locked ? "LOCKED" : "REVIEW"],
      ["SOUND", project ? `4 TRACKS · ${project.smart_ducking?.enabled === false ? "DUCKING OFF" : "DUCKING ON"}` : "·"],
      ["DELIVERY", project ? (PROJECT_STATUS[project.status] || project.status) : "STANDBY"],
    ];
    els.deliverSummarySpecs.innerHTML = specs.map(([label, value]) => `<div><span class="deliver-label mono">${label}</span><strong>${esc(value)}</strong></div>`).join("");
  }
}

function renderTechSummary(project) {
  const total = deliverRuntime(project);
  if (els.deliverMetaDuration) els.deliverMetaDuration.textContent = total ? compactDuration(total) : "·";
  if (els.deliverMetaAspect) els.deliverMetaAspect.textContent = "16:9";
  if (els.deliverMetaCodec) els.deliverMetaCodec.textContent = state.hasFinalVideo ? "H.264 / AAC" : "·";
  if (els.deliverMetaResolution) els.deliverMetaResolution.textContent = state.hasFinalVideo ? "读取中…" : "·";
  if (els.deliverMetaSubtitles) els.deliverMetaSubtitles.textContent = subtitleModeLabel(project?.subtitle_mode || project?.script?.subtitle_mode || "burned");
  if (els.deliverMetaVoiceover) els.deliverMetaVoiceover.textContent = project?.script?.dialogue_locked ? "LOCKED TRACK" : "LOCK REQUIRED";
  if (els.deliverMetaAudio) els.deliverMetaAudio.textContent = project?.script?.dialogue_locked ? "VOICE · MUSIC · SFX · ATMOS" : "LOCK REQUIRED";
}

function renderSoundSummary(project) {
  if (!els.soundSummaryStatus) return;
  const tracks = audioTracksFor(project);
  const duckingOn = project?.smart_ducking?.enabled !== false;
  const tags = AUDIO_TRACK_ORDER.map((key) => {
    const track = tracks[key];
    const ready = track.status === "READY" || track.enabled;
    const label = AUDIO_TRACK_LABELS[key].en;
    const statusText = track.status === "READY" ? "READY" : track.enabled ? "ON" : "OFF";
    const cls = ready ? "is-ready" : "is-pending";
    return `<span class="sound-summary-tag ${cls}">${label} · ${statusText} · ${track.volume_db ?? 0} dB</span>`;
  });
  tags.push(`<span class="sound-summary-tag ${duckingOn ? "is-ready" : "is-pending"}">DUCKING · ${duckingOn ? "ACTIVE" : "OFF"}</span>`);
  tags.push('<span class="sound-summary-tag is-ready">MASTER · -14 LUFS</span>');
  els.soundSummaryStatus.innerHTML = tags.join("");
}

/* ── 声音设计 / Music Brief / 四轨混音 ─────────────────────── */

const AUDIO_TRACK_ORDER = MovieAgentModules.sound.trackKeys;
const AUDIO_TRACK_LABELS = MovieAgentModules.sound.trackLabels;
const AUDIO_MODE_LABELS = MovieAgentModules.sound.audioModeLabels;

const audioTracksFor = (project) => MovieAgentModules.sound.audioTracksFor(project);
const audioModeFor = (project) => MovieAgentModules.sound.audioModeFor(project);

function renderMusicBriefMarkup(project, compact = false) {
  const brief = project?.music_brief || {};
  const arc = Array.isArray(brief.emotional_arc) ? brief.emotional_arc : [];
  const fields = [
    ["STYLE", brief.style || project?.visual_style || "CINEMATIC SCORE"],
    ["BPM", brief.bpm ? `${brief.bpm} BPM` : "·"],
    ["IN", brief.entry_seconds != null ? `${brief.entry_seconds}s` : "0s"],
    ["PEAK", brief.peak_seconds != null ? `${brief.peak_seconds}s` : "·"],
    ["FADE", brief.fade_out_seconds != null ? `${brief.fade_out_seconds}s` : "·"],
  ];
  const fieldsMarkup = fields.map(([label, value]) => `<div class="music-brief-stat"><span class="type-system-meta">${esc(label)}</span><strong class="type-control">${esc(value)}</strong></div>`).join("");
  if (compact) {
    return `<div class="deliver-music-brief-head"><span class="deliver-label type-system-meta">MUSIC BRIEF</span><strong class="type-control">${esc(brief.source || AUDIO_MODE_LABELS[audioModeFor(project)])}</strong><span class="type-system-meta">${brief.bpm ? `${brief.bpm} BPM` : "BRIEF READY"}</span></div><div class="deliver-music-brief-stats">${fieldsMarkup}</div>`;
  }
  return fieldsMarkup;
}

function renderEmotionalArc(project) {
  const arc = Array.isArray(project?.music_brief?.emotional_arc) ? project.music_brief.emotional_arc : [];
  const markup = arc.length
    ? arc.map((item) => {
      const intensity = Math.max(0.12, Math.min(1, Number(item.intensity || 0.2)));
      return `<span class="arc-segment" style="--arc-intensity:${intensity}" title="SHOT ${item.shot} · ${esc(item.emotion || "arc")}"><i></i><b class="type-system-meta">${String(item.shot).padStart(2, "0")}</b></span>`;
    }).join("")
    : '<span class="audio-empty type-helper">情绪曲线将在分镜就绪后生成。</span>';
  [els.emotionalArc, ...$$('[data-deliver-emotional-arc]')].filter(Boolean).forEach((target) => { target.innerHTML = markup; });
}

function renderAudioTrackList(project, target) {
  if (!target) return;
  const tracks = audioTracksFor(project);
  target.innerHTML = AUDIO_TRACK_ORDER.map((key) => {
    const track = tracks[key];
    const labels = AUDIO_TRACK_LABELS[key];
    const enabled = track.enabled !== false;
    const canRegenerate = track.can_regenerate !== false;
    const previewUrl = track.preview_url || "";
    const selected = state.audioInspectorTrack === key;
    return `<article class="audio-track ${enabled ? "is-enabled" : "is-muted"} ${selected ? "is-selected" : ""}" data-audio-track="${key}" data-audio-track-select="${key}" tabindex="0" aria-label="选择 ${labels.en} 音轨" aria-current="${selected ? "true" : "false"}">
      <button class="audio-track-toggle" type="button" data-audio-toggle="${key}" aria-pressed="${enabled}" aria-label="${enabled ? "关闭" : "开启"} ${labels.en} 轨道"><span class="audio-track-led"></span></button>
      <div class="audio-track-main"><div class="audio-track-title"><span class="type-system-meta">${labels.en}</span><strong class="type-control">${esc(track.name || labels.zh)}</strong></div><p class="type-helper">${esc(track.source || "SOUND DESIGN PLAN")}</p></div>
      <div class="audio-track-meter" aria-label="音量 ${esc(track.volume_db ?? 0)} dB"><i style="--meter-level:${Math.max(8, Math.min(100, 68 + Number(track.volume_db || 0) * 2))}%"></i></div>
      <div class="audio-track-status type-status">${esc(track.status || "QUEUED")}<small class="type-system-meta">${esc(String(track.volume_db ?? 0))} dB</small></div>
      <div class="audio-track-actions"><button type="button" class="audio-track-action type-control" data-audio-preview="${key}" data-audio-url="${esc(previewUrl)}">试听</button><button type="button" class="audio-track-action type-control" data-audio-regenerate="${key}" ${canRegenerate ? "" : "disabled"}>重新生成</button></div>
    </article>`;
  }).join("");
}

function audioTrackParamsPayload() {
  const tracks = state.project?.audio_tracks || {};
  return Object.fromEntries(AUDIO_TRACK_ORDER.map((key) => {
    const track = tracks[key] || {};
    return [key, {
      volume_db: Number.isFinite(Number(track.volume_db)) ? Number(track.volume_db) : 0,
      pan: Number.isFinite(Number(track.pan)) ? Number(track.pan) : 0,
      // Only Music ducks by default.  Older projects may not have the field,
      // so do not accidentally enable ducking on Voice/SFX/Ambience.
      ducking: key === "music" ? track.ducking !== false : track.ducking === true,
    }];
  }));
}

function syncAudioInspectors(project = state.project) {
  const tracks = audioTracksFor(project);
  const key = AUDIO_TRACK_ORDER.includes(state.audioInspectorTrack) ? state.audioInspectorTrack : "music";
  state.audioInspectorTrack = key;
  const track = tracks[key];
  const labels = AUDIO_TRACK_LABELS[key];
  document.querySelectorAll("[data-audio-track-select]").forEach((row) => {
    const selected = row.dataset.audioTrackSelect === key;
    row.classList.toggle("is-selected", selected);
    row.setAttribute("aria-current", String(selected));
  });
  document.querySelectorAll("[data-audio-inspector-toggle]").forEach((button) => {
    button.setAttribute("aria-expanded", String(state.audioInspectorOpen));
    button.textContent = state.audioInspectorOpen ? "CLOSE INSPECTOR" : "OPEN INSPECTOR";
  });
  document.querySelectorAll("[data-audio-inspector]").forEach((inspector) => {
    inspector.hidden = !state.audioInspectorOpen;
    inspector.dataset.track = key;
    const label = inspector.querySelector("[data-audio-inspector-label]");
    const name = inspector.querySelector("[data-audio-inspector-name]");
    const status = inspector.querySelector("[data-audio-inspector-status]");
    const copy = inspector.querySelector("[data-audio-inspector-copy]");
    if (label) label.textContent = labels.en;
    if (name) name.textContent = track.name || labels.zh;
    if (status) status.textContent = track.status || "DESIGN READY";
    if (copy) copy.textContent = `${track.source || "SOUND DESIGN PLAN"}。调节后会写回当前项目的混音方案。`;
    const gain = inspector.querySelector('[data-audio-inspector-field="volume_db"]');
    const pan = inspector.querySelector('[data-audio-inspector-field="pan"]');
    const ducking = inspector.querySelector('[data-audio-inspector-field="ducking"]');
    if (gain) gain.value = String(track.volume_db ?? 0);
    if (pan) pan.value = String(track.pan ?? 0);
    if (ducking) ducking.checked = track.ducking !== false;
    const gainOutput = inspector.querySelector('[data-audio-inspector-output="volume_db"]');
    const panOutput = inspector.querySelector('[data-audio-inspector-output="pan"]');
    if (gainOutput) gainOutput.textContent = `${Number(track.volume_db ?? 0).toFixed(1)} dB`;
    if (panOutput) panOutput.textContent = Number(track.pan ?? 0) === 0 ? "C" : (Number(track.pan) < 0 ? `L ${Math.abs(Number(track.pan)).toFixed(2)}` : `R ${Number(track.pan).toFixed(2)}`);
    if (ducking) ducking.disabled = key === "voice";
    const preview = inspector.querySelector("[data-audio-inspector-preview]");
    const regenerate = inspector.querySelector("[data-audio-inspector-regenerate]");
    if (preview) { preview.dataset.audioPreview = key; preview.dataset.audioUrl = track.preview_url || ""; }
    if (regenerate) { regenerate.dataset.audioInspectorRegenerate = key; regenerate.disabled = track.can_regenerate === false; }
  });
}

function selectAudioTrack(key) {
  if (!AUDIO_TRACK_ORDER.includes(key)) return;
  state.audioInspectorTrack = key;
  state.audioInspectorOpen = true;
  syncAudioInspectors(state.project);
}

function audioTimelineCues(project) {
  const script = project?.script || {};
  const cues = Array.isArray(script.subtitle_track) && script.subtitle_track.length
    ? script.subtitle_track
    : Array.isArray(script.dialogue_book) ? script.dialogue_book : [];
  return cues.map((cue, index) => ({
    start: Math.max(0, Number(cue?.start_seconds ?? cue?.start ?? 0)),
    end: Math.max(0, Number(cue?.end_seconds ?? cue?.end ?? 0)),
    text: cue?.text || cue?.subtitle || `SHOT ${index + 1}`,
    shot: Number(cue?.shot || index + 1),
  })).filter((cue) => cue.end > cue.start || cue.text);
}

function audioWaveformMarkup(seed = 1) {
  const bars = Array.from({ length: 48 }, (_, index) => {
    const value = 24 + ((seed * 17 + index * 29) % 62);
    return `<i style="--wave-height:${value}%"></i>`;
  }).join("");
  return `<span class="audio-waveform" aria-hidden="true">${bars}</span>`;
}

function renderAudioTimeline(project) {
  const targets = [els.audioTimeline, els.audioTimelineEditor].filter(Boolean);
  if (!targets.length) return;
  const shots = project?.storyboard || [];
  const total = Math.max(1, deliverRuntime(project));
  state.audioTimelineDuration = total;
  let offset = 0;
  const shotSegments = shots.map((shot) => {
    const duration = Math.max(1, Number(shot.duration_seconds || 1));
    const start = offset;
    offset += duration;
    return { shot, start, duration };
  });
  const segmentMarkup = shotSegments.map(({ shot, start, duration }) => `<button type="button" class="audio-shot-segment type-control" data-audio-seek="${start}" style="--clip-size:${(duration / total * 100).toFixed(3)}%" aria-label="跳转到镜头 ${shot.number} ${compactDuration(start)}"><span class="type-system-meta">${String(shot.number).padStart(2, "0")}</span></button>`).join("");
  const cueMarkup = audioTimelineCues(project).map((cue) => {
    const left = Math.min(100, Math.max(0, cue.start / total * 100));
    const width = Math.max(0.6, Math.min(100 - left, (Math.max(cue.end, cue.start + 0.2) - cue.start) / total * 100));
    return `<button type="button" class="audio-subtitle-cue" data-audio-seek="${cue.start}" data-cue-start="${cue.start}" data-cue-end="${cue.end}" style="left:${left.toFixed(3)}%;width:${width.toFixed(3)}%" title="${esc(cue.text)}"><span>${esc(truncate(cue.text, 22))}</span></button>`;
  }).join("");
  const trackMarkup = AUDIO_TRACK_ORDER.map((key, index) => {
    const label = AUDIO_TRACK_LABELS[key];
    const enabled = project?.audio_tracks?.[key]?.enabled !== false;
    const clips = shotSegments.map(({ duration }) => `<span class="audio-clip" style="--clip-size:${(duration / total * 100).toFixed(3)}%"></span>`).join("");
    const sfxMarkers = key === "sfx"
      ? shotSegments.map(({ shot, start }) => `<i class="audio-cue-marker" style="left:${Math.min(100, Math.max(0, start / total * 100)).toFixed(3)}%" title="SFX CUE · SHOT ${shot.number}"></i>`).join("")
      : "";
    const duckBands = key === "music" && project?.smart_ducking?.enabled !== false
      ? audioTimelineCues(project).map((cue) => {
        const left = Math.min(100, Math.max(0, cue.start / total * 100));
        const width = Math.max(0.8, Math.min(100 - left, (Math.max(cue.end, cue.start + 0.4) - cue.start) / total * 100));
        return `<i class="audio-ducking-band" style="left:${left.toFixed(3)}%;width:${width.toFixed(3)}%" title="SMART DUCKING · ${esc(cue.text)}"><span>DUCK</span></i>`;
      }).join("") : "";
    return `<div class="audio-timeline-track" data-audio-track-row="${key}"><span class="audio-track-name type-system-meta">${label.en}</span><div class="audio-track-lane ${enabled ? "is-enabled" : "is-muted"}">${key === "music" ? `${audioWaveformMarkup(index + 3)}${duckBands}` : `${clips}${sfxMarkers}`}</div></div>`;
  }).join("");
  const rulerMarkup = [0, 0.25, 0.5, 0.75, 1].map((ratio) => `<span>${compactDuration(total * ratio)}</span>`).join("");
  const markup = `
    <header class="audio-timeline-head"><span><span class="deliver-label type-system-meta">SOUND TIMELINE / 声音时间线</span><strong class="type-control">VOICE · MUSIC · SFX · AMBIENCE</strong></span><span class="audio-timeline-time type-system-meta" data-audio-timeline-label>00:00 / ${compactDuration(total)}</span></header>
    <div class="audio-timeline-ruler type-system-meta">${rulerMarkup}</div>
    <div class="audio-timeline-stage" data-audio-seek-track>
      <div class="audio-shot-row"><span class="audio-track-name type-system-meta">SHOTS</span><div class="audio-shot-lane">${segmentMarkup || '<span class="audio-empty type-helper">镜头时间线将在分镜就绪后出现。</span>'}</div></div>
      ${trackMarkup}
      <div class="audio-subtitle-row"><span class="audio-track-name type-system-meta">SUB</span><div class="audio-subtitle-lane">${cueMarkup || '<span class="audio-empty type-helper">锁定台词本后显示字幕 cue。</span>'}</div></div>
      <i class="audio-playhead" data-audio-playhead aria-hidden="true"><b></b></i>
    </div>
    <footer class="audio-timeline-footer"><span class="type-helper">播放头跟随预览，点击 Shot 或字幕 cue 可快速定位。</span><span class="type-system-meta">CUE / PLAYHEAD / MIX</span></footer>`;
  targets.forEach((target) => {
    target.innerHTML = markup;
    target.querySelectorAll("[data-audio-seek]").forEach((button) => {
      button.addEventListener("click", () => {
        const time = Number(button.dataset.audioSeek || 0);
        const media = state.hasFinalVideo ? els.finalVideo : els.roughCutVideo;
        if (media && media.src) {
          media.currentTime = time;
          media.play().catch(() => {});
        }
        syncAudioTimeline(time, total);
      });
    });
  });
  syncAudioTimeline(0, total);
}

function syncAudioTimeline(currentTime = 0, duration = state.audioTimelineDuration || 1) {
  const total = Math.max(1, Number(duration) || state.audioTimelineDuration || 1);
  const ratio = Math.max(0, Math.min(1, Number(currentTime || 0) / total));
  const percent = `${(ratio * 100).toFixed(3)}%`;
  [els.audioTimeline, els.audioTimelineEditor].filter(Boolean).forEach((timeline) => {
    timeline.style.setProperty("--audio-progress", percent);
    timeline.querySelectorAll("[data-audio-playhead]").forEach((playhead) => { playhead.style.left = percent; });
    timeline.querySelectorAll("[data-audio-timeline-label]").forEach((label) => { label.textContent = `${compactDuration(currentTime)} / ${compactDuration(total)}`; });
    timeline.querySelectorAll(".audio-subtitle-cue").forEach((cue) => {
      const start = Number(cue.dataset.cueStart || 0);
      const end = Number(cue.dataset.cueEnd || start);
      cue.classList.toggle("is-active", currentTime >= start && currentTime <= end);
    });
  });
}

function setAudioTimelinePlaybackState(isPlaying) {
  [els.audioTimeline, els.audioTimelineEditor].filter(Boolean).forEach((timeline) => {
    timeline.classList.toggle("is-playing", Boolean(isPlaying));
  });
}

function renderAudioDesign(project) {
  if (!project) return;
  const activeMedia = [els.finalVideo, els.roughCutVideo].find((media) => media && media.src && !media.hidden);
  const timelineTime = activeMedia?.currentTime || 0;
  const timelinePlaying = Boolean(activeMedia && !activeMedia.paused);
  const mode = audioModeFor(project);
  state.musicMode = mode;
  state.musicAssetName = project.music_asset_name || "";
  const rawIntensity = Number(project.music_intensity ?? project.music_brief?.intensity ?? 0.6);
  state.musicIntensity = Number.isFinite(rawIntensity) ? Math.max(0, Math.min(1, rawIntensity)) : 0.6;
  state.smartDucking = project.smart_ducking?.enabled !== false;
  if (els.audioDesignState) els.audioDesignState.textContent = project.music_brief?.mode_status || (mode === "ai" ? "BRIEF READY" : mode.toUpperCase());
  document.querySelectorAll(".audio-mode-switch [data-audio-mode]").forEach((button) => {
    const selected = button.dataset.audioMode === mode;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-checked", String(selected));
  });
  els.audioUploadRow?.classList.toggle("hidden", mode !== "upload");
  if (els.musicUploadNote) els.musicUploadNote.textContent = state.musicAssetName ? `已选择：${state.musicAssetName}` : "上传后将作为 MUSIC 轨来源。";
  els.deliverAudioUploadRow?.classList.toggle("hidden", mode !== "upload");
  if (els.deliverMusicUploadNote) els.deliverMusicUploadNote.textContent = state.musicAssetName ? `已选择：${state.musicAssetName}` : "上传后将作为 MUSIC 轨来源。";
  if (els.deliverMusicIntensity) els.deliverMusicIntensity.value = String(state.musicIntensity);
  if (els.deliverMusicIntensityValue) els.deliverMusicIntensityValue.textContent = `${Math.round(state.musicIntensity * 100)}%`;
  if (els.musicBriefSource) els.musicBriefSource.textContent = project.music_brief?.source || AUDIO_MODE_LABELS[mode];
  if (els.musicBriefVersion) els.musicBriefVersion.textContent = `V${project.music_brief?.version || 1}`;
  if (els.musicBriefGrid) els.musicBriefGrid.innerHTML = renderMusicBriefMarkup(project);
  if (els.musicBriefDirection) els.musicBriefDirection.textContent = project.music_brief?.direction || "AI Music 将读取导演设定、剧本情绪、视觉风格和镜头节奏。";
  if (els.musicBriefInstruments) els.musicBriefInstruments.textContent = `INSTRUMENTS / ${(project.music_brief?.instruments || ["低音合成器", "颗粒钢琴", "弓弦纹理", "低频打击"]).join(" · ")}`;
  if (els.smartDuckingToggle) els.smartDuckingToggle.checked = state.smartDucking;
  if (els.smartDuckingValue) els.smartDuckingValue.textContent = `${project.smart_ducking?.amount_db ?? -8} dB`;
  if (els.smartDuckingCopy) {
    const cueCount = project.smart_ducking?.voice_cues?.length || 0;
    els.smartDuckingCopy.textContent = `${cueCount} 个语音区间 · ${project.smart_ducking?.description || "旁白 / 对白出现时，Music 自动降低并平滑恢复。"}`;
  }
  if (els.deliverSmartDuckingToggle) els.deliverSmartDuckingToggle.checked = state.smartDucking;
  if (els.deliverSmartDuckingValue) els.deliverSmartDuckingValue.textContent = `${project.smart_ducking?.amount_db ?? -8} dB`;
  if (els.deliverSmartDuckingCopy) {
    const cueCount = project.smart_ducking?.voice_cues?.length || 0;
    els.deliverSmartDuckingCopy.textContent = cueCount
      ? `${cueCount} 个语音区间 · 对白出现时自动降低配乐，结束后平滑恢复。`
      : "锁定台词本后，系统会按语音区间自动降低配乐。";
  }
  renderEmotionalArc(project);
  renderAudioTrackList(project, els.audioTrackList);
  renderAudioTimeline(project);
  if (els.deliverAudioState) els.deliverAudioState.textContent = project.mix_state?.status || "MIX PLAN READY";
  if (els.deliverMusicBrief) els.deliverMusicBrief.innerHTML = renderMusicBriefMarkup(project, true);
  renderAudioTrackList(project, els.deliverAudioTrackList);
  syncAudioInspectors(project);
  // Re-rendering a control should not make a playing timeline jump back to 00:00.
  syncAudioTimeline(timelineTime, activeMedia?.duration || state.audioTimelineDuration || 1);
  setAudioTimelinePlaybackState(timelinePlaying);
}

async function persistAudioDesign(changes = {}) {
  if (!state.project) return;
  const trackParams = changes.track_params
    ? JSON.parse(JSON.stringify(changes.track_params))
    : audioTrackParamsPayload();
  // Intensity is the public Music control.  Keep its derived gain in sync
  // unless an Inspector update explicitly supplied a gain value.
  if (changes.music_intensity != null) {
    trackParams.music ||= {};
    if (changes.track_params?.music?.volume_db == null) {
      trackParams.music.volume_db = Number((-20 + Number(changes.music_intensity) * 10).toFixed(1));
    }
  }
  const payload = {
    music_mode: changes.music_mode || state.musicMode || "ai",
    music_intensity: changes.music_intensity ?? state.musicIntensity ?? 0.6,
    smart_ducking: changes.smart_ducking ?? state.smartDucking,
    music_asset_name: changes.music_asset_name ?? state.musicAssetName ?? "",
    track_enabled: Object.fromEntries(AUDIO_TRACK_ORDER.map((key) => [key, state.project?.audio_tracks?.[key]?.enabled !== false])),
    track_params: trackParams,
  };
  try {
    const response = await fetch(`/api/projects/${encodeURIComponent(state.project.project_id)}/audio/design`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const project = await response.json();
    if (!response.ok) throw new Error(project.error || `HTTP ${response.status}`);
    state.project = project;
    renderAudioDesign(project);
    renderWorkspace(project);
  } catch (error) {
    toast(`声音设计保存失败：${error.message}`, true);
  }
}

async function regenerateAudioTrack(trackKey) {
  if (!state.project) return;
  const button = document.querySelector(`[data-audio-regenerate="${trackKey}"]`);
  if (button) { button.disabled = true; button.textContent = "规划中…"; }
  try {
    const response = await fetch(`/api/projects/${encodeURIComponent(state.project.project_id)}/audio/tracks/${encodeURIComponent(trackKey)}/regenerate`, { method: "POST" });
    const project = await response.json();
    if (!response.ok) throw new Error(project.error || `HTTP ${response.status}`);
    state.project = project;
    renderAudioDesign(project);
    renderLogFeed(project);
    toast(`${trackKey.toUpperCase()} 音轨已重新规划。`);
  } catch (error) {
    toast(`音轨更新失败：${error.message}`, true);
    if (button) { button.disabled = false; button.textContent = "重新生成"; }
  }
}

function handleAudioInteraction(event) {
  const inspectorToggle = event.target.closest("[data-audio-inspector-toggle]");
  if (inspectorToggle) {
    state.audioInspectorOpen = !state.audioInspectorOpen;
    syncAudioInspectors(state.project);
    return;
  }
  const modeButton = event.target.closest("[data-audio-mode]");
  if (modeButton) {
    state.musicMode = modeButton.dataset.audioMode || "ai";
    renderAudioDesign({ ...(state.project || {}), music_mode: state.musicMode });
    persistAudioDesign({ music_mode: state.musicMode });
    return;
  }
  const toggle = event.target.closest("[data-audio-toggle]");
  if (toggle) {
    const key = toggle.dataset.audioToggle;
    const current = state.project?.audio_tracks?.[key]?.enabled !== false;
    if (state.project?.audio_tracks?.[key]) state.project.audio_tracks[key].enabled = !current;
    renderAudioDesign(state.project);
    persistAudioDesign();
    return;
  }
  const trackSelect = event.target.closest("[data-audio-track-select]");
  if (trackSelect && !event.target.closest("button, input, select, textarea")) {
    selectAudioTrack(trackSelect.dataset.audioTrackSelect);
    return;
  }
  const inspectorPreview = event.target.closest("[data-audio-inspector-preview]");
  if (inspectorPreview) {
    const key = inspectorPreview.closest("[data-audio-inspector]")?.dataset.track || state.audioInspectorTrack;
    const track = audioTracksFor(state.project)[key] || {};
    if (!track.preview_url) { toast("该音轨还没有可试听的真实音频媒体。先完成 AI Edit 或上传配乐。", true); return; }
    const player = state.audioPreview;
    if (player && !player.paused) player.pause();
    state.audioPreview = new Audio(track.preview_url);
    state.audioPreview.play().catch(() => toast("浏览器阻止了试听，请再次点击试听。", true));
    toast(`${key.toUpperCase()} 试听中。`);
    return;
  }
  const inspectorRegenerate = event.target.closest("[data-audio-inspector-regenerate]");
  if (inspectorRegenerate) { regenerateAudioTrack(inspectorRegenerate.dataset.audioInspectorRegenerate || state.audioInspectorTrack); return; }
  const regenerate = event.target.closest("[data-audio-regenerate]");
  if (regenerate) { regenerateAudioTrack(regenerate.dataset.audioRegenerate); return; }
  const preview = event.target.closest("[data-audio-preview]");
  if (preview) {
    const url = preview.dataset.audioUrl;
    if (!url) { toast("该音轨还没有可试听的真实音频媒体。先完成 AI Edit 或上传配乐。", true); return; }
    const player = state.audioPreview;
    if (player && !player.paused) player.pause();
    state.audioPreview = new Audio(url);
    state.audioPreview.play().catch(() => toast("浏览器阻止了试听，请再次点击试听。", true));
    toast(`${preview.dataset.audioPreview.toUpperCase()} 试听中。`);
  }
}

function handleAudioInspectorKeydown(event) {
  if ((event.key !== "Enter" && event.key !== " ") || !event.target.matches("[data-audio-track-select]")) return;
  event.preventDefault();
  selectAudioTrack(event.target.dataset.audioTrackSelect);
}

function handleAudioInspectorInput(event) {
  const field = event.target.closest("[data-audio-inspector-field]");
  if (!field || !state.project) return;
  const inspector = field.closest("[data-audio-inspector]");
  const key = inspector?.dataset.track || state.audioInspectorTrack;
  state.project.audio_tracks ||= {};
  state.project.audio_tracks[key] ||= {};
  const name = field.dataset.audioInspectorField;
  state.project.audio_tracks[key][name] = field.type === "checkbox" ? Boolean(field.checked) : Number(field.value);
  const output = inspector?.querySelector(`[data-audio-inspector-output="${name}"]`);
  if (output && name === "volume_db") output.textContent = `${Number(field.value).toFixed(1)} dB`;
  if (output && name === "pan") output.textContent = Number(field.value) === 0 ? "C" : (Number(field.value) < 0 ? `L ${Math.abs(Number(field.value)).toFixed(2)}` : `R ${Number(field.value).toFixed(2)}`);
  if (name === "volume_db") {
    document.querySelectorAll(`[data-audio-track="${key}"] .audio-track-meter i`).forEach((meter) => { meter.style.setProperty("--meter-level", `${Math.max(8, Math.min(100, 68 + Number(field.value || 0) * 2))}%`); });
    document.querySelectorAll(`[data-audio-track="${key}"] .audio-track-status small`).forEach((small) => { small.textContent = `${Number(field.value).toFixed(1)} dB`; });
  }
}

async function uploadMusicFile(file) {
  if (!state.project || !file) return;
  const notes = [els.musicUploadNote, els.deliverMusicUploadNote].filter(Boolean);
  notes.forEach((note) => { note.textContent = "正在接收用户配乐…"; });
  try {
    const response = await fetch(`/api/projects/${encodeURIComponent(state.project.project_id)}/audio/upload`, {
      method: "POST",
      headers: { "Content-Type": file.type || "application/octet-stream", "X-Filename": file.name },
      body: file,
    });
    const project = await response.json();
    if (!response.ok) throw new Error(project.error || `HTTP ${response.status}`);
    state.project = project;
    state.musicMode = "upload";
    state.musicAssetName = file.name;
    renderAudioDesign(project);
    renderLogFeed(project);
    toast("用户配乐已挂接到 MUSIC 轨道。");
  } catch (error) {
    notes.forEach((note) => { note.textContent = "上传失败，请重试。"; });
    toast(`配乐上传失败：${error.message}`, true);
  }
}

/* ── Final Look / 全片色彩润色 ──────────────────────────────── */

const FINAL_LOOK_PRESETS = {
  original: {
    label: "原片",
    english: "ORIGINAL",
    description: "保留原始曝光、色彩与镜头质感。",
    css: "original",
  },
  film_narrative: {
    label: "胶片叙事",
    english: "FILM NARRATIVE",
    description: "暖肤色、柔和反差和轻微乳剂颗粒，适合人物叙事。",
    css: "film",
  },
  cool_gray_future: {
    label: "冷灰未来",
    english: "COOL GRAY FUTURE",
    description: "压低暖色、抬高蓝灰阴影，保持克制的未来感。",
    css: "cool",
  },
  dream_surreal: {
    label: "梦境超现实",
    english: "DREAM SURREAL",
    description: "高光轻柔、色彩稍微漂浮，让现实边界变得不确定。",
    css: "dream",
  },
  documentary_desaturated: {
    label: "纪实去饱和",
    english: "DOCUMENTARY DESAT",
    description: "低饱和、高信息密度，保留现场观察感。",
    css: "documentary",
  },
  cyber_night: {
    label: "赛博夜色",
    english: "CYBER NIGHT",
    description: "深黑底色与冷蓝高光，强化夜景和电子空间。",
    css: "cyber",
  },
};

function normaliseFinalLook(value = {}) {
  const raw = value || {};
  const preset = Object.prototype.hasOwnProperty.call(FINAL_LOOK_PRESETS, raw.preset) ? raw.preset : "original";
  const number = (key, fallback) => Math.max(0, Math.min(1, Number.isFinite(Number(raw[key])) ? Number(raw[key]) : fallback));
  return {
    ...raw,
    preset,
    intensity: number("intensity", 0.72),
    grain: number("grain", 0),
    vignette: number("vignette", 0),
    highlight_soften: number("highlight_soften", 0),
    scope: "whole_film",
    applied: Boolean(raw.applied),
    revision: Math.max(1, Number(raw.revision || 1)),
  };
}

function finalLookVideoFilter(look) {
  const preset = look?.preset || "original";
  const intensity = Number(look?.intensity || 0);
  const effects = [];
  const profile = {
    film_narrative: [0.08, -0.16, 0.01, 0.12, 0],
    cool_gray_future: [0.11, -0.28, -0.015, 0, 16],
    dream_surreal: [-0.05, 0.2, 0.035, 0.04, 10],
    documentary_desaturated: [0.1, -0.52, -0.005, 0, 0],
    cyber_night: [0.18, 0.24, -0.055, 0, 180],
  }[preset];
  if (profile && intensity > 0) {
    const [contrast, saturation, brightness, sepia, hue] = profile;
    effects.push("contrast(" + (1 + contrast * intensity).toFixed(3) + ")");
    effects.push("saturate(" + Math.max(0.1, 1 + saturation * intensity).toFixed(3) + ")");
    if (sepia) effects.push("sepia(" + (sepia * intensity).toFixed(3) + ")");
    if (brightness) effects.push("brightness(" + (1 + brightness * intensity).toFixed(3) + ")");
    if (hue) effects.push("hue-rotate(" + (hue * intensity).toFixed(1) + "deg)");
  }
  if (Number(look?.highlight_soften || 0) > 0) effects.push("blur(" + (Number(look.highlight_soften) * 0.35).toFixed(2) + "px)");
  return effects.join(" ") || "none";
}

function applyFinalLookPreview(look) {
  const resolved = normaliseFinalLook(look);
  const info = FINAL_LOOK_PRESETS[resolved.preset];
  if (els.screen) {
    els.screen.dataset.finalLook = resolved.preset;
    els.screen.style.setProperty("--look-intensity", String(resolved.intensity));
    els.screen.style.setProperty("--look-grain", String(resolved.grain));
    els.screen.style.setProperty("--look-grain-alpha", String((resolved.grain * 0.16).toFixed(3)));
    els.screen.style.setProperty("--look-vignette", String(resolved.vignette));
    els.screen.style.setProperty("--look-soften", String(resolved.highlight_soften));
  }
  // Before/After comparison keeps the source cut clean and applies the
  // draft grade only to the clipped Final Look layer.
  if (els.finalVideo) els.finalVideo.style.filter = "none";
  if (els.finalVideoAfter) els.finalVideoAfter.style.filter = finalLookVideoFilter(resolved);
  if (els.finalCompareAfter) els.finalCompareAfter.style.setProperty("--grade-split", `${state.finalLookSplit}%`);
  if (els.finalCompareDivider) {
    els.finalCompareDivider.style.left = `${state.finalLookSplit}%`;
    els.finalCompareDivider.setAttribute("aria-valuenow", String(Math.round(state.finalLookSplit)));
  }
  if (els.finalLookPresetName) els.finalLookPresetName.textContent = info.english;
  if (els.finalLookDescription) els.finalLookDescription.textContent = info.description;
}

function setFinalCompareSplit(value) {
  state.finalLookSplit = Math.max(8, Math.min(92, Number(value) || 50));
  if (els.finalCompareAfter) els.finalCompareAfter.style.setProperty("--grade-split", `${state.finalLookSplit}%`);
  if (els.finalCompareDivider) {
    els.finalCompareDivider.style.left = `${state.finalLookSplit}%`;
    els.finalCompareDivider.setAttribute("aria-valuenow", String(Math.round(state.finalLookSplit)));
  }
}

function initFinalCompare() {
  const compare = els.finalCompare;
  const divider = els.finalCompareDivider;
  if (!compare || !divider) return;
  let dragging = false;
  const updateFromPointer = (event) => {
    const rect = compare.getBoundingClientRect();
    if (!rect.width) return;
    setFinalCompareSplit(((event.clientX - rect.left) / rect.width) * 100);
  };
  divider.addEventListener("pointerdown", (event) => {
    dragging = true;
    divider.setPointerCapture?.(event.pointerId);
    divider.classList.add("is-dragging");
    updateFromPointer(event);
    event.preventDefault();
  });
  divider.addEventListener("pointermove", (event) => {
    if (dragging) updateFromPointer(event);
  });
  const release = (event) => {
    if (!dragging) return;
    dragging = false;
    divider.releasePointerCapture?.(event.pointerId);
    divider.classList.remove("is-dragging");
  };
  divider.addEventListener("pointerup", release);
  divider.addEventListener("pointercancel", release);
  divider.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      setFinalCompareSplit(state.finalLookSplit + (event.key === "ArrowRight" ? 4 : -4));
    }
    if (event.key === "Home") { event.preventDefault(); setFinalCompareSplit(8); }
    if (event.key === "End") { event.preventDefault(); setFinalCompareSplit(92); }
  });
  setFinalCompareSplit(state.finalLookSplit);
}

function syncFinalCompareMedia(source = els.finalVideo) {
  const mirror = els.finalVideoAfter;
  if (!source || !mirror) return;
  try {
    if (Number.isFinite(source.currentTime) && Math.abs((mirror.currentTime || 0) - source.currentTime) > 0.12) mirror.currentTime = source.currentTime;
  } catch { /* the mirrored layer can be waiting for metadata */ }
  if (source.paused) mirror.pause();
  else mirror.play().catch(() => {});
  syncAudioTimeline(source.currentTime || 0, source.duration || state.audioTimelineDuration || 1);
}

function renderFinalLook(project) {
  if (!els.finalLookPanel || !project) return;
  const persisted = normaliseFinalLook(project.final_look || {});
  if (state.finalLookProjectId !== project.project_id) {
    state.finalLookProjectId = project.project_id;
    state.finalLookDraft = persisted;
    state.finalLookDirty = false;
  } else if (!state.finalLookDirty) {
    state.finalLookDraft = persisted;
  }
  const draft = normaliseFinalLook(state.finalLookDraft || persisted);
  const info = FINAL_LOOK_PRESETS[draft.preset];
  els.finalLookPanel.classList.toggle("is-media-missing", !state.hasFinalVideo);
  els.finalLookPresetGrid?.querySelectorAll("[data-final-look-preset]").forEach((button) => {
    const selected = button.dataset.finalLookPreset === draft.preset;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-selected", String(selected));
  });
  const ranges = [
    [els.finalLookIntensity, els.finalLookIntensityValue, draft.intensity],
    [els.finalLookGrain, els.finalLookGrainValue, draft.grain],
    [els.finalLookVignette, els.finalLookVignetteValue, draft.vignette],
    [els.finalLookSoftening, els.finalLookSofteningValue, draft.highlight_soften],
  ];
  ranges.forEach(([input, output, value]) => {
    if (input) input.value = String(value);
    if (output) output.textContent = Math.round(value * 100) + "%";
  });
  if (els.finalLookStatus) {
    els.finalLookStatus.textContent = !state.hasFinalVideo
      ? "MEDIA MISSING"
      : state.finalLookDirty
        ? "PREVIEW · NOT APPLIED"
        : draft.applied
          ? (draft.status || (info.english + " · WHOLE FILM"))
          : "READY TO FINISH";
  }
  if (els.finalLookApply) els.finalLookApply.disabled = !state.hasFinalVideo || !state.finalLookDirty;
  if (els.finalLookReset) els.finalLookReset.disabled = !state.hasFinalVideo;
  applyFinalLookPreview(draft);
}

function updateFinalLookDraft(key, value) {
  if (!state.project) return;
  state.finalLookDraft = normaliseFinalLook({ ...(state.finalLookDraft || state.project.final_look || {}), [key]: value, applied: false });
  state.finalLookDirty = true;
  renderFinalLook(state.project);
}

async function applyFinalLook() {
  if (!state.project || !state.hasFinalVideo || !state.finalLookDraft) return;
  const button = els.finalLookApply;
  if (button) { button.disabled = true; button.textContent = "应用中…"; }
  try {
    const look = normaliseFinalLook({ ...state.finalLookDraft, applied: true });
    const response = await fetch("/api/projects/" + encodeURIComponent(state.project.project_id) + "/final-look", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        preset: look.preset,
        intensity: look.intensity,
        grain: look.grain,
        vignette: look.vignette,
        highlight_soften: look.highlight_soften,
        scope: "whole_film",
        apply: true,
      }),
    });
    const project = await response.json();
    if (!response.ok) throw new Error(project.error || ("HTTP " + response.status));
    state.project = project;
    state.finalLookProjectId = project.project_id;
    state.finalLookDraft = normaliseFinalLook(project.final_look || look);
    state.finalLookDirty = false;
    renderWorkspace(project);
    toast("Final Look 已应用：" + state.finalLookDraft.english + " · WHOLE FILM。");
  } catch (error) {
    toast("Final Look 应用失败：" + error.message, true);
    renderFinalLook(state.project);
  } finally {
    if (button) button.textContent = "应用 Final Look →";
  }
}

function resetFinalLookPreview() {
  if (!state.project || !state.hasFinalVideo) return;
  state.finalLookDraft = normaliseFinalLook({ ...(state.finalLookDraft || state.project.final_look || {}), preset: "original", intensity: 0, grain: 0, vignette: 0, highlight_soften: 0, applied: false });
  state.finalLookDirty = true;
  renderFinalLook(state.project);
  toast("已预览原片状态；确认后点击应用 Final Look。");
}

function handleFinalLookInteraction(event) {
  const preset = event.target.closest("[data-final-look-preset]");
  if (preset) {
    updateFinalLookDraft("preset", preset.dataset.finalLookPreset || "original");
    toast("正在预览 " + (FINAL_LOOK_PRESETS[preset.dataset.finalLookPreset]?.english || "ORIGINAL") + " · 未应用。");
  }
}

function deliverProgressIndex(description = "") {
  const text = String(description || "");
  if (/voice|旁白/i.test(text)) return 1;
  if (/music|配乐|音乐|brief|情绪曲线/i.test(text)) return 2;
  if (/sfx|音效|ambience|环境声/i.test(text)) return 3;
  if (/subtitle|字幕/i.test(text)) return 4;
  if (/mix|混音|ducking/i.test(text)) return 5;
  if (/编码|FFmpeg|encode|final encode/i.test(text)) return 6;
  return 0;
}

function renderDeliverProgress(project, description = "") {
  const status = String(project?.status || "");
  const editing = status === "editing_rough_cut";
  const roughReady = status === "rough_cut_ready";
  const editReady = status === "ready_for_ai_edit";
  if (els.deliverWorkProgress) els.deliverWorkProgress.classList.toggle("hidden", !editing && !roughReady && !editReady);
  if (els.deliverProgressTitle) els.deliverProgressTitle.textContent = roughReady ? "粗剪已完成，等待审片" : editReady ? "AI Edit 已就绪 · 先规划声音" : "粗剪正在组装";
  if (description) state.editProgressStep = deliverProgressIndex(description);
  const activeIndex = roughReady ? 7 : Math.max(0, Math.min(6, state.editProgressStep));
  const stageCount = 7;
  $$("[data-deliver-progress]").forEach((node, index) => {
    const done = roughReady || index < activeIndex;
    const working = editing && index === activeIndex;
    node.dataset.state = done ? "done" : working ? "working" : "queued";
    const stateNode = node.querySelector(".deliver-progress-state");
    if (stateNode) stateNode.textContent = done ? "DONE" : working ? "WORKING" : "QUEUED";
  });
  const percent = roughReady ? 100 : Math.round((activeIndex / stageCount) * 100);
  if (els.deliverProgressPercent) els.deliverProgressPercent.textContent = `${percent}%`;
  if (els.deliverProgressBar) els.deliverProgressBar.style.width = `${percent}%`;
  const preApproval = editing || roughReady || editReady;
  if (els.editConsoleNote) {
    els.editConsoleNote.textContent = project?.script?.dialogue_locked
      ? "AI Edit 会严格读取已锁定的台词本与字幕轨。"
      : "请先在“剧本与旁白”页锁定台词本，剪辑才能继续。";
  }
  if (els.btnApproveEdit) {
    els.btnApproveEdit.classList.toggle("hidden", !roughReady);
    els.btnApproveEdit.disabled = state.editing || !roughReady;
  }
  if (els.btnRecut) els.btnRecut.classList.toggle("hidden", !preApproval);
  if (els.subtitleModeControl) els.subtitleModeControl.classList.toggle("hidden", !preApproval);
}

function updateFinalVideoMetadata() {
  const video = els.finalVideo;
  if (!video || !state.hasFinalVideo) return;
  renderMediaQuality(state.project, "screening");
  if (els.deliverMetaDuration && Number.isFinite(video.duration)) els.deliverMetaDuration.textContent = compactDuration(video.duration);
  if (els.deliverMetaResolution && video.videoWidth && video.videoHeight) {
    els.deliverMetaResolution.textContent = `${video.videoWidth} × ${video.videoHeight}`;
    const ratio = video.videoWidth / video.videoHeight;
    if (els.deliverMetaAspect) els.deliverMetaAspect.textContent = Math.abs(ratio - 1) < 0.04 ? "1:1" : ratio < 0.8 ? "9:16" : "16:9";
  }
}

function renderDeliverTimeline(project) {
  const shots = project?.storyboard || [];
  if (!els.deliverShotTimeline) return;
  let offset = 0;
  const total = deliverRuntime(project);
  els.deliverTimelineTotal.textContent = total ? `${compactDuration(total)} · ${shots.length} SHOTS` : "·";
  els.deliverShotTimeline.innerHTML = shots.length
    ? shots.map((shot) => {
      const duration = Math.max(1, Number(shot.duration_seconds || 1));
      const start = offset;
      offset += duration;
      const stateInfo = shotWorkflowState(shot.status);
      return `<button class="deliver-timeline-shot type-control ${stateInfo.key}" type="button" role="listitem" data-deliver-start="${start}" data-deliver-duration="${duration}" data-deliver-shot="${shot.number}" style="--shot-duration:${duration};" aria-label="跳转到镜头 ${shot.number}"><span class="type-system-meta">SHOT ${String(shot.number).padStart(2, "0")}</span><small class="type-system-meta">${compactDuration(start)} · ${compactDuration(start + duration)}</small><i class="type-status">${duration}s</i><span class="deliver-shot-preview" aria-hidden="true"><i class="deliver-shot-preview-frame"></i><b class="type-system-meta">SHOT ${String(shot.number).padStart(2, "0")} · ${compactDuration(start)}</b></span></button>`;
    }).join("")
    : '<p class="empty-note">镜头生成后，这里会出现可跳转的时间线。</p>';
  els.deliverShotTimeline.querySelectorAll("[data-deliver-start]").forEach((button) => {
    button.addEventListener("click", () => {
      const start = Number(button.dataset.deliverStart || 0);
      if (!state.hasFinalVideo || !els.finalVideo) return;
      els.finalVideo.currentTime = start;
      els.finalVideo.play().catch(() => {});
      els.deliverShotTimeline.querySelectorAll(".is-selected").forEach((item) => item.classList.remove("is-selected"));
      button.classList.add("is-selected");
      syncShotTimelinePlayhead(start);
    });
    button.addEventListener("mouseenter", () => ensureDeliverShotPreview(project, button));
    button.addEventListener("focus", () => ensureDeliverShotPreview(project, button));
    button.addEventListener("mouseleave", pauseDeliverShotPreview);
    button.addEventListener("blur", pauseDeliverShotPreview);
  });
}

/* 悬停镜头时惰性探测单镜媒体，命中才挂载缩略预览视频。 */
function ensureDeliverShotPreview(project, button) {
  const frame = button.querySelector(".deliver-shot-preview-frame");
  if (!frame || !project || frame.querySelector("video")) return;
  const shotNumber = Number(button.dataset.deliverShot || 0);
  if (!shotNumber) return;
  const key = `${project.project_id}:${shotNumber}`;
  if (state.deliverShotPreviewMedia[key] === null) return;
  const url = `/api/projects/${encodeURIComponent(project.project_id)}/shots/${shotNumber}/video`;
  const mediaMap = state.deliverShotPreviewMedia;
  fetch(url, { method: "HEAD" }).then((response) => {
    if (!response.ok) {
      mediaMap[key] = null;
      return;
    }
    mediaMap[key] = url;
    if (!frame.isConnected || frame.querySelector("video")) return;
    const video = document.createElement("video");
    video.src = url;
    video.muted = true;
    video.loop = true;
    video.playsInline = true;
    video.preload = "metadata";
    frame.appendChild(video);
    if (button.matches(":hover")) video.play().catch(() => {});
  }).catch(() => {});
}

function pauseDeliverShotPreview(event) {
  event.currentTarget.querySelectorAll(".deliver-shot-preview-frame video").forEach((video) => {
    video.pause();
    video.currentTime = 0;
  });
}

/* 播放头同步：高亮当前镜头并保持其在横向时间线内可见。 */
function syncShotTimelinePlayhead(currentTime) {
  const box = els.deliverShotTimeline;
  if (!box) return;
  const shots = Array.from(box.querySelectorAll("[data-deliver-start]"));
  if (!shots.length) return;
  const time = Number(currentTime) || 0;
  let active = null;
  for (const node of shots) {
    const start = Number(node.dataset.deliverStart || 0);
    const end = start + Number(node.dataset.deliverDuration || 1);
    const isCurrent = time >= start && time < end;
    node.classList.toggle("is-current", isCurrent);
    if (isCurrent) active = node;
  }
  if (!active && time > 0) {
    const last = shots[shots.length - 1];
    if (time >= Number(last.dataset.deliverStart || 0)) {
      last.classList.add("is-current");
      active = last;
    }
  }
  if (!active) return;
  const target = active.offsetLeft;
  const viewStart = box.scrollLeft;
  const viewEnd = viewStart + box.clientWidth;
  if (target < viewStart + 12 || target + active.offsetWidth > viewEnd - 12) {
    box.scrollTo({
      left: Math.max(0, target - box.clientWidth / 2 + active.offsetWidth / 2),
      behavior: REDUCED_MOTION ? "auto" : "smooth",
    });
  }
}

async function renderScreening(project) {
  const probeRun = ++state.finalVideoProbeRun;
  state.hasFinalVideo = false;
  state.finalVideoUrl = null;
  // Reset the mutually exclusive Deliver surfaces before probing media. This
  // prevents a previous project's player from flashing while a new HEAD check
  // is in flight.
  els.deliverSummary?.classList.remove("hidden");
  els.screen?.classList.add("hidden");
  els.roughCutStage?.classList.add("hidden");
  els.finalVideo?.removeAttribute("src");
  els.finalVideo?.load();
  els.finalVideoAfter?.removeAttribute("src");
  els.finalVideoAfter?.load();
  els.roughCutVideo?.removeAttribute("src");
  els.roughCutVideo?.load();
  els.roughCutStage?.classList.remove("has-media");
  const status = String(project?.status || "");
  const stateInfo = deliverStatus(project);
  if (els.deliverStateTitle) els.deliverStateTitle.textContent = stateInfo.title;
  if (els.deliverStateCopy) els.deliverStateCopy.textContent = stateInfo.copy;
  if (els.deliverStateBadge) {
    els.deliverStateBadge.textContent = stateInfo.badge;
    els.deliverStateBadge.dataset.state = stateInfo.key;
  }
  renderDeliverSummary(project);
  renderMediaQuality(project, status === "editing_rough_cut" || status === "rough_cut_ready" ? "proxy" : "screening");
  renderAudioDesign(project);
  renderDeliverTimeline(project);
  if (els.deliverWorkProgress) els.deliverWorkProgress.classList.toggle("hidden", !["editing", "rough", "ready"].includes(stateInfo.key));
  renderDeliverProgress(project);
  if (els.subtitleMode) els.subtitleMode.value = project?.subtitle_mode || project?.script?.subtitle_mode || "burned";
  const editingOrRough = ["editing_rough_cut", "rough_cut_ready"].includes(status);
  if (editingOrRough) {
    try {
      const response = await fetch(`/api/projects/${encodeURIComponent(project.project_id)}/rough-cut`, { method: "HEAD" });
      if (response.ok && els.roughCutVideo && probeRun === state.finalVideoProbeRun) {
        els.roughCutVideo.src = `/api/projects/${encodeURIComponent(project.project_id)}/rough-cut`;
        els.roughCutStage?.classList.add("has-media");
        renderMediaQuality(project, "proxy");
      }
    } catch { /* mock mode may only expose rough-cut metadata */ }
  }
  const finalStatus = status.startsWith("completed");
  if (finalStatus) {
    const candidate = finalVideoCandidate(project);
    try {
      const response = await fetch(candidate, { method: "HEAD" });
      if (response.ok && probeRun === state.finalVideoProbeRun) {
        state.hasFinalVideo = true;
        state.finalVideoUrl = candidate;
        if (els.finalVideo) els.finalVideo.src = candidate;
        if (els.finalVideoAfter) {
          els.finalVideoAfter.src = candidate;
          els.finalVideoAfter.load();
        }
        renderMediaQuality(project, "screening");
      }
    } catch { /* final media is optional in mock mode */ }
  }
  const resolvedState = deliverStatus(project);
  if (els.deliverStateTitle) els.deliverStateTitle.textContent = resolvedState.title;
  if (els.deliverStateCopy) els.deliverStateCopy.textContent = resolvedState.copy;
  if (els.deliverStateBadge) {
    els.deliverStateBadge.textContent = resolvedState.badge;
    els.deliverStateBadge.dataset.state = resolvedState.key;
  }
  const showFinal = finalStatus && state.hasFinalVideo;
  const roughPhase = ["editing", "rough"].includes(resolvedState.key);
  const progressPhase = ["editing", "rough", "ready"].includes(resolvedState.key);
  const showSummary = !state.hasFinalVideo && !roughPhase;
  if (els.deliverSummary) els.deliverSummary.classList.toggle("hidden", !showSummary);
  els.screen?.classList.toggle("hidden", !showFinal);
  els.roughCutStage?.classList.toggle("hidden", !roughPhase);
  els.deliverFinal?.classList.toggle("hidden", !project);
  if (els.audioDesignConsole) els.audioDesignConsole.classList.toggle("hidden", !progressPhase);
  if (els.deliverAudioPanel) els.deliverAudioPanel.classList.toggle("hidden", !showFinal);
  if (els.subtitleModeControl) els.subtitleModeControl.classList.toggle("hidden", !progressPhase);
  if (els.deliverFinal) els.deliverFinal.classList.toggle("hidden", !showFinal);
  if (els.finalNotGenerated) els.finalNotGenerated.classList.add("hidden");
  if (els.screen) els.screen.classList.toggle("has-video", state.hasFinalVideo);
  if (els.finalPlayerState) els.finalPlayerState.textContent = state.hasFinalVideo ? "READY TO SCREEN" : "MEDIA MISSING";
  renderTechSummary(project);
  renderSoundSummary(project);
  if (els.btnAiEdit) {
    const canStartAiEdit = showSummary && !["rough", "editing"].includes(resolvedState.key);
    els.btnAiEdit.classList.toggle("hidden", !canStartAiEdit);
    els.btnAiEdit.disabled = state.editing || !((project?.storyboard || []).length && (project.storyboard || []).every(isShotReady));
    els.btnAiEdit.innerHTML = state.editing ? "AI Edit 粗剪中…" : 'AI 剪辑成片 <span class="cta-arrow" aria-hidden="true">→</span>';
  }
  if (els.btnApproveEdit) {
    const showApprove = status === "rough_cut_ready" && !state.editing;
    els.btnApproveEdit.classList.toggle("hidden", !showApprove);
    els.btnApproveEdit.disabled = state.editing;
    if (!state.editing) els.btnApproveEdit.innerHTML = '批准最终成片 <span class="cta-arrow" aria-hidden="true">→</span>';
  }
  if (els.btnExportFinal) els.btnExportFinal.classList.toggle("hidden", !showFinal);
  if (els.btnReedit) els.btnReedit.classList.toggle("hidden", !state.hasFinalVideo);
  if (els.btnEditSubtitles) els.btnEditSubtitles.classList.toggle("hidden", !project);
  if (els.editStatus && !state.editing) {
    if (resolvedState.key === "missing") els.editStatus.textContent = "FINAL CUT NOT GENERATED · 先启动 AI 剪辑成片，完成后再回到这里审片。";
    else if (showFinal) els.editStatus.textContent = "FINAL CUT READY · 可审片、调整声音与 Final Look，然后导出。";
  }
  renderFinalLook(project);
  if (els.crewFlow) syncCrewBoard(project, { silent: true });
  updatePipelineForProject(project);
}

function renderDelivery(project) {
  const credits = [
    ["PROJECT", projectTitle(project)],
    ["DIRECTED BY", "DIRECTOR AGENT"],
    ["WRITTEN BY", "WRITER AGENT"],
    ["ART DIRECTION", "VISUAL BIBLE AGENT"],
    ["STORYBOARD", "STORYBOARD AGENT"],
    ["SOUND DESIGN", "VOICE · MUSIC · SFX · AMBIENCE"],
    ["POST PRODUCTION", "GENERATION · QC · EDITOR · MIX"],
    ["DELIVERY", PROJECT_STATUS[project.status] || project.status],
  ];
  els.creditsRoll.innerHTML = credits
    .map(([heading, value]) => `<div class="cr-group"><p class="cr-head">${esc(heading)}</p><p class="cr-strong">${esc(value)}</p></div>`)
    .join("");
  els.exportJson.href = `/api/projects/${project.project_id}/export/json`;
  els.exportMd.href = `/api/projects/${project.project_id}/export/markdown`;
  if (els.exportSrt) els.exportSrt.href = `/api/projects/${project.project_id}/subtitles.srt`;
  if (els.exportVtt) els.exportVtt.href = `/api/projects/${project.project_id}/subtitles.vtt`;
  // 字幕滚动只在新项目首次进入时触发，避免逐镜渲染/实时送达时反复重播。
  if (state.creditsProjectId !== project.project_id) {
    state.creditsProjectId = project.project_id;
    els.creditsRoll.classList.remove("is-rolling");
    void els.creditsRoll.offsetWidth;
    els.creditsRoll.classList.add("is-rolling");
  }
}

async function refreshExportPreflight() {
  if (!state.project || !els.exportPreflight) return;
  const run = ++state.exportPreflightRun;
  const params = new URLSearchParams({
    resolution: state.exportOptions.resolution,
    aspect: state.exportOptions.aspect,
    subtitle_mode: state.exportOptions.subtitle_mode,
  });
  els.exportPreflight.dataset.state = "checking";
  els.exportPreflight.textContent = "PREFLIGHT · CHECKING DELIVERY CONTRACT…";
  try {
    const response = await fetch(`/api/projects/${encodeURIComponent(state.project.project_id)}/delivery-preflight?${params.toString()}`);
    const payload = await response.json().catch(() => ({}));
    if (run !== state.exportPreflightRun) return;
    const blocked = !response.ok || payload.ready === false;
    els.exportPreflight.dataset.state = blocked ? "blocked" : "ready";
    els.exportPreflight.textContent = blocked
      ? `PREFLIGHT · BLOCKED · ${payload.blocking_reasons?.[0] || payload.error || "请先完成交付检查"}`
      : `PREFLIGHT · PASS · ${payload.output?.width || 1920}×${payload.output?.height || 1080} MASTER READY`;
  } catch {
    if (run !== state.exportPreflightRun) return;
    els.exportPreflight.dataset.state = "unknown";
    els.exportPreflight.textContent = "PREFLIGHT · UNAVAILABLE · 导出时仍会再次检查";
  }
}

function updateExportSelection() {
  const options = state.exportOptions;
  const subtitle = options.subtitle_mode === "soft" ? "SOFT" : options.subtitle_mode === "none" ? "NONE" : "BURNED";
  if (els.exportSelection) {
    els.exportSelection.textContent = `${options.container.toUpperCase()} · ${options.container === "webm" ? "VP9" : "H.264"} · ${options.resolution.toUpperCase()} · ${options.aspect} · ${subtitle}`;
  }
  $$("[data-export-field]").forEach((button) => {
    const selected = state.exportOptions[button.dataset.exportField] === button.dataset.exportValue;
    button.classList.toggle("is-selected", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
}

function openExportSheet() {
  if (!state.project || !state.hasFinalVideo) {
    toast("当前没有可导出的 FINAL CUT。", true);
    return;
  }
  show(els.exportSheet);
  els.exportSheet?.classList.add("is-open");
  updateExportSelection();
  refreshExportPreflight();
  els.btnExportRun?.focus();
}

function closeExportSheet() {
  els.exportSheet?.classList.remove("is-open");
  hide(els.exportSheet);
}

async function exportFinalCut() {
  if (!state.project || !state.hasFinalVideo || !els.btnExportRun) return;
  const button = els.btnExportRun;
  const original = button.innerHTML;
  button.disabled = true;
  button.textContent = "编码导出中…";
  try {
    const response = await fetch(`/api/projects/${encodeURIComponent(state.project.project_id)}/export/video`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.exportOptions),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.error || `HTTP ${response.status}`);
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${state.project.project_id}-final-${state.exportOptions.resolution}.${state.exportOptions.container}`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
    closeExportSheet();
    toast(`已导出 ${state.exportOptions.container.toUpperCase()} · ${state.exportOptions.resolution} · ${state.exportOptions.aspect}。`);
  } catch (error) {
    toast(`导出失败：${error.message}`, true);
  } finally {
    button.disabled = false;
    button.innerHTML = original;
  }
}

async function normalizeProjectResolution() {
  if (!state.project || !els.btnNormalizeResolution) return;
  const button = els.btnNormalizeResolution;
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "NORMALIZING…";
  try {
    const response = await fetch(`/api/projects/${encodeURIComponent(state.project.project_id)}/media/normalize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resolution: "1080p", method: "resolution_normalize" }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    state.project = payload;
    renderScreening(payload);
    toast("已完成 1080P / 24fps Resolution Normalize，可继续进入 AI Edit。", false);
  } catch (error) {
    toast(`Resolution Normalize 失败：${error.message}`, true);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

function openSubtitleEditor() {
  if (!state.project) return;
  state.manualTab = "script";
  renderManual(state.project, "script");
  els.manualBody?.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth", block: "center" });
  setTimeout(() => els.manualBody?.querySelector("[data-dialogue-field='text']:not(:disabled)")?.focus(), REDUCED_MOTION ? 0 : 350);
}

function updatePipelineForProject(project) {
  setPipeline(pipelineFromProject(project, state.hasFinalVideo));
}

function renderWorkspace(project, options = {}) {
  show(els.actWorkspace);
  renderProjectDiagnostics(project);
  renderFilmstrip(project, options.entranceFrom);
  renderTimeline(project);
  renderShotMap(project);
  renderMonitor(project, state.rendering);
  renderLogFeed(project);
  renderManual(project, options.tab || state.manualTab, Boolean(options.animateManual));
  renderScreening(project);
  renderDelivery(project);
  updatePipelineForProject(project);
  const videoMode = state.health ? state.health.video_mode : "mock";
  const shots = project.storyboard || [];
  const allShotsReady = shots.length > 0 && shots.every(isShotReady);
  if (videoMode === "comfyui") {
    els.btnRender.disabled = state.rendering || allShotsReady;
    els.renderNote.textContent = allShotsReady
      ? "镜头已全部通过质检，请先锁定台词本，再启动 AI Edit Rough Cut。"
      : state.project?.script?.dialogue_locked
        ? "逐镜提交已验证的 MiniMax-H3 工作流；已通过质检的镜头会自动跳过，失败镜头按重试策略重新提交。"
        : "请先在剧本与旁白页审阅并锁定台词本，再提交 Spark 真实生成。";
  } else {
    els.btnRender.disabled = true;
    els.renderNote.textContent = allShotsReady
      ? "mock 镜头已全部就绪：锁定台词本后可直接启动 AI Edit Rough Cut。"
      : "当前为 mock 视频流程：在 Spark 的 .env 设置 VIDEO_GENERATION_MODE=comfyui 后，这里会变成真实逐镜生成与 FFmpeg 合片。";
  }
}

function applyProjectSnapshot(project) {
  state.project = project;
  renderProjectDiagnostics(project);
  if (els.crewFlow) syncCrewBoard(project, { silent: true });
  renderFilmstrip(project);
  renderTimeline(project);
  renderShotMap(project);
  renderLogFeed(project);
  renderManual(project, state.manualTab);
  renderDelivery(project);
  renderMonitor(project, state.rendering);
  renderScreening(project);
}

/* ── Inspector：镜头 / 剧组详情 ───────────────────────────── */

function clearCrewCardSelection() {
  document.querySelectorAll('.crew-card[data-inspector-open="true"]').forEach((card) => {
    card.dataset.inspectorOpen = "false";
  });
}

function syncInspectorSelection() {
  const active = String(state.activeShotNumber ?? "");
  document.querySelectorAll(".shot-card[data-shot], .timeline-segment[data-shot]").forEach((element) => {
    const isShot = String(element.dataset.shot) === active;
    element.classList.toggle("is-inspected", state.drawerType === "shot" && isShot);
    element.classList.toggle("is-current", element.classList.contains("shot-card") && isShot);
  });
}

function drawerIsOpen() {
  return els.drawer.classList.contains("open");
}

function openDrawerShell() {
  clearTimeout(drawerHideTimer);
  els.drawerBackdrop.classList.remove("hidden");
  els.drawer.classList.add("open");
  requestAnimationFrame(() => els.drawerBackdrop.classList.add("open"));
}

function setInspectorExpanded(expanded) {
  state.inspectorExpanded = Boolean(expanded);
  els.drawer.classList.toggle("is-expanded", state.inspectorExpanded);
  const button = els.drawer.querySelector("[data-inspector-expand]");
  if (!button) return;
  const targetName = state.drawerType === "shot" ? "Shot Workspace" : "Agent Inspector";
  button.setAttribute("aria-expanded", String(state.inspectorExpanded));
  button.setAttribute("aria-label", state.inspectorExpanded ? `收起 ${targetName}` : `展开 ${targetName}`);
  const label = button.querySelector(".inspector-expand-label");
  if (label) label.textContent = state.inspectorExpanded ? "COLLAPSE" : "EXPAND";
}

function renderDrawerContent(markup, { swap = false, onReady } = {}) {
  const run = ++drawerContentRun;
  const current = els.drawer.querySelector(".inspector-content");
  const commit = () => {
    if (run !== drawerContentRun) return;
    els.drawer.innerHTML = markup;
    setInspectorExpanded(state.inspectorExpanded);
    const content = els.drawer.querySelector(".inspector-content");
    if (!content) {
      if (onReady) onReady();
      return;
    }
    requestAnimationFrame(() => {
      content.classList.add("is-ready");
      if (onReady) onReady();
    });
  };
  if (swap && current) {
    current.classList.add("is-swapping");
    window.setTimeout(commit, 120);
  } else {
    commit();
  }
}

function inspectorShotPreviewMarkup(shot) {
  const previewReady = ["approved_comfyui", "generated_comfyui", "awaiting_visual_review"].includes(shot.status) && shot.stale !== true;
  return `
    <section class="inspector-preview-section">
      <header class="inspector-section-head type-system-meta"><span>SHOT PREVIEW / 16:9</span><span class="inspector-preview-state type-system-meta ${previewReady ? "is-ready" : ""}">${previewReady ? "MEDIA READY" : "UNEXPOSED FRAME"}</span></header>
      <div class="inspector-preview" data-inspector-preview="${esc(shot.number)}">
        <div class="inspector-preview-empty"><span class="preview-code type-system-meta">${previewReady ? "LOADING MEDIA" : "UNEXPOSED FRAME"}</span><strong class="type-control">${esc(shot.framing || "待定景别")}</strong><span class="type-helper">${previewReady ? "正在读取镜头媒体…" : "生成后首帧将在这里显影"}</span></div>
        <div class="inspector-viewfinder" aria-hidden="true"><i class="vf tl"></i><i class="vf tr"></i><i class="vf bl"></i><i class="vf br"></i><i class="vf-safe"></i><i class="vf-cross"></i></div>
        <span class="inspector-preview-stamp type-system-meta">${String(shot.number).padStart(2, "0")} · 24 FPS · ${esc(shot.generation_mode || "T2V")}</span>
      </div>
      <p class="inspector-preview-note type-helper">${previewReady ? "视频预览可播放 · 关键帧质检已归档" : "当前显示未冲洗胶片帧 · 完成真实生成后自动替换"}</p>
    </section>`;
}

const PROMPT_SEMANTICS = [
  { key: "character", label: "CHARACTER", tests: /角色|人物|主角|演员|character|subject|figure/i },
  { key: "environment", label: "ENVIRONMENT", tests: /环境|空间|场景|荒原|城市|房间|观测站|environment|location|interior|exterior/i },
  { key: "lighting", label: "LIGHTING", tests: /光|照明|灯|曝光|阴影|高光|lighting|light|shadow|highlight|exposure/i },
  { key: "camera", label: "CAMERA", tests: /镜头|摄影|机位|焦段|景别|推|拉|环绕|camera|lens|dolly|orbit|shot/i },
  { key: "mood", label: "MOOD", tests: /情绪|氛围|质感|风格|梦|紧张|孤独|mood|tone|atmosphere|texture/i },
];

function structuredPromptMarkup(prompt) {
  const text = String(prompt || "").trim();
  if (!text) return '<p class="prompt-empty type-helper">FINAL PROMPT / 等待提示词生成。</p>';
  const chunks = text.split(/(?<=[。！？.!?；;])\s*|\n+/).map((item) => item.trim()).filter(Boolean);
  const parts = chunks.length ? chunks : [text];
  const assigned = parts.map((part, index) => {
    const match = PROMPT_SEMANTICS.find((item) => item.tests.test(part));
    return { key: match?.key || PROMPT_SEMANTICS[index % PROMPT_SEMANTICS.length].key, text: part };
  });
  const chips = PROMPT_SEMANTICS.map((item) => `<button type="button" class="prompt-token" data-prompt-key="${item.key}" aria-pressed="false">${item.label}</button>`).join("");
  const phrases = assigned.map((part) => `<span class="prompt-phrase" data-prompt-key="${part.key}">${esc(part.text)}</span>`).join(" ");
  return `<div class="prompt-structure" role="toolbar" aria-label="提示词语义区段">${chips}</div><div class="prompt-segments" tabindex="0" aria-label="结构化最终提示词">${phrases}</div>`;
}

function buildShotInspectorMarkup(project, shot) {
  const shots = project.storyboard || [];
  const index = Math.max(0, shots.findIndex((item) => item.number === shot.number));
  const previous = shots[(index - 1 + shots.length) % shots.length];
  const next = shots[(index + 1) % shots.length];
  const status = shotWorkflowState(shot.status);
  const scene = String(shotSceneNumber(shot.number, shots.length)).padStart(2, "0");
  const output = shot.output_placeholder || "生成后写入项目 outputs/";
  return `
    <div class="inspector-content inspector-content--shot" data-inspector-type="shot" data-shot-number="${esc(shot.number)}">
      <header class="inspector-head">
        <div class="inspector-head-main">
          <p class="inspector-kicker type-system-meta">SHOT INSPECTOR / SCENE ${scene}</p>
          <div class="inspector-title-row"><h2>镜头 ${String(shot.number).padStart(2, "0")}</h2><span class="inspector-status ${status.key} type-status"><i>${status.symbol}</i>${status.label}</span></div>
          <p class="inspector-subtitle type-helper">${esc(truncate(shot.image_description || "镜头尚未补充画面描述。", 180))}</p>
        </div>
        <div class="inspector-head-actions">
          <button class="inspector-expand type-control" data-inspector-expand type="button" aria-expanded="${String(state.inspectorExpanded)}" aria-label="${state.inspectorExpanded ? "收起 Shot Workspace" : "展开 Shot Workspace"}"><span aria-hidden="true">⤢</span><span class="inspector-expand-label">${state.inspectorExpanded ? "COLLAPSE" : "EXPAND"}</span></button>
          <button class="drawer-close" type="button" aria-label="关闭 Inspector">×</button>
        </div>
      </header>

      <nav class="inspector-shot-nav" aria-label="镜头导航">
        <button class="inspector-nav-btn type-control" type="button" data-shot-nav="-1" aria-label="上一镜头"><span aria-hidden="true">←</span><span>上一镜头</span><b class="type-system-meta">SHOT ${String(previous?.number || shot.number).padStart(2, "0")}</b></button>
        <span class="inspector-nav-count type-system-meta">${String(index + 1).padStart(2, "0")} / ${String(shots.length).padStart(2, "0")}</span>
        <button class="inspector-nav-btn inspector-nav-btn--next type-control" type="button" data-shot-nav="1" aria-label="下一镜头"><b class="type-system-meta">SHOT ${String(next?.number || shot.number).padStart(2, "0")}</b><span>下一镜头</span><span aria-hidden="true">→</span></button>
      </nav>

      ${inspectorShotPreviewMarkup(shot)}

      <dl class="inspector-facts">
        <div><dt class="type-system-meta">DURATION</dt><dd class="type-control">${esc(shot.duration_seconds)}<small class="type-system-meta">s</small></dd></div>
        <div><dt class="type-system-meta">FRAMING</dt><dd class="type-control">${esc(shot.framing || "·")}</dd></div>
        <div><dt class="type-system-meta">GENERATION</dt><dd class="type-system-meta">${esc(shot.generation_mode || "T2V")}</dd></div>
        <div><dt class="type-system-meta">TAKES</dt><dd class="type-system-meta">${esc(shot.attempts || 0)}<small class="type-system-meta">×</small></dd></div>
      </dl>

      <section class="inspector-timing-editor" aria-label="Editorial timing controls">
        <header class="inspector-section-head type-system-meta"><span>EDITORIAL TIMING / 剪辑时长</span><span class="type-helper">NATIVE ${esc(shot.source_duration_seconds || shot.duration_seconds)}s</span></header>
        <div class="inspector-timing-grid">
          <label><span class="inspector-label type-ui-label">DESIRED DURATION / 目标时长</span><input type="number" min="1" max="80" step="1" value="${esc(shot.duration_seconds)}" data-shot-field="desired_duration" /></label>
          <label><span class="inspector-label type-ui-label">EDIT OPERATION / 操作</span><select data-shot-field="timing_mode"><option value="native"${shot.timing_mode === "native" ? " selected" : ""}>Native / 原始</option><option value="trim"${shot.timing_mode === "trim" ? " selected" : ""}>Trim / 裁切</option><option value="extend"${shot.timing_mode === "extend" ? " selected" : ""}>Extend / 延长</option><option value="hold_last_frame"${shot.timing_mode === "hold_last_frame" ? " selected" : ""}>Hold Last Frame / 定格</option><option value="slow_motion"${shot.timing_mode === "slow_motion" ? " selected" : ""}>Slow Motion / 慢放</option></select></label>
        </div>
        <p class="type-helper">先改目标时长，再保存；原始生成长度保持不变，字幕与配乐会自动重新对齐。</p>
      </section>

      <section class="inspector-copy-section">
        <div class="inspector-copy-block inspector-copy-block--wide"><span class="inspector-label type-ui-label">IMAGE / 画面</span><p class="type-helper">${esc(shot.image_description || "·")}</p></div>
        <div class="inspector-copy-block"><span class="inspector-label type-ui-label">ACTION / 动作</span><p class="type-helper">${esc(shot.action || "·")}</p></div>
        <div class="inspector-copy-block"><span class="inspector-label type-ui-label">SOUND / 声音</span><p class="type-helper">${esc(shot.sound_design || "·")}</p></div>
      </section>

      <section class="inspector-prompt-block">
        <header class="inspector-section-head type-system-meta"><span>FINAL PROMPT / 最终提示词</span><button class="inspector-copy-btn type-control" data-copy-prompt type="button">复制</button></header>
        ${structuredPromptMarkup(shot.prompt)}
        <p class="inspector-prompt-note type-helper">展开 Shot Workspace 后可编辑提示词与镜头字段。</p>
      </section>

      <section class="inspector-workspace-tools" aria-label="Shot Workspace 编辑区">
        <header class="inspector-workspace-head"><div><span class="inspector-label type-ui-label">SHOT WORKSPACE / FULL REVIEW</span><h3>镜头编辑与生成控制</h3></div><span class="type-system-meta">DRAFT MODE</span></header>
        <div class="inspector-editor-grid">
          <label><span class="inspector-label type-ui-label">IMAGE / 画面</span><textarea data-shot-field="image_description" rows="4">${esc(shot.image_description || "")}</textarea></label>
          <label><span class="inspector-label type-ui-label">ACTION / 动作</span><textarea data-shot-field="action" rows="4">${esc(shot.action || "")}</textarea></label>
          <label><span class="inspector-label type-ui-label">SOUND / 声音</span><textarea data-shot-field="sound_design" rows="4">${esc(shot.sound_design || "")}</textarea></label>
          <label class="inspector-editor-prompt"><span class="inspector-label type-ui-label">FINAL PROMPT / 最终提示词</span><textarea data-shot-field="prompt" rows="7">${esc(shot.prompt || "")}</textarea></label>
        </div>
        <div class="inspector-editor-actions"><button class="ghost type-control" data-save-shot type="button">保存镜头编辑</button><span class="type-helper">保存后写入项目档案，可继续质检或生成。</span></div>
      </section>

      <div class="inspector-output"><span class="inspector-label type-ui-label">OUTPUT PATH</span><span class="type-system-meta">${esc(output)}</span></div>

       <footer class="inspector-actions">
         ${shot.status === "awaiting_visual_review" ? '<button class="cta inspector-action-primary" data-inspector-action="approve" type="button">APPROVE SHOT <span aria-hidden="true">✓</span></button>' : ""}
         <button class="ghost type-control" data-inspector-action="replan" type="button">↻ 重新规划</button>
        <button class="cta inspector-action-primary" data-inspector-action="regenerate" type="button">重新生成素材 <span aria-hidden="true">→</span></button>
      </footer>
    </div>`;
}

function bindShotInspector(project, shot, { initial = false } = {}) {
  const closeButton = els.drawer.querySelector(".drawer-close");
  closeButton?.addEventListener("click", closeDrawer);
  els.drawer.querySelector("[data-inspector-expand]")?.addEventListener("click", () => {
    setInspectorExpanded(!state.inspectorExpanded);
  });
  els.drawer.querySelectorAll("[data-shot-nav]").forEach((button) => {
    button.addEventListener("click", () => navigateShot(Number(button.dataset.shotNav)));
  });
  els.drawer.querySelector("[data-copy-prompt]")?.addEventListener("click", async (event) => {
    try {
      await navigator.clipboard.writeText(shot.prompt || "");
      event.currentTarget.textContent = "已复制";
      setTimeout(() => { event.currentTarget.textContent = "复制"; }, 1600);
    } catch {
      toast("复制失败，请手动选择文本。", true);
    }
  });
  const setPromptFocus = (key, active) => {
    els.drawer.querySelectorAll("[data-prompt-key]").forEach((item) => {
      item.classList.toggle("is-prompt-focus", active && item.dataset.promptKey === key);
    });
  };
  els.drawer.querySelectorAll(".prompt-token").forEach((token) => {
    const key = token.dataset.promptKey;
    token.addEventListener("mouseenter", () => setPromptFocus(key, true));
    token.addEventListener("mouseleave", () => setPromptFocus(key, false));
    token.addEventListener("focus", () => setPromptFocus(key, true));
    token.addEventListener("blur", () => setPromptFocus(key, false));
    token.addEventListener("click", () => {
      const active = token.classList.toggle("is-prompt-focus");
      setPromptFocus(key, active);
      token.setAttribute("aria-pressed", String(active));
    });
  });
  els.drawer.querySelector('[data-inspector-action="replan"]')?.addEventListener("click", () => regenerateShot(shot.number, "replan"));
  els.drawer.querySelector('[data-inspector-action="regenerate"]')?.addEventListener("click", () => renderSingleShot(shot.number));
  els.drawer.querySelector('[data-inspector-action="approve"]')?.addEventListener("click", () => approveShot(shot.number));
  els.drawer.querySelector("[data-save-shot]")?.addEventListener("click", () => saveShotEdits(shot.number));
  attachInspectorPreview(project, shot);
  if (initial) closeButton?.focus({ preventScroll: true });
}

function attachInspectorPreview(project, shot) {
  if (!["approved_comfyui", "generated_comfyui", "awaiting_visual_review"].includes(shot.status) || shot.stale === true) return;
  const preview = els.drawer.querySelector(`[data-inspector-preview="${shot.number}"]`);
  if (!preview) return;
  const url = `/api/projects/${project.project_id}/shots/${shot.number}/video`;
  fetch(url, { method: "HEAD" }).then((response) => {
    if (!response.ok || !els.drawer.contains(preview)) return;
    const video = document.createElement("video");
    video.src = url;
    video.controls = true;
    video.playsInline = true;
    video.preload = "metadata";
    video.setAttribute("aria-label", `镜头 ${shot.number} 视频预览`);
    preview.querySelector(".inspector-preview-empty")?.remove();
    preview.appendChild(video);
    preview.classList.add("has-media");
  }).catch(() => {});
}

function openDrawer(project, shotNumber) {
  const shot = (project.storyboard || []).find((s) => s.number === shotNumber);
  if (!shot) return;
  const wasOpen = drawerIsOpen();
  state.drawerType = "shot";
  state.activeAgentId = null;
  state.activeShotNumber = shotNumber;
  els.drawer.setAttribute("aria-label", `镜头 ${shotNumber} Inspector`);
  clearCrewCardSelection();
  syncInspectorSelection();
  renderDrawerContent(buildShotInspectorMarkup(project, shot), {
    swap: wasOpen,
    onReady: () => bindShotInspector(project, shot, { initial: !wasOpen }),
  });
  if (!wasOpen) openDrawerShell();
}

function closeDrawer() {
  drawerContentRun += 1;
  els.drawer.classList.remove("open", "is-expanded");
  els.drawerBackdrop.classList.remove("open");
  clearCrewCardSelection();
  state.drawerType = null;
  state.activeAgentId = null;
  state.inspectorExpanded = false;
  syncInspectorSelection();
  clearTimeout(drawerHideTimer);
  drawerHideTimer = setTimeout(() => els.drawerBackdrop.classList.add("hidden"), 300);
}

function crewValueMarkup(value, depth = 0) {
  if (depth > 3) return `<span>${esc(String(value ?? ""))}</span>`;
  if (typeof value === "string") {
    const candidate = value.trim();
    if ((candidate.startsWith("{") && candidate.endsWith("}")) || (candidate.startsWith("[") && candidate.endsWith("]"))) {
      try {
        const parsed = JSON.parse(candidate);
        if (parsed && typeof parsed === "object") return crewValueMarkup(parsed, depth + 1);
      } catch {
        // Keep ordinary Agent prose as readable copy instead of forcing JSON.
      }
    }
    const lines = candidate.split(/\n+/).filter(Boolean);
    if (lines.length > 1) return `<div class="crew-readable-copy">${lines.map((line) => `<p>${esc(line.trim())}</p>`).join("")}</div>`;
  }
  if (Array.isArray(value)) {
    return `<ol class="crew-drawer-list">${value.map((item) => `<li>${crewValueMarkup(item, depth + 1)}</li>`).join("")}</ol>`;
  }
  if (value && typeof value === "object") {
    return `<dl class="crew-readable-dl">${Object.entries(value).map(([key, item]) => `<div><dt>${esc(String(key).replace(/[_-]+/g, " ").toUpperCase())}</dt><dd>${crewValueMarkup(item, depth + 1)}</dd></div>`).join("")}</dl>`;
  }
  return `<span>${esc(value)}</span>`;
}

function crewAssetMarkup(title, value) {
  if (!value || (typeof value === "object" && !Object.keys(value).length)) return "";
  const body = value && typeof value === "object" ? crewValueMarkup(value) : `<p>${esc(value)}</p>`;
  return `<section class="crew-drawer-section"><h3>${esc(title)}</h3>${body}</section>`;
}

function buildCrewInspectorMarkup(agentId) {
  const def = AGENT_DEFS.find((item) => item.id === agentId);
  if (!def) return "";
  const card = document.querySelector(`.crew-card[data-agent="${agentId}"]`);
  const details = state.crewDetails[agentId] || {};
  const project = state.project || {};
  const asset = {
    brief: details.brief || (agentId === "director" ? project.brief : null),
    script: details.script || (agentId === "writer" ? project.script : null),
    visual_bible: details.visual_bible || (agentId === "visual_bible" ? project.visual_bible : null),
    storyboard: details.storyboard || (agentId === "storyboard" ? project.storyboard : null),
    quality_report: details.quality_report || (agentId === "quality" ? project.quality_report : null),
  };
  const artifactMarkup = state.crewArtifacts
    .filter((item) => item.agent === agentId)
    .map((item) => crewAssetMarkup(item.title, item.content))
    .join("");
  const messages = state.crewMessages
    .filter((item) => item.from === agentId || item.to === agentId || item.to === "all")
    .map((item) => `<p class="crew-drawer-message"><span class="radio-time type-system-meta">${esc(item.time || "--:--:--")}</span><span class="radio-from type-system-meta">${esc(item.from)}</span><span class="radio-to type-system-meta"> → ${esc(item.to)}</span><br><span class="type-helper">${esc(item.message)}</span></p>`)
    .join("");
  const assetMarkup = agentId === "director" ? crewAssetMarkup("项目设定", asset.brief)
    : agentId === "writer" ? crewAssetMarkup("剧本与旁白", asset.script)
    : agentId === "visual_bible" ? crewAssetMarkup("视觉规范", asset.visual_bible)
    : agentId === "storyboard" ? crewAssetMarkup("分镜资产", asset.storyboard)
      : agentId === "quality" ? crewAssetMarkup("质检报告", asset.quality_report)
      : agentId === "generation" ? crewAssetMarkup("逐镜任务", project.storyboard)
      : agentId === "editor" ? crewAssetMarkup("剪辑结果", project.final_output_placeholder || project.rough_cut_placeholder || (String(project.status || "") === "ready_for_ai_edit" ? "AI EDIT READY / 等待启动粗剪" : String(project.status || "").startsWith("completed") ? "DELIVERY RECORDED / MEDIA CHECK" : "EDIT QUEUED / 等待镜头通过质检"))
            : `<section class="crew-drawer-section"><h3>任务说明</h3><p class="type-helper">${esc(def.role)}。${esc(card?.querySelector(".crew-summary")?.getAttribute("aria-label") || "等待上游素材。")}</p></section>`;
  return `
    <div class="inspector-content inspector-content--agent" data-inspector-type="agent" data-agent-id="${esc(agentId)}">
      <header class="inspector-head">
        <div class="inspector-head-main">
          <p class="inspector-kicker type-system-meta">AGENT INSPECTOR / ${esc(def.en)}</p>
          <div class="inspector-title-row"><h2>${esc(def.name)} Agent</h2><span class="inspector-status ${card?.classList.contains("working") || card?.classList.contains("ready") || card?.classList.contains("next") ? "active" : card?.classList.contains("failed") ? "failed" : "complete"} type-status"><i>●</i>${esc(card?.querySelector(".crew-state-text")?.textContent || "候场")}</span></div>
          <p class="inspector-subtitle type-helper">${esc(def.role)} · 点击卡片即可查看实时产出、沟通和决策记录。</p>
        </div>
        <div class="inspector-head-actions">
          <button class="inspector-expand type-control" data-inspector-expand type="button" aria-expanded="${String(state.inspectorExpanded)}" aria-label="${state.inspectorExpanded ? "收起 Agent Inspector" : "展开 Agent Inspector"}"><span aria-hidden="true">⤢</span><span class="inspector-expand-label">${state.inspectorExpanded ? "COLLAPSE" : "EXPAND"}</span></button>
          <button class="drawer-close" type="button" aria-label="关闭 Inspector">×</button>
        </div>
      </header>
      <div class="inspector-agent-meta"><div><span class="inspector-label type-ui-label">ROLE</span><strong class="type-control">${esc(def.en)}</strong></div><div><span class="inspector-label type-ui-label">CHANNEL</span><strong class="type-system-meta">${esc(agentId.toUpperCase())}</strong></div><div><span class="inspector-label type-ui-label">ARTIFACTS</span><strong class="type-system-meta">${state.crewArtifacts.filter((item) => item.agent === agentId).length}</strong></div><div><span class="inspector-label type-ui-label">SIGNALS</span><strong class="type-system-meta">${state.crewMessages.filter((item) => item.from === agentId || item.to === agentId || item.to === "all").length}</strong></div></div>
      <div class="inspector-agent-content">
        ${assetMarkup || '<p class="empty-note type-helper">该成员还没有交付内容，正在等待上游信号。</p>'}
        ${artifactMarkup}
        ${messages ? `<section class="crew-drawer-section"><h3>现场沟通</h3>${messages}</section>` : ""}
      </div>
    </div>`;
}

function openCrewDrawer(agentId) {
  const def = AGENT_DEFS.find((item) => item.id === agentId);
  if (!def) return;
  const wasOpen = drawerIsOpen();
  state.drawerType = "agent";
  state.activeAgentId = agentId;
  state.activeShotNumber = null;
  state.inspectorExpanded = false;
  els.drawer.setAttribute("aria-label", `${def.name} Agent Inspector`);
  clearCrewCardSelection();
  syncInspectorSelection();
  const card = document.querySelector(`.crew-card[data-agent="${agentId}"]`);
  if (card) card.dataset.inspectorOpen = "true";
  renderDrawerContent(buildCrewInspectorMarkup(agentId), {
    swap: wasOpen,
    onReady: () => {
      els.drawer.querySelector(".drawer-close")?.addEventListener("click", closeDrawer);
      els.drawer.querySelector("[data-inspector-expand]")?.addEventListener("click", () => setInspectorExpanded(!state.inspectorExpanded));
    },
  });
  if (!wasOpen) openDrawerShell();
}

/* ── 动作：创作 / 渲染 / 重新规划 ──────────────────────────── */

let storyboardStageRun = 0;

function refreshWorkspaceAfterShotUpdate(project) {
  state.project = project;
  renderWorkspace(project);
}

function collectDialogueAssets() {
  const script = state.project?.script || {};
  const dialogue = Array.isArray(script.dialogue_book) ? script.dialogue_book : [];
  const subtitles = Array.isArray(script.subtitle_track) ? script.subtitle_track : dialogue;
  const rows = Array.from(els.manualBody.querySelectorAll("[data-dialogue-row]"));
  const dialogueBook = dialogue.map((entry, index) => {
    const row = rows.find((item) => Number(item.dataset.dialogueRow) === index);
    const text = row?.querySelector('[data-dialogue-field="text"]')?.value.trim();
    const speaker = row?.querySelector('[data-dialogue-field="speaker"]')?.value.trim();
    return { ...entry, text: text || entry.text || "", speaker: speaker || entry.speaker || "旁白" };
  });
  const subtitleTrack = dialogueBook.map((entry, index) => {
    const row = rows.find((item) => Number(item.dataset.dialogueRow) === index);
    const cue = subtitles[index] || entry;
    const field = row?.querySelector('[data-dialogue-field="subtitle"]');
    const text = field ? field.value.trim() : String(cue.text || entry.text || "");
    return { ...cue, shot: entry.shot, start_seconds: entry.start_seconds, end_seconds: entry.end_seconds, text };
  });
  return { dialogueBook, subtitleTrack };
}

async function unlockDialogue() {
  if (!state.project) return;
  try {
    const response = await fetch(`/api/projects/${state.project.project_id}/script/unlock`, { method: "POST" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    state.project = payload;
    renderWorkspace(payload, { tab: "script" });
    toast("台词本已解锁：修改后请重新保存并锁定。 ");
  } catch (error) {
    toast(`解锁台词本失败：${error.message}`, true);
  }
}

async function saveDialogueDraft({ lock = false, button = null } = {}) {
  if (!state.project) return;
  const assets = collectDialogueAssets();
  if (!assets.dialogueBook.length || assets.dialogueBook.some((entry) => !String(entry.text || "").trim())) {
    toast("每个镜头至少需要一条台词或旁白；无对白时可填写留白。", true);
    return;
  }
  const originalText = button?.textContent || "";
  if (button) {
    button.disabled = true;
    button.textContent = lock ? "锁定中…" : "保存中…";
  }
  try {
    let response = await fetch(`/api/projects/${state.project.project_id}/script`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(assets),
    });
    let payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    if (lock) {
      response = await fetch(`/api/projects/${state.project.project_id}/script/lock`, { method: "POST" });
      payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    }
    state.project = payload;
    renderWorkspace(payload, { tab: "script" });
    toast(lock ? "台词本已锁定，后续配音、字幕与 AI Edit 将以此版本为准。" : "台词本与字幕轨草稿已保存。");
  } catch (error) {
    toast(`${lock ? "锁定" : "保存"}台词本失败：${error.message}`, true);
    if (button) {
      button.disabled = false;
      button.textContent = originalText || (lock ? "锁定台词本 →" : "保存台词修改");
    }
  }
}

async function saveShotEdits(shotNumber) {
  if (!state.project) return;
  const fields = {};
  els.drawer.querySelectorAll("[data-shot-field]").forEach((field) => {
    fields[field.dataset.shotField] = field.value.trim();
  });
  if (!fields.prompt) {
    toast("最终提示词不能为空。", true);
    return;
  }
  const button = els.drawer.querySelector("[data-save-shot]");
  if (button) {
    button.disabled = true;
    button.textContent = "保存中…";
  }
  try {
    const response = await fetch(
      `/api/projects/${state.project.project_id}/shots/${shotNumber}`,
      { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields) }
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    refreshWorkspaceAfterShotUpdate(payload);
    openDrawer(payload, shotNumber);
    toast(`镜头 ${shotNumber} 的 Inspector 编辑已保存。`);
  } catch (error) {
    toast(`保存镜头失败：${error.message}`, true);
    if (button) {
      button.disabled = false;
      button.textContent = "保存镜头编辑";
    }
  }
}

async function renderSingleShot(shotNumber) {
  if (!state.project || state.rendering) return;
  const button = els.drawer.querySelector('[data-inspector-action="regenerate"]');
  if (button) {
    button.disabled = true;
    button.innerHTML = "提交生成中…";
  }
  try {
    const response = await fetch(
      `/api/projects/${state.project.project_id}/shots/${shotNumber}/render`,
      { method: "POST" }
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    refreshWorkspaceAfterShotUpdate(payload);
    openDrawer(payload, shotNumber);
    toast(`镜头 ${shotNumber} 已生成并进入质检。`);
  } catch (error) {
    toast(`镜头生成失败：${error.message}`, true);
    if (button) {
      button.disabled = false;
      button.innerHTML = "重新生成素材 <span aria-hidden=\"true\">→</span>";
    }
  }
}

async function cleanWorkingCache() {
  if (!state.project || !els.btnCleanWorkingCache) return;
  const button = els.btnCleanWorkingCache;
  const original = button.textContent;
  button.disabled = true;
  button.textContent = "CLEANING…";
  try {
    const response = await fetch(`/api/projects/${encodeURIComponent(state.project.project_id)}/storage/clean`, { method: "POST" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    toast(`已清理 ${payload.removed_files || 0} 个工作缓存文件，保留 Source 与当前 Final Master。`, false);
    if (els.deliverQualityNote && payload.total_bytes != null) {
      els.deliverQualityNote.textContent += ` PROJECT STORAGE · ${Math.round(Number(payload.total_bytes) / 1024 / 1024)} MB`;
    }
  } catch (error) {
    toast(`缓存清理失败：${error.message}`, true);
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

async function approveShot(shotNumber) {
  if (!state.project) return;
  const button = els.drawer.querySelector('[data-inspector-action="approve"]');
  if (button) {
    button.disabled = true;
    button.textContent = "审批中…";
  }
  try {
    const response = await fetch(
      `/api/projects/${state.project.project_id}/shots/${shotNumber}/approve`,
      { method: "POST" },
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    refreshWorkspaceAfterShotUpdate(payload);
    openDrawer(payload, shotNumber);
    toast(`镜头 ${shotNumber} 已完成人工视觉批准。`);
  } catch (error) {
    toast(`镜头批准失败：${error.message}`, true);
    if (button) {
      button.disabled = false;
      button.textContent = "APPROVE SHOT ✓";
    }
  }
}

function createLiveProject(event) {
  return {
    project_id: event.project_id,
    idea: els.idea.value.trim(),
    duration_seconds: Number(els.duration.value),
    visual_style: state.selectedStyle,
    status: "planning_live",
    brief: {},
    script: {},
    visual_bible: {},
    storyboard: [],
    quality_report: [],
    logs: ["片场开机：正在等待第一份创作资产。"],
    final_output_placeholder: null,
    rough_cut_placeholder: null,
    subtitle_mode: "burned",
    edit_plan: {},
    music_mode: "ai",
    music_intensity: 0.6,
    music_asset_name: "",
    music_brief: {},
    audio_tracks: {},
    smart_ducking: { enabled: true },
    mix_state: {},
    final_look: {},
  };
}

function stageStoryboard(shots) {
  const run = ++storyboardStageRun;
  state.project.storyboard = [];
  renderWorkspace(state.project, { tab: "visual" });
  shots.forEach((shot, index) => {
    setTimeout(() => {
      if (run !== storyboardStageRun || !state.project) return;
      state.project.storyboard.push(shot);
      renderFilmstrip(state.project, index);
      renderTimeline(state.project);
      renderShotMap(state.project);
      renderManualSummary(state.project);
      renderAgentActivity(state.project);
      syncCrewBoard(state.project, { silent: true });
      if (state.manualTab === "quality") renderManual(state.project, "quality");
    }, index * 125);
  });
}

function revealAsset(agent, event) {
  if (!state.project) return;
  const mapping = {
    director: ["brief", "brief"],
    writer: ["script", "script"],
    visual_bible: ["visual_bible", "visual"],
    quality: ["quality_report", "quality"],
  };
  const item = mapping[agent];
  if (!item || !(item[0] in event)) return;
  state.project[item[0]] = event[item[0]];
  // 集结期间就让第三幕工作区可见，页面随时可以往下翻看实时填充的面板。
  renderWorkspace(state.project, { tab: item[1], animateManual: true });
}

function handleCreateEvent(event) {
  if (event.type === "project") {
    state.project = createLiveProject(event);
    state.pendingProjectId = event.project_id;
    pushCrewRadio({ type: "status", agent: "system", status: "BOOT", message: "Project slate received · crew assembly online" });
    els.crewMeta.textContent = `LIVE · PROJECT ${String(event.project_id || "").replace(/^film-/, "").toUpperCase()}`;
    els.modeNote.textContent = `文案引擎：${event.text_mode === "modelscope" ? "ModelScope AI" : "mock"} · 视频引擎：${event.video_mode === "comfyui" ? "Spark 真实生成" : "mock 流程"}`;
  } else if (event.type === "agent_start") {
    state.workingAgent = event.agent;
    rememberCrewEvent(event.agent, { status: "working", startedAt: Date.now() });
    appendCrewStatus(event.agent, "START", `${crewAgentLabel(event.agent)} · pass started`);
    syncCrewBoard(state.project, { silent: true });
  } else if (event.type === "agent_done") {
    state.workingAgent = null;
    rememberCrewEvent(event.agent, { status: "done", ...event });
    revealAsset(event.agent, event);
    appendCrewStatus(event.agent, "DONE", `${crewAgentLabel(event.agent)} · deliverable locked`);
    syncCrewBoard(state.project, { silent: true });
    if (event.agent === "storyboard") {
      stageStoryboard(event.storyboard || []);
      appendCrewStatus("storyboard", "HANDOFF", "Shot list released to QC Gate");
      syncCrewBoard(state.project, { silent: true });
    } else if (event.agent === "quality") {
      appendCrewStatus("quality", "PASS", "QC Gate cleared · render queue can open");
      syncCrewBoard(state.project, { silent: true });
    }
  } else if (event.type === "artifact") {
    appendCrewArtifact(event);
  } else if (event.type === "chat") {
    appendCrewMessage(event);
  } else if (event.type === "project_saved") {
    appendCrewStatus("system", "SAVED", "Project snapshot persisted · production state remains active");
  } else if (event.type === "shot_update") {
    if (event.shot && state.project) {
      const shots = Array.isArray(state.project.storyboard) ? state.project.storyboard : (state.project.storyboard = []);
      const index = shots.findIndex((shot) => Number(shot.number) === Number(event.shot.number));
      if (index >= 0) shots[index] = { ...shots[index], ...event.shot };
      else shots.push(event.shot);
      rememberCrewEvent("generation", { lastShot: event.shot, status: "working" });
      syncCrewBoard(state.project, { silent: true });
      const card = document.querySelector('.crew-card[data-agent="generation"]');
      const summary = card?.querySelector(".crew-summary");
      if (summary) {
        renderCrewSummary(summary, {
          headline: "ACTIVE",
          primary: `SHOT ${String(event.shot.number).padStart(2, "0")}`,
          secondary: shotStatusInfo(event.shot.status),
        });
      }
      appendCrewStatus("generation", "SHOT UPDATE", `SHOT ${String(event.shot.number).padStart(2, "0")} · ${shotStatusInfo(event.shot.status)}`);
    }
  } else if (event.type === "done") {
    storyboardStageRun += 1;
    state.project = event.project;
    if (event.job_status && state.project?.job) state.project.job.status = event.job_status;
    state.job = state.project?.job || null;
    state.pendingProjectId = null;
    els.crewMeta.textContent = `LOCKED · PROJECT ${String(event.project?.project_id || "").replace(/^film-/, "").toUpperCase()}`;
    syncCrewBoard(state.project, { silent: true });
    appendCrewStatus("system", "SAVED", `Project snapshot saved · ${PROJECT_STATUS[state.project.status] || state.project.status}`);
    renderWorkspace(state.project, { entranceFrom: 0 });
    setBrowserActivity("idle", state.project);
    toast(state.project.status === "ready_for_ai_edit"
      ? `${state.project.storyboard?.length || 0}/${state.project.storyboard?.length || 0} SHOTS READY：当前阶段已推进到 DELIVER，请锁定台词本后启动 AI Edit。`
      : `项目 ${state.project.project_id} 已完成并保存。`);
    setTimeout(() => els.actWorkspace.scrollIntoView({ behavior: "smooth", block: "start" }), 350);
  } else if (event.type === "error") {
    const failure = eventErrorMessage(event);
    if (event.project) {
      state.project = event.project;
      if (event.job_status && state.project.job) state.project.job.status = event.job_status;
      renderProjectDiagnostics(event.project);
      syncCrewBoard(event.project, { silent: true });
      renderLogFeed(event.project);
    }
    els.crewMeta.textContent = "INTERRUPTED · RETRY AVAILABLE";
    failWorkingAgent();
    appendCrewStatus("system", "FAILED", `Crew run interrupted · ${failure}`);
    setIdeaError("创作暂时中断，请检查创意后重试。", `制作未完成：${failure}`);
  }
}

async function startCreation() {
  if (state.busy) return;
  const idea = els.idea.value.trim();
  if (!validateIdea({ focus: true })) return;
  setIdeaError();
  state.busy = true;
  state.assemblyLocked = true;
  state.project = null;
  stopJobPolling();
  state.job = null;
  state.jobCursor = 0;
  state.pendingProjectId = null;
  state.viewingHistorical = false;
  state.crewDetails = {};
  state.crewMessages = [];
  state.crewArtifacts = [];
  state.crewRadioLog = [];
  state.crewRadioOpen = false;
  state.hasFinalVideo = false;
  state.editing = false;
  state.editProgressStep = 0;
  state.musicMode = "ai";
  state.musicIntensity = 0.6;
  state.musicAssetName = "";
  state.smartDucking = true;
  state.workingAgent = null;
  els.btnStart.disabled = true;
  els.btnStart.textContent = "拍摄中…";
  buildCrewBoard();
  show(els.actCrew);
  hide(els.actWorkspace);
  setPipeline({ plan: "active" });
  els.crewMeta.textContent = "STARTING · WAITING FOR CREW";
  playUiSound("slate");
  els.actCrew.scrollIntoView({ behavior: "smooth", block: "start" });
  const paced = createPacedHandler(handleCreateEvent);
  try {
    await streamPost(
      "/api/projects/stream",
      { idea, duration: Number(els.duration.value), visual_style: state.selectedStyle },
      paced
    );
  } catch (error) {
    setIdeaError("创作暂时中断，请检查创意后重试。", `制作未完成：${error.message}`);
    els.crewMeta.textContent = "INTERRUPTED · RETRY AVAILABLE";
    failWorkingAgent();
    if (state.project?.project_id) refreshJobStatus(state.project.project_id, { poll: true });
  } finally {
    state.busy = false;
    els.btnStart.disabled = false;
    els.btnStart.innerHTML = '开机 <span class="cta-arrow" aria-hidden="true">→</span>';
  }
}

function closePremiere(autoplay = false) {
  clearTimeout(premiereTimer);
  hide(els.premiere);
  if (!autoplay) return;
  els.screen.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth", block: "center" });
  setTimeout(() => els.finalVideo.play().catch(() => {}), 350);
}

function openPremiere(project) {
  if (!state.hasFinalVideo) return;
  els.premiereTitle.textContent = projectTitle(project);
  els.premiereMeta.textContent = `${project.visual_style} · ${project.duration_seconds} SECONDS · ${project.project_id}`;
  show(els.premiere);
  playUiSound("premiere");
  premiereTimer = setTimeout(() => closePremiere(true), 4200);
}

function handleRenderEvent(event) {
  if (event.type === "render_progress") {
    els.renderRec.classList.add("live");
    if (event.project) applyProjectSnapshot(event.project);
    // 直接用后端下发的逐镜进度，而不是用「已通过质检」的镜头数折算。
    const total = event.total || 0;
    const completed = event.completed || 0;
    if (total) {
      els.monitorShot.textContent = `SHOT ${completed}/${total}`;
      els.monitorPct.textContent = `${Math.round((completed / total) * 100)}%`;
      els.monitorBar.style.width = `${(completed / total) * 100}%`;
    }
    els.monitorDesc.textContent = event.description || "生成中…";
    if (event.description) appendCrewStatus("generation", "SHOT UPDATE", event.description);
  } else if (event.type === "done") {
    state.project = event.project;
    if (event.job_status && state.project?.job) state.project.job.status = event.job_status;
    state.job = state.project?.job || null;
    state.rendering = false;
    rememberCrewEvent("generation", { status: "done" });
    appendCrewStatus("generation", "DONE", `${event.project.storyboard?.length || 0}/${event.project.storyboard?.length || 0} shots ready`);
    appendCrewStatus("editor", "READY", "AI Edit queue opened · start Rough Cut when ready");
    syncCrewBoard(event.project, { silent: true });
    applyProjectSnapshot(event.project);
    els.renderRec.classList.remove("live");
    renderMonitor(event.project, false);
    stopProjectorHum();
    setBrowserActivity("idle", event.project);
    renderManual(event.project);
    // All approved shots now enter DELIVER/AI Edit; do not leave the old
    // full-render CTA looking actionable after the queue is complete.
    els.btnRender.disabled = true;
    els.btnRender.textContent = "提交 Spark 真实生成";
    toast(`${event.project.storyboard?.length || 0}/${event.project.storyboard?.length || 0} SHOTS READY，当前阶段已推进到 DELIVER；请启动 AI Edit 粗剪。`);
  } else if (event.type === "error") {
    const failure = eventErrorMessage(event);
    if (event.project) {
      state.project = event.project;
      if (event.job_status && state.project.job) state.project.job.status = event.job_status;
      applyProjectSnapshot(event.project);
    }
    els.renderRec.classList.remove("live");
    stopProjectorHum();
    setBrowserActivity("idle", state.project);
    state.rendering = false;
    els.btnRender.disabled = false;
    els.btnRender.textContent = "提交 Spark 真实生成";
    els.monitorDesc.textContent = `生成中断：${failure}`;
    rememberCrewEvent("generation", { status: "failed" });
    appendCrewStatus("generation", "FAILED", failure);
    syncCrewBoard(state.project, { silent: true });
    toast(`渲染失败：${failure}`, true);
    if (state.project) updatePipelineForProject(state.project);
  }
}

async function startRender() {
  if (!state.project || state.rendering) return;
  state.rendering = true;
  state.renderStartedAt = performance.now();
  els.btnRender.disabled = true;
  els.btnRender.textContent = "生成中…（可断点续跑）";
  els.monitorDesc.textContent = "正在连接 Spark ComfyUI…";
  renderMonitor(state.project, true);
  setBrowserActivity("render", state.project);
  startProjectorHum();
  setPipeline({ plan: "done", previs: "done", render: "active" });
  try {
    await streamPost(
      `/api/projects/${state.project.project_id}/render/stream`,
      {},
      handleRenderEvent
    );
  } catch (error) {
    els.renderRec.classList.remove("live");
    stopProjectorHum();
    setBrowserActivity("idle", state.project);
    state.rendering = false;
    els.btnRender.disabled = false;
    els.btnRender.textContent = "提交 Spark 真实生成";
    els.monitorDesc.textContent = `生成中断：${error.message}`;
    toast(`渲染失败：${error.message}`, true);
    if (state.project?.project_id) refreshJobStatus(state.project.project_id, { poll: true });
  }
}

function handleEditEvent(event) {
  if (event.type === "edit_progress") {
    rememberCrewEvent("editor", { status: "working" });
    if (event.project) applyProjectSnapshot(event.project);
    if (els.editStatus) els.editStatus.textContent = event.description || "AI Edit 处理中…";
    if (els.monitorDesc) els.monitorDesc.textContent = event.description || "AI Edit 处理中…";
    if (event.project) renderDeliverProgress(event.project, event.description || "");
    if (state.project) renderLogFeed(state.project);
    appendCrewStatus("editor", "PROGRESS", event.description || "AI Edit working");
  } else if (event.type === "done") {
    state.project = event.project;
    if (event.job_status && state.project?.job) state.project.job.status = event.job_status;
    state.job = state.project?.job || null;
    state.editing = false;
    rememberCrewEvent("editor", { status: "done" });
    appendCrewStatus("editor", "ROUGH CUT READY", "Rough Cut assembled · screening pass open");
    syncCrewBoard(event.project, { silent: true });
    applyProjectSnapshot(event.project);
    setBrowserActivity("idle", event.project);
    if (els.editStatus) els.editStatus.textContent = "ROUGH CUT READY · 可预览并批准最终成片";
    state.editProgressStep = 6;
    renderDeliverProgress(event.project);
    toast("Rough Cut 已完成：镜头、声音与字幕轨已汇合，请先预览。");
    els.editConsole?.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth", block: "center" });
  } else if (event.type === "error") {
    const failure = eventErrorMessage(event);
    if (event.project) {
      state.project = event.project;
      if (event.job_status && state.project.job) state.project.job.status = event.job_status;
      applyProjectSnapshot(event.project);
    }
    state.editing = false;
    rememberCrewEvent("editor", { status: "failed" });
    appendCrewStatus("editor", "FAILED", failure);
    setBrowserActivity("idle", state.project);
    if (els.editStatus) els.editStatus.textContent = `AI Edit 中断：${failure}`;
    toast(`AI Edit 失败：${failure}`, true);
    if (state.project) renderWorkspace(state.project);
  }
}

async function startAiEdit() {
  if (!state.project || state.editing || state.rendering) return;
  if (!state.project.script?.dialogue_locked) {
    state.manualTab = "script";
    renderManual(state.project, "script");
    toast("请先审阅并锁定台词本 / 字幕稿，再启动 AI Edit。", true);
    els.manualBody?.scrollIntoView({ behavior: REDUCED_MOTION ? "auto" : "smooth", block: "center" });
    return;
  }
  state.editing = true;
  rememberCrewEvent("editor", { status: "working" });
  appendCrewStatus("editor", "START", "AI Edit reading locked dialogue and shot queue");
  syncCrewBoard({ ...state.project, status: "editing_rough_cut" }, { silent: true });
  state.editProgressStep = 0;
  els.deliverFinal?.classList.add("hidden");
  if (els.btnAiEdit) {
    els.btnAiEdit.disabled = true;
    els.btnAiEdit.textContent = "AI Edit 粗剪中…";
  }
  if (els.editStatus) els.editStatus.textContent = "AI Edit：正在读取锁定台词本…";
  renderDeliverProgress({ ...state.project, status: "editing_rough_cut" }, "");
  setBrowserActivity("edit", state.project);
  setPipeline({ plan: "done", previs: "done", render: "done", deliver: "active" });
  try {
    await streamPost(
      `/api/projects/${state.project.project_id}/edit/stream`,
      {
        music_mode: state.musicMode || state.project.music_mode || "ai",
        music_intensity: state.musicIntensity ?? state.project.music_intensity ?? 0.6,
        smart_ducking: state.smartDucking,
        music_asset_name: state.musicAssetName || state.project.music_asset_name || "",
        track_enabled: Object.fromEntries(AUDIO_TRACK_ORDER.map((key) => [key, state.project?.audio_tracks?.[key]?.enabled !== false])),
      },
      handleEditEvent
    );
  } catch (error) {
    state.editing = false;
    setBrowserActivity("idle", state.project);
    if (els.editStatus) els.editStatus.textContent = `AI Edit 中断：${error.message}`;
    toast(`AI Edit 失败：${error.message}`, true);
    if (state.project?.project_id) refreshJobStatus(state.project.project_id, { poll: true });
  } finally {
    if (els.btnAiEdit && state.project) renderMonitor(state.project, false);
  }
}

async function approveAiEdit() {
  if (!state.project || state.editing) return;
  const mode = els.subtitleMode?.value || "burned";
  if (els.btnApproveEdit) {
    els.btnApproveEdit.disabled = true;
    els.btnApproveEdit.textContent = "交付中…";
  }
  if (els.deliverStateTitle) els.deliverStateTitle.textContent = "最终成片编码中";
  if (els.deliverStateCopy) els.deliverStateCopy.textContent = "FFmpeg 正在写入最终画面与字幕轨，请稍候。";
  if (els.deliverStateBadge) {
    els.deliverStateBadge.textContent = "FINAL ENCODE";
    els.deliverStateBadge.dataset.state = "editing";
  }
  state.editProgressStep = 6;
  renderDeliverProgress({ ...state.project, status: "editing_rough_cut" }, "Final Encode · FFmpeg 编码交付");
  if (els.deliverProgressTitle) els.deliverProgressTitle.textContent = "最终成片编码中";
  try {
    const response = await fetch(`/api/projects/${state.project.project_id}/edit/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subtitle_mode: mode }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    state.project = payload;
    rememberCrewEvent("editor", { status: "done" });
    appendCrewStatus("editor", "FINAL CUT", `Delivery encoded · ${mode.toUpperCase()} subtitles`);
    syncCrewBoard(payload, { silent: true });
    renderWorkspace(payload);
    toast(`最终成片已批准（${mode === "burned" ? "烧录字幕" : mode === "soft" ? "软字幕" : "无字幕"}）。`);
    renderScreening(payload).then(() => {
      if (state.hasFinalVideo) openPremiere(payload);
    });
  } catch (error) {
    toast(`批准成片失败：${error.message}`, true);
    if (state.project) renderWorkspace(state.project);
    if (els.btnApproveEdit) {
      els.btnApproveEdit.disabled = false;
      els.btnApproveEdit.innerHTML = '批准最终成片 <span class="cta-arrow" aria-hidden="true">→</span>';
    }
  }
}

async function regenerateShot(shotNumber, action = "replan") {
  if (!state.project) return;
  const button = els.drawer.querySelector(`[data-inspector-action="${action}"]`);
  if (button) {
    button.disabled = true;
    button.textContent = action === "replan" ? "重新规划中…" : "处理中…";
  }
  try {
    const response = await fetch(
      `/api/projects/${state.project.project_id}/shots/${shotNumber}/regenerate`,
      { method: "POST" }
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    refreshWorkspaceAfterShotUpdate(payload);
    openDrawer(payload, shotNumber);
    toast(`镜头 ${shotNumber} 已重新规划。`);
  } catch (error) {
    toast(`重新规划失败：${error.message}`, true);
    if (button) {
      button.disabled = false;
      button.textContent = "↻ 重新规划";
    }
  }
}

/* ── 片库 ──────────────────────────────────────────────────── */

async function refreshLibrary() {
  try {
    const response = await fetch("/api/projects");
    const payload = await response.json();
    els.librarySelect.innerHTML = "";
    if (!payload.projects.length) {
      const option = document.createElement("option");
      option.textContent = "（暂无已保存项目）";
      option.value = "";
      els.librarySelect.appendChild(option);
      return;
    }
    for (const id of payload.projects) {
      const option = document.createElement("option");
      option.value = id;
      option.textContent = id;
      els.librarySelect.appendChild(option);
    }
  } catch {
    toast("无法读取片库，请确认服务正在运行。", true);
  }
}

async function loadSelectedProject() {
  const projectId = els.librarySelect.value;
  if (!projectId) {
    toast("请先选择一个项目。");
    return;
  }
  try {
    const response = await fetch(`/api/projects/${projectId}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    state.project = payload;
    state.hasFinalVideo = false;
    state.editing = false;
    state.busy = false;
    state.viewingHistorical = true;
    state.crewMessages = [];
    state.crewArtifacts = [];
    buildCrewBoard();
    syncHistoricalCrew(payload);
    show(els.actCrew);
    els.crewMeta.textContent = `RESTORED · PROJECT ${projectId.replace(/^film-/, "").toUpperCase()}`;
    renderWorkspace(payload, { entranceFrom: 0 });
    els.actCrew.scrollIntoView({ behavior: "smooth", block: "start" });
    toast(`已恢复项目 ${projectId}。`);
  } catch (error) {
    toast(`读取失败：${error.message}`, true);
  }
}

/* ── 第一幕细节：打字机 / 时间码 / 时钟 ────────────────────── */

function startTypewriter() {
  let ideaIndex = 0;
  let charIndex = 0;
  let deleting = false;
  function tick() {
    const sample = SAMPLE_IDEAS[ideaIndex];
    if (!deleting) {
      charIndex += 1;
      els.idea.placeholder = sample.slice(0, charIndex);
      if (charIndex >= sample.length) {
        deleting = true;
        setTimeout(tick, 2600);
        return;
      }
      setTimeout(tick, 62);
    } else {
      charIndex -= 1;
      els.idea.placeholder = sample.slice(0, Math.max(0, charIndex));
      if (charIndex <= 0) {
        deleting = false;
        ideaIndex = (ideaIndex + 1) % SAMPLE_IDEAS.length;
        setTimeout(tick, 500);
        return;
      }
      setTimeout(tick, 24);
    }
  }
  tick();
}

function startClock() {
  const startedAt = Date.now();
  setInterval(() => {
    els.clock.textContent = timecode((Date.now() - startedAt) / 1000);
  }, 1000);
}

function buildStyleCards() {
  els.styleCards.innerHTML = "";
  for (const style of STYLE_OPTIONS) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "style-card type-control";
    button.textContent = style;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(style === state.selectedStyle));
    if (style === state.selectedStyle) button.classList.add("selected");
    button.addEventListener("click", () => {
      state.selectedStyle = style;
      if (els.styleCurrent) els.styleCurrent.textContent = style;
      $$(".style-card").forEach((el) => {
        const isSelected = el === button;
        el.classList.toggle("selected", isSelected);
        el.setAttribute("aria-checked", String(isSelected));
      });
    });
    els.styleCards.appendChild(button);
  }
}

/* ── 视图路由：首页 ⇄ 创作页（电影遮幅转场） ────────────────── */

const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const LOW_PERFORMANCE = Number(navigator.hardwareConcurrency || 4) <= 2 || Number(navigator.deviceMemory || 4) <= 2;
const views = { landing: els.viewLanding, studio: els.viewStudio };
let viewTransitioning = false;

function clampUnit(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.min(1, number)) : 0;
}

function lerpValue(from, to, amount) {
  return from + (to - from) * amount;
}

function smoothUnit(value) {
  const unit = clampUnit(value);
  return unit * unit * (3 - 2 * unit);
}

function currentView() {
  return location.hash === "#/studio" ? "studio" : "landing";
}

function applyView(name) {
  document.body.dataset.view = name;
  views.landing.classList.toggle("hidden", name !== "landing");
  views.studio.classList.toggle("hidden", name !== "studio");
}

function gotoView(name) {
  if (viewTransitioning || currentView() === name) return;
  if (REDUCED_MOTION) {
    location.hash = name === "studio" ? "#/studio" : "#/";
    applyView(name);
    window.scrollTo(0, 0);
    return;
  }
  viewTransitioning = true;
  els.shutter.classList.add("is-closed");
  setTimeout(() => {
    const switchView = () => {
      location.hash = name === "studio" ? "#/studio" : "#/";
      applyView(name);
      window.scrollTo(0, 0);
    };
    if (typeof document.startViewTransition === "function") document.startViewTransition(switchView);
    else switchView();
    els.shutter.classList.remove("is-closed");
    setTimeout(() => {
      viewTransitioning = false;
    }, 460);
  }, 440);
}

window.addEventListener("hashchange", () => applyView(currentView()));

/* ── 首页交互：磁性按钮 / 聚光灯卡片 / 滚动渐显 ────────────── */

function initLandingInteractions() {
  const cta = els.btnEnter;
  cta.addEventListener("mousemove", (event) => {
    const rect = cta.getBoundingClientRect();
    const dx = (event.clientX - (rect.left + rect.width / 2)) / rect.width;
    const dy = (event.clientY - (rect.top + rect.height / 2)) / rect.height;
    cta.style.transform = `translate(${dx * 14}px, ${dy * 10}px)`;
  });
  cta.addEventListener("mouseleave", () => {
    cta.style.transform = "";
  });

  for (const card of $$(".feature-card")) {
    const motion = {
      x: card.offsetWidth / 2,
      y: card.offsetHeight / 2,
      targetX: card.offsetWidth / 2,
      targetY: card.offsetHeight / 2,
      tiltX: 0,
      tiltY: 0,
      targetTiltX: 0,
      targetTiltY: 0,
      frame: null,
      hovering: false,
    };

    const renderCardMotion = () => {
      motion.x += (motion.targetX - motion.x) * 0.18;
      motion.y += (motion.targetY - motion.y) * 0.18;
      motion.tiltX += (motion.targetTiltX - motion.tiltX) * 0.16;
      motion.tiltY += (motion.targetTiltY - motion.tiltY) * 0.16;
      card.style.setProperty("--mx", `${motion.x.toFixed(1)}px`);
      card.style.setProperty("--my", `${motion.y.toFixed(1)}px`);

      if (!REDUCED_MOTION) {
        const tiltSettled = Math.abs(motion.tiltX) < 0.02 && Math.abs(motion.tiltY) < 0.02;
        if (motion.hovering || !tiltSettled) {
          card.style.transform = `perspective(920px) rotateX(${motion.tiltY.toFixed(2)}deg) rotateY(${motion.tiltX.toFixed(2)}deg) translateY(-3px)`;
        } else {
          card.style.transform = "";
        }
      }

      const spotlightSettled = Math.abs(motion.targetX - motion.x) < 0.2 && Math.abs(motion.targetY - motion.y) < 0.2;
      const tiltSettled = Math.abs(motion.targetTiltX - motion.tiltX) < 0.02 && Math.abs(motion.targetTiltY - motion.tiltY) < 0.02;
      if (motion.hovering || !spotlightSettled || !tiltSettled) {
        motion.frame = requestAnimationFrame(renderCardMotion);
      } else {
        motion.frame = null;
      }
    };

    const requestCardMotion = () => {
      if (motion.frame === null) motion.frame = requestAnimationFrame(renderCardMotion);
    };

    card.addEventListener("pointerenter", (event) => {
      if (event.pointerType === "touch") return;
      motion.hovering = true;
      card.classList.add("is-hovered");
      card.style.setProperty("--spotlight-opacity", "1");
      requestCardMotion();
    });

    card.addEventListener("pointermove", (event) => {
      if (event.pointerType === "touch") return;
      const rect = card.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const px = x / rect.width - 0.5;
      const py = y / rect.height - 0.5;
      motion.targetX = x;
      motion.targetY = y;
      motion.targetTiltX = REDUCED_MOTION ? 0 : px * 4.2;
      motion.targetTiltY = REDUCED_MOTION ? 0 : py * -3.2;
      motion.hovering = true;
      card.classList.add("is-hovered");
      card.style.setProperty("--spotlight-opacity", "1");
      requestCardMotion();
    });

    card.addEventListener("pointerleave", (event) => {
      if (event.pointerType === "touch") return;
      motion.hovering = false;
      motion.targetX = card.offsetWidth / 2;
      motion.targetY = card.offsetHeight / 2;
      motion.targetTiltX = 0;
      motion.targetTiltY = 0;
      card.classList.remove("is-hovered");
      card.style.setProperty("--spotlight-opacity", "0");
      requestCardMotion();
    });
  }

  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-revealed");
        observer.unobserve(entry.target);
      }
    }
  }, { threshold: 0.2 });
  for (const el of $$(".reveal")) observer.observe(el);

  const hero = $(".landing-hero");
  const spotlight = $(".landing-spotlight");
  let landingFrame = null;
  window.setTimeout(() => hero?.classList.add("is-booted"), REDUCED_MOTION ? 0 : 120);
  window.addEventListener("pointermove", (event) => {
    if (REDUCED_MOTION || currentView() !== "landing" || !hero) return;
    if (landingFrame) cancelAnimationFrame(landingFrame);
    landingFrame = requestAnimationFrame(() => {
      const x = ((event.clientX / window.innerWidth) - 0.5) * 10;
      const y = ((event.clientY / window.innerHeight) - 0.5) * 8;
      hero.style.setProperty("--aurora-x", `${x}px`);
      hero.style.setProperty("--aurora-y", `${y}px`);
      if (spotlight) {
        const x = (event.clientX / Math.max(1, window.innerWidth)) * 100;
        const y = (event.clientY / Math.max(1, window.innerHeight)) * 100;
        const angle = -18 + ((event.clientX / Math.max(1, window.innerWidth)) - 0.5) * 7;
        const dx = ((event.clientX / Math.max(1, window.innerWidth)) - 0.5) * 10;
        const dy = ((event.clientY / Math.max(1, window.innerHeight)) - 0.5) * 7;
        spotlight.style.setProperty("--spotlight-x", `${x.toFixed(2)}%`);
        spotlight.style.setProperty("--spotlight-y", `${y.toFixed(2)}%`);
        spotlight.style.setProperty("--spotlight-angle", `${angle.toFixed(2)}deg`);
        spotlight.style.setProperty("--spotlight-dx", `${dx.toFixed(2)}px`);
        spotlight.style.setProperty("--spotlight-dy", `${dy.toFixed(2)}px`);
      }
      landingFrame = null;
    });
  });
}

/* Production Route：一盏共享的暖色指示灯，连接 ruler、handoff 和 stage surface。 */
function initProductionRouteInteraction() {
  const route = $(".production-route");
  if (!route || REDUCED_MOTION) return;
  const rulerStages = $$(".production-ruler-stage", route);
  const cards = $$(".production-stage-card", route);
  const line = $(".production-ruler-line i", route);
  const stageNames = ["greenlight", "crew", "delivery"];
  const reset = () => {
    route.style.setProperty("--route-pointer-opacity", "0");
    for (const element of [...rulerStages, ...cards]) element.classList.remove("is-route-active");
    if (line) line.style.setProperty("--route-progress", "33.333%");
  };
  const update = (event) => {
    if (event.pointerType === "touch") return;
    const routeRect = route.getBoundingClientRect();
    route.style.setProperty("--route-pointer-x", `${event.clientX - routeRect.left}px`);
    route.style.setProperty("--route-pointer-y", `${event.clientY - routeRect.top}px`);
    route.style.setProperty("--route-pointer-opacity", "1");
    const index = rulerStages.reduce((closest, stage, stageIndex) => {
      const rect = stage.getBoundingClientRect();
      const distance = Math.abs(event.clientX - (rect.left + rect.width / 2));
      const closestRect = rulerStages[closest]?.getBoundingClientRect();
      const closestDistance = closestRect ? Math.abs(event.clientX - (closestRect.left + closestRect.width / 2)) : Number.POSITIVE_INFINITY;
      return distance < closestDistance ? stageIndex : closest;
    }, 0);
    for (const [stageIndex, name] of stageNames.entries()) {
      rulerStages[stageIndex]?.classList.toggle("is-route-active", stageIndex === index);
      cards.find((card) => card.dataset.stage === name)?.classList.toggle("is-route-active", stageIndex === index);
    }
    if (line) line.style.setProperty("--route-progress", `${((index + 1) / stageNames.length) * 100}%`);
  };
  route.addEventListener("pointerenter", update, { passive: true });
  route.addEventListener("pointermove", update, { passive: true });
  route.addEventListener("pointerleave", reset, { passive: true });
}

/* 首页显影台：pointer distance -> 0..1 -> lerp -> 分层视觉状态。
   画面本身不监听 hover 状态，离开后仍会沿着物理回弹曲线退回暗房。 */
function initLandingProximity() {
  const hero = $(".landing-hero");
  const reveal = $("#landing-reveal");
  if (!hero || !reveal || REDUCED_MOTION) {
    reveal?.style.setProperty("--reveal-script", "0.2");
    reveal?.style.setProperty("--reveal-standby", "0.42");
    reveal?.style.setProperty("--reveal-sketch", "0.15");
    reveal?.style.setProperty("--reveal-light", "0.08");
    reveal?.style.setProperty("--reveal-color", "0.04");
    reveal?.style.setProperty("--reveal-final", "0.02");
    return;
  }

  const motion = {
    targetProgress: 0,
    progress: 0,
    targetHeroX: 50,
    targetHeroY: 46,
    heroX: 50,
    heroY: 46,
    targetHeroPresence: 0,
    heroPresence: 0,
    targetLightX: 54,
    targetLightY: 44,
    lightX: 54,
    lightY: 44,
    targetLightAlpha: 0,
    lightAlpha: 0,
    targetTitleFocus: 0,
    titleFocus: 0,
    targetCtaFocus: 0,
    ctaFocus: 0,
    targetCtaX: 50,
    targetCtaY: 50,
    ctaX: 50,
    ctaY: 50,
    targetRevealFocus: 0,
    revealFocus: 0,
    targetDepthX: 0,
    targetDepthY: 0,
    depthX: 0,
    depthY: 0,
    pointerInside: false,
    frame: null,
  };

  const setVar = (name, value) => reveal.style.setProperty(name, String(value));
  const setLightVar = (name, value) => hero.style.setProperty(name, String(value));

  const render = () => {
    const response = LOW_PERFORMANCE ? 0.18 : 0.2;
    motion.progress = lerpValue(motion.progress, motion.targetProgress, response);
    motion.heroX = lerpValue(motion.heroX, motion.targetHeroX, response);
    motion.heroY = lerpValue(motion.heroY, motion.targetHeroY, response);
    motion.heroPresence = lerpValue(motion.heroPresence, motion.targetHeroPresence, response);
    motion.lightX = lerpValue(motion.lightX, motion.targetLightX, response);
    motion.lightY = lerpValue(motion.lightY, motion.targetLightY, response);
    motion.lightAlpha = lerpValue(motion.lightAlpha, motion.targetLightAlpha, response);
    motion.titleFocus = lerpValue(motion.titleFocus, motion.targetTitleFocus, response);
    motion.ctaFocus = lerpValue(motion.ctaFocus, motion.targetCtaFocus, response);
    motion.ctaX = lerpValue(motion.ctaX, motion.targetCtaX, response);
    motion.ctaY = lerpValue(motion.ctaY, motion.targetCtaY, response);
    motion.revealFocus = lerpValue(motion.revealFocus, motion.targetRevealFocus, response);
    motion.depthX = lerpValue(motion.depthX, motion.targetDepthX, response);
    motion.depthY = lerpValue(motion.depthY, motion.targetDepthY, response);

    const progress = motion.progress;
    const script = 0.2 + progress * 0.28;
    const standby = 0.34 + progress * 0.58;
    const sketch = 0.15 + smoothUnit((progress - 0.02) / 0.3) * 0.72;
    const light = 0.08 + smoothUnit((progress - 0.16) / 0.3) * 0.86;
    const color = 0.04 + smoothUnit((progress - 0.42) / 0.34) * 0.96;
    const finalFrame = 0.02 + smoothUnit((progress - 0.68) / 0.32) * 0.98;
    setVar("--reveal-progress", progress.toFixed(3));
    setVar("--reveal-standby", standby.toFixed(3));
    setVar("--reveal-script", script.toFixed(3));
    setVar("--reveal-sketch", sketch.toFixed(3));
    setVar("--reveal-light", light.toFixed(3));
    setVar("--reveal-color", color.toFixed(3));
    setVar("--reveal-final", finalFrame.toFixed(3));
    setVar("--reveal-vignette", Math.min(0.08, 0.04 + finalFrame * 0.04).toFixed(3));
    setVar("--reveal-grain", Math.min(0.04, 0.02 + finalFrame * 0.02).toFixed(3));
    setVar("--reveal-caption", (0.34 + progress * 0.48).toFixed(3));
    setVar("--reveal-final-radius", `${(8 + finalFrame * 92).toFixed(2)}%`);
    setVar("--reveal-light-x", `${motion.lightX.toFixed(2)}%`);
    setVar("--reveal-light-y", `${motion.lightY.toFixed(2)}%`);
    setVar("--reveal-depth-x", `${(motion.depthX * 0.12).toFixed(2)}px`);
    setVar("--reveal-depth-y", `${(motion.depthY * 0.12).toFixed(2)}px`);
    setVar("--script-shift-x", `${(motion.depthX * 0.18).toFixed(2)}px`);
    setVar("--script-shift-y", `${(motion.depthY * 0.18).toFixed(2)}px`);
    setVar("--sketch-shift-x", `${(motion.depthX * 0.34).toFixed(2)}px`);
    setVar("--sketch-shift-y", `${(motion.depthY * 0.34).toFixed(2)}px`);
    setVar("--color-shift-x", `${(motion.depthX * 0.58).toFixed(2)}px`);
    setVar("--color-shift-y", `${(motion.depthY * 0.58).toFixed(2)}px`);
    setVar("--final-shift-x", `${(motion.depthX * 0.82).toFixed(2)}px`);
    setVar("--final-shift-y", `${(motion.depthY * 0.82).toFixed(2)}px`);
    setLightVar("--hero-pointer-x", `${motion.heroX.toFixed(2)}%`);
    setLightVar("--hero-pointer-y", `${motion.heroY.toFixed(2)}%`);
    setLightVar("--hero-pointer-presence", motion.heroPresence.toFixed(3));
    setLightVar("--hero-title-focus", motion.titleFocus.toFixed(3));
    setLightVar("--hero-cta-focus", motion.ctaFocus.toFixed(3));
    setLightVar("--cta-light-x", `${motion.ctaX.toFixed(2)}%`);
    setLightVar("--cta-light-y", `${motion.ctaY.toFixed(2)}%`);
    setLightVar("--hero-reveal-focus", motion.revealFocus.toFixed(3));
    setLightVar("--shared-light-x", `${motion.heroX.toFixed(2)}%`);
    setLightVar("--shared-light-y", `${motion.heroY.toFixed(2)}%`);
    setLightVar("--shared-light-alpha", motion.lightAlpha.toFixed(3));

    const settling = Math.abs(motion.targetProgress - motion.progress) < 0.002
      && Math.abs(motion.targetHeroPresence - motion.heroPresence) < 0.002
      && Math.abs(motion.targetLightAlpha - motion.lightAlpha) < 0.002
      && Math.abs(motion.targetTitleFocus - motion.titleFocus) < 0.002
      && Math.abs(motion.targetCtaFocus - motion.ctaFocus) < 0.002
      && Math.abs(motion.targetCtaX - motion.ctaX) < 0.12
      && Math.abs(motion.targetCtaY - motion.ctaY) < 0.12
      && Math.abs(motion.targetRevealFocus - motion.revealFocus) < 0.002
      && Math.abs(motion.targetDepthX - motion.depthX) < 0.12
      && Math.abs(motion.targetDepthY - motion.depthY) < 0.12;
    if (motion.pointerInside || !settling) motion.frame = requestAnimationFrame(render);
    else motion.frame = null;
  };

  const requestRender = () => {
    if (motion.frame === null) motion.frame = requestAnimationFrame(render);
  };

  const updateTarget = (event) => {
    if (event.pointerType === "touch") return;
    const revealRect = reveal.getBoundingClientRect();
    const heroRect = hero.getBoundingClientRect();
    const proximityTo = (rect, radius) => {
      const closestX = Math.max(rect.left, Math.min(event.clientX, rect.right));
      const closestY = Math.max(rect.top, Math.min(event.clientY, rect.bottom));
      return smoothUnit(clampUnit(1 - Math.hypot(event.clientX - closestX, event.clientY - closestY) / radius));
    };
    const revealRadius = Math.max(260, Math.min(720, Math.max(revealRect.width * 0.82, revealRect.height * 1.22)));
    const revealFocus = proximityTo(revealRect, revealRadius);
    const titleFocus = proximityTo(hero.querySelector(".landing-title")?.getBoundingClientRect() || heroRect, 290);
    const ctaRect = els.btnEnter?.getBoundingClientRect() || heroRect;
    const ctaFocus = proximityTo(ctaRect, 190);
    motion.targetProgress = Math.max(0.16, clampUnit(revealFocus * 1.08));
    motion.targetHeroX = clampUnit((event.clientX - heroRect.left) / Math.max(1, heroRect.width)) * 100;
    motion.targetHeroY = clampUnit((event.clientY - heroRect.top) / Math.max(1, heroRect.height)) * 100;
    motion.targetHeroPresence = 1;
    motion.targetLightX = clampUnit((event.clientX - revealRect.left) / Math.max(1, revealRect.width)) * 100;
    motion.targetLightY = clampUnit((event.clientY - revealRect.top) / Math.max(1, revealRect.height)) * 100;
    motion.targetTitleFocus = titleFocus;
    motion.targetCtaFocus = ctaFocus;
    motion.targetCtaX = clampUnit((event.clientX - ctaRect.left) / Math.max(1, ctaRect.width)) * 100;
    motion.targetCtaY = clampUnit((event.clientY - ctaRect.top) / Math.max(1, ctaRect.height)) * 100;
    motion.targetRevealFocus = revealFocus;
    motion.targetLightAlpha = Math.min(0.86, 0.2 + motion.targetProgress * 0.52 + titleFocus * 0.08 + ctaFocus * 0.1 + revealFocus * 0.12) * (LOW_PERFORMANCE ? 0.84 : 1);
    motion.targetDepthX = Math.max(-12, Math.min(12, (event.clientX - (heroRect.left + heroRect.width * 0.5)) / Math.max(1, heroRect.width) * 18));
    motion.targetDepthY = Math.max(-9, Math.min(9, (event.clientY - (heroRect.top + heroRect.height * 0.46)) / Math.max(1, heroRect.height) * 14));
    motion.pointerInside = true;
    requestRender();
  };

  hero.addEventListener("pointerenter", updateTarget, { passive: true });
  hero.addEventListener("pointermove", updateTarget, { passive: true });
  hero.addEventListener("pointerleave", () => {
    motion.pointerInside = false;
    motion.targetProgress = 0;
    motion.targetHeroPresence = 0;
    motion.targetLightAlpha = 0;
    motion.targetTitleFocus = 0;
    motion.targetCtaFocus = 0;
    motion.targetCtaX = 50;
    motion.targetCtaY = 50;
    motion.targetRevealFocus = 0;
    motion.targetHeroX = 50;
    motion.targetHeroY = 46;
    motion.targetLightX = 54;
    motion.targetLightY = 44;
    motion.targetDepthX = 0;
    motion.targetDepthY = 0;
    requestRender();
  }, { passive: true });
  window.addEventListener("resize", requestRender, { passive: true });
  requestRender();
}

/* Crew Assembly：鼠标在生产链上的距离会连续点亮节点和相邻交接线，
   不改变真实的 Agent 状态，只为当前路径提供空间化反馈。 */
function initCrewProximity() {
  const flow = els.crewFlow;
  if (!flow || REDUCED_MOTION) return;
  const motions = new Map();
  let pointerInside = false;
  let frame = null;

  const ensureMotion = (card) => {
    if (!motions.has(card)) motions.set(card, { value: 0, target: 0, x: 50, y: 50, targetX: 50, targetY: 50 });
    return motions.get(card);
  };
  const render = () => {
    const cards = Array.from(flow.querySelectorAll(".crew-card"));
    const liveCards = new Set(cards);
    for (const card of motions.keys()) if (!liveCards.has(card)) motions.delete(card);
    for (const card of cards) {
      const item = ensureMotion(card);
      item.value = lerpValue(item.value, item.target, LOW_PERFORMANCE ? 0.2 : 0.13);
      item.x = lerpValue(item.x, item.targetX, 0.15);
      item.y = lerpValue(item.y, item.targetY, 0.15);
      card.style.setProperty("--crew-proximity", item.value.toFixed(3));
      card.style.setProperty("--crew-proximity-x", `${item.x.toFixed(1)}%`);
      card.style.setProperty("--crew-proximity-y", `${item.y.toFixed(1)}%`);
      card.style.setProperty("--crew-proximity-border", (item.value * 0.72).toFixed(3));
    }
    const nodes = Array.from(flow.querySelectorAll(".crew-flow-node"));
    nodes.forEach((node, index) => {
      const left = node.querySelector(".crew-card");
      const right = nodes[index + 1]?.querySelector(".crew-card");
      const link = node.querySelector(".crew-flow-link");
      if (!link || !left || !right) return;
      const leftValue = motions.get(left)?.value || 0;
      const rightValue = motions.get(right)?.value || 0;
      const proximity = Math.max(leftValue, rightValue) * 0.86;
      link.style.setProperty("--link-proximity", proximity.toFixed(3));
      link.style.setProperty("--link-proximity-border", (0.18 + proximity * 0.64).toFixed(3));
      link.classList.toggle("is-proximity", proximity > 0.06);
    });
    const settling = !pointerInside && Array.from(motions.values()).every((item) => item.value < 0.004 && item.target < 0.004);
    if (pointerInside || !settling) frame = requestAnimationFrame(render);
    else frame = null;
  };
  const requestRender = () => { if (frame === null) frame = requestAnimationFrame(render); };
  const updateTarget = (event) => {
    if (event.pointerType === "touch") return;
    pointerInside = true;
    const cards = Array.from(flow.querySelectorAll(".crew-card"));
    for (const card of cards) {
      const item = ensureMotion(card);
      const rect = card.getBoundingClientRect();
      const closestX = Math.max(rect.left, Math.min(event.clientX, rect.right));
      const closestY = Math.max(rect.top, Math.min(event.clientY, rect.bottom));
      const distance = Math.hypot(event.clientX - closestX, event.clientY - closestY);
      const radius = Math.max(150, Math.min(280, Math.max(rect.width, rect.height) * 1.55));
      item.target = smoothUnit(1 - distance / radius);
      item.targetX = clampUnit((event.clientX - rect.left) / Math.max(1, rect.width)) * 100;
      item.targetY = clampUnit((event.clientY - rect.top) / Math.max(1, rect.height)) * 100;
    }
    requestRender();
  };
  flow.addEventListener("pointerenter", updateTarget, { passive: true });
  flow.addEventListener("pointermove", updateTarget, { passive: true });
  flow.addEventListener("pointerleave", () => {
    pointerInside = false;
    for (const item of motions.values()) item.target = 0;
    requestRender();
  }, { passive: true });
  requestRender();
}

/* 分镜胶片带：原生 scroll-snap + pointer drag + 轻惯性，拖拽时只加入极轻的速度倾斜。 */
function initFilmstripInteractions() {
  const viewport = els.filmstripViewport;
  const strip = els.filmstrip;
  if (!viewport || !strip) return;
  let dragging = false;
  let moved = false;
  let startX = 0;
  let startScroll = 0;
  let lastX = 0;
  let lastTime = 0;
  let velocity = 0;
  let skewFrame = null;
  let inertiaFrame = null;
  let captured = false;
  const settleSkew = () => {
    velocity *= 0.78;
    strip.style.setProperty("--filmstrip-skew", `${Math.max(-1.8, Math.min(1.8, velocity * -0.06)).toFixed(2)}deg`);
    if (Math.abs(velocity) > 0.15) skewFrame = requestAnimationFrame(settleSkew);
    else { skewFrame = null; strip.style.setProperty("--filmstrip-skew", "0deg"); }
  };
  const runInertia = () => {
    if (REDUCED_MOTION || Math.abs(velocity) < 0.2) {
      inertiaFrame = null;
      cancelAnimationFrame(skewFrame);
      skewFrame = requestAnimationFrame(settleSkew);
      return;
    }
    viewport.scrollLeft -= velocity * 1.35;
    velocity *= 0.91;
    strip.style.setProperty("--filmstrip-skew", `${Math.max(-1.8, Math.min(1.8, velocity * -0.06)).toFixed(2)}deg`);
    inertiaFrame = requestAnimationFrame(runInertia);
  };
  viewport.addEventListener("pointerdown", (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    cancelAnimationFrame(inertiaFrame);
    inertiaFrame = null;
    cancelAnimationFrame(skewFrame);
    skewFrame = null;
    dragging = true;
    moved = false;
    startX = event.clientX;
    startScroll = viewport.scrollLeft;
    lastX = event.clientX;
    lastTime = performance.now();
    captured = false;
    viewport.classList.add("is-dragging");
  });
  viewport.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    const dx = event.clientX - startX;
    if (!moved && Math.abs(dx) <= 10) return;
    moved = true;
    if (!captured) {
      viewport.setPointerCapture?.(event.pointerId);
      captured = true;
    }
    viewport.scrollLeft = startScroll - dx;
    const now = performance.now();
    const dt = Math.max(8, now - lastTime);
    velocity = (event.clientX - lastX) / dt * 16;
    lastX = event.clientX;
    lastTime = now;
    strip.style.setProperty("--filmstrip-skew", `${Math.max(-1.8, Math.min(1.8, velocity * -0.06)).toFixed(2)}deg`);
    event.preventDefault();
  });
  const release = (event) => {
    if (!dragging) return;
    dragging = false;
    state.filmstripDragging = moved;
    viewport.classList.remove("is-dragging");
    if (captured) viewport.releasePointerCapture?.(event.pointerId);
    captured = false;
    cancelAnimationFrame(skewFrame);
    if (moved && !REDUCED_MOTION) inertiaFrame = requestAnimationFrame(runInertia);
    else skewFrame = requestAnimationFrame(settleSkew);
    if (moved) window.setTimeout(() => { state.filmstripDragging = false; }, 40);
  };
  viewport.addEventListener("pointerup", release);
  viewport.addEventListener("pointercancel", release);
  viewport.addEventListener("click", (event) => {
    if (!state.filmstripDragging) return;
    event.preventDefault();
    event.stopPropagation();
    state.filmstripDragging = false;
  }, true);
  viewport.addEventListener("wheel", (event) => {
    if (Math.abs(event.deltaY) > Math.abs(event.deltaX) && viewport.scrollWidth > viewport.clientWidth) {
      viewport.scrollLeft += event.deltaY;
      event.preventDefault();
    }
  }, { passive: false });
}

/* 分镜显影：距离最近的 Shot 从线稿推到彩色 keyframe，已生成视频仍由视频层接管。 */
function initStoryboardProximity() {
  const viewport = els.filmstripViewport;
  if (!viewport || REDUCED_MOTION) return;
  const motions = new Map();
  let pointerInside = false;
  let frame = null;
  const ensureMotion = (card) => {
    if (!motions.has(card)) motions.set(card, { value: 0, target: 0, x: 50, y: 50, targetX: 50, targetY: 50 });
    return motions.get(card);
  };
  const render = () => {
    const cards = Array.from(viewport.querySelectorAll(".shot-card"));
    const liveCards = new Set(cards);
    for (const card of motions.keys()) if (!liveCards.has(card)) motions.delete(card);
    for (const card of cards) {
      const item = ensureMotion(card);
      item.value = lerpValue(item.value, item.target, LOW_PERFORMANCE ? 0.22 : 0.14);
      item.x = lerpValue(item.x, item.targetX, 0.16);
      item.y = lerpValue(item.y, item.targetY, 0.16);
      card.style.setProperty("--shot-proximity", item.value.toFixed(3));
      card.style.setProperty("--shot-proximity-x", `${item.x.toFixed(1)}%`);
      card.style.setProperty("--shot-proximity-y", `${item.y.toFixed(1)}%`);
      card.style.setProperty("--shot-sketch-opacity", (0.68 - item.value * 0.58).toFixed(3));
      card.style.setProperty("--shot-color-opacity", (item.value * 0.86).toFixed(3));
      card.style.setProperty("--shot-color-scale", (1.015 + item.value * 0.035).toFixed(3));
      card.style.setProperty("--shot-sketch-x", `${((item.x - 50) * 0.04).toFixed(2)}px`);
      card.style.setProperty("--shot-sketch-y", `${((item.y - 50) * 0.04).toFixed(2)}px`);
      card.style.setProperty("--shot-color-x", `${((item.x - 50) * 0.1).toFixed(2)}px`);
      card.style.setProperty("--shot-color-y", `${((item.y - 50) * 0.1).toFixed(2)}px`);
    }
    const settling = !pointerInside && Array.from(motions.values()).every((item) => item.value < 0.004 && item.target < 0.004);
    if (pointerInside || !settling) frame = requestAnimationFrame(render);
    else frame = null;
  };
  const requestRender = () => { if (frame === null) frame = requestAnimationFrame(render); };
  const updateTarget = (event) => {
    if (event.pointerType === "touch") return;
    pointerInside = true;
    for (const card of viewport.querySelectorAll(".shot-card")) {
      const item = ensureMotion(card);
      const rect = card.getBoundingClientRect();
      const closestX = Math.max(rect.left, Math.min(event.clientX, rect.right));
      const closestY = Math.max(rect.top, Math.min(event.clientY, rect.bottom));
      const distance = Math.hypot(event.clientX - closestX, event.clientY - closestY);
      const radius = Math.max(150, Math.min(320, rect.width * 1.42));
      item.target = smoothUnit(1 - distance / radius);
      item.targetX = clampUnit((event.clientX - rect.left) / Math.max(1, rect.width)) * 100;
      item.targetY = clampUnit((event.clientY - rect.top) / Math.max(1, rect.height)) * 100;
    }
    requestRender();
  };
  viewport.addEventListener("pointerenter", updateTarget, { passive: true });
  viewport.addEventListener("pointermove", updateTarget, { passive: true });
  viewport.addEventListener("pointerleave", () => {
    pointerInside = false;
    for (const item of motions.values()) item.target = 0;
    requestRender();
  }, { passive: true });
  requestRender();
}

/* 滚动摄影机：用 IntersectionObserver 做离散景深提示，避免在主线程绑 scroll 事件。 */
function initScrollMotion() {
  document.documentElement.style.setProperty("--page-progress", "0");
  const elements = Array.from(document.querySelectorAll(".panel, .feature-card, .crew-radio-wrap"));
  if (!elements.length || typeof IntersectionObserver !== "function") return;
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const index = elements.indexOf(entry.target);
      const direction = index % 2 ? 1 : -1;
      const visibility = Math.max(0, Math.min(1, entry.intersectionRatio));
      const shift = (1 - visibility) * direction * 4;
      entry.target.style.setProperty("--depth-shift", `${shift.toFixed(1)}px`);
    }
  }, { threshold: [0, 0.25, 0.5, 0.75, 1] });
  elements.forEach((element) => observer.observe(element));
}

/* 全站保留浏览器原生光标；局部受光和节点状态承担上下文反馈。 */
function initTheme() {
  const create = MovieAgentModules.theme.createThemeController;
  if (typeof create === "function") {
    create({ toggle: els.themeToggle, wash: els.themeWash, colorMeta: els.themeColor }).init();
  }
}

function updateSoundToggle() {
  els.btnSound.classList.toggle("is-on", state.soundEnabled);
  els.btnSound.textContent = state.soundEnabled ? "♪ ON" : "♪ OFF";
  els.btnSound.setAttribute("aria-pressed", String(state.soundEnabled));
}

function navigateShot(direction) {
  const shots = (state.project && state.project.storyboard) || [];
  if (!shots.length) return;
  const current = shots.findIndex((shot) => shot.number === state.activeShotNumber);
  const index = current < 0 ? 0 : (current + direction + shots.length) % shots.length;
  openDrawer(state.project, shots[index].number);
}

/* ── 初始化 ────────────────────────────────────────────────── */

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    state.health = await response.json();
    els.engineLamp?.classList.remove("is-pending", "is-error");
    const text = state.health.text_mode === "modelscope" ? "ModelScope AI 文案" : "mock 文案";
    const video = state.health.video_mode === "comfyui" ? "Spark 真实视频" : "mock 视频流程";
    els.modeNote.textContent = `制作引擎就绪 · ${text} + ${video}`;
  } catch {
    els.engineLamp?.classList.remove("is-pending");
    els.engineLamp?.classList.add("is-error");
    els.modeNote.textContent = "无法连接后端服务。";
  }
}

function init() {
  initTheme();
  if (LOW_PERFORMANCE) document.body.classList.add("low-performance");
  applyView(currentView());
  setPipeline({ plan: "active" });
  setBrowserActivity("idle");
  updateSoundToggle();
  els.btnEnter.addEventListener("click", () => { playUiSound("slate"); gotoView("studio"); });
  els.brandHome.addEventListener("click", () => gotoView("landing"));
  els.btnSound.addEventListener("click", () => {
    state.soundEnabled = !state.soundEnabled;
    localStorage.setItem("movie-agent-sound", state.soundEnabled ? "on" : "off");
    updateSoundToggle();
    if (state.soundEnabled) playUiSound("done");
  });
  els.crewRadioToggle.addEventListener("click", () => {
    state.crewRadioOpen = !state.crewRadioOpen;
    renderCrewRadio();
  });
  els.btnPremierePlay.addEventListener("click", () => closePremiere(true));
  els.btnPremiereSkip.addEventListener("click", () => closePremiere(false));
  initLandingInteractions();
  initProductionRouteInteraction();
  initLandingProximity();
  initFilmstripInteractions();
  initStoryboardProximity();
  initCrewProximity();
  initFinalCompare();
  initScrollMotion();
  buildStyleCards();
  startTypewriter();
  startClock();
  startCrewTicker();
  loadHealth();
  refreshLibrary();
  els.duration.addEventListener("input", () => {
    els.tcValue.textContent = timecode(Number(els.duration.value));
  });
  els.idea.addEventListener("input", () => {
    updateIdeaCounter();
    if (els.idea.value.trim().length >= 10) setIdeaError();
  });
  els.idea.addEventListener("blur", () => {
    if (els.idea.value.trim()) validateIdea();
  });
  els.btnStart.addEventListener("click", startCreation);
  els.btnLoad.addEventListener("click", loadSelectedProject);
  els.btnRefresh.addEventListener("click", refreshLibrary);
  els.btnRender.addEventListener("click", startRender);
  els.btnAiEdit?.addEventListener("click", startAiEdit);
  els.btnRecut?.addEventListener("click", startAiEdit);
  els.btnReedit?.addEventListener("click", startAiEdit);
  els.btnEditSubtitles?.addEventListener("click", openSubtitleEditor);
  els.btnApproveEdit?.addEventListener("click", approveAiEdit);
  els.techSummaryToggle?.addEventListener("click", () => {
    const details = els.techSummaryDetails;
    if (!details) return;
    const isHidden = details.classList.toggle("hidden");
    els.techSummaryToggle.setAttribute("aria-expanded", String(!isHidden));
  });
  els.soundSummaryToggle?.addEventListener("click", () => {
    const body = els.soundSummaryBody;
    if (!body) return;
    const isHidden = body.classList.toggle("hidden");
    els.soundSummaryToggle.setAttribute("aria-expanded", String(!isHidden));
  });
  els.btnSoundSettings?.addEventListener("click", () => {
    els.soundSummaryBody?.classList.remove("hidden");
    els.soundSummaryToggle?.setAttribute("aria-expanded", "true");
    els.soundSummary?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  document.querySelector("[data-audio-advanced-toggle]")?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    const expanded = els.audioDesignConsole?.classList.toggle("is-expanded") || false;
    button.setAttribute("aria-expanded", String(expanded));
    button.textContent = expanded ? "HIDE MIX CONTROLS" : "SHOW MIX CONTROLS";
  });
  els.deliverQualityModes?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-quality-mode]");
    if (!button || !state.project) return;
    state.previewQualityMode = button.dataset.qualityMode || "auto";
    renderMediaQuality(state.project, state.previewQualityMode === "auto" ? "screening" : state.previewQualityMode);
  });
  els.btnExportFinal?.addEventListener("click", openExportSheet);
  els.btnExportClose?.addEventListener("click", closeExportSheet);
  els.btnExportRun?.addEventListener("click", exportFinalCut);
  document.addEventListener("click", handleAudioInteraction);
  document.addEventListener("keydown", handleAudioInspectorKeydown);
  document.addEventListener("input", handleAudioInspectorInput);
  document.addEventListener("change", (event) => {
    if (!event.target.closest("[data-audio-inspector-field]")) return;
    handleAudioInspectorInput(event);
    persistAudioDesign({ track_params: audioTrackParamsPayload() });
  });
  document.addEventListener("click", handleFinalLookInteraction);
  els.finalLookIntensity?.addEventListener("input", () => updateFinalLookDraft("intensity", els.finalLookIntensity.value));
  els.finalLookGrain?.addEventListener("input", () => updateFinalLookDraft("grain", els.finalLookGrain.value));
  els.finalLookVignette?.addEventListener("input", () => updateFinalLookDraft("vignette", els.finalLookVignette.value));
  els.finalLookSoftening?.addEventListener("input", () => updateFinalLookDraft("highlight_soften", els.finalLookSoftening.value));
  els.finalLookApply?.addEventListener("click", applyFinalLook);
  els.finalLookReset?.addEventListener("click", resetFinalLookPreview);
  els.smartDuckingToggle?.addEventListener("change", () => {
    state.smartDucking = Boolean(els.smartDuckingToggle.checked);
    renderAudioDesign(state.project);
    persistAudioDesign({ smart_ducking: state.smartDucking });
  });
  els.deliverSmartDuckingToggle?.addEventListener("change", () => {
    state.smartDucking = Boolean(els.deliverSmartDuckingToggle.checked);
    renderAudioDesign(state.project);
    persistAudioDesign({ smart_ducking: state.smartDucking });
  });
  els.deliverMusicIntensity?.addEventListener("input", () => {
    state.musicIntensity = Number(els.deliverMusicIntensity.value || 0.6);
    if (els.deliverMusicIntensityValue) els.deliverMusicIntensityValue.textContent = `${Math.round(state.musicIntensity * 100)}%`;
  });
  els.deliverMusicIntensity?.addEventListener("change", () => {
    persistAudioDesign({ music_intensity: state.musicIntensity });
  });
  els.musicUpload?.addEventListener("change", () => {
    const file = els.musicUpload.files?.[0];
    if (file) uploadMusicFile(file);
  });
  els.deliverMusicUpload?.addEventListener("change", () => {
    const file = els.deliverMusicUpload.files?.[0];
    if (file) uploadMusicFile(file);
  });
  els.exportSheet?.addEventListener("click", (event) => {
    if (event.target === els.exportSheet) closeExportSheet();
    const option = event.target.closest("[data-export-field]");
    if (!option) return;
    state.exportOptions[option.dataset.exportField] = option.dataset.exportValue;
    updateExportSelection();
    refreshExportPreflight();
  });
  els.btnMoreExport?.addEventListener("click", () => {
    const isOpen = !els.moreExportMenu?.classList.contains("hidden");
    els.moreExportMenu?.classList.toggle("hidden", isOpen);
    els.btnMoreExport?.setAttribute("aria-expanded", String(!isOpen));
  });
  els.btnNormalizeResolution?.addEventListener("click", normalizeProjectResolution);
  els.btnCleanWorkingCache?.addEventListener("click", cleanWorkingCache);
  [els.finalVideo, els.roughCutVideo].forEach((media) => {
    if (!media) return;
    media.addEventListener("loadedmetadata", () => {
      if (media === els.finalVideo) updateFinalVideoMetadata();
      syncAudioTimeline(media.currentTime || 0, media.duration || state.audioTimelineDuration || 1);
      syncFinalCompareMedia(media);
    });
    media.addEventListener("timeupdate", () => {
      syncAudioTimeline(media.currentTime, media.duration || state.audioTimelineDuration || 1);
      if (media === els.finalVideo) syncFinalCompareMedia(media);
    });
    media.addEventListener("play", () => {
      syncAudioTimeline(media.currentTime, media.duration || state.audioTimelineDuration || 1);
      setAudioTimelinePlaybackState(true);
      if (media === els.finalVideo) syncFinalCompareMedia(media);
    });
    media.addEventListener("pause", () => {
      syncAudioTimeline(media.currentTime, media.duration || state.audioTimelineDuration || 1);
      setAudioTimelinePlaybackState(false);
      if (media === els.finalVideo) syncFinalCompareMedia(media);
    });
    media.addEventListener("ended", () => setAudioTimelinePlaybackState(false));
  });
  els.manualTabs.addEventListener("click", (event) => {
    const button = event.target.closest(".tab");
    if (button) renderManual(state.project, button.dataset.tab);
  });
  els.manualNavigation?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-manual-nav-tab]");
    if (button) renderManual(state.project, button.dataset.manualNavTab);
  });
  els.manualBody.addEventListener("click", (event) => {
    const save = event.target.closest("[data-script-save]");
    const lock = event.target.closest("[data-script-lock]");
    const unlock = event.target.closest("[data-script-unlock]");
    if (save) saveDialogueDraft({ button: save });
    else if (lock) saveDialogueDraft({ lock: true, button: lock });
    else if (unlock) unlockDialogue();
  });
  els.drawerBackdrop.addEventListener("click", closeDrawer);
  document.addEventListener("click", (event) => {
    if (els.moreExportMenu && !event.target.closest(".more-export-trigger, #more-export-menu")) {
      els.moreExportMenu.classList.add("hidden");
      els.btnMoreExport?.setAttribute("aria-expanded", "false");
    }
    if (!drawerIsOpen() || event.target.closest("#drawer")) return;
    if (event.target.closest(".shot-card, .timeline-segment, .crew-card")) return;
    closeDrawer();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDrawer();
      closePremiere(false);
      closeExportSheet();
      return;
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      // 仅在镜头抽屉已打开时响应方向键，避免劫持文本框/滑杆的光标键。
      if (!els.drawer.classList.contains("open") || event.target.closest("textarea, input, select, [contenteditable=\"true\"]")) return;
      navigateShot(event.key === "ArrowLeft" ? -1 : 1);
    }
    if (
      event.key === "Enter"
      && currentView() === "studio"
      && document.activeElement !== els.idea
      && !state.busy
    ) startCreation();
  });
  updateIdeaCounter();
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
else init();
