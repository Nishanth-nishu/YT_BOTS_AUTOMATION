# Publishing to Instagram

REELFORGE never posts on its own. Every reel ends as a package in `output/approved/<date>/<id>/` with the MP4, cover, caption, hashtags, sources and a checklist. From there you can upload manually, or let the official Instagram Graph API publisher post it after you approve.

## Option A: manual upload (works today)

1. Open the package folder, send the MP4 and cover to your phone (or use Instagram on the web).
2. Create a Reel, pick `cover.png` as the cover, paste `caption.txt`.
3. Record the post URL in `package.json` under `post_url`.

## Option B: Graph API publishing (one-time setup, free)

Requirements set by Meta, not by REELFORGE:

1. An Instagram **Professional** account (Creator or Business), linked to a Facebook Page.
2. A Meta developer app (developers.facebook.com) with the **Instagram Graph API** product.
3. A long-lived user access token with scopes `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`. Use the Graph API Explorer to generate a short-lived token, then exchange it for a long-lived one (about 60 days).
4. Your numeric Instagram user id: `GET /me/accounts` for the page id, then `GET /<page-id>?fields=instagram_business_account`.
5. Put both in `.env` (git-ignored):
   ```
   IG_ACCESS_TOKEN=...
   IG_USER_ID=...
   ```

Instagram downloads the video from a public HTTPS URL. REELFORGE hosts the approved MP4 on the project's public GitHub repository on an orphan `media` branch and uses the `raw.githubusercontent.com` URL, which costs nothing. Set `PUBLIC_MEDIA_BASE_URL` in `.env` to use another host.

Publish flow (`services/publishing/instagram.py`):

```bash
# dry run: shows what would be hosted and posted, touches nothing
.venv\Scripts\python -m services.publishing.instagram --package output/approved/2026-11-08/gpt6-cyber
# live: hosts the file, creates a REELS container, waits for processing, publishes, records the permalink
.venv\Scripts\python -m services.publishing.instagram --package output/approved/2026-11-08/gpt6-cyber --confirm
```

Safeguards: the publisher refuses any package whose technical QA did not pass, defaults to a dry run, and requires `--confirm` plus credentials for a live post. Meta rate-limits content publishing to 100 posts per 24 hours per account, far above three reels a day.

## What is not supported

Unofficial Instagram automation (browser bots, private API clients) is excluded by design: it violates Instagram's terms and risks the account.
