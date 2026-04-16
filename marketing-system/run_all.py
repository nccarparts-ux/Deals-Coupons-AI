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
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("run_all")


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
            "telegram": lambda: telegram_reader.fetch_new_deals(),
            "content":  lambda: content_writer.process_pending(),
            "website":  lambda: website_publisher.publish_pending(),
            "email":    lambda: email_engine.send_daily_digest(),
            "pdf":      lambda: pdf_generator.generate_weekly(),
            "learning": lambda: learning_engine.run(),
        }
        log.info("Running single agent: %s", args.agent)
        dispatch[args.agent]()
        return

    # Immediate startup pass
    log.info("Startup pipeline running...")
    for fn in [telegram_reader.fetch_new_deals,
               content_writer.process_pending,
               website_publisher.publish_pending]:
        try:
            fn()
        except Exception as exc:
            log.error("%s startup error: %s", fn.__name__, exc)

    # Scheduler
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    s = BlockingScheduler(timezone="UTC")
    s.add_job(telegram_reader.fetch_new_deals,   IntervalTrigger(minutes=15),             id="telegram")
    s.add_job(content_writer.process_pending,    IntervalTrigger(minutes=15, jitter=300), id="content")
    s.add_job(website_publisher.publish_pending, IntervalTrigger(minutes=15, jitter=600), id="website")
    s.add_job(learning_engine.run,               CronTrigger(hour=6),                     id="learning")
    s.add_job(email_engine.send_daily_digest,    CronTrigger(hour=8),                     id="email_daily")
    s.add_job(email_engine.send_pending_drips,   IntervalTrigger(hours=1),                id="drips")
    s.add_job(pdf_generator.generate_weekly,     CronTrigger(day_of_week="sun", hour=8),  id="pdf")
    s.add_job(email_engine.send_weekly_top10,    CronTrigger(day_of_week="sun", hour=9),  id="email_weekly")

    log.info("Scheduler started. Ctrl+C to stop.")
    try:
        s.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
