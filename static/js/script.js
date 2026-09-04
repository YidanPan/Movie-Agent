/** Dialogue and subtitle projection helpers. */
export const dialogueLocked = (project = {}) => project?.script?.dialogue_locked === true;
export const subtitleCueCount = (project = {}) => Array.isArray(project?.script?.subtitle_track) ? project.script.subtitle_track.length : 0;

export function moduleScript() {
  return { dialogueLocked, subtitleCueCount };
}

