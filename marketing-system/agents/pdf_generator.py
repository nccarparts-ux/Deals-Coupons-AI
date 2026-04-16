"""
agents/pdf_generator.py -- weekly top-10 deals PDF generator.
"""
import io
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import supabase_insert, supabase_select, supabase_update

log = logging.getLogger("pdf_generator")

GROUP_NAME = os.environ.get("GROUP_NAME", "Coupons, Deals & Steals")
SITE_URL   = os.environ.get("SITE_URL", "")
TG_LINK    = os.environ.get("TELEGRAM_INVITE_LINK", "")
AUTO_EMAIL = os.environ.get("AUTO_EMAIL_PDF", "false").lower() == "true"

BG      = colors.HexColor("#111114")
ACCENT  = colors.HexColor("#FF5E1A")
WHITE   = colors.white
GREY    = colors.HexColor("#AAAAAA")
PDFS_DIR = Path(__file__).parent.parent / "pdfs"


def _qr_image(url: str, size: int = 80):
    try:
        import qrcode
        qr = qrcode.make(url)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        buf.seek(0)
        return Image(buf, width=size, height=size)
    except Exception:
        return None


def _remote_image(url: str, w: float, h: float):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        buf = io.BytesIO(r.content)
        return Image(buf, width=w, height=h)
    except Exception:
        return None


def _placeholder(w: float, h: float):
    from reportlab.platypus import Drawing
    from reportlab.graphics.shapes import Rect
    d = Drawing(w, h)
    d.add(Rect(0, 0, w, h, fillColor=colors.HexColor("#333333"), strokeColor=None))
    return d


def _cover(story, deals, date_range):
    story.append(Spacer(1, 1.5 * inch))
    story.append(Paragraph(
        '<font color="#FF5E1A">TOP 10</font>',
        ParagraphStyle("cover_top", fontName="Helvetica-Bold", fontSize=72,
                       textColor=ACCENT, alignment=TA_CENTER)))
    story.append(Paragraph(
        "Amazon Deals This Week",
        ParagraphStyle("cover_title", fontName="Helvetica-Bold", fontSize=32,
                       textColor=WHITE, alignment=TA_CENTER, spaceAfter=12)))
    story.append(Paragraph(
        date_range,
        ParagraphStyle("cover_date", fontName="Helvetica", fontSize=16,
                       textColor=GREY, alignment=TA_CENTER, spaceAfter=24)))
    story.append(Paragraph(
        GROUP_NAME,
        ParagraphStyle("cover_group", fontName="Helvetica-Bold", fontSize=18,
                       textColor=ACCENT, alignment=TA_CENTER, spaceAfter=8)))
    if SITE_URL:
        story.append(Paragraph(
            SITE_URL,
            ParagraphStyle("cover_url", fontName="Helvetica", fontSize=13,
                           textColor=GREY, alignment=TA_CENTER)))
    if TG_LINK:
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph(
            f"Free alerts: {TG_LINK}",
            ParagraphStyle("cover_tg", fontName="Helvetica", fontSize=12,
                           textColor=WHITE, alignment=TA_CENTER)))
    story.append(PageBreak())


def _deal_block(story, deal, idx):
    title_style = ParagraphStyle("dt", fontName="Helvetica-Bold", fontSize=14, textColor=WHITE, spaceAfter=4)
    body_style  = ParagraphStyle("db", fontName="Helvetica", fontSize=11, textColor=GREY, spaceAfter=6)
    price_style = ParagraphStyle("dp", fontName="Helvetica-Bold", fontSize=13, textColor=ACCENT, spaceAfter=4)

    img = _remote_image(deal.get("image_url"), 1.2 * inch, 1.2 * inch) if deal.get("image_url") else None
    if img is None:
        img = _placeholder(1.2 * inch, 1.2 * inch)

    qr = _qr_image(deal.get("amazon_url", SITE_URL), 80)

    price_text = ""
    if deal.get("price") and deal.get("original_price"):
        price_text = f"Was ${deal['original_price']:.2f}  Now ${deal['price']:.2f} — {deal.get('discount_pct',0)}% off"
    elif deal.get("price"):
        price_text = f"${deal['price']:.2f}"

    desc = (deal.get("raw_text") or "")[:200].replace("\n", " ")

    inner = [
        [Paragraph(f"#{idx}  {deal['title'][:80]}", title_style)],
        [Paragraph(price_text, price_style)],
        [Paragraph(desc, body_style)],
    ]
    text_table = Table(inner, colWidths=[4.5 * inch])
    text_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))

    qr_cell = qr if qr else Paragraph("", body_style)
    row = [[img, text_table, qr_cell]]
    t = Table(row, colWidths=[1.4 * inch, 4.6 * inch, 1.2 * inch])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1a1a1f")),
        ("ROUNDEDCORNERS", [4]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2 * inch))


