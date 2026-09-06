/** Film-strip helpers kept independent from DOM rendering. */
export const shotDuration = (shot = {}) => Math.max(0, Number(shot.duration_seconds || shot.desired_duration || 0));
export const shotReady = (shot = {}) => String(shot.status || "").startsWith("approved") && shot.stale !== true;
export const shotPreviewable = (shot = {}) => ["generated_comfyui", "awaiting_visual_review", "approved_comfyui"].includes(String(shot.status || "")) && shot.stale !== true;
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
  return { shotDuration, shotReady, shotPreviewable, shotCapabilities, reviewDomains, formatShotDuration, timingModeLabel, shotStateInfo };
}

