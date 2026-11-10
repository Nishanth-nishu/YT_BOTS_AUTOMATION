# Publishing to Instagram

REELFORGE never posts on its own. Every reel ends as a package in `output/approved/<date>/<id>/` with the MP4, cover, caption, hashtags, sources and a checklist. From there you can upload manually, or let the official Instagram Graph API publisher post it after you approve.

## Option A: manual upload (works today)

1. Open the package folder, send the MP4 and cover to your phone (or use Instagram on the web).
2. Create a Reel, pick `cover.png` as the cover, paste `caption.txt`.
3. Record the post URL in `package.json` under `post_url`.

## Option B: Graph API publishing (one-time setup, free)

Two flavours exist; the publisher supports both via `IG_API_HOST` in `.env`.

**Unified / Instagram login (recommended, no Facebook Page needed)**

1. Instagram app: Settings → Account type and tools → switch to a **Professional** account (Creator or Business).
2. https://developers.facebook.com/apps/ → your app → Products → Instagram → **API setup with Unified login**.
3. Step 2 "Generate access tokens": **Add account**, log in with the Instagram account, then click **Generate token** next to it and approve. The number shown beside the username is the Instagram user id.
4. Put them in `.env` (git-ignored):
   ```
   IG_ACCESS_TOKEN=...
   IG_USER_ID=<number beside the username>
   IG_API_HOST=facebook
   ```
   Unified-login tokens are used against graph.facebook.com; set `instagram` only for a token from the older Instagram-login-only product.
5. Verify without posting: `.venv\Scripts\python -m services.publishing.instagram --check`

**Facebook login (needs an Instagram Professional account linked to a Facebook Page)**

1. Graph API Explorer (https://developers.facebook.com/tools/explorer/): pick the app, "Get User Access Token", add `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, Generate Access Token and select the Page and Instagram account in the dialog.
2. Extend it at https://developers.facebook.com/tools/debug/accesstoken/ (about 60 days).
3. `GET me/accounts?fields=instagram_business_account` gives the Instagram user id. Set `IG_API_HOST=facebook`.

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
