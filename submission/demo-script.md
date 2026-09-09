# 3–5 Minute Demo Script

## Demo boundary

Use the private Studio only after authenticated access is confirmed. Keep the
runtime in Mock-only mode and do not click `提交真实生成`. The walkthrough
demonstrates orchestration and recovery, not real model output.

## Script

| Time | Screen action | Narration / evidence |
|---|---|---|
| 0:00–0:25 | Open the Studio landing page and show the four stages: PLAN, PREVIS, RENDER, DELIVER. | “Movie-Agent turns one original idea into a reviewable film-production state machine. This deployment is intentionally Mock-only for a reproducible, zero-cost demo.” |
| 0:25–0:50 | Show the saved-project selector and open `film-f55e58de` if it has been seeded; otherwise state that the seed is pending. | “The six-shot demo project is a deterministic planning candidate. Its snapshot, job ledger, and revisions are separate from generated media.” |
| 0:50–1:20 | Open Crew Assembly or the agent inventory view. | “Seven application agents divide the work: Director, Writer, Visual Bible, Storyboard, Generation, Reviewer, and Editor. Guardrails remain outside the Agent count.” |
| 1:20–1:55 | Open the storyboard and show the six-shot summary. | “Storyboard contracts make visual continuity, shot duration, action, sound, and transitions reviewable before render.” |
| 1:55–2:25 | Open the script/dialogue view and show Dialogue Lock. | “Dialogue and subtitle state are explicit deliverables. In this Mock run, the lock is demonstrated without a voice or video provider request.” |
| 2:25–3:05 | Open AI Edit / Rough Cut and show job/recovery evidence. | “Idempotency, lease expiry, heartbeat, event sequence, and recovery state make retries observable instead of silently duplicating work.” |
| 3:05–3:40 | Open Deliver and health/readiness evidence without submitting generation or export. | “The Docker target exposes port 7860, uses FFmpeg/FFprobe, and persists runtime data under `/mnt/workspace`. Health responses report capabilities without secrets.” |
| 3:40–4:20 | Show the private Studio identity, architecture diagram, and submission checklist; stop before any real generation or final submission action. | “The remaining delivery actions are authenticated project seeding, judge access confirmation, screenshots, recording, final film, team data, creative-note publication, and the official form.” |

## Recording checklist

- Record one continuous 16:9 screen capture, 3–5 minutes, with no credentials visible.
- Keep browser address bar visible long enough to establish the Studio host, but crop tokens and personal browser tabs.
- Do not claim that Mock assets are real provider output.
- End on the Deliver/checklist screen; do not click real generation, export, publish, or competition submit.
