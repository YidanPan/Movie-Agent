# Movie-Agent

Movie-Agent is a multi-agent film production workspace for the ModelScope “AI + Film/TV” competition. It turns one original science-fiction idea into a production brief, short script, visual bible, structured storyboard, generated shots, quality reports, and an editable final cut plan.

## Workflow

`Idea → Director → Writer → Storyboard → Visual Bible → Shot Generation → Keyframe QA → FFmpeg Edit`

`MovieOrchestrator` coordinates shared project state and event delivery. Director, writer, storyboard, visual bible, generation, reviewer, and editor are independent modules. Projects are persisted as JSON and can resume from completed shots.

## Modes

- **Mock mode** runs the complete planning and production state flow without downloading models or calling ComfyUI.
- **ModelScope text mode** uses the OpenAI-compatible ModelScope endpoint for creative planning agents.
- **Spark ComfyUI mode** submits the verified MiniMax-H3 T2V workflow one shot at a time and uses FFmpeg for assembly.

The currently verified Spark workflow is T2V. I2V and R2V remain disabled until their corresponding workflows are verified.

## Video quality and originality review

Before rendering, the planning quality gate checks structure, duration, prompt completeness, visual cards, and known IP references. When a ModelScope text model is enabled, a semantic copyright reviewer also evaluates substantial similarity to existing films, characters, titles, dialogue, and signature settings. High-risk proposals are blocked; medium-risk proposals receive rewrite guidance.

After each real MP4 is generated, the reviewer extracts 1–5 interior keyframes and stores them under `outputs/<project_id>/quality/shot-XX/`. To enable optional multimodal review, configure a ModelScope vision-capable model:

```text
MODELSCOPE_VISION_MODEL=your-vision-model-id
VISION_KEYFRAMES_PER_SHOT=3
```

The vision reviewer compares character and scene consistency against the visual bible and writes `review.json`. A failed verdict, a score below 70, or high copyright risk triggers the existing shot retry flow. Without a vision model, keyframes are still archived and the result is explicitly marked for human review.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
copy .env.example .env  # Windows; use cp on Linux/macOS
python server.py
```

Open `http://127.0.0.1:9071`. The recommended FastAPI interface provides the cinematic three-act workspace, SSE progress updates, shot timeline, monitor, premiere flow, and project exports. `python app.py` remains available as the Gradio Space fallback.

## Configuration

```text
MODEL_PROVIDER=mock
VIDEO_GENERATION_MODE=mock
MODELSCOPE_API_KEY=
MODELSCOPE_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
COMFY_BASE_URL=http://127.0.0.1:8188
PORT=9071
```

For Spark rendering, set `VIDEO_GENERATION_MODE=comfyui` only after ComfyUI, MiniMax-H3 weights, FFmpeg, and the verified workflow have been validated. Store tokens only in `.env` or platform secrets; never commit them.

## Project layout

- `server.py` — FastAPI service, SSE events, and static frontend.
- `static/` — cinematic frontend assets.
- `app.py` — Gradio fallback entry point.
- `movie_agent/agents/` — independent production agents.
- `movie_agent/services/` — ModelScope, ComfyUI, FFmpeg, storage, and quality adapters.
- `workflows/` — verified ComfyUI API workflow templates.
- `docs/` — deployment and competition notes.
- `projects/` and `outputs/` — runtime artifacts; excluded from Git.

## Compliance

Use only original or licensed material. Do not use existing film IP, characters, titles, dialogue, celebrity likenesses, or unlicensed voices. Never commit passwords, tokens, API keys, server credentials, model weights, caches, or media outputs.
