"""
TikTok Poster for Deal Sniper AI Platform.

TikTok's API does not support programmatic video uploads without approved business access.
This module handles everything else: AI script generation, voiceover synthesis, Pexels stock
clip downloads, MoviePy video assembly with burn-in captions, saving the .mp4 path to
Supabase, and sending a Telegram notification with manual upload instructions.

Required environment variables:
    ANTHROPIC_AUTH_TOKEN   - Anthropic API key for script generation
    ANTHROPIC_MODEL        - Model name (e.g. claude-opus-4-6)
    ANTHROPIC_BASE_URL     - Base URL for Anthropic API (optional override)
    PEXELS_API_KEY         - Pexels API key for stock video clips
                             (add PEXELS_API_KEY=<your_key> to your .env file)
    TELEGRAM_BOT_TOKEN     - Telegram bot token (already in .env)
    TELEGRAM_CHANNEL_ID    - Telegram channel ID (already in .env)
"""

import io
import json
import logging
import os
import random
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OUTPUT_DIR = "deal_sniper_ai/output/tiktok"

# Script section timing — 20 seconds total for music compatibility
# TikTok trending music loops at 15-30s; staying under 22s lets the beat breathe
SECTION_TIMES = {
    "hook":    0,   # 0-2s   ultra-short pattern interrupt
    "problem": 2,   # 2-6s   the deal / savings hook
    "reveal":  6,   # 6-12s  details + proof
    "proof":   12,  # 12-16s urgency / social proof
    "cta":     16,  # 16-20s Telegram/follow CTA
}

# Proven viral TikTok deal-content formats — rotated randomly per video
# These feel organic, not ad-like
VIRAL_FORMATS = [
    {
        "name": "pov_savings",
        "hook_template":    "POV: You just saved {savings} without even trying.",
        "theme":            "lifestyle savings",
        "pexels_query":     "person phone shopping happy",
    },
    {
        "name": "stop_paying",
        "hook_template":    "Stop paying full price. Seriously.",
        "theme":            "money saving tips",
        "pexels_query":     "saving money wallet cash",
    },
    {
        "name": "secret_deal",
        "hook_template":    "Amazon doesn't want you to see this deal.",
        "theme":            "exclusive deal reveal",
        "pexels_query":     "online shopping laptop excited",
    },
    {
        "name": "countdown",
        "hook_template":    "3 deals ending TODAY you need to grab right now.",
        "theme":            "deals countdown",
        "pexels_query":     "shopping online sale discount",
    },
    {
        "name": "frugal_hack",
        "hook_template":    "Things frugal people do that broke people don't.",
        "theme":            "money saving lifestyle",
        "pexels_query":     "woman smiling phone happy",
    },
    {
        "name": "cant_believe",
        "hook_template":    "I literally cannot believe this price right now.",
        "theme":            "deal shock reaction",
        "pexels_query":     "surprised woman phone deal",
    },
    {
        "name": "before_you_buy",
        "hook_template":    "Wait — before you buy anything online, watch this.",
        "theme":            "smart shopping tips",
        "pexels_query":     "smart shopping online coupon",
    },
    {
        "name": "this_week",
        "hook_template":    "Best deals this week that are actually worth it.",
        "theme":            "weekly deals roundup",
        "pexels_query":     "shopping bags sale fashion",
    },
]

# Trending sound categories to suggest in the upload notification
TRENDING_SOUND_TIPS = [
    "Search 'cash register' sounds — great for deal reveals",
    "Use a trending upbeat pop track (check TikTok Discover → Trending sounds)",
    "Lo-fi hip hop works well for money-saving lifestyle content",
    "Use a fast-paced EDM drop that hits at the reveal moment",
    "Search 'viral remix' in TikTok sounds — any trending track with energy",
    "Use a trending audio clip from a creator with 1M+ likes this week",
]

# Pexels video search endpoint
PEXELS_VIDEO_SEARCH_URL = "https://api.pexels.com/videos/search"
PEXELS_IMAGE_SEARCH_URL = "https://api.pexels.com/v1/search"

# TikTok aspect ratio target
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920

# Windows font paths for captions (tries each in order)
WINDOWS_FONTS = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/verdana.ttf",
]

# Maps product keywords → Pexels search terms for relevant footage
PRODUCT_TO_PEXELS: Dict[str, str] = {
    "headphone": "headphones music listening",
    "earphone": "earbuds wireless music",
    "airpod": "earbuds wireless",
    "speaker": "speaker music audio",
    "laptop": "laptop computer typing",
    "computer": "computer desk work",
    "phone": "smartphone mobile",
    "tablet": "tablet screen",
    "camera": "camera photography",
    "television": "television watching",
    "tv ": "television watching",
    "watch": "smartwatch fitness wrist",
    "vacuum": "cleaning home floor",
    "coffee": "coffee kitchen morning",
    "blender": "blender kitchen smoothie",
    "knife": "kitchen cooking chef",
    "cookware": "cooking kitchen pots",
    "pillow": "bedroom sleep pillow",
    "mattress": "bedroom sleeping",
    "chair": "chair office sitting",
    "desk": "office desk workspace",
    "gaming": "gaming controller esports",
    "keyboard": "keyboard typing computer",
    "monitor": "computer monitor screen",
    "shoe": "shoes walking street",
    "sneaker": "sneakers running athletic",
    "backpack": "backpack travel school",
    "fitness": "gym workout exercise",
    "yoga": "yoga exercise stretch",
    "bicycle": "cycling outdoor exercise",
    "drill": "tools construction diy",
    "tool": "tools workshop hardware",
    "outdoor": "outdoor nature adventure",
    "baby": "baby children family",
    "pet": "dog cat pet home",
    "book": "reading books study",
}

# ---------------------------------------------------------------------------
# Viral engagement — comment bait, series hooks, cliffhangers
# ---------------------------------------------------------------------------

COMMENT_BAIT = [
    "Drop a \U0001f525 if you want the direct link",
    "Comment DEAL and I'll DM you the group",
    "Save this before the price goes back up \U0001f446",
    "Tag someone paying full price right now",
    "Reply FREE for the full daily list",
]

SERIES_HOOKS = [
    "Part {n}: deals Amazon doesn't want you finding",
    "Day {n} of never paying full price",
    "Deal #{n} this week that felt illegal",
]

CLIFFHANGER_ENDINGS = [
    "...and there are 9 more just like it in the group",
    "...Part 2 drops tomorrow. Follow so you don't miss it.",
    "...the craziest one I found today is in the group. Link in bio.",
]

