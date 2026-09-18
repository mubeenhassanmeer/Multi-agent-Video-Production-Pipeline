"""Stage 3 CLI: Asset Gatherer.

Takes a script.json (produced by generate_script.py) and produces per-scene
audio + cadence-sized image sets in the given run directory. Standalone
entry point so an OpenClaw skill can invoke this stage on its own.

    python -m pipeline.generate_assets <script.json> <run_dir>
"""
import json
import sys
from pathlib import Path

from moviepy import AudioFileClip

from .generate_audio import synthesize_scenes
from .generate_images import generate_images


def main(script_path: str, run_dir: str) -> None:
    script = json.loads(Path(script_path).read_text())
    scenes = script["scenes"]
    run_dir_path = Path(run_dir)

    audio_paths = synthesize_scenes(scenes, run_dir_path / "audio")
    scene_durations = [AudioFileClip(str(p)).duration for p in audio_paths]
    image_paths = generate_images(scenes, scene_durations, run_dir_path / "images")

    print(json.dumps({
        "audio": [str(p) for p in audio_paths],
        "images": [[str(p) for p in scene_imgs] for scene_imgs in image_paths],
        "total_images": sum(len(scene_imgs) for scene_imgs in image_paths),
    }, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m pipeline.generate_assets <script.json> <run_dir>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
