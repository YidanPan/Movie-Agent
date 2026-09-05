/** Film-strip helpers kept independent from DOM rendering. */
export const shotDuration = (shot = {}) => Math.max(0, Number(shot.duration_seconds || shot.desired_duration || 0));
export const shotReady = (shot = {}) => String(shot.status || "").startsWith("approved") && shot.stale !== true;

export const formatShotDuration = (value) => {
  const seconds = Math.max(0, Number(value || 0));
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${(seconds % 60).toFixed(1).padStart(4, "0")}`;
};

export const timingModeLabel = (shot = {}) => {
  const mode = String(shot.timing_mode || "native").toLowerCase();
  return ({ native: "NATIVE", trim: "TRIM", extend: "EXTEND", hold_last_frame: "HOLD", slow_motion: "SLOW" })[mode] || mode.toUpperCase();
};

export const shotStateInfo = (shot = {}) => {
  const status = String(shot.status || "planned");
  const qcStatus = String(shot.qc_status || "").toUpperCase();
  const flags = Array.isArray(shot.qc_flags) ? shot.qc_flags : [];
  const driftDetails = shot.qc_details?.drift_details || {};
  const driftFlags = [...flags, ...Object.keys(driftDetails)].map((flag) => String(flag).toUpperCase());
  const hasLastError = shot.last_error && typeof shot.last_error === "object" ? Object.keys(shot.last_error).length > 0 : Boolean(shot.last_error);
  if (shot.stale === true || qcStatus.includes("STALE")) return { key: "stale", symbol: "↻", label: "STALE" };
  if (status === "generation_failed" || hasLastError) return { key: "failed", symbol: "×", label: "FAILED" };
  if (status === "awaiting_visual_review" || qcStatus === "AWAITING_VISUAL_REVIEW" || flags.some((flag) => String(flag).toUpperCase().includes("REVIEW"))) {
    const label = driftFlags.some((flag) => flag.includes("CHARACTER")) ? "CHARACTER REVIEW" : driftFlags.some((flag) => flag.includes("SCENE")) ? "SCENE REVIEW" : driftFlags.some((flag) => flag.includes("STYLE")) ? "STYLE REVIEW" : "VISUAL REVIEW";
    return { key: "review", symbol: "!", label };
  }
  if (["approved_mock", "approved_comfyui"].includes(status)) return { key: "complete", symbol: "✓", label: "QC PASS" };
  if (["generating_mock", "generating_comfyui", "generated_comfyui"].includes(status)) return { key: "active", symbol: "●", label: "ACTIVE" };
  return { key: "queued", symbol: "○", label: "QUEUED" };
};

export function moduleStoryboard() {
  return { shotDuration, shotReady, formatShotDuration, timingModeLabel, shotStateInfo };
}

