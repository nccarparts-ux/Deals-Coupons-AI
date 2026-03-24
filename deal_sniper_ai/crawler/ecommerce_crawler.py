"""
E-commerce Crawler for Deal Sniper AI Platform.

Adapted from the existing QA crawler (qa/crawler.js) for Python/Playwright.
Specialized for scraping major retailers (Amazon, Walmart, Target, Home Depot)
with anti-blocking measures and intelligent product discovery.
"""

import asyncio
import random
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any
from urllib.parse import urljoin, urlparse, parse_qs

import yaml
from pathlib import Path
from playwright.async_api import async_playwright, Browser, Page, Response
from pydantic import BaseModel, Field

from deal_sniper_ai.crawler.anti_blocking import (
    AntiBlockingManager, create_anti_blocking_manager,
    get_browser_context_options, handle_crawler_response
)

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
        except Exception as e:
            logger.warning(f"Deal check/post failed for {product_data.title[:40]}: {e}")

    async def _detect_captcha(self, page: Page) -> bool:
        """Detect if CAPTCHA is present on the page."""
        # Common CAPTCHA indicators
        captcha_selectors = [
            "#captcha",
            ".g-recaptcha",
            "iframe[src*='captcha']",
            "div[class*='captcha']",
            "h1:has-text('captcha')",
            "text=robot",
            "text=verify you are human"
        ]

        for selector in captcha_selectors:
            if await page.locator(selector).count() > 0:
                self.stats["captcha_encounters"] += 1
                logger.warning(f"CAPTCHA detected on {page.url}")
                return True

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
            start_time = time.time()
            success = await handle_crawler_response(
                self.anti_blocking, response, page_content, url
            )

            # Update local stats for backward compatibility
            if success:
                self.stats["successful_requests"] += 1
            else:
                # Check what type of failure
                status = response.status
                if status in [403, 429, 503]:
                    self.stats["blocked_requests"] += 1
                # CAPTCHA detection is handled by anti-blocking system

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
                "viewport": {"width": 1920, "height": 1080},
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

            browser = await p.chromium.launch(**launch_options)
            context = await browser.new_context(**context_options)

            page = await context.new_page()

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
                await browser.close()

        logger.info(f"Crawling complete for query '{query}'. Found {len(products)} products.")
        return products

    async def crawl_product_page(self, url: str, context) -> Optional[ProductData]:
        """Crawl individual product page and extract data."""
        logger.info(f"Crawling product page: {url}")

        page = await context.new_page()
        self.stats["total_requests"] += 1

        try:
            # Use 'load' for product pages so JS-rendered prices/titles are present
            response = await page.goto(url, wait_until="load", timeout=60000)
            await self._throttle_request()

            if not await self._handle_blocking(response, page):
                return None

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

        def _parse_price_str(s: Optional[str]) -> Optional[float]:
            if not s:
                return None
            clean = _re.sub(r'[^\d\.]', '', s.strip())
            try:
                return float(clean) if clean else None
            except ValueError:
                return None

        try:
            cards = await page.locator('[data-component-type="s-search-result"]').all()
            for card in cards:
                try:
                    asin = await card.get_attribute('data-asin')
                    if not asin:
                        continue

                    # Title: prefer the linked span inside h2 (product title),
                    # not the h2 raw text which may contain brand-only storefront cards
                    title = None
                    title_span = card.locator('h2 a span')
                    if await title_span.count() > 0:
                        title = (await title_span.first.text_content() or '').strip() or None
                    if not title:
                        h2 = card.locator('h2')
                        if await h2.count() > 0:
                            title = (await h2.first.text_content() or '').strip() or None
                    # Skip brand-only results (fewer than 3 words or under 15 chars)
                    if title and (len(title) < 15 or len(title.split()) < 3):
                        continue

                    # Current price — collect ALL matching elements and take the
                    # largest value >= $1.00.  Amazon cards contain multiple
                    # .a-offscreen nodes: the real pack/product price ($27.99)
                    # AND per-unit prices ($0.03/count, $0.18/oz).  Using
                    # .first would grab the unit price when it appears first in
                    # the DOM, producing fake 96%-off discounts.  The actual
                    # product price is always the largest value on the card.
                    current_price = None
                    price_els = card.locator('.a-price:not(.a-text-price) .a-offscreen')
                    n_prices = await price_els.count()
                    if n_prices > 0:
                        price_candidates = []
                        for _i in range(n_prices):
                            v = _parse_price_str(await price_els.nth(_i).text_content())
                            if v is not None and v >= 1.00:
                                price_candidates.append(v)
                        if price_candidates:
                            current_price = max(price_candidates)

                    # Original/list price (strikethrough) — same approach
                    original_price = None
                    orig_els = card.locator('.a-text-price .a-offscreen')
                    n_orig = await orig_els.count()
                    if n_orig > 0:
                        orig_candidates = []
                        for _i in range(n_orig):
                            v = _parse_price_str(await orig_els.nth(_i).text_content())
                            if v is not None and v >= 1.00:
                                orig_candidates.append(v)
                        if orig_candidates:
                            original_price = max(orig_candidates)

                    # Image
                    img_el = card.locator('.s-image')
                    image_url = None
                    if await img_el.count() > 0:
                        image_url = await img_el.first.get_attribute('src')

                    # Only include products with a valid title and prices
                    if not title or not current_price:
                        continue

                    # ── Discount percentage ─────────────────────────────────
                    # Priority 1: Amazon's own explicit badge ("-35%" or "35% off").
                    #   This is the authoritative source — Amazon only shows this
                    #   badge when the price is genuinely reduced vs. the recent
                    #   selling price.  The strikethrough (.a-text-price) often
                    #   reflects an inflated manufacturer list price (MSRP) that
                    #   has never been the real selling price, leading to fake
                    #   discounts (e.g. baby wipes showing "35% off" but the
                    #   product page shows 5% off).
                    # Priority 2: Fall back to price calculation ONLY when the
                    #   savings are large enough that MSRP inflation can't explain
                    #   them (≥50% AND ≥$10 absolute savings).
                    discount_pct = None

                    badge_el = card.locator('.savingsPercentage')
                    if await badge_el.count() > 0:
                        badge_text = (await badge_el.first.text_content() or '').strip()
                        m = _re.search(r'(\d+)', badge_text)
                        if m:
                            discount_pct = int(m.group(1))

                    if discount_pct is None and original_price and original_price > current_price:
                        calc_pct = int((1 - current_price / original_price) * 100)
                        abs_savings = original_price - current_price
                        # Only trust price-calculated discount when savings are
                        # large enough that inflated list prices are unlikely
                        if calc_pct >= 50 and abs_savings >= 10.0:
                            discount_pct = calc_pct

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

    async def _extract_max_price(self, page: Page, selector: str) -> Optional[float]:
        """Return the largest valid price found among all elements matching selector."""
        try:
            elements = await page.query_selector_all(selector)
            best: Optional[float] = None
            for el in elements:
                raw = await el.inner_text()
                raw = raw.strip().replace(",", "").replace("$", "")
                try:
                    val = float(raw.split()[0])  # handle "13.98 /oz" → 13.98
                    if best is None or val > best:
                        best = val
                except (ValueError, IndexError):
                    pass
            return best
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

            # --- Current price: collect ALL candidates, take max >= $1 -----------
            # Amazon product pages embed BOTH the real price and a per-unit price
            # (e.g. $13.98 AND $537.96/oz) inside the same feature div.
            # Taking .first() grabs the unit price and produces fake 96%-off deals.
            # Collecting all values and taking max() reliably returns the real price.
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
                v = await self._extract_max_price(page, price_sel)
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
                    v = await self._extract_max_price(page, orig_sel)
                    if v is not None and v > current_price:
                        if v <= current_price * 5:   # sanity cap: max 80% off from list
                            original_price = v
                        break  # found a candidate (even if discarded); stop looking

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

    async def crawl_popular_categories(self) -> Dict[str, List[ProductData]]:
        """Crawl popular categories for the retailer."""
        results = {}
        for category in self.config.categories[:3]:  # Limit to 3 categories
            logger.info(f"Crawling category: {category}")
            products = await self.crawl_search_results(category, category)
            results[category] = products
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
                "viewport": {"width": 1920, "height": 1080},
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

            browser = await p.chromium.launch(**launch_options)
            context = await browser.new_context(**context_options)

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