---
name: yt-uploader
description: Publish an approved video to YouTube via the official YouTube Data API. Only invoke after an explicit human APPROVED reply from $yt-approval-gateway.
---

# YouTube Uploader

You are the final stage. Only run this after `$yt-approval-gateway` reports
an explicit "APPROVED" reply for this exact run directory — never invoke
this skill speculatively, on a hunch the video is ready, or because the
render just finished. Uploading without human approval violates the SOW's
mandatory review gate.

## How to run it

```bash
cd /home/tera/Documents/esp32/youtube-pipeline
set -a && source .env && set +a
./venv/bin/python -m pipeline.upload_youtube "<RUN_DIR>" --privacy private
```

Replace `<RUN_DIR>` with the approved run directory.

## Privacy default is intentional

The upload defaults to `--privacy private`, not `public`. This is a
deliberate second safety margin: even an approved upload lands unlisted
from public search/browse, and the user still makes the final call to flip
it to public (in YouTube Studio, or by re-running this with
`--privacy public` if the user explicitly asks for that in the same
approval). Do not default to `public` on your own judgment.

## First-time setup dependency

This requires `client_secret.json` (Google Cloud OAuth "Desktop app"
credentials with YouTube Data API v3 enabled) to already exist at the
project root, and a one-time interactive browser consent to have completed
(cached afterward in `token.json`). If the command fails because
`client_secret.json` is missing, tell the user exactly that — do not try to
work around it or fabricate credentials.

## Handoff

Report the resulting YouTube URL and privacy status back to the reviewer in
the same WhatsApp chat used for approval.
