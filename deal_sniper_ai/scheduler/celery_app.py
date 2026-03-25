"""
Celery configuration for Deal Sniper AI Platform.

Sets up Redis as message broker and result backend, configures task routes,
and defines the Celery app instance for distributed task processing.
"""

import os
from typing import Dict, Any
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready, worker_shutdown
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load .env before accessing config or env vars
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Load configuration
config_path = Path(__file__).parent.parent / "config" / "config.yaml"
with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# Redis configuration
redis_config = config['redis']
redis_url = f"redis://{redis_config['host']}:{redis_config['port']}/{redis_config['db']}"
if redis_config.get('password'):
    redis_url = f"redis://:{redis_config['password']}@{redis_config['host']}:{redis_config['port']}/{redis_config['db']}"

# Celery app configuration
app = Celery(
    'deal_sniper_ai',
    broker=redis_url,
    backend=redis_url,
    include=[
        'deal_sniper_ai.price_watch_grid.tasks',
        'deal_sniper_ai.coupon_engine.tasks',
        'deal_sniper_ai.anomaly_engine.tasks',
        'deal_sniper_ai.glitch_detector.tasks',
        'deal_sniper_ai.affiliate_engine.tasks',
        'deal_sniper_ai.deal_scorer.tasks',
        'deal_sniper_ai.signal_scraper.tasks',
        'deal_sniper_ai.posting_engine.tasks',
        'deal_sniper_ai.growth_engine.tasks',
        'deal_sniper_ai.analytics_engine.tasks',
        'deal_sniper_ai.database.tasks',
        'deal_sniper_ai.monitoring.tasks',
    ]
)

