/** Film-strip helpers kept independent from DOM rendering. */
export const shotDuration = (shot = {}) => Math.max(0, Number(shot.duration_seconds || shot.desired_duration || 0));
export const shotReady = (shot = {}) => String(shot.status || "").startsWith("approved") && shot.stale !== true;

export function moduleStoryboard() {
  return { shotDuration, shotReady };
}

