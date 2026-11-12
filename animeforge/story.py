"""Story engine: turn a story seed into a checked six-shot episode file.

The Hindi narration lines are written by a person and stored with the seed:
the local 7B model's own Hindi was tried on 2026-11-11 and was wrong and
ungrammatical. The model (Ollama) writes only the English picture plan for each
line: the scene and the action. Character looks are fixed here, so the model
cannot drift a design or name someone else's. The result must pass
`episode.check`; problems go back to the model for another try.

    python -m animeforge.story list
    python -m animeforge.story write <seed id>          # writes cluster/episodes/<id>.json
    python -m animeforge.story queue <seed id> [...]    # write, then queue 'episode' jobs
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import httpx
from pydantic import ValidationError

from animeforge import episode, jobs
from animeforge.config import ROOT

SEEDS_FILE = ROOT / "data" / "epics" / "animeforge_seeds.json"
SHOTS = 6

# One fixed, original look per character. Only characters whose rights are cleared are cast.
LOOKS = {
    "arjuna": "1boy, solo, original, young indian warrior prince, archer, brown skin, long black hair in a topknot, small golden crown, determined eyes, ornate blue and gold armor over white dhoti, red sash, golden armbands",
    "karna": "1boy, solo, original, tall indian warrior, brown skin, shoulder-length black hair, golden earrings, radiant golden breastplate, crimson dhoti, sun emblem, proud calm eyes",
    "krishna": "1boy, solo, original, young indian prince, dark blue-toned skin, curly black hair, peacock feather in a golden crown, yellow silk dhoti, flower garland, gentle smile, flute at waist",
    "bhima": "1boy, solo, original, huge muscular indian warrior, brown skin, thick black hair, short beard, bronze armor plates, green dhoti, heavy mace, fierce grin",
    "abhimanyu": "1boy, solo, original, teenage indian warrior prince, brown skin, short black hair, silver circlet, light silver and teal armor, white dhoti, sword and round shield, brave eyes",
}

SYSTEM = """You plan the pictures for a short Hindi mythology video. The narration lines are already written.
For EACH numbered line, in the same order, describe the picture shown while it is spoken.
Reply with one JSON object and nothing else:
{"shots": [{"shows_hero": true or false,
            "scene": "<English tags: who or what is in the picture, place, light, framing. 8 to 20 words>",
            "action": "<English: one or two sentences saying what moves in a five-second clip and how the camera moves>"}]}
Rules:
- One shot per line: the same number of shots as lines.
- shows_hero is true only when the hero is the main subject. Describe everyone else by role and look
  (an elderly sage teacher, a poor brahmin in a simple dhoti, an old monkey). Never write a person's name in "scene".
- Never name any film, show, game, studio or artist. No gore. No modern objects."""


def seeds() -> list[dict]:
    return json.loads(SEEDS_FILE.read_text(encoding="utf-8"))


def seed(seed_id: str) -> dict:
    for s in seeds():
        if s["id"] == seed_id:
            return s
    raise KeyError(f"no story seed {seed_id!r}")


def extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in the reply")
    return json.loads(m.group(0))


def build(sd: dict, raw: dict) -> episode.EpisodeSpec:
    """Model output plus the fixed look becomes an episode."""
    look = LOOKS[sd["character"]]
    shots = raw.get("shots") or []
    lines = sd["lines"]
    if len(shots) != len(lines):
        raise ValueError(f"need one shot per line: {len(lines)} lines, got {len(shots)} shots")
    out = []
    for i, s in enumerate(shots, 1):
        hero = bool(s.get("shows_hero"))
        scene = str(s["scene"]).strip().strip(",")
        subject = f"{look}, {scene}" if hero else f"original, {scene}"
        consistency = " Consistent face, smooth natural motion." if hero else " Smooth natural motion."
        out.append({"id": f"s{i:02d}", "use_reference": hero, "subject": subject,
                    "motion": f"Anime style. {str(s['action']).strip()}{consistency}", "line": lines[i - 1]})
    return episode.EpisodeSpec.model_validate({
        "id": sd["id"], "title": sd["title"], "source": sd["source"],
        "character": {"id": sd["character"], "tags": look}, "shots": out,
        "caption": sd.get("caption", ""), "hashtags": sd.get("hashtags", [])})


def problems_in(spec: episode.EpisodeSpec, db: Path | None = None) -> list[str]:
    bad = episode.check(spec, db)
    for s in spec.shots:
        words = len(s.line.split())
        if words < 4:
            bad.append(f"{s.id}: line has {words} words; write 6 to 12")
        if re.search(r"[A-Za-z]", s.line):
            bad.append(f"{s.id}: line has Latin letters; write Hindi in Devanagari only")
    return bad


def write(seed_id: str, attempts: int = 3, client=None, db: Path | None = None) -> tuple[episode.EpisodeSpec | None, list[str]]:
    sd = seed(seed_id)
    if sd["character"] not in LOOKS:
        return None, [f"no fixed look for character {sd['character']!r}"]
    url = (os.environ.get("STORY_LLM_URL") or "http://localhost:11434/v1").rstrip("/")
    model = os.environ.get("STORY_LLM_MODEL") or "qwen2.5:7b-instruct"
    client = client or httpx.Client(timeout=600)
    user = f"Hero: {sd['character']} ({sd['hero_role']}).\nStory title: {sd['title']}\nSummary:\n{sd['summary']}"
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    bad: list[str] = []
    for _ in range(attempts):
        try:
            r = client.post(f"{url}/chat/completions", json={"model": model, "messages": messages, "temperature": 0.6,
                                                              "response_format": {"type": "json_object"}})
        except httpx.TransportError as exc:
            return None, [f"no local language model answered at {url} ({type(exc).__name__})"]
        if r.status_code != 200:
            return None, [f"language model error {r.status_code}: {r.text[:200]}"]
        reply = r.json()["choices"][0]["message"]["content"]
        try:
            spec = build(sd, extract_json(reply))
            bad = problems_in(spec, db)
        except (ValueError, KeyError, TypeError, ValidationError) as exc:
            spec, bad = None, [f"invalid reply: {str(exc)[:300]}"]
        if spec is not None and not bad:
            return spec, []
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": "Fix these problems and send the whole JSON again:\n- " + "\n- ".join(bad)}]
    return None, bad


def save(spec: episode.EpisodeSpec) -> Path:
    path = episode.EPISODES / f"{spec.id}.json"
    path.write_text(json.dumps(spec.model_dump(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # Hindi text crashed the Windows console encoding
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "list"
    if cmd == "list":
        for s in seeds():
            done = "written" if (episode.EPISODES / f"{s['id']}.json").exists() else "-"
            print(f"{s['id']:34} {s['character']:10} {done:8} {s['title']}")
        return 0
    if cmd in ("write", "queue") and len(argv) > 1:
        code = 0
        for sid in argv[1:]:
            spec, bad = write(sid)
            if spec is None:
                print(f"{sid}: refused\n  " + "\n  ".join(bad))
                code = 1
                continue
            print(f"{sid}: wrote {save(spec)}")
            for s in spec.shots:
                print(f"   {s.id}  {s.line}")
            if cmd == "queue":
                print(f"   queued job {jobs.enqueue('episode', {'id': sid})['id']}")
        return code
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
