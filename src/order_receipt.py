#!/usr/bin/env python3
"""
Order packing-slip renderer for the theodore.net store.

Renders the whole slip as one 1-bit PIL image (previewable without the printer, printed with a
single escpos image call). Layout:

    theodore.net
    Order <orderNo>
    <date>
    ------------------------------
    IN THIS BOX
    <Kit name>
      contents (the live-site "what's in the box" text)
      ...
    <Kit name>          (a box may hold multiple kits)
      ...
    ------------------------------
    <Project title>            [ QR ]
    Build guide, video & docs  [ QR ]

No footer, no thank-you line (the handwritten note is a surprise). The kit `contents` come straight
from each product page's frontmatter `contents` (so the slip matches the store exactly).

Trigger via MQTT with {"type": "order", ...}; see ORDER_SCHEMA. render_order_receipt() is pure and
is unit-tested via `python3 order_receipt.py` (writes a preview PNG).
"""
from PIL import Image, ImageDraw, ImageFont
import textwrap

WIDTH = 384            # 80mm @ 203dpi
MARGIN = 14
CONTENT_W = WIDTH - 2 * MARGIN

ORDER_SCHEMA = {
    "type": "order",
    "orderNo": "1A2B3C4D",
    "date": "June 21, 2026",
    "items": [{"name": "Avian Visitors (+ Frame & Parts)", "contents": ["Everything in the Electronics Kit", "3D Printed backplate"]}],
    "projects": [{"title": "Avian Visitors", "url": "https://theodore.net/projects/AvianVisitors/"}],
}

_MONO = [
    "/Library/Fonts/JetBrainsMono-Regular.ttf", "/Users/twarn/Library/Fonts/JetBrainsMono-Regular.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", "/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf",
]
_MONO_BOLD = [
    "/Library/Fonts/JetBrainsMono-Bold.ttf", "/Users/twarn/Library/Fonts/JetBrainsMono-Bold.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", "/usr/share/fonts/truetype/noto/NotoSansMono-Bold.ttf",
]
_cache = {}

def _font(size, bold=False):
    key = (size, bold)
    if key not in _cache:
        for path in (_MONO_BOLD if bold else _MONO):
            try: _cache[key] = ImageFont.truetype(path, size); break
            except Exception: continue
        else: _cache[key] = ImageFont.load_default()
    return _cache[key]

def _char_w(font):
    b = font.getbbox("M"); return max(1, b[2] - b[0])

def _block(text, size=20, bold=False, align="left", width=CONTENT_W, indent=0):
    """Render a wrapped text block to a 1-bit image `width` px wide (left/center/right aligned)."""
    font = _font(size, bold)
    avail = width - indent
    cpl = max(6, avail // _char_w(font))
    lines = []
    for para in str(text).split("\n"):
        lines.extend(textwrap.wrap(para, width=cpl) or [""])
    lh = int(size * 1.42)
    img = Image.new("L", (width, lh * len(lines) + 2), 255)
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        b = font.getbbox(line); w = b[2] - b[0]
        if align == "center": x = (width - w) // 2
        elif align == "right": x = width - w
        else: x = indent
        d.text((x - b[0], i * lh), line, font=font, fill=0)
    return img

def _rule(width=CONTENT_W):
    img = Image.new("L", (WIDTH, 16), 255)
    ImageDraw.Draw(img).line([((WIDTH - width) // 2, 8), ((WIDTH + width) // 2, 8)], fill=0, width=1)
    return img

def _gap(h=8):
    return Image.new("L", (WIDTH, h), 255)

def _qr_img(url, target=200):
    """A crisp 1-bit QR (~target px), or None if qrcode isn't installed. Rendered at a whole-pixel
    module size with a proper quiet zone -- never downscaled, which is what muddled the old one."""
    try:
        import qrcode
    except Exception:
        return None
    qr = qrcode.QRCode(border=4, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url); qr.make(fit=True)
    modules = qr.modules_count + 2 * qr.border
    qr.box_size = max(3, round(target / modules))   # whole px per module -> sharp + scannable
    return qr.make_image(fill_color="black", back_color="white").convert("1")

def _guide_row(project):
    """Build-guide block: title + 'Build guide, video & docs' + url, then a big crisp QR centered below."""
    parts = [
        _block(project.get("title", ""), size=22, bold=True),
        _block("Build guide, video & docs", size=16),
        _block(project.get("url", ""), size=13),
    ]
    qr = _qr_img(project.get("url", ""), target=200)
    gap = 12
    text_h = sum(p.height for p in parts)
    qh = (gap + qr.height) if qr is not None else 0
    row = Image.new("L", (WIDTH, text_h + qh), 255)
    y = 0
    for p in parts: row.paste(p, (MARGIN, y)); y += p.height
    if qr is not None:
        row.paste(qr, ((WIDTH - qr.width) // 2, y + gap))   # centered, full quiet zone
    return row

def render_order_receipt(order):
    sec = []
    sec.append(_gap(10))
    sec.append(_block("theodore.net", size=38, bold=True, align="center"))
    if order.get("orderNo"): sec.append(_block("Order " + str(order["orderNo"]), size=19, align="center"))
    if order.get("date"): sec.append(_block(str(order["date"]), size=16, align="center"))
    sec.append(_rule())

    sec.append(_block("IN THIS BOX", size=17, bold=True))
    sec.append(_gap(6))
    for it in (order.get("items") or []):
        sec.append(_block(it.get("name", ""), size=24, bold=True))
        for c in (it.get("contents") or []):
            sec.append(_block("·  " + c, size=20, indent=22))
        sec.append(_gap(12))

    projects = order.get("projects") or []
    if projects:
        sec.append(_rule())
        sec.append(_gap(2))
        for p in projects:
            sec.append(_guide_row(p))
            sec.append(_gap(8))

    total_h = sum(s.height for s in sec)
    canvas = Image.new("L", (WIDTH, total_h), 255)
    y = 0
    for s in sec:
        canvas.paste(s, (0, y)); y += s.height
    return canvas.convert("1")


if __name__ == "__main__":
    sample = {
        "orderNo": "1AVPRINT",
        "date": "June 21, 2026",
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
