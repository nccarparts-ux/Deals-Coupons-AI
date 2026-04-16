"""
agents/content_writer.py -- AI content + SEO writer.
For each deal where content_written=false, calls Claude/DeepSeek to generate
SEO copy, social posts, and email subject lines, then stores results.
"""
import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

import anthropic

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import supabase_insert, supabase_select, supabase_update, get_unprocessed, mark_done

log = logging.getLogger("content_writer")

GROUP_NAME  = os.environ.get("GROUP_NAME", "Coupons, Deals & Steals")
MODEL       = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
BASE_URL    = os.environ.get("ANTHROPIC_BASE_URL")
API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
TG_LINK     = os.environ.get("TELEGRAM_INVITE_LINK", "")

_client: anthropic.Anthropic | None = None


def _ai() -> anthropic.Anthropic:
    global _client
    if _client is None:
        kwargs = {"api_key": API_KEY}
        if BASE_URL:
            kwargs["base_url"] = BASE_URL
        _client = anthropic.Anthropic(**kwargs)
    return _client


# ── Learning context ──────────────────────────────────────────────────────────

def _learning_context() -> str:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    # Top 3 deals by CTR
    deals = supabase_select("deals")
    ranked = sorted(
        [d for d in deals if d.get("page_views", 0) > 0],
        key=lambda d: (d.get("click_throughs", 0) / d["page_views"]),
        reverse=True,
    )[:3]
    top_deals = [
        f"{d['title'][:50]} ({d['category']}, {d['discount_pct']}% off, "
        f"CTR={d['click_throughs']/d['page_views']:.1%})"
        for d in ranked
    ] or ["No data yet"]

    # Top email subject patterns from learning_log
    logs = supabase_select("learning_log", {"metric": "email_subject_pattern"})
    recent = sorted(logs, key=lambda r: r.get("recorded_at", ""), reverse=True)[:5]
    subjects = [r["context"].get("subject", "") for r in recent if r.get("context")] or ["No data yet"]

    # Best categories by avg CTR
    cat_stats: dict[str, list] = {}
    for d in deals:
        if d.get("page_views", 0) > 0:
            cat = d.get("category", "other")
            cat_stats.setdefault(cat, []).append(d["click_throughs"] / d["page_views"])
    best_cats = sorted(cat_stats, key=lambda c: sum(cat_stats[c]) / len(cat_stats[c]), reverse=True)[:3]

    return (
        f"Top CTR deals: {'; '.join(top_deals)}. "
        f"Best categories: {', '.join(best_cats) or 'n/a'}. "
        f"High-performing subject lines: {'; '.join(subjects)}."
    )


# ── AI call with retry ────────────────────────────────────────────────────────

def _generate(deal: dict, context: str) -> dict:
    price    = f"${deal['price']:.2f}" if deal.get("price") else "N/A"
    orig     = f"${deal['original_price']:.2f}" if deal.get("original_price") else "N/A"
    disc     = f"{deal['discount_pct']}%" if deal.get("discount_pct") else "N/A"

    system = (
        f"SEO-focused deal copywriter for {GROUP_NAME}. "
        "Tone: energetic, trustworthy, conversational. "
        "Max 1 exclamation mark per piece. "
        "Prioritize copy patterns that have historically driven clicks based on the performance data provided."
    )
    user = (
        f"Deal: {deal['title']} | {price} (was {orig}) | {disc} off | "
        f"{deal.get('category','other')} | {deal['amazon_url']}\n"
        f"Top performing historical patterns: {context}\n\n"
        "Return ONLY valid JSON (no markdown fences):\n"
        '{"seo_title":"","seo_h1":"","seo_keywords":[],"deal_description":"",'
        '"meta_description":"","faq_pairs":[{"q":"","a":""}],'
        '"facebook_post":"","instagram_caption":"",'
        '"email_subject_lines":[]}'
    )

    for attempt in range(3):
        try:
            resp = _ai().messages.create(
                model=MODEL,
                max_tokens=1200,
                messages=[{"role": "user", "content": user}],
                system=system,
            )
            raw = resp.content[0].text.strip()
            # Strip accidental fences
            if raw.startswith("```"):
                raw = re.sub(r"^```\w*\n?", "", raw)
                raw = raw.rstrip("`").strip()
            parsed = json.loads(raw)
            # Log token usage
            usage = getattr(resp, "usage", None)
            if usage:
                supabase_insert("learning_log", {
                    "metric": "content_writer_tokens",
                    "value": usage.input_tokens + usage.output_tokens,
                    "context": {"deal_id": deal["id"], "model": MODEL,
                                "input": usage.input_tokens, "output": usage.output_tokens},
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                })
            return parsed
        except (json.JSONDecodeError, Exception) as exc:
            wait = 2 ** attempt
            log.warning("Attempt %d failed for deal %s: %s — retrying in %ds",
                        attempt + 1, deal["id"], exc, wait)
            time.sleep(wait)

    raise RuntimeError(f"All retries failed for deal {deal['id']}")


