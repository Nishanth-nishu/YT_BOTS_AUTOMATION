"""YouTube uploader: metadata rules, safety gates, and the resumable upload against a fake server."""
from __future__ import annotations

import json

import httpx
import pytest

from services.publishing import youtube


@pytest.fixture(autouse=True)
def creds(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "cid")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "secret")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "refresh")
    monkeypatch.delenv("YOUTUBE_MAX_UPLOADS_PER_DAY", raising=False)


def make_package(tmp_path, qa="PASS", youtube_meta=None):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "vid.mp4").write_bytes(b"x" * 1000)
    (pkg / "caption.txt").write_text("A funny thing happened.\n", encoding="utf-8")
    (pkg / "hashtags.txt").write_text("#funny\n#news\n", encoding="utf-8")
    (pkg / "sources.txt").write_text("https://example.org/story\n", encoding="utf-8")
    meta = {"id": "vid", "title": "The <great> heist", "video": "vid.mp4", "cover": None, "qa": qa}
    if youtube_meta:
        meta["youtube"] = youtube_meta
    (pkg / "package.json").write_text(json.dumps(meta), encoding="utf-8")
    return pkg


def test_title_is_cleaned_capped_and_tagged_as_short():
    assert youtube.clean_title("The <great> heist", shorts=True) == "The great heist #Shorts"
    assert youtube.clean_title("Already #shorts", shorts=True) == "Already #shorts"
    long = youtube.clean_title("x" * 300, shorts=True)
    assert len(long) == youtube.TITLE_MAX and long.endswith("… #Shorts")
    assert youtube.clean_title("Long form", shorts=False) == "Long form"


def test_tags_drop_hashes_duplicates_and_respect_the_500_char_limit():
    assert youtube.clean_tags(["#funny", "Funny", " news ", ""]) == ["funny", "news"]
    many = youtube.clean_tags([f"tag{i:04d}" for i in range(200)])
    assert sum(len(t) for t in many) + len(many) - 1 <= youtube.TAGS_MAX_CHARS


def test_metadata_defaults_are_safe_and_scheduling_forces_private():
    body = youtube.build_metadata("T", "desc <b>", ["a"])
    assert body["status"] == {"privacyStatus": "private", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False}
    assert body["snippet"]["categoryId"] == "23" and body["snippet"]["description"] == "desc b"
    scheduled = youtube.build_metadata("T", privacy="public", publish_at="2026-11-12T12:30:00Z")
    assert scheduled["status"]["privacyStatus"] == "private" and scheduled["status"]["publishAt"] == "2026-11-12T12:30:00Z"
    with pytest.raises(ValueError):
        youtube.build_metadata("T", privacy="everyone")
    with pytest.raises(ValueError):
        youtube.build_metadata("T", category="cooking")


def test_package_refuses_failed_qa(tmp_path):
    with pytest.raises(RuntimeError, match="QA"):
        youtube.publish_package(make_package(tmp_path, qa="FAIL: loudness"), confirm=False, db_path=tmp_path / "db.sqlite")


def test_package_dry_run_builds_description_with_sources_and_uploads_nothing(tmp_path):
    plan = youtube.publish_package(make_package(tmp_path), confirm=False, db_path=tmp_path / "db.sqlite")
    assert plan["mode"] == "DRY RUN" and plan["title"] == "The great heist #Shorts" and plan["privacy"] == "private"
    assert plan["tags"] == ["funny", "news"] and "video_id" not in plan
    assert youtube.uploads_last_24h(tmp_path / "db.sqlite") == 0


def test_package_youtube_block_overrides_defaults(tmp_path):
    pkg = make_package(tmp_path, youtube_meta={"title": "Custom", "description": "Own text", "tags": ["x"], "category": "news"})
    body, _, _, _ = youtube.metadata_from_package(pkg, category=None)
    assert body["snippet"]["title"] == "Custom #Shorts" and body["snippet"]["description"] == "Own text"
    assert body["snippet"]["tags"] == ["x"] and body["snippet"]["categoryId"] == "25"


class FakeYouTube:
    """Token endpoint plus a resumable session that can fail once mid-upload."""

    def __init__(self, fail_once=False):
        self.received = bytearray()
        self.fail_once = fail_once
        self.metadata = None
        self.puts = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.startswith(youtube.TOKEN_URL):
            return httpx.Response(200, json={"access_token": "at"})
        assert request.headers["authorization"] == "Bearer at"
        if request.method == "POST" and "/upload/youtube/v3/videos" in url:
            self.metadata = json.loads(request.content)
            return httpx.Response(200, headers={"Location": "https://upload.test/session"})
        if request.method == "PUT":
            self.puts += 1
            total = int(request.headers["content-range"].split("/")[1])
            if request.headers["content-range"].startswith("bytes */"):
                return self._progress(total)
            if self.fail_once:
                self.fail_once = False
                return httpx.Response(503)
            start = int(request.headers["content-range"].split(" ")[1].split("-")[0])
            assert start == len(self.received)
            self.received += request.content
            return self._progress(total)
        raise AssertionError(f"unexpected request {request.method} {url}")

    def _progress(self, total):
        if len(self.received) == total:
            return httpx.Response(200, json={"id": "VID123"})
        headers = {"Range": f"bytes=0-{len(self.received) - 1}"} if self.received else {}
        return httpx.Response(308, headers=headers)


@pytest.mark.parametrize("fail_once", [False, True])
def test_resumable_upload_sends_every_byte_in_order_and_recovers_from_a_503(tmp_path, fail_once, monkeypatch):
    monkeypatch.setattr(youtube.time, "sleep", lambda s: None)
    video = tmp_path / "v.mp4"
    payload = bytes(range(256)) * 10
    video.write_bytes(payload)
    fake = FakeYouTube(fail_once=fail_once)
    with httpx.Client(transport=httpx.MockTransport(fake)) as client:
        vid = youtube.resumable_upload(client, "at", video, youtube.build_metadata("T"), chunk=1000)
    assert vid == "VID123" and bytes(fake.received) == payload
    assert fake.metadata["status"]["privacyStatus"] == "private"


def test_live_publish_logs_the_upload_then_blocks_a_repeat_and_enforces_the_cap(tmp_path, monkeypatch):
    db = tmp_path / "db.sqlite"
    pkg = make_package(tmp_path)
    with httpx.Client(transport=httpx.MockTransport(FakeYouTube())) as client:
        plan = youtube.publish_package(pkg, confirm=True, client=client, db_path=db)
    assert plan["url"] == "https://youtu.be/VID123"
    assert json.loads((pkg / "package.json").read_text(encoding="utf-8"))["youtube_upload"]["video_id"] == "VID123"
    assert youtube.uploads_last_24h(db) == 1
    with pytest.raises(RuntimeError, match="already uploaded"):
        youtube.publish_package(pkg, confirm=False, db_path=db)
    monkeypatch.setenv("YOUTUBE_MAX_UPLOADS_PER_DAY", "1")
    with pytest.raises(RuntimeError, match="daily cap"):
        youtube.publish_package(pkg, confirm=False, force=True, db_path=db)


def test_refresh_token_is_written_to_env_file_without_touching_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\nYOUTUBE_REFRESH_TOKEN=old\nB=2\n", encoding="utf-8")
    youtube.save_env_value("YOUTUBE_REFRESH_TOKEN", "new", env)
    assert env.read_text(encoding="utf-8") == "A=1\nYOUTUBE_REFRESH_TOKEN=new\nB=2\n"
