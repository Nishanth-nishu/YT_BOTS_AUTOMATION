"""Turn a funny news item into a storyboard the video engine can render.

    # 1. rank today's candidates
    python -m services.story.trending
    # 2a. let the local LLM write candidate number 1
    python -m services.story.generate --pick 1
    # 2b. or bring a story written elsewhere (same JSON shape as data/stories/*.story.json)
    python -m services.story.generate --story-file data/stories/<id>.story.json

Writes data/stories/<id>.story.json and data/storyboards/<id>.json, then the
normal pipeline takes over (synthesize, render, QA, package, YouTube upload).
A story that fails check_story, or a storyboard that fails the house rules, is
never written to data/storyboards.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from services.common import paths
from services.common.env import load_dotenv
from services.common.rules import check_storyboard
from services.common.schema import MusicConfig, Storyboard, StoryboardScene
from services.story.trending import article_summary
from services.story.writer import CTA_WORD, Story, check_story, write_story

STORIES = paths.DATA / "stories"
KICKERS = {"setup": "THE SETUP", "escalation": "IT GETS WEIRDER", "punchline": "THE PUNCHLINE", "cta": "SEE YOU TOMORROW"}
EXPRESSION_WEIGHT = {"hook": 0.65, "setup": 0.35, "escalation": 0.5, "punchline": 0.7, "cta": 0.45}
CTA_TEXT = "Subscribe for tomorrow's story"
CAPTION_TAIL = "Subscribe for a new weird-but-true story every day."


def to_storyboard(story: Story, day: date | None = None) -> Storyboard:
    """One scene per beat. The emotion drives the host's face through data.expression;
    the speaker is kept in data.speaker for the two-character dialogue scene."""
    stamp = (day or date.today()).strftime("%d %b %Y").upper().lstrip("0")
    scenes: list[StoryboardScene] = []
    counts: dict[str, int] = {}
    for beat in story.beats:
        counts[beat.role] = counts.get(beat.role, 0) + 1
        data = {"expression": {"preset": beat.emotion, "weight": EXPRESSION_WEIGHT[beat.role]}, "speaker": beat.speaker}
        common = dict(id=f"{beat.role}{counts[beat.role] if beat.role in ('setup', 'escalation') else ''}", narration=beat.narration.strip(),
                      title=beat.title.strip(), highlight=beat.highlight[:2], lines=[l.strip() for l in beat.lines[:3]])
        if beat.role == "hook":
            data["kicker"] = f"WEIRD BUT TRUE / {stamp}"
            scenes.append(StoryboardScene(kind="hook", data=data, padAfterMs=200, **common))
        elif beat.role == "cta":
            data["kicker"] = KICKERS["cta"]
            scenes.append(StoryboardScene(kind="payoff", data=data, cta=CTA_TEXT, padAfterMs=900, **common))
        else:
            data["kicker"] = KICKERS[beat.role]
            scenes.append(StoryboardScene(kind="concept", data=data, transition="burst" if beat.role == "punchline" else "current", padAfterMs=260, **common))
    caption = (story.description.strip() + "\n\n" if story.description.strip() else "") + CAPTION_TAIL
    hashtags = [h if h.startswith("#") else f"#{h}" for h in story.hashtags] or ["#funny", "#weirdnews", "#shorts"]
    return Storyboard(id=story.id, title=story.title, style="cinematic", music=MusicConfig(file="music/ambient_bed.wav", volume=0.2, bpm=84),
                      caption=caption, hashtags=hashtags, sources=[story.source_url], dmKeyword=CTA_WORD.upper(), dmLink=None, scenes=scenes)


def save(story: Story, source_text: str = "", out_stories: Path | None = None, out_storyboards: Path | None = None) -> dict:
    """Check, then write both files. Raises RuntimeError listing every problem."""
    problems = check_story(story, source_text)
    if problems:
        raise RuntimeError("story rejected:\n- " + "\n- ".join(problems))
    sb = to_storyboard(story)
    house = check_storyboard(sb)
    if house:
        raise RuntimeError("storyboard breaks the house rules:\n- " + "\n- ".join(house))
    stories, boards = out_stories or STORIES, out_storyboards or paths.STORYBOARDS
    stories.mkdir(parents=True, exist_ok=True)
    boards.mkdir(parents=True, exist_ok=True)
    story_path, board_path = stories / f"{story.id}.story.json", boards / f"{story.id}.json"
    story_path.write_text(story.model_dump_json(indent=1), encoding="utf-8")
    board_path.write_text(json.dumps(sb.model_dump(), indent=1, ensure_ascii=False), encoding="utf-8")
    return {"id": story.id, "title": story.title, "words": len(story.narration.split()), "scenes": len(sb.scenes), "source": story.source_url,
            "story": str(story_path), "storyboard": str(board_path)}


def latest_candidates() -> Path | None:
    files = sorted(paths.TOPICS.glob("story-candidates-*.json"))
    return files[-1] if files else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Write a funny story from real news and build its storyboard.")
    ap.add_argument("--pick", type=int, help="candidate number from the latest services.story.trending run (written by the local LLM)")
    ap.add_argument("--candidates", help="candidates file (default: newest data/topics/story-candidates-*.json)")
    ap.add_argument("--story-file", help="a finished story JSON to check and convert")
    ap.add_argument("--attempts", type=int, default=3)
    args = ap.parse_args(argv)
    load_dotenv()
    paths.ensure_dirs()
    source_text = ""
    try:
        if args.story_file:
            story = Story.model_validate_json(Path(args.story_file).read_text(encoding="utf-8"))
            source_text = story.source_title
        elif args.pick:
            cfile = Path(args.candidates) if args.candidates else latest_candidates()
            if not cfile or not cfile.exists():
                raise RuntimeError("no candidates file; run: python -m services.story.trending")
            cands = json.loads(cfile.read_text(encoding="utf-8"))["candidates"]
            if not 1 <= args.pick <= len(cands):
                raise RuntimeError(f"--pick must be between 1 and {len(cands)}")
            cand = cands[args.pick - 1]
            if not cand.get("summary"):
                cand["summary"] = article_summary(cand["url"])
            source_text = f"{cand['title']} {cand.get('summary', '')}"
            story, problems = write_story(cand, attempts=args.attempts)
            if problems:
                if story:
                    STORIES.mkdir(parents=True, exist_ok=True)
                    reject = STORIES / f"{story.id}.rejected-{datetime.now():%H%M%S}.json"
                    reject.write_text(story.model_dump_json(indent=1), encoding="utf-8")
                    print("last attempt kept for review:", reject, file=sys.stderr)
                raise RuntimeError("the local LLM could not write an acceptable story:\n- " + "\n- ".join(problems))
        else:
            ap.error("give --pick N or --story-file PATH")
        result = save(story, source_text)
    except (RuntimeError, ValueError) as e:
        print("error:", e, file=sys.stderr)
        return 1
    print(json.dumps(result, indent=1, ensure_ascii=False))
    print(f"\nnext:\n  python -m services.tts.synthesize {result['storyboard']}\n  python -m services.rendering.local_render --spec data/storyboards/{result['id']}.timed.json --profile draft --concurrency 1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
