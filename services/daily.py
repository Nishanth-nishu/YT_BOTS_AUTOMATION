"""One video a day, start to finish: news -> story -> voice -> render -> QA -> package -> YouTube.

    python -m services.daily                      # full run, YouTube step is a dry run
    python -m services.daily --publish            # full run and upload (private unless --privacy says otherwise)
    python -m services.daily --story-file data/stories/<id>.story.json   # skip the news and the LLM

The run stops at the first stage that fails and exits non-zero; nothing after a
failed stage runs, so a video that fails QA is never packaged or uploaded.
Every run is recorded in SQLite (table daily_runs) and in
output/reports/daily-<date>.json. A day that already produced an upload is not
run again unless --force is given, and a news item is never used twice.

Stages: story, voice, render, qa, package, upload.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import psutil

from services.common import paths
from services.common.env import load_dotenv

STAGES = ("story", "voice", "render", "qa", "package", "upload")
SIZES = {"draft": (720, 1280), "standard": (1080, 1920), "cinematic": (1080, 1920)}


class StageError(RuntimeError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


@dataclass
class Options:
    profile: str = "standard"
    concurrency: int = 1
    publish: bool = False
    privacy: str = "private"
    publish_at: str | None = None
    synthetic: bool = False
    story_file: Path | None = None
    candidates: int = 5      # how many news items to try before giving up
    attempts: int = 3        # LLM attempts per news item
    region: str = "IN"
    force: bool = False
    db_path: Path | None = None


@dataclass
class Run:
    day: str
    status: str = "running"          # running | ok | failed | skipped
    stage: str = ""                  # last stage started
    error: str = ""
    story_id: str = ""
    title: str = ""
    source_url: str = ""
    video: str = ""
    package: str = ""
    video_id: str = ""
    url: str = ""
    uploaded: bool = False
    seconds: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------- run log

def _db(db_path: Path | None = None) -> sqlite3.Connection:
    p = db_path or paths.DATABASE
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.execute("""CREATE TABLE IF NOT EXISTS daily_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL, status TEXT NOT NULL, stage TEXT, error TEXT, story_id TEXT, title TEXT,
        source_url TEXT, video TEXT, video_id TEXT, url TEXT, uploaded INTEGER, started_at REAL, finished_at REAL)""")
    return con


def uploaded_today(day: str, db_path: Path | None = None) -> str | None:
    with _db(db_path) as con:
        row = con.execute("SELECT url FROM daily_runs WHERE day = ? AND status = 'ok' AND uploaded = 1 ORDER BY id DESC LIMIT 1", (day,)).fetchone()
    return row[0] if row else None


def used_sources(db_path: Path | None = None) -> set[str]:
    """News items that already became a finished video (uploaded or not)."""
    with _db(db_path) as con:
        return {r[0] for r in con.execute("SELECT source_url FROM daily_runs WHERE status = 'ok' AND source_url != ''")}


def record(run: Run, started: float, db_path: Path | None = None) -> None:
    with _db(db_path) as con:
        con.execute("INSERT INTO daily_runs (day, status, stage, error, story_id, title, source_url, video, video_id, url, uploaded, started_at, finished_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (run.day, run.status, run.stage, run.error[:2000], run.story_id, run.title, run.source_url, run.video, run.video_id, run.url, int(run.uploaded), started, time.time()))


# ---------------------------------------------------------------- stages (each one is replaceable in tests)

def stage_story(opts: Options, run: Run) -> Path:
    """Pick a fresh news item and get an acceptable story for it; returns the storyboard path."""
    from services.story import generate, trending, writer

    if opts.story_file:
        story = writer.Story.model_validate_json(opts.story_file.read_text(encoding="utf-8"))
        result = generate.save(story, story.source_title)
    else:
        found = trending.discover(limit=max(opts.candidates * 3, 15), region=opts.region)
        if found["errors"]:
            run.notes.append({"feed_errors": found["errors"]})
        used = used_sources(opts.db_path)
        fresh = [c for c in found["candidates"] if c["url"] not in used][: opts.candidates]
        if not fresh:
            raise RuntimeError(f"no unused, low-risk news today (fetched {found['fetched']}, rejected {len(found['rejected'])})")
        result, failures = None, []
        for cand in fresh:
            if not cand.get("summary"):
                cand["summary"] = trending.article_summary(cand["url"])
            if not cand["summary"]:
                # a headline alone is too little to stay truthful: the writer fills the gaps with invention
                failures.append({"title": cand["title"], "problems": ["no article summary available; skipped"]})
                continue
            story, problems = writer.write_story(cand, attempts=opts.attempts)
            if problems and problems[0].startswith(("no local LLM answered", "local LLM error")):
                raise RuntimeError(problems[0])  # the writer is down: trying more items will not help
            if not problems:
                try:
                    result = generate.save(story, f"{cand['title']} {cand.get('summary', '')}")
                    break
                except RuntimeError as exc:
                    problems = [str(exc)]
            failures.append({"title": cand["title"], "problems": problems[:4]})
        run.notes.append({"rejected_stories": failures}) if failures else None
        if result is None:
            raise RuntimeError(f"none of {len(fresh)} news items produced an acceptable story")
        writer.release_model()  # give the model's memory back before the render
    run.story_id, run.title, run.source_url = result["id"], result["title"], result["source"]
    run.notes.append({"written_by": json.loads(Path(result["story"]).read_text(encoding="utf-8")).get("written_by")})
    return Path(result["storyboard"])


def stage_voice(storyboard: Path, opts: Options, run: Run) -> Path:
    from services.common.schema import Storyboard
    from services.tts.synthesize import synthesize_storyboard

    sb = Storyboard.model_validate_json(storyboard.read_text(encoding="utf-8"))
    synthesize_storyboard(sb)
    return paths.STORYBOARDS / f"{sb.id}.timed.json"


def stage_render(spec: Path, opts: Options, run: Run) -> Path:
    from services.rendering.local_render import render

    need = int(os.environ.get("RENDER_MIN_FREE_RAM_MB") or 2500)
    free = psutil.virtual_memory().available // (1024 * 1024)
    if free < need:
        raise RuntimeError(f"only {free} MB of RAM free, {need} MB needed to render safely (close other apps or lower RENDER_MIN_FREE_RAM_MB)")
    out = paths.DRAFTS / f"{run.story_id}.{opts.profile}.mp4"
    render(spec, opts.profile, out, opts.concurrency)
    return out


def stage_qa(video: Path, spec: Path, opts: Options, run: Run) -> Path:
    from services.quality.technical import run_technical

    w, h = SIZES[opts.profile]
    rep = run_technical(video, json.loads(spec.read_text(encoding="utf-8")), w, h)
    out = paths.REPORTS / f"{video.stem}.technical.json"
    out.write_text(json.dumps({**asdict(rep), "passed": rep.passed}, indent=1), encoding="utf-8")
    if not rep.passed:
        raise RuntimeError("technical QA failed: " + ", ".join(f"{c.name} ({c.detail})" for c in rep.checks if not c.passed))
    return out


def stage_package(spec: Path, video: Path, qa: Path, opts: Options, run: Run) -> Path:
    from services.publishing.package import build_package

    return build_package(spec, video, None, qa)


def stage_upload(package: Path, opts: Options, run: Run) -> dict:
    from services.publishing import youtube

    return youtube.publish_package(package, confirm=opts.publish, category=None, privacy=opts.privacy, publish_at=opts.publish_at,
                                   shorts=True, synthetic=opts.synthetic, db_path=opts.db_path)


DEFAULT_STEPS: dict[str, Callable] = {"story": stage_story, "voice": stage_voice, "render": stage_render, "qa": stage_qa, "package": stage_package, "upload": stage_upload}


# ---------------------------------------------------------------- orchestration

def run_daily(opts: Options, steps: dict[str, Callable] | None = None, today: date | None = None) -> Run:
    steps = {**DEFAULT_STEPS, **(steps or {})}
    run = Run(day=(today or date.today()).isoformat())
    started = time.time()
    previous = uploaded_today(run.day, opts.db_path)
    if previous and not opts.force:
        run.status, run.error = "skipped", f"today's video is already uploaded: {previous} (use --force to make another)"
        return run

    def do(stage: str, *args):
        run.stage = stage
        t0 = time.time()
        try:
            return steps[stage](*args, opts, run)
        except Exception as exc:  # noqa: BLE001 - any failure stops the run and is recorded
            raise StageError(stage, f"{type(exc).__name__}: {exc}") from exc
        finally:
            run.seconds[stage] = round(time.time() - t0, 1)

    try:
        storyboard = do("story")
        spec = do("voice", storyboard)
        video = do("render", spec)
        run.video = str(video)
        qa = do("qa", video, spec)
        package = do("package", spec, video, qa)
        run.package = str(package)
        result = do("upload", package)
        run.video_id, run.url = result.get("video_id", ""), result.get("url", "")
        run.uploaded = bool(run.video_id)
        run.notes.append({"upload": {k: result.get(k) for k in ("mode", "privacy", "publish_at", "title", "credentials_present") if k in result}})
        run.status = "ok"
    except StageError as exc:
        run.status, run.error = "failed", f"{exc.stage}: {exc}"
        run.notes.append({"traceback": traceback.format_exc(limit=6)})
    record(run, started, opts.db_path)
    return run


def write_report(run: Run) -> Path:
    paths.REPORTS.mkdir(parents=True, exist_ok=True)
    out = paths.REPORTS / f"daily-{run.day}.json"
    history = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    history.append({"at": datetime.now().isoformat(timespec="seconds"), **asdict(run)})
    out.write_text(json.dumps(history, indent=1, ensure_ascii=False), encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Make and (optionally) upload today's video.")
    ap.add_argument("--publish", action="store_true", help="really upload to YouTube (default: dry run of the upload step)")
    ap.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    ap.add_argument("--publish-at", default=None, help="schedule the upload, ISO 8601 UTC")
    ap.add_argument("--synthetic", action="store_true", help="tick YouTube's altered/synthetic content disclosure")
    ap.add_argument("--profile", default="standard", choices=list(SIZES))
    ap.add_argument("--concurrency", type=int, default=int(os.environ.get("RENDER_LOCAL_CONCURRENCY") or 1))
    ap.add_argument("--story-file", help="use this finished story instead of fetching news and calling the LLM")
    ap.add_argument("--candidates", type=int, default=5)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--region", default="IN")
    ap.add_argument("--force", action="store_true", help="run even if today's video is already uploaded")
    args = ap.parse_args(argv)
    load_dotenv()
    paths.ensure_dirs()
    opts = Options(profile=args.profile, concurrency=args.concurrency, publish=args.publish, privacy=args.privacy, publish_at=args.publish_at,
                   synthetic=args.synthetic, story_file=Path(args.story_file) if args.story_file else None, candidates=args.candidates,
                   attempts=args.attempts, region=args.region, force=args.force)
    run = run_daily(opts)
    report = write_report(run)
    summary = {k: v for k, v in asdict(run).items() if k != "notes" and v not in ("", [], {})}
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    print("report:", report)
    if run.status == "failed":
        print("FAILED at", run.error, file=sys.stderr)
        return 1
    if run.status == "ok" and not run.uploaded:
        print("video is ready and packaged; nothing was uploaded" + ("" if args.publish else " (add --publish to upload)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
