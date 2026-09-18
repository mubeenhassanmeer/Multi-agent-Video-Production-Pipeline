"""Stage 3: produce the scene images for a video.

Each scene gets ceil(scene_duration / IMAGE_CADENCE_SECONDS) images instead
of a single image for the whole scene, so the visual actually changes every
~2.5-3s the way a professionally edited video does. Images are numbered
scene_{i:03d}_img_{j:02d}.png so the render stage can lay them out in the
exact right order and duration for perfect audio sync.

Phase 0/1 default is a local Pillow-drawn placeholder (no network calls, no
API cost). IMAGE_ENGINE=imagen switches to real generated visuals via the
Gemini API's image-capable model (see _generate_imagen).
"""
import base64
import colorsys
import textwrap
import time
from pathlib import Path
from typing import List

import requests
from PIL import Image, ImageDraw, ImageFont

from . import config


def _font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _color_for_index(index: int) -> tuple:
    hue = (index * 0.13) % 1.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.55, 0.35)
    return (int(r * 255), int(g * 255), int(b * 255))


def _generate_placeholder(index: int, prompt: str, out_path: Path) -> None:
    w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    base = _color_for_index(index)
    accent = tuple(min(255, c + 60) for c in base)

    img = Image.new("RGB", (w, h), base)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        blend = tuple(int(base[i] * (1 - t) + accent[i] * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=blend)

    label = f"IMAGE {index + 1:03d}  ·  placeholder (swap in real Imagen later)"
    draw.text((40, 40), label, font=_font(28), fill=(255, 255, 255))

    wrapped = textwrap.fill(prompt, width=36)
    font = _font(56)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.multiline_text(
        ((w - tw) / 2, (h - th) / 2), wrapped, font=font,
        fill=(255, 255, 255), align="center",
    )
    img.save(out_path)


def _generate_imagen(prompt: str, out_path: Path) -> None:
    """Real image generation via the Gemini API's image-capable model.

    Google's original Imagen-specific endpoint was discontinued; this uses
    the standard generateContent endpoint with an image-capable model, which
    is the current supported way to generate images (see config.py note).
    """
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set -- get one at https://aistudio.google.com")

    full_prompt = f"{config.IMAGE_MASTER_PROMPT}, {prompt}" if config.IMAGE_MASTER_PROMPT else prompt

    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{config.IMAGEN_MODEL}:generateContent",
        headers={"x-goog-api-key": config.GEMINI_API_KEY, "Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": full_prompt}]}]},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    parts = data["candidates"][0]["content"]["parts"]
    image_part = next((p for p in parts if "inlineData" in p), None)
    if image_part is None:
        raise RuntimeError(f"No image returned for prompt {full_prompt!r}: {data}")

    image_bytes = base64.b64decode(image_part["inlineData"]["data"])
    out_path.write_bytes(image_bytes)


def _generate_one(index: int, prompt: str, out_path: Path) -> None:
    if config.IMAGE_ENGINE == "placeholder":
        _generate_placeholder(index, prompt, out_path)
        return
    if config.IMAGE_ENGINE != "imagen":
        raise ValueError(f"Unknown IMAGE_ENGINE: {config.IMAGE_ENGINE}")

    last_error = None
    for attempt in range(1, config.IMAGE_MAX_RETRIES + 1):
        try:
            _generate_imagen(prompt, out_path)
            return
        except Exception as e:  # noqa: BLE001 -- deliberately broad: any failure retries
            last_error = e
            if attempt < config.IMAGE_MAX_RETRIES:
                time.sleep(2 ** attempt)  # 2s, 4s, 8s backoff

    # All retries exhausted -- don't kill the whole run over one image.
    print(f"WARNING: image {index} failed after {config.IMAGE_MAX_RETRIES} attempts "
          f"({last_error!r}); using a placeholder instead.")
    _generate_placeholder(index, prompt, out_path)


def generate_images(scenes: List[dict], scene_durations: List[float], scene_dir: Path) -> List[List[Path]]:
    """One list of image paths per scene, sized by IMAGE_CADENCE_SECONDS.

    Returns a list-of-lists (one inner list per scene, in on-screen order) so
    the render stage knows exactly how to split each scene's audio duration
    across its images.
    """
    scene_dir.mkdir(parents=True, exist_ok=True)
    global_index = 0
    per_scene_paths: List[List[Path]] = []

    for scene_idx, (scene, duration) in enumerate(zip(scenes, scene_durations)):
        num_images = max(1, round(duration / config.IMAGE_CADENCE_SECONDS))
        scene_paths = []
        for sub_idx in range(num_images):
            out_path = scene_dir / f"scene_{scene_idx:03d}_img_{sub_idx:02d}.png"
            _generate_one(global_index, scene["image_prompt"], out_path)
            scene_paths.append(out_path)
            global_index += 1
        per_scene_paths.append(scene_paths)

    return per_scene_paths
