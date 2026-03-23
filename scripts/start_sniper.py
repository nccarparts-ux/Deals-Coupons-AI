#!/usr/bin/env python3
"""
Deal Sniper AI Platform - Main Entry Point

This script starts the 24/7 Deal Sniper AI Platform with all components:
- FastAPI server (monitoring dashboard and API)
- Celery worker (background task processing)
- Celery beat (scheduled task scheduler)

Usage:
    python start_sniper.py [api|worker|beat|all] [options]

Examples:
    python start_sniper.py all              # Start all components
    python start_sniper.py api              # Start only API server
    python start_sniper.py worker           # Start only Celery worker
    python start_sniper.py beat             # Start only Celery beat scheduler
    python start_sniper.py all --dry-run    # Test mode: new platforms simulate only
    python start_sniper.py all --social-only # New platforms only (posting + growth queues)
    python start_sniper.py --kill-social    # Emergency stop new platform tasks and exit

CLI flags:
    --dry-run      Sets DEAL_SNIPER_DRY_RUN=1. New social platform posters
                   (facebook, pinterest, twitter expansion, tiktok) check this flag
                   via deal_sniper_ai.posting_engine.dry_run.is_dry_run() and return
                   a mock success without calling the real API. Telegram continues
                   to post normally. The wrapper function run_with_dry_run_check()
                   defined in this file can also be used in tests.
    --social-only  Sets DEAL_SNIPER_SOCIAL_ONLY=1. Starts only the 'posting' and
                   'growth' Celery queues instead of the full queue list.
    --kill-social  Calls kill_switch.delay() from deal_sniper_ai.posting_engine.tasks
                   to revoke all pending Phase-9 platform tasks, then exits.

DRY-RUN NOTE FOR POSTER FILES:
    Each new platform poster (facebook_poster.py, pinterest_poster.py,
    twitter_poster.py, tiktok_poster.py) should add the following at the TOP
    of its post() method to honour --dry-run mode:

        from deal_sniper_ai.posting_engine.dry_run import is_dry_run
        if is_dry_run():
            return {'success': True, 'platform': '<platform_name>', 'dry_run': True}

    Since those files are owned by a separate agent, this file provides:
      1. The helper module at deal_sniper_ai/posting_engine/dry_run.py
      2. The wrapper run_with_dry_run_check() below for use in tests/tasks
"""

import argparse
import importlib
import multiprocessing
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Add project root to Python path and load .env immediately
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass  # dotenv not installed; rely on system env vars

# ── Phase-12 helpers ──────────────────────────────────────────────────────────


def run_with_dry_run_check(
    poster_func: Callable[..., Any],
    deal_data: Dict[str, Any],
    message: str,
    platform: str = 'unknown',
) -> Dict[str, Any]:
    """
    Wrapper that checks DEAL_SNIPER_DRY_RUN before calling a real poster.

    Use this in Celery tasks or tests when you cannot edit the poster file
    directly.  If dry-run mode is active it returns a mock success dict
    without touching any external API.

    Args:
        poster_func: An async coroutine function that accepts (deal_data, message).
        deal_data:   Deal data dictionary passed to the poster.
        message:     Formatted message string passed to the poster.
        platform:    Platform name used in the mock response (for logging).

    Returns:
        {'success': True, 'platform': platform, 'dry_run': True} in dry-run mode,
        otherwise the real result from poster_func(deal_data, message).

    Example usage in a Celery task:
        from scripts.start_sniper import run_with_dry_run_check
        result = run_with_dry_run_check(poster.post, deal_data, msg, 'facebook')
    """
    from deal_sniper_ai.posting_engine.dry_run import is_dry_run
    if is_dry_run():
        print(f'[DRY RUN] Simulating post to {platform} (no real API call)')
        return {'success': True, 'platform': platform, 'dry_run': True}

    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(poster_func(deal_data, message))


