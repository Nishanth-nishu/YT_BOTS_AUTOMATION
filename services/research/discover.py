"""Discover, score, dedupe and save topic candidates.

    python -m services.research.discover [--sources arxiv,hf_papers,...] [--top 25] [--save]

Prints a ranked table; with --save, writes data/topics/<slug>.json for the top
N and a run report to output/reports/research_<date>.json.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from datetime import date

from services.common import paths
from services.research.score import dedupe, load_existing, save_topics, score_candidate
from services.research.sources import fetch_all


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default=None, help="comma-separated subset of source names")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    paths.ensure_dirs()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
    except AttributeError:
        pass

    names = args.sources.split(",") if args.sources else None
    candidates, errors = fetch_all(names)
    scored = [score_candidate(c) for c in candidates if c.title and c.url]
    existing = load_existing()
    ranked = dedupe(scored, existing)[: args.top]

    print(f"\n{'score':>6}  {'cat':<9} {'src':<16} title")
    for t in ranked:
        print(f"{t.score_total:>6}  {t.category:<9} {t.sources[0]['source']:<16} {t.name[:80]}")
    if errors:
        print("\nsource errors:", json.dumps(errors, indent=1))

    if args.save:
        written = save_topics(ranked)
        report = paths.REPORTS / f"research_{date.today().isoformat()}.json"
        report.write_text(json.dumps({"fetched": len(candidates), "scored": len(scored), "saved": [str(p) for p in written], "errors": errors, "top": [asdict(t) for t in ranked]}, indent=1, default=str), encoding="utf-8")
        print(f"\nsaved {len(written)} topics; report {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
