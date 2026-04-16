"""
agents/learning_engine.py -- daily learning + SEO auto-improvement engine.
Run daily at 6am via run_all.py scheduler.
"""
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import supabase_insert, supabase_select, supabase_update

log = logging.getLogger("learning_engine")

MODEL    = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL")
API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
SITE_URL = os.environ.get("SITE_URL", "")
GSC_KEY  = os.environ.get("GOOGLE_SEARCH_CONSOLE_KEY", "")

WEBSITE_DIR = Path(__file__).parent.parent / "website"


def _ai_client():
    import anthropic
    kwargs = {"api_key": API_KEY}
    if BASE_URL:
        kwargs["base_url"] = BASE_URL
    return anthropic.Anthropic(**kwargs)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


# ── 1. Deal performance analysis ─────────────────────────────────────────────

def _analyze_deals():
    deals = supabase_select("deals")
    scored = [d for d in deals if d.get("page_views", 0) > 0]
    if not scored:
        log.info("No deals with page_views yet")
        return

    for d in scored:
        d["_ctr"] = d.get("click_throughs", 0) / d["page_views"]

    top = sorted(scored, key=lambda d: d["_ctr"], reverse=True)[:10]

    # Bucket discount ranges
    buckets = {"<30": [], "30-50": [], "50+": []}
    for d in scored:
        pct = d.get("discount_pct") or 0
        key = "<30" if pct < 30 else ("30-50" if pct <= 50 else "50+")
        buckets[key].append(d["_ctr"])

    avg_by_bucket = {k: (sum(v) / len(v) if v else 0) for k, v in buckets.items()}

    # Category breakdown
    cat_ctrs: dict[str, list] = {}
    for d in scored:
        cat_ctrs.setdefault(d.get("category", "other"), []).append(d["_ctr"])
    cat_avg = {c: sum(v) / len(v) for c, v in cat_ctrs.items()}
    best_cats = sorted(cat_avg, key=cat_avg.get, reverse=True)[:5]

    context = {
        "top_deals": [{"title": d["title"][:60], "category": d.get("category"),
                       "discount_pct": d.get("discount_pct"), "ctr": round(d["_ctr"], 4)}
                      for d in top],
        "discount_bucket_ctr": avg_by_bucket,
        "best_categories": best_cats,
    }
    avg_ctr = sum(d["_ctr"] for d in top) / len(top) if top else 0
    supabase_insert("learning_log", {
        "metric": "deal_ctr_patterns",
        "value": round(avg_ctr, 6),
        "context": context,
        "recorded_at": _now_iso(),
    })
    log.info("Deal CTR patterns logged (%d deals, top avg CTR=%.2f%%)", len(scored), avg_ctr * 100)


# ── 2. Email performance ──────────────────────────────────────────────────────

def _analyze_email():
    logs = supabase_select("email_log")
    if not logs:
        return

    by_template: dict[str, list] = {}
    for row in logs:
        tmpl = row.get("template_name", "unknown")
        by_template.setdefault(tmpl, []).append(row.get("subject", ""))

    # Best subjects by frequency of first 3 words
    word_freq: dict[str, int] = {}
    for subjects in by_template.values():
        for s in subjects:
            key = " ".join(s.split()[:3])
            if key:
                word_freq[key] = word_freq.get(key, 0) + 1

    top_patterns = sorted(word_freq, key=word_freq.get, reverse=True)[:10]
    for pattern in top_patterns:
        supabase_insert("learning_log", {
            "metric": "email_subject_pattern",
            "value": word_freq[pattern],
            "context": {"subject": pattern},
            "recorded_at": _now_iso(),
        })
    log.info("Email subject patterns logged (%d patterns)", len(top_patterns))


# ── 3. SEO performance ingestion ──────────────────────────────────────────────

def _ingest_seo():
    if not GSC_KEY or not SITE_URL:
        return
    try:
        from google.oauth2 import service_account
        import googleapiclient.discovery as gad
    except ImportError:
        log.warning("google-auth not installed — skipping Search Console ingestion")
        return

    try:
        creds = service_account.Credentials.from_service_account_file(
            GSC_KEY, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
        )
        svc = gad.build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=28)
        body = {
            "startDate": str(start), "endDate": str(end),
            "dimensions": ["query", "page"], "rowLimit": 500,
        }
        resp = svc.searchanalytics().query(siteUrl=SITE_URL, body=body).execute()
        rows = resp.get("rows", [])
        for row in rows:
            keys = row.get("keys", ["", ""])
            keyword, page = keys[0], keys[1]
            slug = page.rstrip("/").split("/")[-1]
            supabase_insert("seo_performance", {
                "deal_slug": slug,
                "keyword": keyword,
                "impressions": int(row.get("impressions", 0)),
                "clicks": int(row.get("clicks", 0)),
                "avg_position": round(row.get("position", 0), 2),
                "recorded_at": _now_iso(),
            })
        log.info("SEO: ingested %d rows from Search Console", len(rows))
    except Exception as exc:
        log.error("SEO ingestion failed: %s", exc)


