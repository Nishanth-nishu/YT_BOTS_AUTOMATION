"""Instagram Reels publishing through the official Instagram Graph API.

No unofficial bots. Requirements the user must set up once (free):
  1. An Instagram Professional (Creator or Business) account linked to a
     Facebook Page.
  2. A Meta developer app with the Instagram Graph API product and a long-lived
     user access token with instagram_basic, instagram_content_publish,
     pages_show_list, pages_read_engagement.
  3. The numeric Instagram user id (IG_USER_ID).
Both values go in .env (never in the repo): IG_ACCESS_TOKEN, IG_USER_ID.

Instagram fetches the video from a PUBLIC https URL. REELFORGE hosts the
approved MP4 on the project's public GitHub repository, on an orphan `media`
branch, and uses the raw.githubusercontent.com URL (zero cost). Set
PUBLIC_MEDIA_BASE_URL to use any other host instead.

Usage (always dry-run unless --confirm):
    python -m services.publishing.instagram --package output/approved/<date>/<id> [--confirm]

Flow: host media -> create REELS container -> poll status -> publish -> record permalink in package.json.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from services.common import paths

GRAPH = "https://graph.facebook.com/v21.0"
REPO = os.environ.get("MEDIA_GITHUB_REPO", "Nishanth-nishu/insta-bot")
MEDIA_BRANCH = os.environ.get("MEDIA_BRANCH", "media")


def _env(name: str) -> str | None:
    # Load .env lazily without a dependency.
    env_file = paths.ROOT / ".env"
    if name not in os.environ and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return os.environ.get(name)


@dataclass
class PublishResult:
    media_id: str
    permalink: str
    video_url: str


def host_on_github(video: Path, cover: Path | None, reel_id: str, dry_run: bool) -> tuple[str, str | None]:
    """Commit the MP4 (and cover) to the orphan media branch of the public repo
    and return raw URLs. Uses a temporary worktree so the main checkout is untouched."""
    base = os.environ.get("PUBLIC_MEDIA_BASE_URL")
    if base:
        return f"{base.rstrip('/')}/{reel_id}.mp4", (f"{base.rstrip('/')}/{reel_id}.jpg" if cover else None)
    video_url = f"https://raw.githubusercontent.com/{REPO}/{MEDIA_BRANCH}/{reel_id}.mp4"
    cover_url = f"https://raw.githubusercontent.com/{REPO}/{MEDIA_BRANCH}/{reel_id}.jpg" if cover else None
    if dry_run:
        return video_url, cover_url
    wt = paths.ROOT / ".media-worktree"
    run = lambda *cmd, **kw: subprocess.run(cmd, cwd=kw.get("cwd", paths.ROOT), capture_output=True, text=True)
    # Ensure branch exists remotely or create orphan.
    has_remote = run("git", "ls-remote", "--heads", "origin", MEDIA_BRANCH).stdout.strip() != ""
    if wt.exists():
        run("git", "worktree", "remove", "--force", str(wt))
    if has_remote:
        run("git", "fetch", "origin", MEDIA_BRANCH)
        r = run("git", "worktree", "add", str(wt), f"origin/{MEDIA_BRANCH}", "--detach")
    else:
        r = run("git", "worktree", "add", "--detach", str(wt))
        run("git", "checkout", "--orphan", MEDIA_BRANCH, cwd=wt)
        run("git", "rm", "-rf", "-q", ".", cwd=wt)
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    (wt / f"{reel_id}.mp4").write_bytes(video.read_bytes())
    if cover:
        _write_jpeg(cover, wt / f"{reel_id}.jpg")
    (wt / "README.md").write_text("Media hosting branch for Instagram publishing. Generated videos only.\n", encoding="utf-8")
    run("git", "add", "-A", cwd=wt)
    run("git", "-c", "user.name=Nishanth R", "-c", "user.email=nishanth0962333@gmail.com", "commit", "-q", "-m", f"media: {reel_id}", cwd=wt)
    push = run("git", "push", "origin", f"HEAD:{MEDIA_BRANCH}", cwd=wt)
    if push.returncode != 0:
        raise RuntimeError(push.stderr)
    run("git", "worktree", "remove", "--force", str(wt))
    # Wait until the raw URL answers 200 (CDN propagation).
    with httpx.Client(follow_redirects=True, timeout=30) as c:
        for _ in range(20):
            if c.head(video_url).status_code == 200:
                break
            time.sleep(6)
    return video_url, cover_url


def _write_jpeg(png: Path, out: Path) -> None:
    subprocess.run([paths.FFMPEG, "-y", "-v", "error", "-i", str(png), "-q:v", "3", str(out)], check=True)


def create_container(ig_user: str, token: str, video_url: str, caption: str, cover_url: str | None) -> str:
    data = {"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true", "access_token": token}
    if cover_url:
        data["cover_url"] = cover_url
    r = httpx.post(f"{GRAPH}/{ig_user}/media", data=data, timeout=60)
    body = r.json()
    if r.status_code != 200 or "id" not in body:
        raise RuntimeError(f"container creation failed: {body}")
    return body["id"]


def wait_container(creation_id: str, token: str, timeout_s: int = 600) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        r = httpx.get(f"{GRAPH}/{creation_id}", params={"fields": "status_code,status", "access_token": token}, timeout=30).json()
        code = r.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {code}: {r}")
        time.sleep(8)
    raise TimeoutError("container did not finish processing")


def publish_container(ig_user: str, token: str, creation_id: str) -> PublishResult:
    r = httpx.post(f"{GRAPH}/{ig_user}/media_publish", data={"creation_id": creation_id, "access_token": token}, timeout=60).json()
    if "id" not in r:
        raise RuntimeError(f"publish failed: {r}")
    media_id = r["id"]
    info = httpx.get(f"{GRAPH}/{media_id}", params={"fields": "permalink", "access_token": token}, timeout=30).json()
    return PublishResult(media_id=media_id, permalink=info.get("permalink", ""), video_url="")


def publish_package(package_dir: Path, confirm: bool) -> dict:
    meta = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    video = package_dir / meta["video"]
    cover = package_dir / meta["cover"] if meta.get("cover") else None
    caption = (package_dir / "caption.txt").read_text(encoding="utf-8").strip()
    qa = meta.get("qa", "")
    if not str(qa).startswith("PASS"):
        raise RuntimeError(f"refusing to publish: QA is '{qa}'")
    token = _env("IG_ACCESS_TOKEN")
    ig_user = _env("IG_USER_ID")
    dry = not confirm
    plan = {"video": str(video), "bytes": video.stat().st_size, "caption_chars": len(caption), "cover": str(cover) if cover else None, "credentials_present": bool(token and ig_user), "mode": "DRY RUN" if dry else "LIVE"}
    if dry:
        video_url, cover_url = host_on_github(video, cover, meta["id"], dry_run=True)
        plan.update({"would_host_at": video_url, "would_cover_at": cover_url})
        return plan
    if not token or not ig_user:
        raise RuntimeError("IG_ACCESS_TOKEN and IG_USER_ID must be set in .env before a live publish")
    video_url, cover_url = host_on_github(video, cover, meta["id"], dry_run=False)
    creation = create_container(ig_user, token, video_url, caption, cover_url)
    wait_container(creation, token)
    result = publish_container(ig_user, token, creation)
    meta.update({"status": "published", "post_url": result.permalink, "media_id": result.media_id, "video_url": video_url, "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    (package_dir / "package.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    plan.update({"hosted_at": video_url, "media_id": result.media_id, "permalink": result.permalink})
    return plan


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True, help="output/approved/<date>/<id>")
    ap.add_argument("--confirm", action="store_true", help="actually host and publish (default is a dry run)")
    args = ap.parse_args(argv)
    result = publish_package(Path(args.package), args.confirm)
    print(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
