"""Topic scoring, deduplication and brief storage.

Topic Score = 0.25 novelty + 0.20 audience + 0.20 visual + 0.15 educational
            + 0.10 timeliness + 0.10 shareability, each factor 0..100.

The heuristics are deliberately transparent so a human can read why a topic
ranked where it did. The final choice is still made by the content agent.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from services.common import paths
from services.research.sources import Candidate

WEIGHTS = {"novelty": 0.25, "audience": 0.20, "visual": 0.20, "educational": 0.15, "timeliness": 0.10, "shareability": 0.10}

VISUAL_TERMS = {
    "agent": 90, "agents": 90, "diffusion": 85, "video": 85, "image": 80, "vision": 80, "robot": 95, "robotics": 95,
    "3d": 90, "world model": 90, "simulation": 85, "attention": 75, "transformer": 70, "memory": 75, "reasoning": 70,
    "tool": 70, "code": 70, "coding": 70, "speech": 65, "audio": 65, "music": 70, "game": 80, "search": 60,
    "retrieval": 65, "rag": 70, "embedding": 60, "gpu": 70, "kernel": 60, "compiler": 55, "benchmark": 45,
    "protein": 80, "chip": 75, "hardware": 70, "open-source": 60, "open source": 60, "local": 60, "small model": 70,
}
EDU_TERMS = {"how": 70, "why": 70, "explain": 80, "introduc": 70, "survey": 75, "tutorial": 80, "guide": 75, "architecture": 70, "method": 55, "framework": 55, "understand": 75}
HYPE_TERMS = {"revolutionary": -15, "game-changing": -15, "ultimate": -10, "insane": -15}
AUDIENCE_TERMS = {"openai": 85, "gpt": 80, "claude": 80, "gemini": 80, "llama": 75, "deepseek": 80, "mistral": 70, "qwen": 70, "nvidia": 75, "cursor": 70, "copilot": 70, "agent": 80, "open-source": 70, "free": 65, "local": 65, "benchmark": 55}


def _term_score(text: str, table: dict[str, int], base: int = 35) -> float:
    t = text.lower()
    hits = [v for k, v in table.items() if k in t]
    if not hits:
        return base
    top = sorted(hits, reverse=True)[:3]
    return min(100.0, base + sum(top) * 0.5)


def _age_days(published: datetime | None) -> float | None:
    if not published:
        return None
    now = datetime.now(timezone.utc)
    return max(0.0, (now - published).total_seconds() / 86400)


def _timeliness(published: datetime | None) -> float:
    age = _age_days(published)
    if age is None:
        return 55.0  # unknown date (GitHub trending): recent by construction
    return float(max(5.0, 100.0 - age * 9))


def _popularity(signals: dict) -> float:
    stars = signals.get("stars_today", 0) or signals.get("upvotes", 0) or signals.get("likes", 0) or 0
    if not stars:
        downloads = signals.get("downloads", 0) or 0
        stars = downloads / 2000
    return float(min(100.0, 30 + 14 * math.log1p(stars)))


@dataclass
class Topic:
    id: str
    name: str
    category: str
    description: str
    sources: list[dict]
    published_at: str | None
    notes: str
    verified_claims: list[str]
    unverified_claims: list[str]
    scores: dict
    score_total: float
    status: str = "candidate"
    used_at: str | None = None
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "topic"


CATEGORY_MAP = {"research": "research", "news": "news", "repos": "repos", "products": "products"}


def score_candidate(c: Candidate) -> Topic:
    text = f"{c.title} {c.summary}"
    novelty = min(100.0, _timeliness(c.published) * 0.6 + _term_score(text, VISUAL_TERMS, 20) * 0.4)
    audience = max(_term_score(text, AUDIENCE_TERMS, 30), _popularity(c.signals) * 0.8)
    visual = _term_score(text, VISUAL_TERMS)
    educational = _term_score(text, EDU_TERMS, 40) + (15 if c.source in ("arxiv", "hf_papers") else 0)
    timeliness = _timeliness(c.published)
    shareability = min(100.0, _popularity(c.signals) * 0.7 + _term_score(text, AUDIENCE_TERMS, 25) * 0.3 + sum(v for k, v in HYPE_TERMS.items() if k in text.lower()))
    scores = {"novelty": round(novelty, 1), "audience": round(audience, 1), "visual": round(visual, 1), "educational": round(min(100.0, educational), 1), "timeliness": round(timeliness, 1), "shareability": round(shareability, 1)}
    total = round(sum(WEIGHTS[k] * scores[k] for k in WEIGHTS), 1)
    return Topic(
        id=slugify(c.title),
        name=c.title,
        category=CATEGORY_MAP.get(c.category_hint, "news"),
        description=c.summary,
        sources=[{"url": c.url, "source": c.source, "signals": c.signals, **({"arxiv": c.signals["arxiv"]} if c.signals.get("arxiv") else {})}],
        published_at=c.published.isoformat() if c.published else None,
        notes="",
        verified_claims=[],
        unverified_claims=[],
        scores=scores,
        score_total=total,
    )


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def dedupe(topics: list[Topic], existing: list[Topic], threshold: float = 0.8) -> list[Topic]:
    kept: list[Topic] = []
    seen_urls = {s["url"] for t in existing for s in t.sources}
    seen_names = [t.name for t in existing]
    for t in sorted(topics, key=lambda x: -x.score_total):
        if any(s["url"] in seen_urls for s in t.sources):
            continue
        if any(_similar(t.name, n) > threshold for n in seen_names) or any(_similar(t.name, k.name) > threshold for k in kept):
            # merge sources into the kept duplicate
            for k in kept:
                if _similar(t.name, k.name) > threshold:
                    k.sources.extend(s for s in t.sources if s not in k.sources)
            continue
        kept.append(t)
    return kept


def load_existing() -> list[Topic]:
    out: list[Topic] = []
    for f in paths.TOPICS.glob("*.json"):
        try:
            out.append(Topic(**json.loads(f.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return out


def save_topics(topics: list[Topic]) -> list[Path]:
    paths.TOPICS.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for t in topics:
        p = paths.TOPICS / f"{t.id}.json"
        p.write_text(json.dumps(asdict(t), indent=1, default=str), encoding="utf-8")
        written.append(p)
    return written
