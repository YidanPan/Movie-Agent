/** Playback formatting shared by Screening Room, Inspector and audio timeline. */
export const formatTime = (seconds = 0) => {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
};

export function setPlaybackRate(media, rate = 1) {
  if (!media) return;
  media.playbackRate = Math.min(2, Math.max(0.25, Number(rate) || 1));
}

export function modulePlayer() {
  return { formatTime, setPlaybackRate };
}

