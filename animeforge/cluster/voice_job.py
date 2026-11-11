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

    model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    for s in todo:
        d = out / s["id"]
        d.mkdir(parents=True, exist_ok=True)
        torch.manual_seed(s.get("voice_seed", 1234))
        wav = model.generate(s["line"], language_id="hi", **spec.get("voice_args", {})).detach().cpu()
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)
        torchaudio.save(str(d / "voice.partial.wav"), wav, model.sr, encoding="PCM_S", bits_per_sample=16)
        (d / "voice.partial.wav").rename(d / "voice.wav")
    del model
    torch.cuda.empty_cache()

    from faster_whisper import WhisperModel

    asr = WhisperModel("large-v3", device="cuda", compute_type="float16")
    rows = []
    for s in spec["shots"]:
        f = out / s["id"] / "voice.wav"
        if not f.exists():
            continue
        segs, info = asr.transcribe(str(f), language="hi", beam_size=5)
        heard = " ".join(x.text.strip() for x in segs)
        rows.append({"shot": s["id"], "line": s["line"], "heard": heard, "cer": round(cer(s["line"], heard), 3),
                     "seconds": round(info.duration, 2)})
    (out / "voice_report.json").write_text(json.dumps({"engine": "chatterbox-multilingual", "voice": "built-in",
                                                       "lines": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
