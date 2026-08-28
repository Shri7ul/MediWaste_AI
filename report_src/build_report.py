# -*- coding: utf-8 -*-
"""
build_report.py  —  MediWaste AI  ·  BrainChild Season 2.0 final report generator
Team Dekhte Aschi · Jagannath University A.I & IT Fest 2026

Pure-vector, canvas-driven PDF built with ReportLab. All diagrams are drawn as
crisp vector art; the only raster images are the REAL MedBin sample photos used
as honest input examples. No fabricated screenshots, metrics, or deployments.

Editable source: this file is the deliverable's source. Re-run to regenerate:
    python build_report.py
Output: ../MediWaste_AI_Final_Report_BrainChild_Season_2.pdf
"""

import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

# --------------------------------------------------------------------------- #
#  Paths
# --------------------------------------------------------------------------- #
HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)                       # .../MediWaste_AI
ASSETS = os.path.join(PROJ, "static", "assets")
SAMPLES = os.path.join(PROJ, "static", "samples")
OUT = os.path.join(PROJ, "MediWaste_AI_Final_Report_BrainChild_Season_2.pdf")

# --------------------------------------------------------------------------- #
#  Page geometry
# --------------------------------------------------------------------------- #
PAGE_W, PAGE_H = A4                                 # 595.28 x 841.89
MARGIN_X = 52
MARGIN_TOP = 60
MARGIN_BOT = 52
CW = PAGE_W - 2 * MARGIN_X                          # content width  ~491
CONTENT_TOP = PAGE_H - MARGIN_TOP
CONTENT_BOT = MARGIN_BOT

# --------------------------------------------------------------------------- #
#  Palette  (light dossier + faithful dark-UI mock accents)
# --------------------------------------------------------------------------- #
INK      = HexColor("#0B1220")   # near-black slate (headings)
BODY     = HexColor("#334155")   # body text
BODY2    = HexColor("#475569")
MUTED    = HexColor("#64748B")   # captions
FAINT    = HexColor("#94A3B8")
HAIR     = HexColor("#E2E8F0")   # hairlines
HAIR2    = HexColor("#EDF1F6")
PANEL    = HexColor("#F8FAFC")   # panel fill
PANEL2   = HexColor("#F1F5F9")
WHITE    = HexColor("#FFFFFF")

TEAL     = HexColor("#0E7490")   # primary accent (cyan-800)
TEAL_BR  = HexColor("#0891B2")   # brighter teal
CYAN     = HexColor("#06B6D4")
INDIGO   = HexColor("#4F46E5")   # engineering / team-built accent
INDIGO_L = HexColor("#EEF0FF")
TEAL_L   = HexColor("#E6F4F7")   # teal tint fill

GREEN    = HexColor("#16A34A")   # correct
RED      = HexColor("#DC2626")   # violation
AMBER    = HexColor("#D97706")   # review
GREEN_L  = HexColor("#E9F7EF")
RED_L    = HexColor("#FBEAEA")
AMBER_L  = HexColor("#FBF1E3")

# Exact biomedical stream colours (from policy_engine.STREAMS)
STREAM = {
    "YELLOW": HexColor("#eab308"), "RED": HexColor("#ef4444"),
    "BLUE": HexColor("#3b82f6"),   "WHITE": HexColor("#e5e7eb"),
    "BROWN": HexColor("#a16207"),  "BLACK": HexColor("#1f2937"),
    "RADIOACTIVE": HexColor("#d946ef"),
}

# Dark UI theme (faithful to static/style.css) for interface reconstructions
UI_BG    = HexColor("#0A1424")
UI_CARD  = HexColor("#111E36")
UI_CARD2 = HexColor("#0E1A30")
UI_LINE  = HexColor("#24344F")
UI_ACC   = HexColor("#38bdf8")
UI_TXT   = HexColor("#E6EDF7")
UI_MUT   = HexColor("#94A3B8")

# --------------------------------------------------------------------------- #
#  Fonts
# --------------------------------------------------------------------------- #
def _reg():
    F = "/usr/share/fonts/truetype"
    faces = {
        "Sans":            f"{F}/liberation/LiberationSans-Regular.ttf",
        "Sans-Bold":       f"{F}/liberation2/LiberationSans-Bold.ttf",
        "Sans-Italic":     f"{F}/liberation/LiberationSans-Italic.ttf",
        "Sans-BoldItalic": f"{F}/liberation2/LiberationSans-BoldItalic.ttf",
        "Mono":            f"{F}/liberation2/LiberationMono-Regular.ttf",
        "Mono-Bold":       f"{F}/liberation2/LiberationMono-Bold.ttf",
    }
    for name, path in faces.items():
        pdfmetrics.registerFont(TTFont(name, path))
    pdfmetrics.registerFontFamily(
        "Sans", normal="Sans", bold="Sans-Bold",
        italic="Sans-Italic", boldItalic="Sans-BoldItalic")

_reg()

# --------------------------------------------------------------------------- #
#  Low-level helpers
# --------------------------------------------------------------------------- #
def sw(txt, font, size):
    return pdfmetrics.stringWidth(txt, font, size)

def wrap(text, font, size, max_w):
    """Word-wrap into lines; honours explicit newlines; hard-breaks long words."""
    out = []
    for raw in str(text).split("\n"):
        if raw == "":
            out.append("")
            continue
        words = raw.split(" ")
        line = ""
        for w in words:
            trial = w if not line else line + " " + w
            if sw(trial, font, size) <= max_w:
                line = trial
            else:
                if line:
                    out.append(line)
                # hard-break an over-long single token
                if sw(w, font, size) > max_w:
                    chunk = ""
                    for ch in w:
                        if sw(chunk + ch, font, size) <= max_w:
                            chunk += ch
                        else:
                            out.append(chunk)
                            chunk = ch
                    line = chunk
                else:
                    line = w
        out.append(line)
    return out

def para(c, text, x, y_top, w, font="Sans", size=9.5, leading=14,
         color=BODY, align="left"):
    """Draw wrapped text from a top-left anchor; return bottom y."""
    lines = text if isinstance(text, list) else wrap(text, font, size, w)
    c.setFont(font, size)
    c.setFillColor(color)
    baseline = y_top - size
    for ln in lines:
        if align == "left":
            c.drawString(x, baseline, ln)
        elif align == "center":
            c.drawCentredString(x + w / 2.0, baseline, ln)
        elif align == "right":
            c.drawRightString(x + w, baseline, ln)
        baseline -= leading
    return y_top - size * 1.18 - (len(lines) - 1) * leading

def line(c, x1, y1, x2, y2, color=HAIR, width=1, dash=None):
    c.setStrokeColor(color)
    c.setLineWidth(width)
    if dash:
        c.setDash(dash, 0)
    c.line(x1, y1, x2, y2)
    if dash:
        c.setDash([], 0)

def rrect(c, x, y_top, w, h, r=10, fill=None, stroke=None, sw_=1, dash=None):
    """Rounded rect anchored top-left (y_top is the TOP edge)."""
    c.saveState()
    if fill is not None:
        c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke)
        c.setLineWidth(sw_)
    if dash:
        c.setDash(dash, 0)
    c.roundRect(x, y_top - h, w, h, r,
                stroke=1 if stroke is not None else 0,
                fill=1 if fill is not None else 0)
    c.restoreState()

def rect(c, x, y_top, w, h, fill=None, stroke=None, sw_=1):
    c.saveState()
    if fill is not None:
        c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke)
        c.setLineWidth(sw_)
    c.rect(x, y_top - h, w, h,
           stroke=1 if stroke is not None else 0,
           fill=1 if fill is not None else 0)
    c.restoreState()

def left_bar(c, x, y_top, h, color, w=3.2, r=1.6):
    rrect(c, x, y_top, w, h, r=r, fill=color)

def dot(c, cx, cy, r, fill, stroke=None, sw_=0.8):
    c.saveState()
    c.setFillColor(fill)
    if stroke is not None:
        c.setStrokeColor(stroke)
        c.setLineWidth(sw_)
    c.circle(cx, cy, r, stroke=1 if stroke is not None else 0, fill=1)
    c.restoreState()

def text(c, s, x, y, font="Sans", size=9.5, color=BODY, align="left"):
    c.setFont(font, size)
    c.setFillColor(color)
    if align == "left":
        c.drawString(x, y, s)
    elif align == "center":
        c.drawCentredString(x, y, s)
    elif align == "right":
        c.drawRightString(x, y, s)

def kicker(c, s, x, y, color=TEAL, size=8.2, gap=1.6):
    """Letter-spaced uppercase eyebrow label. Returns width drawn."""
    c.setFont("Sans-Bold", size)
    c.setFillColor(color)
    cx = x
    for ch in s.upper():
        c.drawString(cx, y, ch)
        cx += sw(ch, "Sans-Bold", size) + gap
    return cx - x

def pill(c, s, x, y_top, color, txt_color=WHITE, size=7.6, padx=7, h=15,
         fill=True, font="Sans-Bold"):
    w = sw(s, font, size) + 2 * padx
    if fill:
        rrect(c, x, y_top, w, h, r=h / 2.0, fill=color)
        text(c, s, x + padx, y_top - h + (h - size) / 2.0 + 1, font=font,
             size=size, color=txt_color)
    else:
        rrect(c, x, y_top, w, h, r=h / 2.0, fill=None, stroke=color, sw_=1)
        text(c, s, x + padx, y_top - h + (h - size) / 2.0 + 1, font=font,
             size=size, color=color)
    return w

