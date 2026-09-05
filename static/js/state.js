/** Canonical frontend state helpers; the backend pipeline_state remains authoritative. */
export function createProjectState(project = null) {
  return { project, activeShot: null, busy: false, theme: "dark" };
}

export function canonicalProjectState(project) {
  return String(project?.pipeline_state?.state || "");
}

export function moduleState() {
  return { createProjectState, canonicalProjectState };
}

