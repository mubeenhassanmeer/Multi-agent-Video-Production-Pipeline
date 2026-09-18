"""Local control center: a small web form for tuning the pipeline's
non-secret, frequently-adjusted settings (TTS engine/voice, image cadence,
master prompt, background music) without editing .env or restarting
anything. Writes pipeline_config.json, which config.py reads on every run.

API keys are NOT edited here -- they stay in .env only, so this page stays
safe to leave running/screen-share.

    python -m pipeline.control_center
    -> http://127.0.0.1:5057
"""
import json

import requests
from flask import Flask, redirect, request

from . import config

# Curated, manually vetted subset of Fish Audio's public voice library
# (1000+ entries) -- narration-tagged, generic (not real-person/franchise
# voice clones, to stay clear of publicity-rights issues), verified to
# exist via a live API call before being hardcoded here.
FISHAUDIO_CURATED_VOICES = [
    ("", "(base model voice, no reference)"),
    ("536d3a5e000945adb7038665781a4aca", "Ethan -- male, professional, educational narration"),
    ("b347db033a6549378b48d00acb0d06cd", "Selene -- female, calm, soft narration"),
    ("d8a1340984ee4b63ad1ffae27a6a4339", "ELITE -- male, confident, energetic narration"),
    ("bf322df2096a46f18c579d0baa36f41d", "Adrian -- male, deep, slow narration"),
    ("933563129e564b19a115bedd57b7406a", "Sarah -- female, soft, conversational narration"),
    ("9032b5f2e2554b5a957ad655c052af16", "Slax -- male, deep, educational narration"),
    ("8ec9973300874562962bbcb300f82213", "Guyzo -- male, narration/advertisement"),
]


def _fetch_elevenlabs_voices():
    """Live-fetch the account's actual voice library. Returns None if no
    key is set (so the UI can fall back to a helpful message instead)."""
    if not config.ELEVENLABS_API_KEY:
        return None
    try:
        resp = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": config.ELEVENLABS_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        voices = resp.json().get("voices", [])
        return [("", "(none selected)")] + [
            (v["voice_id"], f'{v["name"]} -- {v.get("category", "")}') for v in voices
        ]
    except Exception:
        return None


app = Flask(__name__)

FIELDS = [
    ("TTS_ENGINE", "select", ["piper", "elevenlabs", "fishaudio"]),
    ("ELEVENLABS_VOICE_ID", "voice_select_elevenlabs", None),
    ("ELEVENLABS_MODEL_ID", "text", None),
    ("FISHAUDIO_REFERENCE_ID", "voice_select_fishaudio", None),
    ("FISHAUDIO_MODEL", "text", None),
    ("IMAGE_ENGINE", "select", ["placeholder", "pollinations", "imagen"]),
    ("IMAGE_CADENCE_SECONDS", "number", None),
    ("IMAGES_PER_BATCH", "number", None),
    ("IMAGE_MAX_RETRIES", "number", None),
    ("IMAGE_MASTER_PROMPT", "textarea", None),
    ("MUSIC_ENABLED", "select", ["true", "false"]),
    ("MUSIC_VOLUME", "number", None),
]

PAGE = """
<!doctype html>
<title>Pipeline Control Center</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 640px; margin: 40px auto; color: #222; }}
  h1 {{ font-size: 1.3rem; }}
  label {{ display: block; margin-top: 16px; font-weight: 600; font-size: 0.9rem; }}
  .hint {{ font-weight: 400; color: #666; font-size: 0.8rem; }}
  input, select, textarea {{ width: 100%; padding: 8px; margin-top: 4px; box-sizing: border-box;
    font-size: 0.95rem; border: 1px solid #ccc; border-radius: 6px; }}
  textarea {{ height: 60px; }}
  button {{ margin-top: 24px; padding: 10px 20px; font-size: 1rem; border: none;
    border-radius: 6px; background: #2e5395; color: white; cursor: pointer; }}
  .note {{ background: #eef2f8; padding: 10px 14px; border-radius: 6px; font-size: 0.85rem; margin-top: 20px; }}
</style>
<h1>Pipeline Control Center</h1>
<p class="hint">Non-secret settings only. API keys stay in .env.</p>
<form method="post" action="/save">
{fields}
  <button type="submit">Save</button>
</form>
<p class="note">Saved to <code>pipeline_config.json</code> and picked up by the next pipeline run
(no restart needed for CLI runs; the OpenClaw agent picks it up on its next stage call too).</p>
"""

HINTS = {
    "IMAGE_CADENCE_SECONDS": "seconds each image stays on screen (e.g. 2.75)",
    "IMAGES_PER_BATCH": "images requested per API batch call (provider limit)",
    "IMAGE_MAX_RETRIES": "retries for one failed image before falling back to a placeholder",
    "IMAGE_MASTER_PROMPT": "style anchor prepended to every scene's image prompt, for a consistent look",
    "MUSIC_VOLUME": "background music volume relative to voiceover (0.0-1.0, e.g. 0.12)",
    "ELEVENLABS_VOICE_ID": "live-fetched from your account if ELEVENLABS_API_KEY is set in .env",
    "FISHAUDIO_REFERENCE_ID": "curated subset -- browse the full 1000+ library at fish.audio/discovery",
}


def _current(key: str, default: str = "") -> str:
    overrides = config._load_overrides()
    if key in overrides:
        return str(overrides[key])
    value = getattr(config, key, default)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _select_html(name: str, value: str, options) -> str:
    opts = "".join(
        f'<option value="{v}"{" selected" if v == value else ""}>{label}</option>' for v, label in options
    )
    return f'<select name="{name}">{opts}</select>'


def _render_field(name: str, kind: str, options) -> str:
    value = _current(name)
    hint = f'<span class="hint"> - {HINTS[name]}</span>' if name in HINTS else ""
    label = f'<label>{name}{hint}</label>'

    if kind == "select":
        opts = "".join(
            f'<option value="{o}"{" selected" if o == value else ""}>{o}</option>' for o in options
        )
        return f'{label}<select name="{name}">{opts}</select>'

    if kind == "voice_select_fishaudio":
        return label + _select_html(name, value, FISHAUDIO_CURATED_VOICES)

    if kind == "voice_select_elevenlabs":
        voices = _fetch_elevenlabs_voices()
        if voices is None:
            return (
                label
                + '<div class="hint">No ELEVENLABS_API_KEY set in .env -- add one to see your '
                  'actual voice library here. Meanwhile, browse voices at '
                  '<a href="https://elevenlabs.io/app/voice-library" target="_blank">elevenlabs.io/app/voice-library</a> '
                  "and enter a voice ID manually below.</div>"
                + f'<input type="text" name="{name}" value="{value}" placeholder="voice_id">'
            )
        return label + _select_html(name, value, voices)

    if kind == "textarea":
        return f'{label}<textarea name="{name}">{value}</textarea>'
    return f'{label}<input type="{kind}" step="any" name="{name}" value="{value}">'


@app.route("/")
def index():
    fields_html = "".join(_render_field(*f) for f in FIELDS)
    return PAGE.format(fields=fields_html)


@app.route("/save", methods=["POST"])
def save():
    overrides = config._load_overrides()
    for name, _kind, _options in FIELDS:
        if name in request.form:
            overrides[name] = request.form[name]
    config.CONTROL_CENTER_CONFIG_PATH.write_text(json.dumps(overrides, indent=2))
    return redirect("/")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5057, debug=False)
