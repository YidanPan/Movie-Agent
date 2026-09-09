# Submission Matrix

This matrix separates what is proven in the repository from what needs the
authenticated competition portal. The official status endpoint currently
reports edition 2, `REGISTRATION`, `submission_open=true`, `work_type=video`,
and `allowed_work_types=[video, studio]`. The submission page's live form
requires a work name, description, a Studio URL for the `studio` track (or an
HTTP(S) external work link for the `video` track), and a creation-notes link.

| Item | Status | Evidence / next action |
|---|---|---|
| Official AI+∞ submission portal | REQUIRED / OPEN | `https://mseo-ai-inf.ms.show/submit`; current status endpoint says submission is open |
| Current phase / schedule | REQUIRED / CONFIRMED | Official status: edition 2, `REGISTRATION`; submission window reports through `2026-09-14T22:00` (confirm timezone in portal) |
| Submission track | REQUIRED / DECISION | Select `studio` for the deployed Movie-Agent; `video` is the alternate track |
| Work name | REQUIRED / READY DRAFT | Fill the portal field `作品名称`; use a final title only after the team confirms it |
| Work description | REQUIRED / READY DRAFT | Fill `作品简介`; use `project-description.md` and obey any live length limit |
| ModelScope Studio link | REQUIRED for studio / READY | `https://modelscope.cn/studios/LuckyPan/Movie-Agent`; currently private, Docker, `master` |
| External work/video link | REQUIRED for video / NOT APPLICABLE to studio | The live video track validates an HTTP(S) public link; no fabricated link is supplied |
| Creation-notes draft | REQUIRED / READY | [creative-note.md](creative-note.md) is 800–1500 Chinese characters and ready for publication |
| Creation-notes link (`blog_url`) | REQUIRED / MISSING | Publish the approved creation notes on ModelScope Learn/Spotlight, then paste the public URL |
| Competition category | COMPATIBLE / CONFIRM | Official works page currently lists `电影Agent`; confirm the selected category in the portal |
| Source repository | SUPPORTING / READY | GitHub `YidanPan/Movie-Agent`, HEAD `7dcd366`; paste exact public URL if the portal asks |
| Demo project seed | REQUIRED FOR LIVE WALKTHROUGH / MANUAL | `film-f55e58de` is local-only; seed through the normal app workflow after private access is confirmed |
| Demo video | UNCLEAR / MISSING | Record `demo-script.md` walkthrough; do not use a generated placeholder as evidence |
| Screenshots | UNCLEAR / MISSING | Capture S1–S7 after authenticated access |
| Architecture diagram | OPTIONAL OR UNCLEAR / READY | `architecture-diagram.svg`; attach if the portal offers an upload/link field |
| Final film | REQUIRED BY FILM CLAIM / MISSING | Current local media candidate is not verified as `《付费解锁人生》`; supply the actual final film and credits |
| Team information | REQUIRED at registration if requested / MISSING | Complete `team-template.md` in the official account only |
| Extra-content incentive | NOT ENABLED in current edition | Official status reports `submission_extra_incentive_enabled=false`; do not prepare a claim |
| Open-source / license statement | UNCLEAR / READY TO CONFIRM | Verify any live portal wording and ensure repository license/attribution meet it |
| Private judge access | REQUIRED / BLOCKED | Anonymous target health previously returned 403; obtain an authenticated judge route or official sharing instruction without making the Studio public |
| Official deadline and file limits | PARTIAL | Deadline is exposed by the official status endpoint; file-size/media limits remain portal/manual confirmation |
