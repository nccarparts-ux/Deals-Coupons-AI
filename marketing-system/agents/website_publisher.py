"""
agents/website_publisher.py -- Static deal page publisher.

For each deal where website_published=false, renders a Jinja2 deal page,
rebuilds deals.json and sitemap.xml at the repo root (which Vercel serves),
pings Google, commits and pushes to GitHub so Vercel auto-deploys.
"""
import argparse
import json
import logging
import logging.handlers
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import supabase_select, supabase_insert, get_unprocessed, mark_done

# ── Paths ─────────────────────────────────────────────────────────────────────
MARKETING_DIR = Path(__file__).parent.parent
REPO_ROOT     = MARKETING_DIR.parent
TEMPLATES_DIR = MARKETING_DIR / "website" / "templates"
DEALS_DIR     = REPO_ROOT / "deals"          # /deals/{slug}/index.html
DEALS_JSON    = REPO_ROOT / "deals.json"     # served at /deals.json (first page only)
SITEMAP_PATH  = REPO_ROOT / "sitemap.xml"
PUBLIC_MIRROR = MARKETING_DIR / "website" / "public"

# Pagination config
PAGE_SIZE = 24   # deals per page (homepage only shows 8/section, so 24 is enough for it)
MAX_DEALS = 300  # total deals kept across all paginated files

# ── Config ────────────────────────────────────────────────────────────────────
GROUP_NAME      = os.environ.get("GROUP_NAME", "Coupons, Deals & Steals")
SITE_URL        = os.environ.get("SITE_URL", "https://deals-coupons-ai.vercel.app").rstrip("/")
TELEGRAM_INVITE = os.environ.get("TELEGRAM_INVITE_LINK", "https://t.me/Coupons_Deals_Steals")
FACEBOOK_GROUP  = os.environ.get("FACEBOOK_GROUP_LINK", "#")

LOG_PATH = MARKETING_DIR / "logs" / "website_publisher.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("website_publisher")
if not log.handlers:
    log.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    log.addHandler(fh)
    log.addHandler(ch)


# ── Template env ──────────────────────────────────────────────────────────────

def _jinja_env() -> Environment:
    if not TEMPLATES_DIR.exists():
        raise RuntimeError(f"Templates dir not found: {TEMPLATES_DIR}")
    return Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)


# ── SEO content loader ────────────────────────────────────────────────────────

def _load_seo(deal_id: str) -> dict:
    rows = supabase_select("content_queue", {"deal_id": deal_id, "platform": "seo"})
    if not rows:
        return {}
    try:
        return json.loads(rows[0]["content_text"])
    except (json.JSONDecodeError, KeyError):
        return {}


# ── Render one deal page ──────────────────────────────────────────────────────

def _render_deal(env: Environment, deal: dict, seo: dict) -> str:
    price    = deal.get("price")
    orig     = deal.get("original_price")
    disc     = deal.get("discount_pct")

    faq_raw = seo.get("faq_pairs", [])
    if faq_raw and isinstance(faq_raw[0], dict):
        faq_pairs = [(p.get("q", ""), p.get("a", "")) for p in faq_raw]
    else:
        faq_pairs = [(p[0], p[1]) for p in faq_raw if len(p) >= 2]

    tmpl = env.get_template("deal.html")
    return tmpl.render(
        seo_title       = seo.get("seo_title") or deal["title"][:60],
        seo_h1          = seo.get("seo_h1") or deal["title"],
        meta_description= seo.get("meta_description", ""),
        deal_description= seo.get("deal_description", ""),
        faq_pairs       = faq_pairs,
        seo_keywords    = seo.get("seo_keywords", []),
        title           = deal.get("title", ""),
        price           = price,
        original_price  = orig,
        discount_pct    = disc,
        amazon_url      = deal.get("amazon_url", "#"),
        image_url       = deal.get("image_url", ""),
        category        = deal.get("category", "other"),
        slug            = deal.get("slug", ""),
        fetched_at      = deal.get("fetched_at", ""),
        group_name      = GROUP_NAME,
        site_url        = SITE_URL,
        telegram_invite = TELEGRAM_INVITE,
        facebook_group  = FACEBOOK_GROUP,
    )


# ── Write deal page ───────────────────────────────────────────────────────────

