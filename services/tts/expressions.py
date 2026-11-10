"""Per-frame facial expression track for the host, from the tone of the words.

Five VRM preset weights per frame, [happy, angry, sad, relaxed, surprised],
built from:
  1. the scene's mood: `scene.data.expression` ({"preset": ..., "weight": ...})
     or a default by scene kind (hook: surprised, payoff: happy, ...);
  2. the sentence being spoken: "?" lifts surprise towards its end, "!" adds
     intensity, a small lexicon nudges the tone (scared/risk -> angry, free/open -> happy);
  3. highlighted words: a short surprise pulse when one is spoken;
  4. voice energy: loud syllables add a little intensity (brows down);
then smoothed so the face moves naturally. Values are 0..1, rounded to 2 dp.
"""
from __future__ import annotations

import re

import numpy as np

from services.common.schema import Caption, TimedScene

PRESETS = ["happy", "angry", "sad", "relaxed", "surprised"]
IDX = {p: i for i, p in enumerate(PRESETS)}

KIND_DEFAULT: dict[str, tuple[str, float]] = {
    "hook": ("surprised", 0.45),
    "payoff": ("happy", 0.35),
    "chart": ("surprised", 0.25),
    "terminal": ("relaxed", 0.2),
    "code": ("relaxed", 0.2),
    "concept": ("relaxed", 0.15),
    "workflow": ("relaxed", 0.15),
}

LEXICON: dict[str, tuple[str, float]] = {
    r"\b(scared|scary|danger|risk|break|broke|replace|replacement|lose|lost|fail|warning|threat)\b": ("angry", 0.3),
    r"\b(free|open|love|great|easy|win|best|simple|follow|link)\b": ("happy", 0.25),
    r"\b(sad|sorry|gone|dead|dying)\b": ("sad", 0.3),
    r"\b(wow|insane|crazy|huge|massive|everything|nobody|everyone)\b": ("surprised", 0.3),
}

_SENT_END = re.compile(r"[.!?]$")


def _sentences(captions: list[Caption]) -> list[tuple[int, int, str]]:
    """(startMs, endMs, text) per sentence, from the caption words."""
    out: list[tuple[int, int, str]] = []
    start: int | None = None
    words: list[str] = []
    for c in captions:
        text = c.text.strip()
        if not text:
            continue
        if start is None:
            start = c.startMs
        words.append(text)
        if _SENT_END.search(text):
            out.append((start, c.endMs, " ".join(words)))
            start, words = None, []
    if words and start is not None:
        out.append((start, captions[-1].endMs, " ".join(words)))
    return out


def expression_track(scenes: list[TimedScene], captions: list[Caption], envelope: list[float], fps: int, duration_ms: int) -> list[list[float]]:
    n = int(round(duration_ms / 1000 * fps)) + 1
    track = np.zeros((n, len(PRESETS)), dtype=np.float32)
    t_ms = (np.arange(n) / fps) * 1000.0

    # 1. scene mood
    for sc in scenes:
        override = sc.data.get("expression") if isinstance(sc.data, dict) else None
        preset, weight = KIND_DEFAULT.get(sc.kind, ("relaxed", 0.1))
        if isinstance(override, dict) and override.get("preset") in IDX:
            preset, weight = override["preset"], float(override.get("weight", weight))
        mask = (t_ms >= sc.startMs) & (t_ms < sc.endMs)
        track[mask, IDX[preset]] = np.maximum(track[mask, IDX[preset]], weight)

    # 2. sentences
    for s_start, s_end, text in _sentences(captions):
        mask = (t_ms >= s_start) & (t_ms < s_end + 250)
        low = text.lower()
        if text.endswith("?"):
            ramp = np.clip((t_ms - s_start) / max(1.0, (s_end - s_start)), 0, 1)
            track[:, IDX["surprised"]] = np.maximum(track[:, IDX["surprised"]], np.where(mask, 0.15 + 0.35 * ramp, 0))
        if text.endswith("!"):
            track[mask, IDX["angry"]] = np.maximum(track[mask, IDX["angry"]], 0.15)
            track[mask, IDX["happy"]] = np.maximum(track[mask, IDX["happy"]], 0.15)
        for pattern, (preset, w) in LEXICON.items():
            if re.search(pattern, low):
                track[mask, IDX[preset]] = np.maximum(track[mask, IDX[preset]], w)

    # 3. highlighted words: a pulse when spoken
    for sc in scenes:
        hl = {w.lower().strip(".,!?") for w in (sc.highlight or [])}
        if not hl:
            continue
        for c in captions:
            if not (sc.audioStartMs - 5 <= c.startMs <= sc.audioEndMs + 5):
                continue
            if c.text.strip().lower().strip(".,!?\"'") in hl:
                mask = (t_ms >= c.startMs - 80) & (t_ms < c.endMs + 320)
                track[mask, IDX["surprised"]] = np.maximum(track[mask, IDX["surprised"]], 0.4)

    # 4. voice energy -> intensity
    env = np.asarray(envelope, dtype=np.float32)
    if len(env):
        e = np.zeros(n, dtype=np.float32)
        m = min(n, len(env))
        e[:m] = env[:m]
        track[:, IDX["angry"]] = np.maximum(track[:, IDX["angry"]], np.clip((e - 0.65) * 0.5, 0, 0.18))

    # smooth (attack/decay ~5 frames) and keep the total expression modest
    k = np.array([0.1, 0.2, 0.4, 0.2, 0.1], dtype=np.float32)
    for j in range(track.shape[1]):
        track[:, j] = np.convolve(track[:, j], k, mode="same")
    total = track.sum(axis=1, keepdims=True)
    scale = np.where(total > 0.9, 0.9 / np.maximum(total, 1e-6), 1.0)
    track = (track * scale).clip(0, 1)
    return [[round(float(v), 2) for v in row] for row in track]
