# RSY Sales Bot (@RSYSalesBot)

Posts every new **Redacted Schizo Yuppies** sale to X automatically, with the NFT image.
It runs for free on GitHub Actions every 5 minutes, reads sales from Magic Eden (which
also reports Tensor sales), and posts as **@RSYSalesBot** using *your own* X API keys.

Example post:

```
𝐑𝐄𝐃𝐀𝐂𝐓𝐄𝐃 @SchizoYuppies SALE‼️

📎 RSY #1835

💰 Sold: 0.17 SOL

🥃 Buyer: 3HZjiA...

🪓 Seller: 6Fvwa3...

🔗 Source: Magic Eden

FUCK THE POOR‼️
```

## What's in here

| File | What it does |
| --- | --- |
| `bot.py` | Checks Magic Eden, builds the posts, uploads the image and posts to X |
| `requirements.txt` | Python libraries the bot needs |
| `.github/workflows/sales.yml` | Tells GitHub to run the bot every 5 minutes |
| `state.json` | The bot's memory of which sales it already posted. **Don't delete it.** |
| `.gitignore` | Keeps downloaded images and junk files out of the repo |

`state.json` is already filled with every sale up to **Nov 15, 2026 12:03 PM ET**, so the
first run will NOT re-post old sales. Only sales after that get posted.

---

## Setup (about 20 minutes, no coding)

### 1. Put these files on GitHub

1. Make a free account at <https://github.com/signup> (skip if you have one).
2. Click **+** (top right) → **New repository**. Name it e.g. `rsy-sales-bot`.
   - **Public is recommended**: GitHub Actions is completely free for public repos. Your X keys are
     *not* in the files (they go in encrypted "secrets", step 3), and `state.json` only holds public
     blockchain transaction IDs.
   - **Private works too**, but private repos only get about 2,000 free Actions minutes a month,
     and running every 5 minutes uses roughly 8,600. If you go private, change the schedule to every
     30 minutes (see "Changing things" below) or add billing to GitHub.
3. On the new repo page click **uploading an existing file**, unzip `rsy-sales-bot.zip` on your
   computer, and drag in **everything inside the folder** (including the `.github` folder; on a
   Mac press Cmd+Shift+. in Finder to show hidden folders). Click **Commit changes**.
   - Check that `.github/workflows/sales.yml` shows up in the repo. If the upload dropped the
     `.github` folder, click **Add file → Create new file**, type `.github/workflows/sales.yml`
     as the name, paste the file's contents, and commit.

### 2. Get X API keys for @RSYSalesBot

Important: do this while signed in to X **as @RSYSalesBot**, not your personal account. The keys
post as whichever account created them.

1. In your browser, sign in to x.com as **@RSYSalesBot**.
2. Go to the X Developer Console: <https://console.x.com> (also reachable from
   <https://developer.x.com>). Accept the developer agreement and fill in the short profile
   (use case e.g. "Posts NFT sales announcements for my collection").
3. **Add credits.** The X API is pay-per-use: you buy credits upfront and each post costs about
   **$0.015** (posts with a link cost much more, which is why these posts have no links).
   At a few sales a day that's pennies. Without credits, posting fails. Check current rates in the
   console; X also gives some free credits when you first add a card. Consider turning on a small
   auto-recharge or spending limit.
4. Create an app (**New App** / project + app).
5. Open the app's **User authentication settings** → **Set up** / **Edit**:
   - App permissions: **Read and write**
   - Type of app: **Web App, Automated App or Bot**
   - Callback URL: `https://example.com` and Website URL: any site you own (e.g. your X profile
     URL `https://x.com/RSYSalesBot`). These are required fields but the bot doesn't use them.
   - Save.
6. Go to the app's **Keys and tokens** page:
   - **API Key and Secret** (a.k.a. Consumer Key/Secret): generate/regenerate and copy both.
   - **Access Token and Secret**: click **Generate** (or **Regenerate**) and copy both.
     **You must (re)generate the access token AFTER setting Read and write**, otherwise the token
     stays read-only and posting fails with a 403 error. Make sure it says it was created with
     *Read and Write* permissions and belongs to @RSYSalesBot.
   - Keys are shown only once. Keep them somewhere safe (a password manager) and never share them.

### 3. Add the 4 keys to GitHub as secrets

In your repo: **Settings → Secrets and variables → Actions → New repository secret**. Add these
four, with exactly these names:

| Name | Value |
| --- | --- |
| `X_API_KEY` | API Key (Consumer Key) |
| `X_API_SECRET` | API Key Secret (Consumer Secret) |
| `X_ACCESS_TOKEN` | Access Token |
| `X_ACCESS_TOKEN_SECRET` | Access Token Secret |

GitHub encrypts these; nobody (including people viewing a public repo) can read them back.

### 4. Test it, then turn it on

1. Open the **Actions** tab. If GitHub asks, click **I understand my workflows, go ahead and enable them**.
2. Click **RSY sales bot** on the left → **Run workflow**. Leave **Dry run** ticked → **Run workflow**.
3. Click the run → **check-sales** → open the **Check Magic Eden and post new sales** step. You
   should see `No new sales.` (or the text of posts it *would* send). Dry runs never post and never
   change `state.json`.
4. That's it: the schedule is on automatically and checks every 5 minutes. The first real post
   happens on the next sale. After it posts, check @RSYSalesBot on X.
5. To force a real run right away, use **Run workflow** with **Dry run unticked**.

To pause the bot: Actions tab → **RSY sales bot** → **⋯** → **Disable workflow**.

