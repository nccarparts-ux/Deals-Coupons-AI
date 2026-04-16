"""
dashboard/app.py -- private admin dashboard + public API endpoints.
Run: python dashboard/app.py  (localhost:5000)
"""
import csv
import io
import json
import os
import re
import sys
import uuid
import base64
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from flask import Flask, request, jsonify, redirect, Response, make_response

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import supabase_insert, supabase_select, supabase_update

app = Flask(__name__)

SITE_URL  = os.environ.get("SITE_URL", "")
TG_LINK   = os.environ.get("TELEGRAM_INVITE_LINK", "#")
FB_LINK   = os.environ.get("FACEBOOK_GROUP_LINK", "#")
WEBSITE   = Path(__file__).parent.parent / "website"
PDFS_DIR  = Path(__file__).parent.parent / "pdfs"
LOGS_DIR  = Path(__file__).parent.parent / "logs"

# ── Base template ─────────────────────────────────────────────────────────────

def _base(title, body, extra_head=""):
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | Deal Sniper Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;600&display=swap" rel="stylesheet">
{extra_head}
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#111114;color:#fff;font-family:'DM Sans',sans-serif;min-height:100vh}}
nav{{background:#0a0a0d;padding:12px 24px;display:flex;gap:24px;align-items:center;border-bottom:1px solid #222}}
nav a{{color:#aaa;text-decoration:none;font-size:14px}}nav a:hover{{color:#FF5E1A}}
nav .brand{{font-family:'Bebas Neue';font-size:22px;color:#FF5E1A;margin-right:16px}}
.main{{padding:32px 24px;max-width:1200px;margin:0 auto}}
h1{{font-family:'Bebas Neue';font-size:40px;margin-bottom:24px}}
h2{{font-family:'Bebas Neue';font-size:28px;margin:28px 0 16px}}
.card{{background:#1a1a1f;border-radius:6px;padding:20px;margin-bottom:16px}}
.stat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:28px}}
.stat{{background:#1a1a1f;border-radius:6px;padding:20px;text-align:center}}
.stat .val{{font-family:'Bebas Neue';font-size:48px;color:#FF5E1A}}
.stat .lbl{{font-size:13px;color:#aaa;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th{{text-align:left;padding:10px 12px;border-bottom:2px solid #333;color:#FF5E1A;font-weight:600}}
td{{padding:8px 12px;border-bottom:1px solid #222}}
tr:hover td{{background:#1f1f25}}
.badge{{display:inline-block;padding:2px 8px;border-radius:3px;font-size:12px;font-weight:600}}
.badge-orange{{background:#FF5E1A;color:#fff}}
.badge-amber{{background:#FFA500;color:#000}}
.btn{{display:inline-block;padding:8px 18px;background:#FF5E1A;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:14px;font-weight:600;text-decoration:none}}
.btn:hover{{background:#e04d0f}}
.btn-sm{{padding:4px 10px;font-size:12px}}
.tabs{{display:flex;gap:8px;margin-bottom:16px}}
.tab{{padding:6px 16px;border:1px solid #333;border-radius:4px;cursor:pointer;font-size:13px}}
.tab.active{{background:#FF5E1A;border-color:#FF5E1A}}
textarea{{width:100%;background:#0d0d10;color:#fff;border:1px solid #333;border-radius:4px;padding:10px;font-size:13px;resize:vertical}}
</style></head><body>
<nav>
  <span class="brand">DEAL SNIPER</span>
  <a href="/">Home</a><a href="/queue">Queue</a><a href="/seo">SEO</a>
  <a href="/subscribers">Subscribers</a><a href="/analytics">Analytics</a>
  <a href="/leads">Leads</a><a href="/learning">Learning</a>
</nav>
<div class="main">{body}</div>
</body></html>"""


def _read_log_tail(name, n=5):
    p = LOGS_DIR / name
    if not p.exists():
        return []
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    return [l for l in lines[-n:] if "ERROR" in l or "FAIL" in l]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def home():
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    deals_today = len([d for d in supabase_select("deals")
                       if (d.get("fetched_at") or "").startswith(today)])
    emails_today = len([e for e in supabase_select("email_log")
                        if (e.get("sent_at") or "").startswith(today)])

    ll = supabase_select("learning_log")
    seo_week = len([r for r in ll if r.get("metric") == "seo_improvement"
                    and (r.get("recorded_at") or "") >= (now - timedelta(days=7)).isoformat()])
    deployed = any(r.get("metric") == "agent_run_website"
                   and (r.get("recorded_at") or "") >= (now - timedelta(hours=24)).isoformat()
                   for r in ll)

    agent_runs = {r["metric"].replace("agent_run_", ""): r["recorded_at"]
                  for r in ll if r.get("metric", "").startswith("agent_run_")}

    errors = []
    for lf in ["telegram_reader.log", "content_writer.log", "website_publisher.log",
               "email_engine.log", "learning_engine.log"]:
        errors += _read_log_tail(lf)

    agent_rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in agent_runs.items())
    error_html = "".join(f'<div style="color:#f66;font-size:13px;padding:4px 0">{e}</div>' for e in errors[-10:]) or "<div style='color:#aaa'>None</div>"

    body = f"""<h1>Dashboard</h1>
<div class="stat-grid">
  <div class="stat"><div class="val">{deals_today}</div><div class="lbl">Deals Today</div></div>
  <div class="stat"><div class="val">{emails_today}</div><div class="lbl">Emails Sent Today</div></div>
  <div class="stat"><div class="val">{'YES' if deployed else 'NO'}</div><div class="lbl">Deployed &lt;24h</div></div>
  <div class="stat"><div class="val">{seo_week}</div><div class="lbl">SEO Improvements (7d)</div></div>
</div>
<h2>Agent Last Runs</h2>
<div class="card"><table><tr><th>Agent</th><th>Last Run</th></tr>{agent_rows}</table></div>
<h2>Recent Errors</h2><div class="card">{error_html}</div>"""
    return _base("Home", body)


@app.route("/queue")
def queue():
    deals = [d for d in supabase_select("deals") if d.get("content_written") and not d.get("social_queued")]
    cards = ""
    for d in deals[:20]:
        cq = supabase_select("content_queue", {"deal_id": d["id"]})
        fb  = next((r["content_text"] for r in cq if r["platform"] == "facebook"), "")
        ig  = next((r["content_text"] for r in cq if r["platform"] == "instagram"), "")
        img = f'<img src="{d["image_url"]}" style="width:80px;height:80px;object-fit:cover;border-radius:4px">' if d.get("image_url") else ""
        cards += f"""<div class="card" style="display:flex;gap:16px;align-items:flex-start">
{img}<div style="flex:1">
<div style="font-weight:600">{d['title'][:80]}</div>
<div style="font-size:13px;color:#FF5E1A">{d.get('discount_pct',0)}% off</div>
<div class="tabs" style="margin-top:12px">
  <div class="tab active" onclick="showTab(this,'fb-{d['id']}')">Facebook</div>
  <div class="tab" onclick="showTab(this,'ig-{d['id']}')">Instagram</div>
</div>
<div id="fb-{d['id']}"><textarea rows="4">{fb}</textarea></div>
<div id="ig-{d['id']}" style="display:none"><textarea rows="4">{ig}</textarea></div>
<div style="margin-top:8px;display:flex;gap:8px">
  <button class="btn btn-sm" onclick="navigator.clipboard.writeText(this.closest('.card').querySelector('textarea:not([style*=none])').value)">Copy</button>
  <button class="btn btn-sm" style="background:#333" onclick="markUsed('{d['id']}')">Mark Used</button>
  <button class="btn btn-sm" style="background:#333" onclick="regen('{d['id']}','facebook')">Regenerate</button>
</div></div></div>"""

    body = f"""<h1>Content Queue</h1>
{cards or '<div class="card" style="color:#aaa">No pending content</div>'}
<script>
function showTab(el,id){{el.closest('.card').querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));el.classList.add('active');el.closest('.card').querySelectorAll('[id^="fb-"],[id^="ig-"]').forEach(d=>d.style.display='none');document.getElementById(id).style.display='block'}}
function markUsed(id){{fetch('/api/mark-used',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{deal_id:id}})}}).then(()=>location.reload())}}
function regen(id,plat){{fetch('/api/regenerate/'+id+'/'+plat,{{method:'POST'}}).then(()=>location.reload())}}
</script>"""
    return _base("Queue", body)


@app.route("/seo")
def seo():
    rows = sorted(supabase_select("seo_performance"), key=lambda r: r.get("avg_position") or 99)
    improvements = [r for r in supabase_select("learning_log") if r.get("metric") == "seo_improvement"][-10:]

    trs = ""
    for r in rows[:100]:
        pos = r.get("avg_position") or 0
        ctr = f"{r['clicks']/r['impressions']*100:.1f}%" if r.get("impressions") else "0%"
        hl  = ' style="background:#3a2800"' if 8 <= pos <= 20 else ""
        trs += f"<tr{hl}><td>{r.get('deal_slug','')}</td><td>{r.get('keyword','')}</td><td>{r.get('impressions',0)}</td><td>{r.get('clicks',0)}</td><td>{'%.1f'%pos}</td><td>{ctr}</td></tr>"

    imp_rows = "".join(f"<tr><td>{r['context'].get('slug','')}</td><td>{r['context'].get('keyword','')}</td><td>{r['context'].get('reasoning','')[:100]}</td><td>{r['recorded_at'][:10]}</td></tr>"
                       for r in improvements if r.get("context"))

    body = f"""<h1>SEO Performance</h1>
<div class="card"><table>
<tr><th>Slug</th><th>Keyword</th><th>Impressions</th><th>Clicks</th><th>Position</th><th>CTR</th></tr>
{trs or '<tr><td colspan="6" style="color:#aaa">No data yet</td></tr>'}
</table></div>
<h2>Auto-Improvements</h2>
<div class="card"><table>
<tr><th>Slug</th><th>Keyword</th><th>Reasoning</th><th>Date</th></tr>
{imp_rows or '<tr><td colspan="4" style="color:#aaa">None yet</td></tr>'}
</table></div>"""
    return _base("SEO", body)


@app.route("/subscribers")
def subscribers():
    subs = supabase_select("subscribers")
    total = len(subs)
    confirmed = sum(1 for s in subs if s.get("confirmed"))
    unsub = sum(1 for s in subs if s.get("unsubscribed"))

    # 30-day growth data
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    by_date: dict[str, int] = {}
    for s in subs:
        d = (s.get("joined_at") or "")[:10]
        if d >= cutoff[:10]:
            by_date[d] = by_date.get(d, 0) + 1
    labels = json.dumps(sorted(by_date))
    values = json.dumps([by_date[k] for k in sorted(by_date)])

    def _mask(email):
        parts = email.split("@") if email else ["", ""]
        return parts[0][:2] + "***@" + (parts[1] if len(parts) > 1 else "")

    recent = subs[-20:][::-1]
    rows_html = "".join(f"<tr><td>{_mask(s.get('email',''))}</td><td>{s.get('first_name','')}</td><td>{(s.get('joined_at') or '')[:10]}</td><td>{'Yes' if s.get('confirmed') else 'No'}</td></tr>"
                        for s in recent)

    chart_head = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>'
    body = f"""<h1>Subscribers</h1>
<div class="stat-grid">
  <div class="stat"><div class="val">{total}</div><div class="lbl">Total</div></div>
  <div class="stat"><div class="val">{confirmed}</div><div class="lbl">Confirmed</div></div>
  <div class="stat"><div class="val">{unsub}</div><div class="lbl">Unsubscribed</div></div>
</div>
<div class="card"><canvas id="growthChart" height="80"></canvas></div>
<div style="margin:16px 0"><a class="btn btn-sm" href="/api/export/subscribers">Export CSV</a></div>
<h2>Recent Subscribers</h2>
<div class="card"><table>
<tr><th>Email</th><th>Name</th><th>Joined</th><th>Confirmed</th></tr>
{rows_html}
</table></div>
<script>
new Chart(document.getElementById('growthChart'),{{type:'bar',data:{{labels:{labels},datasets:[{{label:'New Subscribers',data:{values},backgroundColor:'#FF5E1A'}}]}},options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{beginAtZero:true,ticks:{{color:'#aaa'}}}},x:{{ticks:{{color:'#aaa'}}}}}}}}}}
</script>"""
    return _base("Subscribers", body, chart_head)


@app.route("/analytics")
def analytics():
    deals = supabase_select("deals")
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=30)).isoformat()

    # Deals per day
    by_day: dict[str, int] = {}
    for d in deals:
        day = (d.get("fetched_at") or "")[:10]
        if day >= cutoff[:10]:
            by_day[day] = by_day.get(day, 0) + 1

    # Category counts
    cats: dict[str, int] = {}
    for d in deals:
        c = d.get("category", "other")
        cats[c] = cats.get(c, 0) + 1

    # Top 10 by CTR
    scored = sorted([d for d in deals if d.get("page_views", 0) > 0],
                    key=lambda d: d["click_throughs"] / d["page_views"], reverse=True)[:10]
    top_rows = "".join(
        f"<tr><td>{d['title'][:60]}</td><td>{d.get('category','')}</td>"
        f"<td>{d['click_throughs']}/{d['page_views']}</td>"
        f"<td>{d['click_throughs']/d['page_views']*100:.1f}%</td></tr>"
        for d in scored)

    # Referral leaderboard
    clicks = supabase_select("referral_clicks")
    ref_counts: dict[str, int] = {}
    for c in clicks:
        code = c.get("referral_code", "")
        ref_counts[code] = ref_counts.get(code, 0) + 1
    subs_by_code = {s["referral_code"]: s for s in supabase_select("subscribers") if s.get("referral_code")}
    def _initials(s):
        name = s.get("email", "").split("@")[0]
        return (name[0].upper() + name[-1].upper()) if len(name) >= 2 else name.upper()
    lb_rows = "".join(f"<tr><td>#{i+1}</td><td>{_initials(subs_by_code.get(code, {}))}</td><td>{cnt}</td></tr>"
                      for i, (code, cnt) in enumerate(sorted(ref_counts.items(), key=lambda x: -x[1])[:10]))

    day_labels = json.dumps(sorted(by_day))
    day_vals   = json.dumps([by_day[k] for k in sorted(by_day)])
    cat_labels = json.dumps(list(cats))
    cat_vals   = json.dumps(list(cats.values()))

    email_log = supabase_select("email_log")
    email_rows = "".join(f"<tr><td>{e.get('template_name','')}</td><td>{e.get('subject','')[:60]}</td><td>{(e.get('sent_at') or '')[:16]}</td><td>{e.get('status','')}</td></tr>"
                         for e in email_log[-20:][::-1])

    chart_head = '<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>'
    body = f"""<h1>Analytics</h1>
<div style="display:grid;grid-template-columns:2fr 1fr;gap:16px">
  <div class="card"><canvas id="dealsChart" height="120"></canvas></div>
  <div class="card"><canvas id="catChart"></canvas></div>
</div>
<h2>Top 10 Deals by CTR</h2>
<div class="card"><table>
<tr><th>Title</th><th>Category</th><th>Clicks/Views</th><th>CTR</th></tr>
{top_rows or '<tr><td colspan="4" style="color:#aaa">No data</td></tr>'}
</table></div>
<h2>Referral Leaderboard</h2>
<div class="card"><table>
<tr><th>Rank</th><th>User</th><th>Clicks</th></tr>
{lb_rows or '<tr><td colspan="3" style="color:#aaa">No referrals yet</td></tr>'}
</table></div>
<h2>Recent Emails</h2>
<div class="card"><table>
<tr><th>Template</th><th>Subject</th><th>Sent</th><th>Status</th></tr>
{email_rows or '<tr><td colspan="4" style="color:#aaa">None</td></tr>'}
</table></div>
<script>
new Chart(document.getElementById('dealsChart'),{{type:'bar',data:{{labels:{day_labels},datasets:[{{label:'Deals/Day',data:{day_vals},backgroundColor:'#FF5E1A'}}]}},options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{beginAtZero:true,ticks:{{color:'#aaa'}}}},x:{{ticks:{{color:'#aaa'}}}}}}}}}}
new Chart(document.getElementById('catChart'),{{type:'doughnut',data:{{labels:{cat_labels},datasets:[{{data:{cat_vals},backgroundColor:['#FF5E1A','#e04d0f','#ff8c5a','#c23d00','#ff7040','#993000','#ffaa80','#661f00']}}]}},options:{{plugins:{{legend:{{labels:{{color:'#fff'}}}}}}}}}}
</script>"""
    return _base("Analytics", body, chart_head)


@app.route("/leads")
def leads():
    cfg = supabase_select("config", {"key": "latest_pdf"})
    pdf_path = cfg[0]["value"] if cfg else None
    pdf_name = Path(pdf_path).name if pdf_path else None

    pdfs = sorted(PDFS_DIR.glob("*.pdf"), reverse=True) if PDFS_DIR.exists() else []
    pdf_list = "".join(f'<div style="padding:8px 0;border-bottom:1px solid #222"><a href="/pdfs/{p.name}" style="color:#FF5E1A">{p.name}</a></div>' for p in pdfs)

    body = f"""<h1>PDF Lead Magnet</h1>
<div class="card">
  <div>Latest: <strong>{pdf_name or 'None generated yet'}</strong></div>
  {f'<a class="btn" style="margin-top:12px" href="/pdfs/{pdf_name}">Download</a>' if pdf_name else ''}
  <button class="btn" style="margin-top:12px;margin-left:8px;background:#333" onclick="fetch('/api/generate-pdf',{{method:'POST'}}).then(r=>r.json()).then(d=>alert(d.message))">Regenerate PDF</button>
</div>
<h2>All PDFs</h2>
<div class="card">{pdf_list or '<div style="color:#aaa">None yet</div>'}</div>"""
    return _base("Leads", body)


@app.route("/learning")
def learning():
    rows = sorted(supabase_select("learning_log"), key=lambda r: r.get("recorded_at", ""), reverse=True)[:100]
    trs = "".join(
        f"<tr><td>{r.get('metric','')}</td><td>{r.get('value','')}</td>"
        f"<td style='font-size:12px;color:#aaa'>{str(r.get('context',''))[:120]}</td>"
        f"<td>{(r.get('recorded_at') or '')[:16]}</td></tr>"
        for r in rows)
    body = f"""<h1>Learning Log</h1>
<div class="card"><table>
<tr><th>Metric</th><th>Value</th><th>Context</th><th>Time</th></tr>
{trs or '<tr><td colspan="4" style="color:#aaa">No entries yet</td></tr>'}
</table></div>"""
    return _base("Learning", body)


# ── API ───────────────────────────────────────────────────────────────────────

@app.route("/api/subscribe", methods=["POST"])
def api_subscribe():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({"ok": False, "error": "Invalid email"}), 400
    if supabase_select("subscribers", {"email": email}):
        return jsonify({"ok": False, "error": "Already subscribed"}), 409
    code = str(uuid.uuid4())[:8]
    supabase_insert("subscribers", {
        "email": email,
        "first_name": data.get("first_name", ""),
        "source": data.get("source", "web"),
        "referral_code": code,
        "confirmed": False,
        "joined_at": datetime.now(timezone.utc).isoformat(),
    })
    token = base64.urlsafe_b64encode(email.encode()).decode()
    confirm_url = f"{SITE_URL}/api/confirm?token={token}"
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
        import email_engine
        email_engine.send_confirmation({"email": email, "first_name": data.get("first_name", ""), "confirm_url": confirm_url, "referral_code": code})
    except Exception:
        pass
    return jsonify({"ok": True})


@app.route("/api/confirm")
def api_confirm():
    token = request.args.get("token", "")
    try:
        email = base64.urlsafe_b64decode(token.encode()).decode()
    except Exception:
        return "Invalid token", 400
    supabase_update("subscribers", {"email": email}, {
        "confirmed": True,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    })
    return redirect("/welcome.html")


@app.route("/api/unsubscribe")
def api_unsubscribe():
    email = request.args.get("email", "").strip().lower()
    if email:
        supabase_update("subscribers", {"email": email}, {"unsubscribed": True})
    return "<html><body style='background:#111114;color:#fff;font-family:sans-serif;text-align:center;padding:60px'><h2>You've been unsubscribed.</h2></body></html>"


@app.route("/ref/<code>")
def ref_click(code):
    supabase_insert("referral_clicks", {
        "referral_code": code,
        "clicked_at": datetime.now(timezone.utc).isoformat(),
        "converted": False,
    })
    return redirect(TG_LINK)


@app.route("/leaderboard")
def leaderboard():
    clicks = supabase_select("referral_clicks")
    counts: dict[str, int] = {}
    for c in clicks:
        code = c.get("referral_code", "")
        counts[code] = counts.get(code, 0) + 1
    subs = {s["referral_code"]: s for s in supabase_select("subscribers") if s.get("referral_code")}
    top = sorted(counts.items(), key=lambda x: -x[1])[:10]
    result = []
    for code, cnt in top:
        s = subs.get(code, {})
        email = s.get("email", "")
        name = email.split("@")[0] if email else "?"
        initials = (name[0].upper() + name[-1].upper()) if len(name) >= 2 else name.upper()
        result.append({"initials": initials, "clicks": cnt})
    return jsonify(result)


@app.route("/api/regenerate/<deal_id>/<platform>", methods=["POST"])
def api_regenerate(deal_id, platform):
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
        import content_writer
        content_writer.process_pending(deal_id=deal_id, dry_run=False)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/generate-pdf", methods=["POST"])
def api_generate_pdf():
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
        import pdf_generator
        path = pdf_generator.generate_weekly()
        return jsonify({"ok": True, "message": f"Generated: {path}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/mark-used", methods=["POST"])
def api_mark_used():
    data = request.get_json(silent=True) or {}
    deal_id  = data.get("deal_id")
    platform = data.get("platform")
    if not deal_id:
        return jsonify({"ok": False}), 400
    filters = {"deal_id": deal_id}
    if platform:
        filters["platform"] = platform
    rows = supabase_select("content_queue", filters)
    for row in rows:
        supabase_update("content_queue", {"id": row["id"]}, {
            "status": "used",
            "used_at": datetime.now(timezone.utc).isoformat(),
        })
    all_cq = supabase_select("content_queue", {"deal_id": deal_id})
    if all(r.get("status") == "used" for r in all_cq):
        supabase_update("deals", {"id": deal_id}, {"social_queued": True})
    return jsonify({"ok": True})


@app.route("/api/export/subscribers")
def api_export_subscribers():
    subs = [s for s in supabase_select("subscribers") if s.get("confirmed") and not s.get("unsubscribed")]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["email", "first_name", "joined_at", "referral_code"])
    for s in subs:
        w.writerow([s.get("email"), s.get("first_name"), s.get("joined_at"), s.get("referral_code")])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=subscribers.csv"})


@app.route("/api/deals.json")
def api_deals():
    deals = sorted(supabase_select("deals"), key=lambda d: d.get("fetched_at") or "", reverse=True)[:50]
    fields = ["id", "title", "price", "original_price", "discount_pct",
              "amazon_url", "image_url", "category", "slug", "fetched_at"]
    out = [{f: d.get(f) for f in fields} for d in deals]
    # Also write to website/public/deals.json
    pub = WEBSITE / "public"
    pub.mkdir(exist_ok=True)
    (pub / "deals.json").write_text(json.dumps(out, default=str), encoding="utf-8")
    return jsonify(out)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
