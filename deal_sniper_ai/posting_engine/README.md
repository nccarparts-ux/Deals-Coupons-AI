# Posting Engine for Deal Sniper AI

Handles posting deals and viral content to social platforms with score filtering,
manual upload assistance, and a Telegram DM notification flow for manual steps.

## Platform Status

| Platform | Status | Method |
|----------|--------|--------|
| **Telegram** | Live | Bot API — auto-posts deals to channel immediately |
| **TikTok** | Live (manual upload) | Renders .mp4 → Telegram DM with file path + instructions |
| **Twitter/X** | Manual fallback | API returns 402 (free tier) → saves .txt + Telegram DM |
| **Discord** | Configured | Webhooks, rich embeds |
| **Facebook** | Configured | Placeholder — requires Page token |
| **Pinterest** | Configured | Placeholder — requires board token |

## Key Files

```
posting_engine/
  instant_poster.py          — scores deals, posts to Telegram immediately on detection
  platforms/
    telegram_poster.py       — Telegram Bot API poster
    tiktok_poster.py         — TikTok video pipeline + meme generation
    twitter_poster.py        — Twitter poster (manual fallback + engagement bot)
    remotion_renderer.py     — Remotion DealVideo + MemeVideo renderer
    discord_poster.py        — Discord webhook poster
    facebook_poster.py       — Facebook placeholder
    pinterest_poster.py      — Pinterest placeholder
  cross_poster.py            — tweets TikTok teaser after each render
  tasks.py                   — all Celery task wrappers
  formatter.py               — platform-specific message formatting
  copy_generator.py          — AI-generated deal copy
```

## TikTok Flow

Every deal with `viral_potential >= 8` triggers a video pipeline:

1. `generate_script()` — AI voiceover script (DeepSeek), with `COMMENT_BAIT` and
   `TELEGRAM_INVITE_LINK` injected into the CTA. `CLIFFHANGER_ENDINGS` injected for
   `viral_potential >= 9`.
2. `_build_voiceover()` — edge-tts (en-US-ChristopherNeural, +20% rate)
3. `_fetch_pexels_clips()` — 3 stock clips from Pexels
4. `_assemble_video()` — MoviePy: clips + captions + product image overlay
5. `manual_upload_helper()` — Telegram DM to owner (`TELEGRAM_OWNER_ID`) with:
   - File path of the .mp4
   - Caption to paste
   - `HASHTAG_SETS` for the specific video format (14 sets defined)
   - Suggested pinned comment + "Pin this first for algorithm boost"
   - Trending sound tip
6. `cross_poster.post_tiktok_teaser_tweet()` — tweets a teaser (or saves .txt fallback)

**Meme TikToks** (no deal data needed) use `generate_meme_and_notify()`:
- 6 formats: `two_types`, `skill_issue`, `amazon_knows`, `horror_story`,
  `pov_found_group`, `ancestor_disappointment`
- Same pipeline as deal videos; Remotion `MemeVideo` composition (15s / 450 frames)
  available via `render_meme_video()` in `remotion_renderer.py`

Output directory: `deal_sniper_ai/output/tiktok/`

## Twitter Flow

All tweet types attempt the API first, then fall back automatically if it fails (402/403):

**API available:** posts directly via OAuth 1.0a to `POST /2/tweets`

**API unavailable (current state — free tier 402):**
- Saves a `.txt` file to `deal_sniper_ai/output/twitter/`
- Sends Telegram DM to owner with the tweet text ready to copy-paste and 5-step upload instructions

Tweet types:
- **Meme tweets** — `MEME_TWEETS` pool (15 tweets), AI-enhanced via DeepSeek
- **Viral format tweets** — `TWITTER_VIRAL_FORMATS` (poll, shock stat, thread teaser, engagement hook)
- **Deal tweets** — single tweet with hashtags + `TELEGRAM_INVITE_LINK`
- **Viral threads** — 3-tweet thread for `viral_potential >= 9`
- **Engagement bot** — replies to `#deals #coupons #frugal #AmazonDeals` (10 replies/run)

## Celery Beat Schedule

| Task | Schedule | What it does |
|------|----------|--------------|
| `notify-tiktok-every-30min` | Every 30 min | Deal TikTok for viral_potential >= 8 |
| `render-meme-tiktok-am` | 10:00 UTC | Meme TikTok video |
| `render-meme-tiktok-pm` | 18:00 UTC | Meme TikTok video |
| `post-meme-tweet` | 12:00 UTC | Daily meme tweet (or manual .txt) |
| `run-twitter-engagement-bot` | Every 90 min | Reply to deal hashtag tweets |
| `post-twitter-8am/12pm/5pm/9pm` | 4x daily | Deal tweet (or manual .txt) |
| `daily-deal-planner` | 06:00 UTC | Queues top deals across platforms |

## Environment Variables

```bash
# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=-1003739890278
TELEGRAM_OWNER_ID=1711165098          # receives TikTok + Twitter DM notifications
TELEGRAM_INVITE_LINK=https://t.me/Coupons_Deals_Steals  # injected into every CTA

# Affiliate
AMAZON_ASSOCIATE_TAG=bidyarddeal09-20

# TikTok stock footage
PEXELS_API_KEY=...

# Twitter (OAuth 1.0a — currently 402 on free tier)
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
TWITTER_ACCESS_TOKEN=...
TWITTER_ACCESS_SECRET=...
TWITTER_CLIENT_ID=...
TWITTER_CLIENT_SECRET=...

# AI (DeepSeek via Anthropic-compatible API)
ANTHROPIC_AUTH_TOKEN=...
ANTHROPIC_MODEL=deepseek-chat
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
```

## Affiliate Tag

Current tag: **`bidyarddeal09-20`**

Set in: `.env` → `AMAZON_ASSOCIATE_TAG`, `config.yaml`, and `instant_poster.py` default arg.
All new links generated by the crawler and copy generator use this tag automatically.

## Testing

```bash
# Test meme TikTok + Twitter teaser + Telegram DM
venv/Scripts/python scripts/test_meme_tiktok.py

# Test deal TikTok video generation
venv/Scripts/python scripts/test_comedy_tiktok.py

# Test live Telegram post with a sample deal
venv/Scripts/python scripts/test_live_post.py
```

## Troubleshooting

**Twitter 402 Payment Required** — expected on free developer tier. Posts save to
`deal_sniper_ai/output/twitter/` and a Telegram DM is sent. Upgrade to Twitter Basic
($100/mo) to enable direct posting.

**TikTok video missing captions** — no system font found. Ensure Arial/Calibri is
installed (`C:/Windows/Fonts/arialbd.ttf`).

**Remotion render fails** — check Node.js is installed (`node --version >= 18`).
Run `npm install` in `tiktok_remotion/` manually if deps are missing.

**Pexels clips empty** — verify `PEXELS_API_KEY` in `.env`. Check the query term
isn't too specific.

**Beat schedule not picking up new tasks** — delete the stale `celerybeat-schedule`
file and restart beat.