def route_chip(c, code, x, y_top, h=17, size=8.6, dark=False):
    """Coloured route chip with a stream dot, e.g. BROWN / YELLOW."""
    label = code
    col = STREAM.get(code, MUTED)
    txtc = UI_TXT if dark else INK
    bg = UI_CARD2 if dark else PANEL2
    bd = UI_LINE if dark else HAIR
    w = sw(label, "Sans-Bold", size) + 30
    rrect(c, x, y_top, w, h, r=h / 2.0, fill=bg, stroke=bd, sw_=0.8)
    dot(c, x + 12, y_top - h / 2.0, 4.6, col,
        stroke=HexColor("#00000022"), sw_=0.5)
    text(c, label, x + 21, y_top - h + (h - size) / 2.0 + 1.2,
         font="Sans-Bold", size=size, color=txtc)
    return w

def cover_image(c, path, x, y_top, w, h, r=12):
    """Draw an image as a rounded 'cover' crop (fills box, centre-cropped)."""
    try:
        ir = ImageReader(path)
        iw, ih = ir.getSize()
    except Exception:
        rrect(c, x, y_top, w, h, r=r, fill=PANEL2, stroke=HAIR)
        return
    scale = max(w / iw, h / ih)
    dw, dh = iw * scale, ih * scale
    dx = x - (dw - w) / 2.0
    dy = (y_top - h) - (dh - h) / 2.0
    c.saveState()
    p = c.beginPath()
    p.roundRect(x, y_top - h, w, h, r)
    c.clipPath(p, stroke=0, fill=0)
    c.drawImage(ir, dx, dy, dw, dh, mask="auto")
    c.restoreState()
    # hairline frame
    rrect(c, x, y_top, w, h, r=r, fill=None, stroke=HAIR, sw_=0.8)

def bullet(c, text_str, x, y_top, w, color=BODY, size=9.5, leading=13.5,
           marker_color=TEAL, gap=12, bold_lead=None):
    """A bullet row; optional bold lead-in phrase. Returns bottom y."""
    dot(c, x + 2.2, y_top - size * 0.62, 1.9, marker_color)
    tx = x + gap
    tw = w - gap
    if bold_lead:
        lead_w = sw(bold_lead, "Sans-Bold", size)
        if lead_w < tw - 40:
            text(c, bold_lead, tx, y_top - size, font="Sans-Bold", size=size,
                 color=INK)
            first_indent = lead_w + 4
            # wrap remainder accounting for first-line indent
            words = str(text_str).split(" ")
            lines, cur, avail = [], "", tw - first_indent
            for wd in words:
                t = wd if not cur else cur + " " + wd
                if sw(t, "Sans", size) <= avail:
                    cur = t
                else:
                    lines.append(cur); cur = wd; avail = tw
            lines.append(cur)
            by = y_top - size
            text(c, lines[0], tx + first_indent, by, font="Sans", size=size,
                 color=color)
            for ln in lines[1:]:
                by -= leading
                text(c, ln, tx, by, font="Sans", size=size, color=color)
            return by - size * 0.28
    return para(c, text_str, tx, y_top, tw, size=size, leading=leading,
                color=color)

def chevron_down(c, cx, y_top, color=FAINT, w=9, h=6, lw=1.6):
    c.setStrokeColor(color); c.setLineWidth(lw)
    c.setLineCap(1); c.setLineJoin(1)
    c.line(cx - w / 2, y_top, cx, y_top - h)
    c.line(cx + w / 2, y_top, cx, y_top - h)

def arrow_down(c, cx, y_from, y_to, color=TEAL_BR, lw=1.5, head=4.2):
    c.setStrokeColor(color); c.setLineWidth(lw); c.setLineCap(1)
    c.line(cx, y_from, cx, y_to + head * 0.4)
    c.saveState(); c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(cx, y_to); p.lineTo(cx - head, y_to + head * 1.5)
    p.lineTo(cx + head, y_to + head * 1.5); p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()

def arrow_right(c, x_from, x_to, cy, color=TEAL_BR, lw=1.5, head=4.2):
    c.setStrokeColor(color); c.setLineWidth(lw); c.setLineCap(1)
    c.line(x_from, cy, x_to - head * 0.4, cy)
    c.saveState(); c.setFillColor(color)
    p = c.beginPath()
    p.moveTo(x_to, cy); p.lineTo(x_to - head * 1.5, cy - head)
    p.lineTo(x_to - head * 1.5, cy + head); p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.restoreState()

# --------------------------------------------------------------------------- #
#  Page chrome (header / footer)
# --------------------------------------------------------------------------- #
PAGE_NO = 0
SECTION = ""

def page_header(c, section_label, page_kicker=""):
    y = PAGE_H - 34
    kicker(c, "MEDIWASTE AI", MARGIN_X, y, color=TEAL, size=8.2)
    c.setFont("Sans", 8.2)
    c.setFillColor(FAINT)
    c.drawRightString(PAGE_W - MARGIN_X, y, page_kicker)
    line(c, MARGIN_X, y - 7, PAGE_W - MARGIN_X, y - 7, color=HAIR, width=0.8)

def page_footer(c, n):
    y = 30
    line(c, MARGIN_X, y + 12, PAGE_W - MARGIN_X, y + 12, color=HAIR, width=0.8)
    c.setFont("Sans", 7.6); c.setFillColor(MUTED)
    c.drawString(MARGIN_X, y, "MediWaste AI  ·  Team Dekhte Aschi")
    c.setFont("Sans", 7.6); c.setFillColor(FAINT)
    c.drawCentredString(PAGE_W / 2, y, "BrainChild Season 2.0  ·  JnU A.I & IT Fest 2026")
    c.setFont("Sans-Bold", 8)
    c.setFillColor(TEAL)
    c.drawRightString(PAGE_W - MARGIN_X, y, f"{n:02d}")

def new_page(c, section_label, page_kicker):
    global PAGE_NO
    PAGE_NO += 1
    page_header(c, section_label, page_kicker)
    page_footer(c, PAGE_NO)
    return CONTENT_TOP - 14

def page_title(c, title, y_top, kicker_txt=None, accent=TEAL):
    if kicker_txt:
        kicker(c, kicker_txt, MARGIN_X, y_top, color=accent, size=8.4)
        y_top -= 15
    left_bar(c, MARGIN_X, y_top + 2, 22, accent, w=3.4)
    text(c, title, MARGIN_X + 12, y_top - 17, font="Sans-Bold", size=20,
         color=INK)
    return y_top - 30

# =========================================================================== #
#  PAGE 1 — COVER
# =========================================================================== #
def cover(c):
    global PAGE_NO
    PAGE_NO += 1
    # background
    rect(c, 0, PAGE_H, PAGE_W, PAGE_H, fill=WHITE)
    # top hairline band with team / event
    top = PAGE_H - 54
    kicker(c, "TEAM DEKHTE ASCHI", MARGIN_X, top, color=TEAL, size=9)
    c.setFont("Sans", 9); c.setFillColor(MUTED)
    c.drawRightString(PAGE_W - MARGIN_X, top,
                      "BrainChild Season 2.0")
    line(c, MARGIN_X, top - 9, PAGE_W - MARGIN_X, top - 9, color=HAIR, width=1)

    # ---- title block ----
    ty = PAGE_H - 168
    kicker(c, "INTELLIGENT MEDICAL-WASTE COMPLIANCE PLATFORM", MARGIN_X, ty,
           color=TEAL_BR, size=9)
    ty -= 42
    text(c, "MediWaste AI", MARGIN_X, ty, font="Sans-Bold", size=54, color=INK)
    ty -= 30
    # accent underline
    rrect(c, MARGIN_X + 2, ty + 6, 66, 4, r=2, fill=TEAL)
    ty -= 18
    sub = ("Intelligent Point-of-Disposal Medical-Waste Segregation, "
           "Compliance Verification & Operational Intelligence Platform")
    ty = para(c, sub, MARGIN_X, ty, CW - 40, font="Sans", size=15.5,
              leading=21, color=BODY2)

    # ---- positioning strap-line in a tinted panel ----
    ty -= 20
    panel_h = 66
    rrect(c, MARGIN_X, ty, CW, panel_h, r=12, fill=TEAL_L)
    left_bar(c, MARGIN_X, ty, panel_h, TEAL, w=3.6)
    inner = MARGIN_X + 18
    ptxt = ("From waste detection to disposal intelligence — MediWaste AI "
            "turns a medical-waste image into a policy-controlled disposal "
            "decision, verifies the chosen route, explains it from cited "
            "evidence, and records an auditable event.")
    para(c, ptxt, inner, ty - 12, CW - 34, font="Sans", size=10.2,
         leading=15, color=HexColor("#0B4A57"))

    # ---- real sample strip (honest inputs, labelled) ----
    ty -= panel_h + 26
    strip_h = 150
    imgs = [("sample3.jpg", "Pharmaceuticals"),
            ("sample4.jpg", "Infectious / soiled"),
            ("sample1.jpg", "Radioactive-labelled")]
    gap = 14
    iw = (CW - 2 * gap) / 3.0
    for i, (fn, cap) in enumerate(imgs):
        x = MARGIN_X + i * (iw + gap)
        cover_image(c, os.path.join(SAMPLES, fn), x, ty, iw, strip_h, r=10)
    # caption under strip
    cyy = ty - strip_h - 12
    kicker(c, "REAL MEDBIN SAMPLE INPUTS", MARGIN_X, cyy, color=MUTED, size=7.6)
    c.setFont("Sans", 8); c.setFillColor(FAINT)
    c.drawRightString(PAGE_W - MARGIN_X, cyy,
                      "Diagrams in this report are vector illustrations, not screenshots.")

    # ---- decision-boundary tagline ----
    bty = 150
    line(c, MARGIN_X, bty + 20, PAGE_W - MARGIN_X, bty + 20, color=HAIR, width=1)
    segs = [("Vision observes.", TEAL), ("Rules decide.", INDIGO),
            ("RAG supports.", TEAL_BR), ("LLM explains.", MUTED)]
    c.setFont("Sans-Bold", 13)
    total = sum(sw(s, "Sans-Bold", 13) for s, _ in segs) + 18 * (len(segs) - 1)
    sx = (PAGE_W - total) / 2.0
    for s, col in segs:
        text(c, s, sx, bty, font="Sans-Bold", size=13, color=col)
        sx += sw(s, "Sans-Bold", 13) + 18

    # ---- footer meta ----
    fy = 88
    text(c, "Team Dekhte Aschi", MARGIN_X, fy, font="Sans-Bold", size=10.5,
         color=INK)
    text(c, "BrainChild Season 2.0", PAGE_W - MARGIN_X, fy, font="Sans-Bold",
         size=10.5, color=INK, align="right")
    fy -= 15
    text(c, "Final Technical & Product Report", MARGIN_X, fy, font="Sans",
         size=9, color=MUTED)
    text(c, "Jagannath University A.I & IT Fest 2026", PAGE_W - MARGIN_X, fy,
         font="Sans", size=9, color=MUTED, align="right")
    c.showPage()


