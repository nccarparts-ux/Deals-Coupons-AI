# Affiliate Engine

The Affiliate Engine module provides affiliate link conversion, tracking, and analytics for the Deal Sniper AI Platform. It supports major retailers including Amazon, Walmart, Target, and Home Depot.

## Features

### 1. **Affiliate Link Conversion**
- Convert product URLs to affiliate links for major retailers
- URL sanitization and parameter preservation
- Program-specific URL transformation rules
- Database caching to avoid duplicate conversions

### 2. **Click & Conversion Tracking**
- Track clicks on affiliate links
- Record conversions with revenue amounts
- Update performance metrics in real-time
- Integration with deal posting engine

### 3. **Performance Analytics**
- Comprehensive performance reports
- Conversion funnel analysis
- Revenue forecasting
- Anomaly detection for performance issues
- Integration with posted deals

### 4. **Program Management**
- Support for multiple affiliate programs
- Enable/disable programs via configuration
- Program-specific statistics and monitoring
- Expiration management for affiliate links

## Supported Retailers & Programs

| Retailer | Affiliate Program | Parameter | Configuration Key |
|----------|-------------------|-----------|-------------------|
| Amazon | Amazon Associates | `tag` | `amazon_associates` |
| Walmart | Walmart Affiliate | `affiliate` | `walmart_affiliate` |
| Target | Target Affiliate | `affiliate` | `target_affiliate` |
| Home Depot | Home Depot Affiliate | `affiliate` | `home_depot_affiliate` |

## Installation

The affiliate engine is included in the `deal_sniper_ai` package. No additional installation is required.

## Quick Start

### Basic URL Conversion

```python
import asyncio
from deal_sniper_ai.affiliate_engine import convert_url_to_affiliate

async def main():
    # Convert a product URL to affiliate link
    url = "https://www.amazon.com/dp/B08N5WRWNW"
    affiliate_url = await convert_url_to_affiliate(url)
    print(f"Affiliate URL: {affiliate_url}")

asyncio.run(main())
```

### Using the Converter Class

```python
import asyncio
from deal_sniper_ai.affiliate_engine import AffiliateConverter

async def main():
    converter = AffiliateConverter()

    # Convert URL with specific program
    url = "https://www.amazon.com/dp/B08N5WRWNW"
    affiliate_url = await converter.convert_to_affiliate(
        url,
        affiliate_program="amazon_associates",
        product_id=None  # Optional: associate with product in database
    )

    print(f"Affiliate URL: {affiliate_url}")

asyncio.run(main())
```

### Tracking Clicks and Conversions

```python
import asyncio
from decimal import Decimal
from uuid import uuid4
from deal_sniper_ai.affiliate_engine import (
    track_affiliate_click,
    track_affiliate_conversion
)

async def main():
    # Simulate affiliate link ID (from database)
    affiliate_link_id = uuid4()

    # Track a click
    await track_affiliate_click(affiliate_link_id)

    # Track a conversion with revenue
    revenue = Decimal("149.99")
    await track_affiliate_conversion(affiliate_link_id, revenue)

asyncio.run(main())
```

### Analytics and Reporting

```python
import asyncio
from deal_sniper_ai.affiliate_engine import AffiliateTracker

async def main():
    tracker = AffiliateTracker()

    # Get performance report for last 30 days
    report = await tracker.get_performance_report(days=30)
    print(f"Total Revenue: ${report['summary']['total_revenue']:.2f}")
    print(f"Conversion Rate: {report['summary']['conversion_rate']:.2f}%")

    # Forecast next 30 days revenue
    forecast = await tracker.forecast_revenue(days=30)
    print(f"Forecasted Revenue: ${forecast['forecasted_revenue']:.2f}")

asyncio.run(main())
```

## Configuration

The affiliate engine reads configuration from `config.yaml`:

```yaml
affiliate_programs:
  amazon_associates:
    enabled: true
    base_url: "https://www.amazon.com"
    tag_param: "tag"
    tag_value: "dealsniperai-20"  # Your Amazon Associates tag

  walmart_affiliate:
    enabled: false
    base_url: "https://www.walmart.com"
    partner_id_param: "affiliate"
    partner_id: ""  # Your Walmart Affiliate partner ID

  target_affiliate:
    enabled: false
    base_url: "https://www.target.com"
    account_id_param: "affiliate"
    account_id: ""  # Your Target Affiliate account ID

  home_depot_affiliate:
    enabled: false
    base_url: "https://www.homedepot.com"
    account_id_param: "affiliate"
    account_id: ""  # Your Home Depot Affiliate account ID
```

## Database Schema

The affiliate engine uses the `AffiliateLink` model:

