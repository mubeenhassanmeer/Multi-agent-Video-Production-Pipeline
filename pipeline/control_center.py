"""Local control center: a small web form for tuning the pipeline's
non-secret, frequently-adjusted settings (TTS engine/voice, image cadence,
master prompt, background music) without editing .env or restarting
anything. Writes pipeline_config.json, which config.py reads on every run.

API keys are NOT edited here -- they stay in .env only, so this page stays
safe to leave running/screen-share.

    python -m pipeline.control_center
    -> http://127.0.0.1:5057
"""
from flask import Flask, redirect, request

from . import config

app = Flask(__name__)

FIELDS = [
    ("TTS_ENGINE", "select", ["piper", "elevenlabs", "fishaudio"]),
    ("ELEVENLABS_VOICE_ID", "text", None),
    ("ELEVENLABS_MODEL_ID", "text", None),
    ("FISHAUDIO_REFERENCE_ID", "text", None),
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
    "ELEVENLABS_VOICE_ID": "from your ElevenLabs voice library",
    "FISHAUDIO_REFERENCE_ID": "leave blank to use the base model voice",
}


def _current(key: str, default: str = "") -> str:
    overrides = config._load_overrides()
    if key in overrides:
        return str(overrides[key])
    value = getattr(config, key, default)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _render_field(name: str, kind: str, options) -> str:
    value = _current(name)
    hint = f'<span class="hint"> - {HINTS[name]}</span>' if name in HINTS else ""
    label = f'<label>{name}{hint}</label>'
    if kind == "select":
        opts = "".join(
            f'<option value="{o}"{" selected" if o == value else ""}>{o}</option>' for o in options
        )
        return f'{label}<select name="{name}">{opts}</select>'
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
    config.CONTROL_CENTER_CONFIG_PATH.write_text(__import__("json").dumps(overrides, indent=2))
    return redirect("/")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5057, debug=False)