# ── Store results ─────────────────────────────────────────────────────────────

def _store(deal: dict, content: dict, dry_run: bool) -> None:
    now = datetime.now(timezone.utc).isoformat()
    keywords_str = ", ".join(content.get("seo_keywords", []))

    # Inject Telegram CTA into Facebook post
    fb = content.get("facebook_post", "")
    if TG_LINK and TG_LINK not in fb:
        fb += f"\nJoin us for more deals: {TG_LINK}"

    platforms = {
        "facebook":  (fb, ""),
        "instagram": (content.get("instagram_caption", ""), ""),
        "email":     (
            "\n".join(content.get("email_subject_lines", [])),
            json.dumps(content.get("email_subject_lines", [])),
        ),
        "seo": (
            json.dumps({
                "seo_title":        content.get("seo_title"),
                "seo_h1":           content.get("seo_h1"),
                "meta_description": content.get("meta_description"),
                "deal_description": content.get("deal_description"),
                "faq_pairs":        content.get("faq_pairs"),
                "seo_keywords":     content.get("seo_keywords"),
            }),
            "",
        ),
    }

    if dry_run:
        log.info("[DRY RUN] Would store content for deal %s:\n%s",
                 deal["id"], json.dumps(content, indent=2)[:500])
        return

    for platform, (text, hashtags) in platforms.items():
        supabase_insert("content_queue", {
            "deal_id":      deal["id"],
            "platform":     platform,
            "content_text": text,
            "hashtags":     hashtags,
            "status":       "draft",
            "created_at":   now,
        })

    # Store keywords on the deal row
    supabase_update("deals", {"id": deal["id"]}, {"keywords": keywords_str})
    mark_done(deal["id"], "content_written")
    log.info("Content stored for deal %s (%s)", deal["id"], deal["title"][:50])


# ── Public entry point ────────────────────────────────────────────────────────

def process_pending(deal_id: str | None = None, dry_run: bool = False) -> int:
    if deal_id:
        rows = supabase_select("deals", {"id": deal_id})
    else:
        rows = get_unprocessed("content_written")

    if not rows:
        log.info("No deals pending content generation")
        return 0

    context = _learning_context()
    processed = 0

    for deal in rows:
        if not deal.get("amazon_url"):
            log.warning("Skipping deal %s — no amazon_url", deal["id"])
            continue
        try:
            content = _generate(deal, context)
            _store(deal, content, dry_run)
            processed += 1
        except Exception as exc:
            log.error("Failed to process deal %s: %s", deal["id"], exc)

    log.info("process_pending done: %d processed", processed)
    return processed


def main():
    parser = argparse.ArgumentParser(description="AI content writer")
    parser.add_argument("--deal-id", help="Process a single deal ID")
    parser.add_argument("--dry-run", action="store_true", help="Generate but do not save")
    args = parser.parse_args()

    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "content_writer.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    process_pending(deal_id=args.deal_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