def check_social_platform_credentials() -> Dict[str, Any]:
    """
    Check all social platform credentials required by Phase-9/12 posters.

    Returns a dict keyed by platform name:
        {
            'facebook':  {'configured': bool, 'missing': [str, ...]},
            'pinterest': {'configured': bool, 'missing': [str, ...]},
            'twitter':   {'configured': bool, 'missing': [str, ...]},
            'tiktok':    {'configured': bool, 'missing': [str, ...]},
            'email':     {'configured': bool, 'missing': [str, ...]},
            'blog':      {'configured': bool, 'missing': [str, ...]},
        }

    Logs [OK] for fully configured platforms, [SKIP] for platforms with
    missing required vars, and [WARN] for optional vars.  Does NOT exit
    on missing credentials — callers decide how to handle unconfigured platforms.
    """
    results: Dict[str, Any] = {}

    def _check(platform: str, required: List[str], optional: List[str] = None) -> None:
        optional = optional or []
        missing_required = [v for v in required if not os.environ.get(v, '').strip()]
        missing_optional = [v for v in optional if not os.environ.get(v, '').strip()]

        if missing_required:
            print(f'[SKIP] {platform}: missing {missing_required}')
            results[platform] = {'configured': False, 'missing': missing_required}
        else:
            if missing_optional:
                print(f'[WARN] {platform}: optional vars missing {missing_optional} — continuing')
            print(f'[OK] {platform}: credentials found')
            results[platform] = {'configured': True, 'missing': []}

    print('[CHECK] Checking social platform credentials...')

    # Facebook
    _check('facebook', ['FACEBOOK_PAGE_ID', 'FACEBOOK_ACCESS_TOKEN'])

    # Pinterest
    _check('pinterest', ['PINTEREST_ACCESS_TOKEN'])

    # Twitter / X  — these may already be set from earlier startup checks;
    # we reuse the same env vars rather than duplicating the check.
    _check(
        'twitter',
        ['TWITTER_API_KEY', 'TWITTER_API_SECRET', 'TWITTER_ACCESS_TOKEN', 'TWITTER_ACCESS_SECRET'],
    )

    # TikTok (uses Pexels for royalty-free video backgrounds)
    _check('tiktok', ['PEXELS_API_KEY'])

    # Email digest via Buttondown
    _check('email', ['BUTTONDOWN_API_KEY'])

    # Blog (optional — warn if missing but do not skip)
    blog_url = os.environ.get('BLOG_BASE_URL', '').strip()
    if not blog_url:
        print('[WARN] blog: BLOG_BASE_URL not set — blog posting will be skipped')
        results['blog'] = {'configured': False, 'missing': ['BLOG_BASE_URL']}
    else:
        print(f'[OK] blog: BLOG_BASE_URL={blog_url}')
        results['blog'] = {'configured': True, 'missing': []}

    configured_count = sum(1 for v in results.values() if v.get('configured'))
    total = len(results)
    print(f'[INFO] Social platforms: {configured_count}/{total} configured')

    return results


def log_startup_event_to_supabase(platform_results: Dict[str, Any]) -> None:
    """
    Insert a startup_event row into performance_metrics via the Supabase REST API.

    Uses the synchronous supabase-py client (no async needed here — startup
    runs before the async Celery/FastAPI event loop is initialised).

    Args:
        platform_results: Return value from check_social_platform_credentials().
    """
    configured_count = float(sum(1 for v in platform_results.values() if v.get('configured')))
    try:
        from deal_sniper_ai.database.supabase_client import get_supabase_client
        sb = get_supabase_client()
        sb.table('performance_metrics').insert({
            'metric_type': 'startup_event',
            'metric_name': 'social_platforms_configured',
            'metric_value': configured_count,
            'platform': 'system',
            'calculated_at': datetime.utcnow().isoformat(),
        }).execute()
        print(f'[OK] Startup event logged to Supabase (configured_platforms={configured_count:.0f})')
    except Exception as exc:
        print(f'[WARN] Could not log startup event to Supabase: {exc}')


def verify_new_task_modules() -> None:
    """
    Verify that the Phase-9/12 Celery task modules are importable.

    Prints [OK] for each successfully imported module and [WARN] for any
    module that raises an ImportError.  Does NOT abort startup on failures —
    the worker will surface errors at runtime when tasks are invoked.
    """
    new_task_modules = [
        'deal_sniper_ai.posting_engine.tasks',
        'deal_sniper_ai.growth_engine.tasks',
        'deal_sniper_ai.signal_scraper.tasks',  # already exists — verifying
    ]
    print('[CHECK] Verifying new Celery task modules...')
    for module in new_task_modules:
        try:
            importlib.import_module(module)
            print(f'[OK] {module}')
        except ImportError as e:
            print(f'[WARN] {module}: {e}')


