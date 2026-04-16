"""
run_all.py -- master runner. Single persistent process, auto-starts all agents.

Usage:
  python run_all.py                    # normal run
  python run_all.py --dry-run          # no DB writes or deploys
  python run_all.py --agent NAME       # run one agent immediately then exit
  python run_all.py --stats            # print Supabase counts and exit
  python run_all.py --setup            # run setup_check.py and exit
"""
import argparse
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("run_all")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_OWNER_ID  = os.environ.get("TELEGRAM_OWNER_ID", "1711165098").strip()

# Cooldown: don't spam the same error more than once per hour
_last_alert: dict = {}

def tg_alert(message: str, key: str = "generic") -> None:
    """Send a Telegram DM to the owner. Silently fails if Telegram is unreachable."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    last = _last_alert.get(key)
    if last and (now - last).total_seconds() < 3600:
        return
    _last_alert[key] = now

    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_OWNER_ID,
                "text": f"⚠️ Marketing Pipeline\n{message}",
                "parse_mode": "HTML",
            },
            timeout=10,
        )
    except Exception:
        pass  # Never let alerting crash the pipeline


def guarded(fn, alert_key: str):
    """Run fn(), catch any exception, log it and Telegram-alert the owner."""
    try:
        fn()
    except Exception as exc:
        tb = traceback.format_exc(limit=5)
        log.error("%s crashed: %s\n%s", fn.__name__, exc, tb)
        tg_alert(
            f"<b>{fn.__name__}</b> crashed:\n<code>{exc}</code>\n\n{tb[-800:]}",
            key=fn.__name__,
        )


def print_stats():
    from db import supabase_select
    print("=== Supabase Counts ===")
    for t in ["deals", "subscribers", "content_queue", "email_log",
              "referral_clicks", "seo_performance", "learning_log"]:
        print(f"  {t}: {len(supabase_select(t))}")


def main():
    parser = argparse.ArgumentParser(description="Marketing System Master Runner")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--agent", choices=["telegram","content","website","email","pdf","learning"])
    parser.add_argument("--stats",  action="store_true")
    parser.add_argument("--setup",  action="store_true")
    args = parser.parse_args()

    if args.setup:
        import setup_check  # noqa: F401
        return

    if args.stats:
        print_stats()
        return

    from agents import telegram_reader, content_writer, website_publisher
    from agents import email_engine, pdf_generator, learning_engine

    if args.agent:
        dispatch = {
            "telegram": telegram_reader.fetch_new_deals,
            "content":  content_writer.process_pending,
            "website":  website_publisher.publish_pending,
            "email":    email_engine.send_daily_digest,
            "pdf":      pdf_generator.generate_weekly,
            "learning": learning_engine.run,
        }
        log.info("Running single agent: %s", args.agent)
        guarded(dispatch[args.agent], args.agent)
        return

    # Startup alert
    tg_alert("Marketing pipeline started.", key="startup")

    # Immediate startup pass
    log.info("Startup pipeline running...")
    for fn in [telegram_reader.fetch_new_deals,
               content_writer.process_pending,
               website_publisher.publish_pending]:
        guarded(fn, fn.__name__)

    # Scheduler
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    def wrap(fn):
        return lambda: guarded(fn, fn.__name__)

    s = BlockingScheduler(timezone="UTC")
    s.add_job(wrap(telegram_reader.fetch_new_deals),   IntervalTrigger(minutes=15),             id="telegram")
    s.add_job(wrap(content_writer.process_pending),    IntervalTrigger(minutes=15, jitter=300), id="content")
    s.add_job(wrap(website_publisher.publish_pending), IntervalTrigger(minutes=15, jitter=600), id="website")
    s.add_job(wrap(learning_engine.run),               CronTrigger(hour=6),                     id="learning")
    s.add_job(wrap(email_engine.send_daily_digest),    CronTrigger(hour=8),                     id="email_daily")
    s.add_job(wrap(email_engine.send_pending_drips),   IntervalTrigger(hours=1),                id="drips")
    s.add_job(wrap(pdf_generator.generate_weekly),     CronTrigger(day_of_week="sun", hour=8),  id="pdf")
    s.add_job(wrap(email_engine.send_weekly_top10),    CronTrigger(day_of_week="sun", hour=9),  id="email_weekly")

    log.info("Scheduler started. Ctrl+C to stop.")
    try:
        s.start()
    except (KeyboardInterrupt, SystemExit):
        tg_alert("Marketing pipeline stopped.", key="shutdown")
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
