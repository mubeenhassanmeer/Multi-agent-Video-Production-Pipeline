---
name: yt-asset-gatherer
description: Generate per-scene narration audio and scene images for a video from its script.json, using the pipeline's asset-generation stage.
---

# YouTube Asset Gatherer

You are Agent 3 of the automated YouTube pipeline. Given a run directory
that already has a `script.json` (produced by `$yt-scriptwriter`), generate
the per-scene audio and image files — do not write scripts or render video
from this skill.

## How to run it

```bash
cd /home/tera/Documents/esp32/youtube-pipeline
set -a && source .env && set +a
./venv/bin/python -m pipeline.generate_assets "<RUN_DIR>/script.json" "<RUN_DIR>"
```

Replace `<RUN_DIR>` with the run directory path handed off by the previous
stage (e.g. `output/3-unexplained-phenomena-at-the-bottom-of-the-ocean`).
This writes `<RUN_DIR>/audio/scene_NNN.*` and one or more
`<RUN_DIR>/images/scene_NNN_img_MM.png` per scene (one image per ~2.75s of
that scene's actual audio, not a fixed one-per-scene) and prints the
generated file paths as JSON.

## Current engine settings

Controlled by `TTS_ENGINE` / `IMAGE_ENGINE` in `.env`, or live via
`python -m pipeline.control_center` (http://127.0.0.1:5057) — check
`pipeline_config.json` / the control center page for current values rather
than assuming, since these can change between runs without a code change:

- **Audio**: `piper` (free/local), `elevenlabs`, or `fishaudio`.
- **Images**: `placeholder` (free/local Pillow cards) or `imagen` (real
  generated visuals via the Gemini API's image model). If asked to produce
  a "real"/"professional" video and `IMAGE_ENGINE` is still `placeholder`,
  say so explicitly rather than silently proceeding with placeholders.
- Failed image generation calls retry automatically (`IMAGE_MAX_RETRIES`)
  before falling back to a placeholder for just that one image — a few
  placeholder images mixed into an otherwise-real set means some retries
  were exhausted; mention this if it happens rather than staying silent.

## Handoff

Report how many scenes were generated and hand off the same run directory
to `$yt-editor` for final rendering.
