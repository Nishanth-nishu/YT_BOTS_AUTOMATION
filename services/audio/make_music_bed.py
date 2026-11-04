"""Generate a deterministic ambient music bed (no samples, no downloads).

The bed is a slow, dark pad: three detuned low oscillators, a fifth above,
a very slow filter sweep made with a moving-average low-pass over pink
noise, and a soft pulse every bar. It sits far under the voiceover.

Usage:
    python services/audio/make_music_bed.py --out video-engine/public/music/ambient_bed.wav --seconds 70 --bpm 84
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48000


def pink_noise(n: int, rng: np.random.Generator) -> np.ndarray:
    """Voss-McCartney style pink noise."""
    rows = 16
    array = np.zeros(n)
    total = np.zeros(n)
    for r in range(rows):
        step = 2**r
        vals = rng.standard_normal(n // step + 1)
        total += np.repeat(vals, step)[:n]
    array = total / rows
    return array / (np.abs(array).max() + 1e-9)


def lowpass_moving(x: np.ndarray, width: int) -> np.ndarray:
    kernel = np.ones(width) / width
    return np.convolve(x, kernel, mode="same")


def pad_voice(freq: float, t: np.ndarray, detune_cents: float, lfo_rate: float, phase: float) -> np.ndarray:
    f = freq * (2 ** (detune_cents / 1200))
    vib = 1 + 0.003 * np.sin(2 * math.pi * lfo_rate * t + phase)
    sig = np.sin(2 * math.pi * f * vib * t)
    sig += 0.35 * np.sin(2 * math.pi * 2 * f * vib * t + 0.4)
    sig += 0.12 * np.sin(2 * math.pi * 3 * f * vib * t + 1.1)
    return sig


def make_bed(seconds: float, bpm: float, seed: int = 7, root_hz: float = 55.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR

    # Slow swell envelope over the whole bed.
    swell = 0.6 + 0.4 * np.sin(2 * math.pi * t / 28 - math.pi / 2)

    left = np.zeros(n)
    right = np.zeros(n)
    for detune, lfo, ph, pan in ((-7, 0.11, 0.0, 0.35), (0, 0.09, 1.3, 0.5), (6, 0.13, 2.4, 0.65)):
        v = pad_voice(root_hz, t, detune, lfo, ph)
        left += v * (1 - pan)
        right += v * pan
    fifth = pad_voice(root_hz * 1.5, t, 2, 0.07, 0.7)
    left += 0.45 * fifth
    right += 0.45 * fifth * 0.9
    octave = pad_voice(root_hz * 2, t, -3, 0.05, 2.0)
    left += 0.25 * octave * 0.9
    right += 0.25 * octave

    # Filtered noise air, sweeping.
    noise = pink_noise(n, rng)
    air = lowpass_moving(noise, 220) * 0.9
    sweep = 0.5 + 0.5 * np.sin(2 * math.pi * t / 19)
    left += 0.28 * air * sweep
    right += 0.28 * np.roll(air, SR // 97) * (1 - sweep)

    # Soft sub pulse every bar (4 beats).
    bar = 60 / bpm * 4
    pulse = np.zeros(n)
    for b in np.arange(0, seconds, bar):
        i0 = int(b * SR)
        length = int(0.9 * SR)
        idx = np.arange(min(length, n - i0))
        env = np.exp(-idx / (0.28 * SR))
        pulse[i0 : i0 + len(idx)] += np.sin(2 * math.pi * root_hz / 2 * idx / SR) * env
    left += 0.5 * pulse
    right += 0.5 * pulse

    stereo = np.stack([left, right], axis=1) * swell[:, None]

    # Fade in / out and normalise to -18 dBFS peak so it never competes with VO.
    fade = int(2.5 * SR)
    ramp = np.linspace(0, 1, fade)
    stereo[:fade] *= ramp[:, None]
    stereo[-fade:] *= ramp[::-1][:, None]
    stereo /= np.abs(stereo).max() + 1e-9
    stereo *= 10 ** (-18 / 20)
    return stereo.astype(np.float32)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=70)
    ap.add_argument("--bpm", type=float, default=84)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, make_bed(args.seconds, args.bpm, args.seed), SR, subtype="PCM_16")
    print(f"wrote {out} ({args.seconds}s @ {args.bpm} bpm)")


if __name__ == "__main__":
    main()
