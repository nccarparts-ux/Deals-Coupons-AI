"""
Blog Writer for Deal Sniper AI Platform.

Generates SEO-optimised blog posts from top deals OR evergreen buying guides,
saves them as HTML, rebuilds the index, updates sitemap.xml, pings Google,
and automatically commits + pushes to GitHub (triggering Vercel deploy).

Runs every 3 hours via Celery beat → 8 unique articles per day.
All 20 SEO categories rotate so every category gets fresh content every 2-3 days.

Required .env variables:
  ANTHROPIC_AUTH_TOKEN   — DeepSeek / Anthropic API key
  ANTHROPIC_MODEL        — e.g. deepseek-chat
  ANTHROPIC_BASE_URL     — https://api.deepseek.com/anthropic
  BLOG_BASE_URL          — https://deals-coupons-ai.vercel.app  (no trailing slash)
  BLOG_GIT_BRANCH        — master  (default)
  BLOG_OUTPUT_DIR        — optional override for blog output path
"""

import asyncio
import logging
import os
import re
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

from ..database.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_BLOG_DIR = Path(os.environ.get("BLOG_OUTPUT_DIR", str(_REPO_ROOT / "blog")))

# 20 rotating categories — each gets a dedicated post every ~2-3 days at 8/day
SEO_CATEGORIES = [
    "Electronics",
    "Laptops & Computers",
    "Gaming",
    "Headphones & Earbuds",
    "Smart Home",
    "TVs & Monitors",
    "Smartphones",
    "Kitchen Appliances",
    "Home Appliances",
    "Beauty & Skincare",
    "Fitness & Sports",
    "Clothing & Fashion",
    "Shoes & Footwear",
    "Toys & Kids",
    "Baby & Toddler",
    "Outdoor & Garden",
    "Office Supplies",
    "Tools & Home Improvement",
    "Pet Supplies",
    "Books & Entertainment",
]

CURRENT_YEAR = datetime.now().year


# ---------------------------------------------------------------------------
# Git auto-publish
# ---------------------------------------------------------------------------

