"""
agents/email_engine.py -- Brevo transactional email engine.
"""
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import supabase_insert, supabase_select, supabase_update

log = logging.getLogger("email_engine")

FROM_EMAIL = os.environ.get("FROM_EMAIL", "")
FROM_NAME  = os.environ.get("FROM_NAME", "Coupons, Deals & Steals")
SITE_URL   = os.environ.get("SITE_URL", "")
TG_LINK    = os.environ.get("TELEGRAM_INVITE_LINK", "#")
FB_LINK    = os.environ.get("FACEBOOK_GROUP_LINK", "#")
BREVO_KEY  = os.environ.get("BREVO_API_KEY", "")

TEMPLATES_DIR = Path(__file__).parent.parent / "emails" / "templates"


def _api() -> sib_api_v3_sdk.TransactionalEmailsApi:
    cfg = sib_api_v3_sdk.Configuration()
    cfg.api_key["api-key"] = BREVO_KEY
    return sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(cfg))


def _render(template_name: str, replacements: dict) -> str:
    path = TEMPLATES_DIR / template_name
    html = path.read_text(encoding="utf-8")
    for k, v in replacements.items():
        html = html.replace(k, str(v) if v is not None else "")
    return html


def _send(to_email: str, to_name: str, subject: str, html: str,
          template_name: str = "", subscriber_id: int | None = None) -> bool:
    if not BREVO_KEY or not FROM_EMAIL:
        log.warning("Brevo not configured — skipping send to %s", to_email)
        return False
    try:
        msg = sib_api_v3_sdk.SendSmtpEmail(
            sender={"email": FROM_EMAIL, "name": FROM_NAME},
            to=[{"email": to_email, "name": to_name}],
            subject=subject,
            html_content=html,
        )
        _api().send_transac_email(msg)
        supabase_insert("email_log", {
            "subscriber_id": subscriber_id,
            "template_name": template_name,
            "subject": subject,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "status": "sent",
        })
        log.info("Sent '%s' to %s", template_name, to_email)
        return True
    except ApiException as e:
        log.error("Brevo error sending to %s: %s", to_email, e)
        return False


def _unsub_url(email: str) -> str:
    from urllib.parse import quote
    return f"{SITE_URL}/api/unsubscribe?email={quote(email)}"


# ── Transactional senders ─────────────────────────────────────────────────────

def send_confirmation(subscriber: dict) -> bool:
    html = _render("confirmation.html", {
        "{CONFIRM_URL}": subscriber.get("confirm_url", "#"),
        "{FIRST_NAME}":  subscriber.get("first_name", "there"),
        "{UNSUBSCRIBE_URL}": _unsub_url(subscriber.get("email", "")),
        "{SITE_URL}": SITE_URL,
    })
    return _send(subscriber["email"], subscriber.get("first_name", ""),
                 "Confirm your email to get free Amazon deals",
                 html, "confirmation", subscriber.get("id"))


def send_welcome_day1(subscriber: dict) -> bool:
    import base64
    deals = supabase_select("deals")
    top3  = sorted(deals, key=lambda d: d.get("discount_pct") or 0, reverse=True)[:3]
    deals_html = "".join(
        f'<tr><td style="padding:8px"><img src="{d.get("image_url","")}" width="60" height="60" style="object-fit:cover"></td>'
        f'<td style="padding:8px"><b>{d["title"][:60]}</b><br>${d.get("price","N/A")} '
        f'<span style="color:#FF5E1A">{d.get("discount_pct",0)}% off</span></td>'
        f'<td style="padding:8px"><a href="{d.get("amazon_url","#")}" style="background:#FF5E1A;color:#fff;padding:6px 12px;text-decoration:none;border-radius:3px">See Deal</a></td></tr>'
        for d in top3
    )
    ref_link = f"{SITE_URL}/ref/{subscriber.get('referral_code','')}"
    html = _render("welcome_day1.html", {
        "{FIRST_NAME}": subscriber.get("first_name", "there"),
        "{REFERRAL_LINK}": ref_link,
        "{TELEGRAM_LINK}": TG_LINK,
        "{FACEBOOK_LINK}": FB_LINK,
        "{DEALS_HTML}": deals_html,
        "{SITE_URL}": SITE_URL,
        "{UNSUBSCRIBE_URL}": _unsub_url(subscriber.get("email", "")),
    })
    return _send(subscriber["email"], subscriber.get("first_name", ""),
                 f"Welcome to {FROM_NAME} - your deals start now",
                 html, "welcome_day1", subscriber.get("id"))


