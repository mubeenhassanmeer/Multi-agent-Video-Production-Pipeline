"""Local control center: a small web form for tuning the pipeline's
non-secret, frequently-adjusted settings (TTS engine/voice, image cadence,
master prompt, background music) without editing .env or restarting
anything. Writes pipeline_config.json, which config.py reads on every run.

Tunable settings above the "Add an API key" section are non-secret and
saved to pipeline_config.json. The "Add an API key" section writes
directly to .env instead (never to pipeline_config.json, which is meant to
be safe to commit) -- values are write-only: once saved, this page never
displays them back, only whether each var is currently set.

    python -m pipeline.control_center
    -> http://127.0.0.1:5057
"""
import json
import re

import requests
from flask import Flask, redirect, request

from . import config

ENV_PATH = config.ROOT_DIR / ".env"
ENV_VAR_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Known vars we show set/unset status for. Any other name is still
# accepted (that's the point -- "add an API key for any model manually")
# and just won't get a friendly label.
KNOWN_ENV_VARS = {
    "OPENROUTER_API_KEY": "OpenRouter (scriptwriting LLM)",
    "ELEVENLABS_API_KEY": "ElevenLabs (voice)",
    "FISHAUDIO_API_KEY": "Fish Audio (voice)",
    "GEMINI_API_KEY": "Gemini API (Imagen-successor images)",
    "POLLINATIONS_API_KEY": "Pollinations.ai (images)",
}


def _read_env_lines() -> list:
    if ENV_PATH.exists():
        return ENV_PATH.read_text().splitlines()
    return []


def _env_is_set(name: str) -> bool:
    for line in _read_env_lines():
        if line.startswith(f"{name}=") and line.split("=", 1)[1].strip():
            return True
    return False


def _set_env_var(name: str, value: str) -> None:
    lines = _read_env_lines()
    out, found = [], False
    for line in lines:
        if line.startswith(f"{name}="):
            out.append(f"{name}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{name}={value}")
    ENV_PATH.write_text("\n".join(out) + "\n")

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
  hr {{ margin: 32px 0; border: none; border-top: 1px solid #ddd; }}
  .status {{ font-size: 0.85rem; margin: 4px 0; }}
  .status .set {{ color: #1a7f37; }}
  .status .unset {{ color: #999; }}
</style>
<h1>Pipeline Control Center</h1>
<p class="hint">Non-secret settings only below. API keys stay in .env, set via the section at the bottom.</p>
<form method="post" action="/save">
{fields}
  <button type="submit">Save</button>
</form>
<p class="note">Saved to <code>pipeline_config.json</code> (safe to commit, no secrets) and picked up
by the next pipeline run -- no restart needed for CLI runs; the OpenClaw agent picks it up on its
next stage call too.</p>

<hr>
<h1>Add an API key</h1>
<p class="hint">Writes directly to <code>.env</code> (not <code>pipeline_config.json</code> --
never committed to git). Works for any provider, not just the ones this pipeline already knows
about -- e.g. add a key for a different model/provider you want to wire in later. Values are
write-only: this page never displays a saved value back, only whether it's set.</p>
<div class="status">{env_status}</div>
<form method="post" action="/set-env">
  <label>Variable name<span class="hint"> - e.g. OPENROUTER_API_KEY, or any name for a new provider</span></label>
  <input type="text" name="env_name" placeholder="SOME_PROVIDER_API_KEY" pattern="[A-Z][A-Z0-9_]*" required>
  <label>Value</label>
  <input type="password" name="env_value" placeholder="paste the key here" required>
  <button type="submit">Save to .env</button>
</form>
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


def _env_status_html() -> str:
    rows = []
    for name, label in KNOWN_ENV_VARS.items():
        is_set = _env_is_set(name)
        cls = "set" if is_set else "unset"
        mark = "✅ set" if is_set else "✗ not set"
        rows.append(f'<div class="{cls}">{name} ({label}): {mark}</div>')
    return "".join(rows)


@app.route("/")
def index():
    fields_html = "".join(_render_field(*f) for f in FIELDS)
    return PAGE.format(fields=fields_html, env_status=_env_status_html())


@app.route("/set-env", methods=["POST"])
def set_env():
    name = request.form.get("env_name", "").strip().upper()
    value = request.form.get("env_value", "")
    if not ENV_VAR_NAME_RE.match(name):
        return "Invalid variable name -- must be UPPER_SNAKE_CASE starting with a letter.", 400
    if not value:
        return "Value cannot be empty.", 400
    _set_env_var(name, value)
    return redirect("/")


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
