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
      can_replan: key !== "voice",
      can_render: key === "music" || key === "voice",
      pan: 0,
      ducking: key === "music",
    };
    const actionReadiness = project?.readiness?.track_actions?.[key] || {};
    const replanReady = actionReadiness.REPLAN_AUDIO_TRACK
      ? Boolean(actionReadiness.REPLAN_AUDIO_TRACK.ready)
      : fallback.can_replan;
    const renderReady = actionReadiness.RENDER_AUDIO_TRACK
      ? Boolean(actionReadiness.RENDER_AUDIO_TRACK.ready)
      : fallback.can_render;
    const reviewReady = actionReadiness.REVIEW_AUDIO_TRACK
      ? Boolean(actionReadiness.REVIEW_AUDIO_TRACK.ready)
      : true;
    return [key, {
      ...fallback,
      ...(source[key] || {}),
      key,
      action_readiness: actionReadiness,
      can_replan: key !== "voice" && replanReady,
      can_render: renderReady,
      // Compatibility for older DOM adapters; new actions use explicit
      // planning/rendering capabilities instead of a misleading regenerate.
      can_regenerate: key !== "voice" && replanReady,
      can_review: reviewReady,
    }];
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

