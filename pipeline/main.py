"""Phase 0 entry point: topic in, rendered .mp4 out.

    python -m pipeline.main "3 unexplained phenomena at the bottom of the ocean"

Runs the full chain locally: script -> per-scene audio -> per-scene images ->
word-timestamp alignment -> Ken Burns + captioned render. No upload, no
orchestration -- this proves the render pipeline works before Phase 1 wraps
it in agents.
"""
import argparse
import json
import sys
from pathlib import Path

from . import config
from .align_captions import align_words
from .generate_audio import synthesize_scenes
from .generate_images import generate_images
from .generate_script import generate_script
from .render_video import render_video
from .utils import slugify


def run(topic: str) -> Path:
    run_dir = config.OUTPUT_DIR / slugify(topic)
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] Generating script for: {topic!r}")
    script = generate_script(topic)
    (run_dir / "script.json").write_text(json.dumps(script, indent=2))
    scenes = script["scenes"]
    print(f"      -> title: {script['title']!r}, {len(scenes)} scenes")

    print("[2/5] Synthesizing narration audio per scene")
    audio_paths = synthesize_scenes(scenes, run_dir / "audio")

    print("[3/5] Generating scene images")
    from moviepy import AudioFileClip

    durations = [AudioFileClip(str(p)).duration for p in audio_paths]
    image_paths = generate_images(scenes, durations, run_dir / "images")
    total_images = sum(len(imgs) for imgs in image_paths)
    print(f"      -> {total_images} images across {len(scenes)} scenes")

    print("[4/5] Aligning word-level caption timestamps")
    # Cumulative start offset of each scene, from actual audio durations.
    offsets = [sum(durations[:i]) for i in range(len(durations))]
    scene_words = align_words(audio_paths, offsets)

    print("[5/5] Rendering final video")
    output_path = run_dir / "final.mp4"
    render_video(image_paths, audio_paths, scene_words, output_path)

    print(f"\nDone: {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("topic", help="Video topic / prompt")
    args = parser.parse_args()
    run(args.topic)
