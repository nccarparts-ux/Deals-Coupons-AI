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
- **Twitter API returns 402 on free tier** — all Twitter posting falls back to manual: saves `.txt` to `deal_sniper_ai/output/twitter/` and sends Telegram DM to owner
- **`worker_ready` signal fires before broker transport is fully ready** — `apply_async` called from within it fails silently; dispatch startup tasks from `start_deal_sniper.bat` instead using `python -c "...apply_async(...)"` after a startup delay
- **Global `task_time_limit=300` matches beat interval of 300s** — any long-running task will be killed on every run; override per-task with `@app.task(time_limit=N, soft_time_limit=M)` on the decorator
- **Python 3.13 UnboundLocalError scoping**: if a variable is assigned *anywhere* in a function, Python marks it local for the *entire* scope — reading it before the assignment raises `UnboundLocalError`, not `NameError`. Caught silently at DEBUG level; always assign sentinel (`= None`) before any conditional assignment
- **Amazon CDN URLs blocked by Telegram's `sendPhoto` fetcher** — Telegram's servers try to fetch the image from Amazon and get blocked. Fix: download image bytes ourselves (httpx with Chrome UA + Amazon Referer), then POST bytes as multipart to `sendPhoto`. Fallback to `sendMessage` text-only if download fails

## Key Paths
- `deal_sniper_ai/config/config.yaml` — retailer configs, selectors, affiliate tag `bidyarddeal09-20`
- `deal_sniper_ai/crawler/ecommerce_crawler.py` — Playwright scraper (Chromium, anti-blocking)
- `deal_sniper_ai/crawler/anti_blocking.py` — UserAgentInfo dataclass, 15 built-in agents (no DB)
- `deal_sniper_ai/posting_engine/instant_poster.py` — immediate Telegram post on deal found
- `deal_sniper_ai/posting_engine/platforms/tiktok_poster.py` — TikTok video pipeline + meme generation
- `deal_sniper_ai/posting_engine/platforms/twitter_poster.py` — Twitter poster (manual fallback + engagement bot)
- `deal_sniper_ai/posting_engine/platforms/remotion_renderer.py` — Remotion DealVideo + MemeVideo renderer
- `deal_sniper_ai/posting_engine/cross_poster.py` — auto-tweets TikTok teaser after each render
- `deal_sniper_ai/database/supabase_client.py` — uses service role key, bypasses RLS
- `supabase/migrations/` — all 4 migrations already applied
- `tiktok_remotion/src/DealVideo.tsx` — 20s deal video composition (600 frames)
- `tiktok_remotion/src/MemeVideo.tsx` — 15s meme video composition (450 frames, 4 scenes)
- `tiktok_remotion/src/Root.tsx` — registers both DealVideo and MemeVideo compositions
- `deal_sniper_ai/output/tiktok/` — rendered TikTok .mp4 files
- `deal_sniper_ai/output/twitter/` — manual Twitter post .txt files

## Pipeline (end-to-end working)
```
start_deal_sniper.bat → python -c "monitor_retailer.apply_async('amazon')"  [immediate on startup]

monitor_retailer (Celery, every 5 min, 4 categories/run rotating)
  → EcommerceCrawler.crawl_search_results()   [Playwright, domcontentloaded]
  → crawl_product_page()                       [wait_until=load, 8s selector wait]
  → _save_product()                            → products + price_history (Supabase)
  → _check_and_post_deal()
  → instant_poster.detect_and_post_deal()      → deal_candidates (Supabase)
  → TelegramPoster                             → Telegram channel immediately

TikTok deal video (every 30 min, viral_potential >= 8):
  notify_tiktok_ready → generate_and_notify()
  → generate_script() [AI + COMMENT_BAIT + TELEGRAM_INVITE_LINK injected into CTA]
  → _build_voiceover() [edge-tts]
  → _fetch_pexels_clips() + _assemble_video() [MoviePy]
  → manual_upload_helper() → Telegram DM to owner (file path + hashtags + pinned comment tip)
  → cross_poster.post_tiktok_teaser_tweet() → Twitter teaser (or manual .txt fallback)

Meme TikTok (2x/day: 10am + 6pm UTC):
  render_meme_tiktok_task → generate_meme_and_notify()
  → generate_meme_script() [6 formats: two_types, skill_issue, amazon_knows, horror_story, pov_found_group, ancestor_disappointment]
  → same video pipeline → Telegram DM → cross-post tweet

Twitter meme tweet (daily noon UTC):
  post_meme_tweet_task → post_meme_tweet()
  → MEME_TWEETS pool (15 tweets) + AI enhancement
  → API attempt → if 402/403: save .txt + Telegram DM to owner

Twitter engagement bot (every 90 min):
  run_twitter_engagement_bot_task → twitter_engagement_bot()
  → search #deals #coupons #frugal #AmazonDeals → reply to 10/run
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
- Owner DM: chat ID `1711165098` — receives TikTok upload instructions + Twitter manual posts
- Public invite link: `https://t.me/Coupons_Deals_Steals` (in `TELEGRAM_INVITE_LINK` env var)
- Links use HTML format: `<a href="full_affiliate_url">amazon.com/dp/ASIN</a>` — hides tag

