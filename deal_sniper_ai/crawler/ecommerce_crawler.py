"""
E-commerce Crawler for Deal Sniper AI Platform.

Adapted from the existing QA crawler (qa/crawler.js) for Python/Playwright.
Specialized for scraping major retailers (Amazon, Walmart, Target, Home Depot)
with anti-blocking measures and intelligent product discovery.
"""

import asyncio
import json
import random
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any
from urllib.parse import urljoin, urlparse, parse_qs

import re as _re_hdr
import yaml
from pathlib import Path
from playwright.async_api import async_playwright, Browser, Page, Response
from pydantic import BaseModel, Field

from deal_sniper_ai.crawler.anti_blocking import (
    AntiBlockingManager, create_anti_blocking_manager,
    get_browser_context_options, handle_crawler_response
)

try:
    from playwright_stealth import Stealth as _Stealth
    _stealth = _Stealth()
    _STEALTH_AVAILABLE = True
except ImportError:
    _STEALTH_AVAILABLE = False

try:
    import redis as _redis
    _redis_client = _redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    _redis_client.ping()
    _REDIS_AVAILABLE = True
except Exception:
    _REDIS_AVAILABLE = False

def _build_request_headers(ua: str) -> dict:
    """Build extra HTTP headers that are consistent with the given user-agent string.

    Chrome/Edge send sec-ch-ua client hints; Firefox and Safari do NOT.
    Sending these hints with a non-Chromium UA is a strong bot-detection signal.
    """
    headers: dict = {"Referer": "https://www.google.com/"}
    if not ua:
        return headers

    is_edge = "Edg/" in ua
    # Chromium-based: Chrome or Edge (Edg/ token always accompanied by Chrome/ token)
    is_chromium = "Chrome/" in ua

    if is_chromium:
        m = _re_hdr.search(r'Chrome/(\d+)', ua)
        v = m.group(1) if m else "135"

        if "Macintosh" in ua or "Mac OS" in ua:
            platform = '"macOS"'
        elif "Linux" in ua and "Android" not in ua:
            platform = '"Linux"'
        else:
            platform = '"Windows"'

        mobile = "?1" if "Mobile" in ua else "?0"

        if is_edge:
            brand = f'"Microsoft Edge";v="{v}", "Chromium";v="{v}", "Not-A.Brand";v="8"'
        else:
            brand = f'"Google Chrome";v="{v}", "Chromium";v="{v}", "Not-A.Brand";v="8"'

        headers["sec-ch-ua"] = brand
        headers["sec-ch-ua-mobile"] = mobile
        headers["sec-ch-ua-platform"] = platform
    # Firefox / Safari / others: no sec-ch-ua headers (they don't send them)

    return headers


_VIEWPORTS = [
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1920, "height": 1080},
    {"width": 1280, "height": 800},
    {"width": 1600, "height": 900},
]

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProductData(BaseModel):
    """Extracted product data from retailer pages."""
    sku: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    upc: Optional[str] = None
    model_number: Optional[str] = None
    retailer_product_id: Optional[str] = None
    retailer_url: str
    current_price: Optional[float] = None
    original_price: Optional[float] = None
    currency: str = "USD"
    is_discounted: bool = False
    discount_percent: Optional[int] = None
    coupon_available: bool = False
    coupon_code: Optional[str] = None


class CrawlerConfig(BaseModel):
    """Configuration for a specific retailer crawler."""
    base_url: str
    search_url: str
    categories: List[str]
    max_pages_per_search: int = 5
    request_delay: Tuple[float, float] = (1.0, 3.0)  # min, max seconds
    user_agent_rotation: bool = True
    use_proxies: bool = False
    selectors: Dict[str, str] = Field(default_factory=dict)


