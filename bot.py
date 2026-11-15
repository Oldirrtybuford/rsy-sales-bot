#!/usr/bin/env python3
"""RSY (Redacted Schizo Yuppies) sales bot for X.

Reads recent sales from the Magic Eden activity API (which also includes Tensor
sales), formats each new sale, attaches the NFT image and posts it to X as the
account that owns the API keys (@RSYSalesBot).

Usage:
  python bot.py              # post new sales (needs the 4 X_* env vars)
  python bot.py --dry-run    # print posts + save images, never calls X
  DRY_RUN=1 python bot.py    # same as --dry-run

State (state.json): seen signatures, last blockTime, failed-attempt counters.
"""
import argparse
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Settings you might want to change
# ---------------------------------------------------------------------------
COLLECTION = "redacted_schizo_yuppies"
ME_API = "https://api-mainnet.magiceden.dev/v2"

# The post text. {number}, {price}, {buyer}, {seller}, {source} are filled in.
POST_TEMPLATE = (
    "𝐑𝐄𝐃𝐀𝐂𝐓𝐄𝐃 @SchizoYuppies SALE‼️\n"
    "\n"
    "📎 RSY #{number}\n"
    "\n"
    "💰 Sold: {price} SOL\n"
    "\n"
    "🥃 Buyer: {buyer}\n"
    "\n"
    "🪓 Seller: {seller}\n"
    "\n"
    "🔗 Source: {source}\n"
    "\n"
    "FUCK THE POOR‼️"
)

MAX_ATTEMPTS = 3            # give up on a sale after this many failed posts
SEEN_CAP = 300              # how many signatures to remember
MAX_POSTS_PER_RUN = int(os.environ.get("MAX_POSTS_PER_RUN", "10"))  # flood guard
LOOKBACK_SECS = 3600        # also consider unseen sales up to 1h older than the last posted one
SECONDS_BETWEEN_POSTS = 3
X_IMAGE_LIMIT = 5 * 1024 * 1024   # X: tweet_image max 5 MB
TARGET_IMAGE_BYTES = 4_800_000     # stay a little under the limit

# X API v2 endpoints (OAuth 1.0a user context)
X_MEDIA_UPLOAD = "https://api.x.com/2/media/upload"   # one-shot image upload
X_CREATE_POST = "https://api.x.com/2/tweets"           # create post

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "rsy-sales-bot/1.0 (+github actions)"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Magic Eden
# ---------------------------------------------------------------------------
def get_json(url, tries=3):
    err = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=20)
            if r.status_code == 429:
                raise RuntimeError("Magic Eden rate limit (429)")
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(2 * (i + 1))
    raise err


def fetch_sales(total=100):
    """Newest `total` buyNow activities, returned oldest first."""
    acts, offset = [], 0
    while offset < total:
        n = min(100, total - offset)
        page = get_json(f"{ME_API}/collections/{COLLECTION}/activities"
                        f"?offset={offset}&limit={n}&type=buyNow")
        if not page:
            break
        acts.extend(page)
        offset += n
        if len(page) < n:
            break
    sales = {a["signature"]: a for a in acts
             if a.get("type") == "buyNow" and a.get("signature")}
    return sorted(sales.values(), key=lambda a: (a.get("blockTime") or 0, a.get("slot") or 0))


def marketplace(src):
    s = (src or "").lower()
    if "tensor" in s:
        return "Tensor"
    if s in ("magiceden_v2", "magiceden", "mmm", "m2", "m3") or "magiceden" in s:
        return "Magic Eden"
    log(f"warn: unknown sale source {src!r}; posting raw value")
    return src or "Unknown"


def trunc(wallet):
    return (wallet or "unknown")[:6] + "..."


def format_post(sale, number):
    return POST_TEMPLATE.format(
        number=number,
        price=f"{float(sale['price']):.2f}",
        buyer=trunc(sale.get("buyer")),
        seller=trunc(sale.get("seller")),
        source=marketplace(sale.get("source")),
    )


