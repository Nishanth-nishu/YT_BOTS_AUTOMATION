"""Turn an epic-story episode into a storyboard: a narrator plus characters acting it out.

    python -m services.story.epic data/epics/<id>.episode.json

An episode is a short retelling of one story from the Mahabharata or Ramayana:

    {"id": "...", "title": "...", "source": "Mahabharata, Adi Parva",
     "narrator": "narada", "cast": ["drona", "arjuna"], "backdrop": "gurukul",
     "kicker": "MAHABHARAT", "caption": "...", "hashtags": ["#mahabharat"],
     "beats": [
       {"role": "hook",  "speaker": "narrator", "text": "...", "caption": "...", "title": "..."},
       {"role": "story", "speaker": "narrator", ...},          narrated, the cast stands on stage
       {"role": "line",  "speaker": "arjuna",   ...},          spoken by a cast member
       {"role": "moral", "speaker": "narrator", ...}]}

`text` is what is spoken, in Devanagari (the Hindi voices need it); `caption`
is the same sentence in Roman letters, sentence for sentence and word for word,
because the on-screen fonts have no Devanagari. Optional per beat: `emotes`
and `gestures` ({character: name}, see video-engine/src/design/epicCast.ts),
`backdrop`, `highlight`.

Characters, their models and voices come from services/host/epic_cast.py; any
model that has not been built yet is built here. The result goes through the
same house rules as every other storyboard.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from services.common import paths
from services.common.rules import check_storyboard
from services.common.schema import MusicConfig, PresenterConfig, SceneVoice, Storyboard, StoryboardScene, VoiceConfig
from services.host import epic_cast

EPICS = paths.DATA / "epics"
BACKDROPS = ("gurukul", "kurukshetra", "palace", "cosmos")
EMOTES = ("shock", "awe", "rage", "stern", "focus", "grin", "smirk", "calm", "sad", "worried")
GESTURES = ("idle", "raise", "point", "bow", "open")
CTA_TEXT = "Subscribe for the next story"


class EpicBeat(BaseModel):
    role: Literal["hook", "story", "line", "moral"]
    speaker: str = "narrator"
    text: str
    caption: str
    title: str
    highlight: list[str] = Field(default_factory=list)
    emotes: dict[str, str] = Field(default_factory=dict)
    gestures: dict[str, str] = Field(default_factory=dict)
    backdrop: Optional[str] = None


class Episode(BaseModel):
    id: str
    title: str
    source: str
    narrator: str = "narada"
    cast: list[str]
    backdrop: str = "gurukul"
    kicker: str = "MAHABHARAT"
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    beats: list[EpicBeat]


def check_episode(ep: Episode) -> list[str]:
    problems: list[str] = []
    known = epic_cast.CAST
    for name in [ep.narrator, *ep.cast]:
        if name not in known:
            problems.append(f"unknown character '{name}' (known: {', '.join(known)})")
    if len(ep.cast) != 2:
        problems.append("the stage holds exactly two characters; put the rest in the narration")
    if ep.backdrop not in BACKDROPS:
        problems.append(f"unknown backdrop '{ep.backdrop}' (use one of {BACKDROPS})")
    roles = [b.role for b in ep.beats]
    if not roles or roles[0] != "hook" or roles[-1] != "moral" or roles.count("hook") != 1 or roles.count("moral") != 1:
        problems.append("an episode starts with one hook and ends with one moral")
    for i, b in enumerate(ep.beats, 1):
        if b.role == "line" and b.speaker not in ep.cast:
            problems.append(f"beat {i}: a line must be spoken by someone on stage ({ep.cast}), not '{b.speaker}'")
        if b.role != "line" and b.speaker != "narrator":
            problems.append(f"beat {i}: a {b.role} beat is spoken by the narrator")
        if b.backdrop and b.backdrop not in BACKDROPS:
            problems.append(f"beat {i}: unknown backdrop '{b.backdrop}'")
        for who, emote in b.emotes.items():
            if who not in ep.cast or emote not in EMOTES:
                problems.append(f"beat {i}: emote {who}={emote} (characters {ep.cast}, emotes {EMOTES})")
        for who, gesture in b.gestures.items():
            if who not in ep.cast or gesture not in GESTURES:
                problems.append(f"beat {i}: gesture {who}={gesture} (characters {ep.cast}, gestures {GESTURES})")
    return problems


def _voice(name: str) -> SceneVoice:
    c = epic_cast.CAST[name]
    return SceneVoice(voice=c["voice"], speed=c.get("speed", 1.0), pitch=c.get("pitch", 1.0))


def to_storyboard(ep: Episode) -> Storyboard:
    people = [{"name": n, "label": epic_cast.CAST[n]["label"], "model": f"models/{n}.vrm"} for n in ep.cast]
    narrator = epic_cast.CAST[ep.narrator]
    scenes: list[StoryboardScene] = []
    for i, b in enumerate(ep.beats, 1):
        data: dict = {"backdrop": b.backdrop or ep.backdrop, "speaker": b.speaker}
        common = dict(id=f"{b.role}{i}", narration=b.text.strip(), captionText=b.caption.strip(), title=b.title.strip(), highlight=b.highlight[:2])
        if b.role == "hook":
            data["kicker"] = f"{ep.kicker} / {ep.source.split(',')[-1].strip().upper()}"
            scenes.append(StoryboardScene(kind="hook", data=data, padAfterMs=250, **common))
        elif b.role == "moral":
            data["kicker"] = "SEEKH"
            scenes.append(StoryboardScene(kind="payoff", data=data, cta=CTA_TEXT, padAfterMs=900, **common))
        else:
            data.update(cast=people, emotes=b.emotes, gestures=b.gestures, kicker=ep.kicker if b.role == "story" else epic_cast.CAST[b.speaker]["label"].upper())
            voice = _voice(b.speaker) if b.role == "line" else None
            scenes.append(StoryboardScene(kind="dialogue", data=data, voice=voice, padAfterMs=260, leadInMs=180, **common))
    caption = (ep.caption.strip() + "\n\n" if ep.caption.strip() else "") + "Subscribe for a new story from the epics."
    return Storyboard(
        id=ep.id, title=ep.title, style="epic",
        voice=VoiceConfig(provider="kokoro", voice=narrator["voice"], speed=narrator.get("speed", 1.0), pitch=narrator.get("pitch", 1.0)),
        presenter=PresenterConfig(name=ep.narrator, mood="hype", look="vrm", model=f"models/{ep.narrator}.vrm"),
        music=MusicConfig(file="music/ambient_bed.wav", volume=0.18, bpm=84),
        caption=caption, hashtags=ep.hashtags or ["#mahabharat", "#hindistory", "#shorts"], sources=[ep.source],
        dmKeyword="SUBSCRIBE", dmLink=None, scenes=scenes)


def save(ep: Episode, out_storyboards: Path | None = None, build_models: bool = True) -> dict:
    problems = check_episode(ep)
    if problems:
        raise RuntimeError("episode rejected:\n- " + "\n- ".join(problems))
    sb = to_storyboard(ep)
    house = check_storyboard(sb)
    if house:
        raise RuntimeError("storyboard breaks the house rules:\n- " + "\n- ".join(house))
    built = []
    if build_models:
        for name in dict.fromkeys([ep.narrator, *ep.cast]):
            if not (epic_cast.MODELS / f"{name}.vrm").exists():
                epic_cast.build(name)
                built.append(name)
    out = (out_storyboards or paths.STORYBOARDS) / f"{ep.id}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sb.model_dump(), indent=1, ensure_ascii=False), encoding="utf-8")
    return {"id": ep.id, "title": ep.title, "scenes": len(sb.scenes), "storyboard": str(out), "models_built": built}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    try:
        ep = Episode.model_validate_json(Path(args[0]).read_text(encoding="utf-8"))
        result = save(ep)
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        print("error:", e, file=sys.stderr)
        return 1
    print(json.dumps(result, indent=1, ensure_ascii=True))
    print(f"\nnext:\n  python -m services.tts.synthesize {result['storyboard']}\n  python -m services.rendering.local_render --spec data/storyboards/{result['id']}.timed.json --profile draft --concurrency 1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
