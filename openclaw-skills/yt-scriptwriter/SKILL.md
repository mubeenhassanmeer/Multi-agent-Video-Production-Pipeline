---
name: yt-scriptwriter
description: Turn a video topic into a structured script (hook/body/outro scenes with narration and image prompts) using the pipeline's script-generation stage.
---

# YouTube Scriptwriter

You are Agent 2 of the automated YouTube pipeline. Given a topic (from the
user, or handed off from `$yt-content-analyst`), produce a structured script
by running the pipeline's scriptwriting stage — do not write the script
yourself from scratch, and do not proceed to assets/rendering from this
skill.

## How to run it

```bash
cd /home/tera/Documents/esp32/youtube-pipeline
set -a && source .env && set +a
RUN_DIR="output/$(./venv/bin/python -m pipeline.slug "<TOPIC>")"
mkdir -p "$RUN_DIR"
./venv/bin/python -m pipeline.generate_script "<TOPIC>" | tee "$RUN_DIR/script.json"
```

Replace `<TOPIC>` with the actual topic text (quote it exactly once, don't
double-escape). This prints the script JSON and also saves it to
`$RUN_DIR/script.json` — report `$RUN_DIR` back, the next stage needs it.

## Output contract

The script JSON has `title` and `scenes: [{narration, image_prompt}, ...]`.
If the command fails because `OPENROUTER_API_KEY` or `OPENROUTER_MODEL` is
missing/invalid, report the exact error to the user rather than retrying
blindly — those are config problems, not something to work around.

## Handoff

Report the run directory path and the generated title/scene count to the
user, then hand off to `$yt-asset-gatherer` with that run directory.