# --------------------------------------------------------------------------- #
#  Shared composite helpers
# --------------------------------------------------------------------------- #
def callout(c, body, x, y_top, w, accent=TEAL, fill=TEAL_L, txt_color=None,
            size=11, leading=15.5, pad=14, bold=False, title=None):
    txt_color = txt_color or HexColor("#0B3B47")
    lines = wrap(body, "Sans-Bold" if bold else "Sans", size, w - 2 * pad - 6)
    h = pad * 2 + len(lines) * leading + (16 if title else 0)
    rrect(c, x, y_top, w, h, r=11, fill=fill)
    left_bar(c, x, y_top, h, accent, w=3.6)
    iy = y_top - pad
    if title:
        kicker(c, title, x + pad + 6, iy, color=accent, size=8)
        iy -= 16
    para(c, lines, x + pad + 6, iy, w - 2 * pad - 6,
         font="Sans-Bold" if bold else "Sans", size=size, leading=leading,
         color=txt_color)
    return y_top - h

def kpi_row(c, items, x, y_top, w, h=58, gap=12, accent=TEAL,
            big_size=17, small_size=7.4):
    """Row of KPI cells: items = [(big, small_multiline)]. Returns bottom y."""
    n = len(items)
    bw = (w - gap * (n - 1)) / float(n)
    for i, (big, small) in enumerate(items):
        bx = x + i * (bw + gap)
        rrect(c, bx, y_top, bw, h, r=9, fill=PANEL, stroke=HAIR, sw_=0.9)
        rrect(c, bx + 10, y_top, 22, 3, r=1.5, fill=accent)
        text(c, big, bx + bw / 2.0, y_top - 26, font="Sans-Bold",
             size=big_size, color=accent, align="center")
        sl = wrap(small, "Sans", small_size, bw - 12)
        sy = y_top - 26 - 12
        for ln in sl[:2]:
            text(c, ln, bx + bw / 2.0, sy, font="Sans", size=small_size,
                 color=MUTED, align="center")
            sy -= small_size + 2
    return y_top - h

def gap_flow(c, x, y_top, w):
    """Small illustrative flow: recognised object -> [team-built middle] -> compliant disposal."""
    h = 50
    bw_side = 130
    mid_w = w - 2 * bw_side - 2 * 26
    # left
    rrect(c, x, y_top, bw_side, h, r=9, fill=PANEL, stroke=HAIR, sw_=0.9)
    text(c, "Object recognised", x + bw_side / 2, y_top - 22, font="Sans-Bold",
         size=9, color=INK, align="center")
    text(c, "detector output", x + bw_side / 2, y_top - 34, font="Sans",
         size=7.6, color=MUTED, align="center")
    # middle (highlight)
    mx = x + bw_side + 26
    rrect(c, mx, y_top, mid_w, h, r=9, fill=INDIGO_L, stroke=INDIGO, sw_=1.1)
    text(c, "Policy · Verification · Evidence · Audit",
         mx + mid_w / 2, y_top - 21, font="Sans-Bold", size=8.8, color=INDIGO,
         align="center")
    text(c, "the team-built middle that detection alone skips",
         mx + mid_w / 2, y_top - 34, font="Sans", size=7.4,
         color=HexColor("#4A4AA0"), align="center")
    # right
    rx2 = mx + mid_w + 26
    rrect(c, rx2, y_top, bw_side, h, r=9, fill=GREEN_L, stroke=GREEN, sw_=1)
    text(c, "Compliant disposal", rx2 + bw_side / 2, y_top - 22,
         font="Sans-Bold", size=9, color=HexColor("#12693A"), align="center")
    text(c, "verifiable outcome", rx2 + bw_side / 2, y_top - 34, font="Sans",
         size=7.6, color=HexColor("#2E8B57"), align="center")
    arrow_right(c, x + bw_side + 3, mx - 3, y_top - h / 2, color=INDIGO, lw=1.4)
    arrow_right(c, mx + mid_w + 3, rx2 - 3, y_top - h / 2, color=GREEN, lw=1.4)
    return y_top - h

def mini_section(c, title, body, x, y_top, w, accent=TEAL, tsize=10,
                 bsize=9, leading=12.8, gap=4):
    dot(c, x + 2, y_top - tsize * 0.5, 2.1, accent)
    text(c, title, x + 10, y_top - tsize, font="Sans-Bold", size=tsize,
         color=INK)
    by = y_top - tsize - gap - 3
    by = para(c, body, x, by, w, font="Sans", size=bsize, leading=leading,
              color=BODY)
    return by

def flow_h(c, nodes, x, y_top, w, h=46, gap=16, fill=PANEL, stroke=HAIR,
           accent=TEAL, arrow_color=TEAL_BR, tsize=8.6, ssize=7.2,
           title_color=INK, sub_color=MUTED, bar=True):
    """Horizontal chain of boxes joined by right-arrows. nodes: str or (title, sub)."""
    n = len(nodes)
    bw = (w - gap * (n - 1)) / float(n)
    for i, nd in enumerate(nodes):
        bx = x + i * (bw + gap)
        title, sub = nd if isinstance(nd, tuple) else (nd, None)
        rrect(c, bx, y_top, bw, h, r=8, fill=fill, stroke=stroke, sw_=0.9)
        if bar:
            left_bar(c, bx, y_top, h, accent, w=2.6)
        tl = wrap(title, "Sans-Bold", tsize, bw - 14)
        block_h = len(tl) * (tsize + 2) + (ssize + 3 if sub else 0)
        ty = y_top - (h - block_h) / 2.0 - tsize
        for ln in tl:
            text(c, ln, bx + bw / 2.0, ty, font="Sans-Bold", size=tsize,
                 color=title_color, align="center")
            ty -= tsize + 2
        if sub:
            text(c, sub, bx + bw / 2.0, ty - 1, font="Sans", size=ssize,
                 color=sub_color, align="center")
        if i < n - 1:
            arrow_right(c, bx + bw + 2, bx + bw + gap - 2, y_top - h / 2.0,
                        color=arrow_color, lw=1.4, head=3.6)
    return y_top - h

def table(c, headers, rows, x, y_top, col_ws, header_fill=INK,
          header_txt=WHITE, font=9, hfont=8.4, pad=8, line_color=HAIR,
          zebra=PANEL, body_color=BODY, leading=12.6, first_bold=True,
          cell_colors=None):
    """Simple, robust wrapped table. Returns bottom y."""
    total_w = sum(col_ws)
    # header height
    hlines = [wrap(h, "Sans-Bold", hfont, col_ws[i] - 2 * pad)
              for i, h in enumerate(headers)]
    hh = max(len(l) for l in hlines) * (hfont + 2) + 2 * pad - 4
    rrect(c, x, y_top, total_w, hh, r=6, fill=header_fill)
    # square off bottom corners of header by overpainting a rect
    rect(c, x, y_top - hh + 6, total_w, 6, fill=header_fill)
    cxx = x
    for i, hl in enumerate(hlines):
        ty = y_top - pad - hfont + 2
        for ln in hl:
            text(c, ln, cxx + pad, ty, font="Sans-Bold", size=hfont,
                 color=header_txt)
            ty -= hfont + 2
        cxx += col_ws[i]
    y = y_top - hh
    for r_idx, row in enumerate(rows):
        cell_lines = [wrap(str(cell), "Sans-Bold" if (first_bold and ci == 0)
                           else "Sans", font, col_ws[ci] - 2 * pad)
                      for ci, cell in enumerate(row)]
        rh = max(len(cl) for cl in cell_lines) * leading + 2 * pad - 3
        if zebra and r_idx % 2 == 1:
            rect(c, x, y, total_w, rh, fill=zebra)
        cxx = x
        for ci, cl in enumerate(cell_lines):
            ty = y - pad - font + 3
            fnt = "Sans-Bold" if (first_bold and ci == 0) else "Sans"
            col = INK if (first_bold and ci == 0) else body_color
            if cell_colors and cell_colors.get((r_idx, ci)):
                col = cell_colors[(r_idx, ci)]
                fnt = "Sans-Bold"
            for ln in cl:
                text(c, ln, cxx + pad, ty, font=fnt, size=font, color=col)
                ty -= leading
            cxx += col_ws[ci]
        line(c, x, y - rh, x + total_w, y - rh, color=line_color, width=0.7)
        y -= rh
    # outer frame
    rrect(c, x, y_top, total_w, y_top - y, r=6, fill=None, stroke=line_color,
          sw_=0.9)
    # vertical separators
    cxx = x
    for i in range(len(col_ws) - 1):
        cxx += col_ws[i]
        line(c, cxx, y_top - hh, cxx, y, color=line_color, width=0.7)
    return y


