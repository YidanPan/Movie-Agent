/** Small transform/opacity primitives used by semantic interactions. */
export const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
export const lerp = (from, to, amount) => from + (to - from) * clamp(amount);
export const springStep = (value, target, velocity = 0, stiffness = 0.16, damping = 0.78) => {
  const nextVelocity = (velocity + (target - value) * stiffness) * damping;
  return { value: value + nextVelocity, velocity: nextVelocity };
};
export const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
export const coarsePointer = () => window.matchMedia?.("(hover: none), (pointer: coarse)").matches === true;

export const MOTION_TOKENS = Object.freeze({
  fast: 160,
  control: 220,
  panel: 320,
  sharedFrame: 420,
  cinematic: 720,
  premiere: 1100,
});

export function triggerDarkroomDevelopment(element, { key = "", duration = MOTION_TOKENS.cinematic } = {}) {
  if (!element) return false;
  const token = String(key || element.dataset.darkroomKey || "darkroom");
  if (element.dataset.darkroomKey === token && element.classList.contains("has-darkroom-developed")) return false;
  element.dataset.darkroomKey = token;
  element.classList.remove("has-darkroom-developed", "is-darkroom-developing");
  if (reducedMotion()) {
    element.classList.add("has-darkroom-developed");
    return true;
  }
  void element.offsetWidth;
  element.classList.add("is-darkroom-developing");
  window.setTimeout(() => {
    if (element.dataset.darkroomKey !== token) return;
    element.classList.remove("is-darkroom-developing");
    element.classList.add("has-darkroom-developed");
  }, duration);
  return true;
}

export function runSharedFrameTransition(source, update, { name = "shot-frame" } = {}) {
  let targetForCleanup = null;
  const commit = () => {
    targetForCleanup = update?.();
    if (targetForCleanup?.style) targetForCleanup.style.viewTransitionName = name;
    return targetForCleanup;
  };
  if (!source || reducedMotion()) return commit();
  source.style.viewTransitionName = name;
  if (typeof document.startViewTransition === "function") {
    const transition = document.startViewTransition(commit);
    transition.finished?.finally?.(() => {
      source.style.viewTransitionName = "none";
      if (targetForCleanup?.style) targetForCleanup.style.viewTransitionName = "none";
    });
    return transition;
  }
  source.classList.add("is-frame-source");
  const target = commit();
  window.setTimeout(() => {
    source.classList.remove("is-frame-source");
    source.style.viewTransitionName = "none";
    if (target?.style) target.style.viewTransitionName = "none";
  }, MOTION_TOKENS.sharedFrame);
  return target;
}

export function moduleMotion() {
  return { clamp, lerp, springStep, reducedMotion, coarsePointer, MOTION_TOKENS, triggerDarkroomDevelopment, runSharedFrameTransition };
}