def _write_page(slug: str, html: str) -> Path:
    page_dir = DEALS_DIR / slug
    page_dir.mkdir(parents=True, exist_ok=True)
    page_path = page_dir / "index.html"
    page_path.write_text(html, encoding="utf-8")
    return page_path


# ── Rebuild deals.json ────────────────────────────────────────────────────────

def _rebuild_deals_json() -> None:
    fields = ["id", "title", "price", "original_price", "discount_pct",
              "amazon_url", "image_url", "category", "slug", "fetched_at"]
    all_deals_raw = sorted(
        supabase_select("deals"),
        key=lambda d: d.get("fetched_at") or "",
        reverse=True,
    )
    all_rows = [{f: d.get(f) for f in fields} for d in all_deals_raw[:MAX_DEALS]]

    # deals.json = first PAGE_SIZE deals only — keeps homepage payload tiny
    page_one = all_rows[:PAGE_SIZE]
    payload = json.dumps(page_one, default=str, ensure_ascii=False)
    DEALS_JSON.write_text(payload, encoding="utf-8")
    # Mirror into marketing-system/website/public/
    PUBLIC_MIRROR.mkdir(parents=True, exist_ok=True)
    (PUBLIC_MIRROR / "deals.json").write_text(payload, encoding="utf-8")
    log.info("deals.json rebuilt (%d deals, %d total available)", len(page_one), len(all_rows))

    # Paginated JSON files for top-deals page
    _rebuild_paginated_json(all_rows)


def _rebuild_paginated_json(all_rows: list) -> None:
    """Write deals/page-N.json and deals/pages.json for the top-deals pagination UI."""
    total = len(all_rows)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    for page_num in range(1, total_pages + 1):
        start = (page_num - 1) * PAGE_SIZE
        chunk = all_rows[start:start + PAGE_SIZE]
        out = DEALS_DIR / f"page-{page_num}.json"
        out.write_text(json.dumps(chunk, default=str, ensure_ascii=False), encoding="utf-8")

    meta = {"total_deals": total, "per_page": PAGE_SIZE, "total_pages": total_pages}
    (DEALS_DIR / "pages.json").write_text(json.dumps(meta), encoding="utf-8")
    log.info("Paginated JSON: %d deals across %d pages (%d per page)", total, total_pages, PAGE_SIZE)


# ── Rebuild sitemap.xml ───────────────────────────────────────────────────────

def _rebuild_sitemap() -> None:
    all_deals = supabase_select("deals")
    published = [d for d in all_deals if d.get("website_published") and d.get("slug")]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    static_urls = [
        (SITE_URL + "/",          "daily",   "1.0"),
        (SITE_URL + "/top-deals", "daily",   "0.9"),
        (SITE_URL + "/about",     "monthly", "0.5"),
        (SITE_URL + "/download",  "weekly",  "0.6"),
    ]

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url, freq, pri in static_urls:
        lines.append(
            f"  <url><loc>{url}</loc>"
            f"<changefreq>{freq}</changefreq>"
            f"<priority>{pri}</priority></url>"
        )
    for d in published:
        lines.append(
            f"  <url>"
            f"<loc>{SITE_URL}/deals/{d['slug']}</loc>"
            f"<lastmod>{today}</lastmod>"
            f"<changefreq>weekly</changefreq>"
            f"<priority>0.7</priority>"
            f"</url>"
        )
    lines.append("</urlset>")
    SITEMAP_PATH.write_text("\n".join(lines), encoding="utf-8")
    log.info("sitemap.xml rebuilt (%d deal URLs)", len(published))


# ── Ping Google ───────────────────────────────────────────────────────────────

def _ping_google() -> None:
    try:
        r = requests.get(
            f"https://www.google.com/ping?sitemap={SITE_URL}/sitemap.xml",
            timeout=5,
        )
        log.info("Google ping: HTTP %d", r.status_code)
    except Exception as exc:
        log.warning("Google ping failed (non-fatal): %s", exc)


# ── Git + Vercel deploy ───────────────────────────────────────────────────────