```python
class AffiliateLink(Base):
    __tablename__ = "affiliate_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_url: Mapped[str] = mapped_column(String, nullable=False)
    affiliate_url: Mapped[str] = mapped_column(String, nullable=False)
    affiliate_program: Mapped[str] = mapped_column(String, nullable=False)
    retailer_id: Mapped[str] = mapped_column(String, nullable=False)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))

    # Performance metrics
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal('0.00'))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
```

## Integration Examples

### With E-commerce Crawler

```python
from deal_sniper_ai.affiliate_engine import AffiliateConverter

class EnhancedCrawler:
    def __init__(self):
        self.affiliate_converter = AffiliateConverter()

    async def process_product(self, product_url, product_id):
        # Convert product URL to affiliate link
        affiliate_url = await self.affiliate_converter.convert_to_affiliate(
            product_url,
            product_id=product_id
        )

        # Store product with affiliate URL
        await self.save_product(product_id, {
            'url': product_url,
            'affiliate_url': affiliate_url,
            # ... other product data
        })
```

### With Deal Posting Engine

```python
from deal_sniper_ai.affiliate_engine import convert_url_to_affiliate

async def post_deal(deal_data):
    # Get affiliate link for deal product
    affiliate_url = await convert_url_to_affiliate(
        deal_data['product_url'],
        product_id=deal_data['product_id']
    )

    # Format post with affiliate link
    post_content = f"""
    🔥 DEAL: {deal_data['title']}
    💰 Price: ${deal_data['current_price']}
    🛒 Link: {affiliate_url}
    """

    # Post to platforms
    await post_to_telegram(post_content)
    await post_to_discord(post_content)
```

### With Web Server (Click Tracking)

```python
from fastapi import FastAPI, HTTPException
from uuid import UUID
from deal_sniper_ai.affiliate_engine import track_affiliate_click

app = FastAPI()

@app.get("/affiliate/redirect/{affiliate_link_id}")
async def affiliate_redirect(affiliate_link_id: UUID):
    # Track the click
    click_tracked = await track_affiliate_click(affiliate_link_id)

    if not click_tracked:
        raise HTTPException(status_code=404, detail="Affiliate link not found")

    # Get affiliate URL from database
    affiliate_url = await get_affiliate_url_from_db(affiliate_link_id)

    # Redirect to affiliate URL
    return RedirectResponse(url=affiliate_url)
```

## API Reference

### `AffiliateConverter`

Main class for affiliate link conversion and basic tracking.

#### Methods:
- `convert_to_affiliate(original_url, affiliate_program=None, product_id=None, session=None)`: Convert URL to affiliate link
- `get_affiliate_link(product_id, retailer_id, session=None)`: Get affiliate link for product
- `track_click(affiliate_link_id, session=None)`: Track click on affiliate link
- `track_conversion(affiliate_link_id, revenue, session=None)`: Track conversion with revenue
- `cleanup_expired_links(session=None)`: Clean up expired affiliate links
- `get_program_stats(program_id, session=None)`: Get statistics for affiliate program

### `AffiliateTracker`

Advanced analytics and reporting class.

#### Methods:
- `get_performance_report(days=30, retailer_id=None, program_id=None, session=None)`: Generate performance report
- `get_conversion_funnel(days=7, retailer_id=None, session=None)`: Analyze conversion funnel
- `detect_performance_anomalies(days=30, threshold=3.0, session=None)`: Detect performance anomalies
- `forecast_revenue(days=30, retailer_id=None, program_id=None, session=None)`: Forecast future revenue
- `sync_with_posted_deals(days=7, session=None)`: Sync with posted deals performance

### Convenience Functions

- `convert_url_to_affiliate(url, program=None, product_id=None)`: Convert URL to affiliate link
- `track_affiliate_click(affiliate_link_id)`: Track affiliate click
- `track_affiliate_conversion(affiliate_link_id, revenue)`: Track affiliate conversion

## Error Handling

The module defines several exception classes:

- `AffiliateConverterError`: Base exception for affiliate conversion errors
- `InvalidURLError`: Raised when URL is invalid or retailer cannot be determined
- `ProgramDisabledError`: Raised when affiliate program is disabled

## Testing

Run the tests with:

```bash
cd tests/python
pytest test_affiliate_engine.py -v
```

Or run the example test script:

```bash
python test_affiliate_engine.py
```

## Examples

See the `examples/` directory for complete integration examples:
- `affiliate_engine_usage.py`: Comprehensive usage examples
- Integration with crawler, deal posting, web server, and analytics dashboard

## Performance Considerations

1. **Caching**: The module caches affiliate links in the database to avoid duplicate conversions
2. **Async Operations**: All database operations are asynchronous for better performance
3. **Batch Operations**: Use batch operations when processing multiple URLs
4. **Connection Pooling**: Uses SQLAlchemy connection pooling for database efficiency

## License

Part of the Deal Sniper AI Platform. See main project license for details.