/** Film-strip helpers kept independent from DOM rendering. */
export const shotDuration = (shot = {}) => Math.max(0, Number(shot.duration_seconds || shot.desired_duration || 0));
export const shotReady = (shot = {}) => String(shot.status || "").startsWith("approved") && shot.stale !== true;
export const shotPreviewable = (shot = {}) => ["generated_comfyui", "awaiting_visual_review", "approved_comfyui"].includes(String(shot.status || "")) && shot.stale !== true;

const SCENE_AMBIENTS = [
  { test: /hospital|clinic|ward|fluorescent|medical|医院|病房|诊所/i, ambientRgb: "92 155 171", accentRgb: "109 194 204", intensity: 0.045, label: "COOL CYAN" },
  { test: /home|house|room|apartment|interior|warm|家|住宅|房间|室内/i, ambientRgb: "190 132 69", accentRgb: "220 171 88", intensity: 0.04, label: "WARM AMBER" },
  { test: /night|street|city|exterior|rain|夜|街|城市|雨/i, ambientRgb: "67 91 126", accentRgb: "126 151 190", intensity: 0.035, label: "NIGHT BLUE" },
];

const sceneEntity = (project = {}, sceneId = "") => {
  const scenes = project?.story_world?.scenes;
  if (Array.isArray(scenes)) return scenes.find((item) => String(item?.scene_id || item?.id || "") === String(sceneId)) || {};
  return scenes && typeof scenes === "object" ? scenes[sceneId] || {} : {};
};

const visualSceneEntity = (project = {}, sceneId = "") => {
  const scenes = project?.visual_bible?.scenes;
  if (Array.isArray(scenes)) return scenes.find((item) => String(item?.scene_id || item?.id || "") === String(sceneId)) || {};
  return scenes && typeof scenes === "object" ? scenes[sceneId] || {} : {};
};

const hexRgb = (value) => {
  const match = /^#([0-9a-f]{6})$/i.exec(String(value || "").trim());
  if (!match) return null;
  const hex = match[1];
  return `${parseInt(hex.slice(0, 2), 16)} ${parseInt(hex.slice(2, 4), 16)} ${parseInt(hex.slice(4, 6), 16)}`;
};

const paletteFromMachineData = (palette) => {
  if (!palette || typeof palette !== "object") return null;
  const dominant = hexRgb(palette.dominant);
  const accent = hexRgb(palette.accent);
  const luminance = Number(palette.luminance);
  const temperature = String(palette.temperature || "").toLowerCase();
  if (!dominant || !accent || !Number.isFinite(luminance) || luminance < 0 || luminance > 1 || !["warm", "neutral", "cool"].includes(temperature)) return null;
  return {
    ambientRgb: dominant,
    accentRgb: accent,
    intensity: Math.min(0.065, Math.max(0.018, 0.018 + (1 - luminance) * 0.045)),
    label: `${temperature.toUpperCase()} BIBLE PALETTE`,
  };
};

