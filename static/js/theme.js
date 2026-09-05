/** Theme persistence seam shared by Screening Room and Production Desk. */
const STORAGE_KEY = "movie-agent-theme";

export function readTheme() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch (_) { /* storage can be unavailable in private contexts */ }
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function saveTheme(theme) {
  const value = theme === "light" ? "light" : "dark";
  try { localStorage.setItem(STORAGE_KEY, value); } catch (_) { /* best effort */ }
  document.documentElement.dataset.theme = value;
  return value;
}

export function moduleTheme() {
  return { readTheme, saveTheme };
}