## Affiliate
- **Amazon tag: `bidyarddeal09-20`** (updated from bidyarddeals-20)
- Tag set in: `.env` (AMAZON_ASSOCIATE_TAG), `config.yaml`, `instant_poster.py` default arg
- Links format: `https://www.amazon.com/dp/ASIN?tag=bidyarddeal09-20`

## Crawler (current state)
- Amazon only (Walmart/Target disabled) — extracts from search cards, no individual page visits
- 91 categories in config.yaml, 7 pages each, 35% min discount, 12h per-product cooldown
- **4 categories crawled per beat tick** (rotating via Redis key `crawler_category_index:amazon`); all 91 covered in ~23 runs (~2 hrs). Full 91-category crawl takes ~31 min — never attempt in a single task
- Task time limit: `time_limit=420, soft_time_limit=360` on `monitor_retailer` decorator
- Min post score: 80 — `instant_poster.py` scores and posts immediately on detection
- 5 rotating post templates in `instant_poster.py`, all include `#ad`, times in EST/EDT
- `"jewelry deals"` category returns brand storefronts — replaced with specific terms
- Telegram image posting: TelegramPoster downloads image bytes with Chrome UA then uploads as multipart; falls back to text-only if download fails

## Viral Funnel (TikTok + Twitter)
- `COMMENT_BAIT` injected into every deal CTA; `CLIFFHANGER_ENDINGS` for viral_potential >= 9
- `HASHTAG_SETS` — 14 format-specific hashtag strings sent in TikTok upload DM
- Manual upload DM includes: file path, caption, hashtags, pinned comment suggestion
- Twitter: all posting falls back to `.txt` file + Telegram DM (API is 402 on free tier)
- Cross-poster: tweets TikTok teaser after every render (deal + meme)

## Environment Variables (all in .env)
```
TELEGRAM_BOT_TOKEN         — bot token
TELEGRAM_CHANNEL_ID        — public channel (-1003739890278)
TELEGRAM_OWNER_ID          — owner DM chat ID (1711165098)
TELEGRAM_INVITE_LINK       — https://t.me/Coupons_Deals_Steals
AMAZON_ASSOCIATE_TAG       — bidyarddeal09-20
SUPABASE_URL / SUPABASE_SERVICE_KEY
ANTHROPIC_AUTH_TOKEN / ANTHROPIC_MODEL / ANTHROPIC_BASE_URL  (DeepSeek)
PEXELS_API_KEY             — for TikTok stock footage
TWITTER_API_KEY / TWITTER_API_SECRET
TWITTER_ACCESS_TOKEN / TWITTER_ACCESS_SECRET
TWITTER_CLIENT_ID / TWITTER_CLIENT_SECRET
```

## Next
- Amazon PAAPI integration (needs 3 qualifying Associate sales first)
- Keepa API for price history (available immediately, ~$18/mo)
- Residential proxies (Webshare ~$15/mo) when home IP gets soft-blocked
- Twitter Basic plan ($100/mo) if Twitter becomes a priority channel
- Scale Celery workers for higher throughput
