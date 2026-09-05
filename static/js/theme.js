/** Theme controller shared by Screening Room and Production Desk. */
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

export function createThemeController({ toggle, wash, colorMeta } = {}) {
  const root = document.documentElement;
  const reduced = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
  const updateToggle = (theme) => {
    if (!toggle) return;
    const isLight = theme === "light";
    const next = isLight ? "Screening Room" : "Production Desk";
    const nextShort = isLight ? "SCREENING" : "DESK";
    const label = toggle.querySelector(".theme-toggle-label");
    const icon = toggle.querySelector(".theme-toggle-icon");
    if (label) label.textContent = nextShort;
    if (icon) icon.dataset.target = isLight ? "screening" : "desk";
    toggle.setAttribute("aria-pressed", String(isLight));
    toggle.setAttribute("aria-label", `Switch to ${next}`);
    toggle.title = `Switch to ${next}`;
    toggle.dataset.theme = theme;
  };
  const syncColor = () => {
    if (!colorMeta) return;
    const value = getComputedStyle(root).getPropertyValue("--surface-0").trim();
    if (value) colorMeta.setAttribute("content", value);
  };
  const apply = (theme, { persist = false, animate = true } = {}) => {
    const next = theme === "light" ? "light" : "dark";
    const current = root.dataset.theme === "light" ? "light" : "dark";
    if (persist) saveTheme(next);
    if (current === next) {
      document.body?.setAttribute("data-theme", next);
      updateToggle(next);
      syncColor();
      return next;
    }
    const shouldAnimate = animate && !reduced() && wash;
    if (shouldAnimate) {
      wash.dataset.to = next;
      wash.classList.add("is-active");
      root.classList.add("theme-transitioning");
    }
    root.dataset.theme = next;
    document.body?.setAttribute("data-theme", next);
    updateToggle(next);
    syncColor();
    if (shouldAnimate) {
      window.setTimeout(() => {
        wash.classList.remove("is-active");
        root.classList.remove("theme-transitioning");
        window.setTimeout(() => {
          if (!wash.classList.contains("is-active")) delete wash.dataset.to;
        }, 560);
      }, 56);
    }
    return next;
  };
  const init = () => {
    const preference = readTheme();
    const initial = preference || (root.dataset.theme === "light" ? "light" : "dark");
    root.dataset.theme = initial;
    document.body?.setAttribute("data-theme", initial);
    updateToggle(initial);
    syncColor();
    toggle?.addEventListener("click", () => apply(root.dataset.theme === "light" ? "dark" : "light", { persist: true, animate: true }));
    const media = window.matchMedia?.("(prefers-color-scheme: light)");
    media?.addEventListener?.("change", () => {
      if (!readTheme()) apply(media.matches ? "light" : "dark", { animate: true });
    });
    return initial;
  };
  return { apply, init, read: readTheme };
}

export function moduleTheme() {
  return { readTheme, saveTheme, createThemeController };
}

