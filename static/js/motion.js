/** Small transform/opacity primitives used by semantic interactions. */
export const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
export const lerp = (from, to, amount) => from + (to - from) * clamp(amount);
export const springStep = (value, target, velocity = 0, stiffness = 0.16, damping = 0.78) => {
  const nextVelocity = (velocity + (target - value) * stiffness) * damping;
  return { value: value + nextVelocity, velocity: nextVelocity };
};
export const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;

export function moduleMotion() {
  return { clamp, lerp, springStep, reducedMotion };
}

