/** Deliver read helpers keep quality and final-state semantics explicit. */
export const isFinalReady = (project = {}) => String(project.status || "").startsWith("completed") && Boolean(project.final_output_placeholder || project.final_video_url);
export const qualityLabel = (record = {}) => String(record.quality || (record.width && record.height ? `${record.width}×${record.height}` : "QUALITY UNKNOWN"));
export const deliverRuntime = (project = {}) => {
  const seconds = (project.storyboard || []).reduce((sum, shot) => sum + Number(shot.duration_seconds || 0), 0);
  return seconds || Number(project.duration_seconds || 0) || 0;
};
export const finalVideoCandidate = (project = {}) => project.screening_preview_url || project.final_video_url || `/api/projects/${encodeURIComponent(project.project_id || "")}/screening-preview`;
export const deliverStatus = (project = {}, hasFinalVideo = false) => {
  const status = String(project.status || "");
  const canonical = String(project?.pipeline_state?.state || "");
  if (canonical === "editing" || status === "editing_rough_cut") return { key: "editing", badge: "AI EDITING", title: "AI 剪辑正在组装", copy: "镜头、声音与字幕正在进入粗剪时间线。" };
  if (canonical === "rough_cut_ready" || status === "rough_cut_ready") return { key: "rough", badge: "ROUGH CUT READY", title: "粗剪已完成，等待审片", copy: "先预览 Rough Cut，再决定是否批准最终成片。" };
  if (canonical === "shots_ready" || status === "ready_for_ai_edit") return { key: "ready", badge: "SHOTS READY", title: "AI Edit 已就绪", copy: "全部镜头通过质检；先选择声音设计，再启动 Rough Cut。" };
  if (status.startsWith("completed")) {
    return hasFinalVideo
      ? { key: "complete", badge: "FINAL CUT READY", title: "最终成片已完成", copy: "放映室已就绪：审片、跳转镜头并导出交付版本。" }
      : { key: "missing", badge: "DELIVERY RECORDED", title: "FINAL CUT NOT GENERATED", copy: "交付记录已保存，但后端尚未提供可播放的最终视频文件。" };
  }
  return { key: "unedited", badge: "NOT EDITED", title: "FINAL CUT NOT GENERATED", copy: "镜头已就绪，下一步由 AI Edit 生成可审阅的 Rough Cut。" };
};

export function moduleDeliver() {
  return { isFinalReady, qualityLabel, deliverRuntime, finalVideoCandidate, deliverStatus };
}

