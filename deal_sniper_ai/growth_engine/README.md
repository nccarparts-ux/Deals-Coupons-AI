# Growth Engine for Deal Sniper AI Platform

The Growth Engine module implements community growth features for the Deal Sniper AI Platform, including daily digests, viral deal detection, referral programs, leaderboards, and user engagement tracking.

## Features

### 1. Daily Digest Generation
- Compiles top deals from the past 24 hours
- Configurable send time and deal count
- Personalization based on user preferences
- Performance tracking (open rates, click rates)

### 2. Viral Deal Detection
- Monitors engagement metrics in real-time
- Detects rapidly growing deals based on engagement rate
- Configurable thresholds for viral classification
- Automatic amplification of viral content

### 3. Referral Program
- Tracks user referrals and rewards
- Configurable reward amounts
- Referral link generation
- Status tracking (pending, completed, rejected)

### 4. Leaderboards
- User ranking based on activity metrics
- Multiple ranking categories (referrals, engagement, revenue)
- Daily updates with rank changes
- Public/private visibility controls

### 5. Community Engagement
- User engagement tracking (clicks, shares, saves, votes)
- Community voting system for deal quality
- Personalized deal recommendations
- User preferences and personalization

### 6. User Onboarding & Retention
- Welcome sequences for new users
- Re-engagement campaigns for inactive users
- Achievement system with badges
- Progress tracking and rewards

### 7. Growth Analytics
- User acquisition and retention metrics
- Engagement trends and patterns
- Revenue tracking and forecasting
- Performance reporting

## Installation

The Growth Engine is included in the main Deal Sniper AI Platform. To set it up:

1. **Apply Database Migration**:
   ```bash
   supabase db push
   ```
   This creates the necessary tables for growth features.

2. **Configure Settings**:
   Update `config.yaml` in the growth section:
   ```yaml
   growth:
     daily_digest:
       enabled: true
       send_time: "18:00"  # 6 PM local time
       max_deals_per_digest: 10
     referral_program:
       enabled: false
       reward_per_referral: 1.0  # $1 credit per successful referral
     leaderboard:
       enabled: true
       update_interval: 86400  # Daily
   ```

3. **Start Celery Workers**:
   ```bash
   celery -A deal_sniper_ai.scheduler.celery_app worker --loglevel=info
   celery -A deal_sniper_ai.scheduler.celery_app beat --loglevel=info
   ```

## Database Schema

The Growth Engine adds the following tables:

### Core Tables
- `user_engagement` - Tracks user actions (clicks, shares, saves, votes)
- `referrals` - Tracks user referrals and rewards
- `leaderboard_entries` - User rankings for various metrics
- `user_preferences` - User personalization settings

### Analytics Tables
- `daily_digest_logs` - History of generated daily digests
- `viral_deal_alerts` - Records of detected viral deals
- `community_votes` - Community voting on deals
- `user_achievements` - User achievements and badges

## Usage

### Basic Usage

```python
from deal_sniper_ai.growth_engine import GrowthEngine

# Initialize the engine
engine = GrowthEngine()

# Generate daily digest
digest = await engine.generate_daily_digest()

# Detect viral deals
viral_deals = await engine.detect_viral_deals(hours=24, threshold=1.5)

# Update leaderboard
leaderboard = await engine.update_leaderboard()

# Get growth metrics
metrics = await engine.get_growth_metrics(days=30)

# Track user engagement
await engine.track_user_engagement(
    user_id=user_uuid,
    action="click",
    deal_id=deal_uuid,
    metadata={"source": "web"}
)

# Get personalized recommendations
recommendations = await engine.get_user_recommendations(
    user_id=user_uuid,
    limit=10
)
```

### Scheduled Tasks

The Growth Engine includes Celery tasks for scheduled operations:

```python
from deal_sniper_ai.growth_engine.tasks import (
    generate_daily_digest_task,
    update_leaderboard_task,
    detect_viral_deals_task,
    check_re_engagement_task,
    generate_growth_report_task
)

# Manual task execution (for testing)
result = generate_daily_digest_task()
```

### Configuration

#### Environment Variables
- `DS_GROWTH_DAILY_DIGEST_ENABLED` - Enable/disable daily digest
- `DS_GROWTH_DAILY_DIGEST_SEND_TIME` - Daily digest send time (HH:MM)
- `DS_GROWTH_REFERRAL_PROGRAM_ENABLED` - Enable/disable referral program
- `DS_GROWTH_REFERRAL_REWARD_PER_REFERRAL` - Reward amount per referral

