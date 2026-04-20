"""
Twitter/X API Poster for Deal Sniper AI Platform.

Posting uses OAuth 1.0a (User Context) which is required for POST /2/tweets.
Bearer token (App-Only) is used only for read operations (search/recent).

Required env vars:
    TWITTER_API_KEY            - Consumer Key (from dev portal → Keys and Tokens)
    TWITTER_API_SECRET         - Consumer Secret
    TWITTER_ACCESS_TOKEN       - User Access Token
    TWITTER_ACCESS_TOKEN_SECRET - User Access Token Secret
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import random
import time
import urllib.parse
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

import httpx

from ..formatter import PlatformFormatter
from deal_sniper_ai.database.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Meme tweet pool — edgy, relatable, high retweet / share potential
# Rotated 1x per day alongside deal posts. No product mention.
# ---------------------------------------------------------------------------

MEME_TWEETS = [
    # Overspending shame
    "paying full price in this economy is genuinely a personality disorder",
    "me clicking 'place order' without a coupon code: a horror story",
    "corporations when I pay full price: \U0001f911  me: \U0001f60a  me 10 min later: \U0001f62d",
    "my bank statement is just a list of things I could've gotten cheaper",
    # Deal hacker superiority
    "there are two types of people: those who use coupon codes and those who are wrong",
    "i have never once paid full price and I'm built different",
    "normal people: *buys something*\ndeal people: *buys same thing for 60% less, with cashback*",
    "being bad at finding deals is a skill issue at this point",
    # Platform-specific edgy angles
    "Amazon really said 'original price: $400' and thought we wouldn't notice it's been $400 for 11 years",
    "retailers pricing things at $399.99 thinking we don't know about the glitch that makes it $12",
    "POV: you find out your friend paid full price. you say nothing. you pity them silently.",
    "the audacity of full price existing when coupon stacking is a thing",
    # FOMO + CTA (inject telegram link at post time)
    "47,000 people woke up today and didn't pay full price for anything. that's the group. link in bio.",
    "the deal group in my bio has been finding free items for months and you're still paying full price why",
    "imagine paying full price when there's a free group that texts you deals every single day \U0001f480",
]

# Viral tweet format templates — rotated alongside deal posts
TWITTER_VIRAL_FORMATS = [
    {
        "name": "poll",
        "text": "Are you still paying full price in {year}? \U0001f914\n\nOur free group sends 10+ deals daily. No subscription. Just savings. Link in bio.",
    },
    {
        "name": "shock_stat",
        "text": "Quick stat: people in our free deal group have saved over $500 this month on everyday items.\n\nNo catch. No subscription.\n\nLink in bio \U0001f447",
    },
    {
        "name": "thread_teaser",
        "text": "\U0001f9f5 5 things on Amazon right now that feel illegal to buy at full price:\n\n(thread)\n\n1/ They've all been 40-70% off in our group this week. Follow for the list.",
    },
    {
        "name": "engagement_hook",
        "text": "Tell me your last full-price purchase and I'll find it cheaper. I'll wait.",
    },
]


class TwitterPosterError(Exception):
    """Base exception for Twitter posting errors."""
    pass


class TwitterRateLimitError(TwitterPosterError):
    """Raised when the daily Twitter post limit (17 posts/day on free tier) is reached."""
    pass


class TwitterPoster:
    """Twitter/X API posting implementation."""

    def __init__(self, config: Dict[str, Any], supabase_client=None):
        """
        Initialize Twitter poster.

        Args:
            config: Configuration dictionary
            supabase_client: Optional SupabaseClient instance (defaults to shared singleton)
        """
        self.config = config
        self.platform_config = config.get('posting', {}).get('twitter', {})

        # Platform settings — env vars take priority over config.yaml
        self.enabled = self.platform_config.get('enabled', False)
        self.min_score = self.platform_config.get('min_score', 0)
        self.api_key = (
            os.environ.get('TWITTER_API_KEY') or
            self.platform_config.get('api_key', '')
        )
        self.api_secret = (
            os.environ.get('TWITTER_API_SECRET') or
            self.platform_config.get('api_secret', '')
        )
        self.access_token = (
            os.environ.get('TWITTER_ACCESS_TOKEN') or
            self.platform_config.get('access_token', '')
        )
        self.access_secret = (
            os.environ.get('TWITTER_ACCESS_SECRET') or
            self.platform_config.get('access_secret', '')
        )

        # API endpoints
        self.api_base = 'https://api.twitter.com/2'
        self.oauth_base = 'https://api.twitter.com/oauth2'

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

        # Initialize formatter
        self.formatter = PlatformFormatter(config)

        # Bearer token — for read-only API calls (search/recent) only
        # Posting uses OAuth 1.0a, not bearer token
        self.bearer_token = None

        # Supabase client for rate tracking and affiliate link lookup
        self._supabase_client = supabase_client

    @property
    def supabase(self):
        """Lazy-load the shared Supabase client singleton."""
        if self._supabase_client is None:
            self._supabase_client = get_supabase_client()
        return self._supabase_client

    async def validate_config(self) -> bool:
        """Validate Twitter configuration."""
        if not self.enabled:
            return False

        required_keys = ['api_key', 'api_secret', 'access_token', 'access_secret']
        for key in required_keys:
            if not getattr(self, key):
                logger.warning(f"Twitter {key} not configured")
                return False

        # Check if we have OAuth 2.0 credentials
        # In a real implementation, this would validate the tokens
        return True

    async def post(self, deal_data: Dict[str, Any], formatted_message: str) -> Dict[str, Any]:
        """
        Post deal to Twitter/X.

        Args:
            deal_data: Deal data dictionary
            formatted_message: Formatted message

        Returns:
            Dictionary with posting results
        """
        if not self.enabled:
            raise TwitterPosterError("Twitter posting is disabled")

        if not await self.validate_config():
            raise TwitterPosterError("Invalid Twitter configuration")

        # Apply random jitter delay (5–23 minutes) before posting.
        # Note: celery_app.py beat_schedule does NOT configure per-task jitter,
        # so jitter is handled here at the poster level.
        await self._jitter_delay()

        # Enforce free-tier daily rate limit (17 posts/day)
        daily_count = await self._get_daily_count()
        if daily_count >= 17:
            raise TwitterRateLimitError(
                f"Twitter daily rate limit reached ({daily_count}/17 posts today). "
                "Try again tomorrow."
            )

        # Route high-viral-potential deals to a 3-tweet thread
        viral_potential = deal_data.get('viral_potential')
        if viral_potential is not None:
            try:
                viral_potential = float(viral_potential)
            except (ValueError, TypeError):
                viral_potential = 0
            if viral_potential >= 9:
                result = await self.post_thread(deal_data, formatted_message)
                if result.get('success'):
                    await self._increment_daily_count(daily_count)
                return result

        # Standard single-tweet path
        hashtags = self._generate_hashtags(deal_data)
        telegram_link = os.environ.get("TELEGRAM_INVITE_LINK", "")
        full_message = f"{formatted_message} {hashtags}".strip()
        if telegram_link and telegram_link not in full_message:
            full_message = f"{full_message}\n{telegram_link}"
        if len(full_message) > 280:
            full_message = full_message[:277] + "..."

        response = await self._post_tweet_v2(full_message)
        if response:
            tweet_id = response.get("data", {}).get("id")
            await self._increment_daily_count(daily_count)
            logger.info("Deal tweet posted (id=%s)", tweet_id)
            return {
                "success": True, "platform": "twitter",
                "tweet_id": tweet_id, "formatted_message": full_message,
            }

        # API unavailable — save for manual posting + send Telegram DM
        title = deal_data.get("title", "Deal")
        file_path = await self._save_for_manual_post(
            full_message, tweet_type="deal",
            hashtags=hashtags,
            extra_info=f"Deal: {title}",
        )
        return {
            "success": False, "platform": "twitter",
            "error": "api_unavailable", "manual_file": file_path,
            "formatted_message": full_message,
        }

    # ── Rate limit tracking ──────────────────────────────────────────────────

    async def _get_daily_count(self) -> int:
        """
        Read today's Twitter post count from the performance_metrics table.

        Uses metric_type='twitter_daily_count', metric_name=today's ISO date,
        and platform='twitter'.

        Returns:
            Current post count for today (0 if no record exists yet).
        """
        today = date.today().isoformat()
        try:
            rows = await self.supabase.select(
                'performance_metrics',
                filters={
                    'metric_type': 'twitter_daily_count',
                    'metric_name': today,
                    'platform': 'twitter',
                }
            )
            if rows:
                return int(rows[0].get('metric_value', 0))
        except Exception as e:
            logger.warning(f"Could not read Twitter daily count from Supabase: {e}")
        return 0

    async def _increment_daily_count(self, current_count: int) -> None:
        """
        Upsert today's Twitter post count in the performance_metrics table.

        Args:
            current_count: The count value before this post (will be incremented by 1).
        """
        today = date.today().isoformat()
        new_count = current_count + 1
        try:
            # Attempt to update an existing row first
            updated = await self.supabase.update(
                'performance_metrics',
                filters={
                    'metric_type': 'twitter_daily_count',
                    'metric_name': today,
                    'platform': 'twitter',
                },
                updates={'metric_value': new_count}
            )
            if not updated:
                # No existing row — insert a new one
                await self.supabase.insert(
                    'performance_metrics',
                    {
                        'metric_type': 'twitter_daily_count',
                        'metric_name': today,
                        'platform': 'twitter',
                        'metric_value': new_count,
                    }
                )
            logger.debug(f"Twitter daily count updated to {new_count} for {today}")
        except Exception as e:
            logger.warning(f"Could not update Twitter daily count in Supabase: {e}")

    # ── Jitter delay ─────────────────────────────────────────────────────────

    async def _jitter_delay(self) -> None:
        """
        Sleep for a random duration between 5 and 23 minutes before posting.

        This prevents predictable posting patterns that could trigger Twitter's
        automated detection systems.  The Celery beat_schedule in celery_app.py
        does NOT configure per-task jitter, so this is handled here.
        """
        delay_seconds = random.randint(5, 23) * 60
        logger.info(f"Twitter jitter delay: sleeping for {delay_seconds // 60} minutes")
        await asyncio.sleep(delay_seconds)

    # ── Viral thread posting ─────────────────────────────────────────────────

    async def post_thread(
        self, deal_data: Dict[str, Any], formatted_message: str
    ) -> Dict[str, Any]:
        """
        Post a 3-tweet thread for high-viral-potential deals (viral_potential >= 9).

        Tweet 1: Hook with emoji and savings amount.
        Tweet 2: Product details and why it's worth it.
        Tweet 3: Affiliate link from the affiliate_links table + CTA.

        Args:
            deal_data: Deal data dictionary (must include viral_potential >= 9).
            formatted_message: Pre-formatted deal message used as a base.

        Returns:
            Dictionary with posting results, including thread_tweet_ids list.
        """
        # ── Build tweet texts ────────────────────────────────────────────────
        title = deal_data.get('title', 'Amazing Deal')
        retailer = deal_data.get('retailer', '')
        original_price = deal_data.get('original_price', 0)
        current_price = deal_data.get('current_price', 0)
        discount_percent = deal_data.get('discount_percent', 0)
        category = deal_data.get('category', '')

        try:
            savings = float(original_price) - float(current_price)
        except (ValueError, TypeError):
            savings = 0.0

        try:
            discount_percent = float(discount_percent)
        except (ValueError, TypeError):
            discount_percent = 0.0

        # Tweet 1 — Hook
        savings_str = f"${savings:.2f}" if savings > 0 else f"{discount_percent:.0f}% off"
        tweet1 = (
            f"DEAL ALERT! {title} is now {savings_str} cheaper!\n\n"
            f"This won't last long. Keep reading for details + link. "
            f"{self._generate_hashtags(deal_data)}"
        )
        if len(tweet1) > 280:
            tweet1 = tweet1[:277] + "..."

        # Tweet 2 — Product details
        retailer_label = f" at {retailer.title()}" if retailer else ""
        category_label = f" ({category})" if category else ""
        price_line = (
            f"Was: ${float(original_price):.2f}  =>  Now: ${float(current_price):.2f}"
            if original_price and current_price
            else formatted_message
        )
        tweet2 = (
            f"{title}{retailer_label}{category_label}\n\n"
            f"{price_line}\n\n"
            f"Why it's worth it: {discount_percent:.0f}% discount — "
            f"one of the best prices we've tracked for this item."
        )
        if len(tweet2) > 280:
            tweet2 = tweet2[:277] + "..."

        # Tweet 3 — Affiliate link + CTA
        affiliate_url = await self._lookup_affiliate_url(deal_data)
        if not affiliate_url:
            affiliate_url = deal_data.get('url', deal_data.get('product_url', ''))
        tweet3 = (
            f"Get the deal here: {affiliate_url}\n\n"
            f"Tap the link now before it sells out! "
            f"Follow for more daily deal alerts."
        )
        if len(tweet3) > 280:
            tweet3 = tweet3[:277] + "..."

        # ── Post the thread via Twitter API v2 ───────────────────────────────
        logger.info(f"Posting 3-tweet thread for viral deal: {title}")

        tweet_ids: List[str] = []
        reply_to_id: Optional[str] = None

        api_working = True
        for i, tweet_text in enumerate([tweet1, tweet2, tweet3], start=1):
            response = await self._post_tweet_v2(tweet_text, reply_to_id=reply_to_id)
            if response:
                tweet_id = response.get('data', {}).get('id')
                if tweet_id:
                    tweet_ids.append(tweet_id)
                    reply_to_id = tweet_id
                    logger.info(f"Thread tweet {i}/3 posted (id={tweet_id})")
                else:
                    logger.warning(f"Thread tweet {i}/3: no tweet id in response")
            else:
                logger.warning(f"Thread tweet {i}/3 API failed — falling back to manual")
                api_working = False
                break

        if tweet_ids:
            return {
                'success': True, 'platform': 'twitter', 'thread': True,
                'thread_tweet_ids': tweet_ids,
                'tweet_texts': [tweet1, tweet2, tweet3],
                'affiliate_url': affiliate_url,
                'message': f"3-tweet thread posted for viral deal '{title}'"
            }

        # API unavailable — save all 3 tweets for manual posting + Telegram DM
        file_path = await self._save_for_manual_post(
            tweet1, tweet_type="thread",
            hashtags=self._generate_hashtags(deal_data),
            thread_tweets=[tweet1, tweet2, tweet3],
            extra_info=f"Deal: {title}",
        )
        return {
            'success': False, 'platform': 'twitter', 'thread': True,
            'error': 'api_unavailable', 'manual_file': file_path,
            'tweet_texts': [tweet1, tweet2, tweet3],
        }

    async def _lookup_affiliate_url(self, deal_data: Dict[str, Any]) -> Optional[str]:
        """
        Fetch the affiliate URL for a deal from the affiliate_links table.

        Args:
            deal_data: Deal data dictionary (uses 'product_id' or 'id' as lookup key).

        Returns:
            Affiliate URL string, or None if not found.
        """
        product_id = deal_data.get('product_id') or deal_data.get('id')
        if not product_id:
            return None
        try:
            rows = await self.supabase.select(
                'affiliate_links',
                columns='affiliate_url',
                filters={'product_id': product_id},
                limit=1
            )
            if rows:
                return rows[0].get('affiliate_url')
        except Exception as e:
            logger.warning(f"Could not fetch affiliate URL from Supabase: {e}")
        return None

    # ── Auto-reply to link requests ──────────────────────────────────────────

    async def reply_to_link_requests(
        self, tweet_id: str, affiliate_url: str
    ) -> Dict[str, Any]:
        """
        Search recent replies to tweet_id for "link?" or "where?" and reply
        with the affiliate_url to each matching comment.

        Uses Twitter API v2 recent search endpoint to find replies, then posts
        a reply tweet to each matching comment author.

        Args:
            tweet_id: The ID of the original tweet to monitor for replies.
            affiliate_url: The affiliate URL to share with commenters.

        Returns:
            Dictionary summarising how many replies were sent.
        """
        if not self.bearer_token:
            await self._get_bearer_token()

        replied_to: List[str] = []
        errors: List[str] = []

        try:
            headers = {
                'Authorization': f'Bearer {self.bearer_token}',
                'Content-Type': 'application/json',
            }

            # Search for recent replies to the given tweet
            search_query = f"conversation_id:{tweet_id} (link? OR where?)"
            params = {
                'query': search_query,
                'tweet.fields': 'author_id,conversation_id,in_reply_to_user_id',
                'expansions': 'author_id',
                'user.fields': 'username',
                'max_results': 10,
            }
            search_response = await self.client.get(
                f'{self.api_base}/tweets/search/recent',
                headers=headers,
                params=params,
            )
            search_response.raise_for_status()
            search_data = search_response.json()

            # Build a map of author_id -> username from expansions
            users_map: Dict[str, str] = {}
            for user in search_data.get('includes', {}).get('users', []):
                users_map[user['id']] = user.get('username', '')

            # Reply to each matching tweet
            for reply_tweet in search_data.get('data', []):
                reply_tweet_id = reply_tweet.get('id')
                author_id = reply_tweet.get('author_id', '')
                username = users_map.get(author_id, '')
                if not reply_tweet_id:
                    continue

                mention = f"@{username} " if username else ""
                reply_text = (
                    f"{mention}Here's the link: {affiliate_url}\n"
                    f"Grab it before the price goes back up!"
                )
                if len(reply_text) > 280:
                    reply_text = reply_text[:277] + "..."

                post_response = await self._post_tweet_v2(
                    reply_text, reply_to_id=reply_tweet_id
                )
                if post_response:
                    replied_to.append(reply_tweet_id)
                    logger.info(
                        f"Replied to link request in tweet {reply_tweet_id} "
                        f"(@{username})"
                    )
                else:
                    errors.append(reply_tweet_id)
                    logger.warning(
                        f"Failed to reply to tweet {reply_tweet_id} "
                        f"(@{username})"
                    )

        except httpx.HTTPError as e:
            status_code = (
                e.response.status_code if hasattr(e, 'response') else 'unknown'
            )
            logger.error(
                f"Twitter API error searching replies (status {status_code}): {e}"
            )
        except Exception as e:
            logger.error(f"Error in reply_to_link_requests: {e}")

        return {
            'tweet_id': tweet_id,
            'replied_count': len(replied_to),
            'replied_to_tweet_ids': replied_to,
            'error_count': len(errors),
        }

    def _generate_hashtags(self, deal_data: Dict[str, Any]) -> str:
        """Generate relevant hashtags for tweet."""
        hashtags = ['#DealAlert']

        # Add retailer hashtag
        retailer = deal_data.get('retailer', '').lower()
        if retailer:
            if retailer == 'amazon':
                hashtags.append('#AmazonDeals')
            elif retailer == 'walmart':
                hashtags.append('#WalmartDeals')
            elif retailer == 'target':
                hashtags.append('#TargetDeals')
            elif retailer == 'home_depot':
                hashtags.append('#HomeDepotDeals')
            else:
                hashtags.append(f'#{retailer.title()}Deals')

        # Add category hashtags
        category = deal_data.get('category', '').lower()
        if category:
            if 'electronics' in category:
                hashtags.extend(['#TechDeals', '#Gadgets'])
            elif 'home' in category:
                hashtags.append('#HomeDeals')
            elif 'kitchen' in category:
                hashtags.append('#KitchenDeals')
            elif 'gaming' in category:
                hashtags.extend(['#GamingDeals', '#VideoGames'])

        # Add discount hashtag
        discount = deal_data.get('discount_percent', 0)
        if isinstance(discount, str):
            try:
                discount = float(discount)
            except ValueError:
                discount = 0

        if discount >= 50:
            hashtags.append('#HotDeal')
        elif discount >= 25:
            hashtags.append('#GoodDeal')

        # Limit to 3 hashtags for Twitter
        hashtags = hashtags[:3]

        return ' '.join(hashtags)

    async def _get_bearer_token(self) -> Optional[str]:
        """
        Get OAuth 2.0 bearer token for Twitter API v2.

        Returns:
            Bearer token or None
        """
        # This is a simplified version - actual implementation would
        # use proper OAuth 2.0 client credentials flow
        try:
            # Encode credentials
            import base64
            credentials = f"{self.api_key}:{self.api_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            # Request bearer token
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
            }
            data = {'grant_type': 'client_credentials'}

            response = await self.client.post(
                f'{self.oauth_base}/token',
                headers=headers,
                data=data
            )
            response.raise_for_status()

            token_data = response.json()
            bearer_token = token_data.get('access_token')

            if bearer_token:
                self.bearer_token = bearer_token
                logger.info("Obtained Twitter bearer token")
                return bearer_token
            else:
                logger.error("Failed to obtain Twitter bearer token")
                return None

        except Exception as e:
            logger.error(f"Error getting Twitter bearer token: {e}")
            return None

    def _oauth1_header(self, method: str, url: str, body_params: Dict[str, str]) -> str:
        """
        Build an OAuth 1.0a Authorization header using HMAC-SHA1.

        OAuth 1.0a is required for POST /2/tweets (User Context).
        Bearer token (App-Only) is read-only and cannot post tweets.

        Args:
            method: HTTP method (e.g. 'POST')
            url: Full request URL (no query string)
            body_params: JSON body keys are NOT included in the OAuth signature
                         for application/json requests — pass {} here.

        Returns:
            Value for the Authorization header.
        """
        oauth_params = {
            'oauth_consumer_key': self.api_key,
            'oauth_nonce': uuid.uuid4().hex,
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': str(int(time.time())),
            'oauth_token': self.access_token,
            'oauth_version': '1.0',
        }

        # For application/json POST the body is NOT part of the signature base
        all_params = {**body_params, **oauth_params}
        sorted_pairs = sorted(all_params.items())
        param_string = '&'.join(
            f"{urllib.parse.quote(str(k), safe='')}={urllib.parse.quote(str(v), safe='')}"
            for k, v in sorted_pairs
        )

        base_string = '&'.join([
            method.upper(),
            urllib.parse.quote(url, safe=''),
            urllib.parse.quote(param_string, safe=''),
        ])

        signing_key = (
            urllib.parse.quote(self.api_secret, safe='') + '&' +
            urllib.parse.quote(self.access_secret, safe='')
        )

        raw_sig = hmac.new(
            signing_key.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha1,
        ).digest()
        signature = base64.b64encode(raw_sig).decode('utf-8')

        oauth_params['oauth_signature'] = signature
        header_value = 'OAuth ' + ', '.join(
            f'{urllib.parse.quote(str(k), safe="")}="{urllib.parse.quote(str(v), safe="")}"'
            for k, v in sorted(oauth_params.items())
        )
        return header_value

    async def _post_tweet_v2(
        self, text: str, reply_to_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Post tweet using Twitter API v2 with OAuth 1.0a (User Context).

        OAuth 1.0a is required for write operations. Bearer token is read-only.

        Args:
            text: Tweet text (max 280 chars)
            reply_to_id: Optional tweet ID to reply to (used for thread chaining).

        Returns:
            Tweet response dict or None on failure.
        """
        if not self.api_key or not self.api_secret:
            logger.error(
                "TWITTER_API_KEY and TWITTER_API_SECRET are required for posting. "
                "Add them to .env from developer.twitter.com → Keys and Tokens → Consumer Keys."
            )
            return None

        if not self.access_token or not self.access_secret:
            logger.error("TWITTER_ACCESS_TOKEN / TWITTER_ACCESS_TOKEN_SECRET not set.")
            return None

        try:
            url = f'{self.api_base}/tweets'
            body: Dict[str, Any] = {'text': text}
            if reply_to_id:
                body['reply'] = {'in_reply_to_tweet_id': reply_to_id}

            # OAuth 1.0a header — body params excluded for application/json
            auth_header = self._oauth1_header('POST', url, {})

            headers = {
                'Authorization': auth_header,
                'Content-Type': 'application/json',
            }

            response = await self.client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') else 'unknown'
            logger.error(f"Twitter API error posting tweet (status {status_code}): {e}")
            return None
        except Exception as e:
            logger.error(f"Error posting tweet: {e}")
            return None

    async def test_connection(self) -> bool:
        """
        Test Twitter API connection.

        Returns:
            True if connection successful
        """
        if not await self.validate_config():
            return False

        # Try to get bearer token
        bearer_token = await self._get_bearer_token()
        if not bearer_token:
            return False

        # Test API access
        try:
            headers = {'Authorization': f'Bearer {bearer_token}'}
            response = await self.client.get(
                f'{self.api_base}/tweets/20',  # Test with a public tweet ID
                headers=headers
            )

            if response.status_code == 200:
                logger.info("Twitter API connection test successful")
                return True
            else:
                logger.error(f"Twitter API test failed with status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Twitter connection test failed: {e}")
            return False

    # ── Meme tweet ────────────────────────────────────────────────────────────

    async def post_meme_tweet(self) -> Dict[str, Any]:
        """
        Post a random meme tweet from MEME_TWEETS (no deal data needed).

        Optionally enhances the selected template via Anthropic before posting.
        Injects TELEGRAM_INVITE_LINK if set.

        Returns:
            Dict with success (bool), tweet_id (str | None), text (str).
        """
        telegram_link = os.environ.get("TELEGRAM_INVITE_LINK", "")
        base_text = random.choice(MEME_TWEETS)

        # Inject telegram link for CTA tweets
        if "link in bio" in base_text and telegram_link:
            base_text = base_text.replace("link in bio.", telegram_link).replace(
                "link in bio", telegram_link
            )

        # Try AI enhancement
        enhanced = await self._enhance_meme_tweet(base_text)
        tweet_text = enhanced if enhanced else base_text
        if len(tweet_text) > 280:
            tweet_text = tweet_text[:277] + "..."

        daily_count = await self._get_daily_count()
        if daily_count >= 17:
            logger.warning("Twitter daily limit reached; skipping meme tweet.")
            return {"success": False, "tweet_id": None, "text": tweet_text,
                    "error": "daily_limit_reached"}

        response = await self._post_tweet_v2(tweet_text)
        if response:
            tweet_id = response.get("data", {}).get("id")
            await self._increment_daily_count(daily_count)
            logger.info("Meme tweet posted (id=%s): %s...", tweet_id, tweet_text[:60])
            return {"success": True, "tweet_id": tweet_id, "text": tweet_text}

        # API unavailable — save for manual posting + send Telegram DM
        file_path = await self._save_for_manual_post(tweet_text, tweet_type="meme")
        return {
            "success": False, "tweet_id": None, "text": tweet_text,
            "error": "api_unavailable", "manual_file": file_path,
        }

    async def post_viral_tweet(self) -> Dict[str, Any]:
        """
        Post a random viral-format tweet (poll, shock stat, thread teaser, engagement hook).

        Rotates through TWITTER_VIRAL_FORMATS. Injects TELEGRAM_INVITE_LINK where applicable.

        Returns:
            Dict with success (bool), tweet_id (str | None), format (str).
        """
        import datetime as _dt
        telegram_link = os.environ.get("TELEGRAM_INVITE_LINK", "")
        fmt = random.choice(TWITTER_VIRAL_FORMATS)
        text = fmt["text"].format(year=_dt.date.today().year)

        if telegram_link and "link in bio" in text:
            text = text.replace("Link in bio \U0001f447", telegram_link).replace(
                "link in bio", telegram_link
            )
        if len(text) > 280:
            text = text[:277] + "..."

        daily_count = await self._get_daily_count()
        if daily_count >= 17:
            logger.warning("Twitter daily limit reached; skipping viral tweet.")
            return {"success": False, "format": fmt["name"], "error": "daily_limit_reached"}

        response = await self._post_tweet_v2(text)
        if response:
            tweet_id = response.get("data", {}).get("id")
            await self._increment_daily_count(daily_count)
            logger.info("Viral tweet posted format=%s (id=%s)", fmt["name"], tweet_id)
            return {"success": True, "tweet_id": tweet_id, "format": fmt["name"], "text": text}

        # API unavailable — save for manual posting + send Telegram DM
        file_path = await self._save_for_manual_post(text, tweet_type=f"viral_{fmt['name']}")
        return {
            "success": False, "format": fmt["name"],
            "error": "api_unavailable", "manual_file": file_path,
        }

    async def _enhance_meme_tweet(self, base_text: str) -> Optional[str]:
        """
        Use Anthropic to riff on a meme tweet template. Falls back to None on failure.

        Args:
            base_text: The base meme tweet to enhance.

        Returns:
            Enhanced tweet text (max 270 chars), or None if AI unavailable.
        """
        anthropic_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6")
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

        if not anthropic_key:
            return None

        system = (
            "You write edgy, funny, viral personal finance tweets about deals and saving money. "
            "Keep the same core message but make it more shareable and relatable. "
            "Sound like a real person on Twitter — lowercase is fine, keep it under 250 chars. "
            "Return ONLY the tweet text. No quotes, no hashtags, no explanation."
        )
        user = f"Riff on this tweet to make it funnier/more shareable:\n\n{base_text}"

        try:
            headers = {
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": model,
                "max_tokens": 120,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            async with httpx.AsyncClient(timeout=20.0, base_url=base_url) as client:
                resp = await client.post("/v1/messages", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            text = data["content"][0]["text"].strip().strip('"\'')
            return text[:270] if text else None
        except Exception as exc:
            logger.debug("Meme tweet AI enhancement failed (non-fatal): %s", exc)
            return None

    # ── Twitter engagement bot ────────────────────────────────────────────────

    async def twitter_engagement_bot(self, max_replies: int = 10) -> Dict[str, Any]:
        """
        Search recent tweets with deal hashtags and reply with a helpful 1-liner
        + soft Telegram group mention (up to max_replies per run).

        Uses bearer token for search (read-only) and OAuth 1.0a for replies.
        Respects the daily free-tier post limit.

        Args:
            max_replies: Cap on replies per invocation (default 10).

        Returns:
            Dict with replied_count, skipped, errors.
        """
        if not self.bearer_token:
            await self._get_bearer_token()

        search_hashtags = ["#deals", "#coupons", "#frugal", "#AmazonDeals"]
        replied_count = 0
        skipped = 0
        errors: List[str] = []

        telegram_link = os.environ.get("TELEGRAM_INVITE_LINK", "")

        for hashtag in search_hashtags:
            if replied_count >= max_replies:
                break

            daily_count = await self._get_daily_count()
            if daily_count >= 17:
                logger.warning("engagement_bot: daily limit reached, stopping.")
                break

            try:
                headers = {
                    "Authorization": f"Bearer {self.bearer_token}",
                    "Content-Type": "application/json",
                }
                # Exclude retweets + replies + our own tweets to avoid loops
                query = f"{hashtag} -is:retweet -is:reply lang:en"
                params = {
                    "query": query,
                    "tweet.fields": "author_id,public_metrics",
                    "expansions": "author_id",
                    "user.fields": "username",
                    "max_results": 10,
                }
                search_resp = await self.client.get(
                    f"{self.api_base}/tweets/search/recent",
                    headers=headers,
                    params=params,
                )
                search_resp.raise_for_status()
                search_data = search_resp.json()

                users_map: Dict[str, str] = {
                    u["id"]: u.get("username", "")
                    for u in search_data.get("includes", {}).get("users", [])
                }

                for tweet in search_data.get("data", []):
                    if replied_count >= max_replies:
                        break
                    daily_count = await self._get_daily_count()
                    if daily_count >= 17:
                        break

                    tweet_id = tweet.get("id")
                    author_id = tweet.get("author_id", "")
                    username = users_map.get(author_id, "")
                    if not tweet_id or not username:
                        skipped += 1
                        continue

                    # Generate reply via Anthropic
                    reply_text = await self._generate_engagement_reply(
                        tweet.get("text", ""), username, telegram_link
                    )
                    if not reply_text:
                        skipped += 1
                        continue

                    resp = await self._post_tweet_v2(reply_text, reply_to_id=tweet_id)
                    if resp and resp.get("data", {}).get("id"):
                        replied_count += 1
                        await self._increment_daily_count(daily_count)
                        logger.info(
                            "engagement_bot: replied to @%s (tweet %s)", username, tweet_id
                        )
                        await asyncio.sleep(random.uniform(5, 15))  # be human
                    else:
                        errors.append(tweet_id)

            except Exception as exc:
                logger.warning("engagement_bot: error for %s: %s", hashtag, exc)
                errors.append(str(exc))

        return {
            "replied_count": replied_count,
            "skipped": skipped,
            "error_count": len(errors),
        }

    async def _generate_engagement_reply(
        self, tweet_text: str, username: str, telegram_link: str
    ) -> Optional[str]:
        """
        Use Anthropic to generate a helpful reply to a deal/coupon tweet.

        Returns a short (≤240 char) reply with a soft Telegram CTA, or None on failure.
        """
        anthropic_key = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
        model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-6")
        base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

        cta_line = f" (we have a free daily deal group: {telegram_link})" if telegram_link else ""

        if not anthropic_key:
            # Fallback: generic helpful replies
            fallbacks = [
                f"@{username} nice find! there's usually a coupon code too — check before checkout{cta_line}",
                f"@{username} this is legit, stacked ours with cashback too{cta_line}",
                f"@{username} always check if there's a subscribe-and-save price too, often cheaper{cta_line}",
            ]
            return random.choice(fallbacks)[:240]

        system = (
            "You reply to tweets about deals, coupons, and saving money. "
            "Be genuinely helpful — one sentence, conversational, friendly. "
            "Optionally mention the free deal group softly at the end. "
            "Sound like a real person, not a bot. Under 200 characters. "
            "Return ONLY the reply text."
        )
        user = (
            f"Reply helpfully to this tweet from @{username}:\n\n\"{tweet_text}\"\n\n"
            f"Soft CTA to add if relevant: {cta_line}"
        )

        try:
            headers = {
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": model,
                "max_tokens": 80,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            }
            async with httpx.AsyncClient(timeout=20.0, base_url=base_url) as client:
                resp = await client.post("/v1/messages", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
            text = data["content"][0]["text"].strip().strip('"\'')
            full = f"@{username} {text}"
            return full[:240] if full else None
        except Exception as exc:
            logger.debug("engagement_bot reply generation failed: %s", exc)
            return None

    # ── Manual post export + Telegram DM ─────────────────────────────────────

    async def _save_for_manual_post(
        self,
        tweet_text: str,
        tweet_type: str = "deal",
        hashtags: str = "",
        thread_tweets: Optional[List[str]] = None,
        extra_info: Optional[str] = None,
    ) -> str:
        """
        Save tweet content to a .txt file and send a Telegram DM to the owner.

        Used as a fallback whenever the Twitter API is unavailable/returns an error.
        The operator can open the file, copy the text, and paste it into Twitter manually.

        Args:
            tweet_text:    The main tweet text.
            tweet_type:    Label for the notification ("deal", "meme", "viral", "thread").
            hashtags:      Optional hashtag string to append / display separately.
            thread_tweets: For threads — list of all tweet texts in order.
            extra_info:    Optional extra context line for the notification.

        Returns:
            Absolute path to the saved .txt file.
        """
        output_dir = Path("deal_sniper_ai/output/twitter")
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"tweet_{timestamp}_{tweet_type}.txt"
        file_path = output_dir / filename

        # --- Build the text file content ---
        try:
            from zoneinfo import ZoneInfo
            now_est = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M %p EST")
        except Exception:
            now_est = timestamp

        lines = [
            f"Twitter Post Ready — {now_est}",
            f"Type: {tweet_type}",
            "-" * 60,
        ]

        if thread_tweets:
            for i, t in enumerate(thread_tweets, 1):
                lines += [f"Tweet {i}/{len(thread_tweets)}:", t, ""]
        else:
            lines += [tweet_text, ""]

        if hashtags:
            lines += ["-" * 60, "Hashtags:", hashtags]

        if extra_info:
            lines += ["", "Notes:", extra_info]

        file_content = "\n".join(lines)
        file_path.write_text(file_content, encoding="utf-8")
        abs_path = str(file_path.resolve())
        logger.info("Twitter manual post saved: %s", abs_path)

        # --- Send Telegram DM to owner ---
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        owner_id = os.environ.get("TELEGRAM_OWNER_ID", "") or os.environ.get("TELEGRAM_CHANNEL_ID", "")

        if bot_token and owner_id:
            preview = tweet_text[:200] + ("..." if len(tweet_text) > 200 else "")
            tg_message = (
                "\U0001f426 <b>Twitter Post Ready!</b>\n\n"
                f"<b>Type:</b> {tweet_type}\n"
                f"<b>File:</b> <code>{abs_path}</code>\n\n"
                "<b>Tweet text (copy this):</b>\n"
                f"<code>{preview}</code>\n"
            )
            if hashtags:
                tg_message += f"\n<b>Hashtags:</b>\n<code>{hashtags[:200]}</code>\n"
            if thread_tweets and len(thread_tweets) > 1:
                tg_message += f"\n<i>Thread: {len(thread_tweets)} tweets — see file for full text</i>\n"
            tg_message += (
                "\n<b>Upload steps:</b>\n"
                "1. Open the file at the path above\n"
                "2. Copy the tweet text\n"
                "3. Paste into twitter.com or the X app\n"
                "4. Add hashtags if shown\n"
                "5. Post!"
            )

            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": owner_id,
                    "text": tg_message,
                    "parse_mode": "HTML",
                }
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(url, data=payload)
                    resp.raise_for_status()
                    if resp.json().get("ok"):
                        logger.info("Telegram DM sent for manual Twitter post")
                    else:
                        logger.warning("Telegram DM failed: %s", resp.json().get("description"))
            except Exception as exc:
                logger.warning("Could not send Telegram DM for Twitter manual post: %s", exc)
        else:
            logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_OWNER_ID not set — skipping DM")

        return abs_path

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Convenience functions
async def create_twitter_poster(config: Optional[Dict[str, Any]] = None) -> TwitterPoster:
    """
    Create Twitter poster instance.

    Args:
        config: Optional configuration

    Returns:
        TwitterPoster instance
    """
    from deal_sniper_ai.config.config import get_config
    config = config or get_config()
    return TwitterPoster(config)


async def test_twitter_connection(config: Optional[Dict[str, Any]] = None) -> bool:
    """
    Test Twitter connection.

    Args:
        config: Optional configuration

    Returns:
        True if connection successful
    """
    poster = await create_twitter_poster(config)
    try:
        return await poster.test_connection()
    finally:
        await poster.close()