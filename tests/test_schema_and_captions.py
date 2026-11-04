import json
from pathlib import Path

import pytest

from services.captions.build import sentence_captions, validate_monotonic, word_captions
from services.common.schema import ReelSpec, Storyboard
from services.tts.provider import WordTiming, apply_pronunciation, merge_punctuation, realign_words, text_hash

ROOT = Path(__file__).resolve().parents[1]


def test_storyboard_loads_benchmark():
    sb = Storyboard.model_validate_json((ROOT / "data/storyboards/agents-benchmark.json").read_text(encoding="utf-8"))
    assert sb.id == "agents-benchmark"
    assert len(sb.scenes) >= 5
    kinds = {s.kind for s in sb.scenes}
    assert {"hook", "reasoning", "toolCall", "memory", "workflow"} <= kinds


def test_word_captions_offsets_and_spacing():
    words = [WordTiming("Hello", 0.0, 0.3), WordTiming("world", 0.3, 0.6)]
    caps = word_captions(words, 1000)
    assert caps[0].text == "Hello" and caps[1].text == " world"
    assert caps[0].startMs == 1000 and caps[1].endMs == 1600
    assert validate_monotonic(caps) == []


def test_word_captions_fix_zero_duration():
    caps = word_captions([WordTiming("a", 1.0, 1.0)], 0)
    assert caps[0].endMs > caps[0].startMs


def test_sentence_fallback_spans_audio():
    caps = sentence_captions("One. Two three. Four!", 500, 3000)
    assert caps[0].startMs == 500
    assert caps[-1].endMs == 3500
    assert len(caps) == 3
    assert validate_monotonic(caps) == []


def test_validate_monotonic_flags_overlap():
    caps = word_captions([WordTiming("a", 0.0, 1.0), WordTiming("b", 0.5, 1.5)], 0)
    assert validate_monotonic(caps)


def test_pronunciation_overrides_only_engine_text():
    assert apply_pronunciation("The LLM calls an API") == "The L L M calls an A P I"
    assert apply_pronunciation("RAG pipelines") == "rag pipelines"


def test_text_hash_is_stable_and_sensitive():
    a = text_hash("hi", "kokoro", "af_heart", 1.0)
    assert a == text_hash("hi", "kokoro", "af_heart", 1.0)
    assert a != text_hash("hi", "kokoro", "af_heart", 1.1)


@pytest.mark.skipif(not (ROOT / "data/storyboards/agents-benchmark.timed.json").exists(), reason="timed spec not generated")
def test_timed_spec_is_consistent():
    spec = ReelSpec.model_validate_json((ROOT / "data/storyboards/agents-benchmark.timed.json").read_text(encoding="utf-8"))
    assert 20_000 <= spec.durationMs <= 61_000
    assert 0 < spec.scenes[0].startMs <= 1000  # lead silence before the first word
    prev_end = spec.scenes[0].startMs
    for s in spec.scenes:
        assert s.startMs == prev_end
        assert s.audioStartMs >= s.startMs
        assert s.audioEndMs <= s.endMs
        prev_end = s.endMs
    assert prev_end == spec.durationMs
    assert validate_monotonic(spec.captions) == []
    # every caption lies inside some scene's audio window
    for c in spec.captions:
        assert any(s.audioStartMs - 5 <= c.startMs <= s.audioEndMs + 5 for s in spec.scenes), c


def test_merge_punctuation_attaches_to_words():
    words = [WordTiming("It", 0.0, 0.2), WordTiming("isn't", 0.2, 0.5), WordTiming(".", 0.5, 0.55), WordTiming("A", 0.7, 0.8)]
    merged = merge_punctuation(words)
    assert [w.text for w in merged] == ["It", "isn't.", "A"]
    assert merged[1].end == 0.55


def test_realign_restores_original_spelling():
    engine = [WordTiming("The", 0, 0.1), WordTiming("L L M", 0.1, 0.5), WordTiming("runs", 0.5, 0.8), WordTiming(".", 0.8, 0.85)]
    out = realign_words(engine, "The LLM runs.")
    assert [w.text for w in out] == ["The", "LLM", "runs."]