def send_welcome_day3(subscriber: dict) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    deals = sorted([d for d in supabase_select("deals") if (d.get("fetched_at") or "") >= cutoff],
                   key=lambda d: d.get("discount_pct") or 0, reverse=True)[:5]
    deals_html = "".join(
        f'<tr><td style="padding:6px 8px"><b>{d["title"][:55]}</b></td>'
        f'<td style="padding:6px 8px;color:#FF5E1A;white-space:nowrap">{d.get("discount_pct",0)}% off</td>'
        f'<td style="padding:6px 8px"><a href="{d.get("amazon_url","#")}" style="color:#FF5E1A">See Deal</a></td></tr>'
        for d in deals
    )
    html = _render("welcome_day3.html", {
        "{FIRST_NAME}": subscriber.get("first_name", "there"),
        "{DEALS_HTML}": deals_html,
        "{SITE_URL}": SITE_URL,
        "{UNSUBSCRIBE_URL}": _unsub_url(subscriber.get("email", "")),
    })
    return _send(subscriber["email"], subscriber.get("first_name", ""),
                 "Top 5 deals you may have missed",
                 html, "welcome_day3", subscriber.get("id"))


def send_welcome_day7(subscriber: dict) -> bool:
    ref_link  = f"{SITE_URL}/ref/{subscriber.get('referral_code','')}"
    ref_count = len(supabase_select("referral_clicks", {"referral_code": subscriber.get("referral_code","")}))
    html = _render("welcome_day7.html", {
        "{FIRST_NAME}": subscriber.get("first_name", "there"),
        "{REFERRAL_LINK}": ref_link,
        "{REFERRAL_COUNT}": str(ref_count),
        "{UNSUBSCRIBE_URL}": _unsub_url(subscriber.get("email", "")),
        "{SITE_URL}": SITE_URL,
    })
    return _send(subscriber["email"], subscriber.get("first_name", ""),
                 "You've been with us a week - share and earn",
                 html, "welcome_day7", subscriber.get("id"))


def _best_subject() -> str:
    """Pick best subject pattern from learning_log, fallback to default."""
    rows = sorted(
        [r for r in supabase_select("learning_log") if r.get("metric") == "email_subject_pattern"],
        key=lambda r: r.get("value") or 0, reverse=True
    )
    if rows and rows[0].get("context"):
        return rows[0]["context"].get("subject", "Today's top Amazon deals")
    return "Today's top Amazon deals"


def send_daily_digest() -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    deals = sorted([d for d in supabase_select("deals") if (d.get("fetched_at") or "") >= cutoff],
                   key=lambda d: d.get("discount_pct") or 0, reverse=True)[:5]
    if not deals:
        log.info("No deals for daily digest")
        return 0

    deals_html = "".join(
        f'<tr><td style="padding:8px"><img src="{d.get("image_url","")}" width="60" height="60"></td>'
        f'<td style="padding:8px"><b>{d["title"][:60]}</b><br>'
        f'<span style="color:#FF5E1A">${d.get("price","?")} ({d.get("discount_pct",0)}% off)</span></td>'
        f'<td style="padding:8px"><a href="{d.get("amazon_url","#")}" style="background:#FF5E1A;color:#fff;padding:6px 12px;text-decoration:none;border-radius:3px">See Deal</a></td></tr>'
        for d in deals
    )
    subject  = _best_subject()
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subs     = [s for s in supabase_select("subscribers") if s.get("confirmed") and not s.get("unsubscribed")]
    sent     = 0
    for sub in subs:
        ref_reminder = f'<p style="font-size:13px;color:#888">Share your link and earn: <a href="{SITE_URL}/ref/{sub.get("referral_code","")}" style="color:#FF5E1A">{SITE_URL}/ref/{sub.get("referral_code","")}</a></p>'
        html = _render("daily_digest.html", {
            "{DEALS_HTML}": deals_html,
            "{DATE}": date_str,
            "{REFERRAL_REMINDER}": ref_reminder,
            "{UNSUBSCRIBE_URL}": _unsub_url(sub["email"]),
            "{SITE_URL}": SITE_URL,
        })
        if _send(sub["email"], sub.get("first_name", ""), subject, html, "daily_digest", sub.get("id")):
            sent += 1
    log.info("Daily digest sent to %d subscribers", sent)
    return sent


