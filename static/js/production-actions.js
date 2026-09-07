const LEGACY_ACTION_ALIASES = {
  REGENERATE_SHOT: "RENDER_SHOT",
  REGENERATE_AUDIO_TRACK: "REPLAN_AUDIO_TRACK",
  REPLAN_STORYBOARD: "REVIEW_STORYBOARD",
  REPLAN_STORY_WORLD: "REVIEW_STORY_WORLD",
};
const SUPPORTED_SCHEMA_VERSION = 3;

// Fallback labels are presentation-only compatibility data for snapshots
// produced before production_action_contract existed. Scope, kind, and
// confirmation policy never live in this module.
const ACTION_FALLBACK_LABELS = {
  START_RENDER: "START RENDER",
  RENDER_SHOT: "RENDER SHOT",
  REPLAN_SHOT: "REPLAN SHOT",
  START_AI_EDIT: "START AI EDIT",
  APPROVE_FINAL_CUT: "APPROVE FINAL CUT",
  GENERATE_FINAL_MASTER: "GENERATE FINAL MASTER",
  APPLY_FINAL_LOOK: "APPLY FINAL LOOK",
  EXPORT: "EXPORT",
  APPROVE_PREVIS: "APPROVE PREVIS",
  REVIEW_STORYBOARD: "REVIEW STORYBOARD",
  REVIEW_STORY_WORLD: "REVIEW STORY WORLD",
  REVIEW_VISUAL_BIBLE: "OPEN VISUAL BIBLE",
  OPEN_REFERENCE_BANK: "OPEN REFERENCES",
  REVIEW_SHOT: "REVIEW SHOT",
  REVIEW_AUDIO_TIMELINE: "OPEN AUDIO",
  OPEN_SOUND: "OPEN SOUND",
  OPEN_RENDER_DIAGNOSTICS: "OPEN RENDER",
  REVIEW_RENDER_DIAGNOSTICS: "OPEN RENDER",
  LOCK_DIALOGUE: "LOCK DIALOGUE",
  VERIFY_FINAL_MASTER: "VERIFY MASTER",
  REVIEW_DELIVERY_PREFLIGHT: "REVIEW DELIVERY",
  REPLAN_AUDIO_TRACK: "REPLAN TRACK",
  RENDER_AUDIO_TRACK: "RENDER TRACK",
  REVIEW_AUDIO_TRACK: "REVIEW TRACK",
};

const ACTION_HANDLERS = Object.create(null);

export const canonicalAction = (action) => LEGACY_ACTION_ALIASES[String(action || "").toUpperCase()] || String(action || "").toUpperCase();

const contractFor = (project) => project?.production_action_contract || null;

const supportedContract = (project, { warn = true } = {}) => {
  const contract = contractFor(project);
  if (!contract) return null;
  if (Number(contract.schema_version) !== SUPPORTED_SCHEMA_VERSION) {
    if (warn) console.warn(`ACTION CONTRACT VERSION UNSUPPORTED · ${contract.schema_version}`);
    return { unsupported: true, actions: {} };
  }
  return contract;
};

export function productionActionLabel(action, project = null) {
  const code = canonicalAction(action);
  const contract = supportedContract(project);
  if (contract?.unsupported) return "ACTION UNAVAILABLE";
  return contract?.actions?.[code]?.label || ACTION_FALLBACK_LABELS[code] || "ACTION UNAVAILABLE";
}

export function registerProductionActionHandlers(handlers = {}) {
  Object.keys(ACTION_HANDLERS).forEach((key) => delete ACTION_HANDLERS[key]);
  Object.entries(handlers).forEach(([action, handler]) => {
    if (typeof handler === "function") ACTION_HANDLERS[canonicalAction(action)] = handler;
  });
  return Object.keys(ACTION_HANDLERS);
}

export function validateProductionActionCoverage(project) {
  const contract = supportedContract(project);
  if (!contract) return { supported: true, missing: [] };
  if (contract.unsupported) {
    console.error("ACTION CONTRACT VERSION UNSUPPORTED");
    return { supported: false, missing: [] };
  }
  const missing = Object.entries(contract.actions || {})
    .filter(([, metadata]) => metadata?.kind)
    .map(([action]) => action)
    .filter((action) => !ACTION_HANDLERS[canonicalAction(action)]);
  if (missing.length) console.error("ACTION HANDLER COVERAGE MISSING", missing);
  return { supported: true, missing };
}

export async function requestProductionConfirmation(action, context = {}) {
  const metadata = context.metadata || {};
  if (typeof context.requestConfirmation !== "function") return false;
  return Boolean(await context.requestConfirmation({
    action: canonicalAction(action),
    metadata,
    project: context.project || null,
  }));
}

export async function executeProductionAction(action, context = {}) {
  const requested = String(action || "").toUpperCase();
  const code = canonicalAction(requested);
  const contract = supportedContract(context.project);
  if (contract?.unsupported || (contract && !contract.actions?.[code])) {
    console.warn(`[production-actions] Action unavailable: ${requested}`);
    context.onUnavailable?.(requested);
    return false;
  }
  const handler = ACTION_HANDLERS[code] || context.handlers?.[code];
  if (typeof handler !== "function") {
    console.warn(`[production-actions] No handler registered for: ${code}`);
    context.onUnavailable?.(code);
    return false;
  }
  const metadata = contract?.actions?.[code] || {};
  if (metadata.requires_confirmation && metadata.confirmation_mode !== "sheet") {
    const confirmed = await requestProductionConfirmation(code, { ...context, metadata });
    if (!confirmed) return false;
  }
  await handler(context);
  return true;
}

const scrollTo = (element, reduced = false) => element?.scrollIntoView?.({
  behavior: reduced ? "auto" : "smooth",
  block: "center",
});

export function moduleProductionActions() {
  return {
    canonicalAction,
    productionActionLabel,
    registerProductionActionHandlers,
    validateProductionActionCoverage,
    requestProductionConfirmation,
    executeProductionAction,
    scrollTo,
  };
}
