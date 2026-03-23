# Posting Engine for Deal Sniper AI

The Posting Engine handles posting deals to various social media and messaging platforms with advanced formatting, score filtering, and performance tracking.

## Features

- **Multi-platform Support**: Post to Telegram, Discord, Twitter/X, and TikTok
- **Smart Formatting**: Platform-specific message formatting with templates
- **Score Filtering**: Only post deals that meet platform-specific score thresholds
- **Performance Tracking**: Track clicks, conversions, and revenue with `PostedDeal` model
- **Error Handling**: Automatic retry queue for failed posts
- **Async Operations**: All API calls are async/await with rate limiting
- **Celery Integration**: Background task processing for scheduled posting

## Platform Support

| Platform | Integration Type | Features |
|----------|-----------------|----------|
| **Telegram** | Bot API | HTML formatting, image support, channel posting |
| **Discord** | Webhooks | Rich embeds, fields, thumbnails, formatting |
| **Twitter/X** | API v2 (OAuth 2.0) | Hashtag generation, character limit handling |
| **TikTok** | Manual Export | Export for manual posting with instructions |

## Installation

The posting engine is included in the main Deal Sniper AI installation. Ensure you have the required dependencies:

```bash
pip install httpx sqlalchemy celery python-telegram-bot
```

## Configuration

Configure platforms in `config.yaml`:

```yaml
posting:
  telegram:
    enabled: true
    bot_token: "YOUR_BOT_TOKEN"
    channel_id: "@yourchannel"
    post_format: |
      🔥 <b>DEAL ALERT</b>
      📦 {title}
      💰 <b>Price:</b> ${current_price} (was ${original_price})
      📉 <b>Discount:</b> {discount_percent}% off
      🛒 <b>Link:</b> {affiliate_link}
      📊 <b>Score:</b> {score}/100
      ⏰ <b>Detected:</b> {detection_time}
    min_score: 80

  discord:
    enabled: true
    webhook_url: "https://discord.com/api/webhooks/..."
    post_format: "embed"  # or "plain"
    min_score: 75

  twitter:
    enabled: false  # Requires OAuth 2.0 setup
    api_key: ""
    api_secret: ""
    access_token: ""
    access_secret: ""
    min_score: 85

  tiktok:
    enabled: true
    min_score: 70
```

### Environment Variables

Override configuration with environment variables:

```bash
# Telegram
export DS_POSTING_TELEGRAM_BOT_TOKEN="your_token"
export DS_POSTING_TELEGRAM_CHANNEL_ID="@channel"

# Discord
export DS_POSTING_DISCORD_WEBHOOK_URL="your_webhook"

# Twitter
export DS_POSTING_TWITTER_API_KEY="your_key"
export DS_POSTING_TWITTER_API_SECRET="your_secret"
```

## Usage

### Basic Posting

```python
from deal_sniper_ai.posting_engine.poster import PostingEngine
from uuid import UUID

# Initialize engine
engine = PostingEngine()

# Post a deal to all enabled platforms
deal_id = UUID("your-deal-candidate-id")
result = await engine.post_deal(deal_id)

# Post to specific platforms
result = await engine.post_deal(deal_id, platforms=["telegram", "discord"])

# Check platform status
status = await engine.get_platform_status("telegram")
print(f"Telegram enabled: {status['enabled']}, config valid: {status['config_valid']}")

# Close engine
await engine.close()
```

### Convenience Functions

```python
from deal_sniper_ai.posting_engine.poster import post_deal_to_platforms, get_platform_status

# Simple posting
result = await post_deal_to_platforms(deal_id)

# Check status
status = await get_platform_status("discord")
```

### Message Formatting

```python
from deal_sniper_ai.posting_engine.formatter import PlatformFormatter

formatter = PlatformFormatter()

# Get deal data
deal_data = {
    'title': 'Wireless Headphones',
    'current_price': 129.99,
    'original_price': 199.99,
    'discount_percent': 35.0,
    'affiliate_link': 'https://example.com/link',
    'score': 87.3,
    'retailer': 'amazon',
    'detection_time': '2024-01-15 14:30 UTC'
}

# Format for different platforms
telegram_msg = formatter.format_message(deal_data, 'telegram')
discord_msg = formatter.format_message(deal_data, 'discord')
twitter_msg = formatter.format_message(deal_data, 'twitter')
```

### Platform-Specific Modules

```python
from deal_sniper_ai.posting_engine.platforms import (
    TelegramPoster, DiscordPoster, TwitterPoster, TikTokPoster
)

# Create individual posters
telegram = TelegramPoster(config)
discord = DiscordPoster(config)

# Test connections
if await telegram.test_connection():
    print("Telegram connection successful")

if await discord.test_webhook():
    print("Discord webhook valid")

# Post directly
result = await telegram.post(deal_data, formatted_message)
```

## Celery Tasks

The posting engine includes Celery tasks for background processing:

```python
from deal_sniper_ai.posting_engine.tasks import (
    post_deal_task,
    post_approved_deals_task,
    retry_failed_posts_task,
    test_platform_connections_task
)

# Post a single deal (async)
post_deal_task.delay(str(deal_id), ["telegram", "discord"])

# Post all approved deals
post_approved_deals_task.delay(limit=10)

# Retry failed posts
retry_failed_posts_task.delay()

# Test platform connections
test_platform_connections_task.delay()
```