# =========================================================================== #
#  PAGE 2 — EXECUTIVE SUMMARY
# =========================================================================== #
def page02(c):
    y = new_page(c, "Executive Summary", "Executive Summary")
    y = page_title(c, "Executive Summary", y, kicker_txt="01 · Overview")

    y -= 2
    y = callout(
        c,
        "MediWaste AI transforms medical-waste images into policy-controlled "
        "disposal decisions, verifies disposal compliance, provides "
        "evidence-grounded explanations, and creates an auditable record of "
        "each event.",
        MARGIN_X, y, CW, accent=TEAL, fill=TEAL_L, size=11.5, leading=16,
        bold=True, txt_color=HexColor("#0B3B47"))

    # value chain
    y -= 20
    kicker(c, "CORE VALUE CHAIN  ·  CURRENTLY IMPLEMENTED", MARGIN_X, y,
           color=MUTED, size=7.8)
    y -= 12
    y = flow_h(c, [("Image", "capture"), ("Detect +\nNormalize", "perception"),
                   ("Policy\nDecide", "authority"), ("Verify", "expected vs actual"),
                   ("Explain +\nRecord", "evidence · audit")],
               MARGIN_X, y, CW, h=54, gap=15, accent=TEAL)

    # two columns
    y -= 26
    colw = (CW - 26) / 2.0
    lx = MARGIN_X
    rx = MARGIN_X + colw + 26
    ly = ry = y

    ly = mini_section(c, "The real problem",
        "Manual segregation is error-prone, and wrong-stream disposal drives "
        "infection and sharps-injury risk, regulatory exposure, and cost. "
        "Recognising an object is not the same as making a compliant disposal "
        "decision for it.", lx, ly, colw)
    ly -= 21
    ly = mini_section(c, "What MediWaste AI does",
        "It converts a waste image into a deterministic, policy-controlled "
        "disposal decision, compares that against the route the operator "
        "actually selected, explains the outcome from cited evidence, and "
        "writes an auditable event.", lx, ly, colw)
    ly -= 21
    ly = mini_section(c, "Current MVP capability",
        "Image-based analysis (not live video); one deterministic policy pack "
        "of seven colour-coded streams; operator-confirmed actual route; "
        "best-effort retrieval and explanation with graceful degradation; a "
        "SQLite audit trail and an analytics view.", lx, ly, colw)

    ry = mini_section(c, "Core technical contribution",
        "A strict decision boundary: a deterministic policy engine — not the "
        "language model — is the single authority for waste category and "
        "disposal route. Perception, evidence, and explanation are kept "
        "separate from the decision.", rx, ry, colw, accent=INDIGO)
    ry -= 21
    ry = mini_section(c, "AI components",
        "Roboflow MedBin detector for perception, a CLIP zero-shot "
        "visual-context estimate, Pinecone retrieval for evidence, and "
        "GPT-OSS-120B (via OpenRouter) for explanation only — all arranged "
        "around a team-built policy and compliance core.", rx, ry, colw,
        accent=INDIGO)
    ry -= 21
    ry = mini_section(c, "Intended impact & differentiator",
        "Designed to reduce segregation errors and make every decision "
        "explainable, traceable, and reviewable by ward or station. The "
        "perception model is replaceable; the policy, compliance, and audit "
        "architecture is the product.", rx, ry, colw, accent=INDIGO)

    # system-at-a-glance KPI band (all verifiable from the repository)
    by = min(ly, ry) - 24
    kicker(c, "SYSTEM AT A GLANCE  ·  VERIFIABLE FROM THE REPOSITORY", MARGIN_X,
           by, color=MUTED, size=7.8)
    by -= 13
    by = kpi_row(c, [
        ("7", "colour-coded disposal streams"),
        ("v1.1.0", "deterministic policy pack"),
        ("9", "REST API endpoints"),
        ("62", "tests · 55 offline-verified"),
        ("4", "AI / ML services integrated"),
    ], MARGIN_X, by, CW, h=62)

    # bottom boundary strip
    by -= 26
    line(c, MARGIN_X, by, PAGE_W - MARGIN_X, by, color=HAIR, width=0.8)
    by -= 18
    segs = [("Vision observes.", TEAL), ("Rules decide.", INDIGO),
            ("RAG supports.", TEAL_BR), ("LLM explains.", MUTED)]
    c.setFont("Sans-Bold", 11.5)
    tot = sum(sw(s, "Sans-Bold", 11.5) for s, _ in segs) + 16 * (len(segs) - 1)
    sx = (PAGE_W - tot) / 2.0
    for s, col in segs:
        text(c, s, sx, by, font="Sans-Bold", size=11.5, color=col)
        sx += sw(s, "Sans-Bold", 11.5) + 16
    c.showPage()


# =========================================================================== #
#  PAGE 3 — PROBLEM & EXISTING APPROACHES
# =========================================================================== #
def page03(c):
    y = new_page(c, "Problem", "Problem & Existing Approaches")
    y = page_title(c, "Problem & Existing Approaches", y,
                   kicker_txt="02 · Why this is hard")

    y = para(c,
        "Medical-waste management is not simply an object-recognition problem. "
        "A workable system has to contend with human segregation error, "
        "wrong-stream selection, contamination and context, policy ambiguity, "
        "and — just as importantly — the absence of evidence and traceability "
        "that lets a facility catch repeated violations and act on them.",
        MARGIN_X, y - 2, CW, size=9.6, leading=14.2)

    # dimension chips
    y -= 12
    dims = ["Human segregation error", "Wrong disposal stream",
            "Context / contamination", "Policy ambiguity", "No evidence",
            "No traceability", "Repeated violations", "Limited visibility"]
    cx, cyy = MARGIN_X, y
    for d in dims:
        w = sw(d, "Sans-Bold", 7.8) + 16
        if cx + w > MARGIN_X + CW:
            cx = MARGIN_X; cyy -= 21
        rrect(c, cx, cyy, w, 16, r=8, fill=PANEL2, stroke=HAIR, sw_=0.8)
        text(c, d, cx + 8, cyy - 11.5, font="Sans-Bold", size=7.8, color=BODY2)
        cx += w + 7
    y = cyy - 34

    kicker(c, "EXISTING APPROACHES  ·  WHERE THEY FALL SHORT", MARGIN_X, y,
           color=MUTED, size=7.8)
    y -= 10
    y = table(c,
        ["Existing approach", "Core limitation"],
        [["Manual segregation", "Relies on human judgement under time pressure; "
          "error-prone and unevenly documented."],
         ["Object detector alone", "Identifies objects but does not, by itself, "
          "determine a policy-compliant disposal route."],
         ["Rule-only application", "Sound rules, but require a human to identify "
          "and enter the object first."],
         ["Generic LLM chatbot", "Fluent, but not an appropriate deterministic "
          "authority for a safety-critical routing decision."],
         ["Dashboard-only system", "Mostly reactive reporting; no intervention "
          "at the point of disposal."]],
        MARGIN_X, y, [150, CW - 150], pad=9, leading=14)

    y -= 22
    y = callout(c,
        "MediWaste AI combines perception, deterministic policy reasoning, "
        "verification, evidence retrieval, and auditability into one "
        "point-of-disposal workflow.",
        MARGIN_X, y, CW, accent=INDIGO, fill=INDIGO_L, size=11, leading=15,
        bold=True, txt_color=HexColor("#2A2A6B"))

    # "is this just a pretrained model + website?" answer
    y -= 22
    left_bar(c, MARGIN_X, y, 16, TEAL, w=3.2)
    text(c, "“Is this just a pretrained model + a website?”",
         MARGIN_X + 12, y - 12, font="Sans-Bold", size=11, color=INK)
    y -= 27
    y = para(c,
        "No. The pretrained detector is one replaceable perception component. "
        "Everything that makes a disposal decision safe, explainable, and "
        "auditable — the canonical waste ontology, the deterministic policy "
        "engine, confidence and abstention behaviour, expected-vs-actual "
        "verification, the evidence-grounding gate, and the audit trail — is "
        "engineering built by the team around that model. Page 5 shows this "
        "layer explicitly.",
        MARGIN_X, y, CW, size=9.5, leading=14.5)

    y -= 24
    kicker(c, "DETECTION ALONE DOES NOT CROSS THIS GAP", MARGIN_X, y,
           color=MUTED, size=7.8)
    y -= 15
    y = gap_flow(c, MARGIN_X, y, CW)
    c.showPage()


