"""Free research sources. No API keys, polite rate limits, generic user agent.

Every fetcher returns a list of Candidate records. Page content is treated as
untrusted data: we only extract titles, links, dates, counts and short
summaries, never instructions.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

import feedparser
import httpx
from bs4 import BeautifulSoup

log = logging.getLogger("reelforge.research.sources")

UA = "REELFORGE-research/0.1 (local, non-commercial research bot; contact via repo)"
TIMEOUT = 20.0


@dataclass
class Candidate:
    source: str  # arxiv | hf_papers | hf_models | github_trending | rss:<name>
    title: str
    url: str
    summary: str = ""
    published: datetime | None = None
    category_hint: str = ""
    signals: dict = field(default_factory=dict)  # stars, upvotes, likes, downloads


def _client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": UA, "Accept": "*/*"}, timeout=TIMEOUT, follow_redirects=True)


def _clean(text: str, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    return text[:limit]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime(*feedparser._parse_date(value)[:6], tzinfo=timezone.utc)  # type: ignore[attr-defined]
        except Exception:
            return None


def fetch_arxiv(max_results: int = 40, query: str = "cat:cs.AI OR cat:cs.LG OR cat:cs.CL") -> list[Candidate]:
    url = "https://export.arxiv.org/api/query"
    params = {"search_query": query, "sortBy": "submittedDate", "sortOrder": "descending", "max_results": max_results}
    with _client() as c:
        r = c.get(url, params=params)
        r.raise_for_status()
    feed = feedparser.parse(r.text)
    out: list[Candidate] = []
    for e in feed.entries:
        out.append(Candidate(
            source="arxiv",
            title=_clean(e.get("title", ""), 200),
            url=e.get("link", ""),
            summary=_clean(e.get("summary", "")),
            published=_parse_date(e.get("published")),
            category_hint="research",
            signals={"primary_category": (e.get("arxiv_primary_category") or {}).get("term", "")},
        ))
    time.sleep(3)  # arXiv asks for a 3 s gap between requests
    return out


def fetch_hf_daily_papers(limit: int = 30) -> list[Candidate]:
    with _client() as c:
        r = c.get("https://huggingface.co/api/daily_papers", params={"limit": limit})
        r.raise_for_status()
        data = r.json()
    out: list[Candidate] = []
    for item in data:
        paper = item.get("paper", {})
        pid = paper.get("id", "")
        out.append(Candidate(
            source="hf_papers",
            title=_clean(paper.get("title", ""), 200),
            url=f"https://huggingface.co/papers/{pid}" if pid else "",
            summary=_clean(paper.get("summary", "")),
            published=_parse_date(item.get("publishedAt") or paper.get("publishedAt")),
            category_hint="research",
            signals={"upvotes": paper.get("upvotes", 0), "arxiv": f"https://arxiv.org/abs/{pid}" if pid else ""},
        ))
    return out


def fetch_hf_trending_models(limit: int = 25) -> list[Candidate]:
    with _client() as c:
        r = c.get("https://huggingface.co/api/models", params={"sort": "trendingScore", "direction": -1, "limit": limit})
        r.raise_for_status()
        data = r.json()
    out: list[Candidate] = []
    for m in data:
        mid = m.get("id") or m.get("modelId", "")
        out.append(Candidate(
            source="hf_models",
            title=_clean(mid, 120),
            url=f"https://huggingface.co/{mid}",
            summary=_clean(f"pipeline: {m.get('pipeline_tag', '')}; tags: {', '.join((m.get('tags') or [])[:8])}"),
            published=_parse_date(m.get("createdAt")),
            category_hint="products",
            signals={"likes": m.get("likes", 0), "downloads": m.get("downloads", 0), "pipeline": m.get("pipeline_tag", "")},
        ))
    return out


def fetch_github_trending(since: str = "daily", language: str = "") -> list[Candidate]:
    url = f"https://github.com/trending/{language}".rstrip("/")
    with _client() as c:
        r = c.get(url, params={"since": since})
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    out: list[Candidate] = []
    for article in soup.select("article.Box-row"):
        h2 = article.select_one("h2 a")
        if not h2:
            continue
        repo = re.sub(r"\s+", "", h2.get_text())
        desc = article.select_one("p")
        stars_today = article.select_one("span.d-inline-block.float-sm-right")
        stars_total = article.select_one("a[href$='/stargazers']")
        lang = article.select_one("span[itemprop='programmingLanguage']")
        m = re.search(r"([\d,]+)", stars_today.get_text() if stars_today else "")
        m2 = re.search(r"([\d,]+)", stars_total.get_text() if stars_total else "")
        out.append(Candidate(
            source="github_trending",
            title=repo,
            url=f"https://github.com/{repo.lstrip('/')}",
            summary=_clean(desc.get_text() if desc else ""),
            published=None,
            category_hint="repos",
            signals={
                "stars_today": int(m.group(1).replace(",", "")) if m else 0,
                "stars": int(m2.group(1).replace(",", "")) if m2 else 0,
                "language": lang.get_text(strip=True) if lang else "",
            },
        ))
    return out


RSS_FEEDS: dict[str, str] = {
    "openai": "https://openai.com/news/rss.xml",
    "deepmind": "https://deepmind.google/blog/rss.xml",
    "huggingface": "https://huggingface.co/blog/feed.xml",
    "google-research": "https://research.google/blog/rss/",
    # Meta AI and Anthropic publish no RSS feed (404 on 2026-11-08); fetched via WebSearch when needed.
}


def fetch_rss(name: str, url: str, limit: int = 15) -> list[Candidate]:
    with _client() as c:
        r = c.get(url)
        r.raise_for_status()
    feed = feedparser.parse(r.text)
    out: list[Candidate] = []
    for e in feed.entries[:limit]:
        summary = e.get("summary") or e.get("description") or ""
        summary = BeautifulSoup(summary, "lxml").get_text(" ")
        out.append(Candidate(
            source=f"rss:{name}",
            title=_clean(e.get("title", ""), 200),
            url=e.get("link", ""),
            summary=_clean(summary),
            published=_parse_date(e.get("published") or e.get("updated")),
            category_hint="news",
        ))
    return out


FETCHERS: dict[str, Callable[[], list[Candidate]]] = {
    "arxiv": fetch_arxiv,
    "hf_papers": fetch_hf_daily_papers,
    "hf_models": fetch_hf_trending_models,
    "github_trending": fetch_github_trending,
    **{f"rss:{n}": (lambda n=n, u=u: fetch_rss(n, u)) for n, u in RSS_FEEDS.items()},
}


def fetch_all(names: list[str] | None = None) -> tuple[list[Candidate], dict[str, str]]:
    """Fetch every source, never let one failure stop the others."""
    results: list[Candidate] = []
    errors: dict[str, str] = {}
    for name, fn in FETCHERS.items():
        if names and name not in names:
            continue
        try:
            items = fn()
            log.info("%s: %d items", name, len(items))
            results.extend(items)
        except Exception as exc:  # noqa: BLE001 - we want to continue on any source error
            log.warning("%s failed: %s", name, exc)
            errors[name] = str(exc)[:200]
        time.sleep(1.0)
    return results, errors