def _back_page(story):
    story.append(PageBreak())
    story.append(Spacer(1, 1.2 * inch))
    story.append(Paragraph(
        "Never Miss a Deal",
        ParagraphStyle("back_h", fontName="Helvetica-Bold", fontSize=36,
                       textColor=WHITE, alignment=TA_CENTER, spaceAfter=16)))
    story.append(Paragraph(
        "Join thousands of savvy shoppers getting free Amazon deal alerts.",
        ParagraphStyle("back_b", fontName="Helvetica", fontSize=14,
                       textColor=GREY, alignment=TA_CENTER, spaceAfter=24)))
    if TG_LINK:
        qr = _qr_image(TG_LINK, 100)
        if qr:
            qr.hAlign = "CENTER"
            story.append(qr)
        story.append(Paragraph(TG_LINK, ParagraphStyle("back_tg", fontName="Helvetica",
                       fontSize=12, textColor=ACCENT, alignment=TA_CENTER, spaceAfter=8)))
    if SITE_URL:
        story.append(Paragraph(SITE_URL, ParagraphStyle("back_site", fontName="Helvetica",
                       fontSize=12, textColor=GREY, alignment=TA_CENTER, spaceAfter=24)))
    story.append(Paragraph(
        "Not affiliated with Amazon. Amazon and the Amazon logo are trademarks of Amazon.com, Inc.",
        ParagraphStyle("disc", fontName="Helvetica", fontSize=9, textColor=GREY, alignment=TA_CENTER)))


def _bg_canvas(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG)
    canvas.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)
    canvas.restoreState()


def generate_weekly(dry_run: bool = False, output: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=7)).isoformat()
    deals = sorted(
        [d for d in supabase_select("deals") if (d.get("fetched_at") or "") >= cutoff],
        key=lambda d: d.get("discount_pct") or 0, reverse=True
    )[:10]

    if not deals:
        log.warning("No deals in last 7 days — PDF not generated")
        return ""

    PDFS_DIR.mkdir(exist_ok=True)
    date_str   = now.strftime("%Y-%m-%d")
    start_str  = (now - timedelta(days=7)).strftime("%b %d")
    end_str    = now.strftime("%b %d, %Y")
    date_range = f"{start_str} – {end_str}"

    pdf_path = Path(output) if output else PDFS_DIR / f"top-deals-{date_str}.pdf"

    if dry_run:
        log.info("[DRY RUN] Would generate %s with %d deals", pdf_path, len(deals))
        return str(pdf_path)

    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter,
                            leftMargin=0.6*inch, rightMargin=0.6*inch,
                            topMargin=0.6*inch, bottomMargin=0.6*inch)
    story = []
    _cover(story, deals, date_range)

    # 2 deals per page
    for i in range(0, len(deals), 2):
        _deal_block(story, deals[i], i + 1)
        if i + 1 < len(deals):
            _deal_block(story, deals[i + 1], i + 2)
        if i + 2 < len(deals):
            story.append(PageBreak())

    _back_page(story)
    doc.build(story, onFirstPage=_bg_canvas, onLaterPages=_bg_canvas)

    # Update config + download.html
    existing = supabase_select("config", {"key": "latest_pdf"})
    if existing:
        supabase_update("config", {"key": "latest_pdf"}, {"value": str(pdf_path)})
    else:
        supabase_insert("config", {"key": "latest_pdf", "value": str(pdf_path)})

    dl_page = Path(__file__).parent.parent / "website" / "download.html"
    if dl_page.exists():
        html = dl_page.read_text(encoding="utf-8")
        html = html.replace("PDF_URL", f"/pdfs/{pdf_path.name}")
        dl_page.write_text(html, encoding="utf-8")

    if AUTO_EMAIL:
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            import email_engine
            email_engine.send_weekly_top10()
        except Exception as exc:
            log.warning("Auto-email after PDF failed: %s", exc)

    log.info("PDF generated: %s (%d deals)", pdf_path.name, len(deals))
    return str(pdf_path)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--output", help="Override output path")
    args = p.parse_args()

    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "pdf_generator.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    result = generate_weekly(dry_run=args.dry_run, output=args.output)
    if result:
        print(f"PDF: {result}")
