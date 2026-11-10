"""Story generator: news screening and ranking, story rules, the local-LLM loop, storyboard mapping."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from services.common.rules import check_storyboard
from services.research.sources import Candidate
from services.story import generate, trending, writer

NOW = datetime(2026, 11, 11, 12, tzinfo=timezone.utc)
CAND = {"title": "Drunk raccoon leads to $250,000 for animal control", "url": "https://example.org/raccoon", "source": "nottheonion",
        "summary": "A raccoon that broke into a liquor store and passed out became famous and the shelter raised a quarter of a million dollars."}


def beat(role, narration, title="A short title", emotion="relaxed", **kw):
    return {"role": role, "narration": narration, "title": title, "emotion": emotion, **kw}


def good_story_json():
    filler = "The staff walked in the next morning and found bottles everywhere and one very sleepy bandit on the floor."
    return {"title": "The raccoon who robbed a liquor shop", "description": "A true story about a very thirsty raccoon. Nobody was hurt.", "hashtags": ["#funny", "weirdnews"],
            "beats": [beat("hook", "A raccoon broke into a liquor shop and it paid off.", "Raccoon robs liquor shop", "surprised", highlight=["Raccoon"]),
                      beat("setup", filler + " He had opened the good stuff first.", "The morning after", lines=["Bottles everywhere", "One sleepy bandit"]),
                      beat("escalation", "The photo went everywhere online. People wanted shirts. People wanted mugs. Strangers started sending money to the shelter that took him in.", "It goes viral", "happy"),
                      beat("escalation", "The total reached a quarter of a million dollars. That is more than most of us earn for behaving ourselves all year.", "Quarter of a million", "surprised"),
                      beat("punchline", "So the lesson is simple. Work hard, stay sober, and get out-earned by a raccoon with a hangover.", "The lesson", "angry"),
                      beat("cta", "Subscribe and I will bring you another true story tomorrow.", "See you tomorrow", "happy")]}


def good_story():
    return writer.story_from_json(good_story_json(), CAND)


def test_risk_screen_names_the_category_and_passes_harmless_news():
    assert "death or violence" in trending.risk_reason("Man killed in dispute over parking")
    assert "minors" in trending.risk_reason("Teen wins the science fair with a potato")
    assert "politics or religion" in trending.risk_reason("President pardons a turkey")
    assert trending.risk_reason("Deer rescued after pumpkin stuck on head for 10 days") is None


def test_rank_rejects_risky_items_drops_duplicates_and_prefers_fresh_trending_ones():
    c = lambda title, hours: Candidate(source="rss:nottheonion", title=title, url="https://example.org/x", published=NOW - timedelta(hours=hours))
    items = [(c("Private jet lands safely after striking alligator on runway", 60), 1.0, 0),
             (c("Drunk raccoon raises $250,000 for animal control", 2), 1.0, 1),
             (c("Drunk raccoon raises $250,000 for the animal control team", 3), 0.8, 2),
             (c("Man shot over a sandwich", 1), 1.0, 3)]
    kept, rejected = trending.rank(items, trending=["drunk raccoon video"], now=NOW)
    assert [k.title for k in kept] == ["Drunk raccoon raises $250,000 for animal control", "Private jet lands safely after striking alligator on runway"]
    assert kept[0].signals["trending"] is True
    assert {r["reason"].split(" (")[0] for r in rejected} == {"duplicate of a higher-ranked item", "death or violence"}


def test_discover_survives_a_failing_feed():
    def fetch(name, url, n):
        if name == "offbeat":
            raise RuntimeError("429")
        return [Candidate(source=f"rss:{name}", title=f"Goat elected mascot of {name}", url="https://example.org/g", published=datetime.now(timezone.utc))]
    result = trending.discover(fetch=fetch, pause=0)
    assert "offbeat" in result["errors"] and len(result["candidates"]) >= 1


def test_a_well_formed_story_passes_and_keeps_our_citation():
    story = good_story()
    assert writer.check_story(story, CAND["summary"]) == []
    assert story.source_url == CAND["url"] and story.id.endswith("the-raccoon-who-robbed-a-liquor-shop")


@pytest.mark.parametrize("mutate, expected", [
    (lambda j: j["beats"].__setitem__(0, beat("hook", "word " * 25)), "hook is 25 words"),
    (lambda j: j["beats"].pop(4), "exactly one punchline"),
    (lambda j: j["beats"].reverse(), "first beat must be the hook"),
    (lambda j: j["beats"].__setitem__(5, beat("cta", "Bye for now and see you all again tomorrow.")), "must ask viewers to subscribe"),
    (lambda j: j["beats"][1].__setitem__("narration", j["beats"][1]["narration"] + " Visit example.com now."), "no links"),
    (lambda j: j["beats"][1].__setitem__("title", "Like Minecraft"), "brand or character"),
    (lambda j: j["beats"][2].__setitem__("narration", j["beats"][2]["narration"] + " Then he died."), "sensitive content"),
    (lambda j: j.__setitem__("beats", j["beats"][:1] + j["beats"][5:]), "words; aim for"),
    (lambda j: j["beats"][1].__setitem__("narration", "A raccoon that broke into a liquor store and passed out became famous " + j["beats"][1]["narration"]), "copies the source"),
])
def test_story_rules_catch_each_problem(mutate, expected):
    raw = good_story_json()
    mutate(raw)
    problems = writer.check_story(writer.story_from_json(raw, CAND), CAND["summary"])
    assert any(expected in p for p in problems), problems


def llm(replies):
    """A fake OpenAI-compatible local server that returns each reply in turn and records the prompts."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": replies[len(seen) - 1]}}]})
    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def test_writer_feeds_problems_back_and_accepts_the_fixed_story():
    bad = good_story_json()
    bad["beats"][0] = beat("hook", "word " * 25)
    client, seen = llm([json.dumps(bad), "Here you go:\n" + json.dumps(good_story_json())])
    story, problems = writer.write_story(CAND, client=client)
    assert problems == [] and story.written_by.startswith("local:")
    assert "<news>" in seen[0]["messages"][1]["content"] and "hook is 25 words" in seen[1]["messages"][-1]["content"]
    assert str(seen[0]["model"]) and len(seen) == 2