#### Celery Schedule
Tasks are automatically scheduled via Celery Beat:
- Daily digest: Runs daily at configured time
- Leaderboard update: Runs daily
- Viral deal detection: Runs hourly
- Re-engagement check: Runs daily
- Growth report: Runs weekly
- Referral processing: Runs hourly

## API Integration

### FastAPI Endpoints (Example)

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from deal_sniper_ai.growth_engine import GrowthEngine

router = APIRouter(prefix="/growth", tags=["growth"])

@router.get("/digest/today")
async def get_todays_digest(
    engine: GrowthEngine = Depends(lambda: GrowthEngine())
):
    """Get today's daily digest."""
    return await engine.generate_daily_digest()

@router.get("/leaderboard")
async def get_leaderboard(
    engine: GrowthEngine = Depends(lambda: GrowthEngine())
):
    """Get current leaderboard."""
    return await engine.update_leaderboard()

@router.post("/engagement")
async def track_engagement(
    user_id: UUID,
    action: str,
    deal_id: Optional[UUID] = None,
    metadata: Optional[Dict] = None,
    engine: GrowthEngine = Depends(lambda: GrowthEngine())
):
    """Track user engagement."""
    success = await engine.track_user_engagement(
        user_id=user_id,
        action=action,
        deal_id=deal_id,
        metadata=metadata
    )
    return {"success": success}

@router.get("/recommendations/{user_id}")
async def get_recommendations(
    user_id: UUID,
    limit: int = 10,
    engine: GrowthEngine = Depends(lambda: GrowthEngine())
):
    """Get personalized recommendations for a user."""
    return await engine.get_user_recommendations(
        user_id=user_id,
        limit=limit
    )
```

## Testing

Run the test suite:

```bash
cd deal_sniper_ai/growth_engine
python -m pytest test_growth_engine.py -v
```

Or run the comprehensive test script:

```bash
python -m deal_sniper_ai.growth_engine.test_growth_engine
```

## Monitoring

### Key Metrics to Monitor
1. **Digest Performance**: Open rates, click rates, conversion rates
2. **Referral Program**: Referral completion rate, reward distribution
3. **Leaderboard Engagement**: User participation, rank changes
4. **Viral Deals**: Detection accuracy, amplification effectiveness
5. **User Retention**: Churn rate, re-engagement success

### Logging
The Growth Engine uses structured logging with the following loggers:
- `deal_sniper_ai.growth_engine.engine` - Core engine operations
- `deal_sniper_ai.growth_engine.tasks` - Scheduled task execution
- `deal_sniper_ai.growth_engine.models` - Database operations

## Troubleshooting

### Common Issues

1. **Daily digest not sending**:
   - Check Celery beat scheduler is running
   - Verify `growth.daily_digest.enabled` is `true` in config
   - Check database connection for user preferences

2. **Referrals not tracking**:
   - Verify `growth.referral_program.enabled` is `true`
   - Check RLS policies allow referral creation
   - Ensure user IDs are valid UUIDs

3. **Leaderboard not updating**:
   - Check Celery task execution logs
   - Verify there are users with engagement data
   - Check database permissions for leaderboard_entries table

4. **Viral deals not detecting**:
   - Ensure there are posted deals with engagement data
   - Check threshold configuration (default: 1.5x normal engagement)
   - Verify the hourly task is running

### Database Migration Issues
If tables don't exist, apply the migration:
```bash
supabase db push --file supabase/migrations/20250319000000_growth_engine_schema.sql
```

## Performance Considerations

1. **Database Indexing**: All frequently queried columns are indexed
2. **Async Operations**: All database operations use async/await
3. **Batch Processing**: Large operations are batched to prevent timeouts
4. **Caching**: Consider adding Redis caching for leaderboards and digests
5. **Partitioning**: For large-scale deployment, consider table partitioning by date

## Security

- Row Level Security (RLS) is enabled on all tables
- Users can only access their own data (except public leaderboards)
- Referral rewards require manual approval before payout
- Sensitive user data is never logged

## Extending the Growth Engine

### Adding New Metrics
1. Add new metric type to `LeaderboardEntry.metric_type` CHECK constraint
2. Update `update_leaderboard()` method to calculate the new metric
3. Add corresponding tracking in user engagement

### Custom Digest Templates
1. Create new template formatter in `engine.py`
2. Add template selection to user preferences
3. Update digest generation to use selected template

### Additional Engagement Actions
1. Add new action type to `UserEngagement.action` CHECK constraint
2. Update engagement tracking to handle the new action
3. Add corresponding analytics in growth metrics

## License

Part of the Deal Sniper AI Platform. See main project license.