def send_weekly_top10() -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    deals  = sorted([d for d in supabase_select("deals") if (d.get("fetched_at") or "") >= cutoff],
                    key=lambda d: d.get("discount_pct") or 0, reverse=True)[:10]

    cfg       = supabase_select("config", {"key": "latest_pdf"})
    pdf_name  = Path(cfg[0]["value"]).name if cfg else ""
    pdf_url   = f"{SITE_URL}/pdfs/{pdf_name}" if pdf_name else SITE_URL

    deals_html = "".join(
        f'<tr><td style="padding:6px;font-weight:bold;color:#FF5E1A">#{i+1}</td>'
        f'<td style="padding:6px"><img src="{d.get("image_url","")}" width="50" height="50"></td>'
        f'<td style="padding:6px">{d["title"][:55]}</td>'
        f'<td style="padding:6px;color:#FF5E1A;white-space:nowrap">{d.get("discount_pct",0)}% off</td>'
        f'<td style="padding:6px"><a href="{d.get("amazon_url","#")}" style="color:#FF5E1A">View</a></td></tr>'
        for i, d in enumerate(deals)
    )
    now       = datetime.now(timezone.utc)
    date_range = f"{(now - timedelta(days=7)).strftime('%b %d')} – {now.strftime('%b %d, %Y')}"
    subs      = [s for s in supabase_select("subscribers") if s.get("confirmed") and not s.get("unsubscribed")]
    sent      = 0
    for sub in subs:
        html = _render("weekly_top10.html", {
            "{DEALS_HTML}":  deals_html,
            "{PDF_URL}":     pdf_url,
            "{DATE_RANGE}":  date_range,
            "{UNSUBSCRIBE_URL}": _unsub_url(sub["email"]),
            "{SITE_URL}":    SITE_URL,
        })
        if _send(sub["email"], sub.get("first_name", ""),
                 f"This week's top 10 Amazon deals ({date_range})",
                 html, "weekly_top10", sub.get("id")):
            sent += 1
    log.info("Weekly top10 sent to %d subscribers", sent)
    return sent


def send_pending_drips() -> None:
    """Send day3/day7 welcome drips to eligible subscribers."""
    now  = datetime.now(timezone.utc)
    subs = [s for s in supabase_select("subscribers") if s.get("confirmed") and not s.get("unsubscribed")]
    logs = supabase_select("email_log")
    sent_templates: dict[int, set] = {}
    for row in logs:
        sid = row.get("subscriber_id")
        if sid:
            sent_templates.setdefault(int(sid), set()).add(row.get("template_name", ""))

    for sub in subs:
        sid = sub.get("id")
        confirmed_at = sub.get("confirmed_at")
        if not confirmed_at:
            continue
        try:
            confirmed_dt = datetime.fromisoformat(confirmed_at.replace("Z", "+00:00"))
        except Exception:
            continue
        days_since = (now - confirmed_dt).days
        already    = sent_templates.get(int(sid), set())

        if days_since >= 3 and "welcome_day3" not in already:
            send_welcome_day3(sub)
        if days_since >= 7 and "welcome_day7" not in already:
            send_welcome_day7(sub)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--template", choices=["confirmation","welcome1","day3","day7","daily","weekly"])
    p.add_argument("--email", help="Test recipient email")
    args = p.parse_args()

    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            _logging.FileHandler(log_dir / "email_engine.log", encoding="utf-8"),
            _logging.StreamHandler(sys.stdout),
        ])

    if args.template and args.email:
        test_sub = {"email": args.email, "first_name": "Test", "referral_code": "test1234",
                    "id": 0, "confirm_url": f"{SITE_URL}/api/confirm?token=test"}
        dispatch = {
            "confirmation": lambda: send_confirmation(test_sub),
            "welcome1": lambda: send_welcome_day1(test_sub),
            "day3":  lambda: send_welcome_day3(test_sub),
            "day7":  lambda: send_welcome_day7(test_sub),
            "daily": lambda: send_daily_digest(),
            "weekly": lambda: send_weekly_top10(),
        }
        dispatch[args.template]()
    else:
        send_pending_drips()
