# YouTube Automation Pipeline

See the SOW (`../docs/SOW_YouTube_Automation_Pipeline.docx`) for the full
phased plan. Status: Phase 0 and Phase 1 done and verified. Phase 2's
WhatsApp approval gateway is live and verified end-to-end; the YouTube
upload step is built but blocked on one credential only you can provide
(see below).

## Setup checklist — what's needed from you, and how to get it

| # | What | How to get it | Status |
|---|------|----------------|--------|
| 1 | OpenRouter API key + free model slug | [openrouter.ai/models](https://openrouter.ai/models) (filter: free) → sign up → API key | ✅ done |
| 2 | WhatsApp linked | `openclaw channels login --channel whatsapp`, scan QR | ✅ done |
| 3 | Gemini API key (real images) | [aistudio.google.com](https://aistudio.google.com) → "Get API key" (needs a Google Cloud project with **billing enabled** to go past the free tier — billing setup is a payment-details step only you can do) | ⏳ needed for `IMAGE_ENGINE=imagen` |
| 4 | Fish Audio API key (voice) | [fish.audio](https://fish.audio) → sign up → dashboard → API keys | ⏳ needed for `TTS_ENGINE=fishaudio` |
| 5 | ElevenLabs API key + voice ID (optional alt. voice) | [elevenlabs.io](https://elevenlabs.io) → sign up → API key, then Voice Library for a voice ID | ⏳ optional |
| 6 | YouTube OAuth `client_secret.json` | [console.cloud.google.com](https://console.cloud.google.com) → enable YouTube Data API v3 → OAuth consent screen → OAuth client ID (Desktop app) → download JSON | ⏳ needed for upload |
| 7 | Background music tracks | Your pick of license (see `music/README.md`) — I'm not auto-downloading copyrighted-adjacent files on your behalf | ⏳ optional, improves polish |

Once each key is obtained, put it in `.env` (never paste API keys in chat) —
see `.env.example` for the exact variable names.

## Setting up on a new machine (e.g. a second laptop)

Cloning this repo alone isn't enough — `.env`, `venv/`, and the voice model
are deliberately not in git (see `.gitignore`). This gets you fully running:

```bash
git clone https://github.com/mubeenhassanmeer/Multi-agent-Video-Production-Pipeline.git
cd Multi-agent-Video-Production-Pipeline

python3 -m venv venv
./venv/bin/pip install -r requirements.txt

cp .env.example .env
# edit .env: paste in your own API key values (retype them -- don't copy
# .env between machines through a git repo, even privately)

mkdir -p voice && cd voice
curl -sL -o en_US-lessac-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
curl -sL -o en_US-lessac-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
cd ..

set -a && source .env && set +a
python -m pipeline.main "a test topic"   # confirms the whole chain works
```

For the OpenClaw agent layer (Phase 1/2), also on the new machine:

```bash
curl -fsSL https://openclaw.ai/install.sh | bash   # run yourself, not through Claude
openclaw gateway install
for skill in yt-content-analyst yt-scriptwriter yt-asset-gatherer yt-editor yt-approval-gateway yt-uploader; do
  openclaw skills install "./openclaw-skills/$skill" --as "$skill" --force
done
openclaw channels login --channel whatsapp   # re-link WhatsApp on this machine
```

A Claude Code session on one machine cannot resume/control another machine
just because the same account is logged in — "can't reach your computer" is
expected, not a bug. Each machine runs its own independent OpenClaw
Gateway and Claude Code session; this repo is the thing that travels
between them, not the running session itself.

## What it does

1. **Script** — calls an LLM via OpenRouter, returns title + per-scene
   narration/image-prompt JSON.
2. **Audio** — synthesizes narration per scene. `TTS_ENGINE=piper` (free/
   local, default), `fishaudio`, or `elevenlabs`. Each scene's audio
   duration drives its on-screen time later — no even-split guessing.
3. **Images** — one image per ~`IMAGE_CADENCE_SECONDS` (default 2.75s) of
   that scene's actual audio duration, not one static image per scene.
   `IMAGE_ENGINE=placeholder` (default, free/local Pillow cards) or
   `imagen` (real generated visuals via the Gemini API's image model —
   Google's original Imagen-specific endpoint was discontinued, so this
   goes through the same `generateContent` endpoint as text, using
   `gemini-2.5-flash-image`). Failed image calls retry with backoff
   (`IMAGE_MAX_RETRIES`) before falling back to a placeholder so one bad
   call doesn't kill a whole render.
4. **Captions** — re-transcribes each scene's own audio with faster-whisper
   to get word-level timestamps, offset into the full timeline.
5. **Render** — MoviePy: Ken Burns pan/zoom per image, word-synced burned-in
   captions, stitched voiceover, an optional looped background-music bed
   mixed underneath (`MUSIC_ENABLED`, tracks in `music/`), `.mp4` output.

## Control center — tuning without touching .env

```bash
python -m pipeline.control_center
# -> http://127.0.0.1:5057
```

A local form for the frequently-adjusted, non-secret settings: TTS engine
switch (piper/elevenlabs/fishaudio) + voice/model IDs, image engine switch,
cadence, master prompt (a style anchor prepended to every image prompt so a
video's visuals look consistent), retry count, background music toggle/
volume. Saves to `pipeline_config.json`, which every pipeline run and every
OpenClaw skill picks up immediately — no restart, no editing `.env`. API
keys are never edited here; they stay in `.env` only.

## Setup

```bash
cd youtube-pipeline
source venv/bin/activate
cp .env.example .env   # fill in OPENROUTER_API_KEY and OPENROUTER_MODEL
set -a && source .env && set +a
```

Get `OPENROUTER_MODEL` from https://openrouter.ai/models (filter: free) —
free/stealth model slugs rotate, so check the site rather than reusing an
old value.

## Run

```bash
python -m pipeline.main "3 unexplained phenomena at the bottom of the ocean"
```

Output lands in `output/<slugified-topic>/`:
- `script.json` — the generated script
- `audio/scene_NNN.wav` — per-scene narration
- `images/scene_NNN_img_MM.png` — one or more images per scene, numbered for
  exact playback order and audio sync
- `final.mp4` — the rendered video

## Swapping in real APIs later

Nothing above needs to change structurally — set via `.env` or the control
center (see below):
- `TTS_ENGINE=elevenlabs` + `ELEVENLABS_API_KEY` / `ELEVENLABS_VOICE_ID`, or
  `TTS_ENGINE=fishaudio` + `FISHAUDIO_API_KEY` / `FISHAUDIO_REFERENCE_ID`
- `IMAGE_ENGINE=imagen` + `GEMINI_API_KEY`

## Phase 1 — OpenClaw agents

The pipeline is also wrapped as 5 OpenClaw skills in `openclaw-skills/`,
installed into the agent workspace with:

```bash
openclaw skills install ./openclaw-skills/<name> --as <name> --force
```

`yt-content-analyst` → `yt-scriptwriter` → `yt-asset-gatherer` → `yt-editor`
chain automatically when you ask the OpenClaw agent to run the pipeline for
a topic. Verified working end-to-end.

## Phase 2 — Approval gateway + upload

**1. WhatsApp approval channel** (`yt-approval-gateway`) — ✅ done and
   verified end-to-end: a real pipeline run rendered a video and it arrived
   for approval on WhatsApp with no proxy needed.

**2. YouTube Data API upload** (`yt-uploader`, blocked on missing
   `client_secret.json`):
   - In [Google Cloud Console](https://console.cloud.google.com/): create a
     project, enable **YouTube Data API v3**, configure the OAuth consent
     screen, create an **OAuth client ID → Desktop app**.
   - Download it as `client_secret.json` into this project's root
     (`youtube-pipeline/client_secret.json` — never commit this or
     `token.json` to version control if you set up git later).
   - First upload attempt opens a one-time browser consent screen; after
     that, `token.json` caches the refresh token so it's unattended.
   - Uploads default to `--privacy private` as a deliberate second safety
     margin beyond the WhatsApp approval step — you flip to public
     yourself once you've reviewed the live listing.
