"""YouTube publishing through the official YouTube Data API v3 (free, no SDK).

Only httpx is used: OAuth 2.0 for a Desktop client (loopback redirect + PKCE)
and a resumable upload, so there is no browser automation and no extra
dependency.

One-time setup (free):
  1. console.cloud.google.com: create a project, enable "YouTube Data API v3".
  2. OAuth consent screen: External, add your Google account, then set the
     publishing status to "In production" (in "Testing" the refresh token
     expires after 7 days).
  3. Credentials: create an OAuth client ID of type "Desktop app".
  4. Put the two values in .env (never in the repo):
         YOUTUBE_CLIENT_ID=...
         YOUTUBE_CLIENT_SECRET=...
  5. python -m services.publishing.youtube --auth
     (opens the browser once and writes YOUTUBE_REFRESH_TOKEN into .env)

Usage (always a dry run unless --confirm):
    python -m services.publishing.youtube --check
    python -m services.publishing.youtube --package output/approved/<date>/<id> [--confirm]
    python -m services.publishing.youtube --video x.mp4 --title "..." [--description-file d.txt] [--confirm]

Defaults are deliberately safe: privacy "private", a failed or missing QA is
refused for packages, the same id is never uploaded twice, and a daily cap
keeps the run inside the API quota (10,000 units a day; one upload costs
about 1,600, so six a day at most). Every upload is logged in SQLite.

Note: videos uploaded by an API project that has not passed Google's audit
are locked to private by YouTube. Request the audit once the channel is real.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import re
import secrets
import sqlite3
import sys
import time
import urllib.parse
import webbrowser
from pathlib import Path

import httpx

from services.common import paths
from services.common.env import load_dotenv

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD_API = "https://www.googleapis.com/upload/youtube/v3"
# Upload only, plus read-only so --check can name the channel. No account management scope.
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]

CHUNK = 8 * 1024 * 1024  # must be a multiple of 256 KiB
UPLOAD_QUOTA_UNITS = 1600
DEFAULT_DAILY_CAP = 6
TITLE_MAX = 100
DESCRIPTION_MAX = 5000
TAGS_MAX_CHARS = 500
SHORTS_MAX_SECONDS = 180
CATEGORIES = {"film": "1", "music": "10", "gaming": "20", "people": "22", "comedy": "23", "entertainment": "24", "news": "25", "howto": "26", "education": "27", "science": "28"}


# ---------------------------------------------------------------- metadata

def clean_title(title: str, shorts: bool) -> str:
    """YouTube rejects '<' and '>' and titles over 100 characters."""
    t = re.sub(r"[<>]", "", title).strip()
    suffix = " #Shorts" if shorts and "#shorts" not in t.lower() else ""
    room = TITLE_MAX - len(suffix)
    if len(t) > room:
        t = t[: room - 1].rstrip() + "…"
    return t + suffix


def clean_tags(tags: list[str]) -> list[str]:
    """Strip '#', drop duplicates, and stay under the 500-character total."""
    out: list[str] = []
    used = 0
    for raw in tags:
        tag = raw.strip().lstrip("#").strip()
        if not tag or tag.lower() in (t.lower() for t in out):
            continue
        cost = len(tag) + (2 if " " in tag else 0) + (1 if out else 0)
        if used + cost > TAGS_MAX_CHARS:
            break
        out.append(tag)
        used += cost
    return out


def build_metadata(title: str, description: str = "", tags: list[str] | None = None, *, category: str = "comedy", privacy: str = "private",
                   publish_at: str | None = None, shorts: bool = True, synthetic: bool = False, language: str = "en") -> dict:
    if privacy not in ("private", "unlisted", "public"):
        raise ValueError(f"privacy must be private, unlisted or public, not '{privacy}'")
    category_id = CATEGORIES.get(category.lower(), category)
    if not str(category_id).isdigit():
        raise ValueError(f"unknown category '{category}' (use one of {sorted(CATEGORIES)} or a numeric id)")
    desc = re.sub(r"[<>]", "", description).strip()[:DESCRIPTION_MAX]
    status: dict = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "containsSyntheticMedia": bool(synthetic)}
    if publish_at:
        # A scheduled video must be private until YouTube flips it.
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at
    return {
        "snippet": {"title": clean_title(title, shorts), "description": desc, "tags": clean_tags(tags or []), "categoryId": str(category_id),
                    "defaultLanguage": language, "defaultAudioLanguage": language},
        "status": status,
    }


def metadata_from_package(package_dir: Path, **overrides) -> tuple[dict, Path, Path | None, dict]:
    """Read a package built by services.publishing.package. A "youtube" object in
    package.json ({"title","description","tags","category"}) wins over the defaults."""
    meta = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    qa = str(meta.get("qa", ""))
    if not qa.startswith("PASS"):
        raise RuntimeError(f"refusing to publish: QA is '{qa}'")
    yt = meta.get("youtube") or {}
    video = package_dir / meta["video"]
    cover = package_dir / meta["cover"] if meta.get("cover") and (package_dir / meta["cover"]).exists() else None
    read = lambda name: (package_dir / name).read_text(encoding="utf-8").strip() if (package_dir / name).exists() else ""
    hashtags = [h for h in read("hashtags.txt").splitlines() if h.strip()]
    sources = [s for s in read("sources.txt").splitlines() if s.strip()]
    description = yt.get("description")
    if description is None:
        description = read("caption.txt")
        if sources:
            description += "\n\nSources:\n" + "\n".join(sources)
    if overrides.get("category") is None:
        overrides["category"] = yt.get("category", "comedy")
    body = build_metadata(yt.get("title") or meta["title"], description, yt.get("tags") or hashtags, **overrides)
    return body, video, cover, meta


# ---------------------------------------------------------------- upload log

def _db(db_path: Path | None = None) -> sqlite3.Connection:
    p = db_path or paths.DATABASE
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.execute("""CREATE TABLE IF NOT EXISTS youtube_uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT, video_id TEXT NOT NULL, url TEXT NOT NULL, title TEXT,
        privacy TEXT, publish_at TEXT, file TEXT, bytes INTEGER, uploaded_at REAL NOT NULL)""")
    return con


def uploads_last_24h(db_path: Path | None = None, now: float | None = None) -> int:
    with _db(db_path) as con:
        return con.execute("SELECT COUNT(*) FROM youtube_uploads WHERE uploaded_at > ?", ((now or time.time()) - 86400,)).fetchone()[0]


def already_uploaded(item_id: str, db_path: Path | None = None) -> str | None:
    with _db(db_path) as con:
        row = con.execute("SELECT url FROM youtube_uploads WHERE item_id = ? ORDER BY id DESC LIMIT 1", (item_id,)).fetchone()
    return row[0] if row else None


def record_upload(item_id: str | None, video_id: str, body: dict, video: Path, db_path: Path | None = None) -> None:
    with _db(db_path) as con:
        con.execute("INSERT INTO youtube_uploads (item_id, video_id, url, title, privacy, publish_at, file, bytes, uploaded_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (item_id, video_id, f"https://youtu.be/{video_id}", body["snippet"]["title"], body["status"]["privacyStatus"],
                     body["status"].get("publishAt"), str(video), video.stat().st_size, time.time()))


def daily_cap() -> int:
    return int(os.environ.get("YOUTUBE_MAX_UPLOADS_PER_DAY") or DEFAULT_DAILY_CAP)


# ---------------------------------------------------------------- OAuth

def _client_credentials() -> tuple[str, str]:
    load_dotenv()
    cid, secret = os.environ.get("YOUTUBE_CLIENT_ID"), os.environ.get("YOUTUBE_CLIENT_SECRET")
    if not cid or not secret:
        raise RuntimeError("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set in .env (see the setup steps at the top of this file)")
    return cid, secret


def save_env_value(key: str, value: str, env_file: Path | None = None) -> None:
    """Write or replace KEY=value in the git-ignored .env without touching other lines."""
    f = env_file or (paths.ROOT / ".env")
    lines = f.read_text(encoding="utf-8").splitlines() if f.exists() else []
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value


def authorize(open_browser: bool = True, timeout_s: int = 300) -> None:
    """Desktop-app OAuth: loopback redirect on a free port, PKCE, offline access.
    The refresh token goes straight into .env and is never printed."""
    cid, secret = _client_credentials()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(24)
    got: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state:
                got.update({k: v[0] for k, v in q.items()})
            ok = "code" in got
            self.send_response(200 if ok else 400)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(("Authorised. You can close this tab." if ok else "Authorisation failed.").encode())

        def log_message(self, *a):  # keep the code out of the console
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect = f"http://127.0.0.1:{server.server_address[1]}"
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": " ".join(SCOPES), "access_type": "offline",
        "prompt": "consent", "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})
    print("Open this URL in your browser and approve access:\n" + url)
    if open_browser:
        webbrowser.open(url)
    server.timeout = 5
    t0 = time.time()
    while "code" not in got and "error" not in got and time.time() - t0 < timeout_s:
        server.handle_request()
    server.server_close()
    if "code" not in got:
        raise RuntimeError(f"authorisation did not complete: {got.get('error', 'timed out')}")
    r = httpx.post(TOKEN_URL, data={"client_id": cid, "client_secret": secret, "code": got["code"], "code_verifier": verifier,
                                    "grant_type": "authorization_code", "redirect_uri": redirect}, timeout=30)
    tok = r.json()
    if r.status_code != 200 or "refresh_token" not in tok:
        raise RuntimeError(f"token exchange failed: {tok.get('error_description') or tok.get('error') or r.status_code}")
    save_env_value("YOUTUBE_REFRESH_TOKEN", tok["refresh_token"])
    print("Saved YOUTUBE_REFRESH_TOKEN to .env")


def access_token(client: httpx.Client) -> str:
    cid, secret = _client_credentials()
    refresh = os.environ.get("YOUTUBE_REFRESH_TOKEN")
    if not refresh:
        raise RuntimeError("YOUTUBE_REFRESH_TOKEN is missing; run: python -m services.publishing.youtube --auth")
    r = client.post(TOKEN_URL, data={"client_id": cid, "client_secret": secret, "refresh_token": refresh, "grant_type": "refresh_token"})
    tok = r.json()
    if r.status_code != 200 or "access_token" not in tok:
        hint = " (run --auth again; if the consent screen is in Testing the token expires after 7 days)" if tok.get("error") == "invalid_grant" else ""
        raise RuntimeError(f"token refresh failed: {tok.get('error_description') or tok.get('error')}{hint}")
    return tok["access_token"]


# ---------------------------------------------------------------- API calls

def _api_error(r: httpx.Response) -> str:
    try:
        err = r.json().get("error", {})
        reason = (err.get("errors") or [{}])[0].get("reason", "")
        return f"{r.status_code} {reason}: {err.get('message', '')}".strip()
    except Exception:
        return f"{r.status_code} {r.text[:200]}"


def check_credentials(client: httpx.Client) -> dict:
    """Read-only: confirm the token works and name the channel. Never prints a token."""
    token = access_token(client)
    r = client.get(f"{API}/channels", params={"part": "snippet,status", "mine": "true"}, headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        raise RuntimeError("channel lookup failed: " + _api_error(r))
    items = r.json().get("items", [])
    if not items:
        raise RuntimeError("the authorised Google account has no YouTube channel")
    ch = items[0]
    return {"channel_id": ch["id"], "channel": ch["snippet"]["title"], "long_uploads": ch.get("status", {}).get("longUploadsStatus"),
            "uploads_last_24h": uploads_last_24h(), "daily_cap": daily_cap()}


def resumable_upload(client: httpx.Client, token: str, video: Path, body: dict, chunk: int = CHUNK, retries: int = 5, progress=None) -> str:
    """Start a resumable session, send the file in chunks, resume after errors. Returns the video id."""
    size = video.stat().st_size
    auth = {"Authorization": f"Bearer {token}"}
    start = client.post(f"{UPLOAD_API}/videos", params={"uploadType": "resumable", "part": "snippet,status"}, json=body,
                        headers={**auth, "X-Upload-Content-Type": "video/*", "X-Upload-Content-Length": str(size)})
    if start.status_code != 200 or "location" not in start.headers:
        raise RuntimeError("could not start the upload: " + _api_error(start))
    session = start.headers["location"]
    offset, failures = 0, 0
    with video.open("rb") as fh:
        while True:
            fh.seek(offset)
            data = fh.read(chunk)
            try:
                r = client.put(session, content=data, headers={**auth, "Content-Length": str(len(data)), "Content-Range": f"bytes {offset}-{offset + len(data) - 1}/{size}"})
            except httpx.TransportError:
                r = None
            if r is not None and r.status_code in (200, 201):
                return r.json()["id"]
            if r is not None and r.status_code == 308:
                offset = _next_offset(r)
                failures = 0
            elif r is None or r.status_code in (500, 502, 503, 504):
                failures += 1
                if failures > retries:
                    raise RuntimeError("upload kept failing: " + ("network error" if r is None else _api_error(r)))
                time.sleep(min(2 ** failures, 30) if retries else 0)
                # Ask the server how much it has, then carry on from there.
                q = client.put(session, headers={**auth, "Content-Length": "0", "Content-Range": f"bytes */{size}"})
                if q.status_code in (200, 201):
                    return q.json()["id"]
                if q.status_code == 308:
                    offset = _next_offset(q)
            else:
                raise RuntimeError("upload rejected: " + _api_error(r))
            if progress:
                progress(offset, size)


def _next_offset(r: httpx.Response) -> int:
    """A 308 carries 'Range: bytes=0-N' for what the server holds; no header means nothing yet."""
    m = re.match(r"bytes=0-(\d+)", r.headers.get("range", ""))
    return int(m.group(1)) + 1 if m else 0


def set_thumbnail(client: httpx.Client, token: str, video_id: str, image: Path) -> None:
    """Needs a phone-verified channel; the image must be under 2 MB."""
    mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
    r = client.post(f"{UPLOAD_API}/thumbnails/set", params={"videoId": video_id, "uploadType": "media"}, content=image.read_bytes(),
                    headers={"Authorization": f"Bearer {token}", "Content-Type": mime})
    if r.status_code != 200:
        raise RuntimeError("thumbnail upload failed: " + _api_error(r))


# ---------------------------------------------------------------- orchestration

def publish(video: Path, body: dict, *, confirm: bool, item_id: str | None = None, thumbnail: Path | None = None, force: bool = False,
            client: httpx.Client | None = None, db_path: Path | None = None) -> dict:
    if not video.exists():
        raise FileNotFoundError(video)
    used, cap = uploads_last_24h(db_path), daily_cap()
    plan = {"mode": "LIVE" if confirm else "DRY RUN", "video": str(video), "bytes": video.stat().st_size, "title": body["snippet"]["title"],
            "description_chars": len(body["snippet"]["description"]), "tags": body["snippet"]["tags"], "category": body["snippet"]["categoryId"],
            "privacy": body["status"]["privacyStatus"], "publish_at": body["status"].get("publishAt"), "thumbnail": str(thumbnail) if thumbnail else None,
            "uploads_last_24h": used, "daily_cap": cap, "quota_units": UPLOAD_QUOTA_UNITS}
    previous = already_uploaded(item_id, db_path) if item_id else None
    if previous and not force:
        raise RuntimeError(f"'{item_id}' was already uploaded: {previous} (use --force to upload it again)")
    if used >= cap:
        raise RuntimeError(f"daily cap reached: {used} uploads in the last 24 hours (cap {cap})")
    if not confirm:
        load_dotenv()
        plan["credentials_present"] = all(os.environ.get(k) for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"))
        return plan
    own = client is None
    client = client or httpx.Client(timeout=httpx.Timeout(60, write=300))
    try:
        token = access_token(client)
        video_id = resumable_upload(client, token, video, body, progress=lambda done, total: print(f"  uploaded {done * 100 // total}%", flush=True))
        record_upload(item_id, video_id, body, video, db_path)
        plan.update({"video_id": video_id, "url": f"https://youtu.be/{video_id}"})
        if thumbnail:
            try:
                set_thumbnail(client, token, video_id, thumbnail)
                plan["thumbnail_set"] = True
            except RuntimeError as e:  # the video is up; report the thumbnail problem without losing the id
                plan["thumbnail_set"] = False
                plan["thumbnail_error"] = str(e)
    finally:
        if own:
            client.close()
    return plan


def publish_package(package_dir: Path, *, confirm: bool, force: bool = False, client: httpx.Client | None = None, db_path: Path | None = None, **overrides) -> dict:
    body, video, cover, meta = metadata_from_package(package_dir, **overrides)
    plan = publish(video, body, confirm=confirm, item_id=meta["id"], thumbnail=cover, force=force, client=client, db_path=db_path)
    if confirm:
        meta["youtube_upload"] = {"video_id": plan["video_id"], "url": plan["url"], "privacy": plan["privacy"], "publish_at": plan["publish_at"],
                                  "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        (package_dir / "package.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return plan


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Upload a video to YouTube with the official Data API (dry run unless --confirm).")
    ap.add_argument("--auth", action="store_true", help="one-time browser sign-in; writes YOUTUBE_REFRESH_TOKEN to .env")
    ap.add_argument("--check", action="store_true", help="read-only: verify the credentials and name the channel")
    ap.add_argument("--package", help="output/approved/<date>/<id> (QA must be PASS)")
    ap.add_argument("--video", help="upload a bare MP4 instead of a package (no QA gate)")
    ap.add_argument("--title")
    ap.add_argument("--description-file")
    ap.add_argument("--tags", default="", help="comma separated")
    ap.add_argument("--thumbnail")
    ap.add_argument("--category", default=None, help="name or numeric id (default comedy)")
    ap.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    ap.add_argument("--publish-at", default=None, help="schedule, ISO 8601 UTC, e.g. 2026-11-12T12:30:00Z (the video stays private until then)")
    ap.add_argument("--synthetic", action="store_true", help="tick YouTube's altered/synthetic content disclosure")
    ap.add_argument("--long-form", action="store_true", help="not a Short: do not append #Shorts to the title")
    ap.add_argument("--force", action="store_true", help="upload even if this id was uploaded before")
    ap.add_argument("--confirm", action="store_true", help="actually upload (default is a dry run)")
    args = ap.parse_args(argv)
    load_dotenv()
    try:
        if args.auth:
            authorize()
            return 0
        if args.check:
            with httpx.Client(timeout=30) as c:
                print(json.dumps(check_credentials(c), indent=1))
            return 0
        opts = dict(category=args.category, privacy=args.privacy, publish_at=args.publish_at, shorts=not args.long_form, synthetic=args.synthetic)
        if args.package:
            result = publish_package(Path(args.package), confirm=args.confirm, force=args.force, **opts)
        elif args.video and args.title:
            desc = Path(args.description_file).read_text(encoding="utf-8") if args.description_file else ""
            opts["category"] = opts["category"] or "comedy"
            body = build_metadata(args.title, desc, [t for t in args.tags.split(",") if t.strip()], **opts)
            result = publish(Path(args.video), body, confirm=args.confirm, item_id=Path(args.video).stem, thumbnail=Path(args.thumbnail) if args.thumbnail else None, force=args.force)
        else:
            ap.error("give --package, or --video with --title (or --auth / --check)")
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        print("error:", e, file=sys.stderr)
        return 1
    print(json.dumps(result, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
