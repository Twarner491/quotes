#!/usr/bin/env python3
"""
Order packing-slip renderer for the theodore.net store.

One 1-bit PIL image (previewable without the printer, printed with a single escpos image call), styled
to match the theodore.net invoice aesthetic: JetBrains Mono, NO bold, clean ruled grid, no bullet
glyphs -- hierarchy comes from size, spacing, and rules. Layout:

    theodore.net

    Order   <orderNo>
    Date    <date>
    --------------------------------------
    IN THIS BOX

    <Kit name>
        <content item>          (the literal items in the box -- a pack-and-check list)
        ...
    --------------------------------------
    <Project title>
    Build guide and projects write-up
    <link>

                  ***
       Thank you for your business.
              theodore.net

Trigger via MQTT with {"type": "order", ...}; see ORDER_SCHEMA. render_order_receipt() is pure;
`python3 order_receipt.py` writes a preview PNG.
"""
from PIL import Image, ImageDraw, ImageFont
import re
import textwrap

WIDTH = 384            # 80mm @ 203dpi
MARGIN = 18
CONTENT_W = WIDTH - 2 * MARGIN

ORDER_SCHEMA = {
    "type": "order",
    "orderNo": "1A2B3C4D",
    "date": "June 21, 2026",
    "items": [{"name": "Avian Visitors (+ Frame & Parts)", "contents": ["Inky Impression 13.3\" display", "Raspberry Pi Zero 2 W"]}],
    "projects": [{"title": "Avian Visitors", "url": "https://theodore.net/projects/AvianVisitors/"}],
}

# JetBrains Mono (the theodore.net brand mono), with graceful fallbacks. Regular weight only.
_MONO = [
    "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
    "/usr/local/share/fonts/JetBrainsMono-Regular.ttf",
    "/usr/share/fonts/JetBrainsMono-Regular.ttf",
    "/Library/Fonts/JetBrainsMono-Regular.ttf", "/Users/twarn/Library/Fonts/JetBrainsMono-Regular.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
]
_cache = {}

def _font(size):
    if size not in _cache:
        for path in _MONO:
            try: _cache[size] = ImageFont.truetype(path, size); break
            except Exception: continue
        else: _cache[size] = ImageFont.load_default()
    return _cache[size]

def _char_w(font):
    b = font.getbbox("M"); return max(1, b[2] - b[0])

def _block(text, size=20, align="left", indent=0):
    """Wrapped text -> full-width 1-bit image, left content margined to MARGIN (+indent)."""
    font = _font(size)
    avail = CONTENT_W - indent
    cpl = max(6, avail // _char_w(font))
    lines = []
    for para in str(text).split("\n"):
        lines.extend(textwrap.wrap(para, width=cpl) or [""])
    lh = int(size * 1.5)
    img = Image.new("L", (WIDTH, lh * len(lines) + 2), 255)
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        b = font.getbbox(line); w = b[2] - b[0]
        if align == "center": x = (WIDTH - w) // 2
        elif align == "right": x = WIDTH - MARGIN - w
        else: x = MARGIN + indent
        d.text((x - b[0], i * lh), line, font=font, fill=0)
    return img

def _kv(key, value, size=16, keyw=5):
    """Aligned key/value row (monospace keeps the columns straight), e.g. 'Order   TZR29K0'."""
    return _block(key.ljust(keyw) + "   " + str(value), size=size)

def _rule():
    img = Image.new("L", (WIDTH, 18), 255)
    ImageDraw.Draw(img).line([(MARGIN, 9), (WIDTH - MARGIN, 9)], fill=0, width=1)
    return img

def _gap(h=8):
    return Image.new("L", (WIDTH, h), 255)

def _clean_url(url):
    return re.sub(r"^https?://", "", str(url)).rstrip("/")

# QR is intentionally NOT printed (Teddy prefers the plain link + the QRs muddled on thermal). Kept
# here so it is a one-line change to bring back if wanted.
def _qr_img(url, target=200):
    try:
        import qrcode
    except Exception:
        return None
    qr = qrcode.QRCode(border=4, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url); qr.make(fit=True)
    modules = qr.modules_count + 2 * qr.border
    qr.box_size = max(3, round(target / modules))
    return qr.make_image(fill_color="black", back_color="white").convert("1")

def render_order_receipt(order):
    sec = []
    sec.append(_gap(12))
    sec.append(_block("theodore.net", size=36, align="center"))
    sec.append(_gap(14))
    if order.get("orderNo"): sec.append(_kv("Order", order["orderNo"]))
    if order.get("date"): sec.append(_kv("Date", order["date"]))
    sec.append(_gap(4))
    sec.append(_rule())
    sec.append(_block("IN THIS BOX", size=15))
    sec.append(_gap(8))
    for it in (order.get("items") or []):
        sec.append(_block(it.get("name", ""), size=22))
        sec.append(_gap(2))
        for c in (it.get("contents") or []):
            sec.append(_block(c, size=18, indent=28))
        sec.append(_gap(12))

    projects = order.get("projects") or []
    if projects:
        sec.append(_rule())
        sec.append(_gap(2))
        for p in projects:
            sec.append(_block(p.get("title", ""), size=20))
            sec.append(_block("Build guide and projects write-up", size=15))
            sec.append(_block(_clean_url(p.get("url", "")), size=15))
            sec.append(_gap(10))

    sec.append(_gap(10))
    sec.append(_block("***", size=18, align="center"))
    sec.append(_gap(6))
    sec.append(_block("Thank you for your business.", size=16, align="center"))
    sec.append(_gap(2))
    sec.append(_block("theodore.net", size=16, align="center"))
    sec.append(_gap(18))

    total_h = sum(s.height for s in sec)
    canvas = Image.new("L", (WIDTH, total_h), 255)
    y = 0
    for s in sec:
        canvas.paste(s, (0, y)); y += s.height
    return canvas.convert("1")


if __name__ == "__main__":
    sample = {
        "orderNo": "TZR29K0",
        "date": "September 16, 2025",
        "items": [
            {"name": "Avian Visitors (+ Frame & Parts)", "contents": ["Inky Impression 13.3\" display", "Raspberry Pi Zero 2 W", "microSD card", "40-pin header", "USB-C cable", "USB power brick", "3D printed backplate", "Oak frame & mat"]},
            {"name": "Bird Mic (Electronics + 3D Printed)", "contents": ["Raspberry Pi 4", "USB microphone", "microSD card", "USB-C cable", "USB power brick", "3D printed case"]},
        ],
        "projects": [{"title": "Avian Visitors", "url": "https://theodore.net/projects/AvianVisitors/"}],
    }
    img = render_order_receipt(sample)
    out = "/tmp/receipt_preview.png"
    bordered = Image.new("1", (img.width + 24, img.height + 24), 1)
    bordered.paste(img, (12, 12))
    bordered.save(out)
    print(f"rendered {img.width}x{img.height} -> {out}")
