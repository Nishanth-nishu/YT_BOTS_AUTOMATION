"""Phase 2: Hindi voice benchmark for Chatterbox Multilingual.

Synthesises a fixed set of Hindi lines with the model's built-in voice (no
reference clip, so nobody's voice is cloned), then transcribes each clip with
Whisper and reports the character error rate against the input text. Records
real-time factor and peak VRAM.

    python -m animeforge.cluster.voice_bench --out DIR
"""
from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
from pathlib import Path

LINES = [
    ("narration", "बहुत समय पहले, गुरु द्रोणाचार्य ने अपने शिष्यों की परीक्षा लेने का निश्चय किया।"),
    ("question", "अर्जुन, बताओ, तुम्हें क्या दिखाई दे रहा है?"),
    ("answer", "गुरुदेव, मुझे केवल चिड़िया की आँख दिखाई दे रही है।"),
    ("command", "तो फिर बाण चलाओ!"),
    ("moral", "जिसका लक्ष्य एक होता है, उसका ध्यान भी एक ही होता है।"),
    ("hinglish", "दोस्तों, यह story आपको कैसी लगी? Comment में ज़रूर बताइए।"),
]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[^\w\s]", "", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip().lower()


def cer(ref: str, hyp: str) -> float:
    a, b = norm(ref), norm(hyp)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / max(1, len(a))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--whisper", default="large-v3")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    import torch
    import torchaudio
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    t = time.time()
    model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    load_s = time.time() - t
    rows = []
    torch.cuda.reset_peak_memory_stats()
    for name, text in LINES:
        t = time.time()
        wav = model.generate(text, language_id="hi")
        took = time.time() - t
        wav = wav.detach().cpu()
        if wav.dim() == 1:
            wav = wav.unsqueeze(0)
        path = out / f"{name}.wav"
        torchaudio.save(str(path), wav, model.sr, encoding="PCM_S", bits_per_sample=16)
        dur = wav.shape[-1] / model.sr
        rows.append({"name": name, "text": text, "file": path.name, "audio_seconds": round(dur, 2),
                     "synth_seconds": round(took, 2), "rtf": round(took / dur, 2)})
    peak = torch.cuda.max_memory_allocated() / 2**30
    del model
    torch.cuda.empty_cache()

    from faster_whisper import WhisperModel

    asr = WhisperModel(a.whisper, device="cuda", compute_type="float16")
    for r in rows:
        segs, _ = asr.transcribe(str(out / r["file"]), language="hi", beam_size=5)
        r["heard"] = " ".join(s.text.strip() for s in segs)
        r["cer"] = round(cer(r["text"], r["heard"]), 3)

    report = {"engine": "chatterbox-multilingual", "voice": "built-in default, no reference clip",
              "gpu": torch.cuda.get_device_name(0), "load_seconds": round(load_s, 1),
              "peak_vram_gb": round(peak, 2), "asr": f"faster-whisper {a.whisper}",
              "mean_cer": round(sum(r["cer"] for r in rows) / len(rows), 3),
              "mean_rtf": round(sum(r["rtf"] for r in rows) / len(rows), 2), "lines": rows}
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