def token_info(mint):
    """Returns (number, image_url) from /v2/tokens/{mint}."""
    t = get_json(f"{ME_API}/tokens/{mint}")
    m = re.search(r"#\s*(\d+)", t.get("name") or "")
    if not m:
        raise RuntimeError(f"could not parse number from name {t.get('name')!r}")
    return m.group(1), t.get("image")


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------
def fit_image(raw):
    """Return (bytes, mime). Re-encode only if over X's 5 MB image limit."""
    from PIL import Image

    img = Image.open(io.BytesIO(raw))
    fmt = (img.format or "PNG").upper()
    mime = {"PNG": "image/png", "JPEG": "image/jpeg", "GIF": "image/gif",
            "WEBP": "image/webp"}.get(fmt)
    if mime and len(raw) <= TARGET_IMAGE_BYTES:
        return raw, mime
    # Too big (or odd format): convert to JPEG, shrinking until it fits.
    img = img.convert("RGB")
    quality, scale = 90, 1.0
    while True:
        w, h = int(img.width * scale), int(img.height * scale)
        im = img if scale == 1.0 else img.resize((w, h), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality, optimize=True)
        if buf.tell() <= TARGET_IMAGE_BYTES or (quality <= 50 and scale <= 0.3):
            return buf.getvalue(), "image/jpeg"
        if quality > 70:
            quality -= 10
        else:
            scale *= 0.8


def download_image(url, number, images_dir):
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    data, mime = fit_image(r.content)
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}[mime]
    os.makedirs(images_dir, exist_ok=True)
    path = os.path.join(images_dir, f"{number}.{ext}")
    with open(path, "wb") as f:
        f.write(data)
    return path, data, mime


# ---------------------------------------------------------------------------
# X API
# ---------------------------------------------------------------------------
class XError(Exception):
    def __init__(self, msg, status=None, duplicate=False, stop=False):
        super().__init__(msg)
        self.status, self.duplicate, self.stop = status, duplicate, stop


