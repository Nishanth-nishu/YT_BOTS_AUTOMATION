"""Structured logging: one JSON object per line, to stderr and a daily file."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from animeforge.config import settings


def event(name: str, _stream=None, _dir: Path | None = None, **fields) -> dict:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": name, **fields}
    line = json.dumps(rec, ensure_ascii=False, default=str)
    print(line, file=_stream or sys.stderr)
    try:
        d = _dir or settings().home / "logs"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / f"{rec['ts'][:10]}.jsonl", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    return rec