const paletteFromText = (value) => {
  const text = String(value || "");
  const hexes = text.match(/#[0-9a-f]{6}/gi) || [];
  if (hexes.length >= 2) {
    const dominant = hexRgb(hexes[0]);
    const accent = hexRgb(hexes[1]);
    if (dominant && accent) return { ambientRgb: dominant, accentRgb: accent, intensity: 0.032, label: "VISUAL BIBLE LOCK" };
  }
  return SCENE_AMBIENTS.find((item) => item.test.test(text)) || null;
};

export const sceneAmbientForShot = (shot = {}, project = {}) => {
  const sceneId = String(shot.scene_id || "").trim();
  const scene = sceneEntity(project, sceneId);
  const visualScene = visualSceneEntity(project, sceneId);
  const bible = project?.visual_bible || {};
  const explicitPalette = paletteFromMachineData(visualScene.ui_palette || visualScene.palette_tokens);
  const lockedPalette = paletteFromText(visualScene.palette_lock || visualScene.palette || "");
  const globalPalette = paletteFromText(bible.cinematography?.palette || bible.palette || bible.style_card || "");
  const keywordSource = [
    scene.name, scene.label, scene.role, scene.lighting, scene.lighting_lock,
    scene.palette, scene.palette_lock, visualScene.name, visualScene.label,
  ].filter(Boolean).join(" ");
  const match = explicitPalette || lockedPalette || globalPalette || SCENE_AMBIENTS.find((item) => item.test.test(keywordSource));
  return {
    sceneId,
    ambientRgb: match?.ambientRgb || "151 119 79",
    accentRgb: match?.accentRgb || "194 138 62",
    intensity: match?.intensity || 0.028,
    label: match?.label || "NEUTRAL TUNGSTEN",
  };
};

export function initFilmGateFocus(viewport, { reduced = false } = {}) {
  if (!viewport) return () => {};
  let frame = null;
  let disposed = false;
  const update = () => {
    frame = null;
    if (disposed) return;
    const cards = [...viewport.querySelectorAll(".shot-card")];
    if (!cards.length) return;
    const center = viewport.getBoundingClientRect().left + viewport.clientWidth / 2;
    for (const card of cards) {
      const rect = card.getBoundingClientRect();
      const distance = Math.abs(rect.left + rect.width / 2 - center);
      const proximity = Math.max(0, Math.min(1, 1 - distance / Math.max(1, viewport.clientWidth * 0.72)));
      card.style.setProperty("--film-gate-focus", proximity.toFixed(3));
      card.classList.toggle("is-gate-center", distance <= Math.max(12, rect.width * 0.22));
    }
  };
  const schedule = () => {
    if (frame === null) frame = requestAnimationFrame(update);
  };
  viewport.addEventListener("scroll", schedule, { passive: true });
  window.addEventListener("resize", schedule, { passive: true });
  schedule();
  return () => {
    disposed = true;
    if (frame !== null) cancelAnimationFrame(frame);
    viewport.removeEventListener("scroll", schedule);
    window.removeEventListener("resize", schedule);
  };
}

export const centerShotCard = (card, reduced = false) => {
  card?.scrollIntoView?.({ block: "nearest", inline: "center", behavior: reduced ? "auto" : "smooth" });
};
const REVIEW_FLAG_DOMAIN = {
  PLANNING: "planning",
  LOW_RELEVANCE_SHOT: "planning",
  SHOT_TOO_COMPLEX: "planning",
  STORY_REVIEW_REQUIRED: "planning",
  STYLE_DRIFT: "visual",
  CHARACTER_DRIFT: "visual",
  SCENE_DRIFT: "visual",
  PROP_DRIFT: "visual",
  NARRATIVE_STATE_DRIFT: "narrative",
  MANUAL_VISUAL_REVIEW: "visual",
  MEDIA_INTEGRITY_FAILED: "media",
  MISSING_CHARACTER_REFERENCE: "reference",
  MISSING_SCENE_REFERENCE: "reference",
  MISSING_PROP_REFERENCE: "reference",
  MISSING_PREVIOUS_ENDING_REFERENCE: "reference",
  MISSING_CHARACTER_LOCK: "reference",
  MISSING_SCENE_LOCK: "reference",
  MISSING_PROP_LOCK: "reference",
  SPEECH_OVERFLOW: "audio",
  SCRIPT_TIMING_REVIEW: "audio",
};

const REVIEW_DOMAIN_PRIORITY = ["media", "planning", "visual", "reference", "narrative", "audio"];

export const reviewDomains = (shot = {}, project = {}) => {
  const domains = { planning: [], visual: [], media: [], reference: [], narrative: [], audio: [] };
  const add = (flag, domain = REVIEW_FLAG_DOMAIN[flag]) => {
    if (!domain || !domains[domain]) return;
    const value = String(flag || "").toUpperCase();
    if (value && !domains[domain].includes(value)) domains[domain].push(value);
  };
  for (const flag of shot.qc_flags || []) add(flag);
  for (const flag of shot.context_flags || shot.qc_details?.context_flags || []) add(flag);
  for (const namespace of Object.keys(domains)) {
    for (const flag of shot.qc_details?.[namespace]?.flags || []) add(flag, namespace);
  }
  const overflow = shot.qc_details?.voice_timeline?.overflow || project?.script?.voice_timeline?.overflow || [];
  if (overflow.some((item) => Number(item?.shot || 0) === Number(shot.number))) add("SPEECH_OVERFLOW", "audio");
  if (shot.status === "awaiting_visual_review" && !domains.visual.length) add("MANUAL_VISUAL_REVIEW", "visual");
  const primaryReviewDomain = REVIEW_DOMAIN_PRIORITY.find((domain) => domains[domain].length) || null;
  const primaryAttentionReason = primaryReviewDomain ? domains[primaryReviewDomain][0] : null;
  return { ...domains, primaryReviewDomain, primaryAttentionReason };
};

export const shotCapabilities = (shot = {}, project = {}) => {
  const status = String(shot.status || "planned");
  const qcStatus = String(shot.qc_status || "").toUpperCase();
  const flags = Array.isArray(shot.qc_flags) ? shot.qc_flags : [];
  const hasLastError = shot.last_error && typeof shot.last_error === "object"
    ? Object.keys(shot.last_error).length > 0
    : Boolean(shot.last_error);
  const isStale = shot.stale === true || qcStatus.includes("STALE");
  const isGenerating = status === "generating_mock" || status === "generating_comfyui";
  const isFailed = status === "generation_failed" || hasLastError;
  const review = reviewDomains(shot, project);
  const needsReview = status === "awaiting_visual_review"
    || qcStatus === "AWAITING_VISUAL_REVIEW"
    || Object.values(review).some((value) => Array.isArray(value) && value.length);
  const isReady = shotReady(shot);
  const canPreview = shotPreviewable(shot);
  return {
    canPreview,
    canApprove: canPreview && status === "awaiting_visual_review" && !isGenerating && review.primaryReviewDomain === "visual",
    canApproveVisual: canPreview && status === "awaiting_visual_review" && !isGenerating && review.primaryReviewDomain === "visual",
    canApprovePlanning: review.primaryReviewDomain === "planning",
    canResolveReference: review.primaryReviewDomain === "reference",
    canFixTiming: review.primaryReviewDomain === "audio",
    canRegenerate: !isGenerating,
    canReplan: !isGenerating,
    canEditMetadata: !isGenerating,
    canEnterCut: isReady,
    needsReview,
    reviewDomains: review,
    primaryReviewDomain: review.primaryReviewDomain,
    primaryAttentionReason: review.primaryAttentionReason,
    isGenerating,
    isFailed,
    isStale,
    isReady,
  };
};

export const formatShotDuration = (value) => {
  const seconds = Math.max(0, Number(value || 0));
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${(seconds % 60).toFixed(1).padStart(4, "0")}`;
};

export const timingModeLabel = (shot = {}) => {
  const mode = String(shot.timing_mode || "native").toLowerCase();
  return ({ native: "NATIVE", trim: "TRIM", extend: "EXTEND", hold_last_frame: "HOLD", slow_motion: "SLOW" })[mode] || mode.toUpperCase();
};

export const shotStateInfo = (shot = {}, project = {}) => {
  const status = String(shot.status || "planned");
  const qcStatus = String(shot.qc_status || "").toUpperCase();
  const flags = Array.isArray(shot.qc_flags) ? shot.qc_flags : [];
  const driftDetails = shot.qc_details?.drift_details || {};
  const driftFlags = [...flags, ...Object.keys(driftDetails)].map((flag) => String(flag).toUpperCase());
  const hasLastError = shot.last_error && typeof shot.last_error === "object" ? Object.keys(shot.last_error).length > 0 : Boolean(shot.last_error);
  if (shot.stale === true || qcStatus.includes("STALE")) return { key: "stale", symbol: "↻", label: "STALE" };
  if (status === "generation_failed" || hasLastError) return { key: "failed", symbol: "×", label: "FAILED" };
  const domain = reviewDomains(shot, project).primaryReviewDomain;
  if (status === "awaiting_visual_review" || qcStatus === "AWAITING_VISUAL_REVIEW" || domain || flags.some((flag) => String(flag).toUpperCase().includes("REVIEW"))) {
    const label = domain === "planning" ? "STORY REVIEW" : domain === "reference" ? "REFERENCE REVIEW" : domain === "media" ? "MEDIA REVIEW" : domain === "audio" ? "AUDIO TIMING REVIEW" : driftFlags.some((flag) => flag.includes("CHARACTER")) ? "CHARACTER REVIEW" : driftFlags.some((flag) => flag.includes("SCENE")) ? "SCENE REVIEW" : driftFlags.some((flag) => flag.includes("STYLE")) ? "STYLE REVIEW" : "VISUAL REVIEW";
    return { key: "review", symbol: "!", label };
  }
  if (["approved_mock", "approved_comfyui"].includes(status)) return { key: "complete", symbol: "✓", label: "QC PASS" };
  if (["generating_mock", "generating_comfyui", "generated_comfyui"].includes(status)) return { key: "active", symbol: "●", label: "ACTIVE" };
  return { key: "queued", symbol: "○", label: "QUEUED" };
};

export function moduleStoryboard() {
  return { shotDuration, shotReady, shotPreviewable, shotCapabilities, reviewDomains, formatShotDuration, timingModeLabel, shotStateInfo, sceneAmbientForShot, initFilmGateFocus, centerShotCard };
}

