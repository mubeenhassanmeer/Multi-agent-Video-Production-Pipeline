---
name: yt-approval-gateway
description: Send a rendered video to the human reviewer over WhatsApp for approve/reject before any YouTube upload.
metadata:
  {
    "openclaw":
      {
        "requires": { "config": ["channels.whatsapp"] }
      }
  }
---

# YouTube Approval Gateway

You are the mandatory human checkpoint between rendering and publishing. A
video must NEVER be uploaded to YouTube without an explicit "APPROVED" reply
from the reviewer over WhatsApp — this is a hard rule from the SOW
(`/home/tera/Documents/esp32/docs/SOW_YouTube_Automation_Pipeline.docx`),
not a suggestion. If you have not seen an approval message for a given run
directory, do not invoke `$yt-uploader` for it, no matter how confident you
are the video is good.

## How to send a video for review

After `$yt-editor` produces `<RUN_DIR>/final.mp4`:

```bash
openclaw message send --channel whatsapp --target "+923278805181" \
  --message "Review needed: <TITLE>\n\nRun dir: <RUN_DIR>\n\nReply APPROVED to publish, or REJECT: <reason> to send back for changes." \
  --media "<RUN_DIR>/final.mp4"
```

`+923278805181` is the configured reviewer's WhatsApp number — replace
`<TITLE>` with the script's title and `<RUN_DIR>` with the run directory
path.

## Handling the reply

When a message arrives from that number:
- **"APPROVED"** (case-insensitive, possibly with extra text) — hand off to
  `$yt-uploader` with that run directory.
- **"REJECT: ..."** — do not upload. Relay the stated reason; if it implies
  a script/asset problem, that may mean re-running an earlier stage rather
  than the whole pipeline.
- Anything else — treat as a question/comment, answer it, and continue
  waiting. Do not interpret silence or an unrelated message as approval.
