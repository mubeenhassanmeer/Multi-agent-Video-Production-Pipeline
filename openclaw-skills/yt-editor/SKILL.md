---
name: yt-editor
description: Render the final captioned video (Ken Burns pan/zoom, word-synced burned-in captions, stitched voiceover) from a run directory's audio and images.
---

# YouTube Editor

You are Agent 4 of the automated YouTube pipeline. Given a run directory
that already has `audio/` and `images/` populated (by `$yt-asset-gatherer`),
render the final `.mp4` — do not generate assets or upload from this skill.

## How to run it

```bash
cd /home/tera/Documents/esp32/youtube-pipeline
set -a && source .env && set +a
./venv/bin/python -m pipeline.render_final "<RUN_DIR>"
```

Replace `<RUN_DIR>` with the run directory path handed off by the previous
stage. This can take a few minutes for longer videos (CPU-bound video
encode) — don't assume it hung; let it finish. It writes
`<RUN_DIR>/final.mp4` and prints its path on success.

## After rendering

This is the end of the automated chain for Phase 1 — there is no upload or
approval-gateway automation yet (that's Phase 2 per the SOW at
`/home/tera/Documents/esp32/docs/SOW_YouTube_Automation_Pipeline.docx`).
Tell the user the final video path and that it still needs manual review
and manual upload to YouTube.