# =========================================================================== #
#  PAGE 4 — SYSTEM ARCHITECTURE
# =========================================================================== #
def phase_card(c, x, y_top, w, no, name, accent, chips, note=None, ch=34,
               chip_fill=WHITE):
    hdr = 20
    inner_pad = 12
    body_h = ch + 8
    h = hdr + body_h + (14 if note else 0)
    rrect(c, x, y_top, w, h, r=10, fill=PANEL, stroke=HAIR, sw_=0.9)
    left_bar(c, x, y_top, h, accent, w=3.4)
    # header
    dot(c, x + inner_pad + 4, y_top - 12, 7.5, accent)
    text(c, str(no), x + inner_pad + 4, y_top - 14.6, font="Sans-Bold",
         size=8.5, color=WHITE, align="center")
    text(c, name, x + inner_pad + 18, y_top - 15, font="Sans-Bold", size=9.5,
         color=INK)
    if note:
        text(c, note, x + w - inner_pad, y_top - 15, font="Sans", size=7.8,
             color=MUTED, align="right")
    # chips row
    flow_h(c, chips, x + inner_pad, y_top - hdr - 3, w - 2 * inner_pad, h=ch,
           gap=11, fill=chip_fill, stroke=HAIR, accent=accent,
           arrow_color=accent, tsize=7.9, ssize=6.6, bar=False)
    return y_top - h

def page04(c):
    y = new_page(c, "Architecture", "System Architecture")
    y = page_title(c, "System Architecture", y,
                   kicker_txt="03 · One-directional pipeline")

    y = para(c,
        "Data flows one way, and the decision authority sits in the middle. "
        "Perception feeds a deterministic core; evidence and language sit "
        "downstream of the decision and can never reach back to change it.",
        MARGIN_X, y - 2, CW, size=9.4, leading=13.6)

    y -= 14
    gap_between = 18
    y = phase_card(c, MARGIN_X, y, CW, 1, "PERCEIVE", TEAL,
                   [("Image /\nCapture", None), ("Input\nQuality", None),
                    ("Vision\nRoboflow", None), ("Confidence\nGate", None)],
                   note="observes")
    arrow_down(c, PAGE_W / 2, y - 3, y - gap_between + 3, color=TEAL_BR)
    y -= gap_between
    y = phase_card(c, MARGIN_X, y, CW, 2, "UNDERSTAND", TEAL,
                   [("Canonical\nNormalize", None), ("Waste\nOntology", None),
                    ("Visual Context\nCLIP · estimate", None)],
                   note="standardizes")
    arrow_down(c, PAGE_W / 2, y - 3, y - gap_between + 3, color=INDIGO)
    y -= gap_between
    y = phase_card(c, MARGIN_X, y, CW, 3, "DECIDE  &  VERIFY", INDIGO,
                   [("Policy\nEngine", None), ("Expected\nRoute", None),
                    ("Actual /\nSelected", None), ("Compliance\nVerify", None)],
                   note="decides — single source of truth")
    arrow_down(c, PAGE_W / 2, y - 3, y - gap_between + 3, color=TEAL_BR)
    y -= gap_between
    y = phase_card(c, MARGIN_X, y, CW, 4, "EXPLAIN  &  RECORD", TEAL_BR,
                   [("Evidence\nRAG", None), ("Grounding\nGate", None),
                    ("Explanation\nLLM", None), ("Audit\nEvent", None),
                    ("Analytics", None)],
                   note="supports · explains · records")

    # cross-cutting registries band
    y -= 22
    kicker(c, "CROSS-CUTTING PROVENANCE & GOVERNANCE", MARGIN_X, y, color=MUTED,
           size=7.8)
    y -= 13
    reg = [("Model Registry", "id · version"), ("Rule Registry", "policy vers."),
           ("Evidence Provenance", "source · ids"), ("Review / Feedback", "abstention")]
    n = len(reg)
    bw = (CW - 12 * (n - 1)) / n
    for i, (t, s) in enumerate(reg):
        bx = MARGIN_X + i * (bw + 12)
        rrect(c, bx, y, bw, 36, r=8, fill=PANEL2, stroke=HAIR, sw_=0.8)
        text(c, t, bx + bw / 2, y - 15, font="Sans-Bold", size=8.4, color=INK,
             align="center")
        text(c, s, bx + bw / 2, y - 26, font="Mono", size=7, color=MUTED,
             align="center")
    y -= 36

    y -= 16
    y = para(c,
        "Every stage writes its inputs and outputs to the audit event, so any "
        "decision in the pipeline can be reconstructed and reviewed after the "
        "fact — the boundary below is enforced structurally, not by convention.",
        MARGIN_X, y, CW, size=9, leading=13.4, color=BODY2)
    y -= 12
    y = callout(c,
        "Vision observes.   Rules decide.   RAG supports.   LLM explains.",
        MARGIN_X, y, CW, accent=INDIGO, fill=INDIGO_L, size=12.5, leading=16,
        bold=True, txt_color=INK, pad=13)
    c.showPage()


# =========================================================================== #
#  DRIVER
# =========================================================================== #
# =========================================================================== #
#  SHARED HELPERS FOR PAGES 5–12
# =========================================================================== #
def stack_layer(c, x, y_top, w, label, tag, accent, fill, h=25,
                tag_fill=None, txt_color=INK):
    """One horizontal layer in the 'more-than-a-model' vertical stack."""
    rrect(c, x, y_top, w, h, r=7, fill=fill, stroke=HAIR, sw_=0.9)
    left_bar(c, x, y_top, h, accent, w=3.2)
    text(c, label, x + 13, y_top - h / 2.0 - 3.1, font="Sans-Bold", size=8.8,
         color=txt_color)
    if tag:
        tf = tag_fill or accent
        tw = sw(tag, "Sans-Bold", 6.7) + 13
        cy = y_top - h / 2.0
        rrect(c, x + w - tw - 11, cy + 7, tw, 14, r=7, fill=tf)
        text(c, tag, x + w - tw - 11 + 6.5, cy - 2.4,
             font="Sans-Bold", size=6.7, color=WHITE)
    return y_top - h


def panel_list(c, x, y_top, w, title, items, accent, fill=WHITE,
               title_bg=None, dashed=False, isize=8.7, lead=12.2, minh=0):
    """Titled rounded panel with a bulleted list. Returns bottom y."""
    title_bg = title_bg or accent
    inner = w - 26
    measured = [wrap(it, "Sans", isize, inner - 12) for it in items]
    item_hs = [isize * 1.16 + (len(m) - 1) * lead for m in measured]
    body_h = sum(item_hs) + 9 * len(items) + 8
    hdr = 21
    h = max(minh, hdr + body_h)
    rrect(c, x, y_top, w, h, r=10, fill=fill, stroke=accent, sw_=1.15,
          dash=(3, 2) if dashed else None)
    rrect(c, x, y_top, w, hdr, r=10, fill=title_bg)
    rect(c, x, y_top - hdr + 6, w, 6, fill=title_bg)
    text(c, title, x + 13, y_top - 14.5, font="Sans-Bold", size=8.6,
         color=WHITE)
    iy = y_top - hdr - 9
    for it, mh in zip(items, item_hs):
        bullet(c, it, x + 11, iy, inner, size=isize, leading=lead,
               marker_color=accent, gap=11)
        iy -= mh + 9
    return y_top - h


def outcome_card(c, x, y_top, w, verdict, verdict_col, fill, expected, actual,
                 route_exp, route_act, meta, evt):
    """Compliance outcome card for the workflow page. Returns bottom y."""
    h = 118
    rrect(c, x, y_top, w, h, r=10, fill=fill, stroke=verdict_col, sw_=1.3)
    left_bar(c, x, y_top, h, verdict_col, w=3.6)
    text(c, verdict, x + 14, y_top - 19, font="Sans-Bold", size=12,
         color=verdict_col)
    text(c, meta, x + 14, y_top - 33, font="Sans", size=8, color=BODY2)
    # expected / actual route chips
    ly = y_top - 52
    text(c, "expected", x + 14, ly, font="Sans", size=7.4, color=MUTED)
    route_chip(c, route_exp, x + 62, ly + 5.5)
    ly2 = y_top - 74
    text(c, "actual", x + 14, ly2, font="Sans", size=7.4, color=MUTED)
    route_chip(c, route_act, x + 62, ly2 + 5.5)
    # footer line
    line(c, x + 14, y_top - 88, x + w - 12, y_top - 88, color=HAIR, width=0.7)
    text(c, evt, x + 14, y_top - 102, font="Mono", size=7.4, color=MUTED)
    return y_top - h


