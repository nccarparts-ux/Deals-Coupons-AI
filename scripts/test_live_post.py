"""
Live post test — fires a real Telegram deal alert + TikTok video generation immediately.
Bypasses Celery and jitter delay for instant testing.

Usage:
    python scripts/test_live_post.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Make sure project root is on the path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── Sample deal data ──────────────────────────────────────────────────────────
SAMPLE_DEAL = {
    "id": "test-deal-001",
    "title": "Sony WH-1000XM5 Wireless Noise Canceling Headphones",
    "current_price": 229.99,
    "original_price": 399.99,
    "discount_percent": 43,
    "retailer": "amazon",
    "category": "electronics",
    "rating": 4.8,
    "review_count": 18423,
    "viral_potential": 9.2,
    "url": "https://www.amazon.com/dp/B09XS7JWHH?tag=bidyarddeals-20",
    "affiliate_link": "https://www.amazon.com/dp/B09XS7JWHH?tag=bidyarddeals-20",
    "image_url": "https://m.media-amazon.com/images/I/71o8Q5XJS5L._AC_SL1000_.jpg",
}


async def send_telegram_deal(deal: dict) -> bool:
    """Send a formatted deal alert directly to Telegram."""
    import httpx

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    # Send test deal to owner DM if set, otherwise group channel
    channel_id = os.environ.get("TELEGRAM_OWNER_ID") or os.environ.get("TELEGRAM_CHANNEL_ID", "")

    if not bot_token or not channel_id:
        print("[FAIL] TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not set in .env")
        return False

    savings = deal["original_price"] - deal["current_price"]
    message = (
        f"🔥 DEAL ALERT — {deal['discount_percent']}% OFF\n\n"
        f"<b>{deal['title']}</b>\n\n"
        f"💰 Now: <b>${deal['current_price']:.2f}</b>\n"
        f"❌ Was: ${deal['original_price']:.2f}\n"
        f"💵 You save: ${savings:.2f}\n\n"
        f"⭐ {deal['rating']} stars · {deal['review_count']:,} reviews\n\n"
        f"🛒 <a href=\"{deal['affiliate_link']}\">Grab it on Amazon →</a>\n\n"
        f"<i>Deals found by @DealSniperAI · Join for daily alerts</i>"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": channel_id, "text": message, "parse_mode": "HTML"},
        )
        result = resp.json()
        if result.get("ok"):
            print(f"[OK] Telegram deal alert sent!")
            return True
        else:
            print(f"[FAIL] Telegram error: {result.get('description')}")
            return False


async def generate_tiktok(deal: dict) -> dict:
    """Generate TikTok video + send Telegram upload notification."""
    from deal_sniper_ai.posting_engine.platforms.tiktok_poster import generate_and_notify

    print("[...] Generating TikTok video (this takes 1-2 minutes)...")
    caption = (
        f"{deal['title']} — {deal['discount_percent']}% off! "
        f"Now ${deal['current_price']:.2f} (was ${deal['original_price']:.2f}). "
        f"Join our Telegram for daily deals — link in bio!"
    )
    result = await generate_and_notify(
        deal_data=deal,
        posted_deal_id=deal["id"],
        caption=caption,
    )
    return result


async def main():
    print("=" * 60)
    print("  Deal Sniper AI — Live Post Test")
    print("=" * 60)
    print(f"\nDeal: {SAMPLE_DEAL['title']}")
    print(f"Price: ${SAMPLE_DEAL['current_price']} (was ${SAMPLE_DEAL['original_price']})")
    print(f"Discount: {SAMPLE_DEAL['discount_percent']}% off\n")

    # Step 1: Telegram deal alert
    print("Step 1: Sending Telegram deal alert...")
    await send_telegram_deal(SAMPLE_DEAL)

    # Step 2: TikTok video + Telegram upload notification
    print("\nStep 2: Generating TikTok video...")
    try:
        result = await generate_tiktok(SAMPLE_DEAL)
        if result.get("success"):
            print(f"[OK] TikTok video saved to: {result.get('video_path')}")
            print("[OK] Telegram upload notification sent!")
        else:
            print(f"[WARN] TikTok generation skipped: {result.get('error')}")
    except Exception as e:
        print(f"[FAIL] TikTok error: {e}")
        print("       (Check that moviepy, gTTS, pydub are installed)")
        print("       pip install moviepy gTTS pydub")

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
