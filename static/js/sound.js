/** Sound-console semantics: four stable tracks, one source of truth. */
export const trackKeys = ["voice", "music", "sfx", "ambience"];
export const trackLabels = {
  voice: { zh: "旁白 / Dialogue", en: "VOICE" },
  music: { zh: "配乐 / Score", en: "MUSIC" },
  sfx: { zh: "动作音效 / Effects", en: "SFX" },
  ambience: { zh: "环境声 / Atmos", en: "AMBIENCE" },
};
export const audioModeLabels = { ai: "AI 自动配乐", library: "素材库音乐", upload: "用户上传音乐" };

export function audioTracksFor(project = {}) {
  const source = project.audio_tracks || {};
  return Object.fromEntries(trackKeys.map((key) => {
    const fallback = {
      key,
      label: trackLabels[key].en,
      name: trackLabels[key].zh,
      status: key === "voice" && project.script?.dialogue_locked ? "READY" : "DESIGN READY",
      source: key === "voice" ? "DIALOGUE BOOK" : "SOUND DESIGN PLAN",
      enabled: true,
      volume_db: key === "voice" ? -2 : key === "music" ? -14 : key === "sfx" ? -10 : -22,
      preview_url: null,
      can_regenerate: key !== "voice",
      pan: 0,
      ducking: key === "music",
    };
    return [key, { ...fallback, ...(source[key] || {}), key }];
  }));
}

export const audioModeFor = (project = {}) => ["ai", "library", "upload"].includes(project.music_mode) ? project.music_mode : "ai";
export const soundReady = (project = {}) => trackKeys.every((key) => {
  const track = project?.audio_tracks?.[key];
  return Boolean(track && track.enabled !== false && ["READY", "FILE READY", "DESIGN READY"].includes(String(track.status || "")));
});

export function moduleSound() {
  return { trackKeys, trackLabels, audioModeLabels, audioTracksFor, audioModeFor, soundReady };
}

