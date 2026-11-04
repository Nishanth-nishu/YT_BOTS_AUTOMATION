"""Turn a storyboard into a timed ReelSpec with voiceover and captions.

For each scene: synthesize narration (cached by text hash), measure its
duration, lay scenes out back to back with lead-in and pad, build the full
voice track, and emit:

    video-engine/public/voice/<reel_id>/full.wav     (48 kHz stereo-safe mono)
    data/storyboards/<reel_id>.timed.json             (ReelSpec for Remotion)
    assets/audio/<reel_id>/scene_<id>.wav + words.json

Usage:
    python -m services.tts.synthesize data/storyboards/agents-benchmark.json [--device cpu|cuda|auto] [--force]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from services.captions.build import sentence_captions, validate_monotonic, word_captions
from services.common import paths
from services.common.schema import Caption, ReelSpec, Storyboard, TimedScene
from services.tts.provider import TTSResult, WordTiming, get_provider, realign_words, text_hash

log = logging.getLogger("reelforge.tts.synthesize")
OUT_SR = 48000


def _resample(audio: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return audio
    n_out = int(round(len(audio) * sr_out / sr_in))
    x_old = np.linspace(0, 1, len(audio), endpoint=False)
    x_new = np.linspace(0, 1, n_out, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def _cached(cache_dir: Path, key: str) -> TTSResult | None:
    wav = cache_dir / f"{key}.wav"
    meta = cache_dir / f"{key}.json"
    if wav.exists() and meta.exists():
        audio, sr = sf.read(wav, dtype="float32")
        m = json.loads(meta.read_text(encoding="utf-8"))
        words = [WordTiming(w["text"], w["start"], w["end"]) for w in m.get("words", [])]
        return TTSResult(audio, sr, words, m.get("provider", ""), m.get("voice", ""), 0.0)
    return None


def _store(cache_dir: Path, key: str, r: TTSResult) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    sf.write(cache_dir / f"{key}.wav", r.audio, r.sample_rate)
    (cache_dir / f"{key}.json").write_text(
        json.dumps({"provider": r.provider, "voice": r.voice, "words": [w.__dict__ for w in r.words]}, indent=1),
        encoding="utf-8",
    )


def synthesize_storyboard(sb: Storyboard, device: str = "auto", force: bool = False, provider_name: str | None = None) -> ReelSpec:
    paths.ensure_dirs()
    provider = get_provider(provider_name or sb.voice.provider, device=device)
    if not provider.available():
        raise RuntimeError(f"TTS provider {provider.name} is not available in this environment")

    voice_dir = paths.PUBLIC / "voice" / sb.id
    voice_dir.mkdir(parents=True, exist_ok=True)
    scene_audio_dir = paths.ASSETS / "audio" / sb.id
    scene_audio_dir.mkdir(parents=True, exist_ok=True)

    cursor_ms = 400  # leading silence before the first word
    track: list[np.ndarray] = [np.zeros(int(OUT_SR * cursor_ms / 1000), dtype=np.float32)]
    captions: list[Caption] = []
    timed: list[TimedScene] = []
    caption_mode = "word"
    total_synth = 0.0

    for scene in sb.scenes:
        key = text_hash(scene.narration, provider.name, sb.voice.voice, sb.voice.speed)
        result = None if force else _cached(paths.AUDIO_CACHE, key)
        if result is None:
            log.info("synthesizing scene %s (%d chars)", scene.id, len(scene.narration))
            result = provider.synthesize(scene.narration, sb.voice.voice, sb.voice.speed)
            _store(paths.AUDIO_CACHE, key, result)
            total_synth += result.synth_seconds
        else:
            log.info("cache hit for scene %s", scene.id)

        result.words = realign_words(result.words, scene.narration)
        audio48 = _resample(result.audio, result.sample_rate, OUT_SR)
        audio_ms = int(round(len(audio48) / OUT_SR * 1000))
        start_ms = cursor_ms
        audio_start = start_ms + scene.leadInMs
        audio_end = audio_start + audio_ms
        end_ms = max(audio_end + scene.padAfterMs, start_ms + scene.minDurationMs)

        track.append(np.zeros(int(OUT_SR * scene.leadInMs / 1000), dtype=np.float32))
        track.append(audio48)
        track.append(np.zeros(int(OUT_SR * (end_ms - audio_end) / 1000), dtype=np.float32))

        sf.write(scene_audio_dir / f"scene_{scene.id}.wav", result.audio, result.sample_rate)
        if result.words:
            captions.extend(word_captions(result.words, audio_start))
        else:
            caption_mode = "sentence"
            captions.extend(sentence_captions(scene.narration, audio_start, audio_ms))

        timed.append(TimedScene(**scene.model_dump(), startMs=start_ms, endMs=end_ms, audioStartMs=audio_start, audioEndMs=audio_end))
        cursor_ms = end_ms

    full = np.concatenate(track)
    # Gentle peak normalisation so the VO sits around -3 dBFS peak.
    peak = float(np.abs(full).max()) or 1.0
    full = full * (10 ** (-3 / 20) / peak)
    sf.write(voice_dir / "full.wav", full, OUT_SR, subtype="PCM_16")

    problems = validate_monotonic(captions)
    if problems:
        log.warning("caption problems: %s", problems[:5])

    spec = ReelSpec(
        id=sb.id,
        title=sb.title,
        style=sb.style,
        durationMs=cursor_ms,
        voice={"file": f"voice/{sb.id}/full.wav", "provider": provider.name, "voice": sb.voice.voice, "speed": sb.voice.speed},
        music=sb.music,
        captions=captions,
        captionMode=caption_mode,  # type: ignore[arg-type]
        scenes=timed,
        caption=sb.caption,
        hashtags=sb.hashtags,
        sources=sb.sources,
    )
    out = paths.STORYBOARDS / f"{sb.id}.timed.json"
    out.write_text(spec.model_dump_json(indent=1), encoding="utf-8")
    # Copy for Remotion Studio (served from public/specs) so previews need no props file.
    spec_pub = paths.PUBLIC / "specs"
    spec_pub.mkdir(parents=True, exist_ok=True)
    (spec_pub / f"{sb.id}.json").write_text(spec.model_dump_json(indent=1), encoding="utf-8")
    (scene_audio_dir / "words.json").write_text(json.dumps([c.model_dump() for c in captions], indent=1), encoding="utf-8")
    log.info("wrote %s (%.1fs, %d captions, synth %.1fs)", out, cursor_ms / 1000, len(captions), total_synth)
    return spec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--provider", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    sb = Storyboard.model_validate_json(Path(args.storyboard).read_text(encoding="utf-8"))
    t0 = time.time()
    spec = synthesize_storyboard(sb, device=args.device, force=args.force, provider_name=args.provider)
    print(json.dumps({"id": spec.id, "durationMs": spec.durationMs, "captions": len(spec.captions), "captionMode": spec.captionMode, "scenes": [(s.id, s.startMs, s.endMs) for s in spec.scenes], "seconds": round(time.time() - t0, 1)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
