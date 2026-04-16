"""
agents/telegram_reader.py -- Pipeline bridge: syncs deal_candidates+products -> deals.

Reads posted deal_candidates (joined with products) from the main pipeline's Supabase
tables and inserts them into the marketing `deals` table.

Note: originally designed as a Telegram getUpdates reader, but Telegram bots cannot
receive messages sent by other bots. Since the main pipeline already writes every deal
to deal_candidates + products, we read directly from there instead.
"""
import argparse
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

import requests
import os

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import supabase_insert, supabase_select, supabase_update

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

log = logging.getLogger("telegram_reader")

CATEGORIES = {
    "electronics": ["phone","laptop","tablet","tv","camera","headphone","speaker","monitor","keyboard","mouse","printer","router","drone","gaming","console"],
    "kitchen":     ["kitchen","cookware","blender","coffee","air fryer","instant pot","knife","pan","pot","toaster","microwave"],
    "clothing":    ["shirt","pants","dress","jacket","shoes","sneaker","boot","sock","underwear","hoodie","coat","apparel","clothing"],
    "toys":        ["toy","lego","puzzle","game","doll","action figure","board game","kids","children","baby"],
    "home":        ["furniture","pillow","sheet","blanket","lamp","rug","curtain","storage","organizer","vacuum","mop","mattress","home"],
    "beauty":      ["skincare","makeup","shampoo","conditioner","perfume","lotion","serum","beauty","hair","nail","moisturizer"],
    "sports":      ["gym","fitness","yoga","running","bicycle","bike","tent","camping","hiking","sport","exercise","protein","dumbbell"],
    "books":       ["book","novel","guide","workbook","textbook","kindle"],
}


def _slugify(text: str, max_len: int = 60) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:max_len]


def _classify(text: str) -> str:
    lower = text.lower()
    for cat, kws in CATEGORIES.items():
        if any(k in lower for k in kws):
            return cat
    return "other"


def _fetch_posted_candidates(since_hours: int | None = None) -> list[dict]:
    """Read posted deal_candidates joined with products from main pipeline."""
    url = (
        f"{SUPABASE_URL}/rest/v1/deal_candidates"
        "?select=*,products(*)"
        "&status=eq.posted"
        "&order=detected_at.desc"
        "&limit=100"
    )
    if since_hours:
        import time
        since_iso = datetime.fromtimestamp(
            time.time() - since_hours * 3600, tz=timezone.utc
        ).isoformat()
        url += f"&detected_at=gte.{since_iso}"

    r = requests.get(url, headers=_HEADERS, timeout=15)
    if r.status_code != 200:
        log.error("deal_candidates fetch failed: HTTP %d %s", r.status_code, r.text[:200])
        return []
    return r.json()


def _existing_deal_ids() -> set:
    rows = supabase_select("deals")
    return {r["id"] for r in rows if r.get("id")}


def _build_deal_row(candidate: dict) -> dict | None:
    product = candidate.get("products") or {}
    if not product:
        return None

    title = product.get("title", "").strip()
    if not title:
        return None

    amazon_url = product.get("retailer_url", "")
    if not amazon_url:
        return None

    # Ensure affiliate tag
    if "tag=" not in amazon_url:
        sep = "&" if "?" in amazon_url else "?"
        amazon_url = f"{amazon_url}{sep}tag=bidyarddeal09-20"

    price = candidate.get("current_price")
    original_price = (
        candidate.get("original_price")
        or product.get("original_price")
    )
    disc = candidate.get("price_drop_percent")
    if disc is not None:
        disc = int(round(float(disc)))

    category = (
        product.get("category")
        or _classify(title)
    )
    if category:
        category = category.lower().split()[0] if category else "other"

    return {
        "id":               str(candidate["id"]),
        "title":            title[:255],
        "price":            float(price) if price is not None else None,
        "original_price":   float(original_price) if original_price is not None else None,
        "discount_pct":     disc,
        "amazon_url":       amazon_url,
        "image_url":        product.get("image_url", ""),
        "category":         category or "other",
        "description":      product.get("description", ""),
        "slug":             _slugify(title),
        "fetched_at":       candidate.get("detected_at") or datetime.now(timezone.utc).isoformat(),
        "content_written":  False,
        "email_sent":       False,
        "website_published": False,
        "social_queued":    False,
    }


def fetch_new_deals(since_hours: int | None = None, dry_run: bool = False) -> int:
    candidates = _fetch_posted_candidates(since_hours=since_hours)
    if not candidates:
        log.info("No posted deal_candidates found")
        return 0

    existing = _existing_deal_ids()
    inserted = 0

    for cand in candidates:
        row = _build_deal_row(cand)
        if not row:
            continue
        if row["id"] in existing:
            log.debug("Already in deals: %s", row["id"])
            continue

        log.info(
            "New deal: %s (%.0f%% off $%.2f)",
            row["title"][:60],
            row["discount_pct"] or 0,
            row["price"] or 0,
        )

        if not dry_run:
            try:
                supabase_insert("deals", row)
                existing.add(row["id"])
                inserted += 1
            except Exception as exc:
                log.error("Insert failed for %s: %s", row["id"], exc)
        else:
            inserted += 1

    log.info("fetch_new_deals done: %d %s", inserted, "would insert" if dry_run else "inserted")
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Pipeline bridge: deal_candidates -> deals")
    parser.add_argument("--test", action="store_true", help="Dry run -- parse but do not insert")
    parser.add_argument("--since-hours", type=int, metavar="N",
                        help="Only sync candidates detected in last N hours")
    args = parser.parse_args()

    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "telegram_reader.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    if args.test:
        log.info("DRY RUN mode")
        fetch_new_deals(since_hours=args.since_hours, dry_run=True)
        return

    fetch_new_deals(since_hours=args.since_hours)

    from apscheduler.schedulers.blocking import BlockingScheduler
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(fetch_new_deals, "interval", minutes=15, id="pipeline_bridge")
    log.info("Scheduler started (every 15 min). Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Stopped.")


if __name__ == "__main__":
    main()
