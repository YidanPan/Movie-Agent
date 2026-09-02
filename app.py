"""Gradio entry point for the Movie-Agent MVP."""

from __future__ import annotations

from pathlib import Path

import gradio as gr

from movie_agent.config import Settings
from movie_agent.orchestrator import MovieOrchestrator


settings = Settings.from_env()
orchestrator = MovieOrchestrator(settings)


APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Merriweather:wght@300;400;700&family=Noto+Serif+SC:wght@500;600;700&family=Playfair+Display:wght@600;700&display=swap');
:root {
  --ink: #161514;
  --ink-soft: #292725;
  --accent: #dd4e38;
  --accent-deep: #b63322;
  --paper: #f5f2ea;
  --surface: #fffdf8;
  --surface-muted: #ece7dd;
  --line: #d8d0c4;
  --muted: #756e64;
  --success: #366552;
}
body, .gradio-container {
  background: var(--paper);
  color: var(--ink);
}
.gradio-container {
  max-width: 1540px !important;
  padding: 22px clamp(16px, 3.4vw, 56px) 56px !important;
  font-family: "Manrope", "Noto Sans SC", "Microsoft YaHei UI", Arial, sans-serif;
}
.app-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 18px;
  padding: 0 2px;
}
.brand-lockup { display: flex; align-items: center; gap: 10px; }
.brand-mark { display: grid; place-items: center; width: 28px; height: 28px; color: var(--surface); background: var(--ink); font-family: "DM Mono", monospace; font-size: .68rem; font-weight: 500; letter-spacing: -.08em; }
.brand-name { color: var(--ink); font-size: .83rem; font-weight: 800; letter-spacing: .15em; }
.topbar-meta { color: var(--muted); font-family: "DM Mono", monospace; font-size: .68rem; letter-spacing: .04em; }
.movie-hero {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 32px;
  align-items: end;
  margin-bottom: 18px;
  padding: clamp(30px, 5vw, 64px);
  border-radius: 3px;
  color: var(--surface);
  background: var(--ink);
  box-shadow: 0 18px 38px rgba(29,25,19,.12);
}
.movie-hero::after {
  content: "";
  position: absolute;
  inset: -24% -5% auto auto;
  width: min(42vw, 560px);
  aspect-ratio: 1;
  border: 1px solid rgba(255,253,248,.22);
  border-radius: 50%;
}
.movie-hero__eyebrow {
  margin: 0 0 13px;
  color: #d8d0c4;
  font-family: "DM Mono", monospace;
  font-size: .68rem;
  font-weight: 500;
  letter-spacing: .12em;
  text-transform: uppercase;
}
.movie-hero h1 { position: relative; z-index: 1; margin: 0; color: var(--surface) !important; font-family: "Noto Serif SC", "Songti SC", Georgia, serif !important; font-size: clamp(2.35rem, 4.5vw, 4.5rem); font-weight: 600; letter-spacing: .1em; line-height: 1.05; }
.movie-hero p:last-child { position: relative; z-index: 1; max-width: 600px; margin: 18px 0 0; color: #d8d0c4 !important; font-size: .98rem; line-height: 1.8; }
.hero-status { position: relative; z-index: 1; display: grid; gap: 9px; min-width: 205px; padding: 16px 17px; border: 1px solid rgba(255,253,248,.24); background: rgba(255,253,248,.06); font-size: .77rem; line-height: 1.45; }
.hero-status::before { content: "LIVE"; color: #ef725f; font-family: "DM Mono", monospace; font-size: .62rem; letter-spacing: .14em; }
.hero-status strong { color: var(--surface); font-size: .92rem; letter-spacing: .04em; }
.hero-status span { color: #d8d0c4; }
.panel {
  padding: 22px !important;
  border: 1px solid var(--line) !important;
  border-radius: 3px !important;
  background: var(--surface) !important;
  box-shadow: none !important;
}
.panel-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin: 0 0 18px; padding-bottom: 14px; border-bottom: 1px solid var(--line); }
.panel-title { margin: 0; color: var(--ink); font-family: "DM Mono", monospace; font-size: .69rem; font-weight: 500; letter-spacing: .1em; text-transform: uppercase; }
.panel-kicker { color: var(--muted); font-size: .76rem; }
.panel-note { margin: -5px 0 18px; color: var(--muted); font-size: .81rem; line-height: 1.65; }
.stage-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  margin: 0 0 18px;
  border: 1px solid var(--line);
  background: var(--line);
}
.stage-strip span {
  display: block;
  padding: 16px 14px;
  color: var(--ink);
  background: var(--surface);
  font-size: .78rem;
  font-weight: 700;
  letter-spacing: .03em;
}
.stage-strip b { display: block; margin-bottom: 5px; color: var(--muted); font-family: "DM Mono", monospace; font-size: .62rem; font-weight: 500; letter-spacing: .09em; }
.stage-strip span:nth-child(1), .stage-strip span:nth-child(2) { background: #f0ece3; }
.stage-strip span:nth-child(3) { color: var(--surface); background: var(--ink); }
.stage-strip span:nth-child(3) b { color: #ef725f; }
#create-button, #create-button button, #render-button, #render-button button {
  min-height: 48px;
  border: 1px solid var(--ink) !important;
  border-radius: 2px !important;
  color: var(--surface) !important;
  background: var(--ink) !important;
  box-shadow: none !important;
  font-weight: 700 !important;
  letter-spacing: .04em;
  transition: background .18s ease, color .18s ease, border-color .18s ease !important;
}
.render-note { margin: 10px 0 0; color: var(--muted); font-size: .72rem; line-height: 1.55; }
#render-button, #render-button button { border-color: var(--accent) !important; background: var(--accent) !important; }
#create-button:hover, #create-button button:hover { color: var(--ink) !important; background: var(--surface-muted) !important; }
#render-button:hover, #render-button button:hover { border-color: var(--accent-deep) !important; background: var(--accent-deep) !important; }
button.secondary, button:not(.primary) { border-radius: 2px !important; }
button, textarea, input, .wrap, .prose, .markdown { font-family: "Manrope", "Noto Sans SC", "Microsoft YaHei UI", Arial, sans-serif !important; }
.prose h1, .prose h2, .prose h3, .markdown h1, .markdown h2, .markdown h3 { font-family: "Noto Serif SC", "Songti SC", Georgia, serif !important; color: var(--ink); }
.prose h2, .markdown h2 { margin-top: 1.45rem !important; padding-top: 1.15rem !important; border-top: 1px solid var(--line); font-size: 1.2rem !important; }
.prose p, .markdown p, .prose li, .markdown li { color: #413d38 !important; line-height: 1.8 !important; }
.block, .form, .gr-box, .gr-panel { border-color: var(--line) !important; }
label span { color: var(--ink) !important; font-weight: 700; }
#create-button button:focus-visible, #render-button button:focus-visible, button:focus-visible, input:focus-visible, textarea:focus-visible { outline: 3px solid rgba(221,78,56,.35) !important; outline-offset: 2px !important; }
input[type="range"] { accent-color: var(--accent) !important; }
textarea, input, .wrap-inner { border-radius: 2px !important; }
#status textarea, #final-output textarea { color: var(--ink) !important; background: #f0ece3 !important; font-family: "DM Mono", monospace !important; font-size: .75rem !important; }
#final-video { overflow: hidden; border: 1px solid var(--line); border-radius: 3px; }
.workspace-status { display: grid; grid-template-columns: 1.6fr .9fr; gap: 18px; align-items: start; }
.status-meta { padding: 4px 0; }
.status-meta__label { margin-bottom: 5px; color: var(--muted); font-family: "DM Mono", monospace; font-size: .62rem; letter-spacing: .1em; text-transform: uppercase; }
.status-meta__copy { color: var(--ink); font-size: .8rem; font-weight: 700; line-height: 1.55; }
.status-meta__copy span { display: block; margin-top: 5px; color: var(--muted); font-size: .73rem; font-weight: 500; }
.tabs { margin-top: 18px !important; }
.tabs > .tab-nav { gap: 18px !important; border-bottom: 1px solid var(--line) !important; }
.tabs > .tab-nav button { padding: 11px 0 !important; color: var(--muted) !important; font-weight: 700 !important; }
.tabs > .tab-nav button.selected { color: var(--ink) !important; border-color: var(--accent) !important; }
.tabs > .tab-nav button:hover { color: var(--ink) !important; }
.asset-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 0 0 16px; }
.asset-card { min-height: 80px; padding: 14px; border: 1px solid var(--line); background: #faf7f0; }
.asset-card b { display: block; margin-bottom: 7px; color: var(--ink); font-size: .8rem; }
.asset-card span { color: var(--muted); font-size: .72rem; line-height: 1.45; }
.file-delivery { padding: 22px; border: 1px dashed #bdb2a3; background: #f7f3eb; }
.file-delivery h3 { margin: 0 0 8px; font-family: "Noto Serif SC", serif; font-size: 1.25rem; }
.file-delivery p { margin: 0; color: var(--muted); font-size: .82rem; line-height: 1.65; }
button { cursor: pointer !important; }
button[disabled] { opacity: .48 !important; cursor: not-allowed !important; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; } }
@media (max-width: 760px) {
  .gradio-container { padding: 16px !important; }
  .app-topbar { align-items: flex-start; }
  .topbar-meta { display: none; }
  .movie-hero { padding: 30px 24px; }
  .movie-hero { grid-template-columns: 1fr; }
  .movie-hero h1 { font-size: 2rem; letter-spacing: .055em; }
  .hero-status { min-width: 0; }
  .stage-strip { grid-template-columns: repeat(2, 1fr); }
  .workspace-status, .asset-grid { grid-template-columns: 1fr; }
  .panel { padding: 17px !important; }
}

/* Visual language inspired by the accompanying personal site: calm editorial type,
   dusty-rose accents, generous whitespace, and softly elevated surfaces. */
:root { --ink: #3a3d4f; --ink-soft: #4d516d; --paper: #fcfaf9; --surface: #ffffff; --surface-muted: #f3ecea; --line: #e8dedb; --muted: #9698a6; --accent: #a8868c; --accent-deep: #8b6b72; --accent-soft: #efe4e6; --lavender: #efeaf0; --lavender-ink: #695773; }
body, .gradio-container { background: var(--paper); color: var(--ink); }
.gradio-container { position: relative; isolation: isolate; max-width: 1500px !important; padding: 24px clamp(18px, 4.8vw, 72px) 64px !important; font-family: "Merriweather", "Noto Serif SC", Georgia, serif; }
.gradio-container::before, .gradio-container::after { position: fixed; z-index: -1; width: 31rem; height: 31rem; border-radius: 50%; content: ""; pointer-events: none; }
.gradio-container::before { top: -20rem; right: -14rem; background: rgba(239,228,230,.5); }
.gradio-container::after { bottom: -23rem; left: -18rem; background: rgba(239,234,240,.62); }
.app-topbar { min-height: 64px; margin-bottom: 54px; padding: 0 2px; border-bottom: 1px solid var(--line); }
.brand-mark { width: 34px; height: 34px; border-radius: 50%; color: var(--accent-deep); background: linear-gradient(135deg, var(--accent-soft), #cbb3b8); box-shadow: 0 2px 8px rgba(61,64,79,.06); font-family: "Playfair Display", "Noto Serif SC", serif; font-size: .92rem; font-weight: 700; }
.brand-name { color: var(--ink); font-family: "JetBrains Mono", monospace; font-size: .84rem; font-weight: 600; letter-spacing: .02em; }
.topbar-nav { display: flex; align-items: center; gap: 2px; margin-left: auto; padding: 4px; border-radius: 999px; background: var(--surface-muted); }
.topbar-nav span { padding: 7px 13px; border-radius: 999px; color: var(--ink-soft); font-size: .71rem; line-height: 1; }
.topbar-nav span:first-child { color: var(--accent-deep); background: var(--surface); box-shadow: 0 1px 2px rgba(61,64,79,.05); }
.topbar-meta { margin-left: 3px; color: var(--muted); font-family: "JetBrains Mono", monospace; font-size: .62rem; letter-spacing: .04em; }
.movie-hero { overflow: visible; grid-template-columns: minmax(0, 1fr) minmax(220px, .42fr); gap: clamp(32px, 7vw, 100px); align-items: center; margin: 0 0 54px; padding: 0 5.5% 0 5%; border-radius: 0; color: var(--ink); background: transparent; box-shadow: none; }
.movie-hero::after { z-index: -1; inset: auto 3% auto auto; top: 45%; width: clamp(190px, 25vw, 320px); height: clamp(190px, 25vw, 320px); border: 1px dashed rgba(168,134,140,.55); }
.movie-hero__eyebrow { margin-bottom: 14px; color: var(--accent); font-family: "JetBrains Mono", monospace; font-size: .67rem; letter-spacing: .09em; }
.movie-hero h1 { color: var(--ink) !important; font-family: "Playfair Display", "Noto Serif SC", Georgia, serif !important; font-size: clamp(2.7rem, 5.2vw, 5.15rem); font-weight: 700; letter-spacing: -.02em; line-height: 1.12; }
.movie-hero p:last-child { max-width: 610px; margin-top: 20px; color: var(--ink-soft) !important; font-size: .95rem; line-height: 1.95; }
.hero-status { z-index: 1; gap: 10px; padding: 25px 24px; border: 1px solid var(--line); border-radius: 18px; background: rgba(255,255,255,.9); box-shadow: 0 8px 24px rgba(61,64,79,.08); }
.hero-status::before { content: "PRODUCTION STATUS"; color: var(--accent); font-family: "JetBrains Mono", monospace; font-size: .61rem; letter-spacing: .1em; }
.hero-status strong { color: var(--ink); font-family: "Playfair Display", "Noto Serif SC", serif; font-size: 1.25rem; letter-spacing: -.02em; }
.hero-status span { color: var(--ink-soft); }
.panel { padding: 24px !important; border-radius: 16px !important; background: rgba(255,255,255,.9) !important; box-shadow: 0 2px 8px rgba(61,64,79,.06) !important; }
.panel-heading { margin-bottom: 19px; padding-bottom: 15px; }
.panel-title { color: var(--accent); font-family: "JetBrains Mono", monospace; font-size: .66rem; font-weight: 600; letter-spacing: .08em; }
.panel-note { color: var(--ink-soft); font-size: .78rem; line-height: 1.8; }
.stage-strip { gap: 8px; margin-bottom: 21px; border: 0; background: transparent; }
.stage-strip span { padding: 13px 12px; border: 1px solid var(--line); border-radius: 12px; color: var(--ink-soft); background: rgba(255,255,255,.64); font-size: .72rem; font-weight: 400; }
.stage-strip b { color: var(--muted); font-family: "JetBrains Mono", monospace; font-size: .58rem; }
.stage-strip span:nth-child(1), .stage-strip span:nth-child(2) { background: var(--surface-muted); }
.stage-strip span:nth-child(3) { border-color: var(--accent); color: var(--accent-deep); background: var(--accent-soft); }
.stage-strip span:nth-child(3) b { color: var(--accent); }
#create-button, #create-button button, #render-button, #render-button button { border-color: var(--accent) !important; border-radius: 999px !important; color: #fff !important; background: var(--accent) !important; box-shadow: 0 8px 20px rgba(168,134,140,.22) !important; transition: transform .2s ease, box-shadow .2s ease, background .2s ease !important; }
#render-button, #render-button button { border-color: var(--lavender-ink) !important; background: var(--lavender-ink) !important; box-shadow: 0 8px 20px rgba(105,87,115,.18) !important; }
#create-button:hover, #create-button button:hover, #render-button:hover, #render-button button:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(61,64,79,.12) !important; }
button.secondary, button:not(.primary) { border-radius: 999px !important; border-color: var(--line) !important; color: var(--ink-soft) !important; background: var(--surface) !important; }
button, textarea, input, .wrap, .prose, .markdown { font-family: "Merriweather", "Noto Serif SC", Georgia, serif !important; }
label span { color: var(--ink) !important; font-size: .78rem !important; }
textarea, input, .wrap-inner { border-radius: 9px !important; }
#status textarea, #final-output textarea { color: var(--ink-soft) !important; background: var(--surface-muted) !important; font-family: "JetBrains Mono", monospace !important; font-size: .7rem !important; }
.status-meta { padding: 14px 15px; border-radius: 12px; background: var(--lavender); }
.status-meta__label { color: var(--lavender-ink); font-family: "JetBrains Mono", monospace; font-size: .58rem; }
.status-meta__copy { color: var(--ink); font-size: .78rem; line-height: 1.6; }.status-meta__copy span { color: var(--ink-soft); font-size: .71rem; font-weight: 400; }
.tabs > .tab-nav { gap: 7px !important; border-bottom: 0 !important; }.tabs > .tab-nav button { padding: 9px 15px !important; border: 1px solid transparent !important; border-radius: 999px !important; color: var(--ink-soft) !important; font-size: .78rem !important; font-weight: 400 !important; }.tabs > .tab-nav button.selected { border-color: var(--line) !important; color: var(--accent-deep) !important; background: var(--accent-soft) !important; }.tabs > .tab-nav button:hover { color: var(--accent-deep) !important; background: var(--surface-muted) !important; }
.asset-card { border-radius: 12px; background: var(--surface-muted); transition: transform .2s ease, box-shadow .2s ease; }.asset-card:nth-child(2) { background: var(--lavender); }.asset-card:nth-child(3) { background: #f7f4f7; }.asset-card:hover { transform: translateY(-2px); box-shadow: 0 2px 8px rgba(61,64,79,.06); }.asset-card b { font-family: "Playfair Display", "Noto Serif SC", serif; font-size: .93rem; }.asset-card span { color: var(--ink-soft); line-height: 1.6; }
.file-delivery { border: 1px solid var(--line); border-radius: 14px; background: linear-gradient(135deg, var(--surface-muted), var(--lavender)); }.file-delivery h3 { font-family: "Playfair Display", "Noto Serif SC", serif; color: var(--ink); }.file-delivery p { color: var(--ink-soft); line-height: 1.8; }

/* Gradio's default columns have a desktop-sized minimum width. Switch the
   production layout to one full-width column before they begin to overflow. */
#studio-layout { align-items: flex-start !important; }
#studio-layout > * { min-width: 0 !important; }
@media (max-width: 1100px) {
  .gradio-container { width: 100% !important; max-width: none !important; }
  #studio-layout { display: flex !important; flex-direction: column !important; flex-wrap: nowrap !important; width: 100% !important; }
  #studio-layout > * { flex: 0 0 auto !important; width: 100% !important; max-width: 100% !important; min-width: 0 !important; }
  .movie-hero { grid-template-columns: 1fr; margin-bottom: 42px; padding: 0 3%; }
  .hero-status { width: min(100%, 420px); }
}
@media (max-width: 760px) { .gradio-container { padding: 16px !important; }.app-topbar { min-height: 54px; margin-bottom: 38px; }.topbar-nav, .topbar-meta { display: none; }.movie-hero { margin-bottom: 40px; padding: 0 5%; }.movie-hero h1 { font-size: 2.5rem; letter-spacing: -.02em; }.movie-hero::after { right: -9%; top: 24%; opacity: .55; }.panel { padding: 18px !important; } }

/* Reading-first production flow: a stable cover, then one generous vertical
   workspace instead of competing left/right columns. */
.app-topbar { position: sticky; top: 0; z-index: 20; margin-left: -8px; margin-right: -8px; padding: 0 10px; background: rgba(252,250,249,.92); backdrop-filter: blur(14px) saturate(150%); }
.movie-hero { min-height: min(620px, calc(100vh - 88px)); margin-bottom: 64px; }
#studio-layout { display: flex !important; flex-direction: column !important; flex-wrap: nowrap !important; gap: 32px !important; width: 100% !important; }
#studio-layout > .column { flex: 0 0 auto !important; width: 100% !important; max-width: 100% !important; min-width: 0 !important; }
.workspace-status { grid-template-columns: 1fr !important; }
.project-meta-row { flex-direction: column !important; }
.project-meta-row > * { width: 100% !important; }
.history-actions { flex-direction: column !important; }
.history-actions > * { width: 100% !important; }
.asset-grid { grid-template-columns: 1fr !important; gap: 16px; }
.gradio-container { font-size: 18px !important; }
.panel { padding: clamp(26px, 3vw, 38px) !important; }
.panel-title { font-size: .8rem; }
.panel-kicker, .panel-note { font-size: 1rem; }
label span { font-size: 1rem !important; }
textarea, input, .wrap-inner, button { font-size: 1rem !important; }
.render-note { margin-top: 14px; font-size: .9rem; line-height: 1.75; }
.stage-strip { gap: 12px; margin-bottom: 26px; }
.stage-strip span { padding: 18px 16px; font-size: .95rem; }
.stage-strip b { margin-bottom: 7px; font-size: .7rem; }
.status-meta__label { font-size: .7rem; }.status-meta__copy { font-size: 1rem; }.status-meta__copy span { font-size: .88rem; }
.tabs > .tab-nav { gap: 10px !important; }.tabs > .tab-nav button { padding: 12px 20px !important; font-size: 1rem !important; }
.asset-card { min-height: 118px; padding: 22px; }.asset-card b { font-size: 1.2rem; }.asset-card span { font-size: .92rem; }
.file-delivery { padding: 30px; }.file-delivery h3 { font-size: 1.7rem; }.file-delivery p { font-size: 1rem; }
.prose p, .markdown p, .prose li, .markdown li { font-size: 1rem; }
@media (max-width: 760px) { .app-topbar { margin-left: -2px; margin-right: -2px; }.movie-hero { min-height: 0; margin-bottom: 40px; }.panel { padding: 22px !important; }.stage-strip { grid-template-columns: 1fr 1fr; }.stage-strip span { padding: 14px 12px; font-size: .82rem; }.panel-kicker { display: none; } }

/* Keep the canvas continuous: no hard-edged decorative colour blocks, and one
   shared centred grid for the navigation, cover, and vertical workspace. */
html, body, #root, .gradio-container, .gradio-container > .main { background: var(--paper) !important; }
html, body { width: 100%; min-width: 0; }
.gradio-container { width: 100% !important; max-width: none !important; margin: 0 !important; }
.gradio-container::before, .gradio-container::after { display: none !important; }
.app-topbar, .movie-hero, #studio-layout { width: min(100%, 1420px) !important; margin-left: auto !important; margin-right: auto !important; }
.app-topbar { padding-left: 18px; padding-right: 18px; }
.movie-hero { padding-left: clamp(32px, 5vw, 84px); padding-right: clamp(32px, 5vw, 84px); }
@media (max-width: 760px) { .app-topbar { width: 100% !important; padding-left: 0; padding-right: 0; }.movie-hero { padding-left: 8px; padding-right: 8px; } }
"""


def create_project(idea: str, duration: int, visual_style: str):
    try:
        project = orchestrator.create_project(idea, duration, visual_style)
    except Exception as error:
        return _empty_project_outputs(f"创作失败：{error}")
    text_mode = "ModelScope AI 文案" if orchestrator.using_creative_llm else "mock 文案"
    video_mode = "Spark 真实视频待生成" if settings.video_generation_mode == "comfyui" else "mock 视频流程"
    return _project_outputs(
        project,
        f"已完成：{text_mode} + {video_mode}（{project.project_id}）",
        gr.update(choices=orchestrator.store.list_project_ids(), value=project.project_id),
    )


def load_project(project_id: str):
    if not project_id:
        return _empty_project_outputs("尚未选择项目")
    try:
        project = orchestrator.store.load(project_id)
    except Exception as error:
        return _empty_project_outputs(f"读取失败：{error}")
    return _project_outputs(project, f"已恢复项目：{project.project_id}", gr.update(value=project.project_id))


def refresh_history():
    project_ids = orchestrator.store.list_project_ids()
    return gr.update(choices=project_ids, value=project_ids[0] if project_ids else None)


def regenerate_shot(project_id: str, shot_number: int):
    try:
        project = orchestrator.regenerate_shot(project_id, int(shot_number))
    except Exception as error:
        return _project_error_outputs(project_id, f"重新规划失败：{error}")
    return _project_outputs(project, f"已重新规划镜头 {int(shot_number)}", gr.update(value=project.project_id))


def render_project(project_id: str, progress=gr.Progress()):
    try:
        progress(0, desc="正在连接 Spark ComfyUI")
        project = orchestrator.render_project(
            project_id,
            progress_callback=lambda completed, total, description: progress(
                completed / total, desc=description
            ),
        )
    except Exception as error:
        return _project_error_outputs(project_id, f"渲染失败：{error}")
    return _project_outputs(
        project,
        f"真实镜头已生成，等待 AI Edit Rough Cut（{project.project_id}）",
        gr.update(value=project.project_id),
    )


def export_project(project_id: str):
    if not project_id:
        raise gr.Error("请先创建或打开一个项目。")
    return [str(path) for path in orchestrator.store.export(project_id)]


def _project_outputs(project, status_message: str, history_update):
    status = str(project.status)
    if status == "rough_cut_ready":
        edit_status = "Rough Cut 已完成：请预览后批准最终成片。"
    elif status.startswith("completed"):
        edit_status = f"最终成片已批准（字幕模式：{project.subtitle_mode}）。"
    elif status == "ready_for_ai_edit":
        edit_status = "SHOTS READY：锁定台词本后可启动 AI Edit。"
    else:
        edit_status = "等待镜头全部通过质检。"
    return (
        project.project_id,
        project.brief_as_markdown(),
        project.script_as_markdown(),
        project.visual_bible_as_markdown(),
        project.storyboard_as_markdown(),
        project.log_as_markdown(),
        status_message,
        project.final_output_placeholder or "",
        _video_update(project.final_output_placeholder),
        history_update,
        project.script.get("dialogue_book", []),
        project.script.get("subtitle_track", []),
        "LOCKED" if project.script.get("dialogue_locked") else "DRAFT · 可编辑",
        project.subtitle_mode,
        _video_update(project.rough_cut_placeholder),
        edit_status,
    )


def _empty_project_outputs(message: str):
    return (
        "", "", "", "", "", f"## 任务日志\n- {message}", message, "", _hidden_video(), gr.update(),
        [], [], "DRAFT · 等待项目", "burned", _hidden_video(), "",
    )


def _project_error_outputs(project_id: str, message: str):
    """Keep the current workspace visible when a downstream action fails."""

    try:
        project = orchestrator.store.load(project_id)
    except Exception:
        return _empty_project_outputs(message)
    return _project_outputs(project, message, gr.update(value=project.project_id))


def save_dialogue(project_id: str, dialogue_book: list[dict], subtitle_track: list[dict]):
    try:
        project = orchestrator.update_dialogue(
            project_id,
            dialogue_book=dialogue_book or [],
            subtitle_track=subtitle_track or [],
        )
    except Exception as error:
        return _project_error_outputs(project_id, f"保存台词本失败：{error}")
    return _project_outputs(project, "台词本草稿已保存，尚未锁定。", gr.update(value=project.project_id))


def lock_dialogue(project_id: str):
    try:
        project = orchestrator.lock_dialogue(project_id)
    except Exception as error:
        return _project_error_outputs(project_id, f"锁定台词本失败：{error}")
    return _project_outputs(project, "台词本已锁定：后续配音、字幕与剪辑读取此版本。", gr.update(value=project.project_id))


def unlock_dialogue(project_id: str):
    try:
        project = orchestrator.unlock_dialogue(project_id)
    except Exception as error:
        return _project_error_outputs(project_id, f"解锁台词本失败：{error}")
    return _project_outputs(project, "台词本已解锁，可修改后重新保存并锁定。", gr.update(value=project.project_id))


def create_rough_cut(project_id: str, progress=gr.Progress()):
    try:
        progress(0, desc="正在读取锁定台词本")
        project = orchestrator.create_rough_cut(
            project_id,
            progress_callback=lambda description: progress(0.55, desc=description),
        )
    except Exception as error:
        return _project_error_outputs(project_id, f"Rough Cut 失败：{error}")
    progress(1, desc="Rough Cut 已完成")
    return _project_outputs(project, "Rough Cut 已完成，可预览或批准最终成片。", gr.update(value=project.project_id))


def approve_edit(project_id: str, subtitle_mode: str):
    try:
        project = orchestrator.approve_edit(project_id, subtitle_mode)
    except Exception as error:
        return _project_error_outputs(project_id, f"批准成片失败：{error}")
    return _project_outputs(project, f"最终成片已批准（字幕模式：{project.subtitle_mode}）。", gr.update(value=project.project_id))


def export_subtitles(project_id: str):
    if not project_id:
        raise gr.Error("请先创建或打开一个项目。")
    try:
        project = orchestrator.store.load(project_id)
        paths = orchestrator.editor.write_subtitle_exports(project)
    except Exception as error:
        raise gr.Error(f"字幕导出失败：{error}") from error
    return [str(path) for path in paths]


def _hidden_video():
    return gr.update(value=None, visible=False)


def _video_update(path: str | None):
    if path and Path(path).is_file():
        return gr.update(value=path, visible=True)
    return _hidden_video()


with gr.Blocks(title="Movie-Agent · 流影制片台", css=APP_CSS) as demo:
    gr.HTML(
        """
        <header class="app-topbar">
          <div class="brand-lockup"><span class="brand-mark">M</span><span class="brand-name">Movie Agent</span></div>
          <div class="topbar-nav"><span>创作</span><span>分镜</span><span>生成</span><span>交付</span></div>
          <div class="topbar-meta">AI FILM STUDIO / V1.0</div>
        </header>
        <section class="movie-hero">
          <div><p class="movie-hero__eyebrow">Original AI film production desk</p><h1>把灵感，<br>拍成一部电影。</h1><p>从一句原创科幻创意出发，完成剧本、分镜、视觉设定与成片交付；每一步都可审阅、可恢复。</p></div>
          <aside class="hero-status"><strong>制作引擎就绪</strong><span>文案策划 · H3 生成 · FFmpeg 合片</span></aside>
        </section>
        """
    )
    with gr.Row(equal_height=False, elem_id="studio-layout"):
        with gr.Column(scale=1):
            with gr.Group(elem_classes="panel"):
                gr.HTML("<div class='panel-heading'><div class='panel-title'>01 / 新建项目</div><div class='panel-kicker'>从创意开始</div></div>")
                gr.HTML("<p class='panel-note'>先完成策划与分镜确认；视频生成会在你主动提交后才使用 Spark 资源。</p>")
                idea = gr.Textbox(
                    label="原创科幻创意",
                    lines=5,
                    placeholder="例如：最后一位城市值班员每天点亮空城，直到发现整座城市都在等待他下班。",
                )
                duration = gr.Slider(30, 80, value=48, step=1, label="目标时长（秒）")
                visual_style = gr.Dropdown(
                    ["写实近未来", "胶片科幻", "极简冷色", "梦境超现实"],
                    value="写实近未来",
                    label="视觉风格",
                )
                submit = gr.Button("开始创作", variant="primary", elem_id="create-button")
                gr.HTML("<p class='render-note'>系统会保存项目方案、制作日志与每一个镜头状态。</p>")
            with gr.Group(elem_classes="panel"):
                gr.HTML("<div class='panel-heading'><div class='panel-title'>02 / 项目库</div><div class='panel-kicker'>可随时恢复</div></div>")
                gr.HTML("<p class='panel-note'>打开已有项目，或针对不满意的镜头重新生成其策划方案。</p>")
                history = gr.Dropdown(
                    choices=orchestrator.store.list_project_ids(), label="已保存项目", interactive=True
                )
                with gr.Row(elem_classes="history-actions"):
                    refresh = gr.Button("刷新历史")
                    load = gr.Button("打开项目")
                shot_number = gr.Slider(1, 10, value=1, step=1, label="要重新规划的镜头号")
                regenerate = gr.Button("重新规划单个镜头")
        with gr.Column(scale=2):
            gr.HTML("<div class='stage-strip'><span><b>01 / PLAN</b>设定与剧本</span><span><b>02 / PREVIS</b>分镜与视觉</span><span><b>03 / RENDER</b>H3 生成</span><span><b>04 / DELIVER</b>剪辑成片</span></div>")
            with gr.Group(elem_classes="panel"):
                gr.HTML("<div class='panel-heading'><div class='panel-title'>制作工作区</div><div class='panel-kicker'>状态与交付控制</div></div>")
                with gr.Row(elem_classes="workspace-status"):
                    status = gr.Textbox(label="当前制作状态", interactive=False, elem_id="status", placeholder="输入创意后，制作状态会显示在这里。")
                    gr.HTML("<div class='status-meta'><div class='status-meta__label'>Render policy</div><div class='status-meta__copy'>先策划，后渲染<span>仅在你点击“提交 Spark 生成”后，才会启动逐镜生成与合片。</span></div></div>")
                with gr.Row(elem_classes="project-meta-row"):
                    project_id = gr.Textbox(label="项目 ID", interactive=False, placeholder="尚未创建项目")
                    final_output = gr.Textbox(label="成片输出路径", interactive=False, elem_id="final-output", placeholder="成片完成后显示")
                render = gr.Button("提交 Spark 真实生成", variant="primary", elem_id="render-button")
                gr.HTML("<p class='render-note'>镜头全部通过后显示 <b>SHOTS READY</b>；先锁定台词本，再进入 AI Edit Rough Cut。</p>")
            with gr.Group(elem_classes="panel"):
                gr.HTML("<div class='panel-heading'><div class='panel-title'>台词本与 AI Edit</div><div class='panel-kicker'>Writer lock → Rough Cut → Delivery</div></div>")
                gr.HTML("<p class='panel-note'>编剧阶段会生成按镜头拆分的 Dialogue Book 与 Subtitle Track。锁定后，配音、字幕和剪辑只读取这一版。</p>")
                dialogue_book = gr.JSON(label="Dialogue Book / 台词本（可编辑）", value=[])
                subtitle_track = gr.JSON(label="Subtitle Track / 字幕轨（可编辑）", value=[])
                with gr.Row(elem_classes="history-actions"):
                    save_dialogue_button = gr.Button("保存台词草稿")
                    lock_dialogue_button = gr.Button("锁定台词本 →", variant="primary")
                    unlock_dialogue_button = gr.Button("解锁并修改")
                dialogue_state = gr.Textbox(label="台词版本状态", value="DRAFT · 等待项目", interactive=False)
                with gr.Row(elem_classes="history-actions"):
                    rough_cut_button = gr.Button("AI 剪辑成片 →", variant="primary")
                    subtitle_mode = gr.Dropdown(
                        ["burned", "soft", "none"], value="burned", label="最终字幕模式", interactive=True
                    )
                    approve_edit_button = gr.Button("批准最终成片", variant="primary")
                rough_video = gr.Video(label="Rough Cut 粗剪预览", interactive=False, visible=False)
                edit_status = gr.Textbox(label="AI Edit 状态", value="", interactive=False)
                subtitle_export_button = gr.Button("导出 SRT / VTT")
                subtitle_exports = gr.File(label="字幕文件", file_count="multiple", interactive=False)
            with gr.Tabs():
                with gr.Tab("创作资产"):
                    with gr.Group(elem_classes="panel"):
                        gr.HTML("<div class='panel-heading'><div class='panel-title'>创作资产</div><div class='panel-kicker'>导演 · 编剧 · 视觉设定</div></div><div class='asset-grid'><div class='asset-card'><b>项目设定</b><span>主题、人物、世界观与影片规格</span></div><div class='asset-card'><b>剧本与旁白</b><span>可朗读的叙事与节奏骨架</span></div><div class='asset-card'><b>视觉规范</b><span>角色卡、场景卡与统一风格</span></div></div>")
                        brief = gr.Markdown("*创建项目后，这里会出现导演 Agent 的项目设定。*")
                        script = gr.Markdown("*剧本与旁白将在策划完成后显示。*")
                        visual_bible = gr.Markdown("*角色、场景和风格规范将在这里汇总。*")
                with gr.Tab("分镜制作"):
                    with gr.Group(elem_classes="panel"):
                        gr.HTML("<div class='panel-heading'><div class='panel-title'>镜头计划与日志</div><div class='panel-kicker'>6–10 个可渲染镜头</div></div>")
                        storyboard = gr.Markdown("*创建项目后，分镜 Agent 会在这里给出结构化镜头计划。*")
                        logs = gr.Markdown("*任务日志会记录每一步制作决策。*")
                with gr.Tab("交付文件"):
                    with gr.Group(elem_classes="panel"):
                        gr.HTML("<div class='file-delivery'><h3>交付中心</h3><p>生成完成后，在此预览最终 MP4，并导出可提交的项目 JSON 与 Markdown 制作档案。</p></div>")
                        final_video = gr.Video(label="最终成片", interactive=False, visible=False, elem_id="final-video")
                        export = gr.Button("导出项目档案（JSON + Markdown）")
                        exports = gr.File(label="项目导出", file_count="multiple", interactive=False)

    # Keep creation and history recovery on the same display contract.
    project_outputs = [
        project_id, brief, script, visual_bible, storyboard, logs, status, final_output, final_video, history,
        dialogue_book, subtitle_track, dialogue_state, subtitle_mode, rough_video, edit_status,
    ]
    submit.click(create_project, inputs=[idea, duration, visual_style], outputs=project_outputs)
    refresh.click(refresh_history, outputs=history)
    load.click(
        load_project,
        inputs=history,
        outputs=project_outputs,
    )
    regenerate.click(
        regenerate_shot,
        inputs=[project_id, shot_number],
        outputs=project_outputs,
    )
    render.click(
        render_project,
        inputs=project_id,
        outputs=project_outputs,
    )
    save_dialogue_button.click(save_dialogue, inputs=[project_id, dialogue_book, subtitle_track], outputs=project_outputs)
    lock_dialogue_button.click(lock_dialogue, inputs=project_id, outputs=project_outputs)
    unlock_dialogue_button.click(unlock_dialogue, inputs=project_id, outputs=project_outputs)
    rough_cut_button.click(create_rough_cut, inputs=project_id, outputs=project_outputs)
    approve_edit_button.click(approve_edit, inputs=[project_id, subtitle_mode], outputs=project_outputs)
    subtitle_export_button.click(export_subtitles, inputs=project_id, outputs=subtitle_exports)
    export.click(export_project, inputs=project_id, outputs=exports)


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=1).launch(server_name="0.0.0.0", server_port=settings.port)
