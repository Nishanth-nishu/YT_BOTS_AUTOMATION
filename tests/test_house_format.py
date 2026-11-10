"""House format: content rules, Hinglish word timing, presenter envelope."""
import json
from pathlib import Path

import numpy as np

from services.common.rules import check_storyboard, split_sentences
from services.common.schema import Storyboard
from services.tts.provider import estimate_word_timings, lang_for_voice, text_hash, voiced_span
from services.tts.synthesize import mouth_envelope

ROOT = Path(__file__).resolve().parents[1]


def _sb(**over):
    base = {
        "id": "t", "title": "t", "caption": "Kuch bhi. Comment karo LETS GO.", "sources": ["https://example.com/x"],
        "scenes": [
            {"id": "hook", "kind": "hook", "narration": "Coders, डर जाओ। Ye reel skip mat karna.", "captionText": "Coders, dar jao. Ye reel skip mat karna.", "title": "Dar jao"},
            {"id": "end", "kind": "payoff", "narration": "Comment LETS GO.", "cta": "Comment LETS GO"},
        ],
    }
    base.update(over)
    return Storyboard.model_validate(base)


def test_rules_pass_on_clean_storyboard():
    assert check_storyboard(_sb()) == []


def test_rules_catch_links_devanagari_hook_length_and_keyword():
    sb = _sb(caption="Link: https://github.com/x/y")
    probs = check_storyboard(sb)
    assert any("caption contains a link" in p for p in probs)
    assert any("never asks for the keyword" in p for p in probs)
    sb = _sb()
    sb.scenes[0].title = "डर जाओ"
    assert any("Devanagari on screen" in p for p in check_storyboard(sb))
    sb = _sb()
    sb.scenes[0].narration = " ".join(["word"] * 19)
    sb.scenes[0].captionText = None
    assert any("hook narration is 19 words" in p for p in check_storyboard(sb))
    sb = _sb()
    sb.scenes[0].data = {"command": "git clone https://github.com/x/y"}
    assert any("on-screen text contains a link" in p for p in check_storyboard(sb))


def test_rules_require_matching_caption_text():
    sb = _sb()
    sb.scenes[0].captionText = None
    assert any("no romanised captionText" in p for p in check_storyboard(sb))
    sb.scenes[0].captionText = "Coders, dar jao. Ye reel skip mat karna bhai."
    assert any("spoken words but" in p for p in check_storyboard(sb))
    sb.scenes[0].captionText = "Coders dar jao ye reel skip mat karna."
    assert any("sentences" in p for p in check_storyboard(sb))


def test_split_sentences_handles_danda():
    assert split_sentences("एक। दो. तीन? चार!") == ["एक।", "दो.", "तीन?", "चार!"]


def test_lang_for_voice():
    assert lang_for_voice("hm_omega") == "h"
    assert lang_for_voice("af_heart") == "a"
    assert lang_for_voice("bm_george") == "b"


def test_estimate_word_timings_covers_voiced_span_in_order():
    sr = 24000
    audio = np.zeros(sr * 2, dtype=np.float32)
    audio[int(0.3 * sr) : int(1.5 * sr)] = 0.3 * np.sin(np.arange(int(1.2 * sr)) * 0.1)
    s, e = voiced_span(audio, sr)
    assert 0.25 <= s <= 0.32 and 1.48 <= e <= 1.55
    words = estimate_word_timings(audio, sr, ["Coders,", "dar", "jao."], offset=1.0)
    assert [w.text for w in words] == ["Coders,", "dar", "jao."]
    assert abs(words[0].start - (1.0 + s)) < 1e-6
    assert abs(words[-1].end - (1.0 + e)) < 1e-6
    for a, b in zip(words, words[1:]):
        assert a.end == b.start
    assert words[0].end - words[0].start > words[1].end - words[1].start  # longer word, longer slot


def test_text_hash_changes_with_caption_text():
    assert text_hash("x", "kokoro", "hm_omega", 1.15) != text_hash("x", "kokoro", "hm_omega", 1.15, "y")


def test_mouth_envelope_is_per_frame_in_unit_range():
    sr, fps = 48000, 30
    track = np.zeros(sr * 2, dtype=np.float32)
    track[sr : sr + sr // 2] = 0.5 * np.sin(np.arange(sr // 2) * 0.05)
    env = mouth_envelope(track, sr, fps)
    assert len(env) == 60
    assert all(0.0 <= v <= 1.0 for v in env)
    assert max(env[:28]) == 0.0 and max(env[31:44]) > 0.5


def test_hinglish_storyboard_in_repo_passes_rules():
    sb = Storyboard.model_validate_json((ROOT / "data/storyboards/dsh-superagent-hinglish.json").read_text(encoding="utf-8"))
    assert check_storyboard(sb) == []
    assert sb.voice.voice.startswith("hm_") and sb.presenter.enabled
    timed = ROOT / "data/storyboards/dsh-superagent-hinglish.timed.json"
    if timed.exists():
        spec = json.loads(timed.read_text(encoding="utf-8"))
        assert spec["scenes"][0]["endMs"] <= 5600, "hook must land inside 5 s"
        assert len(spec["presenter"]["envelope"]) >= spec["durationMs"] / 1000 * 30 - 2
