"""Find funny, real, low-risk news to turn into a story. Free sources, no API keys.

    python -m services.story.trending [--limit 15] [--region IN]

Sources: Reddit RSS (r/nottheonion, r/offbeat: real news that reads like a
joke), UPI Odd News, and Google Trends (used only as a "people are searching
for this" boost, never as a story on its own).

Every item is screened before it is ranked. Anything touching death, violence,
minors, sexual content, tragedy, politics or religion is rejected with the
reason recorded: those are bad comedy and bad for an advertiser-friendly
channel. Fetched text is untrusted data: only the title, link, date and a
short summary are kept.

Writes data/topics/story-candidates-<date>.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable

from services.common import paths
import feedparser
from bs4 import BeautifulSoup

from services.research.sources import Candidate, _clean, _client, _parse_date, fetch_rss

# (name, url, weight): weight is how reliably the source is funny real news.
FEEDS: list[tuple[str, str, float]] = [
    ("nottheonion", "https://www.reddit.com/r/nottheonion/top/.rss?t=day", 1.0),
    ("offbeat", "https://www.reddit.com/r/offbeat/top/.rss?t=day", 0.8),
    ("upi_odd", "https://rss.upi.com/news/odd_news.rss", 0.9),
]
TRENDS_URL = "https://trends.google.com/trending/rss?geo={region}"

RISK: dict[str, str] = {
    "death or violence": r"\b(dead|death|dies|died|dying|kill(?:s|ed|ing|er)?|murder\w*|shot|shooting|stabb\w*|suicide|overdose|corpse|body found|fatal\w*|manslaughter|homicide|beheaded|massacre|terror\w*|bomb\w*|war|hostage|kidnap\w*|assault\w*|attack(?:s|ed)?|beaten|tortur\w*|on fire|engulfed|in flames|burn(?:s|ed|ing|t)?)\b",
    "minors": r"\b(child|children|kid|kids|baby|babies|infant|toddler|teen|teens|teenager\w*|minor|minors|student|students|schoolgirl|schoolboy|pupil|[1-9]-year-old|1[0-7]-year-old|boy|girl|daughter|son)\b",
    "sexual content": r"\b(sex\w*|rape\w*|porn\w*|nude\w*|naked|molest\w*|grop\w*|prostitut\w*|onlyfans|genital\w*|penis|vagina|masturbat\w*|incest)\b",
    "tragedy or illness": r"\b(cancer|tumou?r|crash(?:es|ed)?|earthquake|flood\w*|wildfire|hurricane|famine|pandemic|disabled|disability|amputat\w*|coma|miscarriage|funeral|grief|abuse\w*|trafficking|addict\w*|homeless\w*)\b",
    "politics or religion": r"\b(elected|councill?or\w*|council|assembly|mayor\w*|governor\w*|lawmaker\w*|politic\w*|election\w*|president\w*|prime minister|minister|senator|congress\w*|parliament|republican\w*|democrat\w*|trump|biden|harris|modi|putin|xi jinping|netanyahu|gaza|israel\w*|palestin\w*|ukrain\w*|russia\w*|immigra\w*|refugee\w*|abortion|racis\w*|nazi\w*|church|mosque|temple|priest|imam|pastor|muslim\w*|hindu\w*|christian\w*|jewish|islam\w*|god|allah|bible|quran)\b",
    "identity or immigration": r"\b(ICE agents?|detained by ICE|deport\w*|border patrol|asylum|lgbt\w*|pride|gay|lesbian|transgender|trans|queer|gender|ethnic\w*|caste|tribe)\b",
    "legal dispute or money loss": r"\b(sues?|sued|suing|lawsuit\w*|court|judge|trial|convict\w*|sentenc\w*|jail\w*|prison\w*|arrest\w*|detained|charged|fraud\w*|scam\w*|gambl\w*|bets?|betting|debt|bankrupt\w*)\b",
    "crime against a person": r"\b(arrest\w* for (?:assault|rape|murder)|victim\w*|robb(?:ed|ery) at gunpoint|domestic|stalk\w*|harass\w*)\b",
}
_RISK_RE = {reason: re.compile(pattern, re.I) for reason, pattern in RISK.items()}
_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("a an the of to in on at for and or with from by is are was were be been it its this that after over into as his her their man woman people says say said new".split())


@dataclass
class StoryCandidate:
    title: str
    url: str
    source: str
    summary: str = ""
    published: str | None = None
    score: float = 0.0
    signals: dict = field(default_factory=dict)


def fetch_reddit(name: str, url: str, limit: int = 25) -> list[Candidate]:
    """Reddit's feed links to the comment thread; the article itself is the "[link]"
    anchor inside each entry. Keep that as the source and drop the boilerplate summary."""
    with _client() as c:
        r = c.get(url)
        r.raise_for_status()
    out: list[Candidate] = []
    for e in feedparser.parse(r.text).entries[:limit]:
        html = " ".join(part.get("value", "") for part in e.get("content", [])) or e.get("summary", "")
        article = next((a.get("href", "") for a in BeautifulSoup(html, "lxml").find_all("a") if a.get_text(strip=True) == "[link]"), "")
        if not article or "reddit.com" in article or "redd.it" in article:
            continue  # a self post or an image, not a news article
        out.append(Candidate(source=f"rss:{name}", title=_clean(e.get("title", ""), 200), url=article,
                             published=_parse_date(e.get("published") or e.get("updated")), category_hint="news",
                             signals={"thread": e.get("link", "")}))
    return out


def article_summary(url: str, limit: int = 500) -> str:
    """The article's own one-paragraph description (meta tags only). Empty on any failure.
    This is untrusted text: it is only ever passed on as facts, fenced, to the story writer."""
    try:
        with _client() as c:
            r = c.get(url)
            r.raise_for_status()
        soup = BeautifulSoup(r.text[:400_000], "lxml")
        for attrs in ({"property": "og:description"}, {"name": "description"}, {"name": "twitter:description"}):
            tag = soup.find("meta", attrs=attrs)
            if tag and tag.get("content"):
                return _clean(tag["content"], limit)
    except Exception:  # noqa: BLE001 - a missing summary is fine
        pass
    return ""


def risk_reason(text: str) -> str | None:
    """Name the first risk category the text falls into, or None if it is clean."""
    for reason, rx in _RISK_RE.items():
        m = rx.search(text)
        if m:
            return f"{reason} ('{m.group(0).lower()}')"
    return None


def _keywords(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def _freshness(published: datetime | None, now: datetime) -> float:
    """1.0 for something from the last few hours, fading to 0 at three days."""
    if not published:
        return 0.4
    hours = max((now - published).total_seconds() / 3600, 0)
    return max(0.0, 1.0 - hours / 72)


def rank(items: list[tuple[Candidate, float, int]], trending: list[str], now: datetime | None = None) -> tuple[list[StoryCandidate], list[dict]]:
    """items: (candidate, source weight, position in its feed). Returns (kept, rejected)."""
    now = now or datetime.now(timezone.utc)
    trend_words = [_keywords(t) for t in trending]
    kept: list[StoryCandidate] = []
    rejected: list[dict] = []
    seen: list[set[str]] = []
    for cand, weight, position in items:
        title = cand.title.strip()
        if not title or not cand.url:
            continue
        reason = risk_reason(f"{title} {cand.summary}")
        if reason:
            rejected.append({"title": title, "source": cand.source, "reason": reason})
            continue
        kw = _keywords(title)
        if any(len(kw & other) / max(len(kw | other), 1) > 0.6 for other in seen):
            rejected.append({"title": title, "source": cand.source, "reason": "duplicate of a higher-ranked item"})
            continue
        seen.append(kw)
        fresh = _freshness(cand.published, now)
        rank_in_feed = max(0.0, 1.0 - position / 15)
        trend = 1.0 if any(len(kw & t) >= 2 for t in trend_words) else 0.0
        score = round(0.4 * weight + 0.3 * fresh + 0.2 * rank_in_feed + 0.1 * trend, 3)
        kept.append(StoryCandidate(title=title, url=cand.url, source=cand.source.removeprefix("rss:"), summary=cand.summary[:400],
                                   published=cand.published.isoformat() if cand.published else None, score=score,
                                   signals={"source_weight": weight, "freshness": round(fresh, 2), "feed_rank": position + 1, "trending": bool(trend)}))
    kept.sort(key=lambda c: c.score, reverse=True)
    return kept, rejected


def discover(limit: int = 15, region: str = "IN", fetch: Callable[[str, str, int], list[Candidate]] | None = None, pause: float = 4.0) -> dict:
    """Fetch every feed (one failure never stops the others), screen, rank."""
    fetch = fetch or (lambda name, url, n: (fetch_reddit if "reddit.com" in url else fetch_rss)(name, url, n))
    items: list[tuple[Candidate, float, int]] = []
    errors: dict[str, str] = {}
    for name, url, weight in FEEDS:
        try:
            for i, cand in enumerate(fetch(name, url, 25)):
                items.append((cand, weight, i))
        except Exception as exc:  # noqa: BLE001 - keep going on any source error
            errors[name] = str(exc)[:200]
        time.sleep(pause)
    trending: list[str] = []
    try:
        trending = [c.title for c in fetch("google_trends", TRENDS_URL.format(region=region), 25)]
    except Exception as exc:  # noqa: BLE001
        errors["google_trends"] = str(exc)[:200]
    kept, rejected = rank(items, trending)
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "region": region, "candidates": [asdict(c) for c in kept[:limit]],
            "rejected": rejected, "errors": errors, "fetched": len(items)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Rank funny, low-risk real news for the story generator.")
    ap.add_argument("--limit", type=int, default=15)
    ap.add_argument("--region", default="IN", help="Google Trends region code (default IN)")
    args = ap.parse_args(argv)
    paths.ensure_dirs()
    result = discover(args.limit, args.region)
    out = paths.TOPICS / f"story-candidates-{datetime.now().date().isoformat()}.json"
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    for i, c in enumerate(result["candidates"], 1):
        print(f"{i:2d}. [{c['score']:.2f}] ({c['source']}) {c['title']}".encode("ascii", "replace").decode())
    print(f"\nkept {len(result['candidates'])} of {result['fetched']} fetched, rejected {len(result['rejected'])}; errors: {result['errors'] or 'none'}")
    print("saved:", out)
    return 0 if result["candidates"] else 1


if __name__ == "__main__":
    sys.exit(main())
