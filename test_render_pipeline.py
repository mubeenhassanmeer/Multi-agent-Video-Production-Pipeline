"""One-off smoke test: proves stages 2-5 (audio, images, captions, render)
work end-to-end using a hand-written stub script, without needing an
OpenRouter key yet. Run from the project root with the venv active:

    python test_render_pipeline.py
"""
from pathlib import Path

from pipeline import config
from pipeline.align_captions import align_words
from pipeline.generate_audio import synthesize_scenes
from pipeline.generate_images import generate_images
from pipeline.render_video import render_video

STUB_SCENES = [
    {
        "narration": "Deep beneath the waves lies a world stranger than fiction.",
        "image_prompt": "a glowing deep sea creature in pitch black ocean water",
    },
    {
        "narration": "Scientists recently found a shipwreck untouched for centuries.",
        "image_prompt": "an old wooden shipwreck covered in coral on the seafloor",
    },
    {
        "narration": "But the strangest discovery was still waiting below.",
        "image_prompt": "a mysterious dark trench disappearing into the abyss",
    },
]


def main():
    run_dir = config.OUTPUT_DIR / "smoke-test"
    run_dir.mkdir(parents=True, exist_ok=True)

    print("[1/4] Synthesizing narration audio")
    audio_paths = synthesize_scenes(STUB_SCENES, run_dir / "audio")

    print("[2/4] Generating placeholder images (cadence-based, multiple per scene)")
    from moviepy import AudioFileClip

    durations = [AudioFileClip(str(p)).duration for p in audio_paths]
    image_paths = generate_images(STUB_SCENES, durations, run_dir / "images")
    total_images = sum(len(imgs) for imgs in image_paths)
    print(f"      -> {total_images} images across {len(STUB_SCENES)} scenes")

    print("[3/4] Aligning word-level captions")
    offsets = [sum(durations[:i]) for i in range(len(durations))]
    scene_words = align_words(audio_paths, offsets)
    total_words = sum(len(w) for w in scene_words)
    print(f"      -> {total_words} words aligned across {len(audio_paths)} scenes")

    print("[4/4] Rendering final video")
    output_path = run_dir / "final.mp4"
    render_video(image_paths, audio_paths, scene_words, output_path)
    print(f"\nDone: {output_path}")


if __name__ == "__main__":
    main()
