/* ═══════════════════════════════════════════════════════════════
   Movie-Agent · AI 片场 — 交互层
   第一幕 开机 / 第二幕 剧组集结 / 第三幕 制片工作区
   ═══════════════════════════════════════════════════════════════ */

"use strict";

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
  duration: $("#duration"),
  tcValue: $("#tc-value"),
  styleCards: $("#style-cards"),
  btnStart: $("#btn-start"),
  modeNote: $("#mode-note"),
  librarySelect: $("#library-select"),
  btnLoad: $("#btn-load"),
  btnRefresh: $("#btn-refresh"),
  actCrew: $("#act-crew"),
  actWorkspace: $("#act-workspace"),
  crewPrimary: $("#crew-primary"),
  crewSecondary: $("#crew-secondary"),
  crewMeta: $("#crew-meta"),
  crewRadioWrap: $(".crew-radio-wrap"),
  crewRadioToggle: $("#crew-radio-toggle"),
  crewRadioSummary: $("#crew-radio-summary"),
  pipeline: $("#pipeline"),
  crewRadio: $("#crew-radio"),
  filmstrip: $("#filmstrip"),
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
  logFeed: $("#log-feed"),
  manualTabs: $("#manual-tabs"),
  manualBody: $("#manual-body"),
  manualSummary: $("#manual-summary"),
  activitySummary: $("#activity-summary"),
  activityBody: $("#activity-body"),
  screen: $("#screen"),
  finalVideo: $("#final-video"),
  posterTitle: $("#poster-title"),
  posterMeta: $("#poster-meta"),
  exportJson: $("#export-json"),
  exportMd: $("#export-md"),
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
  { id: "director", index: "01", name: "导演", en: "DIRECTOR", role: "主题与叙事边界", primary: true,
    summarize: (d) => d.brief && d.brief["主题"] ? `THEME / ${truncate(d.brief["主题"], 64)}` : "THEME / PROJECT BRIEF LOCKED" },
  { id: "writer", index: "02", name: "编剧", en: "WRITER", role: "剧本与旁白", primary: true,
    summarize: (d) => d.script && d.script.story ? `DRAFT / ${truncate(d.script.story, 66)}` : "DRAFT / SCREENPLAY LOCKED" },
  { id: "visual_bible", index: "03", name: "美术指导", en: "ART DIRECTOR", role: "角色 · 场景 · 风格 · 声音", primary: true,
    summarize: () => "VISUAL RULES / 4 continuity cards locked" },
  { id: "storyboard", index: "04", name: "分镜师", en: "STORYBOARD", role: "可渲染镜头拆解", primary: true,
    summarize: (d) => `SHOT LIST / ${(d.storyboard || []).length} shots locked` },
  { id: "quality", index: "05", name: "质检", en: "QC GATE", role: "结构与版权风险", primary: false,
    summarize: (d) => `QC GATE / ${(d.quality_report || []).length} checks complete` },
  { id: "generation", index: "06", name: "生成调度", en: "GENERATION", role: "逐镜生成与重试", primary: false,
    summarize: () => "SHOT QUEUE / render tasks ready" },
  { id: "editor", index: "07", name: "剪辑", en: "EDITOR", role: "合片成片", primary: false,
    summarize: (d) => (d.final_output ? "DELIVERY / master cut ready" : "DELIVERY / awaiting shot media") },
];

const AGENT_STATUS_COPY = {
  director: { idle: "WAITING", working: "DIRECTING", done: "DIRECTION LOCKED" },
  writer: { idle: "WAITING", working: "WRITING", done: "SCRIPT LOCKED" },
  visual_bible: { idle: "WAITING", working: "DESIGNING", done: "VISUAL LOCKED" },
  storyboard: { idle: "WAITING", working: "BOARDING", done: "STORYBOARD READY" },
  quality: { idle: "QUEUED", next: "NEXT · QC GATE", working: "REVIEWING", done: "QC APPROVED" },
  generation: { idle: "QUEUED", working: "RENDERING", done: "ASSETS READY" },
  editor: { idle: "QUEUED", working: "ASSEMBLING", done: "CUT COMPLETE" },
};

const SHOT_STATUS = {
  planned: "待拍",
  replanned: "已重排",
  generating_mock: "生成中",
  generating_comfyui: "生成中",
  generated_comfyui: "待质检",
  approved_mock: "已通过",
  approved_comfyui: "已通过",
  generation_failed: "失败",
};

const PROJECT_STATUS = {
  planned_mock: "策划完成（mock 文案）",
  planned_text_ai: "策划完成（AI 文案）",
  ready_for_comfyui_render: "待真实生成",
  generating_video_mock: "mock 生成中",
  rendering_comfyui: "真实生成中",
  render_failed: "生成中断（可续跑）",
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
  crewRadioOpen: false,
};

let manualTypingRun = 0;
let monitorTimecodeTimer = null;
let premiereTimer = null;
let projectorOscillator = null;
let projectorGain = null;
let faviconBlinkTimer = null;

