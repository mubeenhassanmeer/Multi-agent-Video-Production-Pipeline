"""Stage 2: synthesize per-scene narration audio.

Each scene gets its own WAV file so its exact spoken duration is known
directly -- later stages size each scene's on-screen time to match its real
audio length instead of dividing total duration evenly across scenes.
"""
import time
import wave
from pathlib import Path
from typing import List

from . import config


class ConfigError(Exception):
    """A missing/invalid setting -- retrying won't help, unlike a transient API error."""


def _synthesize_piper(text: str, out_path: Path) -> None:
    from piper import PiperVoice, SynthesisConfig

    # Cache the loaded voice across calls in this process.
    if not hasattr(_synthesize_piper, "_voice"):
        _synthesize_piper._voice = PiperVoice.load(config.PIPER_MODEL_PATH)
    voice = _synthesize_piper._voice

    syn_config = SynthesisConfig()
    with wave.open(str(out_path), "wb") as wav_file:
        voice.synthesize_wav(text, wav_file, syn_config=syn_config)


def _synthesize_elevenlabs(text: str, out_path: Path) -> None:
    import requests

    if not config.ELEVENLABS_API_KEY or not config.ELEVENLABS_VOICE_ID:
        raise ConfigError("ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID not set.")

    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}",
        headers={"xi-api-key": config.ELEVENLABS_API_KEY},
        json={"text": text, "model_id": config.ELEVENLABS_MODEL_ID},
        timeout=120,
    )
    resp.raise_for_status()
    out_path.write_bytes(resp.content)  # ElevenLabs returns mp3 by default


def _synthesize_fishaudio(text: str, out_path: Path) -> None:
    import requests

    if not config.FISHAUDIO_API_KEY:
        raise ConfigError("FISHAUDIO_API_KEY not set.")

    body = {"text": text, "format": "mp3"}
    if config.FISHAUDIO_REFERENCE_ID:
        body["reference_id"] = config.FISHAUDIO_REFERENCE_ID

    resp = requests.post(
        "https://api.fish.audio/v1/tts",
        headers={
            "Authorization": f"Bearer {config.FISHAUDIO_API_KEY}",
            "Content-Type": "application/json",
            "model": config.FISHAUDIO_MODEL,
        },
        json=body,
        timeout=120,
    )
    resp.raise_for_status()
    out_path.write_bytes(resp.content)


def _synthesize_one(engine: str, text: str, out_path: Path) -> None:
    if engine == "piper":
        _synthesize_piper(text, out_path)
        return

    last_error = None
    for attempt in range(1, config.TTS_MAX_RETRIES + 1):
        try:
            if engine == "elevenlabs":
                _synthesize_elevenlabs(text, out_path)
            elif engine == "fishaudio":
                _synthesize_fishaudio(text, out_path)
            else:
                raise ValueError(f"Unknown TTS_ENGINE: {engine}")
            return
        except (ValueError, ConfigError):
            raise  # not retryable -- a real config error, not a transient one
        except Exception as e:  # noqa: BLE001 -- broad on purpose: any transient failure retries
            last_error = e
            if attempt < config.TTS_MAX_RETRIES:
                wait = 5 * attempt  # 5s, 10s, 15s... gentler than exponential for rate limits
                print(f"WARNING: TTS call failed (attempt {attempt}/{config.TTS_MAX_RETRIES}): "
                      f"{e!r}; retrying in {wait}s")
                time.sleep(wait)

    raise RuntimeError(f"TTS synthesis failed after {config.TTS_MAX_RETRIES} attempts") from last_error


def synthesize_scenes(scenes: List[dict], scene_dir: Path) -> List[Path]:
    """Synthesize one audio file per scene. Returns list of file paths in order."""
    scene_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, scene in enumerate(scenes):
        ext = "wav" if config.TTS_ENGINE == "piper" else "mp3"
        out_path = scene_dir / f"scene_{i:03d}.{ext}"
        _synthesize_one(config.TTS_ENGINE, scene["narration"], out_path)
        paths.append(out_path)
    return paths