class EcommerceCrawler:
    """Main crawler class for e-commerce retailers."""

    def __init__(self, retailer_id: str, config: dict):
        self.retailer_id = retailer_id
        self.config = CrawlerConfig(**config)
        self.visited_urls: Set[str] = set()
        self.session_id = f"{retailer_id}_{int(time.time())}"

        # Anti-blocking manager
        self.anti_blocking: Optional[AntiBlockingManager] = None

        # Stats (kept for backward compatibility)
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "blocked_requests": 0,
            "captcha_encounters": 0,
            "products_found": 0,
            "errors": 0,
        }

    async def _initialize_anti_blocking(self):
        """Initialize the anti-blocking manager."""
        if not self.anti_blocking:
            self.anti_blocking = await create_anti_blocking_manager(self.retailer_id)

    async def _throttle_request(self):
        """Apply throttling delay before next request."""
        if self.anti_blocking:
            await self.anti_blocking.throttle_request()
        else:
            # Fallback to random delay
            delay = random.uniform(*self.config.request_delay)
            await asyncio.sleep(delay)

    async def _save_scraping_session(self):
        """Save scraping session stats to database."""
        # This is now handled by the anti-blocking manager
        if self.anti_blocking:
            # Get metrics from anti-blocking manager
            metrics = await self.anti_blocking.get_performance_metrics()

            # Update local stats for backward compatibility
            self.stats["total_requests"] = metrics["request_count"]
            self.stats["successful_requests"] = metrics["success_count"]
            self.stats["blocked_requests"] = metrics["block_count"]
            self.stats["captcha_encounters"] = metrics["captcha_count"]

            # The anti-blocking manager saves session stats automatically
            # when sessions end or when cleanup() is called
        else:
            # Fallback to Supabase REST
            try:
                from deal_sniper_ai.database.supabase_client import get_supabase_client
                db = get_supabase_client()
                db.table('scraping_sessions').insert({
                    'retailer_id': self.retailer_id,
                    'session_id': self.session_id,
                    'total_requests': self.stats['total_requests'],
                    'successful_requests': self.stats['successful_requests'],
                    'blocked_requests': self.stats['blocked_requests'],
                    'captcha_encounters': self.stats['captcha_encounters'],
                    'success_rate': (
                        self.stats['successful_requests'] / self.stats['total_requests'] * 100
                        if self.stats['total_requests'] > 0 else 0
                    ),
                    'ended_at': datetime.utcnow().isoformat(),
                    'duration_seconds': int(time.time() - int(self.session_id.split('_')[1]))
                }).execute()
            except Exception as e:
                logger.warning(f"Could not save scraping session: {e}")

    async def _save_product(self, product_data: ProductData) -> Optional[str]:
        """Save or update product in database via Supabase REST. Returns product ID."""
        try:
            from deal_sniper_ai.database.supabase_client import get_supabase_client
            db = get_supabase_client()
            now = datetime.utcnow().isoformat()
            rid = product_data.retailer_product_id or product_data.sku or ''

            # Check if product exists
            existing = db.table('products').select('id').eq(
                'retailer_id', self.retailer_id
            ).eq('retailer_product_id', rid).execute()

            if existing.data:
                product_id = existing.data[0]['id']
                db.table('products').update({
                    'title': product_data.title,
                    'current_price': product_data.current_price,
                    'original_price': product_data.original_price,
                    'image_url': product_data.image_url,
                    'last_scraped_at': now,
                }).eq('id', product_id).execute()
            else:
                result = db.table('products').insert({
                    'sku': product_data.sku or rid,
                    'title': product_data.title,
                    'description': product_data.description,
                    'category': product_data.category,
                    'brand': product_data.brand,
                    'image_url': product_data.image_url,
                    'retailer_id': self.retailer_id,
                    'retailer_product_id': rid,
                    'retailer_url': product_data.retailer_url,
                    'current_price': product_data.current_price,
                    'original_price': product_data.original_price,
                    'currency': product_data.currency,
                    'last_scraped_at': now,
                }).execute()
                product_id = result.data[0]['id'] if result.data else None

            # Save price history
            if product_id and product_data.current_price is not None:
                db.table('price_history').insert({
                    'product_id': product_id,
                    'price': product_data.current_price,
                    'currency': product_data.currency,
                    'is_discounted': product_data.is_discounted,
                    'discount_percent': product_data.discount_percent,
                    'coupon_applied': product_data.coupon_available,
                    'source': 'crawler',
                    'captured_at': now,
                }).execute()

            self.stats["products_found"] += 1
            logger.info(f"Saved product: {product_data.title[:60]}")
            return product_id

        except Exception as e:
            logger.error(f"Error saving product {product_data.title}: {e}")
            self.stats["errors"] += 1
            return None

    async def _check_and_post_deal(self, product_id: str, product_data: ProductData):
        """Immediately post deal to Telegram if it qualifies."""
        try:
            from deal_sniper_ai.posting_engine.instant_poster import detect_and_post_deal
            await detect_and_post_deal(
                product_id=product_id,
                title=product_data.title,
                retailer_url=product_data.retailer_url,
                current_price=product_data.current_price,
                original_price=product_data.original_price,
                discount_percent=product_data.discount_percent,
                coupon_available=product_data.coupon_available,
                image_url=product_data.image_url,
            )
        except Exception:
            logger.exception(f"Deal check/post failed for {product_data.title[:40]}")

    async def _detect_captcha(self, page: Page) -> bool:
        """Detect if CAPTCHA or Amazon block page is present."""
        url = page.url

        # URL-based detection — Amazon redirects to these on hard blocks
        if any(p in url for p in ('validateCaptcha', '/errors/', 'ap/captcha')):
            self.stats["captcha_encounters"] += 1
            logger.warning(f"Amazon block URL detected: {url}")
            return True

        # Page title check — fastest signal, no DOM traversal needed
        try:
            title = await page.title()
            if any(t in title for t in ('Robot Check', 'CAPTCHA', 'Sorry!', '503')):
                self.stats["captcha_encounters"] += 1
                logger.warning(f"Amazon block page title: '{title}' on {url}")
                return True
        except Exception:
            pass

        # Content-based checks (covers 200-OK soft-block pages)
        block_phrases = [
            "verify you are human",
            "not a robot",
            "enter the characters you see",
            "to discuss automated access",
            "unusual traffic",
            "g-recaptcha",
            "h-captcha",
            "cf-chl-widget",
        ]
        try:
            content = (await page.content()).lower()
            for phrase in block_phrases:
                if phrase in content:
                    self.stats["captcha_encounters"] += 1
                    logger.warning(f"Block phrase '{phrase}' detected on {url}")
                    return True
        except Exception:
            pass

        return False

    async def _handle_blocking(self, response: Optional[Response], page: Page) -> bool:
        """Handle blocking responses and CAPTCHAs."""
        # Update stats for backward compatibility
        self.stats["total_requests"] += 1

        if response is None:
            self.stats["blocked_requests"] += 1
            if self.anti_blocking:
                await self.anti_blocking.record_request_result(
                    success=False, was_blocked=True
                )
            return False

        # Get page content for CAPTCHA detection
        page_content = await page.content()
        url = str(page.url)

        # Use anti-blocking system if available
        if self.anti_blocking:
            # Always run our richer CAPTCHA/block detection first —
            # Amazon returns 200 on block pages so status-code checks miss them.
            if await self._detect_captcha(page):
                self.stats["blocked_requests"] += 1
                await self.anti_blocking.record_request_result(
                    success=False, was_blocked=False, had_captcha=True
                )
                return False

            start_time = time.time()
            success = await handle_crawler_response(
                self.anti_blocking, response, page_content, url
            )

            if success:
                self.stats["successful_requests"] += 1
            else:
                status = response.status
                if status in [403, 429, 503]:
                    self.stats["blocked_requests"] += 1

            return success
        else:
            # Fallback to old method
            status = response.status
            if status in [403, 429, 503]:  # Common blocking status codes
                self.stats["blocked_requests"] += 1
                logger.warning(f"Blocked with status {status} on {response.url}")
                return False

            if await self._detect_captcha(page):
                self.stats["captcha_encounters"] += 1
                return False

            self.stats["successful_requests"] += 1
            return True

    async def crawl_search_results(self, query: str, category: Optional[str] = None) -> List[ProductData]:
        """Crawl search results for a given query."""
        logger.info(f"Crawling {self.retailer_id} for query: {query}")
        products = []

        async with async_playwright() as p:
            # Initialize anti-blocking if not already done
            await self._initialize_anti_blocking()

            # Launch browser with anti-detection measures
            launch_options = {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ]
            }

            # Get browser context options from anti-blocking manager
            context_options = {
                "viewport": random.choice(_VIEWPORTS),
                "locale": "en-US",
                "timezone_id": "America/New_York",
            }

            if self.anti_blocking:
                anti_blocking_options = await get_browser_context_options(self.anti_blocking)
                context_options.update(anti_blocking_options)

                # Add proxy to launch options if provided by anti-blocking
                if "proxy" in anti_blocking_options:
                    launch_options["proxy"] = anti_blocking_options["proxy"]
            elif self.config.use_proxies:
                # Fallback to old proxy logic (simplified)
                logger.warning("Using fallback proxy logic - anti-blocking not initialized")
                # Note: Old proxy logic would go here, but it was empty

            # Build headers consistent with the selected user agent (must come after
            # anti_blocking_options are applied so we know the actual UA string)
            context_options["extra_http_headers"] = _build_request_headers(
                context_options.get("user_agent", "")
            )

            browser = await p.chromium.launch(**launch_options)
            context = await browser.new_context(**context_options)
            await self._restore_cookies(context)

            page = await context.new_page()
            if _STEALTH_AVAILABLE:
                await _stealth.apply_stealth_async(page)

            try:
                for page_num in range(1, self.config.max_pages_per_search + 1):
                    # Construct search URL
                    if self.retailer_id == "amazon":
                        url = self.config.search_url.format(query=query, page=page_num)
                    elif self.retailer_id == "walmart":
                        url = self.config.search_url.format(query=query, page=page_num)
                    elif self.retailer_id == "target":
                        offset = (page_num - 1) * 24
                        url = self.config.search_url.format(query=query, offset=offset)
                    elif self.retailer_id == "home_depot":
                        offset = (page_num - 1) * 24
                        url = self.config.search_url.format(query=query, offset=offset)
                    else:
                        url = f"{self.config.base_url}/search?q={query}&page={page_num}"

                    logger.info(f"Navigating to search page {page_num}: {url}")
                    self.stats["total_requests"] += 1

                    try:
                        response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        await self._throttle_request()

                        if not await self._handle_blocking(response, page):
                            logger.error(f"Blocked on search page {page_num}")
                            break

                        await self._simulate_human_behavior(page)

                        # For Amazon, extract all product data directly from search cards
                        # (avoids individual page visits which trigger bot detection)
                        if self.retailer_id == "amazon":
                            page_products = await self._extract_products_from_search_cards(page)
                            logger.info(f"Extracted {len(page_products)} products from search cards")
                            for product_data in page_products:
                                asin_url = f"https://www.amazon.com/dp/{product_data.sku}"
                                if asin_url not in self.visited_urls:
                                    products.append(product_data)
                                    product_id = await self._save_product(product_data)
                                    if product_id:
                                        await self._check_and_post_deal(product_id, product_data)
                                    self.visited_urls.add(asin_url)
                        else:
                            # Non-Amazon: visit individual product pages
                            product_links = await self._extract_product_links(page)
                            logger.info(f"Found {len(product_links)} product links on page {page_num}")
                            for link in product_links[:10]:
                                if link not in self.visited_urls:
                                    product_data = await self.crawl_product_page(link, context)
                                    if product_data:
                                        products.append(product_data)
                                        product_id = await self._save_product(product_data)
                                        if product_id:
                                            await self._check_and_post_deal(product_id, product_data)
                                    self.visited_urls.add(link)
                                    await self._throttle_request()

                        # Check if there are more pages
                        if not await self._has_next_page(page):
                            break

                    except Exception as e:
                        logger.error(f"Error crawling search page {page_num}: {e}")
                        self.stats["errors"] += 1
                        continue

            finally:
                await self._save_cookies(context)
                await browser.close()

        logger.info(f"Crawling complete for query '{query}'. Found {len(products)} products.")
        return products

    async def crawl_product_page(self, url: str, context) -> Optional[ProductData]:
        """Crawl individual product page and extract data."""
        logger.info(f"Crawling product page: {url}")

        page = await context.new_page()
        if _STEALTH_AVAILABLE:
            await _stealth.apply_stealth_async(page)
        self.stats["total_requests"] += 1

        try:
            # Use 'load' for product pages so JS-rendered prices/titles are present
            response = await page.goto(url, wait_until="load", timeout=60000)
            await self._throttle_request()

            if not await self._handle_blocking(response, page):
                return None

            await self._simulate_human_behavior(page)

            # Extract product data using retailer-specific selectors
            product_data = await self._extract_product_data(page, url)
            if product_data:
                logger.info(f"Extracted product: {product_data.title}")
                return product_data

        except Exception as e:
            logger.error(f"Error crawling product page {url}: {e}")
            self.stats["errors"] += 1
            return None

        finally:
            await page.close()

        return None

    async def _extract_product_links(self, page: Page) -> List[str]:
        """Extract product links from search results page."""
        retailer_selectors = {
            "amazon": "a[href*='/dp/']",
            "walmart": "a[href*='/ip/']",
            "target": "a[data-test='product-title']",
            "home_depot": "a[data-test='product-title']",
        }

        selector = retailer_selectors.get(self.retailer_id, "a[href*='/product/']")
        links = []

        try:
            link_elements = await page.locator(selector).all()
            for element in link_elements:
                href = await element.get_attribute("href")
                if href:
                    full_url = urljoin(self.config.base_url, href)
                    # Filter out non-product links
                    if any(pattern in full_url for pattern in ["/dp/", "/ip/", "/product/", "/p/"]):
                        links.append(full_url)
        except Exception as e:
            logger.error(f"Error extracting product links: {e}")

        # Deduplicate
        return list(set(links))

    async def _extract_products_from_search_cards(self, page: Page) -> List[ProductData]:
        """
        Extract product data directly from Amazon search result cards.
        Avoids visiting individual product pages (which trigger bot detection).
        Returns ProductData objects with title, prices, ASIN, and image.
        """
        products = []
        import re as _re

        # Per-unit price indicators used in multiple guards below
        _UNIT_INDICATORS = ('/oz', '/fl oz', '/count', '/ct', '/ea', '/lb', '/kg', '/g ', '/ml', '/liter', '/piece', '/item')

        def _parse_price_str(s: Optional[str]) -> Optional[float]:
            if not s:
                return None
            # Per-unit prices include "/" in their text (e.g., "$0.44/fl oz",
            # "$13.90/oz", "$1.49/count") — reject them outright.
            if '/' in s:
                return None
            clean = _re.sub(r'[^\d\.]', '', s.strip())
            try:
                return float(clean) if clean else None
            except ValueError:
                return None

        try:
            cards = await page.locator('[data-component-type="s-search-result"]').all()
            if not cards:
                page_title = await page.title()
                page_url = page.url
                logger.warning(
                    f"0 search cards found — possible block. "
                    f"title='{page_title}' url={page_url}"
                )
            for card in cards:
                try:
                    asin = await card.get_attribute('data-asin')
                    if not asin:
                        continue

                    # Title — Amazon removed the <a> wrapper inside h2 in 2025,
                    # so 'h2 a span' now returns 0 elements. Try selectors in order:
                    # 1. h2 a span  (old structure — keep for any remaining cards)
                    # 2. h2 a       (intermediate structure)
                    # 3. h2         (current structure — confirmed working Apr 2025)
                    title = None
                    for _title_sel in ('h2 a span', 'h2 a', 'h2'):
                        _el = card.locator(_title_sel)
                        if await _el.count() > 0:
                            _txt = (await _el.first.text_content() or '').strip()
                            if _txt:
                                title = _txt
                                break
                    # Skip brand-only storefront cards (< 3 words or < 15 chars)
                    if title and (len(title) < 15 or len(title.split()) < 3):
                        continue

                    # Current price — tiered selector approach to avoid per-unit prices.
                    # Amazon cards embed multiple .a-offscreen nodes (real price + per-unit
                    # price like $/oz). Using max() can pick the wrong one when a per-unit
                    # price exceeds the product price.
                    #
                    # Tier 1: data-a-size="xl" — Amazon's dedicated main-price size attribute.
                    #   Single element, take directly (no aggregation needed).
                    # Tier 2: .a-price:not(.a-text-price):not([data-a-size="mini"]) — exclude
                    #   mini (per-unit) elements; take the FIRST match only.
                    # Tier 3: broad selector — take min() of values >= $5 (heuristic: for
                    #   items over $5 the real price is lower than inflated unit prices).
                    current_price = None

                    # Tier 1
                    xl_els = card.locator('[data-a-size="xl"] .a-offscreen')
                    if await xl_els.count() > 0:
                        current_price = _parse_price_str(await xl_els.first.text_content())
                        if current_price is not None and current_price < 1.00:
                            current_price = None

                    # Tier 2
                    if current_price is None:
                        t2_els = card.locator('.a-price:not(.a-text-price):not([data-a-size="mini"]) .a-offscreen')
                        if await t2_els.count() > 0:
                            v = _parse_price_str(await t2_els.first.text_content())
                            if v is not None and v >= 1.00:
                                current_price = v

                    # Tier 3 — same mini exclusion as Tier 2, but collects all
                    # matches and uses min() to avoid high per-unit prices
                    # (e.g. $537/oz) that survived the not-mini filter.
                    if current_price is None:
                        price_els = card.locator(
                            '.a-price:not(.a-text-price):not([data-a-size="mini"]) .a-offscreen'
                        )
                        n_prices = await price_els.count()
                        if n_prices > 0:
                            price_candidates = []
                            for _i in range(n_prices):
                                v = _parse_price_str(await price_els.nth(_i).text_content())
                                if v is not None and v >= 1.00:
                                    price_candidates.append(v)
                            if price_candidates:
                                current_price = min(price_candidates)

                    # Original/list price (strikethrough) — tiered approach.
                    # Tier 1: data-a-size="b" is Amazon's standard for the comparison price.
                    # Tier 2: broad .a-text-price selector — take the FIRST element only.
                    # Sanity cap: discard if original_price > current_price * 4
                    #   (inflated MSRP from a different pack size).
                    original_price = None

                    # Tier 1
                    orig_b_els = card.locator('.a-text-price[data-a-size="b"] .a-offscreen')
                    if await orig_b_els.count() > 0:
                        v = _parse_price_str(await orig_b_els.first.text_content())
                        if v is not None and v >= 1.00:
                            original_price = v

                    # Tier 2
                    if original_price is None:
                        orig_els = card.locator('.a-text-price .a-offscreen')
                        if await orig_els.count() > 0:
                            v = _parse_price_str(await orig_els.first.text_content())
                            if v is not None and v >= 1.00:
                                original_price = v

                    # Sanity cap: reject inflated MSRPs
                    if original_price is not None and current_price is not None:
                        if original_price > current_price * 4:
                            original_price = None

                    # Unit-price guard: check the visible text of the .a-text-price
                    # element for per-unit indicators like /oz, /fl oz, /count.
                    # Amazon sometimes renders a per-unit comparison in a strikethrough
                    # style — e.g., "($13.90/oz)" — which .a-offscreen strips to just
                    # "$13.90", making it look like a real list price.
                    if original_price is not None:
                        try:
                            _op_els = card.locator('.a-text-price')
                            if await _op_els.count() > 0:
                                _op_text = (await _op_els.first.text_content() or '').lower()
                                if any(ind in _op_text for ind in _UNIT_INDICATORS):
                                    original_price = None
                                    logger.debug(f"Discarded per-unit original_price for {asin}")
                        except Exception:
                            pass

                    # Image — try src, data-src, srcset in order; skip Amazon's lazy-load placeholder
                    img_el = card.locator('.s-image')
                    image_url = None
                    if await img_el.count() > 0:
                        for attr in ('src', 'data-src', 'data-old-hires', 'srcset'):
                            val = await img_el.first.get_attribute(attr)
                            if val and 'grey-pixel' not in val and 'blank.gif' not in val:
                                # srcset may be "url 1x, url2 2x" — take first URL
                                image_url = val.split()[0].rstrip(',')
                                break

                    # Only include products with a valid title and prices
                    if not title or not current_price:
                        continue

                    # ── Discount percentage ─────────────────────────────────
                    # Priority 1: Amazon's own badge — authoritative.
                    # Priority 2: Calculated from extracted prices — used as
                    #   fallback when no badge is present but both prices are valid.
                    #   The multi-tier price extraction + sanity cap above make
                    #   the calculated value reliable enough to act on.
                    discount_pct = None
                    _badge_discount = None  # set only when sourced from a badge

                    # Try all known badge selectors (Amazon rotates class names)
                    for _badge_sel in (
                        '.savingsPercentage',                        # most common: "-35%"
                        '[data-a-badge-type="s-badge-icon-percent"]',
                        '.a-badge-label .a-badge-text',
                    ):
                        badge_el = card.locator(_badge_sel)
                        if await badge_el.count() > 0:
                            badge_text = (await badge_el.first.text_content() or '').strip()
                            m = _re.search(r'(\d+)', badge_text)
                            if m:
                                _badge_discount = int(m.group(1))
                                discount_pct = _badge_discount
                                break

                    # Cross-validate badge % against extracted prices.
                    # If badge says 40% off but prices imply only 5% off,
                    # price extraction is unreliable — keep badge pct but
                    # reconstruct original_price from the badge so the savings
                    # calculation is consistent.
                    if discount_pct is not None and current_price is not None and discount_pct < 100:
                        if original_price is not None and original_price > 0:
                            implied_pct = int((1 - current_price / original_price) * 100)
                            if abs(implied_pct - discount_pct) > 25:
                                # Prices don't match badge — reconstruct from badge
                                original_price = round(current_price / (1 - discount_pct / 100), 2)
                        else:
                            # No original_price extracted — reconstruct from badge
                            original_price = round(current_price / (1 - discount_pct / 100), 2)

                    # Fallback: calculate discount from prices when no badge found.
                    # Only used when both prices were cleanly extracted and survive
                    # the sanity cap (original_price <= current_price * 4).
                    if discount_pct is None and original_price is not None and current_price is not None:
                        if original_price > current_price > 0:
                            discount_pct = int((1 - current_price / original_price) * 100)

                    # Final guard: a calculated discount > 80% with no Amazon badge
                    # almost always means per-unit price contamination survived the
                    # earlier filters (e.g., .a-offscreen contained just the number
                    # without "/oz"). Clear the fake discount and original_price.
                    if _badge_discount is None and discount_pct is not None and discount_pct > 80:
                        logger.debug(
                            f"Dropped {asin}: {discount_pct}% calculated discount "
                            f"without badge — likely per-unit price contamination"
                        )
                        original_price = None
                        discount_pct = None

                    logger.info(
                        f"CARD asin={asin} cur={current_price} orig={original_price} "
                        f"disc={discount_pct}% | {title[:55]}"
                    )

                    retailer_url = f"https://www.amazon.com/dp/{asin}"
                    products.append(ProductData(
                        sku=asin,
                        title=title,
                        retailer_product_id=asin,
                        retailer_url=retailer_url,
                        current_price=current_price,
                        original_price=original_price,
                        is_discounted=original_price is not None and current_price < original_price,
                        discount_percent=discount_pct,
                        coupon_available=False,
                        image_url=image_url,
                    ))
                except Exception as card_err:
                    logger.debug(f"Card extraction error: {card_err}")
                    continue
        except Exception as e:
            logger.error(f"Error extracting search cards: {e}")

        return products

    async def _extract_real_price(self, page: Page, selector: str) -> Optional[float]:
        """Return the smallest valid non-unit price found among all elements matching selector.

        Amazon pages contain both a real price ($13.98) and a per-unit price ($537.96/oz)
        inside the same container. Per-unit prices are identified by a '/' character in the
        text (e.g. '/oz', '/count'). We skip those and return the minimum of what remains,
        which is the actual listing price.
        """
        try:
            elements = await page.query_selector_all(selector)
            candidates: list = []
            for el in elements:
                raw = await el.inner_text()
                raw = raw.strip()
                # Skip per-unit prices like "$537.96/oz" or "537.96 /fl oz"
                if "/" in raw:
                    continue
                cleaned = raw.replace(",", "").replace("$", "")
                try:
                    val = float(cleaned.split()[0])
                    candidates.append(val)
                except (ValueError, IndexError):
                    pass
            # Return smallest valid price >= $1 (real price is lower than inflated unit price)
            valid = [v for v in candidates if v >= 1.0]
            return min(valid) if valid else None
        except Exception:
            return None

    async def _extract_product_data(self, page: Page, url: str) -> Optional[ProductData]:
        """Extract product data from product page."""
        try:
            # Wait for key elements to load (JS-rendered content)
            try:
                await page.wait_for_selector("#productTitle", timeout=8000)
            except Exception:
                try:
                    await page.wait_for_selector("h1", timeout=3000)
                except Exception:
                    pass

            # Get retailer-specific selectors from config
            selectors = self.config.selectors

            # Extract basic information
            title = await self._extract_text(page, selectors.get("title", "h1"))

            # --- Current price: skip per-unit prices, take min valid >= $1 --------
            # Amazon product pages embed BOTH the real price and a per-unit price
            # (e.g. $13.98 AND $537.96/oz) inside the same feature div.
            # Per-unit text contains "/" so we filter those out, then take min()
            # of what remains — the real listing price is always the smaller number.
            current_price = None
            for price_sel in [
                ".priceToPay .a-offscreen",           # most reliable — actual checkout price
                selectors.get("price", ""),            # config: #corePrice_feature_div .a-offscreen
                ".a-price:not(.a-text-price) .a-offscreen",
                "#priceblock_ourprice",
                "#priceblock_dealprice",
                "#priceblock_saleprice",
                "#price_inside_buybox",
            ]:
                if not price_sel:
                    continue
                v = await self._extract_real_price(page, price_sel)
                if v is not None and v >= 1.0:
                    current_price = v
                    break

            # --- Original price: same max() approach + sanity cap ---------------
            # If original / current > 5× the "original" is a bulk/case list price,
            # not the item's real was-price — discard it to prevent fake discounts.
            original_price = None
            if current_price:
                for orig_sel in [
                    ".a-text-price .a-offscreen",
                    "[data-a-strike='true'] .a-offscreen",
                    ".basisPrice .a-offscreen",
                    "#listPrice",
                    ".a-price.a-text-strike .a-offscreen",
                ]:
                    v = await self._extract_real_price(page, orig_sel)
                    if v is not None and v > current_price:
                        if v <= current_price * 5:   # sanity cap: max 80% off from list
                            original_price = v
                        break  # found a candidate (even if discarded); stop looking

            # Extract SKU from URL (e.g. /dp/ASIN for Amazon)
            sku = await self._extract_sku(page, url)

            # Extract main product image
            image_url = await self._extract_attribute(
                page, selectors.get("image", "#landingImage"), "src"
            )

            # Check for coupons
            coupon_available = await self._detect_coupon(page, selectors.get("coupon", ".coupon"))

            return ProductData(
                sku=sku or "",
                title=title or "Unknown Product",
                retailer_product_id=sku,
                retailer_url=url,
                current_price=current_price,
                original_price=original_price,
                is_discounted=original_price is not None and current_price < original_price,
                discount_percent=(
                    int((1 - current_price / original_price) * 100)
                    if original_price and current_price and original_price > 0
                    else None
                ),
                coupon_available=coupon_available,
                image_url=image_url,
            )

        except Exception as e:
            logger.error(f"Error extracting product data: {e}")
            return None

    async def _extract_text(self, page: Page, selector: str) -> Optional[str]:
        """Extract text from element if it exists."""
        try:
            if await page.locator(selector).count() > 0:
                return await page.locator(selector).first().text_content()
        except:
            pass
        return None

    async def _extract_attribute(self, page: Page, selector: str, attribute: str) -> Optional[str]:
        """Extract attribute from element if it exists."""
        try:
            if await page.locator(selector).count() > 0:
                return await page.locator(selector).first().get_attribute(attribute)
        except:
            pass
        return None

    async def _extract_sku(self, page: Page, url: str) -> Optional[str]:
        """Extract SKU from URL or page."""
        # Try to extract from URL first
        url_parts = urlparse(url)
        path = url_parts.path

        # Common patterns for retailer URLs
        if "/dp/" in path:  # Amazon
            parts = path.split("/dp/")
            if len(parts) > 1:
                return parts[1].split("/")[0]
        elif "/ip/" in path:  # Walmart
            parts = path.split("/ip/")
            if len(parts) > 1:
                return parts[1].split("/")[0]
        elif "/p/" in path:  # Target
            parts = path.split("/p/")
            if len(parts) > 1:
                return parts[1].split("/")[0]

        # Try to find SKU in page content
        sku_selectors = [
            "[data-test='sku']",
            "[itemprop='sku']",
            ".sku",
            "text=SKU",
            "text=Item #",
        ]

        for selector in sku_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    element = await page.locator(selector).first()
                    text = await element.text_content()
                    if text:
                        # Extract numbers from text
                        import re
                        numbers = re.findall(r'\d+', text)
                        if numbers:
                            return numbers[0]
            except:
                continue

        return None

    def _parse_single_price(self, price_text: Optional[str]) -> Optional[float]:
        """Parse a single price string into a float."""
        if not price_text:
            return None
        try:
            import re
            clean_text = re.sub(r'[^\d\.]', '', price_text.strip())
            return float(clean_text) if clean_text else None
        except Exception:
            return None

    def _parse_price(self, price_text: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
        """Parse price text into (current_price, None). Use _parse_single_price for individual prices."""
        price = self._parse_single_price(price_text)
        return price, None

    async def _detect_coupon(self, page: Page, coupon_selector: str) -> bool:
        """Detect if coupon is available on page."""
        try:
            if await page.locator(coupon_selector).count() > 0:
                return True

            # Also look for common coupon text
            coupon_indicators = [
                "text=Coupon",
                "text=Save",
                "text=Discount",
                "text=Promo",
                "text=Offer",
            ]

            for indicator in coupon_indicators:
                if await page.locator(indicator).count() > 0:
                    return True

        except:
            pass

        return False

    async def _has_next_page(self, page: Page) -> bool:
        """Check if there is a next page of search results."""
        next_selectors = [
            "a:has-text('Next')",
            "button:has-text('Next')",
            "[aria-label='Next']",
            ".next-page",
        ]

        for selector in next_selectors:
            try:
                if await page.locator(selector).count() > 0:
                    return True
            except:
                continue

        return False

    async def _simulate_human_behavior(self, page):
        """Simulate human scroll and mouse movement to avoid bot detection."""
        try:
            scroll_y = random.randint(300, 1200)
            await page.evaluate(f"window.scrollTo({{top: {scroll_y}, behavior: 'smooth'}})")
            await asyncio.sleep(random.uniform(0.8, 2.0))
            await page.mouse.move(
                random.randint(100, 1200),
                random.randint(100, 600)
            )
            await asyncio.sleep(random.uniform(0.3, 0.8))
        except Exception:
            pass

    async def _restore_cookies(self, context):
        """Restore Amazon session cookies from Redis if available."""
        if not _REDIS_AVAILABLE:
            return
        try:
            raw = _redis_client.get(f"crawler_cookies:{self.retailer_id}")
            if raw:
                cookies = json.loads(raw)
                await context.add_cookies(cookies)
                logger.debug(f"Restored {len(cookies)} cookies for {self.retailer_id}")
        except Exception as e:
            logger.debug(f"Cookie restore failed: {e}")

    async def _save_cookies(self, context):
        """Save current cookies to Redis for next run."""
        if not _REDIS_AVAILABLE:
            return
        try:
            cookies = await context.cookies()
            if cookies:
                _redis_client.setex(
                    f"crawler_cookies:{self.retailer_id}",
                    6 * 3600,  # 6 hour TTL
                    json.dumps(cookies)
                )
                logger.debug(f"Saved {len(cookies)} cookies for {self.retailer_id}")
        except Exception as e:
            logger.debug(f"Cookie save failed: {e}")

    async def crawl_popular_categories(self) -> Dict[str, List[ProductData]]:
        """Crawl popular categories for the retailer."""
        results = {}
        categories = self.config.categories[:3]  # Limit to 3 categories
        for idx, category in enumerate(categories):
            logger.info(f"Crawling category: {category}")
            products = await self.crawl_search_results(category, category)
            results[category] = products
            # Pause between categories (skip after the last one)
            if idx < len(categories) - 1:
                pause = random.uniform(15, 45)
                logger.debug(f"Inter-category pause: {pause:.1f}s")
                await asyncio.sleep(pause)
        return results

    async def crawl_product(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Crawl a single product URL and return extracted data.

        Args:
            url: Product page URL

        Returns:
            Dictionary with product data including price, currency, etc.
        """

        async with async_playwright() as p:
            # Initialize anti-blocking if not already done
            await self._initialize_anti_blocking()

            # Launch browser with anti-detection measures
            launch_options = {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ]
            }

            # Get browser context options from anti-blocking manager
            context_options = {
                "viewport": random.choice(_VIEWPORTS),
                "locale": "en-US",
                "timezone_id": "America/New_York",
            }

            if self.anti_blocking:
                anti_blocking_options = await get_browser_context_options(self.anti_blocking)
                context_options.update(anti_blocking_options)

                # Add proxy to launch options if provided by anti-blocking
                if "proxy" in anti_blocking_options:
                    launch_options["proxy"] = anti_blocking_options["proxy"]
            elif self.config.use_proxies:
                # Fallback to old proxy logic (simplified)
                logger.warning("Using fallback proxy logic - anti-blocking not initialized")
                # Note: Old proxy logic would go here, but it was empty

            # Build headers consistent with the selected user agent
            context_options["extra_http_headers"] = _build_request_headers(
                context_options.get("user_agent", "")
            )

            browser = await p.chromium.launch(**launch_options)
            context = await browser.new_context(**context_options)
            await self._restore_cookies(context)

            try:
                product_data = await self.crawl_product_page(url, context)
                if product_data:
                    return {
                        'price': product_data.current_price,
                        'currency': product_data.currency,
                        'title': product_data.title,
                        'is_discounted': product_data.is_discounted,
                        'discount_percent': product_data.discount_percent,
                        'coupon_applied': product_data.coupon_available,
                        'image_url': product_data.image_url,
                        'sku': product_data.sku,
                        'retailer_product_id': product_data.retailer_product_id
                    }
                return None
            finally:
                await self._save_cookies(context)
                await browser.close()

    async def close(self):
        """Close any resources used by the crawler."""
        # Clean up anti-blocking manager
        if self.anti_blocking:
            await self.anti_blocking.cleanup()
            self.anti_blocking = None

        logger.info(f"Crawler for {self.retailer_id} closed")

    async def run(self, queries: Optional[List[str]] = None):
        """Main entry point for crawler execution."""
        start_time = time.time()
        logger.info(f"Starting {self.retailer_id} crawler session {self.session_id}")

        try:
            # Use provided queries or default to categories
            if not queries:
                queries = self.config.categories[:2]  # Limit to 2 categories for initial run

            all_products = []
            for query in queries:
                products = await self.crawl_search_results(query)
                all_products.extend(products)

            # Save session stats
            await self._save_scraping_session()

            elapsed = time.time() - start_time
            logger.info(
                f"Crawler session completed in {elapsed:.2f}s. "
                f"Found {len(all_products)} products. "
                f"Success rate: {self.stats['successful_requests'] / self.stats['total_requests'] * 100:.1f}%"
            )

            return all_products

        except Exception as e:
            logger.error(f"Crawler session failed: {e}")
            # Still save session stats
            await self._save_scraping_session()
            return []
        finally:
            # Ensure cleanup happens
            await self.close()


async def main():
    """Example usage of the crawler."""
    import asyncio

    # Load configuration
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Test with Amazon crawler
    amazon_config = config['retailers']['amazon']
    crawler = EcommerceCrawler("amazon", amazon_config)

    # Crawl for "laptop" and "headphones"
    products = await crawler.run(["laptop", "headphones"])

    print(f"Found {len(products)} products:")
    for product in products[:5]:  # Show first 5
        print(f"  - {product.title}: ${product.current_price}")

    # Save session stats
    await crawler._save_scraping_session()


if __name__ == "__main__":
    asyncio.run(main())