def test_writer_gives_up_with_reasons_and_reports_a_missing_server():
    client, seen = llm(["not json at all"] * 2)
    story, problems = writer.write_story(CAND, attempts=2, client=client)
    assert story is None and "invalid story JSON" in problems[0] and len(seen) == 2

    def refuse(request):
        raise httpx.ConnectError("refused")
    story, problems = writer.write_story(CAND, client=httpx.Client(transport=httpx.MockTransport(refuse)))
    assert story is None and "no local LLM answered" in problems[0]


def test_storyboard_passes_house_rules_and_carries_emotion_source_and_cta():
    sb = generate.to_storyboard(good_story())
    assert check_storyboard(sb) == []
    assert [s.kind for s in sb.scenes] == ["hook", "concept", "concept", "concept", "concept", "payoff"]
    assert sb.scenes[0].data["expression"] == {"preset": "surprised", "weight": 0.65} and sb.scenes[0].data["kicker"].startswith("WEIRD BUT TRUE")
    assert sb.scenes[-1].cta == generate.CTA_TEXT and sb.sources == [CAND["url"]] and sb.dmLink is None
    assert "http" not in sb.caption and sb.hashtags == ["#funny", "#weirdnews"]
    assert len({s.id for s in sb.scenes}) == len(sb.scenes)


def test_save_writes_both_files_and_refuses_a_bad_story(tmp_path):
    result = generate.save(good_story(), CAND["summary"], tmp_path / "stories", tmp_path / "boards")
    assert (tmp_path / "boards" / f"{result['id']}.json").exists() and (tmp_path / "stories" / f"{result['id']}.story.json").exists()
    raw = good_story_json()
    raw["beats"].pop(4)
    with pytest.raises(RuntimeError, match="story rejected"):
        generate.save(writer.story_from_json(raw, CAND), "", tmp_path / "s2", tmp_path / "b2")
    assert not (tmp_path / "b2").exists()
