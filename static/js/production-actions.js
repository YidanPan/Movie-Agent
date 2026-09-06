const LEGACY_ACTION_ALIASES = { REGENERATE_SHOT: "RENDER_SHOT" };

export const PRODUCTION_ACTIONS = {
  START_RENDER: { label: "START RENDER" },
  RENDER_SHOT: { label: "RENDER SHOT" },
  REPLAN_SHOT: { label: "REPLAN SHOT" },
  START_AI_EDIT: { label: "START AI EDIT" },
  APPROVE_FINAL_CUT: { label: "APPROVE FINAL CUT" },
  GENERATE_FINAL_MASTER: { label: "GENERATE FINAL MASTER" },
  EXPORT: { label: "EXPORT" },
  APPROVE_PREVIS: { label: "APPROVE PREVIS" },
  REPLAN_STORYBOARD: { label: "REVIEW STORYBOARD" },
  REPLAN_STORY_WORLD: { label: "REVIEW STORY WORLD" },
  REVIEW_VISUAL_BIBLE: { label: "OPEN VISUAL BIBLE" },
  OPEN_REFERENCE_BANK: { label: "OPEN REFERENCES" },
  REVIEW_SHOT: { label: "REVIEW SHOT" },
  REVIEW_AUDIO_TIMELINE: { label: "OPEN AUDIO" },
  OPEN_SOUND: { label: "OPEN SOUND" },
  OPEN_RENDER_DIAGNOSTICS: { label: "OPEN RENDER" },
  REVIEW_RENDER_DIAGNOSTICS: { label: "OPEN RENDER" },
  LOCK_DIALOGUE: { label: "LOCK DIALOGUE" },
  VERIFY_FINAL_MASTER: { label: "VERIFY MASTER" },
  REVIEW_DELIVERY_PREFLIGHT: { label: "REVIEW DELIVERY" },
};

const canonicalAction = (action) => LEGACY_ACTION_ALIASES[String(action || "").toUpperCase()] || String(action || "").toUpperCase();

const scrollTo = (element, reduced = false) => element?.scrollIntoView?.({
  behavior: reduced ? "auto" : "smooth",
  block: "center",
});

export function productionActionLabel(action) {
  const code = canonicalAction(action);
  return PRODUCTION_ACTIONS[code]?.label || "ACTION UNAVAILABLE";
}

export async function executeProductionAction(action, context = {}) {
  const requested = String(action || "").toUpperCase();
  const code = canonicalAction(requested);
  if (!PRODUCTION_ACTIONS[code]) {
    console.warn(`[production-actions] Unknown action: ${requested}`);
    context.onUnavailable?.(requested);
    return false;
  }
  const handlers = context.handlers || {};
  const handler = handlers[code];
  if (typeof handler !== "function") {
    console.warn(`[production-actions] No handler registered for: ${code}`);
    context.onUnavailable?.(code);
    return false;
  }
  await handler(context);
  return true;
}

export function moduleProductionActions() {
  return { PRODUCTION_ACTIONS, canonicalAction, productionActionLabel, executeProductionAction };
}

export { scrollTo };