def _git_commit_and_push(commit_message: str) -> bool:
    """
    Stage blog/, commit, and push to origin.
    Returns True on success (or when there's nothing new to commit).
    """
    repo_root = str(_REPO_ROOT)
    branch = os.environ.get("BLOG_GIT_BRANCH", "master")
    try:
        subprocess.run(
            ["git", "add", "blog/"],
            cwd=repo_root, check=True, capture_output=True, text=True,
        )
        r = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=repo_root, capture_output=True, text=True,
        )
        if r.returncode != 0:
            out = (r.stdout + r.stderr).lower()
            if "nothing to commit" in out or "nothing added" in out:
                logger.info("Git: nothing new to commit for blog")
                return True
            logger.error(f"Git commit failed: {r.stderr.strip()}")
            return False
        r2 = subprocess.run(
            ["git", "push", "origin", branch],
            cwd=repo_root, capture_output=True, text=True, timeout=90,
        )
        if r2.returncode != 0:
            logger.error(f"Git push failed: {r2.stderr.strip()}")
            return False
        logger.info(f"Git: blog pushed → Vercel deploy triggered ({commit_message})")
        return True
    except Exception as exc:
        logger.error(f"Git commit/push error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Category rotation
# ---------------------------------------------------------------------------

def _get_next_category() -> str:
    """
    Return the first SEO category that has NOT yet been written today.
    Falls back to a time-based rotation if all have been written.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    written_slugs = {f.stem for f in _BLOG_DIR.glob(f"{today}-*.html")}

    for cat in SEO_CATEGORIES:
        slug = _make_slug(cat)
        if slug not in written_slugs:
            return cat

    # All written today — rotate by hour so each batch still picks a different one
    idx = (datetime.now().hour // 3) % len(SEO_CATEGORIES)
    return SEO_CATEGORIES[idx]


def _make_slug(category: str, date: str = None) -> str:
    today = date or datetime.now().strftime("%Y-%m-%d")
    cat_slug = re.sub(r"[^a-z0-9]+", "-", category.lower()).strip("-")
    return f"{today}-best-{cat_slug}-deals"


# ---------------------------------------------------------------------------
# Data retrieval
# ---------------------------------------------------------------------------

async def get_top_deals_this_week(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Return top deals from the past 7 days ordered by click count.
    """
    client = get_supabase_client()
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    response = (
        client.table("posted_deals")
        .select("id, deal_candidate_id, clicks, blog_post_slug, posted_at, platform_copy")
        .order("clicks", desc=True)
        .limit(limit)
        .execute()
    )
    posted_rows = response.data if hasattr(response, "data") else []

    deals = []
    for row in posted_rows:
        posted_at_str = row.get("posted_at") or ""
        if posted_at_str:
            try:
                posted_at = datetime.fromisoformat(posted_at_str.replace("Z", "+00:00"))
                if posted_at.tzinfo is None:
                    posted_at = posted_at.replace(tzinfo=timezone.utc)
                if posted_at < datetime.now(timezone.utc) - timedelta(days=7):
                    continue
            except ValueError:
                pass

        candidate_id = row.get("deal_candidate_id")
        if not candidate_id:
            continue

        dc_resp = (
            client.table("deal_candidates")
            .select("id, product_id, current_price, original_price, price_drop_percent, affiliate_url")
            .eq("id", candidate_id).limit(1).execute()
        )
        dc_rows = dc_resp.data if hasattr(dc_resp, "data") else []
        if not dc_rows:
            continue
        dc = dc_rows[0]

        product_id = dc.get("product_id")
        if not product_id:
            continue

        prod_resp = (
            client.table("products")
            .select("id, title, category, image_url")
            .eq("id", product_id).limit(1).execute()
        )
        prod_rows = prod_resp.data if hasattr(prod_resp, "data") else []
        if not prod_rows:
            continue
        prod = prod_rows[0]

        affiliate_url = dc.get("affiliate_url") or ""
        aff_resp = (
            client.table("affiliate_links")
            .select("affiliate_url")
            .eq("deal_candidate_id", candidate_id).limit(1).execute()
        )
        aff_rows = aff_resp.data if hasattr(aff_resp, "data") else []
        if aff_rows:
            affiliate_url = aff_rows[0].get("affiliate_url") or affiliate_url

        current_price = dc.get("current_price")
        original_price = dc.get("original_price")
        discount_pct = dc.get("price_drop_percent")

        deals.append({
            "deal_id": str(row.get("id", "")),
            "title": prod.get("title") or "Untitled Deal",
            "category": prod.get("category") or "General",
            "current_price": float(current_price) if current_price is not None else None,
            "original_price": float(original_price) if original_price is not None else None,
            "discount_pct": float(discount_pct) if discount_pct is not None else None,
            "affiliate_url": affiliate_url,
            "clicks": int(row.get("clicks") or 0),
            "image_url": prod.get("image_url") or "",
        })

    logger.info(f"Retrieved {len(deals)} top deals from the past 7 days")
    return deals


# ---------------------------------------------------------------------------
# Blog post generation — deal roundup
# ---------------------------------------------------------------------------

async def generate_blog_post(
    deals: List[Dict[str, Any]], category: str = None
) -> Dict[str, str]:
    """
    Generate an SEO-optimised deal-roundup article via LLM.

    Returns: {html, meta_description, title, slug}
    """
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    model = os.environ.get("ANTHROPIC_MODEL", "deepseek-chat")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic").rstrip("/")

    effective_category = category or "Shopping"
    today_str = datetime.now().strftime("%Y-%m-%d")
    year = CURRENT_YEAR

    deal_lines = []
    for i, d in enumerate(deals, 1):
        price_info = ""
        if d.get("current_price") is not None and d.get("original_price") is not None:
            price_info = f"${d['current_price']:.2f} (was ${d['original_price']:.2f})"
        elif d.get("current_price") is not None:
            price_info = f"${d['current_price']:.2f}"
        discount_info = f"{d['discount_pct']:.0f}% off" if d.get("discount_pct") else ""
        deal_lines.append(
            f"{i}. {d['title']}\n"
            f"   Price: {price_info} {discount_info}\n"
            f"   URL: {d.get('affiliate_url','#')}\n"
            f"   Image: {d.get('image_url','')}"
        )
    deals_text = "\n".join(deal_lines)

    primary_kw = f"best {effective_category.lower()} deals"

    prompt = f"""You are an expert SEO content writer for a deals website. Write a high-quality, SEO-optimised blog post.

Primary keyword: "{primary_kw}"
Target date: {today_str}
Category: {effective_category}

Deals to feature:
{deals_text}

STRICT FORMAT REQUIREMENTS:
1. First line must be: <!-- META: [150-160 char meta description containing "{primary_kw}"] -->
2. Use this exact HTML structure:

<article itemscope itemtype="https://schema.org/Article">
<h1 itemprop="headline">[Title containing "{primary_kw}" and year {year}]</h1>
<p class="post-intro">[2-3 sentence intro. Use "{primary_kw}" naturally in the first sentence. Preview the savings readers will find.]</p>

<h2>Best {effective_category} Deals Right Now ({year})</h2>
[For each deal, use this structure:]
<section class="deal-item">
  <h3>[Product Name] — [X]% Off</h3>
  <img src="[IMAGE_URL]" alt="[descriptive alt text with keywords]" loading="lazy" width="400" height="300">
  <p><strong>Price: <span class="deal-price">$[PRICE]</span></strong> <s>$[ORIGINAL]</s> — [X]% savings</p>
  <p>[2-3 sentences: what it is, who it's for, why this price is exceptional. Be specific and helpful.]</p>
  <p><a href="[AFFILIATE_URL]" rel="nofollow sponsored" target="_blank" class="cta-btn">Check Price on Amazon</a></p>
</section>

<h2>How We Find the Best {effective_category} Deals</h2>
<p>[Paragraph explaining deal-finding methodology — builds trust and topical authority]</p>

<h2>Tips to Save More on {effective_category}</h2>
<ul>
<li>[Tip 1 — price history tracking]</li>
<li>[Tip 2 — best days/times to buy]</li>
<li>[Tip 3 — coupon stacking]</li>
<li>[Tip 4 — price alert setup]</li>
</ul>

<h2>Frequently Asked Questions About {effective_category} Deals</h2>
<div itemscope itemtype="https://schema.org/FAQPage">
<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
  <h3 itemprop="name">When is the best time to buy {effective_category.lower()}?</h3>
  <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
    <p itemprop="text">[Detailed answer — mention Black Friday, Prime Day, seasonal patterns]</p>
  </div>
</div>
<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
  <h3 itemprop="name">Are these {effective_category.lower()} prices really the lowest?</h3>
  <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
    <p itemprop="text">[Explain price history tracking methodology]</p>
  </div>
</div>
<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
  <h3 itemprop="name">How do I get notified about {effective_category.lower()} deals?</h3>
  <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
    <p itemprop="text">[Mention Telegram channel, bookmarking this page]</p>
  </div>
</div>
</div>

<h2>Conclusion</h2>
<p>[2-3 sentence wrap-up. Include "{primary_kw}" naturally. End with CTA to bookmark/subscribe.]</p>
</article>

ADDITIONAL REQUIREMENTS:
- Total word count: 1000-1400 words
- Use "{primary_kw}" 3-5 times total (naturally, not stuffed)
- Output ONLY the HTML content above — no <html>/<head>/<body> tags
- Make every sentence genuinely useful to a real shopper"""

    html_content = ""
    async with httpx.AsyncClient(timeout=120.0) as http_client:
        try:
            resp = await http_client.post(
                f"{base_url}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            html_content = data["content"][0]["text"]
        except Exception as exc:
            logger.error(f"LLM API call failed (deal roundup): {exc}")
            html_content = f"<!-- Blog generation failed: {exc} -->\n<p>Content unavailable.</p>"

    return _extract_post_metadata(html_content, effective_category, today_str)


# ---------------------------------------------------------------------------
# Blog post generation — evergreen SEO article (no deal data required)
# ---------------------------------------------------------------------------

async def generate_evergreen_article(category: str) -> Dict[str, str]:
    """
    Generate a timeless buying-guide article targeting informational search queries.
    Used when no live deal data is available for a category.
    """
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    model = os.environ.get("ANTHROPIC_MODEL", "deepseek-chat")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.deepseek.com/anthropic").rstrip("/")

    today_str = datetime.now().strftime("%Y-%m-%d")
    year = CURRENT_YEAR
    primary_kw = f"best {category.lower()} deals"

    prompt = f"""You are an expert SEO content writer. Write a comprehensive, evergreen buying guide.

Primary keyword: "{primary_kw}"
Category: {category}
Year: {year}

STRICT FORMAT REQUIREMENTS:
1. First line: <!-- META: [150-160 char meta description with "{primary_kw}"] -->
2. Full HTML article structure:

<article itemscope itemtype="https://schema.org/Article">
<h1 itemprop="headline">Best {category} Deals in {year}: Expert Buying Guide & Where to Save</h1>
<p class="post-intro">[2-3 sentence intro. Use "{primary_kw}" in first sentence. Tease the value readers will get.]</p>

<h2>What to Look for in {category} ({year} Guide)</h2>
<p>[300-400 word section on buying criteria — specs, brands, value factors. Be an expert.]</p>

<h2>Best Price Ranges for {category}</h2>
<ul>
<li><strong>Budget ($X–$Y):</strong> [What you get, recommended for whom]</li>
<li><strong>Mid-Range ($Y–$Z):</strong> [Sweet spot for most buyers]</li>
<li><strong>Premium ($Z+):</strong> [When it's worth paying more]</li>
</ul>

<h2>When Is the Best Time to Buy {category}?</h2>
<p>[Specific seasonal advice: Black Friday, Prime Day, end-of-season, back-to-school, etc. Mention exact months.]</p>

<h2>Top Retailers for {category} Deals</h2>
<ul>
<li><strong>Amazon:</strong> [Why/when to buy here]</li>
<li><strong>Walmart:</strong> [Why/when to buy here]</li>
<li><strong>Target:</strong> [Why/when to buy here]</li>
<li><strong>Best Buy / Specialty:</strong> [Price matching, open-box, etc.]</li>
</ul>

<h2>How to Stack Savings on {category}</h2>
<p>[Price history tools, coupon sites, credit card rewards, cashback portals — specific tactics]</p>

<h2>Frequently Asked Questions</h2>
<div itemscope itemtype="https://schema.org/FAQPage">
<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
  <h3 itemprop="name">What is a good discount percentage for {category.lower()}?</h3>
  <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
    <p itemprop="text">[Specific answer with numbers]</p>
  </div>
</div>
<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
  <h3 itemprop="name">How do I know if a {category.lower()} deal is actually good?</h3>
  <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
    <p itemprop="text">[CamelCamelCamel, price history, 90-day tracking explanation]</p>
  </div>
</div>
<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
  <h3 itemprop="name">Are refurbished {category.lower()} products worth buying?</h3>
  <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
    <p itemprop="text">[Honest breakdown of certified refurbished vs used, warranty considerations]</p>
  </div>
</div>
<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
  <h3 itemprop="name">Which brands offer the best value in {category.lower()}?</h3>
  <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
    <p itemprop="text">[Name 3-4 brands with brief justification]</p>
  </div>
</div>
</div>

<h2>Final Verdict: Getting the Best {category} Deals</h2>
<p>[2-3 sentence conclusion. Use "{primary_kw}" naturally. Direct CTA to bookmark/subscribe.]</p>
</article>

REQUIREMENTS:
- 1100-1500 words total
- Use "{primary_kw}" 4-6 times throughout (naturally)
- Every claim should be specific and actionable, not vague
- Output ONLY the HTML — no outer html/head/body tags"""

    html_content = ""
    async with httpx.AsyncClient(timeout=120.0) as http_client:
        try:
            resp = await http_client.post(
                f"{base_url}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            html_content = data["content"][0]["text"]
        except Exception as exc:
            logger.error(f"LLM API call failed (evergreen): {exc}")
            html_content = f"<!-- Blog generation failed: {exc} -->\n<p>Content unavailable.</p>"

    return _extract_post_metadata(html_content, category, today_str)


def _extract_post_metadata(html_content: str, category: str, today_str: str) -> Dict[str, str]:
    """Parse meta description, title, and slug from generated HTML."""
    meta_description = ""
    meta_match = re.search(r"<!--\s*META:\s*(.*?)\s*-->", html_content)
    if meta_match:
        meta_description = meta_match.group(1).strip()

    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", html_content, re.IGNORECASE | re.DOTALL)
    title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else f"Best {category} Deals"

    slug = _make_slug(category, today_str)

    if not meta_description:
        meta_description = (
            f"Find the best {category.lower()} deals today. "
            f"AI-curated discounts, price drops, and coupons — updated {today_str}."
        )[:160]

    return {
        "html": html_content,
        "meta_description": meta_description,
        "title": title,
        "slug": slug,
    }


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def save_blog_post(
    html: str, slug: str, meta_description: str = "", title: str = ""
) -> str:
    """
    Write blog/{slug}.html with full SEO meta tags, JSON-LD schema, OG/Twitter cards.
    Rebuilds index.html after saving.
    Returns the absolute file path.
    """
    blog_dir = _BLOG_DIR
    blog_dir.mkdir(parents=True, exist_ok=True)

    file_path = blog_dir / f"{slug}.html"
    display_title = title or slug.replace("-", " ").title()
    description = meta_description or f"Best deals curated by Deal Sniper AI — {display_title}"
    blog_base_url = os.environ.get("BLOG_BASE_URL", "https://deals-coupons-ai.vercel.app").rstrip("/")
    canonical = f"{blog_base_url}/blog/{slug}"
    today_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    date_only = slug[:10] if len(slug) >= 10 else datetime.now().strftime("%Y-%m-%d")

    # JSON-LD Article schema
    json_ld = (
        '{{"@context":"https://schema.org","@type":"Article",'
        '"headline":{title_json},'
        '"description":{desc_json},'
        '"datePublished":"{date}",'
        '"dateModified":"{date}",'
        '"author":{{"@type":"Organization","name":"Deal Sniper AI","url":"{base_url}"}},'
        '"publisher":{{"@type":"Organization","name":"Deal Sniper AI","url":"{base_url}"}},'
        '"mainEntityOfPage":{{"@type":"WebPage","@id":"{canonical}"}}}}'
    ).format(
        title_json=_json_str(display_title),
        desc_json=_json_str(description),
        date=today_iso,
        base_url=blog_base_url,
        canonical=canonical,
    )

    # Breadcrumb JSON-LD
    breadcrumb_ld = (
        '{{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":['
        '{{"@type":"ListItem","position":1,"name":"Home","item":"{base_url}"}},'
        '{{"@type":"ListItem","position":2,"name":"Blog","item":"{base_url}/blog/"}},'
        '{{"@type":"ListItem","position":3,"name":"{title}","item":"{canonical}"}}'
        ']}}'
    ).format(
        base_url=blog_base_url,
        title=display_title.replace('"', "'"),
        canonical=canonical,
    )

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{display_title} | Deal Sniper AI</title>
  <meta name="description" content="{description}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{canonical}">
  <link rel="stylesheet" href="/blog/style.css">
  <link rel="sitemap" type="application/xml" href="{blog_base_url}/blog/sitemap.xml">

  <!-- Open Graph -->
  <meta property="og:type" content="article">
  <meta property="og:title" content="{display_title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:site_name" content="Deal Sniper AI">
  <meta property="article:published_time" content="{today_iso}">

  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{display_title}">
  <meta name="twitter:description" content="{description}">

  <!-- JSON-LD Structured Data -->
  <script type="application/ld+json">{json_ld}</script>
  <script type="application/ld+json">{breadcrumb_ld}</script>
</head>
<body>
  <header class="site-header">
    <a href="/blog/" class="logo">&#127919; Deal Sniper AI</a>
    <nav>
      <a href="/">Home</a>
      <a href="/blog/">Blog</a>
    </nav>
  </header>

  <nav class="breadcrumb" aria-label="Breadcrumb">
    <ol>
      <li><a href="/">Home</a></li>
      <li><a href="/blog/">Blog</a></li>
      <li aria-current="page">{display_title}</li>
    </ol>
  </nav>

  <main class="post-content">
    <div class="post-header">
      <time datetime="{date_only}" class="post-date">{date_only}</time>
    </div>
{html}
  </main>

  <aside class="related-posts">
    <h2>More Deal Guides</h2>
    <p><a href="/blog/">Browse all deal roundups &rarr;</a></p>
  </aside>

  <footer class="site-footer">
    <p>&copy; {CURRENT_YEAR} Deal Sniper AI &mdash;
      <a href="/blog/sitemap.xml">Sitemap</a> &mdash;
      Affiliate links may be present &mdash;
      <a href="/">Back to App</a>
    </p>
  </footer>
</body>
</html>
"""

    file_path.write_text(full_html, encoding="utf-8")
    logger.info(f"Blog post saved: {file_path}")
    _rebuild_index()
    return str(file_path)


def _json_str(s: str) -> str:
    """Minimal JSON string escaping for inline JSON-LD."""
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def _rebuild_index() -> None:
    """Regenerate blog/index.html with all posts, newest first, full SEO meta tags."""
    blog_dir = _BLOG_DIR
    blog_base_url = os.environ.get("BLOG_BASE_URL", "https://deals-coupons-ai.vercel.app").rstrip("/")

    post_files = sorted(
        [f for f in blog_dir.glob("*.html") if f.stem != "index"],
        reverse=True,
    )

    post_cards = ""
    for f in post_files:
        slug = f.stem
        parts = slug.split("-", 3)
        if len(parts) >= 4:
            date_str = f"{parts[0]}-{parts[1]}-{parts[2]}"
            post_title = parts[3].replace("-", " ").title()
        else:
            date_str = ""
            post_title = slug.replace("-", " ").title()

        # Try to extract meta description from saved file for richer cards
        excerpt = ""
        try:
            content = f.read_text(encoding="utf-8")
            m = re.search(r'name="description" content="([^"]{30,})"', content)
            if m:
                excerpt = m.group(1)
        except Exception:
            pass

        post_cards += f"""
    <article class="post-card">
      <div class="post-meta">{date_str}</div>
      <h2><a href="/blog/{slug}">{post_title}</a></h2>
      {f'<p class="post-excerpt">{excerpt}</p>' if excerpt else ''}
      <a href="/blog/{slug}" class="read-more">Read deals &rarr;</a>
    </article>"""

    if not post_cards:
        post_cards = """
    <div class="coming-soon-card" style="background:linear-gradient(135deg,#1a1f2e 0%,#252d3d 100%);border:1px dashed #3b82f6;border-radius:12px;padding:3rem 2rem;text-align:center;">
      <div style="font-size:3rem;margin-bottom:1rem;">&#128269;</div>
      <h3 style="font-size:1.3rem;font-weight:700;margin-bottom:.75rem;color:#e2e8f0;">Scanning for the Best Deals&hellip;</h3>
      <p style="color:#94a3b8;max-width:420px;margin:0 auto 1.5rem;">Our AI publishes new deal guides every few hours. Check back soon!</p>
    </div>"""

    now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+00:00")

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Best Deals &amp; Coupons {CURRENT_YEAR} | Deal Sniper AI Blog</title>
  <meta name="description" content="AI-curated deal roundups and buying guides. The best discounts on electronics, gaming, home, kitchen, and more &mdash; updated every few hours.">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{blog_base_url}/blog/">
  <link rel="stylesheet" href="/blog/style.css">
  <link rel="sitemap" type="application/xml" href="{blog_base_url}/blog/sitemap.xml">

  <meta property="og:type" content="website">
  <meta property="og:title" content="Best Deals {CURRENT_YEAR} | Deal Sniper AI Blog">
  <meta property="og:description" content="AI-curated deal roundups updated every few hours. Top discounts ranked by savings.">
  <meta property="og:url" content="{blog_base_url}/blog/">
  <meta property="og:site_name" content="Deal Sniper AI">

  <script type="application/ld+json">
  {{"@context":"https://schema.org","@type":"Blog","name":"Deal Sniper AI Blog",
   "url":"{blog_base_url}/blog/","description":"AI-curated deal roundups and buying guides",
   "publisher":{{"@type":"Organization","name":"Deal Sniper AI","url":"{blog_base_url}"}}}}
  </script>
</head>
<body>
  <header class="site-header">
    <a href="/blog/" class="logo">&#127919; Deal Sniper AI</a>
    <nav>
      <a href="/">Home</a>
      <a href="/blog/">Blog</a>
    </nav>
  </header>

  <main class="index-main">
    <div class="hero">
      <h1>Best Deals &amp; Coupons {CURRENT_YEAR}</h1>
      <p>AI-curated buying guides and deal roundups &mdash; updated every few hours with real price drops across 20 categories.</p>
      <span class="badge">&#10024; New articles added throughout the day</span>
    </div>

    <div class="posts-grid">
      <h2 class="section-title">Recent Deal Guides</h2>
      {post_cards}
    </div>
  </main>

  <footer class="site-footer">
    <p>&copy; {CURRENT_YEAR} Deal Sniper AI &mdash;
      <a href="/blog/sitemap.xml">Sitemap</a> &mdash;
      Affiliate links may be present &mdash;
      <a href="/">Back to App</a>
    </p>
  </footer>
</body>
</html>
"""
    (blog_dir / "index.html").write_text(index_html, encoding="utf-8")
    logger.info("Blog index.html rebuilt")


# ---------------------------------------------------------------------------
# Sitemap + robots
# ---------------------------------------------------------------------------

def build_sitemap() -> str:
    """Build sitemap.xml with daily changefreq for recent posts, weekly for older."""
    blog_base_url = os.environ.get(
        "BLOG_BASE_URL", "https://deals-coupons-ai.vercel.app"
    ).rstrip("/")
    blog_dir = _BLOG_DIR
    blog_dir.mkdir(parents=True, exist_ok=True)

    sitemap_path = blog_dir / "sitemap.xml"
    today = datetime.now().date()
    url_entries = []

    # Blog index — highest priority
    url_entries.append(
        f"  <url>\n"
        f"    <loc>{blog_base_url}/blog/</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        f"    <changefreq>hourly</changefreq>\n"
        f"    <priority>1.0</priority>\n"
        f"  </url>"
    )

    for html_file in sorted(blog_dir.glob("*.html"), reverse=True):
        if html_file.stem == "index":
            continue
        slug = html_file.stem
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", slug)
        lastmod = date_match.group(1) if date_match else str(today)

        try:
            post_date = datetime.strptime(lastmod, "%Y-%m-%d").date()
            age_days = (today - post_date).days
        except ValueError:
            age_days = 999

        changefreq = "daily" if age_days <= 7 else "weekly"
        priority = "0.9" if age_days <= 3 else ("0.8" if age_days <= 14 else "0.6")

        url_entries.append(
            f"  <url>\n"
            f"    <loc>{blog_base_url}/blog/{quote(slug)}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    sitemap_content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(url_entries)
        + "\n</urlset>\n"
    )
    sitemap_path.write_text(sitemap_content, encoding="utf-8")
    logger.info(f"Sitemap built with {len(url_entries)} URLs")
    return str(sitemap_path)


def build_robots_txt() -> str:
    """Write blog/robots.txt (Vercel serves it at /blog/robots.txt)."""
    blog_base_url = os.environ.get(
        "BLOG_BASE_URL", "https://deals-coupons-ai.vercel.app"
    ).rstrip("/")
    robots_path = _BLOG_DIR / "robots.txt"
    robots_path.write_text(
        f"User-agent: *\n"
        f"Allow: /\n\n"
        f"Sitemap: {blog_base_url}/blog/sitemap.xml\n",
        encoding="utf-8",
    )
    return str(robots_path)


# ---------------------------------------------------------------------------
# Google Search Console ping
# ---------------------------------------------------------------------------

async def ping_google_search_console(sitemap_url: str) -> bool:
    ping_url = f"https://www.google.com/ping?sitemap={quote(sitemap_url, safe=':/')}"
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        try:
            resp = await http_client.get(ping_url)
            ok = resp.status_code < 300
            if ok:
                logger.info(f"Google Search Console ping OK (HTTP {resp.status_code})")
            else:
                logger.warning(f"Google ping returned HTTP {resp.status_code}")
            return ok
        except Exception as exc:
            logger.error(f"Google ping failed: {exc}")
            return False


# ---------------------------------------------------------------------------
# Public orchestrators
# ---------------------------------------------------------------------------

async def write_seo_article(category: str = None) -> Dict[str, Any]:
    """
    Generate one SEO article for a given category (or the next unwritten one).
    Uses real deal data if available; falls back to an evergreen buying guide.
    Saves the file, rebuilds index, updates sitemap, pings Google, and pushes to GitHub.
    """
    if not category:
        category = _get_next_category()

    logger.info(f"Writing SEO article: {category}")

    # Try to use real deal data filtered to this category
    all_deals = await get_top_deals_this_week(limit=30)
    category_deals = [
        d for d in all_deals
        if category.lower().split()[0] in (d.get("category") or "").lower()
    ]

    if category_deals:
        post = await generate_blog_post(category_deals[:10], category=category)
        post_type = "deal roundup"
    else:
        post = await generate_evergreen_article(category)
        post_type = "evergreen guide"

    file_path = save_blog_post(
        post["html"], post["slug"],
        meta_description=post["meta_description"],
        title=post["title"],
    )

    build_sitemap()
    build_robots_txt()

    blog_base_url = os.environ.get("BLOG_BASE_URL", "https://deals-coupons-ai.vercel.app").rstrip("/")
    await ping_google_search_console(f"{blog_base_url}/blog/sitemap.xml")

    pushed = _git_commit_and_push(
        f"blog: {category} {post_type} [{post['slug']}]"
    )

    result = {
        "slug": post["slug"],
        "category": category,
        "post_type": post_type,
        "file_path": file_path,
        "git_pushed": pushed,
    }
    logger.info(f"SEO article complete: {result}")
    return result


async def write_weekly_blog() -> Dict[str, Any]:
    """
    Weekly deal-roundup orchestrator (kept for backward compatibility with Friday/Sunday tasks).
    Fetches top 10 deals, generates a roundup, and pushes to GitHub.
    """
    client = get_supabase_client()
    deals = await get_top_deals_this_week(limit=10)

    if not deals:
        logger.warning("No deals found for weekly blog — aborting")
        return {"slug": None, "file_path": None, "deals_count": 0,
                "sitemap_updated": False, "google_pinged": False, "git_pushed": False}

    category_counts = Counter(d.get("category") or "General" for d in deals)
    top_category = category_counts.most_common(1)[0][0]
    logger.info(f"Generating weekly blog post for category: {top_category}")

    post = await generate_blog_post(deals, category=top_category)
    file_path = save_blog_post(post["html"], post["slug"],
                               meta_description=post["meta_description"],
                               title=post["title"])

    build_sitemap()
    build_robots_txt()

    blog_base_url = os.environ.get("BLOG_BASE_URL", "https://deals-coupons-ai.vercel.app").rstrip("/")
    google_pinged = await ping_google_search_console(f"{blog_base_url}/blog/sitemap.xml")

    # Update blog_post_slug on posted deals
    for deal in deals:
        deal_id = deal.get("deal_id")
        if deal_id:
            try:
                client.table("posted_deals").update(
                    {"blog_post_slug": post["slug"]}
                ).eq("id", deal_id).execute()
            except Exception as exc:
                logger.warning(f"Could not update blog_post_slug for {deal_id}: {exc}")

    # Log to daily_digest_logs
    today_str = datetime.now().strftime("%Y-%m-%d")
    try:
        client.table("daily_digest_logs").insert({
            "digest_date": today_str,
            "type": "weekly_blog",
            "total_deals": len(deals),
            "slug": post["slug"],
        }).execute()
    except Exception as exc:
        logger.warning(f"Could not insert daily_digest_logs row: {exc}")

    pushed = _git_commit_and_push(f"blog: weekly roundup [{post['slug']}]")

    result = {
        "slug": post["slug"],
        "file_path": file_path,
        "deals_count": len(deals),
        "sitemap_updated": True,
        "google_pinged": google_pinged,
        "git_pushed": pushed,
    }
    logger.info(f"Weekly blog complete: {result}")
    return result
