/** Canonical frontend state helpers; the backend pipeline_state remains authoritative. */
export function createProjectState(project = null) {
  return { project, activeShot: null, busy: false, theme: "dark" };
}

export function canonicalProjectState(project) {
  return String(project?.pipeline_state?.state || "");
}

export function pipelineFromProject(project, hasVideo = false, historical = false, shotReady = () => false) {
  const states = { plan: "todo", previs: "todo", render: "todo", deliver: "todo" };
  if (!project) return states;
  const canonical = canonicalProjectState(project);
  if (canonical) {
    const backendPipeline = project.pipeline_state?.pipeline || {};
    for (const key of Object.keys(states)) {
      const value = backendPipeline[key];
      if (["todo", "active", "ready", "review", "failed", "stale", "done", "archived"].includes(value)) states[key] = value;
    }
    if (canonical === "final_ready" && hasVideo) states.deliver = "done";
    return states;
  }
  states.plan = "done";
  if ((project.storyboard || []).length > 0) states.previs = "done";
  const status = project.status || "";
  const shots = project.storyboard || [];
  const allReady = shots.length > 0 && shots.every(shotReady);
  const finalApproved = status.startsWith("completed") && hasVideo;
  if (["rendering_comfyui", "generating_video_mock", "ready_for_comfyui_render"].includes(status)) states.render = "active";
  else if (status === "render_failed") states.render = "failed";
  else if (historical && ["planned_mock", "planned_text_ai"].includes(status)) states.render = "ready";
  else if (allReady || status.startsWith("editing_") || status === "rough_cut_ready" || finalApproved) states.render = "done";
  if (finalApproved) states.deliver = "done";
  else if (status === "ready_for_ai_edit") states.deliver = historical ? "ready" : "active";
  else if (allReady || status === "editing_rough_cut" || status === "rough_cut_ready") states.deliver = "active";
  if (historical && status.startsWith("completed") && !finalApproved) states.deliver = "archived";
  return states;
}

export function moduleState() {
  return { createProjectState, canonicalProjectState, pipelineFromProject };
}

