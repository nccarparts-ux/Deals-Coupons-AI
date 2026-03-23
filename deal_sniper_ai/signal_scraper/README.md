# Signal Scraper Module

The Signal Scraper module monitors deal communities (Slickdeals, Reddit, Telegram) as secondary signal sources to complement direct price monitoring in the Deal Sniper AI Platform.

## Features

- **Community Monitoring**: Scrapes deals from multiple communities:
  - **Slickdeals**: RSS feed parsing
  - **Reddit**: API integration for subreddits (buildapcsales, GameDeals, etc.)
  - **Telegram**: Channel monitoring (requires API keys)
- **Deal Signal Extraction**: Extracts structured deal data from unstructured text
- **Product Matching**: Fuzzy matching of community deals with existing products
- **Signal Strength Calculation**: Calculates community signal strength (0-1) for deal scoring
- **Anti-Blocking Measures**: Respects rate limits and implements proper scraping etiquette
- **Database Integration**: Stores and updates community signals in the database

## Architecture

### Core Components

1. **SignalScraper** (`scraper.py`): Main orchestrator class
2. **CommunitySignal**: Data class representing a deal signal from a community
3. **Parsers** (`parsers.py`): Community-specific parsing logic
4. **Matchers** (`matcher.py`): Product matching algorithms
5. **Celery Tasks** (`tasks.py`): Scheduled scraping tasks

### Data Flow

1. **Scraping**: Fetch posts from enabled communities
2. **Parsing**: Extract structured deal data (prices, retailer, coupons, etc.)
3. **Matching**: Match extracted deals with existing products in database
4. **Scoring**: Calculate community signal strength based on engagement metrics
5. **Integration**: Update deal candidates with community signal scores

## Configuration

The module reads from `config.yaml` under the `deal_communities` section:

```yaml
deal_communities:
  slickdeals:
    enabled: true
    base_url: "https://slickdeals.net"
    rss_url: "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1"
    scrape_interval: 600  # seconds
  reddit:
    enabled: true
    base_url: "https://www.reddit.com"
    subreddits:
      - "buildapcsales"
      - "GameDeals"
      - "PS4Deals"
      - "NintendoSwitchDeals"
    scrape_interval: 900
  telegram:
    enabled: false  # Requires API keys
    channels:
      - "@dealschannel"
    scrape_interval: 300
```

### Environment Variables

For Reddit API integration, set these environment variables:
- `REDDIT_CLIENT_ID`: Your Reddit app client ID
- `REDDIT_CLIENT_SECRET`: Your Reddit app client secret
- `REDDIT_USER_AGENT`: User agent string (e.g., "DealSniperAI/0.1.0")

## Usage

### Basic Usage

```python
import asyncio
from deal_sniper_ai.signal_scraper import create_signal_scraper

async def main():
    # Create scraper instance
    scraper = await create_signal_scraper()

    # Scrape a specific community
    signals = await scraper.scrape_community('slickdeals')

    # Process signals
    for signal in signals:
        matched_ids = await scraper.match_with_products(signal)
        if matched_ids:
            # Update deal candidates
            await scraper.update_deal_candidates_with_signals(matched_ids, [signal])

    # Or run a complete scraping cycle
    await scraper.run_scraping_cycle()

    # Clean up
    await scraper.close()

asyncio.run(main())
```

### Celery Integration

The module includes Celery tasks for scheduled scraping:

```python
# Run as Celery task
from deal_sniper_ai.signal_scraper.tasks import scrape_deal_community

# Scrape a specific community
scrape_deal_community.delay('slickdeals')

# Scrape all enabled communities
scrape_all_communities.delay()

# Run complete scraping cycle
run_signal_scraping_cycle.delay()
```

### Scheduled Scraping

Configure in `config.yaml` Celery beat schedule:

```yaml
celery:
  beat_schedule:
    monitor_slickdeals:
      task: "deal_sniper_ai.signal_scraper.tasks.scrape_deal_community"
      schedule: 600.0  # 10 minutes
      args: ["slickdeals"]
    monitor_reddit:
      task: "deal_sniper_ai.signal_scraper.tasks.scrape_deal_community"
      schedule: 900.0  # 15 minutes
      args: ["reddit"]
```

## Matching Strategies

The module uses multiple matching strategies in order of priority:

1. **Exact SKU/UPC Match**: Match by exact SKU or UPC code
2. **Retailer Product ID Match**: Extract product ID from URL and match
3. **URL Match**: Exact URL matching
4. **Fuzzy Title Matching**: Fuzzy string matching on product titles
5. **Price & Retailer Match**: Match by price range and retailer

## Signal Strength Calculation

Community signal strength (0-1) is calculated based on:

1. **Velocity**: Upvotes/comments per hour
2. **Recency**: Time since posting (more recent = stronger)
3. **Community Reputation**: Authority of the community
4. **Author Credibility**: User flair/reputation
5. **Engagement Quality**: Comments/upvotes ratio

The signal strength is used to adjust deal scores in the `community_signal` component.

## Error Handling

- **Rate Limiting**: Respects community `scrape_interval` settings
- **Network Errors**: Retry logic with exponential backoff
- **Parsing Errors**: Graceful degradation with logging
- **API Limits**: Respects Reddit API rate limits

## Testing

Run the test suite:

```bash
python test_signal_scraper.py
```

Or run specific tests:

```python
# Test parsers
python -c "from deal_sniper_ai.signal_scraper.parsers import extract_prices; print(extract_prices('Was $99, now $79'))"

# Test matcher
python -c "from deal_sniper_ai.signal_scraper.matcher import ProductMatcher; print('Matcher imported successfully')"
```

## Dependencies

See `requirements_signal_scraper.txt` for additional dependencies:

- `aiohttp`: HTTP client for RSS feeds
- `feedparser`: RSS feed parsing
- `asyncpraw`: Reddit API client (async)
- `thefuzz`: Fuzzy string matching
- `beautifulsoup4`: HTML parsing (optional)
- `dateparser`: Date parsing (optional)

## Extending

### Adding a New Community Parser

1. Create a new parser class in `parsers.py`:

```python
class NewCommunityParser(BaseCommunityParser):
    def parse(self, raw_data):
        # Parse raw data into CommunitySignal
        pass
```

2. Register it in `ParserFactory`:

```python
ParserFactory.register_parser('new_community', NewCommunityParser)
```

### Custom Matching Logic

Override the `ProductMatcher` class:

```python
class CustomMatcher(ProductMatcher):
    async def match_signal(self, signal):
        # Custom matching logic
        pass
```

## Performance Considerations

- **Batch Processing**: Use `BatchProductMatcher` for efficient bulk matching
- **Caching**: Consider caching product data for fuzzy matching
- **Rate Limiting**: Configure appropriate `scrape_interval` values
- **Database Indexing**: Ensure proper indexes on `Product.sku`, `Product.upc`, `Product.retailer_product_id`

## Monitoring

The module logs to the `deal_sniper_ai.signal_scraper` logger and stores performance metrics in the `performance_metrics` table with `metric_type = 'signal_scraping'`.

Key metrics:
- Success rate per community
- Number of signals scraped
- Matching success rate
- Signal strength distribution