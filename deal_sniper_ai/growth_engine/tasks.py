"""
Celery tasks for Growth Engine scheduled operations.

This module defines Celery tasks for:
- Daily digest generation and distribution
- Leaderboard updates
- Viral deal detection
- Re-engagement campaigns
- Growth analytics reporting
- Weekly blog post writing (run_weekly_blog_writer)
- Weekly email digest sending (run_weekly_email_digest)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from celery import Celery
from sqlalchemy.ext.asyncio import AsyncSession

from ..database.session import AsyncSessionLocal
from .engine import GrowthEngine
from .models import DailyDigestLog

logger = logging.getLogger(__name__)

# Get Celery app from scheduler module
try:
    from ..scheduler.celery_app import celery_app
except ImportError:
    # Fallback: create Celery app if scheduler module doesn't exist
    from ..config.config import get_config as _get_config
    celery_app = Celery('growth_engine')
    _config = _get_config()
    _celery_config = _config.get('celery', {})
    celery_app.conf.update(
        broker_url=_config.get('redis_url', 'redis://localhost:6379/0'),
        result_backend=_config.get('redis_url', 'redis://localhost:6379/0'),
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        worker_concurrency=_celery_config.get('worker_concurrency', 4),
    )


@celery_app.task(name="growth_engine.generate_daily_digest")
def generate_daily_digest_task(date_str: str = None) -> Dict[str, Any]:
    """
    Celery task to generate and distribute daily digest.

    Args:
        date_str: Optional date string in ISO format (defaults to today)

    Returns:
        Task result with digest generation status
    """
    try:
        date = datetime.fromisoformat(date_str) if date_str else datetime.now()

        # Run async operation in sync context
        import asyncio
        result = asyncio.run(_async_generate_daily_digest(date))

        if "error" in result:
            logger.error(f"Failed to generate daily digest: {result['error']}")
            return {
                "status": "error",
                "error": result["error"],
                "timestamp": datetime.now().isoformat()
            }

        logger.info(f"Daily digest generated for {date.date()}: "
                   f"{result.get('deal_count', 0)} deals, "
                   f"{result.get('total_deals', 0)} total")

        # Here you would add logic to distribute the digest
        # via email, push notifications, etc.
        _distribute_digest(result)

        return {
            "status": "success",
            "digest_date": result["date"],
            "deal_count": result["deal_count"],
            "total_deals": result["total_deals"],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in daily digest task: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def _async_generate_daily_digest(date: datetime) -> Dict[str, Any]:
    """Async wrapper for digest generation."""
    engine = GrowthEngine()
    return await engine.generate_daily_digest(date)


def _distribute_digest(digest: Dict[str, Any]) -> None:
    """
    Distribute daily digest to users.

    This is a placeholder implementation. In production, you would:
    1. Get list of users who want daily digest
    2. Personalize digest for each user based on preferences
    3. Send via email, push notifications, etc.
    4. Track delivery and engagement metrics
    """
    # Placeholder implementation
    logger.info(f"Distributing digest to users (placeholder)")
    # In production, integrate with your email/messaging system


@celery_app.task(name="growth_engine.update_leaderboard")
def update_leaderboard_task() -> Dict[str, Any]:
    """
    Celery task to update user leaderboards.

    Returns:
        Task result with leaderboard update status
    """
    try:
        import asyncio
        result = asyncio.run(_async_update_leaderboard())

        if "error" in result:
            logger.error(f"Failed to update leaderboard: {result['error']}")
            return {
                "status": "error",
                "error": result["error"],
                "timestamp": datetime.now().isoformat()
            }

        logger.info(f"Leaderboard updated: {result.get('total_users', 0)} users ranked")

        # Here you could add notifications for users who moved up in ranks
        _notify_leaderboard_changes(result)

        return {
            "status": "success",
            "total_users": result["total_users"],
            "updated_at": result["updated_at"],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in leaderboard update task: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def _async_update_leaderboard() -> Dict[str, Any]:
    """Async wrapper for leaderboard update."""
    engine = GrowthEngine()
    return await engine.update_leaderboard()


def _notify_leaderboard_changes(leaderboard_data: Dict[str, Any]) -> None:
    """
    Notify users about leaderboard changes.

    This is a placeholder implementation.
    """
    # Placeholder implementation
    logger.info("Notifying users about leaderboard changes (placeholder)")


@celery_app.task(name="growth_engine.detect_viral_deals")
def detect_viral_deals_task(hours: int = 24, threshold: float = 1.5) -> Dict[str, Any]:
    """
    Celery task to detect viral deals.

    Args:
        hours: Time window to analyze
        threshold: Growth multiplier threshold

    Returns:
        Task result with viral deals detected
    """
    try:
        import asyncio
        viral_deals = asyncio.run(_async_detect_viral_deals(hours, threshold))

        logger.info(f"Detected {len(viral_deals)} viral deals in past {hours} hours")

        # Take action on viral deals (amplify, feature, etc.)
        if viral_deals:
            _amplify_viral_deals(viral_deals)

        return {
            "status": "success",
            "viral_deals_count": len(viral_deals),
            "hours_analyzed": hours,
            "threshold": threshold,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in viral deal detection task: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def _async_detect_viral_deals(hours: int, threshold: float) -> List[Dict[str, Any]]:
    """Async wrapper for viral deal detection."""
    engine = GrowthEngine()
    return await engine.detect_viral_deals(hours, threshold)


def _amplify_viral_deals(viral_deals: List[Dict[str, Any]]) -> None:
    """
    Amplify viral deals by featuring them, sending alerts, etc.

    This is a placeholder implementation.
    """
    for deal in viral_deals:
        logger.info(f"Amplifying viral deal: {deal.get('title', 'Unknown')} "
                   f"(engagement: {deal.get('engagement_rate', 0)})")
        # In production, you might:
        # 1. Feature the deal on homepage
        # 2. Send push notifications
        # 3. Post to social media
        # 4. Add to special "Trending" section


@celery_app.task(name="growth_engine.check_re_engagement")
def check_re_engagement_task() -> Dict[str, Any]:
    """
    Celery task to check for re-engagement opportunities.

    Returns:
        Task result with re-engagement opportunities found
    """
    try:
        import asyncio
        opportunities = asyncio.run(_async_check_re_engagement())

        logger.info(f"Found {len(opportunities)} re-engagement opportunities")

        # Launch re-engagement campaigns
        if opportunities:
            _launch_re_engagement_campaigns(opportunities)

        return {
            "status": "success",
            "opportunities_count": len(opportunities),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in re-engagement check task: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def _async_check_re_engagement() -> List[Dict[str, Any]]:
    """Async wrapper for re-engagement check."""
    engine = GrowthEngine()
    return await engine.check_re_engagement_opportunities()


def _launch_re_engagement_campaigns(opportunities: List[Dict[str, Any]]) -> None:
    """
    Launch re-engagement campaigns for inactive users.

    This is a placeholder implementation.
    """
    for opp in opportunities:
        logger.info(f"Re-engaging user {opp.get('user_id')} "
                   f"(inactive for {opp.get('days_inactive', 0)} days)")
        # In production, you might:
        # 1. Send personalized email with best deals
        # 2. Offer special incentives
        # 3. Ask for feedback


@celery_app.task(name="growth_engine.generate_growth_report")
def generate_growth_report_task(days: int = 7) -> Dict[str, Any]:
    """
    Celery task to generate growth analytics report.

    Args:
        days: Number of days to include in report

    Returns:
        Task result with report generation status
    """
    try:
        import asyncio
        report = asyncio.run(_async_generate_growth_report(days))

        if "error" in report:
            logger.error(f"Failed to generate growth report: {report['error']}")
            return {
                "status": "error",
                "error": report["error"],
                "timestamp": datetime.now().isoformat()
            }

        logger.info(f"Growth report generated for {days} days")

        # Send report to administrators
        _send_growth_report(report)

        return {
            "status": "success",
            "report_days": days,
            "summary": report.get("summary", {}),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in growth report task: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def _async_generate_growth_report(days: int) -> Dict[str, Any]:
    """Async wrapper for growth report generation."""
    engine = GrowthEngine()
    return await engine.get_growth_metrics(days)


def _send_growth_report(report: Dict[str, Any]) -> None:
    """
    Send growth report to administrators.

    This is a placeholder implementation.
    """
    # Placeholder implementation
    summary = report.get("summary", {})
    logger.info(f"Sending growth report to admins: "
               f"{summary.get('total_referrals', 0)} referrals, "
               f"{summary.get('total_revenue', 0)} revenue")
    # In production, send email to admin team


@celery_app.task(name="growth_engine.process_pending_referrals")
def process_pending_referrals_task() -> Dict[str, Any]:
    """
    Celery task to process pending referrals.

    Checks for referrals that should be marked as completed
    based on user activity (e.g., first purchase).

    Returns:
        Task result with processed referrals count
    """
    try:
        import asyncio
        processed_count = asyncio.run(_async_process_pending_referrals())

        logger.info(f"Processed {processed_count} pending referrals")

        return {
            "status": "success",
            "processed_count": processed_count,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in pending referrals task: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def _async_process_pending_referrals() -> int:
    """
    Process pending referrals and mark as completed when criteria met.

    Returns:
        Number of referrals processed
    """
    async with AsyncSessionLocal() as session:
        try:
            # This is a simplified implementation
            # In production, you would check specific criteria like:
            # - Has the referred user made their first purchase?
            # - Has the referred user been active for X days?
            # - Has the referred user completed their profile?

            # For now, we'll just log and return 0
            # Implement your business logic here

            logger.debug("Processing pending referrals (placeholder)")
            return 0

        except Exception as e:
            logger.error(f"Error processing pending referrals: {e}")
            return 0


@celery_app.task(name="growth_engine.clean_old_data")
def clean_old_data_task(days_to_keep: int = 90) -> Dict[str, Any]:
    """
    Celery task to clean old growth data.

    Args:
        days_to_keep: Number of days of data to keep

    Returns:
        Task result with cleanup statistics
    """
    try:
        import asyncio
        cleanup_stats = asyncio.run(_async_clean_old_data(days_to_keep))

        logger.info(f"Cleaned old growth data: {cleanup_stats}")

        return {
            "status": "success",
            "days_to_keep": days_to_keep,
            "cleanup_stats": cleanup_stats,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in data cleanup task: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def _async_clean_old_data(days_to_keep: int) -> Dict[str, Any]:
    """
    Clean old growth data to prevent database bloat.

    Returns:
        Dictionary with cleanup statistics
    """
    async with AsyncSessionLocal() as session:
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            stats = {}

            # Clean old user engagement data (keep detailed data for 30 days, summary for 90)
            engagement_cutoff = datetime.now() - timedelta(days=30)
            engagement_query = delete(DailyDigestLog).where(
                DailyDigestLog.generated_at < engagement_cutoff
            )
            result = await session.execute(engagement_query)
            stats["old_engagement_records"] = result.rowcount

            # Clean old digest logs (keep for 90 days)
            digest_cutoff = datetime.now() - timedelta(days=90)
            digest_query = delete(DailyDigestLog).where(
                DailyDigestLog.generated_at < digest_cutoff
            )
            result = await session.execute(digest_query)
            stats["old_digest_logs"] = result.rowcount

            await session.commit()

            return stats

        except Exception as e:
            logger.error(f"Error cleaning old data: {e}")
            await session.rollback()
            return {"error": str(e)}


@celery_app.task(name='deal_sniper_ai.growth_engine.tasks.run_seo_article_batch')
def run_seo_article_batch(categories: list = None):
    """
    Generate SEO articles for 1-2 categories per run.
    Scheduled every 3 hours → 8 unique articles per day across 20 categories.
    Automatically picks unwritten categories for today and pushes to GitHub.
    """
    logger.info("Starting Celery task: run_seo_article_batch")

    async def _run():
        from .blog_writer import write_seo_article, SEO_CATEGORIES, _get_next_category
        results = []

        # If explicit categories provided, write those; otherwise auto-select 1 unwritten category
        targets = categories if categories else [_get_next_category()]
        for cat in targets:
            try:
                result = await write_seo_article(category=cat)
                results.append(result)
                logger.info(f"SEO article done: {result.get('slug')} (pushed={result.get('git_pushed')})")
            except Exception as exc:
                logger.error(f"SEO article failed for {cat}: {exc}")

        return results

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_run())


@celery_app.task(name='deal_sniper_ai.growth_engine.tasks.run_weekly_blog_writer')
def run_weekly_blog_writer():
    """
    Celery task to generate and publish the weekly SEO blog post.

    Runs every Sunday (beat schedule configured separately in celery_app.py).
    Calls write_weekly_blog() from blog_writer.py.
    """
    logger.info("Starting Celery task: run_weekly_blog_writer")

    async def _run():
        try:
            from .blog_writer import write_weekly_blog
            result = await write_weekly_blog()
            logger.info(f"Weekly blog writer complete: {result}")
            return result
        except Exception as exc:
            logger.error(f"Error in run_weekly_blog_writer task: {exc}")
            raise

    # Run async function in sync context
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_run())


@celery_app.task(name='deal_sniper_ai.growth_engine.tasks.run_weekly_email_digest')
def run_weekly_email_digest():
    """
    Celery task to send the weekly email digest via Buttondown.

    Runs every Friday (beat schedule configured separately in celery_app.py).
    Calls send_weekly_digest() from email_digest.py.
    """
    logger.info("Starting Celery task: run_weekly_email_digest")

    async def _run():
        try:
            from .email_digest import send_weekly_digest
            result = await send_weekly_digest()
            logger.info(f"Weekly email digest complete: {result}")
            return result
        except Exception as exc:
            logger.error(f"Error in run_weekly_email_digest task: {exc}")
            raise

    # Run async function in sync context
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_run())


# Test function
if __name__ == "__main__":
    # Test the tasks (run synchronously for testing)
    print("Testing Growth Engine Tasks...")

    # Test daily digest generation
    print("\n1. Testing daily digest generation:")
    result = generate_daily_digest_task()
    print(f"   Result: {result.get('status', 'unknown')}")

    # Test leaderboard update
    print("\n2. Testing leaderboard update:")
    result = update_leaderboard_task()
    print(f"   Result: {result.get('status', 'unknown')}")

    # Test viral deal detection
    print("\n3. Testing viral deal detection:")
    result = detect_viral_deals_task(hours=24, threshold=1.5)
    print(f"   Result: {result.get('status', 'unknown')}")

    # Test growth report
    print("\n4. Testing growth report generation:")
    result = generate_growth_report_task(days=7)
    print(f"   Result: {result.get('status', 'unknown')}")

    print("\nGrowth engine tasks test completed!")