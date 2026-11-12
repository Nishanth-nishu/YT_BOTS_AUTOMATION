"""Voice side of an episode: one Hindi clip per shot line, checked by Whisper.

Runs in the TTS environment. Uses Chatterbox Multilingual's built-in voice; no
reference clip is given, so no person's voice is cloned.

    python -m animeforge.cluster.voice_job <episode.json> <out dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from animeforge.cluster.voice_bench import cer

MAX_CER = 0.25   # the same limit the episode review uses


def main() -> None:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = Path(sys.argv[2])
    todo = [s for s in spec["shots"] if s.get("line") and not (out / s["id"] / "voice.wav").exists()]
    if not todo:
        print("voices already made")
        return

    import torch
    import torchaudio
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    from faster_whisper import WhisperModel

    model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    asr = WhisperModel("large-v3", device="cuda", compute_type="float16")

    def hear(f: Path) -> tuple[str, float]:
        segs, info = asr.transcribe(str(f), language="hi", beam_size=5)
        return " ".join(x.text.strip() for x in segs), info.duration

    # The engine sometimes runs on after the line and speaks nonsense (seen 2026-11-12: a 9-word
    # line came back 14 s long, error 1.9). So every take is transcribed, and a bad one is retaken
    # with another seed; the best of up to four takes is kept.
    takes = {}
    for s in todo:
        d = out / s["id"]
        d.mkdir(parents=True, exist_ok=True)
        best = None
        for k in range(4):
            seed = s.get("voice_seed", 1234) + k
            torch.manual_seed(seed)
            wav = model.generate(s["line"], language_id="hi", **spec.get("voice_args", {})).detach().cpu()
            if wav.dim() == 1:
                wav = wav.unsqueeze(0)
            f = d / f"voice.take{k}.wav"
            torchaudio.save(str(f), wav, model.sr, encoding="PCM_S", bits_per_sample=16)
            heard, _ = hear(f)
            err = cer(s["line"], heard)
            if best is None or err < best[0]:
                best = (err, f, seed)
            if err <= MAX_CER:
                break
        best[1].replace(d / "voice.wav")
        for f in d.glob("voice.take*.wav"):
            f.unlink()
        takes[s["id"]] = {"takes": k + 1, "seed": best[2]}

    rows = []
    for s in spec["shots"]:
        f = out / s["id"] / "voice.wav"
        if not f.exists():
            continue
        heard, seconds = hear(f)
        rows.append({"shot": s["id"], "line": s["line"], "heard": heard, "cer": round(cer(s["line"], heard), 3),
                     "seconds": round(seconds, 2), **takes.get(s["id"], {})})
    (out / "voice_report.json").write_text(json.dumps({"engine": "chatterbox-multilingual", "voice": "built-in",
                                                       "lines": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
