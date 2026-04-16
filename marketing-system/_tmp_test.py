"""
agents/website_publisher.py -- Static deal page publisher.
For each deal where website_published=false:
  - Renders deal page via Jinja2 template
  - Writes website/deals/{slug}/index.html
  - Rebuilds website/public/deals.json (last 50 deals)
  - Rebuilds website/sitemap.xml
  - Pings Google Sitemap
  - git add . && git commit && git push
  - vercel --prod
  - Marks website_published=true
"""
import argparse
import json
import logging
import logging.handlers
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv
from jinja2 import Environment, BaseLoader

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import supabase_select, get_unprocessed, mark_done

# ---- Paths ------------------------------------------------------------------

MARKETING_DIR = Path(__file__).parent.parent
REPO_ROOT     = MARKETING_DIR.parent
WEBSITE_DIR   = MARKETING_DIR / "website"
DEALS_DIR     = WEBSITE_DIR / "deals"
PUBLIC_DIR    = WEBSITE_DIR / "public"

# ---- Env --------------------------------------------------------------------

GROUP_NAME      = os.environ.get("GROUP_NAME", "Coupons, Deals & Steals")
SITE_URL        = os.environ.get("SITE_URL", "https://deals-coupons-ai.vercel.app").rstrip("/")
TELEGRAM_INVITE = os.environ.get("TELEGRAM_INVITE_LINK", "https://t.me/Coupons_Deals_Steals")
FACEBOOK_GROUP  = os.environ.get("FACEBOOK_GROUP_LINK", "#")

# ---- Logging ----------------------------------------------------------------

LOG_PATH = MARKETING_DIR / "logs" / "website_publisher.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

log = logging.getLogger("website_publisher")
if not log.handlers:
    log.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh = logging.handlers.RotatingFileHandler(
        LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    log.addHandler(fh)
    log.addHandler(ch)

print("imports OK")
