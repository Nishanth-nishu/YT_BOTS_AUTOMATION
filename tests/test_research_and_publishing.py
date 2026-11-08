import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.publishing import instagram
from services.research.score import WEIGHTS, dedupe, score_candidate, slugify
from services.research.sources import Candidate

ROOT = Path(__file__).resolve().parents[1]


def _cand(title, summary="", days_old=0, source="arxiv", **signals):
    return Candidate(source=source, title=title, url=f"https://example.org/{slugify(title)}", summary=summary,
                     published=datetime.now(timezone.utc) - timedelta(days=days_old), category_hint="research", signals=signals)


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_scores_are_normalised_and_fresh_visual_topics_rank_higher():
    fresh = score_candidate(_cand("Agents with memory for robots", "agent robot memory", days_old=0, upvotes=40))
    stale = score_candidate(_cand("A note on linear algebra", "matrix proof", days_old=9))
    for t in (fresh, stale):
        assert all(0 <= v <= 100 for v in t.scores.values())
        assert 0 <= t.score_total <= 100
    assert fresh.score_total > stale.score_total


def test_dedupe_merges_similar_titles_and_known_urls():
    a = score_candidate(_cand("Latent context compression for agents"))
    b = score_candidate(_cand("Latent context compression for agents (v2)"))
    kept = dedupe([a, b], existing=[])
    assert len(kept) == 1
    assert len(kept[0].sources) == 2
    assert dedupe([a], existing=[a]) == []


def test_publisher_refuses_failed_qa(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "x.mp4").write_bytes(b"0" * 10)
    (pkg / "caption.txt").write_text("hi", encoding="utf-8")
    (pkg / "package.json").write_text(json.dumps({"id": "x", "video": "x.mp4", "cover": None, "qa": "FAIL: loudness"}), encoding="utf-8")
    try:
        instagram.publish_package(pkg, confirm=False)
        assert False, "should refuse"
    except RuntimeError as exc:
        assert "refusing" in str(exc)


def test_publisher_dry_run_builds_raw_url(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "x.mp4").write_bytes(b"0" * 10)
    (pkg / "caption.txt").write_text("hi", encoding="utf-8")
    (pkg / "package.json").write_text(json.dumps({"id": "demo-reel", "video": "x.mp4", "cover": None, "qa": "PASS"}), encoding="utf-8")
    plan = instagram.publish_package(pkg, confirm=False)
    assert plan["mode"] == "DRY RUN"
    assert plan["would_host_at"].endswith("/media/demo-reel.mp4")
    assert plan["would_host_at"].startswith("https://raw.githubusercontent.com/")
