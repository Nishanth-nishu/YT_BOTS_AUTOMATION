---
name: generate-voiceover
description: Turn a REELFORGE storyboard JSON into a timed ReelSpec with a Kokoro voiceover (male Hinglish host voice hm_omega by default, local CPU or Ada CUDA), per-scene WAVs, word-level captions and the presenter mouth envelope. Use when a storyboard is ready for audio, when narration changed, or when the user says "generate the voiceover", "make the VO", "re-time the scenes".
---

# generate-voiceover

## Purpose
Synthesize narration for every scene, lay the scenes out in time, and write the ReelSpec that the Remotion `Reel` composition renders.

## Trigger
A storyboard exists at `data/storyboards/<id>.json` and has no `.timed.json`, or its narration changed.

## Inputs
- `data/storyboards/<id>.json` (schema: `services/common/schema.py::Storyboard`).
- Voice settings inside it (`voice.provider`, `voice.voice`, `voice.speed`).

## Outputs
- `data/storyboards/<id>.timed.json` and a copy in `video-engine/public/specs/<id>.json` (ReelSpec).
- `video-engine/public/voice/<id>/full.wav` (48 kHz mono, -3 dBFS peak).
- `assets/audio/<id>/scene_<sceneId>.wav` and `words.json`.
- Cache in `assets/audio/cache/<hash>.wav|json` keyed by text, provider, voice, speed.

## Workflow
```bash
.venv\Scripts\python -m services.tts.synthesize data/storyboards/<id>.json --device cpu
```
- `--device cuda` on Ada. `--force` ignores the cache. `--provider piper` for the fallback.
- Pronunciation overrides live in `services/tts/provider.py::PRONUNCIATION` (engine text only; captions keep the original spelling).
- **Hinglish path** (voices `hm_*` / `hf_*`, or any Devanagari in the narration): Kokoro's Hindi pipeline gives no word timestamps, so the provider synthesizes sentence by sentence (split on `।`, `.`, `!`, `?`), trims each sentence's silence to 50 ms lead / 100 ms tail, inserts a 120 ms gap, and spreads each sentence's voiced span over the words of `captionText` by letter count. Captions show `captionText` (romanised). The storyboard must pass `services.common.rules` first (the command refuses otherwise; `--allow-rule-violations` overrides).
- **Presenter envelope**: the spec gets `presenter.envelope`, mouth openness 0..1 per frame (RMS per frame of the full voice track, 92nd percentile = fully open). The Remotion `Presenter` reads it; nothing else to do.
- Pace: the Hindi voice runs about 2.4 words/s after trimming; a 55 s reel is about 125 words. Speed above 1.2 starts to slur.
- Timing: each scene = leadInMs + audio + padAfterMs, at least minDurationMs. Scenes are back to back; `durationMs` is the sum plus 400 ms lead.

## Validation
- The command prints scene start/end times and the caption count. Run `pytest tests/test_schema_and_captions.py` which checks scene contiguity and caption monotonicity.
- Listen check: open `video-engine/public/voice/<id>/full.wav`. If a term is mispronounced, add a `PRONUNCIATION` entry and re-run with `--force`.

## Error handling
- `provider not available`: the venv lacks `kokoro`; run `pip install -r requirements.txt`.
- First run downloads Kokoro-82M (about 330 MB) and the spaCy English model; needs internet once.
- Empty `tokens` (no timestamps) switches the spec to `captionMode: "sentence"` automatically.

## Dependencies
Python venv (`requirements.txt`), Kokoro 0.9.x (Apache-2.0), soundfile, numpy.
