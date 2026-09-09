# 3–5 Minute Demo Script

## Demo boundary

Use the private Studio only after authenticated access is confirmed. Keep the
runtime in Mock-only mode and do not click `提交真实生成`. The walkthrough
demonstrates orchestration and recovery, not real model output.

## Script

| Time | Screen action | Narration / evidence |
|---|---|---|
| 0:00–0:25 | Open the Studio landing page and show the four stages: PLAN, PREVIS, RENDER, DELIVER. | “Movie-Agent turns one original idea into a reviewable film-production state machine. This deployment is intentionally Mock-only for a reproducible, zero-cost demo.” |
| 0:25–0:55 | Show the saved-project selector and open `film-f55e58de` if it has been seeded; otherwise show the documented local candidate and state the seed is pending. | “The demo project has six storyboard shots. The project snapshot, job ledger, and revisions are separate from generated media.” |
| 0:55–1:35 | Open project brief, script/dialogue, Visual Bible, and storyboard tabs. | “The planning agents establish story, dialogue, visual constraints, and shot contracts before any render operation. The six candidate shots are `approved_mock`.” |
| 1:35–2:15 | Show the architecture diagram and the project/job status fields. | “The Orchestrator owns revision and recovery. Director, Writer, Visual Bible, Storyboard, Generation, Reviewer, and Editor are the seven application agents; quality and copyright gates are guardrails.” |
| 2:15–2:50 | Show health/readiness evidence and the Deliver panel without submitting generation. | “The Docker target exposes port 7860, uses FFmpeg/FFprobe, and persists runtime data under `/mnt/workspace`. Health responses report capabilities without secrets.” |
| 2:50–3:30 | If available, show a pre-existing Mock failure/recovery record or job event history; do not create a real provider task. | “Reliability is part of the product: idempotency, lease expiry, heartbeat, event sequence, and recovery state make a retry observable instead of silently duplicating work.” |
| 3:30–4:00 | Show the submission checklist and private Studio URL, then stop before any real generation or final submission action. | “The remaining gates are manual: authenticated judge access, project seeding confirmation, screenshots, demo recording, final film, team data, and the official submission form.” |

## Recording checklist

- Record one continuous 16:9 screen capture, 3–5 minutes, with no credentials visible.
- Keep browser address bar visible long enough to establish the Studio host, but crop tokens and personal browser tabs.
- Do not claim that Mock assets are real provider output.
- End on the Deliver/checklist screen; do not click real generation, export, publish, or competition submit.

