# Deals-Coupons-AI

**Stack:** Python/FastAPI, Supabase REST (no direct PostgreSQL), Redis/Celery, Playwright, Telegram Bot, DeepSeek LLM (64K ctx)

## Rules
- **Never read files in `archive/` unless explicitly asked**

## Conventions
- Open files with `encoding='utf-8'` on Windows
- Use ASCII not Unicode in console output (Windows CP1252)
- `pip install scikit-learn --only-binary` on Windows
- Absolute imports, conventional commits, no debug logs in prod

## Known Issues
- Supabase direct PostgreSQL blocked (IPv6) — always use REST API
- **Must use `SUPABASE_SERVICE_KEY` for writes** (anon key gets 401 on INSERT/UPDATE)
- SQLite: cannot FK to `auth.users` — skip in local tests
- Playwright: use `domcontentloaded` for search pages, `load` for product pages
- `networkidle` times out on Amazon — never use it
- `AsyncSessionLocal` raises RuntimeError everywhere — use `get_supabase_client()` instead
- Port 8000 gets phantom socket entries on Windows that can't be killed — use 8001
- Celery task modules use `from deal_sniper_ai.scheduler.celery_app import celery_app` — the export is `celery_app = app` (alias exists at bottom of celery_app.py); without it all tasks fall back to broken local app
- Beat crashes if `celerybeat-schedule` file is stale — delete it before restarting beat
- Amazon search results mix brand storefront cards (brand-only h2) with product cards — use `h2 a span` selector and skip titles < 15 chars or < 3 words
- Webshare free datacenter proxies are all blocked by Amazon — not worth using; residential proxies (~$15/mo) work indefinitely

## Key Paths
- `deal_sniper_ai/config/config.yaml` — retailer configs, selectors, affiliate tag `bidyarddeals-20`
- `deal_sniper_ai/crawler/ecommerce_crawler.py` — Playwright scraper (Chromium, anti-blocking)
- `deal_sniper_ai/crawler/anti_blocking.py` — UserAgentInfo dataclass, 15 built-in agents (no DB)
- `deal_sniper_ai/posting_engine/instant_poster.py` — immediate Telegram post on deal found
- `deal_sniper_ai/database/supabase_client.py` — uses service role key, bypasses RLS
- `supabase/migrations/` — all 4 migrations already applied

## Pipeline (end-to-end working)
```
monitor_retailer (Celery, every 5 min)
  → EcommerceCrawler.crawl_search_results()   [Playwright, domcontentloaded]
  → crawl_product_page()                       [wait_until=load, 8s selector wait]
  → _save_product()                            → products + price_history (Supabase)
  → _check_and_post_deal()
  → instant_poster.detect_and_post_deal()      → deal_candidates (Supabase)
  → TelegramPoster                             → Telegram immediately
```

## Services (all running)
- Redis: Windows service, port 6379
- Celery worker + beat: started via `start_deal_sniper.bat`
- API: `venv/Scripts/uvicorn deal_sniper_ai.api.main:app --port 8001 --reload`
- Dashboard: http://localhost:8001/dashboard (dark modern theme)
- Admin alerts: Telegram DM to chat ID `1711165098` every 15 min if broken

## Telegram
- Bot: `@coupondealssteals_bot` (token in .env)
- Channel: `-1003739890278` (supergroup, bot is admin)
- Links use HTML format: `<a href="full_affiliate_url">amazon.com/dp/ASIN</a>` — hides tag

## Crawler (current state)
- Amazon only (Walmart/Target disabled) — extracts from search cards, no individual page visits
- 89 categories in config.yaml, 7 pages each, 35% min discount, 12h per-product cooldown
- Min post score: 80 — `instant_poster.py` scores and posts immediately on detection
- 5 rotating post templates in `instant_poster.py`, all include `#ad`, times in EST/EDT
- `"jewelry deals"` category returns brand storefronts — replaced with specific terms

## Next
- Amazon PAAPI integration (needs 3 qualifying Associate sales first)
- Keepa API for price history (available immediately, ~$18/mo)
- Residential proxies (Webshare ~$15/mo) when home IP gets soft-blocked
- Scale Celery workers for higher throughput
