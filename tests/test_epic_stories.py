"""Epic-story episodes: episode rules, storyboard mapping, the cast registry and voice pitch."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest

from services.common import paths
from services.common.rules import check_storyboard
from services.host import epic_cast
from services.story import epic

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "epics" / "arjun-chidiya-ki-aankh.episode.json"


def sample() -> epic.Episode:
    return epic.Episode.model_validate_json(SAMPLE.read_text(encoding="utf-8"))


def test_the_sample_episode_is_valid_and_its_captions_match_the_speech_word_for_word():
    ep = sample()
    assert epic.check_episode(ep) == []
    sb = epic.to_storyboard(ep)
    assert check_storyboard(sb) == []  # includes the sentence and word count match for Devanagari narration
    for b in ep.beats:
        assert re.search(r"[ऀ-ॿ]", b.text) and not re.search(r"[ऀ-ॿ]", b.caption + b.title)


def test_storyboard_stages_narration_and_lines_with_voices_acting_and_backdrop():
    sb = epic.to_storyboard(sample())
    assert sb.style == "epic" and sb.presenter.model == "models/narada.vrm" and sb.voice.voice == "hm_psi" and sb.voice.pitch == 1.14
    assert [s.kind for s in sb.scenes] == ["hook"] + ["dialogue"] * 7 + ["payoff"]
    told, spoken = sb.scenes[1], sb.scenes[3]
    assert told.data["speaker"] == "narrator" and told.voice is None  # narrated: the storyboard's narrator voice
    assert spoken.data["speaker"] == "drona" and (spoken.voice.voice, spoken.voice.pitch) == ("hm_omega", 0.9)
    assert [m["model"] for m in spoken.data["cast"]] == ["models/drona.vrm", "models/arjuna.vrm"]
    assert spoken.data["emotes"] == {"drona": "stern", "arjuna": "shock"} and spoken.data["gestures"] == {"drona": "point"}
    assert all(s.data["backdrop"] == "gurukul" for s in sb.scenes) and sb.scenes[-1].cta == epic.CTA_TEXT


@pytest.mark.parametrize("mutate, expected", [
    (lambda e: e.cast.append("krishna"), "exactly two characters"),
    (lambda e: setattr(e, "narrator", "gandalf"), "unknown character 'gandalf'"),
    (lambda e: setattr(e, "backdrop", "moon"), "unknown backdrop"),
    (lambda e: setattr(e.beats[3], "speaker", "krishna"), "must be spoken by someone on stage"),
    (lambda e: e.beats[3].emotes.update(drona="sneeze"), "emote drona=sneeze"),
    (lambda e: e.beats[3].gestures.update(drona="cartwheel"), "gesture drona=cartwheel"),
    (lambda e: e.beats.pop(), "ends with one moral"),
])
def test_episode_rules_catch_each_problem(mutate, expected):
    ep = sample()
    mutate(ep)
    assert any(expected in p for p in epic.check_episode(ep)), epic.check_episode(ep)


def test_save_refuses_a_bad_episode_and_writes_a_good_one(tmp_path):
    ep = sample()
    result = epic.save(ep, tmp_path, build_models=False)
    assert json.loads(Path(result["storyboard"]).read_text(encoding="utf-8"))["style"] == "epic"
    ep.beats[1].caption = "Too short."
    with pytest.raises(RuntimeError, match="house rules"):
        epic.save(ep, tmp_path / "x", build_models=False)


def test_python_cast_and_the_video_engine_registry_list_the_same_characters():
    ts = (ROOT / "video-engine" / "src" / "design" / "epicCast.ts").read_text(encoding="utf-8")
    block = ts.split("export const EPIC_CAST", 1)[1].split("};", 1)[0]
    assert set(re.findall(r"^\s{2}(\w+): \{ props", block, re.M)) == set(epic_cast.CAST)
    ts_emotes = set(re.findall(r"^\s{2}(\w+): \{", ts.split("export const EMOTES", 1)[1].split("};", 1)[0], re.M))
    assert ts_emotes == set(epic.EMOTES)
    assert set(re.findall(r'"(\w+)"', ts.split("export type Gesture =", 1)[1].split(";", 1)[0])) == set(epic.GESTURES)
    for name, spec in epic_cast.CAST.items():
        assert spec["base"] in epic_cast.BASES and spec["voice"][:2] in ("hm", "hf") and 0.7 <= spec.get("pitch", 1.0) <= 1.3


def test_recolour_keeps_shading_and_swaps_the_colour():
    from PIL import Image

    grad = np.tile(np.linspace(10, 240, 64, dtype=np.uint8)[None, :, None], (8, 1, 3))
    im = Image.fromarray(np.dstack([grad, np.full((8, 64, 1), 255, np.uint8)]), "RGBA")
    out = np.asarray(epic_cast.recolour(im, (40, 80, 200), floor=0.4)).astype(int)
    assert (out[0, :, 2] >= out[0, :, 0]).all() and out[0, -1, 2] > out[0, 0, 2] + 60  # blue, and still shaded
    assert (out[:, :, 3] == 255).all()


def test_pitch_shifts_the_voice_without_changing_the_pace(tmp_path, monkeypatch):
    from services.common.schema import SceneVoice, Storyboard, StoryboardScene
    from services.tts import synthesize as syn
    from services.tts.provider import TTSProvider, TTSResult, WordTiming

    asked = []

    class Fake(TTSProvider):
        name, sample_rate = "fake", 24000

        def available(self):
            return True

        def synthesize(self, text, voice, speed=1.0, caption_text=None):
            asked.append(round(speed, 3))
            n = int(24000 / speed)  # a slower request gives proportionally more audio
            ws = text.split()
            return TTSResult(np.sin(np.arange(n) / 20).astype(np.float32) * 0.3, 24000, [WordTiming(w, i / len(ws) / speed, (i + 1) / len(ws) / speed) for i, w in enumerate(ws)], "fake", voice)

    for attr, sub in (("PUBLIC", "public"), ("ASSETS", "assets"), ("AUDIO_CACHE", "cache"), ("STORYBOARDS", "boards")):
        monkeypatch.setattr(paths, attr, tmp_path / sub)
    monkeypatch.setattr(paths, "ensure_dirs", lambda: [(tmp_path / d).mkdir(exist_ok=True) for d in ("public", "assets", "cache", "boards")])
    monkeypatch.setattr(syn, "get_provider", lambda name, device="auto": Fake())
    scene = lambda i, voice: StoryboardScene(id=f"s{i}", kind="hook" if i == 0 else "payoff", narration="one two three subscribe", voice=voice, cta="Subscribe", minDurationMs=0, leadInMs=0, padAfterMs=0)
    sb = Storyboard(id="p", title="t", caption="subscribe", dmKeyword="SUBSCRIBE", scenes=[scene(0, None), scene(1, SceneVoice(pitch=0.8))])
    spec = syn.synthesize_storyboard(sb, force=True)
    assert asked == [1.05, round(1.05 / 0.8, 3)]  # the deep voice is asked to speak faster, then slowed back down
    a, b = (s.audioEndMs - s.audioStartMs for s in spec.scenes)
    assert abs(a - b) <= 30  # same pace either way
