"""Sarvam TTS provider, exercised with a fake HTTP post (no network, no key)."""
import base64
import io
import json

import numpy as np
import pytest
import soundfile as sf

from services.common.env import load_dotenv
from services.tts.provider import SarvamProvider, get_provider, pick_provider_name


def _wav_b64(seconds: float, sr: int = 24000) -> str:
    n = int(sr * seconds)
    audio = np.zeros(n, dtype=np.float32)
    # 150 ms of silence, then a tone, then 300 ms of silence
    a, b = int(0.15 * sr), n - int(0.3 * sr)
    audio[a:b] = 0.3 * np.sin(np.arange(b - a) * 0.08)
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode("ascii")


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_sarvam_synthesizes_per_sentence_with_estimated_word_timings():
    calls = []

    def post(url, json, headers, timeout):
        calls.append((url, json, headers))
        return FakeResp(200, {"request_id": "r", "audios": [_wav_b64(1.2)]})

    prov = SarvamProvider(api_key="k", model="bulbul:v3", speaker="shubh", language="en-IN", post=post)
    r = prov.synthesize("Coders, be scared. DeepSeek just open-sourced your replacement.", "am_fenrir", 1.05)
    assert len(calls) == 2
    url, body, headers = calls[0]
    assert url == "https://api.sarvam.ai/text-to-speech"
    assert headers["api-subscription-key"] == "k"
    assert body["language_code"] == "en-IN" and body["model"] == "bulbul:v3" and body["speaker"] == "shubh"
    assert body["pace"] == 1.05 and body["output_audio_codec"] == "wav"
    assert r.provider == "sarvam" and r.voice == "shubh" and r.estimated
    assert [w.text for w in r.words] == ["Coders,", "be", "scared.", "DeepSeek", "just", "open-sourced", "your", "replacement."]
    for a, b in zip(r.words, r.words[1:]):
        assert b.start >= a.end - 1e-6
    # silence trimmed: two 1.2 s clips become well under 2.4 s plus the gap
    assert r.duration < 2.2
    assert r.words[-1].end <= r.duration + 1e-6


def test_sarvam_uses_storyboard_voice_when_it_is_not_a_kokoro_id():
    prov = SarvamProvider(api_key="k", speaker="shubh")
    assert prov.resolve_voice("am_fenrir") == "shubh"
    assert prov.resolve_voice("") == "shubh"
    assert prov.resolve_voice("abhilash") == "abhilash"


def test_sarvam_retries_then_raises_on_persistent_error(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    attempts = []

    def post(**kw):
        attempts.append(1)
        return FakeResp(429, {"error": {"code": "rate_limit_exceeded_error"}})

    prov = SarvamProvider(api_key="k", post=post)
    with pytest.raises(RuntimeError, match="HTTP 429"):
        prov.synthesize("Hello there.", "shubh", 1.0)
    assert len(attempts) == 3


def test_sarvam_without_key_is_unavailable_and_explains():
    prov = SarvamProvider(api_key="")
    assert not prov.available()
    with pytest.raises(RuntimeError, match="SARVAM_API_KEY"):
        prov.synthesize("x.", "shubh", 1.0)


def test_provider_switch_precedence(monkeypatch):
    monkeypatch.delenv("VOICE_PROVIDER", raising=False)
    assert pick_provider_name(None, "kokoro") == "kokoro"
    monkeypatch.setenv("VOICE_PROVIDER", "sarvam")
    assert pick_provider_name(None, "kokoro") == "sarvam"
    assert pick_provider_name("kokoro", "sarvam") == "kokoro"
    monkeypatch.setenv("SARVAM_API_KEY", "k")
    assert get_provider("sarvam").name == "sarvam"


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("VOICE_PROVIDER=sarvam\nSARVAM_SPEAKER=rahul   # comment\n# ignored\n", encoding="utf-8")
    monkeypatch.setenv("VOICE_PROVIDER", "kokoro")
    monkeypatch.delenv("SARVAM_SPEAKER", raising=False)
    load_dotenv(env)
    import os

    assert os.environ["VOICE_PROVIDER"] == "kokoro"
    assert os.environ["SARVAM_SPEAKER"] == "rahul"
