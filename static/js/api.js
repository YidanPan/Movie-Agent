/** Lightweight API seam for the zero-build console. */
export const projectPath = (projectId, suffix = "") =>
  `/api/projects/${encodeURIComponent(projectId)}${suffix}`;

export async function requestJSON(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

export function moduleApi() {
  return { projectPath, requestJSON };
}

