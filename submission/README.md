# Movie-Agent Submission Package

This directory contains the small, review-facing materials that can safely live
in source control. It intentionally does not contain `.env`, access tokens,
generated media, local project snapshots, or private Studio data.

## Package contents

- [Project description](project-description.md)
- [Creative note](creative-note.md)
- [Demo script](demo-script.md)
- [Screenshots checklist](screenshots-checklist.md)
- [Team template](team-template.md)
- [Submission matrix](submission-matrix.md)
- [Architecture diagram](architecture-diagram.svg)

## Truth boundary

The repository and private Studio are accepted engineering artifacts. The
current runtime is Mock-only (`MODEL_PROVIDER=mock`,
`IMAGE_GENERATION_MODE=mock`, `VIDEO_GENERATION_MODE=mock`, `TTS_PROVIDER=none`)
and must be presented that way. `film-f55e58de` is a local six-shot planning
candidate for a safe UI walkthrough; it is not a final film and it has no
committed or verified delivery media.
