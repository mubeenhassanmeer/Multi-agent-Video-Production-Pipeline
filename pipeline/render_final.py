"""Stage 4 CLI: Editor.

Takes a run directory already populated with audio/ and images/ (from
generate_assets.py) and renders the final captioned, Ken-Burns .mp4.
Standalone entry point so an OpenClaw skill can invoke this stage on its own.

    python -m pipeline.render_final <run_dir>
"""
import itertools
import re
import sys
from pathlib import Path
from typing import List

from moviepy import AudioFileClip

from .align_captions import align_words
from .render_video import render_video

IMAGE_NAME_RE = re.compile(r"^scene_(\d+)_img_(\d+)\.png$")


def _group_images_by_scene(images_dir: Path) -> List[List[Path]]:
    """Reconstruct the per-scene image groups from scene_NNN_img_MM.png names."""
    matches = []
    for p in images_dir.glob("scene_*_img_*.png"):
        m = IMAGE_NAME_RE.match(p.name)
        if m:
            matches.append((int(m.group(1)), int(m.group(2)), p))
    matches.sort(key=lambda t: (t[0], t[1]))

    grouped = []
    for scene_idx, group in itertools.groupby(matches, key=lambda t: t[0]):
        grouped.append([p for _, _, p in group])
    return grouped


def main(run_dir: str) -> None:
    run_dir_path = Path(run_dir)
    audio_paths = sorted((run_dir_path / "audio").glob("scene_*.*"))
    image_paths = _group_images_by_scene(run_dir_path / "images")

    if not audio_paths or not image_paths:
        raise RuntimeError(f"No audio/images found under {run_dir_path}. Run generate_assets first.")
    if len(audio_paths) != len(image_paths):
        raise RuntimeError(
            f"Scene count mismatch: {len(audio_paths)} audio files vs {len(image_paths)} image groups."
        )

    durations = [AudioFileClip(str(p)).duration for p in audio_paths]
    offsets = [sum(durations[:i]) for i in range(len(durations))]
    scene_words = align_words(audio_paths, offsets)

    output_path = run_dir_path / "final.mp4"
    render_video(image_paths, audio_paths, scene_words, output_path)
    print(str(output_path))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m pipeline.render_final <run_dir>")
        sys.exit(1)
    main(sys.argv[1])
