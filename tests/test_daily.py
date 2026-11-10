"""Daily pipeline: stage order, stop-on-failure, once-a-day lock, run log."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from services import daily

DAY = date(2026, 11, 11)


def fake_steps(calls, fail_at=None, upload=None):
    def step(name, value):
        def fn(*args):
            calls.append(name)
            if name == fail_at:
                raise RuntimeError(f"{name} broke")
            run = args[-1]
            if name == "story":
                run.story_id, run.title, run.source_url = "s1", "A title", "https://example.org/a"
            return value
        return fn
    return {"story": step("story", Path("sb.json")), "voice": step("voice", Path("spec.json")), "render": step("render", Path("v.mp4")),
            "qa": step("qa", Path("qa.json")), "package": step("package", Path("pkg")),
            "upload": step("upload", upload or {"mode": "DRY RUN", "privacy": "private", "title": "A title #Shorts"})}


def opts(tmp_path, **kw):
    return daily.Options(db_path=tmp_path / "db.sqlite", **kw)


def test_stages_run_in_order_and_a_dry_run_is_ok_but_not_uploaded(tmp_path):
    calls = []
    run = daily.run_daily(opts(tmp_path), fake_steps(calls), today=DAY)
    assert calls == list(daily.STAGES)
    assert run.status == "ok" and run.uploaded is False and run.story_id == "s1" and run.package == "pkg"
    assert set(run.seconds) == set(daily.STAGES)
    assert daily.uploaded_today(DAY.isoformat(), tmp_path / "db.sqlite") is None
    assert daily.used_sources(tmp_path / "db.sqlite") == {"https://example.org/a"}


@pytest.mark.parametrize("fail_at", ["story", "voice", "render", "qa", "package"])
def test_a_failed_stage_stops_everything_after_it(tmp_path, fail_at):
    calls = []
    run = daily.run_daily(opts(tmp_path), fake_steps(calls, fail_at=fail_at), today=DAY)
    assert run.status == "failed" and run.error.startswith(f"{fail_at}: RuntimeError: {fail_at} broke")
    assert calls == list(daily.STAGES[: daily.STAGES.index(fail_at) + 1]) and "upload" not in calls
    assert daily.used_sources(tmp_path / "db.sqlite") == set()


def test_once_uploaded_the_day_is_locked_unless_forced(tmp_path):
    live = {"mode": "LIVE", "video_id": "VID1", "url": "https://youtu.be/VID1", "privacy": "private"}
    first = daily.run_daily(opts(tmp_path, publish=True), fake_steps([], upload=live), today=DAY)
    assert first.status == "ok" and first.uploaded and first.url == "https://youtu.be/VID1"
    calls = []
    second = daily.run_daily(opts(tmp_path, publish=True), fake_steps(calls, upload=live), today=DAY)
    assert second.status == "skipped" and calls == [] and "VID1" in second.error
    forced = daily.run_daily(opts(tmp_path, publish=True, force=True), fake_steps(calls, upload=live), today=DAY)
    assert forced.status == "ok" and calls == list(daily.STAGES)
    tomorrow = daily.run_daily(opts(tmp_path, publish=True), fake_steps([], upload=live), today=date(2026, 11, 12))
    assert tomorrow.status == "ok"


def test_render_refuses_to_start_without_enough_free_memory(tmp_path, monkeypatch):
    monkeypatch.setenv("RENDER_MIN_FREE_RAM_MB", str(10 ** 9))
    with pytest.raises(RuntimeError, match="MB of RAM free"):
        daily.stage_render(Path("spec.json"), opts(tmp_path), daily.Run(day="2026-11-11", story_id="s1"))


def test_story_stage_skips_used_news_and_stops_at_once_when_the_llm_is_down(tmp_path, monkeypatch):
    from services.story import trending, writer

    cands = [{"title": f"Goat {i}", "url": f"https://example.org/{i}", "source": "x", "summary": "s"} for i in range(3)]
    monkeypatch.setattr(trending, "discover", lambda **kw: {"candidates": cands, "errors": {}, "fetched": 3, "rejected": []})
    monkeypatch.setattr(daily, "used_sources", lambda db=None: {"https://example.org/0"})
    tried = []

    def down(cand, attempts=3):
        tried.append(cand["url"])
        return None, ["no local LLM answered at http://localhost:11434/v1 (ConnectError); start Ollama or set STORY_LLM_URL"]
    monkeypatch.setattr(writer, "write_story", down)
    with pytest.raises(RuntimeError, match="no local LLM answered"):
        daily.stage_story(opts(tmp_path), daily.Run(day="2026-11-11"))
    assert tried == ["https://example.org/1"]