def start_api():
    """Start the FastAPI server."""
    import uvicorn
    import yaml

    config_path = project_root / "deal_sniper_ai" / "config" / "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    api_config = config['api']
    print(f"[START] Starting Deal Sniper API on {api_config['host']}:{api_config['port']}")

    uvicorn.run(
        "deal_sniper_ai.api.main:app",
        host=api_config['host'],
        port=api_config['port'],
        reload=api_config.get('reload', True),
        workers=api_config.get('workers', 1),
        log_level="info"
    )

def start_worker():
    """Start the Celery worker."""
    from deal_sniper_ai.scheduler.celery_app import start_worker as celery_start_worker

    print("[WORKER] Starting Celery worker...")
    celery_start_worker()

def start_beat():
    """Start the Celery beat scheduler."""
    from deal_sniper_ai.scheduler.celery_app import start_beat as celery_start_beat

    print("[CLOCK] Starting Celery beat scheduler...")
    celery_start_beat()

def start_all():
    """Start all components in separate processes."""
    print("[START] Starting Deal Sniper AI Platform (all components)...")
    print(f"[FOLDER] Project root: {project_root}")

    processes = []

    # Start API server
    api_proc = multiprocessing.Process(target=start_api, name="api-server")
    api_proc.start()
    processes.append(api_proc)
    time.sleep(2)  # Give API time to start

    # Start Celery worker
    worker_proc = multiprocessing.Process(target=start_worker, name="celery-worker")
    worker_proc.start()
    processes.append(worker_proc)
    time.sleep(1)

    # Start Celery beat
    beat_proc = multiprocessing.Process(target=start_beat, name="celery-beat")
    beat_proc.start()
    processes.append(beat_proc)

    print("\n[OK] All components started!")
    print("   API Server:   http://localhost:8000")
    print("   API Docs:     http://localhost:8000/api/docs")
    print("   Dashboard:    http://localhost:8000/dashboard")
    print("   Celery Flower: http://localhost:5555 (if enabled)")
    print("\n[CHART] Monitoring:")
    print("   Health check: curl http://localhost:8000/api/health")
    print("   System stats: curl http://localhost:8000/api/system")
    print("\n[STOP] Press Ctrl+C to stop all components")

    # Signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\n[STOP] Shutting down Deal Sniper AI Platform...")
        for proc in processes:
            if proc.is_alive():
                print(f"   Stopping {proc.name}...")
                proc.terminate()
                proc.join(timeout=5)
                if proc.is_alive():
                    print(f"   Force killing {proc.name}...")
                    proc.kill()
        print("[OK] All components stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Keep main process alive
    try:
        while True:
            time.sleep(1)
            # Monitor processes and restart if needed (basic supervision)
            for i, proc in enumerate(processes):
                if not proc.is_alive():
                    print(f"[WARN] Process {proc.name} died, restarting...")
                    if proc.name == "api-server":
                        new_proc = multiprocessing.Process(target=start_api, name="api-server")
                    elif proc.name == "celery-worker":
                        new_proc = multiprocessing.Process(target=start_worker, name="celery-worker")
                    elif proc.name == "celery-beat":
                        new_proc = multiprocessing.Process(target=start_beat, name="celery-beat")
                    else:
                        continue

                    new_proc.start()
                    processes[i] = new_proc
                    time.sleep(2)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

def check_environment():
    """Check if required environment variables and dependencies are set up."""
    print("[CHECK] Checking environment...")

    # Check Python version
    if sys.version_info < (3, 9):
        print(f"[WARN] Python 3.9+ required, found {sys.version}")
        return False

    # Check configuration file
    config_path = project_root / "deal_sniper_ai" / "config" / "config.yaml"
    if not config_path.exists():
        print(f"[FAIL] Configuration file not found: {config_path}")
        return False

    # Check Supabase REST API connection
    try:
        import yaml
        from deal_sniper_ai.database.supabase_client import get_supabase_client

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        supabase_config = config.get('supabase', {})
        url = supabase_config.get('url') or os.environ.get('SUPABASE_URL')
        anon_key = supabase_config.get('anon_key') or os.environ.get('SUPABASE_KEY')

        if not url or not anon_key:
            print(f"   [FAIL] Supabase URL or key not configured")
            print("   Set SUPABASE_URL and SUPABASE_KEY environment variables or in config.yaml")
            return False

        print(f"   Testing Supabase REST API connection to {url[:30]}...")

        import asyncio
        async def test_supabase():
            client = get_supabase_client()
            # Test by counting rows in a table
            count = await client.count("products")
            print(f"   Found {count} products in database")
            return True

        asyncio.run(test_supabase())
        print("   [OK] Supabase REST API connection successful")
    except Exception as e:
        print(f"   [FAIL] Supabase connection failed: {e}")
        print("   Make sure Supabase project is active and URL/key are correct")
        return False

    # Check Redis connection
    try:
        from redis import Redis
        import yaml

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        redis_config = config['redis']
        print(f"   Testing Redis connection to {redis_config['host']}:{redis_config['port']}...")

        redis_client = Redis(
            host=redis_config['host'],
            port=redis_config['port'],
            password=redis_config.get('password'),
            db=redis_config['db']
        )
        redis_client.ping()
        print("   [OK] Redis connection successful")
    except Exception as e:
        print(f"   [FAIL] Redis connection failed: {e}")
        print("   Make sure Redis is running on the configured port")
        return False

    print("[OK] Environment check passed!")
    return True

def main():
    parser = argparse.ArgumentParser(description="Deal Sniper AI Platform - Main Entry Point")
    parser.add_argument(
        "component",
        choices=["api", "worker", "beat", "all", "check"],
        nargs="?",
        default="all",
        help="Component to start (default: all)"
    )
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="Skip environment checks"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    # ── Phase-12 CLI flags ────────────────────────────────────────────────────
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Test mode: set DEAL_SNIPER_DRY_RUN=1 so new social platform posters "
            "(facebook, pinterest, twitter expansion, tiktok) simulate posts and "
            "return mock success dicts without calling real APIs. "
            "Telegram continues to post normally."
        ),
    )
    parser.add_argument(
        "--social-only",
        action="store_true",
        help=(
            "Set DEAL_SNIPER_SOCIAL_ONLY=1 and start only the 'posting' and 'growth' "
            "Celery queues instead of the full queue list."
        ),
    )
    parser.add_argument(
        "--kill-social",
        action="store_true",
        help=(
            "Trigger the kill_switch Celery task to revoke all pending Phase-9 "
            "platform tasks (facebook, pinterest, twitter, tiktok, daily_deal_planner) "
            "without stopping Telegram.  Exits after triggering."
        ),
    )

    args = parser.parse_args()

    # ── Handle --kill-social first (exit immediately after) ──────────────────
    if args.kill_social:
        print('[KILL SWITCH] All new social platform tasks paused')
        try:
            from deal_sniper_ai.posting_engine.tasks import kill_switch
            kill_switch.delay()
            print('[OK] kill_switch task dispatched to Celery broker')
        except Exception as exc:
            print(f'[WARN] Could not dispatch kill_switch task: {exc}')
            print('       Make sure Celery worker and Redis broker are running.')
        sys.exit(0)

    # ── Apply --dry-run flag ──────────────────────────────────────────────────
    if args.dry_run:
        os.environ['DEAL_SNIPER_DRY_RUN'] = '1'
        print(
            '[DRY RUN] New platforms will simulate posts — Telegram continues normally'
        )

    # ── Apply --social-only flag ──────────────────────────────────────────────
    if args.social_only:
        os.environ['DEAL_SNIPER_SOCIAL_ONLY'] = '1'
        print('[SOCIAL ONLY] Running new platforms only — existing tasks paused')

    # Set log level
    if args.verbose:
        os.environ["LOG_LEVEL"] = "DEBUG"

    # ── Social platform credential check (Phase-12) ───────────────────────────
    platform_results = check_social_platform_credentials()

    # Log startup event to Supabase (best-effort — won't abort on failure)
    log_startup_event_to_supabase(platform_results)

    # ── Verify new Celery task modules (Phase-12) ─────────────────────────────
    verify_new_task_modules()

    # Run environment check unless disabled
    if not args.no_check and args.component != "check":
        if not check_environment():
            print("[FAIL] Environment check failed. Please fix the issues above.")
            sys.exit(1)

    # Start requested component
    if args.component == "api":
        start_api()
    elif args.component == "worker":
        start_worker()
    elif args.component == "beat":
        start_beat()
    elif args.component == "all":
        start_all()
    elif args.component == "check":
        check_environment()
        sys.exit(0)

if __name__ == "__main__":
    main()