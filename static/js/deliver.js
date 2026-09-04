/** Deliver read helpers keep quality and final-state semantics explicit. */
export const isFinalReady = (project = {}) => String(project.status || "").startsWith("completed") && Boolean(project.final_output_placeholder || project.final_video_url);
export const qualityLabel = (record = {}) => String(record.quality || (record.width && record.height ? `${record.width}×${record.height}` : "QUALITY UNKNOWN"));

export function moduleDeliver() {
  return { isFinalReady, qualityLabel };
}

