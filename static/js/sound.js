/** Sound-console semantics: four stable tracks, one source of truth. */
export const trackKeys = ["voice", "music", "sfx", "ambience"];
export const soundReady = (project = {}) => trackKeys.every((key) => {
  const track = project?.audio_tracks?.[key];
  return Boolean(track && track.enabled !== false && ["READY", "FILE READY", "DESIGN READY"].includes(String(track.status || "")));
});

export function moduleSound() {
  return { trackKeys, soundReady };
}