# =========================================================================== #
#  PAGE 5 — AI / ML & ENGINEERING STACK
# =========================================================================== #
def page05(c):
    y = new_page(c, "Stack", "AI / ML & Engineering Stack")
    y = page_title(c, "AI / ML & Engineering Stack", y,
                   kicker_txt="04 · Reused vs team-built")

    y = para(c,
        "MediWaste AI integrates four third-party AI/ML services for "
        "perception, visual context, retrieval, and language. Each is confined "
        "to a specific role — the disposal decision, verification, and audit "
        "layers around them are engineered by the team.",
        MARGIN_X, y - 2, CW, size=9.4, leading=13.6)

    y -= 15
    kicker(c, "INTEGRATED THIRD-PARTY AI / ML SERVICES", MARGIN_X, y,
           color=MUTED, size=7.8)
    y -= 10
    y = table(c,
        ["Service", "Role in the pipeline", "Boundary"],
        [["Roboflow MedBin\n(medbin_dataset-fqhi7/1)", "Object perception and "
          "detection", "Observes — proposes labels only"],
         ["CLIP (ViT-B/32)", "Zero-shot visual-context estimate",
          "Advisory — never decides"],
         ["Pinecone (brainchild index)", "Evidence retrieval (top-k 8)",
          "Supplies citations only"],
         ["OpenRouter GPT-OSS-120B", "Natural-language explanation",
          "Explains — never decides"]],
        MARGIN_X, y, [150, 190, CW - 340], pad=7, font=8.6, hfont=8.2,
        leading=12)

    y -= 20
    kicker(c, "WHY THIS IS MORE THAN A PRETRAINED MODEL + A WEB APP", MARGIN_X,
           y, color=INDIGO, size=7.8)
    y -= 12
    layers = [
        ("Web UI  ·  Flask REST API (9 endpoints)", "DELIVERY", MUTED, PANEL2),
        ("Pretrained perception — Roboflow MedBin detector", "REUSED", AMBER,
         AMBER_L),
        ("Canonical normalization  ·  waste ontology", "TEAM-BUILT", TEAL,
         TEAL_L),
        ("Deterministic policy engine  ·  v1.1.0  ·  7 streams", "DECIDES",
         INDIGO, INDIGO_L),
        ("Confidence & abstention gates", "TEAM-BUILT", TEAL, WHITE),
        ("Expected-vs-actual compliance verification", "TEAM-BUILT", TEAL,
         WHITE),
        ("Evidence grounding gate  →  explanation", "TEAM-BUILT", TEAL, WHITE),
        ("SQLite audit trail & analytics", "TEAM-BUILT", TEAL, WHITE),
    ]
    for lab, tag, acc, fil in layers:
        y = stack_layer(c, MARGIN_X, y, CW, lab, tag, acc, fil, h=25)
        y -= 5

    y -= 8
    y = callout(c,
        "Exactly one layer is a reused, replaceable perception model. "
        "Everything around it — ontology, policy, verification, grounding, and "
        "audit — is engineering built by the team. Swap the detector and the "
        "compliance architecture still stands.",
        MARGIN_X, y, CW, accent=INDIGO, fill=INDIGO_L, size=9.6, leading=13.6,
        txt_color=HexColor("#2A2A6B"))
    c.showPage()


# =========================================================================== #
#  PAGE 6 — DECISION SAFETY & RESPONSIBLE AI
# =========================================================================== #
def page06(c):
    y = new_page(c, "Decision Safety", "Decision Safety & Responsible AI")
    y = page_title(c, "Decision Safety & Responsible AI", y,
                   kicker_txt="05 · The model proposes, the policy disposes")

    y = para(c,
        "Safety-critical routing is never delegated to a probabilistic model. "
        "A deterministic, versioned policy engine makes every category-and-"
        "route decision, and the system is explicitly allowed to abstain when "
        "it is not confident.",
        MARGIN_X, y - 2, CW, size=9.4, leading=13.6)

    # DECIDES vs SUPPORTS
    y -= 16
    colw = (CW - 22) / 2.0
    decides = ["Deterministic policy engine (policy v1.1.0)",
               "Expected route from versioned static rules",
               "Expected-vs-actual compliance verification"]
    supports = ["Perception — Roboflow MedBin (observes)",
                "Visual context — CLIP (estimate)",
                "Evidence — Pinecone retrieval (supports)",
                "Explanation — GPT-OSS-120B (describes only)"]
    # equalize height
    def _ph(items):
        inner = colw - 26
        mh = [wrap(it, "Sans", 8.7, inner - 12) for it in items]
        ih = [8.7 * 1.16 + (len(m) - 1) * 12.2 for m in mh]
        return 21 + sum(ih) + 9 * len(items) + 8
    mh = max(_ph(decides), _ph(supports))
    panel_list(c, MARGIN_X, y, colw, "DECIDES  ·  DETERMINISTIC", decides,
               INDIGO, fill=INDIGO_L, minh=mh)
    yb = panel_list(c, MARGIN_X + colw + 22, y, colw, "SUPPORTS  ·  ADVISORY",
                    supports, TEAL, fill=TEAL_L, minh=mh)
    y = yb

    y -= 18
    kicker(c, "SAFETY STATES  ·  THE SYSTEM IS ALLOWED TO ABSTAIN", MARGIN_X, y,
           color=MUTED, size=7.8)
    y -= 10
    y = table(c,
        ["Condition", "System behaviour", "Signal"],
        [["Confidence ≥ 0.40, known class", "Trusted — policy rule "
          "applied", "ACCEPT"],
         ["Confidence below 0.40", "Not routed — sent to human review",
          "REVIEW · LOW_CONFIDENCE"],
         ["Unknown / unmapped class", "No route guessed — review",
          "REVIEW · UNKNOWN_CLASS"],
         ["No expected route", "Flagged, not treated as a violation",
          "REVIEW_REQUIRED"],
         ["No citable evidence", "Explanation withheld",
          "SKIPPED_NO_EVIDENCE"]],
        MARGIN_X, y, [168, 200, CW - 368], pad=6.5, font=8.4, hfont=8,
        leading=11.6)
    y = para(c,
        "Two thresholds are defined in the policy pack: detections at or above "
        "0.40 are routed; those below 0.20 are treated as noise; the band "
        "between is sent to review — the system never forces an uncertain "
        "prediction into a confident disposal recommendation.",
        MARGIN_X, y - 8, CW, size=8.2, leading=11.8, color=MUTED)

    y -= 14
    y = callout(c,
        "The LLM is not the decision authority. A deterministic, versioned "
        "policy engine makes every category-and-route decision; the language "
        "model only explains it.",
        MARGIN_X, y, CW, accent=INDIGO, fill=INDIGO_L, size=10, leading=14,
        bold=True, txt_color=INK)

    y -= 16
    kicker(c, "RESPONSIBLE-AI BEHAVIOUR", MARGIN_X, y, color=MUTED, size=7.8)
    y -= 12
    y = bullet(c, "unknown and low-confidence cases are routed to review, not "
               "silently placed in general waste.", MARGIN_X, y, CW, size=9,
               leading=12.6, bold_lead="Never defaults to general waste — ")
    y -= 5
    y = bullet(c, "every event stores the policy version and the rule id that "
               "produced the decision.", MARGIN_X, y, CW, size=9, leading=12.6,
               bold_lead="Deterministic & versioned — ")
    y -= 5
    y = bullet(c, "if retrieval or the language model fails, the disposal "
               "decision and the audit record still complete.", MARGIN_X, y, CW,
               size=9, leading=12.6, bold_lead="Graceful degradation — ")
    c.showPage()


# =========================================================================== #
#  PAGE 7 — END-TO-END COMPLIANCE WORKFLOW
# =========================================================================== #
def page07(c):
    y = new_page(c, "Workflow", "End-to-End Compliance Workflow")
    y = page_title(c, "End-to-End Compliance Workflow", y,
                   kicker_txt="06 · One image, one auditable event")

    y = para(c,
        "The same detection can end in compliance or in a violation depending "
        "only on the route the operator selects. Both outcomes below are real "
        "pipeline events captured during development — nothing is "
        "hardcoded.",
        MARGIN_X, y - 2, CW, size=9.4, leading=13.6)

    # input thumbnail + caption
    y -= 12
    thumb = 60
    cover_image(c, os.path.join(SAMPLES, "sample3.jpg"), MARGIN_X, y, thumb,
                thumb, r=9)
    text(c, "Real MedBin sample input", MARGIN_X + thumb + 14, y - 16,
         font="Sans-Bold", size=9.2, color=INK)
    text(c, "Pharmaceutical blister packs", MARGIN_X + thumb + 14, y - 30,
         font="Sans", size=8.4, color=BODY2)
    text(c, "static/samples/sample3.jpg", MARGIN_X + thumb + 14, y - 43,
         font="Mono", size=7.4, color=MUTED)
    y -= thumb + 12

    y = flow_h(c, [("Detect", "drug_packaging ×4"),
                   ("Normalize", "PHARMACEUTICAL"),
                   ("Confidence", "0.959"),
                   ("Policy", "expected BROWN"),
                   ("Actual", "operator route"),
                   ("Verify", "expected vs actual")],
               MARGIN_X, y, CW, h=50, gap=10, accent=TEAL, tsize=8.2,
               ssize=6.8)

    # outcome pair
    y -= 20
    colw = (CW - 22) / 2.0
    outcome_card(c, MARGIN_X, y, colw, "CORRECT", GREEN, GREEN_L,
                 "BROWN", "BROWN", "BROWN", "BROWN",
                 "Operator selected BROWN → matches expected.",
                 "event 9a9f2b0f · rule R-PHARMA · v1.1.0")
    y2 = outcome_card(c, MARGIN_X + colw + 22, y, colw, "VIOLATION", RED, RED_L,
                      "BROWN", "YELLOW", "BROWN", "YELLOW",
                      "Operator selected YELLOW → mismatch.",
                      "event 05b0846e · WRONG_WASTE_STREAM")
    y = y2

    y -= 18
    y = callout(c,
        "Both events share the same perception (drug_packaging ×4 → "
        "PHARMACEUTICAL, 0.959) and the same rule (R-PHARMA); only the "
        "operator's selected route differs. Each was retrieved and explained "
        "(RAG OK, LLM OK) and written to the audit trail.",
        MARGIN_X, y, CW, accent=TEAL, fill=TEAL_L, size=9.2, leading=13,
        txt_color=HexColor("#0B3B47"))

    y -= 14
    kicker(c, "WHAT EACH RUN RECORDS", MARGIN_X, y, color=MUTED, size=7.8)
    y -= 12
    y = para(c,
        "event id · timestamp · raw detector labels · canonical class · "
        "confidence · model id · expected route · rule id · policy version · "
        "actual route · compliance status · RAG status · LLM status · "
        "evidence IDs.",
        MARGIN_X, y, CW, font="Mono", size=8, leading=13, color=BODY2)
    c.showPage()


