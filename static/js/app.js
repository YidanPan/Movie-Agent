/**
 * P2 module registry and browser bootstrap.  The domain modules register
 * first, then the DOM adapter is loaded dynamically so it cannot observe a
 * partially populated registry.
 */
import { moduleApi } from "./api.js";
import { moduleState } from "./state.js";
import { moduleTheme } from "./theme.js";
import { moduleMotion } from "./motion.js";
import { modulePlayer } from "./player.js";
import { moduleCrew } from "./crew.js";
import { moduleStoryboard } from "./storyboard.js";
import { moduleScript } from "./script.js";
import { moduleSound } from "./sound.js";
import { moduleDeliver } from "./deliver.js";

Object.assign(window.MovieAgentModules || (window.MovieAgentModules = {}), {
  api: moduleApi(),
  state: moduleState(),
  theme: moduleTheme(),
  motion: moduleMotion(),
  player: modulePlayer(),
  crew: moduleCrew(),
  storyboard: moduleStoryboard(),
  script: moduleScript(),
  sound: moduleSound(),
  deliver: moduleDeliver(),
});

window.dispatchEvent(new CustomEvent("movie-agent:modules-ready"));

// Keep one browser entry point.  A classic script tag would execute before
// this deferred module and race the registry initialization.
await import("../app.js?v=ui-20260905-p5");