def x_session():
    from requests_oauthlib import OAuth1Session

    names = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit(f"Missing secrets: {', '.join(missing)}. Add them in GitHub "
                         "Settings > Secrets and variables > Actions, or use --dry-run.")
    return OAuth1Session(
        client_key=os.environ["X_API_KEY"],
        client_secret=os.environ["X_API_SECRET"],
        resource_owner_key=os.environ["X_ACCESS_TOKEN"],
        resource_owner_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def _raise_for_x(r, what):
    body = r.text[:500]
    dup = "duplicate" in body.lower()
    # 401 bad keys, 402/403 no credits or permissions, 429 rate limit: stop this run.
    stop = r.status_code in (401, 402, 429) or (r.status_code == 403 and not dup)
    raise XError(f"{what} failed: HTTP {r.status_code}: {body}", r.status_code, dup, stop)


def x_upload_image(sess, data, mime, filename):
    r = sess.post(X_MEDIA_UPLOAD,
                  files={"media": (filename, data, mime)},
                  data={"media_category": "tweet_image"},
                  timeout=60)
    if r.status_code >= 300:
        _raise_for_x(r, "media upload")
    d = r.json().get("data") or {}
    media_id = d.get("id") or r.json().get("media_id_string")
    if not media_id:
        raise XError(f"media upload: no id in response {r.text[:300]}")
    return str(media_id)


def x_create_post(sess, text, media_id=None):
    body = {"text": text}
    if media_id:
        body["media"] = {"media_ids": [media_id]}
    r = sess.post(X_CREATE_POST, json=body, timeout=30)
    if r.status_code >= 300:
        _raise_for_x(r, "create post")
    return (r.json().get("data") or {}).get("id")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def load_state(path):
    if not os.path.exists(path):
        return {"last_blockTime": 0, "seen": [], "attempts": {}}
    with open(path) as f:
        st = json.load(f)
    st.setdefault("last_blockTime", 0)
    st.setdefault("seen", [])
    st.setdefault("attempts", {})
    return st


def save_state(path, st):
    st["seen"] = st["seen"][-SEEN_CAP:]
    with open(path, "w") as f:
        json.dump(st, f, indent=1)
        f.write("\n")


def mark_seen(st, sale):
    sig = sale["signature"]
    if sig not in st["seen"]:
        st["seen"].append(sig)
    st["attempts"].pop(sig, None)
    st["last_blockTime"] = max(st["last_blockTime"], sale.get("blockTime") or 0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print posts and save images; never call X")
    ap.add_argument("--state", default=os.path.join(HERE, "state.json"))
    ap.add_argument("--images-dir", default=os.path.join(HERE, "images"))
    ap.add_argument("--max", type=int, default=MAX_POSTS_PER_RUN, help="max posts per run")
    ap.add_argument("--fetch", type=int, default=100, help="how many recent sales to read")
    ap.add_argument("--seed", action="store_true",
                    help="mark all current sales as seen without posting (fresh start)")
    args = ap.parse_args()
    dry = args.dry_run or os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes")

    st = load_state(args.state)
    sales = fetch_sales(args.fetch)
    log(f"fetched {len(sales)} sales; newest blockTime "
        f"{sales[-1]['blockTime'] if sales else 'n/a'}; mode={'DRY RUN' if dry else 'LIVE'}")

    if args.seed or (not st["seen"] and not dry):
        # A brand-new/empty state would repost history; seed instead.
        for s in sales:
            mark_seen(st, s)
        save_state(args.state, st)
        log(f"seeded state with {len(sales)} sales; nothing posted")
        return 0

    seen = set(st["seen"])
    cutoff = st["last_blockTime"] - LOOKBACK_SECS
    new = [s for s in sales if s["signature"] not in seen
           and ((s.get("blockTime") or 0) >= cutoff or s["signature"] in st["attempts"])]

    if len(new) > args.max:
        skipped = new[:-args.max]
        log(f"warn: {len(new)} new sales; flood guard posts only the newest {args.max} "
            f"and skips {len(skipped)} older ones")
        if not dry:
            for s in skipped:
                mark_seen(st, s)
        new = new[-args.max:]

    if not new:
        log("no new sales")
        print("No new sales.")
        return 0

    sess = None if dry else x_session()
    failures = 0
    for i, sale in enumerate(new):
        sig = sale["signature"]
        when = datetime.fromtimestamp(sale.get("blockTime") or 0, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        try:
            number, image_url = token_info(sale["tokenMint"])
            image_url = image_url or sale.get("image")
            text = format_post(sale, number)
            img = None
            if image_url:
                try:
                    img = download_image(image_url, number, args.images_dir)
                except Exception as e:  # noqa: BLE001
                    log(f"warn: image for #{number} failed ({e}); posting without image")

            if dry:
                print(f"----- DRY RUN post ({when}, sig {sig[:12]}..., source={sale.get('source')}) -----")
                print(text)
                print(f"[image: {img[0] + f' ({len(img[1]):,} bytes, {img[2]})' if img else 'none'}]")
                print()
                continue

            media_id = x_upload_image(sess, img[1], img[2], os.path.basename(img[0])) if img else None
            try:
                post_id = x_create_post(sess, text, media_id)
                log(f"posted RSY #{number}: https://x.com/i/web/status/{post_id}")
            except XError as e:
                if not e.duplicate:
                    raise
                log(f"RSY #{number}: X says duplicate content, treating as already posted")
            mark_seen(st, sale)
            save_state(args.state, st)
            if i < len(new) - 1:
                time.sleep(SECONDS_BETWEEN_POSTS)
        except Exception as e:  # noqa: BLE001
            failures += 1
            n = st["attempts"].get(sig, 0) + 1
            if dry:
                log(f"error (dry run) for {sig[:12]}...: {e}")
                continue
            if n >= MAX_ATTEMPTS:
                log(f"ERROR giving up on {sig} after {n} attempts: {e}")
                mark_seen(st, sale)
            else:
                st["attempts"][sig] = n
                log(f"ERROR attempt {n}/{MAX_ATTEMPTS} for {sig}: {e} (will retry next run)")
            save_state(args.state, st)
            if isinstance(e, XError) and e.stop:
                log("stopping this run (auth, credits or rate-limit problem)")
                break

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