### Scheduled Tasks

Add to Celery beat schedule in `config.yaml`:

```yaml
celery:
  beat_schedule:
    post_approved_deals:
      task: "deal_sniper_ai.posting_engine.tasks.post_approved_deals_task"
      schedule: 300.0  # Every 5 minutes
      args: [10]  # Limit to 10 deals

    retry_failed_posts:
      task: "deal_sniper_ai.posting_engine.tasks.retry_failed_posts_task"
      schedule: 600.0  # Every 10 minutes

    test_platform_connections:
      task: "deal_sniper_ai.posting_engine.tasks.test_platform_connections_task"
      schedule: 3600.0  # Every hour

    cleanup_old_exports:
      task: "deal_sniper_ai.posting_engine.tasks.cleanup_old_exports_task"
      schedule: 86400.0  # Daily
      args: [30]  # Cleanup files older than 30 days
```

## Database Integration

### PostedDeal Model

The engine automatically creates `PostedDeal` records when posting succeeds:

```python
from deal_sniper_ai.database.models import PostedDeal
from sqlalchemy import select

async with AsyncSessionLocal() as session:
    # Get posted deals
    query = select(PostedDeal).order_by(PostedDeal.posted_at.desc())
    result = await session.execute(query)
    posted_deals = result.scalars().all()

    for deal in posted_deals:
        print(f"Deal {deal.deal_candidate_id} posted to {deal.posted_to}")
        print(f"Clicks: {deal.clicks}, Conversions: {deal.conversions}")
        print(f"Revenue: ${deal.estimated_revenue}")
```

### Performance Tracking

Track clicks and conversions:

```python
from deal_sniper_ai.affiliate_engine.converter import AffiliateConverter

converter = AffiliateConverter()

# Track a click
await converter.track_click(affiliate_link_id)

# Track a conversion with revenue
await converter.track_conversion(affiliate_link_id, Decimal("29.99"))
```

## Template Variables

Available variables for message templates:

| Variable | Description | Example |
|----------|-------------|---------|
| `{title}` | Product title | "Wireless Bluetooth Headphones" |
| `{current_price}` | Current price | "129.99" |
| `{original_price}` | Original price | "199.99" |
| `{discount_percent}` | Discount percentage | "35.0" |
| `{affiliate_link}` | Affiliate link | "https://amazon.com/..." |
| `{score}` | Deal score (0-100) | "87" |
| `{retailer}` | Retailer name | "Amazon" |
| `{detection_time}` | Detection timestamp | "2024-01-15 14:30 UTC" |
| `{hashtags}` | Generated hashtags | "#DealAlert #AmazonDeals" |
| `{quality}` | Quality indicator emoji | "🔥" |

## Error Handling

The engine includes comprehensive error handling:

```python
try:
    result = await engine.post_deal(deal_id)

    if result['failed_platforms']:
        print(f"Failed platforms: {result['failed_platforms']}")

        # Retry failed posts
        retry_result = await engine.retry_failed_posts()
        print(f"Retried: {retry_result['retried']}, Successful: {retry_result['successful']}")

except PlatformDisabledError as e:
    print(f"Platform disabled: {e}")
except InsufficientScoreError as e:
    print(f"Deal score too low: {e}")
except PostingError as e:
    print(f"Posting error: {e}")
```

## Testing

Run the built-in tests:

```bash
# Test the posting engine
python -m deal_sniper_ai.posting_engine.poster

# Test formatter
python -m deal_sniper_ai.posting_engine.formatter

# Test platform connections
python -c "
import asyncio
from deal_sniper_ai.posting_engine.poster import test_all_platforms
results = asyncio.run(test_all_platforms())
print(results)
"
```

## Platform-Specific Notes

### Telegram
- Requires bot token from [@BotFather](https://t.me/BotFather)
- Bot must be added to channel as administrator
- Supports HTML formatting and images

### Discord
- Create webhook in Discord channel settings
- Supports rich embeds with colors and fields
- Webhook URL should be kept secret

### Twitter/X
- Requires Twitter Developer account
- API v2 with OAuth 2.0 authentication
- Character limit: 280 characters

### TikTok
- No public API for automated posting
- Export system creates files for manual posting
- Includes detailed posting instructions

## Troubleshooting

### Common Issues

1. **Telegram: "Bot token invalid"**
   - Verify bot token format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`
   - Ensure bot is active and not banned

2. **Discord: "Invalid webhook"**
   - Check webhook URL format
   - Ensure webhook is not deleted or expired
   - Bot may need proper permissions in channel

3. **Twitter: Authentication failed**
   - Verify API keys and tokens
   - Ensure OAuth 2.0 is properly configured
   - Check rate limits and API permissions

4. **Database: No PostedDeal record**
   - Check if deal candidate exists and is approved
   - Verify database connection
   - Check for transaction rollbacks

### Logging

Enable debug logging for troubleshooting:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Or in configuration:

```yaml
platform:
  log_level: "DEBUG"
```

## Contributing

1. Follow the existing code structure
2. Add type hints for all functions
3. Include docstrings with examples
4. Update documentation
5. Test with multiple platforms

## License

Part of the Deal Sniper AI Platform. See main project license.