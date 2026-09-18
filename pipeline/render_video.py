"""Stage 5: assemble the final .mp4.

Renders one scene at a time to its own small temp .mp4 (Ken Burns images +
that scene's own captions + its own voice track), closing every MoviePy
clip and forcing garbage collection between scenes, then stitches all scene
files together with a stream-copy ffmpeg concat (near-zero memory) and
mixes in background music as a final lightweight ffmpeg pass.

This matters on a memory-constrained machine: building one giant in-memory
composite across every image in a video (which can be 50+ for a 5-minute
video at the default cadence) is what was OOM-killing the whole host.
Peak memory now scales with images-per-scene (~5-8), not total images.
"""
import gc
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    concatenate_videoclips,
)

from . import config
from .align_captions import Word

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Ken Burns zoom range: images are generated at exactly the target
# resolution, so scale never drops below 1.0 -- guarantees no black borders
# at any point during the zoom.
ZOOM_MIN, ZOOM_MAX = 1.0, 1.15


def _ken_burns_clip(image_path: Path, duration: float, zoom_in: bool) -> CompositeVideoClip:
    w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    start, end = (ZOOM_MIN, ZOOM_MAX) if zoom_in else (ZOOM_MAX, ZOOM_MIN)

    def scale_at(t, _start=start, _end=end, _duration=duration):
        return _start + (_end - _start) * (t / _duration)

    base = ImageClip(str(image_path)).with_duration(duration)
    zoomed = base.resized(scale_at).with_position("center")
    return CompositeVideoClip([zoomed], size=(w, h)).with_duration(duration)


def _scene_video_clip(image_paths: List[Path], scene_duration: float, scene_idx: int) -> CompositeVideoClip:
    """Split one scene's duration evenly across its images."""
    n = len(image_paths)
    per_image_duration = scene_duration / n
    clips = [
        _ken_burns_clip(img_path, per_image_duration, zoom_in=((scene_idx + i) % 2 == 0))
        for i, img_path in enumerate(image_paths)
    ]
    if len(clips) == 1:
        return clips[0]
    return concatenate_videoclips(clips, method="compose")


def _caption_clips(words: List[Word]) -> List[TextClip]:
    """words must already have scene-relative (not global-timeline) timestamps."""
    h = config.VIDEO_HEIGHT
    clips = []
    for word in words:
        dur = max(word["end"] - word["start"], 0.05)
        clip = (
            TextClip(
                font=FONT_PATH,
                text=word["text"].upper(),
                font_size=int(h * 0.06),
                color="white",
                stroke_color="black",
                stroke_width=int(h * 0.004) or 2,
                method="label",
            )
            .with_start(word["start"])
            .with_duration(dur)
            .with_position(("center", h * 0.78))
        )
        clips.append(clip)
    return clips


def _render_scene_to_file(
    image_paths: List[Path], audio_path: Path, relative_words: List[Word], scene_idx: int, tmp_dir: Path
) -> tuple:
    w, h = config.VIDEO_WIDTH, config.VIDEO_HEIGHT
    audio_clip = AudioFileClip(str(audio_path))
    duration = audio_clip.duration

    video = _scene_video_clip(image_paths, duration, scene_idx)
    captions = _caption_clips(relative_words)
    composite = CompositeVideoClip([video, *captions], size=(w, h)).with_duration(duration)
    composite = composite.with_audio(audio_clip)

    out_path = tmp_dir / f"scene_{scene_idx:03d}.mp4"
    composite.write_videofile(
        str(out_path), fps=config.FPS, codec="libx264", audio_codec="aac", threads=2, logger=None,
    )

    composite.close()
    video.close()
    audio_clip.close()
    for c in captions:
        c.close()
    del composite, video, captions, audio_clip
    gc.collect()

    return out_path, duration


def _concat_scenes(scene_files: List[Path], output_path: Path) -> None:
    """Stream-copy concat -- all scene files share codec/resolution/fps, so no
    re-encoding is needed and memory use stays minimal."""
    list_path = output_path.parent / "_concat_list.txt"
    list_path.write_text("".join(f"file '{p.resolve()}'\n" for p in scene_files))
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path),
         "-c", "copy", str(output_path)],
        check=True, capture_output=True,
    )
    list_path.unlink()


def _pick_music_track() -> Optional[Path]:
    if not config.MUSIC_ENABLED or not config.MUSIC_LIBRARY_DIR.exists():
        return None
    tracks = [
        p for p in config.MUSIC_LIBRARY_DIR.iterdir()
        if p.suffix.lower() in (".mp3", ".wav", ".m4a") and p.is_file()
    ]
    return random.choice(tracks) if tracks else None


def _mix_background_music(video_path: Path, output_path: Path) -> None:
    music_path = _pick_music_track()
    if music_path is None:
        shutil.move(str(video_path), str(output_path))
        return

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-stream_loop", "-1", "-i", str(music_path),
            "-filter_complex",
            f"[1:a]volume={config.MUSIC_VOLUME}[music];"
            f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=0[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            str(output_path),
        ],
        check=True, capture_output=True,
    )


def render_video(
    image_paths: List[List[Path]],
    audio_paths: List[Path],
    scene_words: List[List[Word]],
    output_path: Path,
) -> Path:
    tmp_dir = Path(tempfile.mkdtemp(prefix="render_scenes_"))
    try:
        scene_files = []
        offset = 0.0
        for scene_idx, (imgs, audio_path, words) in enumerate(zip(image_paths, audio_paths, scene_words)):
            relative_words = [
                {"text": w["text"], "start": w["start"] - offset, "end": w["end"] - offset}
                for w in words
            ]
            scene_file, scene_duration = _render_scene_to_file(imgs, audio_path, relative_words, scene_idx, tmp_dir)
            scene_files.append(scene_file)
            offset += scene_duration

        output_path.parent.mkdir(parents=True, exist_ok=True)
        concat_path = tmp_dir / "concat.mp4"
        _concat_scenes(scene_files, concat_path)
        _mix_background_music(concat_path, output_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return output_path