# ── 4. SEO auto-improvement ───────────────────────────────────────────────────

def _auto_improve_seo(dry_run: bool):
    if not GSC_KEY:
        return
    rows = supabase_select("seo_performance")
    opportunities = [r for r in rows if r.get("avg_position") and 8 <= r["avg_position"] <= 20]
    if not opportunities:
        return

    client = _ai_client()
    improved = 0

    for row in opportunities[:10]:  # cap at 10/run
        slug = row["deal_slug"]
        page_path = WEBSITE_DIR / "deals" / slug / "index.html"
        if not page_path.exists():
            continue
        html = page_path.read_text(encoding="utf-8")

        title_m = re.search(r"<title>(.*?)</title>", html)
        meta_m  = re.search(r'<meta name="description" content="(.*?)"', html)
        cur_title = title_m.group(1) if title_m else slug
        cur_meta  = meta_m.group(1) if meta_m else ""

        prompt = (
            f"Page ranks {row['avg_position']:.1f} for '{row['keyword']}'.\n"
            f"Title: '{cur_title}'\nMeta: '{cur_meta}'\n"
            "Return ONLY JSON: {\"new_title\": \"\", \"new_meta\": \"\", \"reasoning\": \"\"}"
        )
        try:
            resp = client.messages.create(
                model=MODEL, max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
                system="SEO expert. Respond only with JSON.",
            )
            raw = resp.content[0].text.strip().strip("`").strip()
            data = json.loads(raw)
            if not dry_run:
                new_html = re.sub(r"<title>.*?</title>",
                                  f"<title>{data['new_title']}</title>", html)
                new_html = re.sub(r'(<meta name="description" content=")[^"]*(")',
                                  rf'\g<1>{data["new_meta"]}\2', new_html)
                page_path.write_text(new_html, encoding="utf-8")
            supabase_insert("learning_log", {
                "metric": "seo_improvement",
                "value": row["avg_position"],
                "context": {"slug": slug, "keyword": row["keyword"],
                            "old_pos": row["avg_position"],
                            "new_title": data.get("new_title"),
                            "reasoning": data.get("reasoning", "")[:200]},
                "recorded_at": _now_iso(),
            })
            improved += 1
        except Exception as exc:
            log.warning("SEO improvement failed for %s: %s", slug, exc)

    log.info("SEO auto-improvement: %d pages updated", improved)


# ── 5. Internal linking (weekly, Monday) ─────────────────────────────────────

def _update_internal_links(dry_run: bool):
    if datetime.now(timezone.utc).weekday() != 0:
        return

    deals = supabase_select("deals")
    by_cat: dict[str, list] = {}
    for d in deals:
        by_cat.setdefault(d.get("category", "other"), []).append(d)

    updated = 0
    for cat, cat_deals in by_cat.items():
        top5 = sorted(cat_deals, key=lambda d: d.get("page_views", 0), reverse=True)[:5]
        if len(top5) < 2:
            continue
        links_html = "".join(
            f'<a href="/deals/{d["slug"]}/">{d["title"][:50]}</a> '
            for d in top5
        )
        for deal in top5:
            page = WEBSITE_DIR / "deals" / deal["slug"] / "index.html"
            if not page.exists():
                continue
            html = page.read_text(encoding="utf-8")
            marker = "<!-- internal-links -->"
            block = (f'\n{marker}\n<section class="related-links">'
                     f'<h3>More {cat.title()} Deals</h3>{links_html}</section>\n')
            if marker in html:
                html = re.sub(rf"{marker}.*?</section>", block.strip(), html, flags=re.DOTALL)
            else:
                html = html.replace("</body>", block + "</body>")
            if not dry_run:
                page.write_text(html, encoding="utf-8")
            updated += 1

    log.info("Internal links updated: %d pages", updated)


# ── Public entry ──────────────────────────────────────────────────────────────

def run(dry_run: bool = False):
    supabase_insert("learning_log", {
        "metric": "agent_run_learning",
        "value": 1,
        "context": {"dry_run": dry_run},
        "recorded_at": _now_iso(),
    })
    _analyze_deals()
    _analyze_email()
    _ingest_seo()
    _auto_improve_seo(dry_run)
    _update_internal_links(dry_run)
    log.info("Learning engine run complete")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "learning_engine.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    run(dry_run=args.dry_run)