# Hashtag sets per video format — paste into TikTok after uploading
HASHTAG_SETS: Dict[str, str] = {
    "pov_savings":    "#DealsAndSteals #SaveMoney #MoneyHacks #DealAlert #FrugalLiving #TikTokDeals #AmazonDeals #CouponQueen #Savings #FYP",
    "stop_paying":    "#BudgetHacks #MoneyTips #SaveMoney #NeverPayFull #CouponCode #Deals #FrugalLife #SmartShopping #Cashback #FYP",
    "secret_deal":    "#SecretDeal #HiddenDeal #DealHack #PriceGlitch #AmazonHack #DealAlert #Savings #FYP #TikTokMadeMeBuyIt #ForYou",
    "countdown":      "#DealAlert #TodayOnly #LimitedTime #SaleAlert #FlashSale #Deals #Savings #FYP #Amazon #GrabItNow",
    "frugal_hack":    "#FrugalLiving #MoneyHacks #CouponLife #BudgetQueen #SavingMoney #FinanceTok #MoneyTips #Deals #FYP #Smart",
    "cant_believe":   "#UnbelievableDeal #PriceDrop #WontLast #DealShock #AmazonFinds #DealsAndSteals #Savings #FYP #Viral #ShoppingHack",
    "before_you_buy": "#ShoppingTips #MoneyHacks #SmartShopping #BeforeYouBuy #SaveMoney #ConsumerTips #Deals #FYP #Hack #DealAlert",
    "this_week":      "#WeeklyDeals #BestDeals #TopDeals #DealRoundup #Savings #FrugalLiving #AmazonDeals #FYP #DealAlert #Sale",
    # Meme formats
    "two_types":             "#TwoTypes #FinanceTok #MoneyMeme #CouponMeme #DealMeme #BrokeOrBuilt #SmartMoney #FYP #Viral #Relatable",
    "skill_issue":           "#SkillIssue #FinanceTok #MoneyMeme #PaidFullPrice #CouponLife #FYP #Viral #FunnyMoney #Relatable #Deals",
    "amazon_knows":          "#AmazonHack #PriceDrop #DealGlitch #CouponCode #FYP #Viral #FinanceTok #MoneyMeme #SmartShopping #Deals",
    "horror_story":          "#HorrorStory #FullPrice #DealMiss #FOMO #MoneyMistake #FYP #Viral #FinanceTok #SaveMoney #CouponLife",
    "pov_found_group":       "#POV #TelegramDeals #FreeDeals #NeverPayFull #DealGroup #FYP #Viral #MoneyHacks #Deals #CouponLife",
    "ancestor_disappointment": "#AncestorDisappointed #FullPrice #MoneyMeme #FinanceTok #CouponLife #FYP #Viral #Funny #SaveMoney #Deals",
}

# Meme content formats — rotated for meme TikTok + Twitter posts
MEME_FORMATS = [
    {
        "name": "two_types",
        "meme_style": "dark",
        "pexels_query": "person shopping comparison contrast lifestyle",
        "setup":    "there are two types of people in this economy",
        "type_a":   "Type A: pays $400 for headphones at checkout",
        "type_b":   "Type B: joins a free Telegram group, gets them for $58",
        "punchline": "both exist. only one is built different.",
        "cta":      "which one are you. link in bio.",
    },
    {
        "name": "skill_issue",
        "meme_style": "bright",
        "pexels_query": "person frustrated shocked phone online",
        "setup":    "paying full price in 2025",
        "reaction": "bro that's a skill issue",
        "detail":   "there's literally a free group that sends you deals every morning",
        "cta":      "no subscription. no catch. just deals. link in bio.",
    },
    {
        "name": "amazon_knows",
        "meme_style": "dark",
        "pexels_query": "person surprised laptop shopping excited",
        "setup":    "Amazon when they see me about to pay full price",
        "reaction": "\U0001f923 \U0001f4b0 \U0001f37e",
        "detail":   "me after someone showed me the coupon glitch",
        "punchline": "Amazon: \U0001f628",
        "cta":      "we find these every day. free group. link in bio.",
    },
    {
        "name": "horror_story",
        "meme_style": "horror",
        "pexels_query": "person shocked phone screen horror",
        "setup":    "a horror story in 3 parts",
        "part1":    "Part 1: You buy something at full price.",
        "part2":    "Part 2: Same item. 60% off. Two days later.",
        "part3":    "Part 3: You didn't know about our free deal group.",
        "cta":      "don't let this happen to you. link in bio.",
    },
    {
        "name": "pov_found_group",
        "meme_style": "dark",
        "pexels_query": "friends phone texting happy excited",
        "setup":    "POV: your friend adds you to a free Telegram deal group",
        "beat1":    "Day 1: cute, free coffee",
        "beat2":    "Day 7: free headphones",
        "beat3":    "Day 30: you haven't paid full price for anything",
        "cta":      "link in bio. it's free. obviously.",
    },
    {
        "name": "ancestor_disappointment",
        "meme_style": "bright",
        "pexels_query": "person embarrassed regret shopping mistake",
        "setup":    "my ancestors watching me pay $14 for a candle",
        "reaction": "\U0001f624\U0001f624\U0001f624",
        "detail":   "bro it was $3 with coupon stacking",
        "punchline": "they did not survive for this",
        "cta":      "join the group. honor your lineage. link in bio.",
    },
]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TikTokPosterError(Exception):
    """Base exception for TikTok poster errors."""
    pass


# ---------------------------------------------------------------------------
# Helper: generate voiceover audio bytes with gTTS + pydub speed change
# ---------------------------------------------------------------------------

async def _build_voiceover(script_text: str) -> bytes:
    """
    Synthesise natural-sounding speech using Microsoft Edge TTS (edge-tts).

    Uses en-US-ChristopherNeural — a natural conversational male voice.
    Rate is set to +20% for TikTok energy without sounding rushed.

    Args:
        script_text: Full narration text.

    Returns:
        MP3 audio bytes.
    """
    try:
        import edge_tts
    except ImportError as exc:
        raise TikTokPosterError(
            "edge-tts is required: pip install edge-tts"
        ) from exc

    tmp_path = tempfile.mktemp(suffix=".mp3")
    try:
        communicate = edge_tts.Communicate(
            script_text,
            voice="en-US-ChristopherNeural",
            rate="+20%",
            pitch="+0Hz",
        )
        await communicate.save(tmp_path)
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Helper: get smart Pexels search keywords from product title
# ---------------------------------------------------------------------------

def _get_pexels_keywords(title: str, category: str) -> str:
    """Return relevant Pexels search terms based on product title keywords."""
    title_lower = title.lower()
    for keyword, search_terms in PRODUCT_TO_PEXELS.items():
        if keyword in title_lower:
            return search_terms
    # Fall back to category, stripping generic retail words
    cat = category.lower().replace("electronics", "technology").replace("home_improvement", "tools")
    return cat or "shopping lifestyle"


# ---------------------------------------------------------------------------
# Helper: download product image to temp file
# ---------------------------------------------------------------------------

