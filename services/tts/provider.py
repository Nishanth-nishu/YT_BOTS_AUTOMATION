"""TTS provider abstraction.

    TTSProvider
        |-- KokoroProvider   (hexgrad/Kokoro-82M, Apache-2.0, CPU or CUDA, word timestamps)
        |-- PiperProvider    (OHF-Voice piper1-gpl, GPL-3.0, CPU, sentence-level timing only)

Each provider returns 24 kHz (Kokoro) or 22.05 kHz (Piper) mono float32 audio
plus a list of word timings in seconds relative to the start of that audio.
Word timings may be empty, in which case the caption builder falls back to
evenly distributed sentence-level captions.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger("reelforge.tts")


@dataclass
class WordTiming:
    text: str
    start: float
    end: float


@dataclass
class TTSResult:
    audio: np.ndarray  # mono float32
    sample_rate: int
    words: list[WordTiming] = field(default_factory=list)
    provider: str = ""
    voice: str = ""
    synth_seconds: float = 0.0

    @property
    def duration(self) -> float:
        return float(len(self.audio)) / self.sample_rate


class TTSProvider:
    name = "base"
    sample_rate = 24000

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> TTSResult:  # pragma: no cover - interface
        raise NotImplementedError

    def available(self) -> bool:  # pragma: no cover - interface
        return False


# Pronunciation overrides for terms Kokoro's G2P tends to mangle. Applied to
# the text sent to the engine only; captions keep the original spelling.
PRONUNCIATION: dict[str, str] = {
    r"\bLLMs\b": "L L Ms",
    r"\bLLM\b": "L L M",
    r"\bRAG\b": "rag",
    r"\bGPU\b": "G P U",
    r"\bGPUs\b": "G P Us",
    r"\bAPI\b": "A P I",
    r"\bAPIs\b": "A P Is",
    r"\bJSON\b": "jason",
    r"\barXiv\b": "archive",
    r"\bSQL\b": "sequel",
    r"\bnpm\b": "N P M",
    r"\bCUDA\b": "koo-da",
    r"\bPyTorch\b": "pie-torch",
}


def apply_pronunciation(text: str) -> str:
    out = text
    for pattern, replacement in PRONUNCIATION.items():
        out = re.sub(pattern, replacement, out)
    return out


class KokoroProvider(TTSProvider):
    name = "kokoro"
    sample_rate = 24000

    def __init__(self, device: str = "auto", lang_code: str = "a") -> None:
        self.device = device
        self.lang_code = lang_code
        self._pipeline = None

    def available(self) -> bool:
        try:
            import kokoro  # noqa: F401

            return True
        except Exception:  # pragma: no cover
            return False

    def _get(self):
        if self._pipeline is None:
            import torch
            from kokoro import KPipeline

            device = None
            if self.device == "cuda" or (self.device == "auto" and torch.cuda.is_available()):
                device = "cuda"
            elif self.device == "cpu":
                device = "cpu"
            t0 = time.time()
            self._pipeline = KPipeline(lang_code=self.lang_code, repo_id="hexgrad/Kokoro-82M", device=device)
            log.info("Kokoro pipeline ready on %s in %.1fs", device or "auto", time.time() - t0)
        return self._pipeline

    def synthesize(self, text: str, voice: str = "af_heart", speed: float = 1.0) -> TTSResult:
        pipe = self._get()
        spoken = apply_pronunciation(text)
        t0 = time.time()
        chunks: list[np.ndarray] = []
        words: list[WordTiming] = []
        offset = 0.0
        for result in pipe(spoken, voice=voice, speed=speed):
            audio = result.audio.numpy() if hasattr(result.audio, "numpy") else np.asarray(result.audio)
            audio = audio.astype(np.float32)
            for tok in result.tokens or []:
                if tok.start_ts is None or tok.end_ts is None or not tok.text.strip():
                    continue
                words.append(WordTiming(tok.text, offset + float(tok.start_ts), offset + float(tok.end_ts)))
            chunks.append(audio)
            offset += len(audio) / self.sample_rate
        audio_all = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        return TTSResult(audio_all, self.sample_rate, _realign_words(words, text), self.name, voice, time.time() - t0)


class PiperProvider(TTSProvider):
    """Fallback. Requires `pip install piper-tts` and a downloaded .onnx voice."""

    name = "piper"
    sample_rate = 22050

    def __init__(self, model_path: Optional[Path] = None) -> None:
        self.model_path = model_path

    def available(self) -> bool:
        try:
            import piper  # noqa: F401

            return self.model_path is not None and Path(self.model_path).exists()
        except Exception:
            return False

    def synthesize(self, text: str, voice: str = "", speed: float = 1.0) -> TTSResult:
        from piper import PiperVoice  # type: ignore

        t0 = time.time()
        pv = PiperVoice.load(str(self.model_path))
        self.sample_rate = pv.config.sample_rate
        pcm = bytearray()
        for chunk in pv.synthesize(apply_pronunciation(text)):
            pcm.extend(chunk.audio_int16_bytes)
        audio = np.frombuffer(bytes(pcm), dtype=np.int16).astype(np.float32) / 32768.0
        return TTSResult(audio, self.sample_rate, [], self.name, voice or Path(str(self.model_path)).stem, time.time() - t0)


_PUNCT_ONLY = re.compile(r"^[^\w]+$")


def merge_punctuation(words: list[WordTiming]) -> list[WordTiming]:
    """Kokoro emits punctuation as its own tokens. Attach trailing punctuation
    to the previous word and leading punctuation (quotes, brackets) to the
    next word so captions read like text."""
    out: list[WordTiming] = []
    pending_prefix = ""
    for w in words:
        if _PUNCT_ONLY.match(w.text):
            if out and w.text not in ("(", "[", "\u201c", "\""):
                out[-1] = WordTiming(out[-1].text + w.text, out[-1].start, max(out[-1].end, w.end))
            else:
                pending_prefix += w.text
            continue
        out.append(WordTiming(pending_prefix + w.text, w.start, w.end))
        pending_prefix = ""
    return out


def realign_words(words: list[WordTiming], original: str) -> list[WordTiming]:
    """Map engine tokens back onto the original words so captions show the
    original spelling (e.g. "LLM" not "L L M"). Punctuation-only tokens are
    merged first. If counts still diverge, keep engine tokens."""
    merged = merge_punctuation(words)
    originals = [w for w in re.findall(r"\S+", original)]
    if len(originals) == len(merged):
        return [WordTiming(o, w.start, w.end) for o, w in zip(originals, merged)]
    return merged


_realign_words = realign_words


def text_hash(text: str, provider: str, voice: str, speed: float) -> str:
    return hashlib.sha1(json.dumps([text, provider, voice, speed]).encode("utf-8")).hexdigest()[:16]


def get_provider(name: str = "kokoro", device: str = "auto", piper_model: Optional[Path] = None) -> TTSProvider:
    if name == "piper":
        return PiperProvider(piper_model)
    return KokoroProvider(device=device)
