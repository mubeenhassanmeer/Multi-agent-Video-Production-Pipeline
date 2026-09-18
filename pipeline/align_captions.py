"""Stage 4: word-level timestamp alignment for burned-in synced captions.

Runs faster-whisper per scene audio file (cheap: each file is a few seconds)
and offsets the resulting word timestamps by that scene's cumulative start
time, so the whole video has one continuous word-timing track.

This works the same way regardless of which TTS engine produced the audio
(Piper now, ElevenLabs later) since it re-transcribes the actual audio
rather than relying on engine-specific alignment metadata.
"""
from pathlib import Path
from typing import List, TypedDict

from faster_whisper import WhisperModel

from . import config


class Word(TypedDict):
    text: str
    start: float  # seconds, offset into the full concatenated video audio
    end: float


_model = None


def _get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(config.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
    return _model


def align_words(audio_paths: List[Path], scene_offsets: List[float]) -> List[List[Word]]:
    """Returns one list of Word dicts per scene, with start/end already
    offset into the full video's timeline (per scene_offsets[i])."""
    model = _get_model()
    per_scene_words: List[List[Word]] = []

    for path, offset in zip(audio_paths, scene_offsets):
        segments, _info = model.transcribe(str(path), word_timestamps=True)
        words: List[Word] = []
        for segment in segments:
            for w in segment.words:
                words.append({
                    "text": w.word.strip(),
                    "start": offset + w.start,
                    "end": offset + w.end,
                })
        per_scene_words.append(words)

    return per_scene_words