# =========================================================================== #
#  PAGE 8 — RAG, EVIDENCE & EXPLAINABILITY
# =========================================================================== #
def page08(c):
    y = new_page(c, "Evidence", "Evidence, Retrieval & Explainability")
    y = page_title(c, "Evidence, Retrieval & Explainability", y,
                   kicker_txt="07 · Grounded, or it stays silent")

    y = para(c,
        "Explanations are generated only from retrieved, citable evidence. The "
        "query is built from the structured decision, not free text, and if "
        "nothing relevant is retrieved the language model is not called at all.",
        MARGIN_X, y - 2, CW, size=9.4, leading=13.6)

    y -= 16
    y = flow_h(c, [("Structured", "decision"), ("Deterministic", "query"),
                   ("Retrieval", "Pinecone · k=8"), ("Evidence", "IDs"),
                   ("Grounding", "gate"), ("Explanation", "LLM")],
               MARGIN_X, y, CW, h=50, gap=9, accent=TEAL, tsize=8.2, ssize=6.8)

    y -= 18
    y = callout(c,
        "No evidence → no grounded explanation. The language model is never "
        "invoked without citable evidence IDs; with none, the event records "
        "SKIPPED_NO_EVIDENCE and no explanation is fabricated.",
        MARGIN_X, y, CW, accent=INDIGO, fill=INDIGO_L, size=10, leading=14,
        bold=True, txt_color=INK)

    y -= 20
    colw = (CW - 26) / 2.0
    lx, rx = MARGIN_X, MARGIN_X + colw + 26
    ly = ry = y
    ly = mini_section(c, "Deterministic query",
        "Built from the structured decision — canonical class, disposal "
        "stream, and rule — so retrieval targets the policy in force rather "
        "than an open-ended prompt.", lx, ly, colw, accent=TEAL)
    ly -= 18
    ly = mini_section(c, "Provenance preserved",
        "Evidence source and IDs are stored on the event. The pharmaceutical "
        "example above carried eight evidence IDs recorded alongside its "
        "decision.", lx, ly, colw, accent=TEAL)
    ly -= 18
    ly = mini_section(c, "Retrieval scope",
        "Retrieval runs against the Pinecone ‘brainchild’ index with its "
        "integrated embedding model, returning up to eight passages per "
        "query for the grounding gate to filter.", lx, ly, colw, accent=TEAL)

    ry = mini_section(c, "Explanation-only role",
        "The model describes the policy outcome in natural language; it cannot "
        "change the disposal route or override the rule that decided it.",
        rx, ry, colw, accent=INDIGO)
    ry -= 18
    ry = mini_section(c, "Hallucination guard",
        "Evidence IDs not present in retrieval are stripped, so unsupported "
        "citations are never surfaced to the operator.", rx, ry, colw,
        accent=INDIGO)
    ry -= 18
    ry = mini_section(c, "Safe degradation",
        "Retrieval and LLM calls are isolated; on failure their status is "
        "recorded as UNAVAILABLE and the decision still stands.", rx, ry, colw,
        accent=INDIGO)

    y = min(ly, ry) - 16
    y = para(c,
        "Index vector count and embedding dimension are inspected at runtime "
        "against the live Pinecone index; they are not asserted as fixed "
        "figures in this report.",
        MARGIN_X, y, CW, size=8.2, leading=11.8, color=MUTED)
    c.showPage()


# =========================================================================== #
#  PAGE 9 — AUDITABILITY, TESTING & ANALYTICS
# =========================================================================== #
def page09(c):
    y = new_page(c, "Audit & Testing", "Auditability, Testing & Analytics")
    y = page_title(c, "Auditability, Testing & Analytics", y,
                   kicker_txt="08 · Every event reconstructable")

    y = para(c,
        "Each analysis writes a single, self-describing event. Any past "
        "decision can be reconstructed from what the system saw, which rule "
        "fired, and the model and policy versions that produced it.",
        MARGIN_X, y - 2, CW, size=9.4, leading=13.6)

    y -= 20
    kicker(c, "AUDIT EVENT  ·  WHAT EACH ANALYSIS RECORDS", MARGIN_X, y,
           color=MUTED, size=7.8)
    y -= 11
    y = table(c,
        ["Field group", "Captured fields"],
        [["Identity & time", "event id, timestamp"],
         ["Perception", "raw detector labels, canonical class, confidence, "
          "model id"],
         ["Decision", "expected route, rule id, policy version"],
         ["Outcome", "actual / selected route, compliance status"],
         ["Support", "RAG status, LLM status, evidence IDs"]],
        MARGIN_X, y, [120, CW - 120], pad=7, font=8.6, hfont=8,
        leading=12.4)

    y -= 24
    kicker(c, "TESTING  ·  OFFLINE-VERIFIED vs REQUIRES ML RUNTIME", MARGIN_X, y,
           color=MUTED, size=7.8)
    y -= 13
    y = kpi_row(c, [
        ("62", "test functions total"),
        ("55", "passed offline here"),
        ("0", "failed / errored"),
        ("1", "skipped offline"),
        ("7", "Flask API · ml runtime"),
    ], MARGIN_X, y, CW, h=60, big_size=16)
    y = para(c,
        "Offline run in this environment: passed 55, failed 0, errored 0, "
        "skipped 1. The 7 Flask API tests require the ML runtime and are "
        "executed there — deferred, not counted as passed.",
        MARGIN_X, y - 9, CW, size=8.3, leading=12, color=MUTED)

    y -= 24
    kicker(c, "ANALYTICS  ·  DEVELOPMENT & TEST DATA (NOT A DEPLOYMENT)",
           MARGIN_X, y, color=MUTED, size=7.8)
    y -= 13
    y = kpi_row(c, [
        ("27", "events captured"),
        ("8", "CORRECT"),
        ("2", "VIOLATION"),
        ("16", "PENDING VERIF."),
        ("1", "REVIEW REQ."),
    ], MARGIN_X, y, CW, h=60, big_size=16, accent=INDIGO)
    y = para(c,
        "These are real pipeline outputs from development and testing, not "
        "hospital operational data. The analytics view aggregates recorded "
        "events; richer ward/station attribution is future work.",
        MARGIN_X, y - 9, CW, size=8.3, leading=12, color=MUTED)

    y -= 24
    kicker(c, "HOW THE AUDIT TRAIL IS DESIGNED TO SURFACE PATTERNS", MARGIN_X, y,
           color=MUTED, size=7.8)
    y -= 13
    y = flow_h(c, [("Recorded", "events"), ("Compliance", "status trend"),
                   ("Repeated", "patterns"), ("Review /", "intervention")],
               MARGIN_X, y, CW, h=50, gap=16, accent=INDIGO, tsize=8.6,
               ssize=7)
    c.showPage()


# =========================================================================== #
#  PAGE 10 — OPERATIONAL ROADMAP / BIN CAPACITY
# =========================================================================== #
def page10(c):
    y = new_page(c, "Roadmap", "Operational Roadmap")
    y = page_title(c, "Operational Roadmap", y,
                   kicker_txt="09 · Today's MVP vs what's next")

    y = para(c,
        "Everything on the left is implemented in the current MVP. Everything "
        "on the right is proposed and clearly not yet built — the distinction "
        "is kept explicit so no future capability reads as a shipped feature.",
        MARGIN_X, y - 2, CW, size=9.4, leading=13.6)

    y -= 16
    colw = (CW - 22) / 2.0
    current = ["Single-image analysis (not live video)",
               "7-stream deterministic policy pack (v1.1.0)",
               "Operator-selected actual route + verification",
               "Best-effort RAG + LLM explanation (graceful degradation)",
               "SQLite audit trail + analytics view",
               "9-endpoint Flask REST API"]
    future = ["Live capture / continuous monitoring",
              "Physical bin recognition & fill-level sensing",
              "IoT / weight sensors and threshold alerts",
              "Automated collection routing",
              "Facility-specific policy profiles",
              "Larger validation dataset & clinical validation"]

    def _ph(items):
        inner = colw - 26
        mh = [wrap(it, "Sans", 8.7, inner - 12) for it in items]
        ih = [8.7 * 1.16 + (len(m) - 1) * 12.2 for m in mh]
        return 21 + sum(ih) + 9 * len(items) + 8
    mh = max(_ph(current), _ph(future))
    panel_list(c, MARGIN_X, y, colw, "CURRENT MVP  ·  IMPLEMENTED", current,
               GREEN, fill=GREEN_L, minh=mh)
    yb = panel_list(c, MARGIN_X + colw + 22, y, colw,
                    "PROPOSED  ·  NOT YET IMPLEMENTED", future, AMBER,
                    fill=WHITE, dashed=True, minh=mh)
    y = yb

    y -= 20
    kicker(c, "FUTURE OPERATIONAL LAYER  ·  PROPOSED — NOT IMPLEMENTED",
           MARGIN_X, y, color=AMBER, size=7.6)
    y -= 12
    y = flow_h(c, [("Bin", "monitoring"), ("Capacity", "estimate"),
                   ("Threshold", "alert"), ("Collection", "request"),
                   ("Transport", None), ("Treatment /", "storage"),
                   ("Audit", None)],
               MARGIN_X, y, CW, h=46, gap=8, fill=AMBER_L, stroke=AMBER,
               accent=AMBER, arrow_color=AMBER, tsize=7.6, ssize=6.6,
               sub_color=HexColor("#9A6A18"))

    y -= 18
    y = callout(c,
        "Bin-capacity and fill-level tracking is a proposed future capability. "
        "The current MVP does not sense physical bins or measure fill levels; "
        "any such view would be a conceptual prototype, not sensor data.",
        MARGIN_X, y, CW, accent=AMBER, fill=AMBER_L, size=9.4, leading=13.4,
        txt_color=HexColor("#7A4A08"),
        title="FUTURE EXTENSION · NOT A SHIPPED FEATURE")

    y -= 14
    y = callout(c,
        "From point-of-disposal compliance toward facility-wide waste "
        "operational intelligence.",
        MARGIN_X, y, CW, accent=TEAL, fill=TEAL_L, size=10.5, leading=14.5,
        bold=True, txt_color=HexColor("#0B3B47"))
    c.showPage()


