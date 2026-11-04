"""Build Remotion captions from TTS word timings.

Word mode: one Caption per word with exact timestamps (Kokoro).
Sentence mode (fallback): the narration is split into sentences and spread
proportionally to character count over the audio duration.
"""
from __future__ import annotations

import re

from services.common.schema import Caption
from services.tts.provider import WordTiming

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def word_captions(words: list[WordTiming], offset_ms: int) -> list[Caption]:
    out: list[Caption] = []
    for i, w in enumerate(words):
        start = offset_ms + int(round(w.start * 1000))
        end = offset_ms + int(round(w.end * 1000))
        if end <= start:
            end = start + 80
        text = w.text if i == 0 else " " + w.text
        out.append(Caption(text=text, startMs=start, endMs=end, timestampMs=(start + end) // 2, confidence=None))
    return out


def sentence_captions(narration: str, offset_ms: int, duration_ms: int) -> list[Caption]:
    sentences = [s.strip() for s in _SENT_SPLIT.split(narration.strip()) if s.strip()]
    if not sentences:
        return []
    total_chars = sum(len(s) for s in sentences)
    cursor = offset_ms
    out: list[Caption] = []
    for i, s in enumerate(sentences):
        share = len(s) / total_chars
        length = int(duration_ms * share)
        end = cursor + length if i < len(sentences) - 1 else offset_ms + duration_ms
        out.append(Caption(text=(s if i == 0 else " " + s), startMs=cursor, endMs=end, timestampMs=(cursor + end) // 2, confidence=None))
        cursor = end
    return out


def validate_monotonic(captions: list[Caption]) -> list[str]:
    """Return a list of problems (empty when valid)."""
    problems: list[str] = []
    last_end = -1
    for c in captions:
        if c.startMs < last_end - 5:
            problems.append(f"caption '{c.text.strip()}' starts at {c.startMs} before previous end {last_end}")
        if c.endMs <= c.startMs:
            problems.append(f"caption '{c.text.strip()}' has non-positive duration")
        last_end = max(last_end, c.endMs)
    return problems