async def _fetch_product_image(image_url: str) -> Optional[str]:
    """
    Download product image from URL and save to a temp file.

    Returns:
        Absolute path to the temp image file, or None on failure.
    """
    if not image_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(image_url, follow_redirects=True)
            resp.raise_for_status()
            suffix = ".jpg" if "jpeg" in resp.headers.get("content-type", "") else ".png"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(resp.content)
            tmp.close()
            return tmp.name
    except Exception as exc:
        logger.warning("Could not download product image: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Helper: fetch Pexels video clips
# ---------------------------------------------------------------------------

async def _fetch_pexels_clips(category: str, pexels_api_key: str, count: int = 3) -> List[str]:
    """
    Search Pexels for stock videos matching *category* and download them.

    Args:
        category: Product category keyword for search.
        pexels_api_key: Pexels API key.
        count: Number of clips to download.

    Returns:
        List of local file paths for downloaded clips.
    """
    if not pexels_api_key:
        raise TikTokPosterError(
            "PEXELS_API_KEY is not set. Add it to your .env file: PEXELS_API_KEY=<your_key>"
        )

    headers = {"Authorization": pexels_api_key}
    params = {"query": category or "shopping", "per_page": count}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(PEXELS_VIDEO_SEARCH_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

    videos = data.get("videos", [])
    if not videos:
        raise TikTokPosterError(
            f"Pexels returned no videos for query '{category}'. "
            "Try a broader category name."
        )

    clip_paths: List[str] = []
    tmp_dir = tempfile.mkdtemp(prefix="tiktok_clips_")

    async with httpx.AsyncClient(timeout=120.0) as client:
        for idx, video in enumerate(videos[:count]):
            # Pick the first SD or HD video file available
            video_files = video.get("video_files", [])
            # Prefer portrait orientation (height > width) for TikTok
            portrait_files = [
                vf for vf in video_files
                if (vf.get("height", 0) or 0) >= (vf.get("width", 1) or 1)
            ]
            target_file = portrait_files[0] if portrait_files else (video_files[0] if video_files else None)

            if not target_file:
                logger.warning("Pexels video %d has no downloadable files, skipping.", idx)
                continue

            video_url = target_file.get("link")
            if not video_url:
                continue

            clip_path = os.path.join(tmp_dir, f"clip_{idx}.mp4")
            logger.info("Downloading Pexels clip %d from %s", idx + 1, video_url[:60])

            async with client.stream("GET", video_url) as stream:
                stream.raise_for_status()
                with open(clip_path, "wb") as f:
                    async for chunk in stream.aiter_bytes(chunk_size=65536):
                        f.write(chunk)

            clip_paths.append(clip_path)

    if not clip_paths:
        raise TikTokPosterError("No Pexels clips could be downloaded.")

    return clip_paths


# ---------------------------------------------------------------------------
# Helper: assemble video with MoviePy
# ---------------------------------------------------------------------------

def _assemble_video(
    clip_paths: List[str],
    audio_bytes: bytes,
    script_sections: Dict[str, str],
    output_path: str,
    product_image_path: Optional[str] = None,
) -> str:
    """
    Concatenate stock clips, add voiceover, and burn-in section captions.

    Args:
        clip_paths: Paths to downloaded Pexels clips.
        audio_bytes: WAV audio bytes for the voiceover.
        script_sections: Dict with keys hook/problem/reveal/proof/cta and text values.
        output_path: Destination .mp4 path.

    Returns:
        Absolute path to the rendered .mp4 file.
    """
    try:
        # moviepy 2.x uses top-level imports; 1.x used moviepy.editor
        try:
            from moviepy import (
                AudioFileClip,
                CompositeVideoClip,
                ImageClip,
                TextClip,
                VideoFileClip,
                concatenate_videoclips,
            )
        except ImportError:
            from moviepy.editor import (
                AudioFileClip,
                CompositeVideoClip,
                ImageClip,
                TextClip,
                VideoFileClip,
                concatenate_videoclips,
            )
    except ImportError as exc:
        raise TikTokPosterError(
            "moviepy is required for video assembly. "
            "Install it with: pip install moviepy"
        ) from exc

    # Write audio bytes to a temp file so MoviePy can load it (MP3 via imageio_ffmpeg)
    tmp_audio_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_audio_file.write(audio_bytes)
    tmp_audio_file.close()

    try:
        audio_clip = AudioFileClip(tmp_audio_file.name)
        target_duration = audio_clip.duration  # match video length to voiceover

        # --- Build stock footage segment ---
        raw_clips = []
        for path in clip_paths:
            try:
                vc = VideoFileClip(path).without_audio()
                raw_clips.append(vc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load clip %s: %s", path, exc)

        if not raw_clips:
            raise TikTokPosterError("No valid video clips could be loaded by MoviePy.")

        # Concatenate, then trim/loop to voiceover length
        base_video = concatenate_videoclips(raw_clips, method="compose")

        if base_video.duration < target_duration:
            # Loop the concatenated clip to fill the duration
            loops_needed = int(target_duration / base_video.duration) + 1
            base_video = concatenate_videoclips([base_video] * loops_needed, method="compose")

        # moviepy 2.x renamed subclip → subclipped, resize → resized
        base_video = base_video.subclipped(0, target_duration)

        # Resize to 9:16 portrait for TikTok
        base_video = base_video.resized(height=TARGET_HEIGHT)

        # --- Find a valid system font for captions ---
        font_path = None
        for fp in WINDOWS_FONTS:
            if os.path.exists(fp):
                font_path = fp
                break

        # --- Burn-in captions ---
        caption_clips = []
        section_order = ["hook", "problem", "reveal", "proof", "cta"]

        if font_path:
            for i, section_key in enumerate(section_order):
                text = script_sections.get(section_key, "")
                if not text:
                    continue

                start_t = SECTION_TIMES[section_key]
                if i + 1 < len(section_order):
                    end_t = SECTION_TIMES[section_order[i + 1]]
                else:
                    end_t = target_duration
                end_t = min(end_t, target_duration)
                clip_dur = end_t - start_t
                if clip_dur <= 0:
                    continue

                # Wrap text at 32 chars for large readable captions
                words = text.split()
                lines, line = [], ""
                for word in words:
                    if len(line) + len(word) + 1 <= 32:
                        line = (line + " " + word).strip()
                    else:
                        if line:
                            lines.append(line)
                        line = word
                if line:
                    lines.append(line)
                wrapped_text = "\n".join(lines)

                try:
                    txt_clip = (
                        TextClip(
                            text=wrapped_text,
                            font=font_path,
                            font_size=72,
                            color="white",
                            stroke_color="black",
                            stroke_width=4,
                            method="caption",
                            size=(TARGET_WIDTH - 120, None),
                            text_align="center",
                        )
                        .with_start(start_t)
                        .with_duration(clip_dur)
                        .with_position(("center", 0.65), relative=True)
                    )
                    caption_clips.append(txt_clip)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("TextClip failed for '%s': %s", section_key, exc)
        else:
            logger.warning("No system font found — captions skipped")

        # --- Product image overlay (bottom-left corner) ---
        image_clips = []
        if product_image_path and os.path.exists(product_image_path):
            try:
                img_clip = (
                    ImageClip(product_image_path)
                    .with_duration(target_duration)
                    .resized(width=320)
                    .with_position((40, TARGET_HEIGHT - 420))
                )
                image_clips.append(img_clip)
                logger.info("Product image overlay added")
            except Exception as exc:
                logger.warning("Could not add product image overlay: %s", exc)

        # --- Composite everything ---
        layers = [base_video] + image_clips + caption_clips
        final_video = CompositeVideoClip(layers)

        # Attach voiceover (moviepy 2.x: set_audio → with_audio)
        final_video = final_video.with_audio(audio_clip)

        # Render
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_video.write_videofile(
            output_path,
            fps=30,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )

        logger.info("TikTok video rendered to: %s", output_path)
        return os.path.abspath(output_path)

    finally:
        try:
            os.unlink(tmp_audio_file.name)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Main module functions
# ---------------------------------------------------------------------------


async def generate_script(deal_data: dict) -> Dict[str, str]:
    """
    Generate a 15-20 second viral TikTok voiceover script.

    Rotates through VIRAL_FORMATS — content is deals/savings lifestyle focused,
    not a product ad. Each format has a proven organic hook style.
    Timing is compressed to ~20s so it rides naturally on trending music.

    Returns:
        Dict with keys: hook, problem, reveal, proof, cta, full_script, format_name, pexels_query
    """
    anthropic_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    # Pick a random viral format
    fmt = random.choice(VIRAL_FORMATS)

    title = deal_data.get("title", "this product")
    current_price = deal_data.get("current_price") or deal_data.get("price", "")
    original_price = deal_data.get("original_price", "")
    discount_pct = deal_data.get("discount_percent") or deal_data.get("discount_pct", "")
    category = deal_data.get("category", "")

    try:
        savings = f"${float(original_price) - float(current_price):.0f}" if original_price and current_price else "big money"
    except (TypeError, ValueError):
        savings = "big money"

    hook_line = fmt["hook_template"].format(savings=savings, discount=discount_pct, category=category)

    system_prompt = (
        "You are a viral TikTok creator who posts about deals, coupons, and saving money. "
        "Your content feels 100% organic — like a real person sharing a discovery, "
        "NOT a sponsored ad or product review. "
        "You talk like a relatable friend texting excited about a deal they found. "
        "Use short, punchy sentences — 5-10 words max per line. "
        "Vary rhythm: sometimes fast staccato, sometimes a longer payoff line. "
        "NEVER read out model numbers, SKUs, or full product names. "
        "Refer to products naturally: 'these headphones', 'this kitchen gadget', 'it'. "
        "The total script must be spoken in under 20 seconds — keep it tight. "
        "Return ONLY a JSON object with exactly these five keys: "
        "hook, problem, reveal, proof, cta. "
        "hook = 1-2 punchy sentences (pattern interrupt). "
        "problem = 1-2 sentences (relatable struggle with prices / missing deals). "
        "reveal = 2-3 sentences (the deal details — price, savings, why it's wild). "
        "proof = 1-2 sentences (social proof or urgency — reviews, selling fast). "
        "cta = 1 sentence directing viewers to the Telegram channel for daily deals. "
        "No markdown, no code fences, no extra keys."
    )

    user_prompt = (
        f"Write a viral TikTok voiceover using this format: '{fmt['name']}'\n\n"
        f"Theme: {fmt['theme']}\n"
        f"Opening hook line to build from: '{hook_line}'\n\n"
        f"Deal details to weave in naturally:\n"
        f"- Product category: {category or 'consumer goods'}\n"
        f"- Was: ${original_price} → Now: ${current_price}\n"
        f"- Savings: {savings} ({discount_pct}% off)\n\n"
        "Make it feel real, organic, and like something that would stop someone mid-scroll. "
        "Do NOT sound like an ad. Sound like a person who just found this and HAS to share it.\n\n"
        "Return ONLY a JSON object with keys: hook, problem, reveal, proof, cta."
    )

    if not anthropic_key:
        logger.warning("ANTHROPIC_AUTH_TOKEN not set; using fallback script.")
        return _fallback_script(fmt, hook_line, savings, discount_pct, current_price)

    headers = {
        "x-api-key": anthropic_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 400,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, base_url=base_url) as client:
            response = await client.post("/v1/messages", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        raw_text = data["content"][0]["text"].strip()
    except Exception as exc:
        logger.warning("AI script generation failed (%s); using fallback.", exc)
        return _fallback_script(fmt, hook_line, savings, discount_pct, current_price)

    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    raw_text = raw_text.strip()

    try:
        sections = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Non-JSON response; using fallback script.")
        return _fallback_script(fmt, hook_line, savings, discount_pct, current_price)

    for key in ("hook", "problem", "reveal", "proof", "cta"):
        if key not in sections:
            sections[key] = ""

    sections["full_script"] = " ".join(
        sections[k] for k in ("hook", "problem", "reveal", "proof", "cta") if sections[k]
    )
    sections["format_name"] = fmt["name"]
    sections["pexels_query"] = fmt["pexels_query"]
    return _inject_cta_enhancements(sections)


def _inject_cta_enhancements(sections: Dict[str, str]) -> Dict[str, str]:
    """
    Append TELEGRAM_INVITE_LINK and a random COMMENT_BAIT line to the CTA section.

    Called as a post-processing step after both AI and fallback script generation.
    """
    telegram_link = os.environ.get("TELEGRAM_INVITE_LINK", "")
    comment_bait = random.choice(COMMENT_BAIT)

    cta = sections.get("cta", "")
    if telegram_link and telegram_link not in cta:
        cta = f"{cta} Free. 47K+ members. 10+ deals daily. {telegram_link}"
    cta = f"{cta} {comment_bait}"
    sections["cta"] = cta.strip()

    # Rebuild full_script with updated CTA
    sections["full_script"] = " ".join(
        sections[k] for k in ("hook", "problem", "reveal", "proof", "cta")
        if sections.get(k)
    )
    return sections


def _fallback_script(
    fmt: Dict[str, str],
    hook_line: str,
    savings: str,
    discount_pct: Any,
    current_price: Any,
) -> Dict[str, str]:
    """Organic fallback scripts — one per viral format."""
    fallbacks: Dict[str, Dict[str, str]] = {
        "pov_savings": {
            "hook":    hook_line,
            "problem": "We're all out here paying way too much for stuff.",
            "reveal":  f"Just found this marked down {discount_pct}% — down to ${current_price}. That's actually insane.",
            "proof":   "Thousands of people already grabbed it. Won't last.",
            "cta":     "Link in bio — join our Telegram for daily deals like this.",
        },
        "stop_paying": {
            "hook":    hook_line,
            "problem": "Full price is a choice. And it's the wrong one.",
            "reveal":  f"This one is {discount_pct}% off right now. Save {savings}.",
            "proof":   "This deal won't be there tomorrow. I'm not joking.",
            "cta":     "Follow for more — link in bio to our free deal channel.",
        },
        "secret_deal": {
            "hook":    hook_line,
            "problem": "Most people scroll right past deals like this.",
            "reveal":  f"{discount_pct}% off. Save {savings}. Right now.",
            "proof":   "Selling fast. Grab it before it goes back to full price.",
            "cta":     "Join our Telegram — we post these daily. Link in bio.",
        },
        "countdown": {
            "hook":    hook_line,
            "problem": "These prices won't last — they never do.",
            "reveal":  f"Up to {discount_pct}% off. Saving people {savings} today.",
            "proof":   "Already trending. Don't sleep on it.",
            "cta":     "Free daily deals in our Telegram — link in bio.",
        },
    }
    sections = fallbacks.get(fmt["name"], fallbacks["pov_savings"])
    sections = dict(sections)
    sections["full_script"] = " ".join(
        sections[k] for k in ("hook", "problem", "reveal", "proof", "cta") if sections.get(k)
    )
    sections["format_name"] = fmt["name"]
    sections["pexels_query"] = fmt["pexels_query"]
    return _inject_cta_enhancements(sections)


# ---------------------------------------------------------------------------
# Meme content generation
# ---------------------------------------------------------------------------


def _meme_format_to_scenes(fmt: Dict[str, Any]) -> Dict[str, str]:
    """Normalize any MEME_FORMAT dict to the 4 generic scene keys."""
    name = fmt["name"]
    if name == "two_types":
        return {
            "scene1": fmt["setup"],
            "scene2": fmt["type_a"] + "\n" + fmt["type_b"],
            "scene3": fmt["punchline"],
            "cta": fmt["cta"],
        }
    elif name == "skill_issue":
        return {
            "scene1": fmt["setup"],
            "scene2": fmt["reaction"],
            "scene3": fmt["detail"],
            "cta": fmt["cta"],
        }
    elif name == "amazon_knows":
        return {
            "scene1": fmt["setup"],
            "scene2": fmt["reaction"],
            "scene3": (fmt["detail"] + "\n" + fmt.get("punchline", "")).strip(),
            "cta": fmt["cta"],
        }
    elif name == "horror_story":
        return {
            "scene1": fmt["setup"],
            "scene2": fmt["part1"] + "\n" + fmt["part2"],
            "scene3": fmt["part3"],
            "cta": fmt["cta"],
        }
    elif name == "pov_found_group":
        return {
            "scene1": fmt["setup"],
            "scene2": fmt["beat1"] + "\n" + fmt["beat2"],
            "scene3": fmt["beat3"],
            "cta": fmt["cta"],
        }
    elif name == "ancestor_disappointment":
        return {
            "scene1": fmt["setup"],
            "scene2": fmt["reaction"] + "\n" + fmt["detail"],
            "scene3": fmt["punchline"],
            "cta": fmt["cta"],
        }
    else:
        return {
            "scene1": fmt.get("setup", ""),
            "scene2": fmt.get("detail", fmt.get("reaction", "")),
            "scene3": fmt.get("punchline", ""),
            "cta": fmt.get("cta", "link in bio."),
        }


def _fallback_meme_script(fmt: Dict[str, Any], scenes: Dict[str, str], telegram_link: str) -> Dict[str, str]:
    """Return template scenes with TELEGRAM_INVITE_LINK injected into cta."""
    result = dict(scenes)
    if telegram_link and telegram_link not in result.get("cta", ""):
        result["cta"] = result.get("cta", "link in bio.").replace(
            "link in bio.", f"free group: {telegram_link}"
        )
    result["full_script"] = " ".join(
        result.get(k, "") for k in ("scene1", "scene2", "scene3", "cta") if result.get(k)
    )
    result["format_name"] = fmt["name"]
    result["pexels_query"] = fmt.get("pexels_query", "lifestyle shopping funny")
    result["meme_style"] = fmt.get("meme_style", "dark")
    return result


async def generate_meme_script() -> Dict[str, str]:
    """
    Generate a 15-second viral TikTok meme voiceover script.

    Picks a random MEME_FORMAT, calls Anthropic to riff on the template,
    falls back to template text if AI is unavailable.

    Returns:
        Dict with keys: scene1, scene2, scene3, cta, full_script,
        format_name, pexels_query, meme_style.
    """
    anthropic_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    telegram_link = os.environ.get("TELEGRAM_INVITE_LINK", "t.me/coupondealssteals")

    fmt = random.choice(MEME_FORMATS)
    scenes = _meme_format_to_scenes(fmt)

    system_prompt = (
        "You are a viral TikTok meme creator in the personal finance / deals space. "
        "Your content is edgy, relatable, and spreads because it's genuinely funny. "
        "You roast people who pay full price — in a fun, not mean way. "
        "Think TikTok humor: short punchy sentences, lowercase is fine, emoji used sparingly. "
        "Never sound corporate. Sound like a friend texting you memes at 2am. "
        "Return ONLY a JSON object with keys: scene1, scene2, scene3, cta. "
        "Each value is 1-3 short punchy lines (30 words max each). "
        "The cta must mention the free Telegram group and say 'link in bio'. "
        "No markdown, no code fences, no extra keys."
    )

    user_prompt = (
        f"Riff on this meme format for a TikTok about our free deals group:\n\n"
        f"Format: '{fmt['name']}'\n"
        f"Template scenes:\n"
        f"  Scene 1: {scenes['scene1']}\n"
        f"  Scene 2: {scenes['scene2']}\n"
        f"  Scene 3: {scenes['scene3']}\n"
        f"  CTA: {scenes['cta']}\n\n"
        f"Make it funnier and more relatable, same structure. "
        f"CTA must mention the free Telegram group: {telegram_link}\n"
        f"Return ONLY JSON with keys: scene1, scene2, scene3, cta."
    )

    if not anthropic_key:
        logger.warning("ANTHROPIC_AUTH_TOKEN not set; using fallback meme script.")
        return _fallback_meme_script(fmt, scenes, telegram_link)

    headers = {
        "x-api-key": anthropic_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 300,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, base_url=base_url) as client:
            response = await client.post("/v1/messages", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        raw_text = data["content"][0]["text"].strip()
    except Exception as exc:
        logger.warning("AI meme script generation failed (%s); using fallback.", exc)
        return _fallback_meme_script(fmt, scenes, telegram_link)

    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    raw_text = raw_text.strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Non-JSON meme response; using fallback.")
        return _fallback_meme_script(fmt, scenes, telegram_link)

    for key in ("scene1", "scene2", "scene3", "cta"):
        if key not in result:
            result[key] = scenes.get(key, "")

    result["full_script"] = " ".join(
        result[k] for k in ("scene1", "scene2", "scene3", "cta") if result.get(k)
    )
    result["format_name"] = fmt["name"]
    result["pexels_query"] = fmt.get("pexels_query", "lifestyle shopping")
    result["meme_style"] = fmt.get("meme_style", "dark")
    return result


async def generate_meme_and_notify() -> Dict[str, Any]:
    """
    Generate a meme TikTok video (no deal data needed) and notify operator.

    Steps:
        1. generate_meme_script() — pick random meme format, AI riff or fallback.
        2. _build_voiceover()     — edge-tts narration.
        3. _fetch_pexels_clips()  — lifestyle footage matching the meme vibe.
        4. _assemble_video()      — MoviePy with captions.
        5. manual_upload_helper() — Telegram DM with upload instructions.
        6. cross_poster           — teaser tweet to Twitter.

    Returns:
        Dict with success (bool), video_path (str | None), format (str), error (str | None).
    """
    pexels_api_key = os.environ.get("PEXELS_API_KEY", "")

    try:
        script_sections = await generate_meme_script()
        logger.info("Meme script generated: format=%s", script_sections.get("format_name"))
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "video_path": None, "error": f"Meme script failed: {exc}"}

    try:
        audio_bytes = await _build_voiceover(script_sections.get("full_script", ""))
        logger.info("Meme voiceover generated via edge-tts")
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "video_path": None, "error": f"Voiceover failed: {exc}"}

    pexels_query = script_sections.get("pexels_query", "person laughing shopping lifestyle")
    try:
        clip_paths = await _fetch_pexels_clips(pexels_query, pexels_api_key, count=3)
        logger.info("Downloaded %d Pexels clips for meme", len(clip_paths))
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "video_path": None, "error": f"Pexels failed: {exc}"}

    # Map meme scenes to standard section keys (_assemble_video uses hook/problem/reveal/proof/cta)
    meme_sections: Dict[str, str] = {
        "hook":    script_sections.get("scene1", ""),
        "problem": script_sections.get("scene2", ""),
        "reveal":  script_sections.get("scene3", ""),
        "proof":   "",
        "cta":     script_sections.get("cta", ""),
    }

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fmt_name = script_sections.get("format_name", "meme")
    output_path = os.path.join(OUTPUT_DIR, f"meme_{timestamp}_{fmt_name}.mp4")

    try:
        final_video_path = _assemble_video(clip_paths, audio_bytes, meme_sections, output_path)
        logger.info("Meme video assembled: %s", final_video_path)
    except Exception as exc:  # noqa: BLE001
        return {"success": False, "video_path": None, "error": f"Assembly failed: {exc}"}

    caption = (
        f"[MEME] {fmt_name}\n"
        f"Style: {script_sections.get('meme_style', 'dark')}\n\n"
        + script_sections.get("full_script", "")[:300]
    )
    meme_deal_data = {
        "title": f"Meme: {fmt_name}",
        "viral_potential": 8,
        "format_name": fmt_name,
    }
    await manual_upload_helper(meme_deal_data, final_video_path, caption)

    try:
        from deal_sniper_ai.posting_engine.cross_poster import post_tiktok_teaser_tweet
        await post_tiktok_teaser_tweet(
            None, final_video_path,
            meme_format=fmt_name,
            meme_teaser=script_sections.get("scene1", ""),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Meme cross-post teaser failed (non-fatal): %s", exc)

    return {
        "success": True,
        "video_path": final_video_path,
        "format": fmt_name,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Manual upload helper
# ---------------------------------------------------------------------------


async def manual_upload_helper(deal_data: dict, video_path: str, caption: str) -> bool:
    """
    Send a Telegram notification with manual TikTok upload instructions and log
    the event to the daily_digest_logs table.

    Args:
        deal_data: Deal candidate data dictionary.
        video_path: Absolute path to the rendered .mp4 file.
        caption: TikTok caption text (from copy_generator or similar).

    Returns:
        True if the Telegram notification was sent successfully.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    # TikTok upload notifications go to the owner's DM, not the public group
    channel_id = os.environ.get("TELEGRAM_OWNER_ID") or os.environ.get("TELEGRAM_CHANNEL_ID", "")

    title = deal_data.get("title", "Deal")
    format_name = deal_data.get("format_name", "pov_savings")
    hashtag_set = HASHTAG_SETS.get(format_name, "#Deals #DealAlert #Savings #FYP #TikTokDeals #AmazonDeals #MoneyHacks #FrugalLiving #CouponLife #ForYou")
    pinned_comment = random.choice(COMMENT_BAIT)

    telegram_channel = os.environ.get("TELEGRAM_CHANNEL_ID", "our Telegram channel")
    message = (
        "\U0001f3ac TikTok Video Ready!\n\n"
        f"Title: {title}\n"
        f"Format: {format_name}\n"
        f"Video: {video_path}\n\n"
        "Caption to copy:\n"
        f"{caption}\n\n"
        "Hashtags to add:\n"
        f"{hashtag_set}\n\n"
        "Upload checklist:\n"
        "1. Open TikTok app \u2192 + button\n"
        "2. Select video from path above\n"
        "3. Paste caption (CTA directs to Telegram for daily deals)\n"
        "4. Add hashtags from above\n"
        "5. Post, then immediately pin this comment:\n"
        f"   \u2192 {pinned_comment}\n"
        "   \u26a0 Pin this comment first for algorithm boost\n"
        "6. Add link to Telegram channel in bio if not already set\n"
        f"7. \U0001f3b5 Sound tip: {random.choice(TRENDING_SOUND_TIPS)}\n"
        "8. Monitor first 30 min for engagement\n\n"
        f"Telegram channel ID: {telegram_channel}"
    )

    telegram_ok = False
    if bot_token and channel_id:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": channel_id,
                "text": message,
                "parse_mode": "HTML",
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, data=payload)
                response.raise_for_status()
                result = response.json()
                if result.get("ok"):
                    logger.info("Telegram notification sent for TikTok video: %s", title[:50])
                    telegram_ok = True
                else:
                    logger.error("Telegram API error: %s", result.get("description"))
        except httpx.HTTPError as exc:
            logger.error("HTTP error sending Telegram notification: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error sending Telegram notification: %s", exc)
    else:
        logger.warning(
            "TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID not set; skipping Telegram notification."
        )

    # Log to daily_digest_logs table
    try:
        from deal_sniper_ai.database.supabase_client import get_supabase_client

        client_db = get_supabase_client()
        await client_db.insert(
            "daily_digest_logs",
            {
                "type": "tiktok_ready",
                "deal_title": title,
                "video_path": video_path,
                "notified_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        logger.info("Logged tiktok_ready event to daily_digest_logs.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not log to daily_digest_logs: %s", exc)

    return telegram_ok


async def generate_and_notify(
    deal_data: dict,
    posted_deal_id: str,
    caption: str,
) -> Dict[str, Any]:
    """
    Main entry point: generate a TikTok video for a high-viral-potential deal
    and notify the operator via Telegram for manual upload.

    Steps:
        1. Guard: skip if viral_potential < 8.
        2. Generate AI script via Anthropic API.
        3. Synthesise gTTS voiceover with random speed variant.
        4. Download 3 Pexels stock clips matching the product category.
        5. Assemble .mp4 with MoviePy (captions + voiceover).
        6. Save video path to posted_deals.tiktok_video_path via Supabase.
        7. Send Telegram notification with upload instructions.

    Args:
        deal_data: Deal candidate data dict (must include 'viral_potential').
        posted_deal_id: UUID string of the row in posted_deals to update.
        caption: Caption text to include in the Telegram notification.

    Returns:
        Dict with keys: success (bool), video_path (str or None), error (str or None).
    """
    viral_potential = deal_data.get("viral_potential", 0)
    try:
        viral_potential = float(viral_potential)
    except (TypeError, ValueError):
        viral_potential = 0.0

    if viral_potential < 8:
        logger.info(
            "Deal '%s' has viral_potential %.1f < 8; skipping TikTok video generation.",
            deal_data.get("title", "?"),
            viral_potential,
        )
        return {
            "success": False,
            "video_path": None,
            "error": f"viral_potential {viral_potential} is below threshold of 8",
        }

    pexels_api_key = os.environ.get("PEXELS_API_KEY", "")
    title = deal_data.get("title", "deal")
    category = deal_data.get("category", "shopping")
    image_url = deal_data.get("image_url", "")

    # --- Step 1: Generate script (AI rewrites name to natural speech) ---
    try:
        script_sections = await generate_script(deal_data)
        logger.info("Script generated for '%s'", title[:50])
    except Exception as exc:  # noqa: BLE001
        logger.error("Script generation failed: %s", exc)
        return {"success": False, "video_path": None, "error": f"Script generation failed: {exc}"}

    # Inject cliffhanger ending for ultra-viral deals (viral_potential >= 9)
    if viral_potential >= 9:
        cliffhanger = random.choice(CLIFFHANGER_ENDINGS)
        script_sections["cta"] = f"{script_sections.get('cta', '')} {cliffhanger}".strip()
        script_sections["full_script"] = " ".join(
            script_sections[k] for k in ("hook", "problem", "reveal", "proof", "cta")
            if script_sections.get(k)
        )
        logger.info("Cliffhanger injected for viral_potential=%.1f", viral_potential)

    # --- Step 2: Generate voiceover with edge-tts (natural human voice) ---
    try:
        audio_bytes = await _build_voiceover(script_sections.get("full_script", ""))
        logger.info("Voiceover generated via edge-tts")
    except TikTokPosterError as exc:
        logger.error("Voiceover generation failed: %s", exc)
        return {"success": False, "video_path": None, "error": f"Voiceover failed: {exc}"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected voiceover error: %s", exc)
        return {"success": False, "video_path": None, "error": f"Voiceover error: {exc}"}

    # --- Step 3: Download Pexels clips using viral format's lifestyle query ---
    # Prefer the format's pexels_query (lifestyle/organic) over product-specific keywords
    pexels_query = script_sections.get("pexels_query") or _get_pexels_keywords(title, category)
    try:
        clip_paths = await _fetch_pexels_clips(pexels_query, pexels_api_key, count=3)
        logger.info("Downloaded %d Pexels clips for '%s'", len(clip_paths), pexels_query)
    except TikTokPosterError as exc:
        logger.error("Pexels clip download failed: %s", exc)
        return {"success": False, "video_path": None, "error": f"Pexels download failed: {exc}"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected Pexels error: %s", exc)
        return {"success": False, "video_path": None, "error": f"Pexels error: {exc}"}

    # --- Step 3b: Download product image for overlay ---
    product_image_path = await _fetch_product_image(image_url)
    if product_image_path:
        logger.info("Product image downloaded for overlay")

    # --- Step 4: Assemble video with captions + product image ---
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() else "_" for c in title)[:40]
    output_filename = f"tiktok_{timestamp}_{safe_title}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    try:
        final_video_path = _assemble_video(
            clip_paths, audio_bytes, script_sections, output_path,
            product_image_path=product_image_path,
        )
        logger.info("Video assembled: %s", final_video_path)
    except TikTokPosterError as exc:
        logger.error("Video assembly failed: %s", exc)
        return {"success": False, "video_path": None, "error": f"Video assembly failed: {exc}"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected video assembly error: %s", exc)
        return {"success": False, "video_path": None, "error": f"Assembly error: {exc}"}
    finally:
        # Clean up temp product image
        if product_image_path:
            try:
                os.unlink(product_image_path)
            except OSError:
                pass

    # --- Step 5: Save video path to Supabase ---
    try:
        from deal_sniper_ai.database.supabase_client import get_supabase_client

        db_client = get_supabase_client()
        await db_client.update(
            "posted_deals",
            filters={"id": posted_deal_id},
            updates={"tiktok_video_path": final_video_path},
        )
        logger.info("Saved tiktok_video_path to posted_deals row %s", posted_deal_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not update posted_deals.tiktok_video_path: %s", exc)
        # Non-fatal; continue to notification

    # --- Step 6: Send Telegram notification (include format_name for hashtag sets) ---
    deal_data_with_format = {**deal_data, "format_name": script_sections.get("format_name", "pov_savings")}
    await manual_upload_helper(deal_data_with_format, final_video_path, caption)

    # --- Step 7: Cross-post teaser to Twitter ---
    try:
        from deal_sniper_ai.posting_engine.cross_poster import post_tiktok_teaser_tweet
        await post_tiktok_teaser_tweet(deal_data, final_video_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cross-post teaser tweet failed (non-fatal): %s", exc)

    return {"success": True, "video_path": final_video_path, "error": None}


# ---------------------------------------------------------------------------
# Legacy class-based interface (preserved for backward compatibility with
# existing code that instantiates TikTokPoster(config))
# ---------------------------------------------------------------------------


class TikTokPoster:
    """
    TikTok poster: video generation pipeline + manual upload helper.

    For high-viral-potential deals (viral_potential >= 8) this class:
      - Generates an AI voiceover script via Anthropic
      - Synthesises gTTS audio with pydub speed variation
      - Downloads Pexels stock clips
      - Assembles an .mp4 with MoviePy captions
      - Saves the path to Supabase posted_deals
      - Sends a Telegram notification for manual upload

    For lower-scoring deals, it falls back to the legacy JSON export behaviour.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.platform_config = config.get("posting", {}).get("tiktok", {})
        self.enabled = self.platform_config.get("enabled", False)
        self.min_score = self.platform_config.get("min_score", 0)

        from ..formatter import PlatformFormatter
        self.formatter = PlatformFormatter(config)

    async def validate_config(self) -> bool:
        return self.enabled

    async def post(self, deal_data: Dict[str, Any], formatted_message: str) -> Dict[str, Any]:
        """
        Post deal: if viral_potential >= 8, generate video and notify.
        Otherwise export deal data to a JSON file for manual posting.
        """
        if not self.enabled:
            raise TikTokPosterError("TikTok posting is disabled")

        viral_potential = deal_data.get("viral_potential", 0)
        try:
            viral_potential = float(viral_potential)
        except (TypeError, ValueError):
            viral_potential = 0.0

        if viral_potential >= 8:
            posted_deal_id = str(deal_data.get("posted_deal_id", deal_data.get("id", "")))
            caption = formatted_message
            result = await generate_and_notify(deal_data, posted_deal_id, caption)
            result["platform"] = "tiktok"
            return result

        # Fallback: legacy JSON export for lower-scoring deals
        return await self._legacy_export(deal_data, formatted_message)

    # ------------------------------------------------------------------
    # Legacy export helpers (unchanged from original placeholder)
    # ------------------------------------------------------------------

    async def _legacy_export(self, deal_data: Dict[str, Any], formatted_message: str) -> Dict[str, Any]:
        import json as _json
        from pathlib import Path

        export_dir = Path(self.config.get("platform", {}).get("data_dir", "./data")) / "tiktok_exports"
        export_dir.mkdir(parents=True, exist_ok=True)

        export_data = self._create_export_data(deal_data, formatted_message)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() else "_" for c in export_data["title"])[:50]
        filename = f"tiktok_export_{timestamp}_{safe_title}.json"
        filepath = export_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            _json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info("Exported deal for TikTok manual posting (legacy): %s", export_data["title"][:50])
        return {
            "success": True,
            "platform": "tiktok",
            "export_file": str(filepath),
            "message": "Deal exported for manual TikTok posting",
        }

    def _create_export_data(self, deal_data: Dict[str, Any], formatted_message: str) -> Dict[str, Any]:
        hashtags = self._generate_hashtags(deal_data)
        tiktok_description = self._create_tiktok_description(deal_data, formatted_message, hashtags)
        return {
            "title": deal_data.get("title", "Deal Alert"),
            "description": tiktok_description,
            "hashtags": hashtags,
            "affiliate_link": deal_data.get("affiliate_link", ""),
            "image_url": deal_data.get("image_url", ""),
            "current_price": str(deal_data.get("current_price", "")),
            "original_price": str(deal_data.get("original_price", "")),
            "discount_percent": str(deal_data.get("discount_percent", "")),
            "score": str(deal_data.get("score", "")),
            "retailer": deal_data.get("retailer", ""),
            "category": deal_data.get("category", ""),
            "export_time": datetime.now(timezone.utc).isoformat(),
        }

    def _create_tiktok_description(
        self,
        deal_data: Dict[str, Any],
        formatted_message: str,
        hashtags: List[str],
    ) -> str:
        title = deal_data.get("title", "Deal Alert")
        current_price = deal_data.get("current_price", "")
        original_price = deal_data.get("original_price", "")
        discount = deal_data.get("discount_percent", 0)

        try:
            discount_f = float(discount)
        except (TypeError, ValueError):
            discount_f = 0.0

        lines: List[str] = []
        if discount_f >= 50:
            lines.append("MAJOR PRICE DROP ALERT!")
        elif discount_f >= 30:
            lines.append("HOT DEAL ALERT!")
        else:
            lines.append("DEAL ALERT!")

        short_title = title[:50] + "..." if len(title) > 50 else title
        lines.append(short_title)

        if current_price and original_price:
            lines.append(f"NOW: ${current_price}")
            lines.append(f"WAS: ${original_price}")
            if discount:
                lines.append(f"SAVE: {discount}%")

        retailer = deal_data.get("retailer", "").title()
        if retailer:
            lines.append(retailer)

        lines.append("Link in bio!")
        if hashtags:
            lines.append(" ".join(hashtags))

        description = "\n".join(lines)
        if len(description) > 150:
            description = description[:147] + "..."
        return description

    def _generate_hashtags(self, deal_data: Dict[str, Any]) -> List[str]:
        hashtags = ["#DealAlert", "#Deals"]
        retailer = deal_data.get("retailer", "").lower()
        if retailer == "amazon":
            hashtags.extend(["#AmazonFinds", "#AmazonDeals"])
        elif retailer == "walmart":
            hashtags.extend(["#WalmartFinds", "#WalmartDeals"])
        elif retailer == "target":
            hashtags.extend(["#TargetFinds", "#TargetDeals"])
        elif retailer == "home_depot":
            hashtags.extend(["#HomeDepot", "#DIYDeals"])

        category = deal_data.get("category", "").lower()
        if "electronics" in category:
            hashtags.extend(["#TechTok", "#GadgetTok"])
        elif "home" in category:
            hashtags.extend(["#HomeTok", "#HomeDecor"])
        elif "kitchen" in category:
            hashtags.extend(["#KitchenTok", "#Cooking"])
        elif "gaming" in category:
            hashtags.extend(["#GamingTok", "#Gamer"])

        discount = deal_data.get("discount_percent", 0)
        try:
            discount = float(discount)
        except (ValueError, TypeError):
            discount = 0.0

        if discount >= 50:
            hashtags.extend(["#Steal", "#BudgetFriendly"])
        elif discount >= 30:
            hashtags.extend(["#GoodDeal", "#Savings"])

        hashtags.extend(["#FYP", "#ForYouPage", "#TikTokMadeMeBuyIt"])
        return hashtags[:10]

    async def close(self):
        """No persistent resources to release."""
        pass


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


async def create_tiktok_poster(config: Optional[Dict[str, Any]] = None) -> TikTokPoster:
    """
    Create a TikTokPoster instance.

    Args:
        config: Optional configuration dict; loads from get_config() if omitted.

    Returns:
        TikTokPoster instance.
    """
    from deal_sniper_ai.config.config import get_config
    config = config or get_config()
    return TikTokPoster(config)