If a run fails, GitHub emails you (the repo owner). Open the failed run to see why; the common
causes are listed under "Troubleshooting".

---

## Changing things

All in `bot.py` / `sales.yml`. On GitHub, open the file → pencil icon (✏️) → edit → **Commit changes**.

- **Post text:** in `bot.py`, edit `POST_TEMPLATE` near the top. Each `"...\n"` is one line; a line
  with only `"\n"` is the blank line between rows. Keep the `{number}`, `{price}`, `{buyer}`,
  `{seller}` and `{source}` placeholders where you want those values. The bold 𝐑𝐄𝐃𝐀𝐂𝐓𝐄𝐃 uses
  special Unicode letters; copy-paste it rather than retyping. Avoid adding links (costs more
  per post).
- **How often it checks:** in `.github/workflows/sales.yml`, change `"*/5 * * * *"` to e.g.
  `"*/15 * * * *"` (every 15 min) or `"*/30 * * * *"` (every 30 min). 5 minutes is GitHub's minimum.
- **Max posts per run:** `MAX_POSTS_PER_RUN` in `bot.py` (default 10). If more than that many new
  sales show up at once (e.g. after a long outage), only the newest 10 get posted and the older
  ones are skipped, so the account doesn't spam.

## How it works (details)

- **Sales source:** `GET https://api-mainnet.magiceden.dev/v2/collections/redacted_schizo_yuppies/activities?type=buyNow`
  (newest 100). This feed includes Tensor sales. The `source` field is mapped:
  `magiceden_v2`, `mmm`, `m2`, `m3` → **Magic Eden**; anything containing `tensor`
  (e.g. `tensortrade`) → **Tensor**; anything else → the raw value (and a warning in the log).
- **NFT number & image:** `GET /v2/tokens/{mint}`; the number comes from the name
  (`REDACTED Schizo Yuppie #1835`). Images are ~1.1 MB PNGs and are uploaded as-is; if one is ever
  over ~4.8 MB (X's image limit is 5 MB) it's converted to JPEG and shrunk until it fits. If the
  image can't be downloaded the sale is posted without it.
- **No duplicates:** `state.json` keeps the last 300 posted transaction signatures plus the newest
  posted sale time. After each run GitHub commits `state.json` back (only if it changed). Runs never
  overlap (`concurrency`).
- **Order and retries:** posts go out oldest first, ~3 seconds apart. A sale is only marked done after
  X accepts it. If a post fails it's retried on the next run, up to 3 attempts per sale, then it's
  skipped and logged (no infinite loops). If X says the post is a duplicate, it's treated as posted.
  Auth, credit, permission, and rate-limit errors stop the run early, and the run shows as failed.
- **Dry run:** `python bot.py --dry-run` or `DRY_RUN=1` prints the posts and saves images to `images/`
  without contacting X or changing `state.json`.

### X API used (OAuth 1.0a user context, Read and write app)

1. `POST https://api.x.com/2/media/upload`: one-shot image upload (multipart: `media` +
   `media_category=tweet_image`), returns `data.id`. The old v1.1 `upload.twitter.com` endpoint
   is no longer used.
2. `POST https://api.x.com/2/tweets`: `{"text": ..., "media": {"media_ids": [id]}}`.

Requests are signed with `requests-oauthlib` (`OAuth1Session`) using the 4 secrets.

Docs relied on:
- Upload Media (v2): <https://docs.x.com/x-api/media/upload-media>
- Media best practices / size limits (images ≤ 5 MB): <https://docs.x.com/x-api/media/quickstart/best-practices>
- Chunked upload (videos only, not needed here): <https://docs.x.com/x-api/media/quickstart/media-upload-chunked>
- Create Post: <https://docs.x.com/x-api/posts/create-post>
- Getting access / credentials: <https://docs.x.com/x-api/getting-started/getting-access>
- App permissions (Read and write; regenerate tokens after changing): <https://docs.x.com/resources/fundamentals/developer-apps>
- API key and secret: <https://docs.x.com/resources/fundamentals/authentication/oauth-1-0a/api-key-and-secret>
- Pay-per-use pricing and credits: <https://docs.x.com/x-api/getting-started/pricing>

## GitHub Actions caveats

- **Scheduled runs can be late.** GitHub runs cron jobs "best effort"; at busy times a 5-minute
  schedule may run 10-30+ minutes late or occasionally skip a slot. Sales are not lost: each run looks
  at the latest 100 sales and the state file.
- **60-day pause (public repos).** GitHub disables scheduled workflows in public repos after 60 days with
  no repository activity. Every posted sale commits `state.json`, which counts as activity, so this only
  happens if there are no sales for 60 days. If it does, GitHub emails you; re-enable it from the
  Actions tab (**Enable workflow**).
- **Minutes on private repos:** see step 1.
- Docs: <https://docs.github.com/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule>

## Troubleshooting

| Log message | Fix |
| --- | --- |
| `Missing secrets: ...` | Add the 4 secrets in step 3 (names must match exactly). |
| `HTTP 401` | Wrong or old keys. Regenerate and update the secrets. |
| `HTTP 403` (not duplicate) | App isn't Read and write, or the access token was made before you switched it. Regenerate the access token. |
| `HTTP 402` / credits / payment | Add X API credits in the Developer Console. |
| `HTTP 429` | Rate limit. It retries automatically next run. |
| Posts appear on the wrong account | The keys were generated while signed in as the wrong X account. Redo step 2 as @RSYSalesBot. |
| `Could not push state.json` | Settings → Actions → General → Workflow permissions → choose **Read and write permissions**. |

## Running it on your own computer (optional)

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python bot.py --dry-run
```
