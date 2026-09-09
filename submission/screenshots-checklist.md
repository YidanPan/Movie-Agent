# Screenshot Checklist

Capture these after authenticated access is confirmed. Each image should show
the relevant UI state only; redact tokens, cookies, personal email addresses,
and unrelated browser tabs.

| ID | Required view | Evidence to capture | Status |
|---|---|---|---|
| S1 | Landing / pipeline | PLAN → PREVIS → RENDER → DELIVER navigation and project selector | MANUAL |
| S2 | Project brief | Original idea, duration, visual style, and safe Mock boundary | MANUAL |
| S3 | Script + dialogue | Story, dialogue/subtitle mode, and locked dialogue state | MANUAL |
| S4 | Visual Bible + storyboard | Character/scene constraints and six-shot storyboard summary | MANUAL |
| S5 | Job/recovery state | Status, progress, event history, retry/recovery fields without secrets | MANUAL |
| S6 | Health/readiness | `/health`, `/api/health`, or in-app capability result showing PASS fields | MANUAL |
| S7 | Deliver / architecture | Deliver panel plus `architecture-diagram.svg` as a separate attachment | MANUAL |

## Acceptance rules

- Use PNG or high-quality JPG; keep a consistent 16:9 crop where possible.
- File names: `S1-home.png` through `S7-deliver.png`.
- Every screenshot must be reproducible from the private Studio or the source repository.
- Screenshots are not a substitute for the required demo recording or final film.

