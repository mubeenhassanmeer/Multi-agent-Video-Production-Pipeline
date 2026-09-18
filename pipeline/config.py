"""Central configuration for the pipeline.

Secrets (API keys) come from environment variables only (.env). Tunable,
non-secret settings (TTS engine choice, image cadence, master prompt, etc.)
live in pipeline_config.json, written by the control center (see
pipeline/control_center.py) and readable here without a restart. Env vars
remain the fallback/default for every tunable so the CLI tools keep working
with no control center running.

The control center's "Add an API key" section can also write directly to
.env (never to pipeline_config.json, which stays safe to commit/share) --
see control_center.py for that flow.
"""
import json
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CONTROL_CENTER_CONFIG_PATH = ROOT_DIR / "pipeline_config.json"


def _load_overrides() -> dict:
    if CONTROL_CENTER_CONFIG_PATH.exists():
        try:
            return json.loads(CONTROL_CENTER_CONFIG_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _tunable(key: str, default: str) -> str:
    """Control-center JSON overrides env var, which overrides the default."""
    overrides = _load_overrides()
    if key in overrides and overrides[key] not in (None, ""):
        return str(overrides[key])
    return os.environ.get(key, default)


# --- LLM (scriptwriting) -----------------------------------------------
# "openrouter" or "groq" -- both are OpenAI-compatible chat-completions
# APIs, just different base URL/key/model. OpenRouter's free tier caps at
# 50 requests/day *account-wide* (shared across every free model) unless
# $10 lifetime credit has been purchased; Groq's free tier has no such
# balance gate and is far more generous (verified: 2026-09-18).
LLM_PROVIDER = _tunable("LLM_PROVIDER", "groq")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Set this to the exact free model slug shown on https://openrouter.ai/models
# (filter by "free") -- slugs for free/stealth models change over time, so it
# is intentionally not hardcoded here.
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL = _tunable("GROQ_MODEL", "openai/gpt-oss-120b")

# --- TTS (voiceover) -----------------------------------------------------
# "piper" (free/local), "elevenlabs", or "fishaudio". Switchable live from
# the control center without touching .env.
TTS_ENGINE = _tunable("TTS_ENGINE", "piper")
PIPER_MODEL_PATH = os.environ.get(
    "PIPER_MODEL_PATH", str(ROOT_DIR / "voice" / "en_US-lessac-medium.onnx")
)
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = _tunable("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL_ID = _tunable("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

FISHAUDIO_API_KEY = os.environ.get("FISHAUDIO_API_KEY", "")
FISHAUDIO_REFERENCE_ID = _tunable("FISHAUDIO_REFERENCE_ID", "")
FISHAUDIO_MODEL = _tunable("FISHAUDIO_MODEL", "s2.1-pro-free")

# Retries for one scene's TTS call before giving up on that scene entirely.
# The free Fish Audio tier in particular has a per-minute rate limit that a
# fast back-to-back per-scene loop can hit -- backoff handles that.
TTS_MAX_RETRIES = int(_tunable("TTS_MAX_RETRIES", "4"))

# --- Images (scene visuals) ----------------------------------------------
# "placeholder" (free/local Pillow cards) or "imagen" (Gemini API, real
# generated visuals -- see pipeline/generate_images.py::_generate_imagen).
# Note: Google's original Imagen-specific API endpoint was discontinued;
# image generation now goes through the same Gemini generateContent endpoint
# as text, using an image-capable model ("gemini-2.5-flash-image", aka
# "Nano Banana"). The setting name stays IMAGE_ENGINE/"imagen" since that's
# the concept (real AI-generated visuals vs local placeholders); only the
# underlying model id changed.
IMAGE_ENGINE = _tunable("IMAGE_ENGINE", "placeholder")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
IMAGEN_MODEL = _tunable("IMAGEN_MODEL", "gemini-2.5-flash-image")

# Pollinations.ai: fully free, no signup needed to generate at all, but the
# "nologo" watermark-removal flag specifically requires a free (not paid)
# registered account -- get a key at https://enter.pollinations.ai
POLLINATIONS_API_KEY = os.environ.get("POLLINATIONS_API_KEY", "")

# A style anchor prepended to every scene's image_prompt so all images in a
# video look like they belong to the same shoot/art style, not a random grab
# bag. Editable from the control center.
IMAGE_MASTER_PROMPT = _tunable("IMAGE_MASTER_PROMPT", "")

# One image is shown on screen for roughly this many seconds -- controls how
# many images get generated per scene (scene_duration / this, rounded).
IMAGE_CADENCE_SECONDS = float(_tunable("IMAGE_CADENCE_SECONDS", "2.75"))

# Some providers cap how many images can be requested per call; the pipeline
# batches generation into chunks of this size regardless of provider.
IMAGES_PER_BATCH = int(_tunable("IMAGES_PER_BATCH", "5"))

# Retries for a single image generation call before giving up on that one
# image and substituting a placeholder so one bad call doesn't kill a run.
IMAGE_MAX_RETRIES = int(_tunable("IMAGE_MAX_RETRIES", "3"))

# --- Captions --------------------------------------------------------------
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")

# --- Background music ------------------------------------------------------
MUSIC_ENABLED = _tunable("MUSIC_ENABLED", "true").lower() == "true"
MUSIC_LIBRARY_DIR = Path(os.environ.get("MUSIC_LIBRARY_DIR", str(ROOT_DIR / "music")))
MUSIC_VOLUME = float(_tunable("MUSIC_VOLUME", "0.12"))  # relative to voiceover at 1.0

# --- Video ------------------------------------------------------------------
VIDEO_WIDTH = int(os.environ.get("VIDEO_WIDTH", "1920"))
VIDEO_HEIGHT = int(os.environ.get("VIDEO_HEIGHT", "1080"))
FPS = int(os.environ.get("FPS", "30"))

OUTPUT_DIR = ROOT_DIR / "output"