# =========================================================================== #
#  PAGE 11 — IMPACT, SCALABILITY & DEPLOYMENT
# =========================================================================== #
def page11(c):
    y = new_page(c, "Scalability", "Impact, Scalability & Deployment")
    y = page_title(c, "Impact, Scalability & Deployment", y,
                   kicker_txt="10 · From one station outward")

    y = para(c,
        "The architecture is designed to reduce segregation errors and make "
        "every decision traceable and reviewable. Benefits below are stated as "
        "intended outcomes of the design, not as measured deployment results.",
        MARGIN_X, y - 2, CW, size=9.4, leading=13.6)

    y -= 16
    kicker(c, "INTENDED IMPACT  ·  BY DESIGN, NOT MEASURED", MARGIN_X, y,
           color=MUTED, size=7.8)
    y -= 12
    icolw = (CW - 26) / 2.0
    iy_l = bullet(c, "Fewer wrong-stream disposals at the point of decision.",
                  MARGIN_X, y, icolw, size=9, leading=12.6, marker_color=TEAL)
    iy_l = bullet(c, "Traceable, evidence-grounded decisions for every event.",
                  MARGIN_X, iy_l - 6, icolw, size=9, leading=12.6,
                  marker_color=TEAL)
    iy_r = bullet(c, "Safer handling through earlier, consistent segregation.",
                  MARGIN_X + icolw + 26, y, icolw, size=9, leading=12.6,
                  marker_color=TEAL)
    iy_r = bullet(c, "Facility-wide compliance visibility over recorded events.",
                  MARGIN_X + icolw + 26, iy_r - 6, icolw, size=9, leading=12.6,
                  marker_color=TEAL)
    y = min(iy_l, iy_r)

    y -= 18
    kicker(c, "SCALABILITY PATH", MARGIN_X, y, color=MUTED, size=7.8)
    y -= 12
    y = flow_h(c, ["Disposal\npoint", "Ward", "Facility", "Multi-\nfacility",
                   ("Central", "compliance")],
               MARGIN_X, y, CW, h=48, gap=12, accent=INDIGO, tsize=8.4,
               ssize=6.8)
    y = para(c,
        "The policy engine already carries a facility-profile parameter; today "
        "a single ‘default’ profile is active. Rules and model "
        "version are configurable per profile as scale increases.",
        MARGIN_X, y - 8, CW, size=8.4, leading=12, color=MUTED)

    y -= 20
    kicker(c, "DEPLOYMENT PROPERTIES", MARGIN_X, y, color=MUTED, size=7.8)
    y -= 12
    colw = (CW - 26) / 2.0
    lx, rx = MARGIN_X, MARGIN_X + colw + 26
    ly = ry = y
    ly = mini_section(c, "Replaceable perception",
        "The model id is stamped on every event, so a stronger detector can be "
        "swapped in without touching the decision or audit layers.",
        lx, ly, colw, accent=TEAL)
    ly -= 16
    ly = mini_section(c, "Durable audit",
        "A SQLite audit trail today; the same event schema ports to a managed "
        "database for multi-facility scale.", lx, ly, colw, accent=TEAL)
    ry = mini_section(c, "Failure isolation",
        "Retrieval and language calls run best-effort; their failure is "
        "recorded but never blocks a disposal decision.", rx, ry, colw,
        accent=TEAL)
    ry -= 16
    ry = mini_section(c, "Event-based & modular",
        "Perception, policy, evidence, and explanation are independent stages "
        "joined by a recorded event, not a monolith.", rx, ry, colw,
        accent=TEAL)
    y = min(ly, ry)

    y -= 20
    kicker(c, "OBSERVED LATENCY  ·  SINGLE SAMPLE, TEAM ML ENV (NOT A BENCHMARK)",
           MARGIN_X, y, color=MUTED, size=7.6)
    y -= 12
    y = kpi_row(c, [
        ("~1.8s", "inference"),
        ("~0.3s", "retrieval"),
        ("~9s", "LLM explain"),
        ("~4.9s", "CLIP context"),
        ("~26s", "end-to-end"),
    ], MARGIN_X, y, CW, h=54, big_size=15)
    y = para(c,
        "Measured once on a single sample and dominated by network round-trips "
        "to hosted services. A 4→1 CLIP-encode change was verified numerically "
        "equivalent; its runtime effect is not yet measured.",
        MARGIN_X, y - 8, CW, size=8.2, leading=11.8, color=MUTED)
    c.showPage()


# =========================================================================== #
#  PAGE 12 — LIMITATIONS, ALIGNMENT & CONCLUSION
# =========================================================================== #
def page12(c):
    y = new_page(c, "Limitations", "Limitations, Alignment & Conclusion")
    y = page_title(c, "Limitations, Alignment & Conclusion", y,
                   kicker_txt="11 · Honest boundaries")

    kicker(c, "LIMITATIONS  ·  DISCLOSED", MARGIN_X, y, color=MUTED, size=7.8)
    y -= 10
    y = table(c,
        ["Limitation", "Handling / status"],
        [["Single image, not live video", "By design in the MVP; live capture "
          "is future work"],
         ["Perception limited to dataset classes", "Detector is replaceable; "
          "unknown classes → review"],
         ["Actual route is operator-selected", "Not physically sensed in the "
          "MVP"],
         ["CLIP context is an estimate", "Advisory only; not clinical ground "
          "truth"],
         ["RAG / LLM need network + credentials", "Degrade gracefully; the "
          "decision is unaffected"],
         ["No clinical / regulatory validation", "Not claimed; requires a "
          "formal study"],
         ["Analytics from dev / test data", "No operational or deployment "
          "claims are made"]],
        MARGIN_X, y, [180, CW - 180], pad=6, font=8.3, hfont=7.9,
        leading=11.4)

    y -= 16
    kicker(c, "EVALUATION-CRITERIA ALIGNMENT  ·  OFFICIAL WEIGHTS", MARGIN_X, y,
           color=MUTED, size=7.8)
    y -= 10
    y = table(c,
        ["Criterion", "Addressed by"],
        [["Innovation (15)", "Decision-boundary architecture: the model "
          "proposes, the deterministic policy disposes"],
         ["Problem Solving (20)", "End-to-end point-of-disposal workflow with "
          "verification, not just detection"],
         ["Technical Excellence (20)", "Policy engine, grounding gate, audit "
          "schema, and a 62-test suite"],
         ["AI Integration (15)", "Four AI/ML services with strict, separated "
          "roles"],
         ["User Experience (10)", "Operator-confirmed routing, clear "
          "compliance signals, analytics view"],
         ["Scalability (10)", "Replaceable perception, facility-profile "
          "parameter, portable audit schema"],
         ["Presentation Skills (10)", "This dossier plus an inspectable, "
          "reproducible repository"]],
        MARGIN_X, y, [130, CW - 130], pad=6, font=8.3, hfont=7.9,
        leading=11.4)

    y -= 18
    y = callout(c,
        "MediWaste AI is not designed merely to recognize medical waste; it is "
        "designed to turn recognition into policy-controlled, verifiable, "
        "explainable and auditable disposal intelligence.",
        MARGIN_X, y, CW, accent=TEAL, fill=TEAL_L, size=10.5, leading=15,
        bold=True, txt_color=HexColor("#0B3B47"), pad=13)

    y -= 26
    line(c, MARGIN_X + 90, y, PAGE_W - MARGIN_X - 90, y, color=HAIR, width=0.8)
    y -= 18
    text(c, "T H E   P R O G R E S S I O N", PAGE_W / 2.0, y, font="Sans-Bold",
         size=7.8, color=MUTED, align="center")
    y -= 16
    y = para(c,
        "What is it?   →   What does it mean in this context?   →   Where "
        "should it go?   →   Is the selected route correct?   →   Why?   →   "
        "What evidence supports it?   →   What happened?   →   What patterns "
        "are emerging?   →   How can the facility improve?",
        MARGIN_X + 24, y, CW - 48, size=9.3, leading=15.5, color=BODY2,
        align="center")
    y -= 20
    text(c, "From Waste Detection to Disposal Intelligence", PAGE_W / 2.0, y,
         font="Sans-Bold", size=13, color=TEAL, align="center")
    c.showPage()


def build():
    c = canvas.Canvas(OUT, pagesize=A4)
    c.setTitle("MediWaste AI — Final Report — BrainChild Season 2.0")
    c.setAuthor("Team Dekhte Aschi")
    c.setSubject("Intelligent Point-of-Disposal Medical-Waste "
                 "Segregation & Compliance Platform")
    cover(c)
    page02(c)
    page03(c)
    page04(c)
    page05(c)
    page06(c)
    page07(c)
    page08(c)
    page09(c)
    page10(c)
    page11(c)
    page12(c)
    c.save()
    print("WROTE", OUT)


if __name__ == "__main__":
    build()