# Update configuration from config.yaml
app.conf.update(
    # Worker settings
    worker_concurrency=config['celery']['worker_concurrency'],
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    worker_cancel_long_running_tasks_on_connection_loss=True,

    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
    task_reject_on_worker_lost=True,
    task_annotations={
        '*': {'rate_limit': '10/m'}  # Default rate limit
    },

    # Result settings
    result_expires=3600,  # 1 hour
    result_backend_max_retries=3,

    # Queue settings
    task_default_queue='default',
    task_default_exchange='deal_sniper',
    task_default_routing_key='default',
    task_routes={
        'deal_sniper_ai.price_watch_grid.tasks.*': {'queue': 'monitoring'},
        'deal_sniper_ai.coupon_engine.tasks.*': {'queue': 'coupons'},
        'deal_sniper_ai.anomaly_engine.tasks.*': {'queue': 'analytics'},
        'deal_sniper_ai.glitches.tasks.*': {'queue': 'glitches'},
        'deal_sniper_ai.affiliate_engine.tasks.*': {'queue': 'affiliate'},
        'deal_sniper_ai.deal_scorer.tasks.*': {'queue': 'scoring'},
        'deal_sniper_ai.signal_scraper.tasks.*': {'queue': 'community'},
        'deal_sniper_ai.posting_engine.tasks.*': {'queue': 'posting'},
        'deal_sniper_ai.growth_engine.tasks.*': {'queue': 'growth'},
        'deal_sniper_ai.analytics_engine.tasks.*': {'queue': 'analytics'},
        'deal_sniper_ai.database.tasks.*': {'queue': 'maintenance'},
    },

    # Scheduled tasks (Celery Beat)
    beat_schedule={
        # Price monitoring tasks - every 5 minutes (Amazon only)
        'monitor-amazon': {
            'task': 'deal_sniper_ai.price_watch_grid.tasks.monitor_retailer',
            'schedule': 300.0,  # 5 minutes
            'args': ('amazon',),
            'options': {'queue': 'monitoring'}
        },
        # Walmart, Target, Home Depot disabled — enable when configured

        # Deal community monitoring - every 10-15 minutes
        'monitor-slickdeals': {
            'task': 'deal_sniper_ai.signal_scraper.tasks.scrape_deal_community',
            'schedule': 600.0,  # 10 minutes
            'args': ('slickdeals',),
            'options': {'queue': 'community'}
        },
        'monitor-reddit': {
            'task': 'deal_sniper_ai.signal_scraper.tasks.scrape_deal_community',
            'schedule': 900.0,  # 15 minutes
            'args': ('reddit',),
            'options': {'queue': 'community'}
        },

        # Analytics and optimization - daily
        'update-deal-weights': {
            'task': 'deal_sniper_ai.analytics_engine.tasks.update_scoring_weights',
            'schedule': crontab(hour=2, minute=0),  # 2 AM daily
            'options': {'queue': 'analytics'}
        },

        # Admin health check & alerting - every 5 minutes
        'health-check-alert': {
            'task': 'deal_sniper_ai.monitoring.tasks.health_check_task',
            'schedule': 300.0,  # 5 minutes
            'options': {'queue': 'default'}
        },

        # Database maintenance - every 12 hours
        'clean-old-data': {
            'task': 'deal_sniper_ai.database.tasks.clean_old_records',
            'schedule': 43200.0,  # 12 hours
            'options': {'queue': 'maintenance'}
        },

        # Performance metrics collection - hourly
        'collect-performance-metrics': {
            'task': 'deal_sniper_ai.analytics_engine.tasks.collect_performance_metrics',
            'schedule': 3600.0,  # 1 hour
            'options': {'queue': 'analytics'}
        },

        # ── Phase-9: Facebook peak times (9am, 1pm, 7pm UTC) ─────────────────
        'post-facebook-9am': {
            'task': 'deal_sniper_ai.posting_engine.tasks.post_to_facebook',
            'schedule': crontab(hour=9, minute=0),
            'args': (),
            'options': {'queue': 'posting'},
        },
        'post-facebook-1pm': {
            'task': 'deal_sniper_ai.posting_engine.tasks.post_to_facebook',
            'schedule': crontab(hour=13, minute=0),
            'args': (),
            'options': {'queue': 'posting'},
        },
        'post-facebook-7pm': {
            'task': 'deal_sniper_ai.posting_engine.tasks.post_to_facebook',
            'schedule': crontab(hour=19, minute=0),
            'args': (),
            'options': {'queue': 'posting'},
        },

        # ── Phase-9: Pinterest peak times (8pm, 9pm, 10pm UTC) ───────────────
        'post-pinterest-8pm': {
            'task': 'deal_sniper_ai.posting_engine.tasks.post_to_pinterest',
            'schedule': crontab(hour=20, minute=0),
            'args': (),
            'options': {'queue': 'posting'},
        },
        'post-pinterest-9pm': {
            'task': 'deal_sniper_ai.posting_engine.tasks.post_to_pinterest',
            'schedule': crontab(hour=21, minute=0),
            'args': (),
            'options': {'queue': 'posting'},
        },
        'post-pinterest-10pm': {
            'task': 'deal_sniper_ai.posting_engine.tasks.post_to_pinterest',
            'schedule': crontab(hour=22, minute=0),
            'args': (),
            'options': {'queue': 'posting'},
        },

        # ── Phase-9: Twitter/X peak times (8am, 12pm, 5pm, 9pm UTC) ─────────
        'post-twitter-8am': {
            'task': 'deal_sniper_ai.posting_engine.tasks.post_to_twitter_expansion',
            'schedule': crontab(hour=8, minute=0),
            'args': (),
            'options': {'queue': 'posting'},
        },
        'post-twitter-12pm': {
            'task': 'deal_sniper_ai.posting_engine.tasks.post_to_twitter_expansion',
            'schedule': crontab(hour=12, minute=0),
            'args': (),
            'options': {'queue': 'posting'},
        },
        'post-twitter-5pm': {
            'task': 'deal_sniper_ai.posting_engine.tasks.post_to_twitter_expansion',
            'schedule': crontab(hour=17, minute=0),
            'args': (),
            'options': {'queue': 'posting'},
        },
        'post-twitter-9pm': {
            'task': 'deal_sniper_ai.posting_engine.tasks.post_to_twitter_expansion',
            'schedule': crontab(hour=21, minute=0),
            'args': (),
            'options': {'queue': 'posting'},
        },

        # ── TikTok: check every 30 minutes for viral deals ───────────────────
        'notify-tiktok-every-30min': {
            'task': 'deal_sniper_ai.posting_engine.tasks.notify_tiktok_ready',
            'schedule': crontab(minute='*/30'),
            'args': (),
            'options': {'queue': 'posting'},
        },

        # ── Phase-9: Daily deal planner at 6am UTC ────────────────────────────
        'daily-deal-planner': {
            'task': 'deal_sniper_ai.posting_engine.tasks.daily_deal_planner',
            'schedule': crontab(hour=6, minute=0),
            'args': (),
            'options': {'queue': 'posting'},
        },

        # ── SEO blog: new article every 3 hours (8 posts/day, 20 rotating categories) ──
        'seo-article-every-3h': {
            'task': 'deal_sniper_ai.growth_engine.tasks.run_seo_article_batch',
            'schedule': crontab(minute=15, hour='*/3'),  # :15 past every 3rd hour
            'args': (),
            'options': {'queue': 'growth'},
        },

        # ── Weekly deal roundup every Sunday at 3am UTC (top deals from DB) ──
        'weekly-blog-writer': {
            'task': 'deal_sniper_ai.growth_engine.tasks.run_weekly_blog_writer',
            'schedule': crontab(hour=3, minute=0, day_of_week=0),  # 0 = Sunday
            'args': (),
            'options': {'queue': 'growth'},
        },

        # ── Phase-10: Weekly email digest every Friday at 10am UTC ───────────
        'weekly-email-digest': {
            'task': 'deal_sniper_ai.growth_engine.tasks.run_weekly_email_digest',
            'schedule': crontab(hour=10, minute=0, day_of_week=5),  # 5 = Friday
            'args': (),
            'options': {'queue': 'growth'},
        },
    },

    # Timezone
    timezone='UTC',
    enable_utc=True,

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)


