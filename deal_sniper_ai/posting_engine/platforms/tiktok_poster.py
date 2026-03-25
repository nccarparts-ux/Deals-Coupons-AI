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

# Script section timing in seconds
SECTION_TIMES = {
    "hook": 0,
    "problem": 3,
    "reveal": 8,
    "proof": 20,
    "cta": 35,
}

# Pexels video search endpoint
PEXELS_VIDEO_SEARCH_URL = "https://api.pexels.com/videos/search"

# TikTok aspect ratio target
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TikTokPosterError(Exception):
    """Base exception for TikTok poster errors."""
    pass


# ---------------------------------------------------------------------------
# Helper: generate voiceover audio bytes with gTTS + pydub speed change
# ---------------------------------------------------------------------------

def _build_voiceover(script_text: str, speed: float = 1.0) -> bytes:
    """
    Synthesise speech from *script_text* and return raw WAV bytes.

    Args:
        script_text: Full narration text.
        speed: Playback speed multiplier (1.0, 1.05, or 1.1).

    Returns:
        WAV audio bytes.
    """
    try:
        from gtts import gTTS
        from pydub import AudioSegment
    except ImportError as exc:
        raise TikTokPosterError(
            "gTTS and pydub are required for voiceover generation. "
            "Install them with: pip install gTTS pydub"
        ) from exc

    # Generate base MP3 with gTTS
    tts = gTTS(text=script_text, lang="en", slow=False)
    mp3_buffer = io.BytesIO()
    tts.write_to_fp(mp3_buffer)
    mp3_buffer.seek(0)

    # Load into pydub and apply speed change
    audio = AudioSegment.from_file(mp3_buffer, format="mp3")

    if speed != 1.0:
        # pydub speed change: stretch frame rate then resample back
        new_frame_rate = int(audio.frame_rate * speed)
        audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_frame_rate})
        audio = audio.set_frame_rate(44100)

    # Export as WAV into bytes
    wav_buffer = io.BytesIO()
    audio.export(wav_buffer, format="wav")
    wav_buffer.seek(0)
    return wav_buffer.read()


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
        from moviepy.editor import (
            AudioFileClip,
            CompositeVideoClip,
            TextClip,
            VideoFileClip,
            concatenate_videoclips,
        )
    except ImportError as exc:
        raise TikTokPosterError(
            "moviepy is required for video assembly. "
            "Install it with: pip install moviepy"
        ) from exc

    # Write audio bytes to a temp file so MoviePy can load it
    tmp_audio_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
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

        base_video = base_video.subclip(0, target_duration)

        # Resize to 9:16 portrait for TikTok
        base_video = base_video.resize(height=TARGET_HEIGHT)

        # --- Burn-in captions ---
        caption_clips = []
        section_order = ["hook", "problem", "reveal", "proof", "cta"]

        for i, section_key in enumerate(section_order):
            text = script_sections.get(section_key, "")
            if not text:
                continue

            start_t = SECTION_TIMES[section_key]
            # End time is next section start, or target_duration for last section
            if i + 1 < len(section_order):
                end_t = SECTION_TIMES[section_order[i + 1]]
            else:
                end_t = target_duration

            end_t = min(end_t, target_duration)
            clip_dur = end_t - start_t
            if clip_dur <= 0:
                continue

            # Wrap long text
            max_chars = 40
            wrapped_lines = []
            words = text.split()
            line = ""
            for word in words:
                if len(line) + len(word) + 1 <= max_chars:
                    line = (line + " " + word).strip()
                else:
                    if line:
                        wrapped_lines.append(line)
                    line = word
            if line:
                wrapped_lines.append(line)
            wrapped_text = "\n".join(wrapped_lines)

            try:
                txt_clip = (
                    TextClip(
                        wrapped_text,
                        fontsize=60,
                        color="white",
                        stroke_color="black",
                        stroke_width=3,
                        font="Arial-Bold",
                        method="caption",
                        size=(TARGET_WIDTH - 80, None),
                        align="center",
                    )
                    .set_start(start_t)
                    .set_duration(clip_dur)
                    .set_position(("center", "center"))
                )
                caption_clips.append(txt_clip)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not create TextClip for section '%s': %s", section_key, exc)

        # Composite captions over base video
        if caption_clips:
            final_video = CompositeVideoClip([base_video] + caption_clips)
        else:
            final_video = base_video

        # Attach voiceover
        final_video = final_video.set_audio(audio_clip)

        # Render
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_video.write_videofile(
            output_path,
            fps=30,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=tmp_audio_file.name + "_temp.m4a",
            remove_temp=True,
            verbose=False,
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
    Generate a 30-45 second TikTok script via the Anthropic API.

    The script is structured as five sections:
        hook      (0-3s)
        problem   (3-8s)
        reveal    (8-20s)
        proof     (20-35s)
        cta       (35-45s)

    Args:
        deal_data: Deal candidate data dictionary.

    Returns:
        Dict with keys: hook, problem, reveal, proof, cta (and optionally full_script).
    """
    anthropic_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6")
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    title = deal_data.get("title", "this product")
    current_price = deal_data.get("current_price") or deal_data.get("price", "?")
    original_price = deal_data.get("original_price", "?")
    discount_pct = deal_data.get("discount_percent") or deal_data.get("discount_pct", "?")
    rating = deal_data.get("rating", None)
    review_count = deal_data.get("review_count", None)

    rating_str = f"{rating}" if rating else "[rating]"
    review_str = f"{int(review_count):,}" if review_count else "[review_count]"

    system_prompt = (
        "You are a viral TikTok content writer specialising in deal alerts. "
        "Write punchy, conversational voiceover scripts that feel authentic and urgent. "
        "Always return a JSON object with exactly these five keys: "
        "hook, problem, reveal, proof, cta. "
        "Each value is a single short paragraph of spoken narration for that section. "
        "The cta section must always direct viewers to join the Telegram channel for "
        "daily deal alerts — use phrases like 'Join our free Telegram for daily deals', "
        "'Link in bio to our Telegram deal channel', or 'Follow us on Telegram so you "
        "never miss a deal like this'. "
        "Do not include any markdown, code fences, or extra keys."
    )

    user_prompt = (
        f"Write a 30-45 second TikTok voiceover script for this deal:\n\n"
        f"Product: {title}\n"
        f"Original price: ${original_price}\n"
        f"Current price: ${current_price}\n"
        f"Discount: {discount_pct}% off\n"
        f"Rating: {rating_str} stars\n"
        f"Reviews: {review_str}\n\n"
        "Follow this exact structure:\n"
        f"- hook (0-3s): Start with 'Wait, {title} is HOW cheap right now??'\n"
        f"- problem (3-8s): 'Been wanting this but couldn't justify ${original_price}'\n"
        f"- reveal (8-20s): 'Just dropped to ${current_price} — that\\'s {discount_pct}% off'\n"
        f"- proof (20-35s): '{rating_str} stars, {review_str} reviews' plus social proof\n"
        "- cta (35-45s): 'Link in bio, won\\'t last long'\n\n"
        "Return ONLY a JSON object with keys: hook, problem, reveal, proof, cta."
    )

    if not anthropic_key:
        logger.warning("ANTHROPIC_AUTH_TOKEN not set; using template script fallback.")
        return _fallback_script(title, current_price, original_price, discount_pct, rating_str, review_str)

    headers = {
        "x-api-key": anthropic_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 512,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }

    async with httpx.AsyncClient(timeout=30.0, base_url=base_url) as client:
        response = await client.post("/v1/messages", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    raw_text = data["content"][0]["text"].strip()

    # Strip markdown code fences if the model wrapped the JSON
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
    raw_text = raw_text.strip()

    try:
        sections = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Anthropic returned non-JSON script; using fallback template.")
        return _fallback_script(title, current_price, original_price, discount_pct, rating_str, review_str)

    # Ensure all required keys exist
    for key in ("hook", "problem", "reveal", "proof", "cta"):
        if key not in sections:
            sections[key] = ""

    sections["full_script"] = " ".join(
        sections[k] for k in ("hook", "problem", "reveal", "proof", "cta") if sections[k]
    )
    return sections


def _fallback_script(
    title: str,
    current_price: Any,
    original_price: Any,
    discount_pct: Any,
    rating_str: str,
    review_str: str,
) -> Dict[str, str]:
    """Return a template-based script when the Anthropic API is unavailable."""
    sections = {
        "hook": f"Wait, {title} is HOW cheap right now??",
        "problem": f"I've been wanting this for ages but just couldn't justify paying ${original_price}.",
        "reveal": f"It just dropped to ${current_price} — that's {discount_pct}% off! I couldn't believe it.",
        "proof": f"{rating_str} stars with {review_str} reviews. People absolutely love this thing.",
        "cta": "Join our free Telegram for daily deals like this — link in bio. Don't wait, this won't last long!",
    }
    sections["full_script"] = " ".join(sections[k] for k in ("hook", "problem", "reveal", "proof", "cta"))
    return sections


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
    channel_id = os.environ.get("TELEGRAM_CHANNEL_ID", "")

    title = deal_data.get("title", "Deal")

    telegram_channel = os.environ.get("TELEGRAM_CHANNEL_ID", "our Telegram channel")
    message = (
        "\U0001f3ac TikTok Video Ready!\n\n"
        f"Title: {title}\n"
        f"Video: {video_path}\n\n"
        "Caption to copy:\n"
        f"{caption}\n\n"
        "Upload checklist:\n"
        "1. Open TikTok app \u2192 + button\n"
        "2. Select video from path above\n"
        "3. Paste caption (CTA directs to Telegram for daily deals)\n"
        "4. Add link to Telegram channel in bio if not already set\n"
        "5. Add trending sounds/hashtags\n"
        "6. Post & monitor first 30 min for engagement\n\n"
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

    # --- Step 1: Generate script ---
    try:
        script_sections = await generate_script(deal_data)
        logger.info("Script generated for '%s'", title[:50])
    except Exception as exc:  # noqa: BLE001
        logger.error("Script generation failed: %s", exc)
        return {"success": False, "video_path": None, "error": f"Script generation failed: {exc}"}

    # --- Step 2: Generate voiceover ---
    speed = random.choice([1.0, 1.05, 1.1])
    try:
        audio_bytes = _build_voiceover(script_sections.get("full_script", ""), speed=speed)
        logger.info("Voiceover generated (speed=%.2f)", speed)
    except TikTokPosterError as exc:
        logger.error("Voiceover generation failed: %s", exc)
        return {"success": False, "video_path": None, "error": f"Voiceover failed: {exc}"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected voiceover error: %s", exc)
        return {"success": False, "video_path": None, "error": f"Voiceover error: {exc}"}

    # --- Step 3: Download Pexels clips ---
    try:
        clip_paths = await _fetch_pexels_clips(category, pexels_api_key, count=3)
        logger.info("Downloaded %d Pexels clips for category '%s'", len(clip_paths), category)
    except TikTokPosterError as exc:
        logger.error("Pexels clip download failed: %s", exc)
        return {"success": False, "video_path": None, "error": f"Pexels download failed: {exc}"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected Pexels error: %s", exc)
        return {"success": False, "video_path": None, "error": f"Pexels error: {exc}"}

    # --- Step 4: Assemble video ---
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() else "_" for c in title)[:40]
    output_filename = f"tiktok_{timestamp}_{safe_title}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    try:
        final_video_path = _assemble_video(clip_paths, audio_bytes, script_sections, output_path)
        logger.info("Video assembled: %s", final_video_path)
    except TikTokPosterError as exc:
        logger.error("Video assembly failed: %s", exc)
        return {"success": False, "video_path": None, "error": f"Video assembly failed: {exc}"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected video assembly error: %s", exc)
        return {"success": False, "video_path": None, "error": f"Assembly error: {exc}"}

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

    # --- Step 6: Send Telegram notification ---
    await manual_upload_helper(deal_data, final_video_path, caption)

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
