# Movie-Agent Stage 5B Release Checklist

This is the short acceptance checklist for the private ModelScope Docker
Studio. It does not authorize paid or real-provider generation.

## Baseline

- [ ] Working tree is clean before release work.
- [ ] Full local test suite passes.
- [ ] `python -m compileall .` passes.
- [ ] `git diff --check` passes.
- [ ] Release commit SHA is recorded.
- [ ] GitHub `main` and ModelScope `main`/`master` point to the intended SHA.

## Production configuration

- [ ] Studio is private.
- [ ] Target branch is `master`.
- [ ] Hardware is free `platform/2v-cpu-16g-mem`.
- [ ] `PORT=7860`; server binds `0.0.0.0`.
- [ ] `PROJECTS_DIR=/mnt/workspace/projects`.
- [ ] `OUTPUTS_DIR=/mnt/workspace/outputs`.
- [ ] `COMFY_OUTPUT_DIR=/mnt/workspace/comfy-output`.
- [ ] `MODEL_PROVIDER=mock`, `IMAGE_GENERATION_MODE=mock`, and
  `VIDEO_GENERATION_MODE=mock` for acceptance.

## Runtime, persistence, and recovery

- [ ] Build completes and runtime logs contain `Application startup complete`.
- [ ] Stage 5A self-check reports FFmpeg, FFprobe, workspace, application
  routes, frontend assets, and same-origin checks as `PASS`.
- [ ] A later startup reports
  `persistence_marker_previous=PRESENT` and
  `persistence_survived_restart=PASS`.
- [ ] A Mock test project survives refresh/restart and its Job Ledger can be
  read with `GET /api/projects/<project_id>/job?after=0&limit=40`.
- [ ] Recovery uses the documented `RECOVERABLE_FAILED / RESUME AVAILABLE`
  path and never deletes project state.

## API safety and final gate

- [ ] Upload limits, filename sanitization, project isolation, and atomic
  writes are covered by tests.
- [ ] Missing Provider credentials fail closed with an explicit state; no
  placeholder media is presented as real output.
- [ ] No prompt, token, secret, internal path, or signed URL appears in
  browser payloads or logs.
- [ ] No real video/image/LLM/voice generation request was made.
- [ ] Public exposure remains `NOT RECOMMENDED` until authentication review.

Evidence and known residual risks belong in the Stage 5B release report.