def start_worker():
    """Start a Celery worker."""
    argv = [
        'worker',
        '--loglevel=info',
        '--concurrency=4',
        '--queues=default,monitoring,coupons,analytics,glitches,affiliate,scoring,community,posting,growth,maintenance',
        '--hostname=worker@%h',
        '--pool=solo',  # Use solo for Windows compatibility, prefer prefork/gevent for production
    ]
    app.start(argv)


def start_beat():
    """Start Celery Beat scheduler."""
    argv = [
        'beat',
        '--loglevel=info',
        '--schedule=celerybeat-schedule',
    ]
    app.start(argv)


# ── Lifecycle notifications ──────────────────────────────────────────────────

@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Notify admin when the Celery worker comes online."""
    try:
        from deal_sniper_ai.monitoring.alerting import send_admin_alert_sync
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M %Z')
        send_admin_alert_sync(
            f"\u2705 <b>Deal Bot STARTED</b>\n\n"
            f"The Celery worker is online and scanning for deals.\n"
            f"Time: {now}",
            alert_key="bot_started",
            skip_cooldown=True,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not send startup alert: {e}")


@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    """Notify admin when the Celery worker shuts down."""
    try:
        from deal_sniper_ai.monitoring.alerting import send_admin_alert_sync
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo('America/New_York')).strftime('%Y-%m-%d %H:%M %Z')
        send_admin_alert_sync(
            f"\U0001f6d1 <b>Deal Bot STOPPED</b>\n\n"
            f"The Celery worker has shut down. The bot is no longer posting deals.\n\n"
            f"To restart: double-click <code>start_deal_sniper.bat</code>\n"
            f"Time: {now}",
            alert_key="bot_stopped",
            skip_cooldown=True,
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not send shutdown alert: {e}")


# Alias so task modules can import celery_app from this module
celery_app = app


if __name__ == '__main__':
    # For direct execution, start a worker
    start_worker()