def _git_push(slugs: list) -> None:
    def run(*args):
        result = subprocess.run(
            list(args), cwd=str(REPO_ROOT),
            capture_output=True, text=True, encoding="utf-8",
        )
        if result.returncode != 0:
            log.warning("git %s stderr: %s", args[1] if len(args) > 1 else "", result.stderr[:300])
        return result

    # Stage changed files
    run("git", "add", "deals/", "deals.json", "sitemap.xml")

    msg = "feat: publish deal pages [" + ", ".join(slugs[:5]) + (", ..." if len(slugs) > 5 else "") + "]"
    result = run("git", "commit", "-m", msg)
    if result.returncode != 0:
        if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
            log.info("git commit: nothing new to commit")
            return
        log.warning("git commit failed: %s", result.stderr[:200])
        return

    push = run("git", "push", "origin", "master")
    if push.returncode == 0:
        log.info("git push OK -- Vercel will auto-deploy from GitHub")
    else:
        log.warning("git push failed: %s", push.stderr[:200])


def _vercel_deploy() -> None:
    try:
        result = subprocess.run(
            ["vercel", "--prod", "--yes"],
            cwd=str(REPO_ROOT),
            capture_output=True, text=True, encoding="utf-8",
            timeout=120,
        )
        if result.returncode == 0:
            log.info("vercel --prod deploy triggered")
        else:
            log.warning("vercel deploy returned %d: %s", result.returncode, result.stderr[:200])
    except FileNotFoundError:
        log.info("vercel CLI not found -- relying on GitHub auto-deploy")
    except Exception as exc:
        log.warning("vercel deploy error (non-fatal): %s", exc)


# ── Public entry point ────────────────────────────────────────────────────────

def publish_pending(rebuild_all: bool = False, dry_run: bool = False) -> int:
    # Validate template dir exists
    if not TEMPLATES_DIR.exists():
        log.error("Templates dir missing: %s -- skipping publish", TEMPLATES_DIR)
        return 0

    try:
        env = _jinja_env()
    except Exception as exc:
        log.error("Jinja2 init failed: %s", exc)
        return 0

    if rebuild_all:
        deals = supabase_select("deals")
    else:
        deals = get_unprocessed("website_published")

    # Only process deals that also have content (seo row in content_queue)
    pending = [d for d in deals if d.get("amazon_url") and d.get("slug")]
    if not pending:
        log.info("No deals pending website publish")
        return 0

    log.info("Publishing %d deal pages (dry_run=%s)", len(pending), dry_run)
    published_slugs = []

    for deal in pending:
        slug = deal["slug"]
        seo = _load_seo(deal["id"])
        if not seo:
            log.warning("No SEO content for deal %s (%s) -- skipping", deal["id"], slug)
            continue

        try:
            html = _render_deal(env, deal, seo)
        except Exception as exc:
            log.error("Render failed for %s: %s", slug, exc)
            continue

        if not dry_run:
            try:
                _write_page(slug, html)
                published_slugs.append(slug)
                log.info("Written: deals/%s/index.html", slug)
            except Exception as exc:
                log.error("Write failed for %s: %s", slug, exc)
                continue
        else:
            log.info("[DRY RUN] Would write deals/%s/index.html", slug)
            published_slugs.append(slug)

    if not published_slugs:
        log.info("No pages written")
        return 0

    if not dry_run:
        # Mark done first so sitemap rebuild includes these slugs
        for deal in pending:
            if deal["slug"] in published_slugs:
                mark_done(deal["id"], "website_published")

        _rebuild_deals_json()
        _rebuild_sitemap()
        _ping_google()
        _git_push(published_slugs)
        _vercel_deploy()

        supabase_insert("learning_log", {
            "metric": "agent_run_website",
            "value": len(published_slugs),
            "context": {"slugs": published_slugs[:20], "dry_run": False},
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
    else:
        log.info("[DRY RUN] Skipping git push, Vercel deploy, and DB updates")

    log.info("publish_pending done: %d pages published", len(published_slugs))
    return len(published_slugs)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Website publisher agent")
    parser.add_argument("--rebuild-all", action="store_true",
                        help="Reprocess all deals, not just unpublished ones")
    parser.add_argument("--dry-run", action="store_true",
                        help="Render pages but do not write files or push to git")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.handlers.RotatingFileHandler(
                LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            ),
            logging.StreamHandler(sys.stdout),
        ],
    )

    count = publish_pending(rebuild_all=args.rebuild_all, dry_run=args.dry_run)
    log.info("Done: %d pages", count)


if __name__ == "__main__":
    main()
