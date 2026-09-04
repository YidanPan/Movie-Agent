/**
 * P2 module registry.  The legacy static/app.js remains the browser entry
 * point for backwards compatibility; these ES modules provide stable seams
 * for incremental extraction without introducing a build step.
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

window.MovieAgentModules = {
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
};