/* ── 小工具 ────────────────────────────────────────────────── */

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function timecode(seconds) {
  const s = Math.max(0, Math.round(seconds));
  const hh = String(Math.floor(s / 3600)).padStart(2, "0");
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

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

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

function projectTitle(project = state.project) {
  return truncate((project && project.brief && project.brief["主题"]) || (project && project.idea) || "未命名短片", 28);
}

function setBrowserActivity(mode, project = state.project) {
  const projectId = project && project.project_id ? project.project_id : "Movie-Agent";
  document.title = mode === "render" ? `● RENDERING ${projectId}` : `Movie-Agent · ${projectTitle(project)}`;
  clearInterval(faviconBlinkTimer);
  const setFavicon = (dot) => {
    if (!els.favicon) return;
    els.favicon.href = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='6' fill='%230d0c0a'/%3E%3Ccircle cx='24' cy='8' r='4' fill='${dot}'/%3E%3Crect x='6' y='12' width='5' height='8' fill='%23e8a34c'/%3E%3Crect x='14' y='12' width='5' height='8' fill='%23e8a34c' opacity='.55'/%3E%3C/svg%3E`;
  };
  if (mode !== "render") {
    setFavicon("%23e8a34c");
    return;
  }
  let lit = true;
  setFavicon("%23e85a4f");
  faviconBlinkTimer = setInterval(() => {
    lit = !lit;
    setFavicon(lit ? "%23e85a4f" : "%23332a25");
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
  const delays = { project: 80, agent_start: 260, agent_done: 620, artifact: 360, chat: 280, shot_update: 110, archived: 120 };
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

function setPipeline(states) {
  const order = ["plan", "previs", "render", "deliver"];
  let activeAssigned = false;
  for (const key of order) {
    const el = els.pipeline.querySelector(`[data-step="${key}"]`);
    el.classList.remove("is-active", "is-done");
    if (states[key] === "done") {
      el.classList.add("is-done");
    } else if (!activeAssigned) {
      el.classList.add("is-active");
      activeAssigned = true;
    }
  }
}

function pipelineFromProject(project, hasVideo) {
  const states = { plan: "todo", previs: "todo", render: "todo", deliver: "todo" };
  if (!project) return states;
  states.plan = "done";
  if ((project.storyboard || []).length > 0) states.previs = "done";
  const anyApproved = (project.storyboard || []).some((shot) => String(shot.status || "").startsWith("approved"));
  const status = project.status || "";
  if (anyApproved || status.startsWith("completed")) states.render = "done";
  if (status === "completed_comfyui" && hasVideo) states.deliver = "done";
  return states;
}

/* ── 第二幕 · 剧组看板 ─────────────────────────────────────── */

function buildCrewBoard() {
  const render = (container, defs) => {
    container.innerHTML = "";
    defs.forEach((def, index) => {
      if (index > 0) {
        const arrow = document.createElement("span");
        arrow.className = "crew-arrow mono";
        arrow.innerHTML = "<i></i>";
        container.appendChild(arrow);
      }
      const card = document.createElement("div");
      card.className = "crew-card idle";
      card.dataset.agent = def.id;
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.setAttribute("aria-expanded", "false");
      card.setAttribute("aria-label", `${def.name} Agent 详情`);
      card.innerHTML = `
        <div class="crew-indexline mono"><span>${esc(def.index)} / NODE</span><span>${esc(def.en)}</span></div>
        <div class="crew-head"><span class="crew-name">${esc(def.name)}</span><span class="crew-en mono">${esc(def.role)}</span></div>
        <div class="crew-state mono"><span class="crew-state-icon" aria-hidden="true"></span><span class="crew-state-text">${AGENT_STATUS_COPY[def.id]?.idle || "WAITING"}</span></div>
        <p class="crew-summary"></p>`;
      card.addEventListener("click", () => openCrewDrawer(def.id));
      card.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openCrewDrawer(def.id);
        }
      });
      container.appendChild(card);
    });
  };
  render(els.crewPrimary, AGENT_DEFS.filter((d) => d.primary));
  render(els.crewSecondary, AGENT_DEFS.filter((d) => !d.primary));
  refreshCrewConnectors();
  renderCrewRadio();
}

function setAgentState(agentId, agentState, data) {
  const card = document.querySelector(`.crew-card[data-agent="${agentId}"]`);
  if (!card) return;
  card.classList.remove("idle", "next", "working", "done", "failed");
  card.classList.add(agentState);
  const text = card.querySelector(".crew-state-text");
  const summary = card.querySelector(".crew-summary");
  card.setAttribute("aria-expanded", "false");
  if (agentState === "working") {
    card.dataset.startedAt = String(Date.now());
    text.textContent = `${AGENT_STATUS_COPY[agentId]?.working || "WORKING"} · 00:00`;
    summary.innerHTML = '<span class="sk sk-1"></span><span class="sk sk-2"></span>';
  } else if (agentState === "done") {
    delete card.dataset.startedAt;
    text.textContent = AGENT_STATUS_COPY[agentId]?.done || "COMPLETE";
    const def = AGENT_DEFS.find((d) => d.id === agentId);
    const baseSummary = def ? def.summarize(data || {}) : "";
    card.dataset.summary = baseSummary;
    summary.textContent = baseSummary;
    renderCrewCardExtras(agentId);
    playUiSound("done");
  } else if (agentState === "next") {
    delete card.dataset.startedAt;
    text.textContent = AGENT_STATUS_COPY[agentId]?.next || "NEXT";
    summary.textContent = "UPSTREAM LOCKED / WAITING FOR THIS PASS";
  } else if (agentState === "failed") {
    delete card.dataset.startedAt;
    text.textContent = "INTERRUPTED";
    summary.textContent = "INTERRUPTED / RETRY AVAILABLE";
  } else {
    delete card.dataset.startedAt;
    text.textContent = AGENT_STATUS_COPY[agentId]?.idle || "WAITING";
    summary.textContent = "";
  }
  refreshCrewConnectors();
}

function refreshCrewConnectors() {
  for (const row of [els.crewPrimary, els.crewSecondary]) {
    const cards = Array.from(row.querySelectorAll(".crew-card"));
    const arrows = Array.from(row.querySelectorAll(".crew-arrow"));
    arrows.forEach((arrow, index) => {
      const previous = cards[index]?.classList;
      const next = cards[index + 1]?.classList;
      arrow.dataset.state = previous?.contains("done") && next?.contains("done") ? "done"
        : previous?.contains("working") || next?.contains("working") || next?.contains("next") ? "active" : "waiting";
    });
  }
  const bridge = document.querySelector(".crew-bridge");
  const board = document.querySelector('.crew-card[data-agent="storyboard"]');
  const qc = document.querySelector('.crew-card[data-agent="quality"]');
  if (bridge) bridge.dataset.state = board?.classList.contains("done") && (qc?.classList.contains("working") || qc?.classList.contains("next")) ? "active" : board?.classList.contains("done") ? "ready" : "waiting";
}

function rememberCrewEvent(agentId, event) {
  if (!agentId) return;
  state.crewDetails[agentId] = { ...(state.crewDetails[agentId] || {}), ...event };
}

function renderCrewCardExtras(agentId) {
  const card = document.querySelector(`.crew-card[data-agent="${agentId}"]`);
  if (!card) return;
  const latest = state.crewArtifacts.filter((item) => item.agent === agentId).at(-1);
  if (!latest) return;
  const summary = card.querySelector(".crew-summary");
  summary.innerHTML = `${esc(card.dataset.summary || "")}<span class="crew-artifact"><span class="artifact-title">${esc(latest.title)}</span><span class="artifact-content">${esc(truncate(latest.content, 110))}</span></span>`;
}

function appendCrewArtifact(event) {
  if (!event.agent || !event.content) return;
  state.crewArtifacts.push({
    agent: event.agent,
    title: event.title || "现场产出",
    content: event.content,
    time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  });
  rememberCrewEvent(event.agent, { artifacts: state.crewArtifacts.filter((item) => item.agent === event.agent) });
  renderCrewCardExtras(event.agent);
  renderCrewRadio();
}

function appendCrewMessage(event) {
  if (!event.message) return;
  state.crewMessages.push({
    from: event.from || "crew",
    to: event.to || "all",
    message: event.message,
    time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  });
  rememberCrewEvent(event.from, { messages: state.crewMessages.filter((item) => item.from === event.from) });
  renderCrewRadio();
}

function renderCrewRadio() {
  if (!els.crewRadio) return;
  els.crewRadio.innerHTML = "";
  const entries = [
    ...state.crewMessages.map((item) => ({ type: "chat", ...item })),
    ...state.crewArtifacts.map((item) => ({ type: "artifact", ...item })),
  ].slice(-18);
  if (!entries.length) {
    els.crewRadio.innerHTML = '<div class="radio-msg radio-system"><span class="radio-time">--:--:--</span><span class="radio-from">SYSTEM</span><span class="radio-to"> · STANDBY</span><br>Waiting for the first creative signal…</div>';
  } else {
    for (const item of entries) {
      const row = document.createElement("div");
      row.className = item.type === "chat" ? "radio-msg" : "radio-msg radio-artifact";
      row.innerHTML = item.type === "chat"
        ? `<span class="radio-time">${esc(item.time || "--:--:--")}</span><span class="radio-from">${esc(item.from)}</span><span class="radio-to"> → ${esc(item.to)}</span><br>${esc(item.message)}`
        : `<span class="radio-time">${esc(item.time || "--:--:--")}</span><span class="radio-from">✦ ${esc(item.title)}</span><span class="radio-to"> · ${esc(item.agent)}</span><br>${esc(truncate(item.content, 180))}`;
      els.crewRadio.appendChild(row);
    }
  }
  const latest = entries.at(-1);
  const latestLabel = latest
    ? latest.type === "chat" ? `${latest.from} → ${latest.to}` : `${latest.title || "NEW ARTIFACT"}`
    : "STANDBY";
  if (els.crewRadioSummary) {
    els.crewRadioSummary.textContent = `${entries.length} MESSAGES · ${truncate(latestLabel, 34).toUpperCase()}`;
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
  state.workingAgent = null;
}

function markAllAgentsDone(project) {
  state.workingAgent = null;
  const dataset = {
    brief: project.brief,
    script: project.script,
    visual_bible: project.visual_bible,
    storyboard: project.storyboard,
    quality_report: project.quality_report,
    final_output: project.final_output_placeholder,
  };
  for (const def of AGENT_DEFS) setAgentState(def.id, "done", dataset);
}

/* ── 第三幕 · 工作区渲染 ───────────────────────────────────── */

function shotStatusInfo(status) {
  return SHOT_STATUS[status] || status || "待拍";
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
    card.className = `shot-card${index >= entranceFrom ? " card-enter" : ""}`;
    card.dataset.shot = shot.number;
    card.dataset.status = shot.status || "planned";
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `镜头 ${shot.number} 详情`);
    card.innerHTML = `
      <header class="shot-head mono"><span>SHOT ${String(shot.number).padStart(2, "0")}</span><span>${shot.duration_seconds}s</span></header>
      <div class="shot-frame"><span class="film-stamp mono">${String(shot.number).padStart(2, "0")} · 24 FPS</span><span class="shot-framing">${esc(shot.framing)}</span><span class="shot-mode mono">${esc(shot.generation_mode)}</span></div>
      <footer class="shot-foot mono">
        <span class="shot-status"><i class="dot" aria-hidden="true"></i>${shotStatusInfo(shot.status)}</span>
        <span class="shot-attempts">${shot.attempts > 0 ? `↻${shot.attempts}` : ""}</span>
      </footer>`;
    card.addEventListener("click", () => openDrawer(project, shot.number));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openDrawer(project, shot.number);
      }
    });
    els.filmstrip.appendChild(card);
  }
  attachShotPreviews(project);
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
    segment.dataset.status = shot.status || "planned";
    segment.style.flexGrow = String(Math.max(1, shot.duration_seconds || 1));
    segment.title = `镜头 ${shot.number} · ${shot.duration_seconds} 秒 · ${shotStatusInfo(shot.status)}`;
    segment.setAttribute("aria-label", segment.title);
    segment.innerHTML = `<span>${String(shot.number).padStart(2, "0")}</span>`;
    segment.addEventListener("click", () => openDrawer(project, shot.number));
    els.editTimeline.appendChild(segment);
  }
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
      card.appendChild(video);
      const shotCard = card.closest(".shot-card");
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
  els.logFeed.textContent = (project.logs || []).join("\n");
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
  const approved = shots.filter((s) => String(s.status || "").startsWith("approved")).length;
  setMonitorTimecode(live);
  if (live) {
    els.monitorShot.textContent = `SHOT ${approved}/${shots.length}`;
    els.monitorPct.textContent = shots.length ? `${Math.round((approved / shots.length) * 100)}%` : "";
    els.monitorBar.style.width = shots.length ? `${(approved / shots.length) * 100}%` : "0%";
  } else {
    els.monitorShot.textContent = "STANDBY";
    els.monitorPct.textContent = "";
    els.monitorBar.style.width = "0%";
    els.monitorDesc.textContent = `${PROJECT_STATUS[project.status] || project.status} · ${shots.length} 个镜头，${approved} 个已通过。`;
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
  if (status.startsWith("completed")) return { key: "complete", symbol: "✓", label: "DELIVERED", copy: "成片已交付" };
  if (status.includes("render")) return { key: "active", symbol: "●", label: "RENDERING", copy: "正在生成" };
  if (shots.length >= 6 && (project?.quality_report || []).length) return { key: "complete", symbol: "✓", label: "READY FOR GENERATION", copy: "已通过策划质检" };
  if (shots.length) return { key: "active", symbol: "●", label: "BOARDING", copy: "分镜正在生长" };
  return { key: "active", symbol: "●", label: "PLANNING", copy: "剧组正在策划" };
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
  els.manualSummary.innerHTML = `
    <div class="manual-project-line">
      <div>
        <span class="manual-project-id mono">FILM ${esc(filmId)} / ${shots.length ? "CUT 01" : "PREP"}</span>
        <h3>${esc(projectTitle(project))}</h3>
      </div>
      <span class="manual-project-status ${status.key} mono"><i>${status.symbol}</i>${status.label}</span>
    </div>
    <div class="manual-stats" role="list" aria-label="项目摘要">
      <div role="listitem"><span class="mono">SHOTS</span><strong>${shots.length || "—"}</strong></div>
      <div role="listitem"><span class="mono">DURATION</span><strong>${shots.length ? compactDuration(total) : "—"}</strong></div>
      <div role="listitem"><span class="mono">FRAME</span><strong>16:9</strong></div>
      <div role="listitem"><span class="mono">STATUS</span><strong>${esc(status.copy)}</strong></div>
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
  const agentsDone = String(project.status || "").startsWith("completed") ? 7 : Math.min(7, assets + (project.final_output_placeholder ? 2 : 0));
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
  const value = String(status || "planned");
  if (["approved_mock", "approved_comfyui"].includes(value)) return { key: "complete", symbol: "✓", label: "COMPLETE" };
  if (["generating_mock", "generating_comfyui", "generated_comfyui"].includes(value)) return { key: "active", symbol: "●", label: "ACTIVE" };
  if (value === "generation_failed") return { key: "failed", symbol: "!", label: "FAILED" };
  return { key: "queued", symbol: "○", label: "QUEUED" };
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
  const promptReady = String(shot.prompt || "").trim().length >= 20;
  return [
    { label: "CHARACTER CONSISTENCY", status: failed ? "FAILED" : complete ? "COMPLETE" : "QUEUED", symbol: failed ? "!" : complete ? "✓" : "○" },
    { label: "SCENE CONSISTENCY", status: failed ? "FAILED" : complete ? "COMPLETE" : "QUEUED", symbol: failed ? "!" : complete ? "✓" : "○" },
    { label: "PROMPT INTEGRITY", status: promptReady ? "COMPLETE" : "QUEUED", symbol: promptReady ? "✓" : "○" },
    { label: "IP / COPYRIGHT CHECK", status: complete ? "COMPLETE" : "QUEUED", symbol: complete ? "✓" : "○" },
  ];
}

function renderBriefTab(project) {
  const entries = Object.entries(project.brief || {});
  const rows = [
    ["ORIGINAL IDEA", "原始创意", project.idea],
    ["TARGET DURATION", "目标时长", `${project.duration_seconds || "—"} 秒`],
    ["VISUAL STYLE", "视觉风格", project.visual_style],
    ...entries.map(([key, value]) => [manualFieldLabel(key), key, value]),
  ];
  const unique = rows.filter((row, index, list) => row[2] && list.findIndex((item) => item[1] === row[1]) === index);
  return `
    <section class="manual-intro">
      <span class="manual-section-kicker mono">DIRECTOR'S NOTE / 导演定调</span>
      <h3>先确定这部电影为何存在。</h3>
      <p class="manual-type">从创意、主题到叙事边界，导演 Agent 将每一个上游决定交给后续剧组。</p>
    </section>
    <div class="brief-sheet">${unique.map(([en, key, value]) => `
      <div class="brief-row"><span class="manual-label mono">${esc(en)}</span><span class="brief-key">${esc(key)}</span><p class="manual-type">${esc(value)}</p></div>`).join("") || '<p class="empty-note">暂无项目设定。</p>'}</div>`;
}

function renderScriptTab(project) {
  const story = String((project.script || {}).story || "").split(/\n+/).filter(Boolean);
  const narration = String((project.script || {}).narration || "").trim();
  return `
    <section class="screenplay-reader">
      <header class="screenplay-head mono"><span>SCREENPLAY / DRAFT 01</span><span>${story.length ? `${story.length} SCENES` : "AWAITING DRAFT"}</span></header>
      <div class="screenplay-body">${story.map((para, index) => `<p><span class="screenplay-line-no mono">${String(index + 1).padStart(2, "0")}</span><span class="manual-type">${esc(para)}</span></p>`).join("") || '<p class="empty-note">暂无剧本。</p>'}</div>
      ${narration ? `<aside class="screenplay-narration"><span class="manual-label mono">NARRATION / 旁白</span><p class="manual-type">${esc(narration)}</p></aside>` : ""}
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
      <span class="manual-section-kicker mono">ART DEPARTMENT / 美术部门</span>
      <h3>所有镜头共享同一套世界规则。</h3>
      <p class="manual-type">角色、场景、风格与声音被锁定为可复用的视觉连续性约束。</p>
    </section>
    <div class="visual-board">${entries.map(([key, value]) => `
      <section class="visual-spec"><header><span class="manual-label mono">${esc(manualFieldLabel(key))}</span><span class="visual-lock mono">LOCKED ✓</span></header><h4>${esc(key)}</h4><p class="manual-type">${esc(value)}</p></section>`).join("") || '<p class="empty-note">暂无视觉规范。</p>'}</div>
    <div class="visual-palette"><span class="manual-label mono">STUDIO PALETTE / 片场参考色</span><div>${palette.map(([label, color]) => `<span class="palette-chip"><i style="--chip:${color}"></i><b class="mono">${label}</b></span>`).join("")}</div></div>`;
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
      nav.push(`<div class="shot-scene-label mono">SCENE ${String(scene).padStart(2, "0")}</div>`);
    }
    const status = shotWorkflowState(shot.status);
    nav.push(`<button class="shot-nav-item${shot.number === active.number ? " is-active" : ""}" type="button" data-manual-shot="${shot.number}" aria-label="打开镜头 ${shot.number}"><span class="shot-nav-no mono">${String(shot.number).padStart(2, "0")}</span><span class="shot-nav-copy"><b>${esc(truncate(shot.image_description, 30))}</b><small class="mono">${esc(status.label)}</small></span><span class="shot-nav-duration mono">${shot.duration_seconds}s</span><span class="shot-nav-state ${status.key}" aria-label="${status.label}">${status.symbol}</span></button>`);
  }
  const qc = shotChecks(active);
  return `
    <div class="shot-sheet">
      <aside class="shot-nav"><header class="shot-nav-head"><span class="manual-label mono">SHOT LIST</span><span class="mono">${shots.length} SHOTS</span></header><div class="shot-nav-list">${nav.join("")}</div></aside>
      <article class="shot-detail">
        <header class="shot-detail-head"><div><span class="manual-section-kicker mono">SCENE ${String(shotSceneNumber(active.number, shots.length)).padStart(2, "0")} / SHOT ${String(active.number).padStart(2, "0")}</span><h3>镜头 ${String(active.number).padStart(2, "0")}</h3><p class="manual-type">${esc(active.image_description)}</p></div><span class="shot-detail-status ${activeState.key} mono"><i>${activeState.symbol}</i>${activeState.label}</span></header>
        <div class="shot-facts"><div><span class="manual-label mono">DURATION</span><strong>${active.duration_seconds}s</strong></div><div><span class="manual-label mono">FRAMING</span><strong>${esc(active.framing)}</strong></div><div><span class="manual-label mono">CAMERA</span><strong>${esc(shotCameraAngle(active))}</strong></div><div><span class="manual-label mono">MOVEMENT</span><strong>${esc(shotMovement(active))}</strong></div></div>
        <div class="shot-detail-grid"><section><span class="manual-label mono">ACTION / 动作</span><p class="manual-type">${esc(active.action)}</p></section><section><span class="manual-label mono">SOUND / 声音</span><p class="manual-type">${esc(active.sound_design)}</p></section></div>
        <section class="shot-prompt"><header><span class="manual-label mono">VISUAL PROMPT / 最终提示词</span><span class="mono">${esc(active.generation_mode)}</span></header><p class="manual-type">${esc(active.prompt)}</p></section>
        <section class="shot-qc"><header><span class="manual-label mono">QC GATE / 质检门</span><span class="mono">${active.attempts ? `TAKE ${active.attempts}` : "TAKE 01"}</span></header><div class="shot-qc-grid">${qc.map((item) => `<div class="shot-qc-item ${item.status === "COMPLETE" ? "complete" : item.status === "FAILED" ? "failed" : "queued"}"><i>${item.symbol}</i><span>${item.label}</span><b class="mono">${item.status}</b></div>`).join("")}</div></section>
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

async function renderScreening(project) {
  state.hasFinalVideo = false;
  els.screen.classList.remove("has-video");
  els.finalVideo.removeAttribute("src");
  els.posterTitle.textContent = truncate(
    (project.brief && (project.brief["主题"] || project.brief["原始创意"])) || project.idea,
    34
  );
  els.posterMeta.textContent = `${project.visual_style} · ${project.duration_seconds}S · ${project.project_id}`;
  // 只有真实生成完成的项目才探测成片文件；mock 模式不把占位路径当真实成片。
  if (project.status === "completed_comfyui") {
    try {
      const response = await fetch(`/api/projects/${project.project_id}/final-video`, { method: "HEAD" });
      if (response.ok) {
        state.hasFinalVideo = true;
        els.finalVideo.src = `/api/projects/${project.project_id}/final-video`;
        els.screen.classList.add("has-video");
      }
    } catch { /* offline / not generated */ }
  }
  updatePipelineForProject(project);
}

function renderDelivery(project) {
  const credits = [
    ["PROJECT", projectTitle(project)],
    ["DIRECTED BY", "DIRECTOR AGENT"],
    ["WRITTEN BY", "WRITER AGENT"],
    ["ART DIRECTION", "VISUAL BIBLE AGENT"],
    ["STORYBOARD", "STORYBOARD AGENT"],
    ["POST PRODUCTION", "GENERATION · QC · EDITOR"],
    ["DELIVERY", PROJECT_STATUS[project.status] || project.status],
  ];
  els.creditsRoll.innerHTML = credits
    .map(([heading, value]) => `<div class="cr-group"><p class="cr-head">${esc(heading)}</p><p class="cr-strong">${esc(value)}</p></div>`)
    .join("");
  els.exportJson.href = `/api/projects/${project.project_id}/export/json`;
  els.exportMd.href = `/api/projects/${project.project_id}/export/markdown`;
  // 字幕滚动只在新项目首次进入时触发，避免逐镜渲染/实时送达时反复重播。
  if (state.creditsProjectId !== project.project_id) {
    state.creditsProjectId = project.project_id;
    els.creditsRoll.classList.remove("is-rolling");
    void els.creditsRoll.offsetWidth;
    els.creditsRoll.classList.add("is-rolling");
  }
}

function updatePipelineForProject(project) {
  setPipeline(pipelineFromProject(project, state.hasFinalVideo));
}

function renderWorkspace(project, options = {}) {
  show(els.actWorkspace);
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
  if (videoMode === "comfyui") {
    els.btnRender.disabled = state.rendering;
    els.renderNote.textContent = "逐镜提交已验证的 MiniMax-H3 工作流；已通过质检的镜头会自动跳过，失败镜头按重试策略重新提交。";
  } else {
    els.btnRender.disabled = true;
    els.renderNote.textContent = "当前为 mock 视频流程：在 Spark 的 .env 设置 VIDEO_GENERATION_MODE=comfyui 后，这里会变成真实逐镜生成与 FFmpeg 合片。";
  }
}

function applyProjectSnapshot(project) {
  state.project = project;
  renderFilmstrip(project);
  renderTimeline(project);
  renderShotMap(project);
  renderLogFeed(project);
  renderManual(project, state.manualTab);
  renderDelivery(project);
  renderMonitor(project, state.rendering);
}

/* ── 镜头抽屉 ──────────────────────────────────────────────── */

function openDrawer(project, shotNumber) {
  const shot = (project.storyboard || []).find((s) => s.number === shotNumber);
  if (!shot) return;
  state.activeShotNumber = shotNumber;
  els.drawer.innerHTML = `
    <div class="drawer-head">
      <span class="drawer-title">镜头 ${String(shot.number).padStart(2, "0")}</span>
      <button class="drawer-close" type="button">✕ 关闭</button>
    </div>
    <span class="drawer-chip mono">${shotStatusInfo(shot.status)} · 尝试 ${shot.attempts} 次</span>
    <dl>
      <dt>时长</dt><dd>${shot.duration_seconds} 秒</dd>
      <dt>景别</dt><dd>${esc(shot.framing)}</dd>
      <dt>画面</dt><dd>${esc(shot.image_description)}</dd>
      <dt>动作</dt><dd>${esc(shot.action)}</dd>
      <dt>声音</dt><dd>${esc(shot.sound_design)}</dd>
      <dt>生成方式</dt><dd>${esc(shot.generation_mode)}</dd>
      <dt>输出</dt><dd class="mono" style="font-size:.72rem">${esc(shot.output_placeholder)}</dd>
    </dl>
    <div class="prompt-block">
      <h3>FINAL PROMPT</h3>
      <div class="prompt-box">${esc(shot.prompt)}<button class="prompt-copy" type="button">复制</button></div>
    </div>
    <div class="drawer-actions">
      <button class="ghost" type="button" id="drawer-regenerate">↻ 重新规划这个镜头</button>
    </div>`;
  els.drawer.querySelector(".drawer-close").addEventListener("click", closeDrawer);
  els.drawer.querySelector(".prompt-copy").addEventListener("click", async (event) => {
    try {
      await navigator.clipboard.writeText(shot.prompt);
      event.target.textContent = "已复制";
      setTimeout(() => { event.target.textContent = "复制"; }, 1600);
    } catch {
      toast("复制失败，请手动选择文本。", true);
    }
  });
  els.drawer.querySelector("#drawer-regenerate").addEventListener("click", () => regenerateShot(shot.number));
  if (["approved_comfyui", "generated_comfyui"].includes(shot.status)) {
    const url = `/api/projects/${project.project_id}/shots/${shot.number}/video`;
    fetch(url, { method: "HEAD" }).then((response) => {
      if (!response.ok) return;
      const video = document.createElement("video");
      video.src = url;
      video.controls = true;
      video.playsInline = true;
      els.drawer.appendChild(video);
    }).catch(() => {});
  }
  els.drawer.classList.add("open");
  els.drawerBackdrop.classList.remove("hidden");
  requestAnimationFrame(() => els.drawerBackdrop.classList.add("open"));
}

function closeDrawer() {
  els.drawer.classList.remove("open");
  els.drawerBackdrop.classList.remove("open");
  const expanded = document.querySelector('.crew-card[aria-expanded="true"]');
  if (expanded) expanded.setAttribute("aria-expanded", "false");
  setTimeout(() => els.drawerBackdrop.classList.add("hidden"), 260);
}

function crewAssetMarkup(title, value) {
  if (!value || (typeof value === "object" && !Object.keys(value).length)) return "";
  if (Array.isArray(value)) {
    return `<section class="crew-drawer-section"><h3>${esc(title)}</h3><ol class="crew-drawer-list">${value.map((item) => {
      if (typeof item === "string") return `<li>${esc(item)}</li>`;
      return `<li><strong>镜头 ${esc(item.number || "")}</strong> · ${esc(item.duration_seconds || "")} 秒 · ${esc(item.framing || "")} · ${esc(item.generation_mode || "")}<br>${esc(item.image_description || "")}<br><span class="drawer-muted">动作：${esc(item.action || "")} · 声音：${esc(item.sound_design || "")}<br>提示词：${esc(item.prompt || "")}</span></li>`;
    }).join("")}</ol></section>`;
  }
  if (typeof value === "object") {
    return `<section class="crew-drawer-section"><h3>${esc(title)}</h3><dl>${Object.entries(value).map(([key, item]) => `<dt>${esc(key)}</dt><dd>${esc(item)}</dd>`).join("")}</dl></section>`;
  }
  return `<section class="crew-drawer-section"><h3>${esc(title)}</h3><p>${esc(value)}</p></section>`;
}

function openCrewDrawer(agentId) {
  const def = AGENT_DEFS.find((item) => item.id === agentId);
  if (!def) return;
  const card = document.querySelector(`.crew-card[data-agent="${agentId}"]`);
  if (card) card.setAttribute("aria-expanded", "true");
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
    .map((item) => `<p class="crew-drawer-message"><span class="radio-time">${esc(item.time || "--:--:--")}</span><span class="radio-from">${esc(item.from)}</span><span class="radio-to"> → ${esc(item.to)}</span><br>${esc(item.message)}</p>`)
    .join("");
  const assetMarkup = agentId === "director" ? crewAssetMarkup("项目设定", asset.brief)
    : agentId === "writer" ? crewAssetMarkup("剧本与旁白", asset.script)
    : agentId === "visual_bible" ? crewAssetMarkup("视觉规范", asset.visual_bible)
    : agentId === "storyboard" ? crewAssetMarkup("分镜资产", asset.storyboard)
    : agentId === "quality" ? crewAssetMarkup("质检报告", asset.quality_report)
      : agentId === "generation" ? crewAssetMarkup("逐镜任务", project.storyboard)
        : agentId === "editor" ? crewAssetMarkup("交付结果", project.final_output_placeholder || "等待镜头素材")
            : `<section class="crew-drawer-section"><h3>任务说明</h3><p>${esc(def.role)}。${esc(card?.querySelector(".crew-summary")?.textContent || "等待上游素材。")}</p></section>`;
  els.drawer.innerHTML = `
    <div class="drawer-head"><span class="drawer-title">${esc(def.name)} Agent</span><button class="drawer-close" type="button">✕ 关闭</button></div>
    <span class="drawer-chip mono">${esc(def.en)} · ${esc(card?.querySelector(".crew-state-text")?.textContent || "候场")}</span>
    <p class="crew-drawer-intro">${esc(def.role)} · 点击卡片即可查看实时产出、沟通和决策记录。</p>
    ${assetMarkup || '<p class="empty-note">该成员还没有交付内容，正在等待上游信号。</p>'}
    ${artifactMarkup}
    ${messages ? `<section class="crew-drawer-section"><h3>现场沟通</h3>${messages}</section>` : ""}`;
  els.drawer.querySelector(".drawer-close").addEventListener("click", closeDrawer);
  els.drawer.classList.add("open");
  els.drawerBackdrop.classList.remove("hidden");
  requestAnimationFrame(() => els.drawerBackdrop.classList.add("open"));
}

/* ── 动作：创作 / 渲染 / 重新规划 ──────────────────────────── */

let storyboardStageRun = 0;

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
  state.project.logs.push(`${AGENT_DEFS.find((definition) => definition.id === agent)?.name || agent} Agent：创作资产已实时送达。`);
  // 集结期间就让第三幕工作区可见，页面随时可以往下翻看实时填充的面板。
  renderWorkspace(state.project, { tab: item[1], animateManual: true });
}

function handleCreateEvent(event) {
  if (event.type === "project") {
    state.project = createLiveProject(event);
    state.pendingProjectId = event.project_id;
    els.crewMeta.textContent = `LIVE · PROJECT ${String(event.project_id || "").replace(/^film-/, "").toUpperCase()}`;
    els.modeNote.textContent = `文案引擎：${event.text_mode === "modelscope" ? "ModelScope AI" : "mock"} · 视频引擎：${event.video_mode === "comfyui" ? "Spark 真实生成" : "mock 流程"}`;
  } else if (event.type === "agent_start") {
    state.workingAgent = event.agent;
    rememberCrewEvent(event.agent, { status: "working", startedAt: Date.now() });
    setAgentState(event.agent, "working");
  } else if (event.type === "agent_done") {
    state.workingAgent = null;
    rememberCrewEvent(event.agent, { status: "done", ...event });
    setAgentState(event.agent, "done", event);
    revealAsset(event.agent, event);
    if (event.agent === "storyboard") {
      state.project.logs.push("分镜师：开始逐张冲印镜头。 ");
      stageStoryboard(event.storyboard || []);
      setAgentState("quality", "next");
      setPipeline({ plan: "done", previs: "active" });
    }
  } else if (event.type === "artifact") {
    appendCrewArtifact(event);
  } else if (event.type === "chat") {
    appendCrewMessage(event);
  } else if (event.type === "shot_update") {
    const card = document.querySelector('.crew-card[data-agent="generation"] .crew-summary');
    if (card && event.shot) {
      card.textContent = `镜头 ${event.shot.number} · ${shotStatusInfo(event.shot.status)}`;
    }
  } else if (event.type === "done") {
    storyboardStageRun += 1;
    state.project = event.project;
    state.pendingProjectId = null;
    els.crewMeta.textContent = `LOCKED · PROJECT ${String(event.project?.project_id || "").replace(/^film-/, "").toUpperCase()}`;
    renderWorkspace(state.project, { entranceFrom: 0 });
    setBrowserActivity("idle", state.project);
    toast(`项目 ${state.project.project_id} 已完成并存档。`);
    setTimeout(() => els.actWorkspace.scrollIntoView({ behavior: "smooth", block: "start" }), 350);
  } else if (event.type === "error") {
    els.crewMeta.textContent = "INTERRUPTED · RETRY AVAILABLE";
    failWorkingAgent();
    toast(`创作失败：${event.message}`, true);
  }
}

async function startCreation() {
  if (state.busy) return;
  const idea = els.idea.value.trim();
  if (idea.length < 10) {
    toast("请输入至少 10 个字的原创科幻创意。", true);
    els.idea.focus();
    return;
  }
  state.busy = true;
  state.assemblyLocked = true;
  state.project = null;
  state.pendingProjectId = null;
  state.crewDetails = {};
  state.crewMessages = [];
  state.crewArtifacts = [];
  state.crewRadioOpen = false;
  state.hasFinalVideo = false;
  state.workingAgent = null;
  els.btnStart.disabled = true;
  els.btnStart.textContent = "🎬 拍摄中…";
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
    toast(`创作失败：${error.message}`, true);
    els.crewMeta.textContent = "INTERRUPTED · RETRY AVAILABLE";
    failWorkingAgent();
  } finally {
    state.busy = false;
    els.btnStart.disabled = false;
    els.btnStart.textContent = "🎬 开 机";
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
  } else if (event.type === "done") {
    state.project = event.project;
    applyProjectSnapshot(event.project);
    els.renderRec.classList.remove("live");
    renderMonitor(event.project, false);
    stopProjectorHum();
    setBrowserActivity("idle", event.project);
    renderScreening(event.project).then(() => openPremiere(event.project));
    renderManual(event.project);
    state.rendering = false;
    els.btnRender.disabled = false;
    els.btnRender.textContent = "提交 Spark 真实生成";
    toast("真实成片已生成，可在放映室预览。");
  } else if (event.type === "error") {
    els.renderRec.classList.remove("live");
    stopProjectorHum();
    setBrowserActivity("idle", state.project);
    state.rendering = false;
    els.btnRender.disabled = false;
    els.btnRender.textContent = "提交 Spark 真实生成";
    els.monitorDesc.textContent = `生成中断：${event.message}`;
    toast(`渲染失败：${event.message}`, true);
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
  }
}

async function regenerateShot(shotNumber) {
  if (!state.project) return;
  try {
    const response = await fetch(
      `/api/projects/${state.project.project_id}/shots/${shotNumber}/regenerate`,
      { method: "POST" }
    );
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
    state.project = payload;
    renderFilmstrip(payload);
    renderShotMap(payload);
    renderManual(payload);
    renderDelivery(payload);
    updatePipelineForProject(payload);
    toast(`镜头 ${shotNumber} 已重新规划。`);
    closeDrawer();
  } catch (error) {
    toast(`重新规划失败：${error.message}`, true);
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
    buildCrewBoard();
    markAllAgentsDone(payload);
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
    button.className = "style-card";
    button.textContent = style;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(style === state.selectedStyle));
    if (style === state.selectedStyle) button.classList.add("selected");
    button.addEventListener("click", () => {
      state.selectedStyle = style;
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
const views = { landing: els.viewLanding, studio: els.viewStudio };
let viewTransitioning = false;

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
    location.hash = name === "studio" ? "#/studio" : "#/";
    applyView(name);
    window.scrollTo(0, 0);
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
  let parallaxFrame = null;
  window.addEventListener("pointermove", (event) => {
    if (REDUCED_MOTION || currentView() !== "landing" || !hero) return;
    if (parallaxFrame) cancelAnimationFrame(parallaxFrame);
    parallaxFrame = requestAnimationFrame(() => {
      const x = ((event.clientX / window.innerWidth) - 0.5) * 10;
      const y = ((event.clientY / window.innerHeight) - 0.5) * 8;
      hero.style.setProperty("--aurora-x", `${x}px`);
      hero.style.setProperty("--aurora-y", `${y}px`);
    });
  });
}

/* 滚动摄影机：把页面滚动位置转成景深偏移与全局进度，低成本且可自然降级。 */
function initScrollMotion() {
  let frame = null;
  const update = () => {
    const viewport = window.innerHeight || 1;
    const pageLength = Math.max(1, document.documentElement.scrollHeight - viewport);
    const progress = Math.min(1, Math.max(0, window.scrollY / pageLength));
    document.documentElement.style.setProperty("--page-progress", progress.toFixed(3));
    const aurora = document.querySelector(".aurora");
    if (aurora) aurora.style.setProperty("--aurora-scroll", `${Math.min(110, window.scrollY * 0.08).toFixed(1)}px`);
    document.querySelectorAll(".panel, .feature-card, .crew-radio-wrap").forEach((element, index) => {
      const rect = element.getBoundingClientRect();
      const distance = (viewport * 0.5 - (rect.top + rect.height * 0.5)) / viewport;
      const shift = Math.max(-1, Math.min(1, distance)) * (index % 2 ? 4 : -4);
      element.style.setProperty("--depth-shift", `${shift.toFixed(1)}px`);
    });
    frame = null;
  };
  const requestUpdate = () => {
    if (frame === null) frame = requestAnimationFrame(update);
  };
  window.addEventListener("scroll", requestUpdate, { passive: true });
  window.addEventListener("resize", requestUpdate, { passive: true });
  requestUpdate();
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
    const text = state.health.text_mode === "modelscope" ? "ModelScope AI 文案" : "mock 文案";
    const video = state.health.video_mode === "comfyui" ? "Spark 真实视频" : "mock 视频流程";
    els.modeNote.textContent = `制作引擎就绪 · ${text} + ${video}`;
  } catch {
    els.modeNote.textContent = "无法连接后端服务。";
  }
}

function init() {
  applyView(currentView());
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
  els.btnStart.addEventListener("click", startCreation);
  els.btnLoad.addEventListener("click", loadSelectedProject);
  els.btnRefresh.addEventListener("click", refreshLibrary);
  els.btnRender.addEventListener("click", startRender);
  els.manualTabs.addEventListener("click", (event) => {
    const button = event.target.closest(".tab");
    if (button) renderManual(state.project, button.dataset.tab);
  });
  els.drawerBackdrop.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDrawer();
      closePremiere(false);
      return;
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      // 仅在镜头抽屉已打开时响应方向键，避免劫持文本框/滑杆的光标键。
      if (!els.drawer.classList.contains("open")) return;
      navigateShot(event.key === "ArrowLeft" ? -1 : 1);
    }
    if (
      event.key === "Enter"
      && currentView() === "studio"
      && document.activeElement !== els.idea
      && !state.busy
    ) startCreation();
  });
}

init();
