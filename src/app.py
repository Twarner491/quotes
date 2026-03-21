from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from escpos.printer import Usb
from datetime import datetime
import textwrap
import base64
import io
import unicodedata
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import numpy as np

app = Flask(__name__)
CORS(app) # Allow cross-origin requests

# ============================================================================
# CONFIGURATION
# ============================================================================
# UPDATE THESE WITH YOUR PRINTER'S VALUES
# Run `lsusb` to find these values for your specific printer.
VENDOR_ID = 0x0483      # Your vendor ID
PRODUCT_ID = 0x5720     # Your product ID
OUT_EP = 0x03           # Your OUT endpoint
IN_EP = 0x81            # Your IN endpoint

# Image settings for thermal printer
# 80mm paper at 203 DPI = ~384 pixels width, leave margins
PRINTER_WIDTH_PIXELS = 384
MAX_IMAGE_WIDTH = 370  # Leave small margin on edges

# Dithering mode: 'floyd-steinberg', 'ordered', or 'threshold'
# Floyd-Steinberg produces the best results for photos
# Ordered dithering gives a more retro/patterned look
# Threshold is the simple on/off (original behavior)
DITHER_MODE = 'floyd-steinberg'

# Image enhancement settings (1.0 = no change)
CONTRAST_BOOST = 1.2   # Increase contrast slightly for better thermal printing
SHARPNESS_BOOST = 1.3  # Sharpen edges for clearer output

# ============================================================================
# IMAGE PROCESSING (r1b-inspired algorithms)
# ============================================================================

# 8x8 Bayer ordered dithering matrix (from r1b)
BAYER_MATRIX_8X8 = np.array([
    [ 0, 32,  8, 40,  2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44,  4, 36, 14, 46,  6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [ 3, 35, 11, 43,  1, 33,  9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47,  7, 39, 13, 45,  5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21]
], dtype=np.float32) / 64.0  # Normalize to 0-1 range

def ordered_dither(img_array):
    """
    Apply ordered (Bayer) dithering to a grayscale image array.
    Inspired by r1b's R1B_DTHR_ORD algorithm.
    Produces a retro, patterned appearance.
    """
    height, width = img_array.shape
    # Tile the Bayer matrix to cover the entire image
    threshold_matrix = np.tile(BAYER_MATRIX_8X8,
                               (height // 8 + 1, width // 8 + 1))[:height, :width]
    # Apply threshold: pixel > threshold -> white, else black
    return (img_array > threshold_matrix * 255).astype(np.uint8) * 255

def process_image_for_thermal(image_base64, dither_mode=None, contrast=None, sharpness=None):
    """
    Process a base64 encoded image for thermal printing.
    Uses r1b-inspired dithering algorithms for better quality output.

    Dithering modes:
    - 'floyd-steinberg': Best for photos, smooth gradients (default)
    - 'ordered': Retro patterned look, good for graphics
    - 'threshold': Simple on/off, fastest but loses detail

    Returns a PIL Image ready for printing.
    """
    # Use defaults if not specified
    if dither_mode is None:
        dither_mode = DITHER_MODE
    if contrast is None:
        contrast = CONTRAST_BOOST
    if sharpness is None:
        sharpness = SHARPNESS_BOOST

    try:
        # Decode base64 image
        image_data = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(image_data))

        # Convert to RGB if necessary (handles RGBA, palette, etc.)
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create white background for transparent images
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Resize to fit printer width while maintaining aspect ratio
        if img.width > MAX_IMAGE_WIDTH:
            ratio = MAX_IMAGE_WIDTH / img.width
            new_height = int(img.height * ratio)
            img = img.resize((MAX_IMAGE_WIDTH, new_height), Image.Resampling.LANCZOS)

        # Limit height to reasonable size (max 400px to not use too much paper)
        if img.height > 400:
            ratio = 400 / img.height
            new_width = int(img.width * ratio)
            img = img.resize((new_width, 400), Image.Resampling.LANCZOS)

        # Convert to grayscale for processing
        img = img.convert('L')

        # Apply contrast enhancement (helps thermal printing)
        if contrast != 1.0:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(contrast)

        # Apply sharpening (makes edges clearer on thermal paper)
        if sharpness != 1.0:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(sharpness)

        # Apply dithering based on selected mode
        if dither_mode == 'floyd-steinberg':
            # PIL's built-in Floyd-Steinberg dithering
            # This is what r1b calls R1B_DTHR_FS
            img = img.convert('1')
        elif dither_mode == 'ordered':
            # Ordered (Bayer) dithering - r1b's R1B_DTHR_ORD
            img_array = np.array(img, dtype=np.float32)
            dithered = ordered_dither(img_array)
            img = Image.fromarray(dithered, mode='L').convert('1')
        else:
            # Simple threshold (original behavior)
            img = img.point(lambda x: 0 if x < 128 else 255, '1')

        return img
    except Exception as e:
        print(f"Image processing error: {e}")
        return None

# ============================================================================
# TEXT RENDERING (for non-ASCII: CJK, Arabic, emoji, etc.)
# ============================================================================
TEXT_FONT_SIZE = 22
AUTHOR_FONT_SIZE = 18
EMOJI_NATIVE_SIZE = 109  # NotoColorEmoji only renders at this size

_font_cache = {}

def _load_text_font(size):
    """Load a Unicode-capable text font (CJK/Arabic/Latin) at the given size."""
    key = ("text", size)
    if key not in _font_cache:
        for path in [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        ]:
            try:
                _font_cache[key] = ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
                return _font_cache[key]
            except Exception:
                continue
        _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]

def _load_emoji_font():
    """Load the color emoji font at its native size."""
    if "emoji" not in _font_cache:
        try:
            _font_cache["emoji"] = ImageFont.truetype(
                "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
                EMOJI_NATIVE_SIZE)
        except Exception:
            _font_cache["emoji"] = None
    return _font_cache["emoji"]

def _is_emoji(ch):
    """Check if a character is an emoji."""
    cp = ord(ch)
    if cp >= 0x1F600 and cp <= 0x1F64F:
        return True
    if cp >= 0x1F300 and cp <= 0x1F5FF:
        return True
    if cp >= 0x1F680 and cp <= 0x1F6FF:
        return True
    if cp >= 0x1F900 and cp <= 0x1F9FF:
        return True
    if cp >= 0x1FA00 and cp <= 0x1FA6F:
        return True
    if cp >= 0x1FA70 and cp <= 0x1FAFF:
        return True
    if cp >= 0x2600 and cp <= 0x26FF:
        return True
    if cp >= 0x2700 and cp <= 0x27BF:
        return True
    if cp >= 0xFE00 and cp <= 0xFE0F:
        return True
    if cp == 0x200D:
        return True
    if cp == 0x20E3:
        return True
    if cp >= 0xE0020 and cp <= 0xE007F:
        return True
    cat = unicodedata.category(ch)
    if cat == "So":
        return cp > 0x2100
    return False

def _render_emoji_glyph(ch, target_height):
    """Render a single emoji at native size and scale down to target_height."""
    emoji_font = _load_emoji_font()
    if not emoji_font:
        return None, 0
    try:
        canvas = Image.new("RGBA", (EMOJI_NATIVE_SIZE * 2, EMOJI_NATIVE_SIZE * 2), (255, 255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        draw.text((0, 0), ch, font=emoji_font, embedded_color=True)
        bbox = canvas.getbbox()
        if not bbox:
            return None, 0
        cropped = canvas.crop(bbox)
        ratio = target_height / cropped.height
        new_w = max(1, int(cropped.width * ratio))
        scaled = cropped.resize((new_w, target_height), Image.Resampling.LANCZOS)
        gray = Image.new("L", scaled.size, 255)
        for y in range(scaled.height):
            for x in range(scaled.width):
                r, g, b, a = scaled.getpixel((x, y))
                if a > 0:
                    lum = int(0.299 * r + 0.587 * g + 0.114 * b)
                    lum = int(lum * (a / 255) + 255 * (1 - a / 255))
                    gray.putpixel((x, y), lum)
        return gray, new_w
    except Exception:
        return None, 0

def needs_image_rendering(text):
    """Check if text contains characters the printer can't handle natively."""
    for ch in text:
        if ord(ch) > 127:
            return True
    return False

def _segment_text(text):
    """Split text into runs of (is_emoji, substring)."""
    segments = []
    current = ""
    current_is_emoji = False
    for ch in text:
        ch_emoji = _is_emoji(ch)
        if current and ch_emoji != current_is_emoji:
            segments.append((current_is_emoji, current))
            current = ch
            current_is_emoji = ch_emoji
        else:
            current += ch
            current_is_emoji = ch_emoji
    if current:
        segments.append((current_is_emoji, current))
    return segments

def _measure_segment(seg_is_emoji, seg_text, text_font, glyph_height):
    """Measure the pixel width of a text segment."""
    if seg_is_emoji:
        w = 0
        for ch in seg_text:
            _, ew = _render_emoji_glyph(ch, glyph_height)
            w += ew if ew else glyph_height
        return w
    else:
        bbox = text_font.getbbox(seg_text)
        return bbox[2] - bbox[0] if bbox else 0

def render_text_image(text, font_size=TEXT_FONT_SIZE, max_width=MAX_IMAGE_WIDTH,
                      align="left", bold=False):
    """Render text as a 1-bit image for thermal printing with emoji support."""
    text_font = _load_text_font(font_size)
    glyph_height = int(font_size * 1.2)
    line_height = int(font_size * 1.4)

    lines = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current_line = ""
        current_width = 0
        for char in paragraph:
            is_em = _is_emoji(char)
            if is_em:
                _, char_w = _render_emoji_glyph(char, glyph_height)
                char_w = char_w if char_w else glyph_height
            else:
                test = current_line + char
                bbox = text_font.getbbox(test)
                test_w = bbox[2] - bbox[0] if bbox else 0
                char_w = test_w - current_width
            if current_width + char_w > max_width and current_line:
                lines.append(current_line)
                current_line = char
                if is_em:
                    current_width = char_w
                else:
                    bbox = text_font.getbbox(char)
                    current_width = bbox[2] - bbox[0] if bbox else 0
            else:
                current_line += char
                if is_em:
                    current_width += char_w
                else:
                    bbox = text_font.getbbox(current_line)
                    current_width = bbox[2] - bbox[0] if bbox else 0
        if current_line:
            lines.append(current_line)

    if not lines:
        return None

    img_height = line_height * len(lines) + 4
    img = Image.new("L", (max_width, img_height), 255)
    draw = ImageDraw.Draw(img)

    for i, line in enumerate(lines):
        y = i * line_height
        segments = _segment_text(line)

        total_w = 0
        for seg_emoji, seg_text in segments:
            total_w += _measure_segment(seg_emoji, seg_text, text_font, glyph_height)

        if align == "center":
            x = (max_width - total_w) // 2
        elif align == "right":
            x = max_width - total_w
        else:
            x = 0

        for seg_emoji, seg_text in segments:
            if seg_emoji:
                for ch in seg_text:
                    emoji_img, ew = _render_emoji_glyph(ch, glyph_height)
                    if emoji_img:
                        ey = y + (line_height - glyph_height) // 2
                        img.paste(emoji_img, (x, ey))
                        x += ew
                    else:
                        x += glyph_height
            else:
                draw.text((x, y), seg_text, fill=0, font=text_font)
                bbox = text_font.getbbox(seg_text)
                x += bbox[2] - bbox[0] if bbox else 0

    return img.convert("1")

# ============================================================================
# PAPER STATUS
# ============================================================================
PAPER_STATUS_LABELS = {0: "out", 1: "near_end", 2: "ok"}

def check_paper():
    """Check paper status. Returns (status_int, label)."""
    try:
        p = Usb(VENDOR_ID, PRODUCT_ID, out_ep=OUT_EP, in_ep=IN_EP)
        status = p.paper_status()
        p.close()
    except Exception as e:
        print(f"Could not query paper status: {e}")
        return (2, "unknown")
    return (status, PAPER_STATUS_LABELS.get(status, "unknown"))

def print_quote(quote, author="Anonymous", image_base64=None):
    try:
        # Initialize printer with correct endpoints
        p = Usb(VENDOR_ID, PRODUCT_ID, out_ep=OUT_EP, in_ep=IN_EP)

        # Header
        p.set(align='center', bold=True, width=2, height=2)
        p.text("QUOTE RECEIPT\n")
        p.set(align='center', bold=False, width=1, height=1)
        p.text("=" * 32 + "\n")
        p.text(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        p.text("=" * 32 + "\n\n")

        # Quote body (if provided)
        if quote:
            quote_text = f'\u201c{quote}\u201d'
            author_text = f"\u2014 {author}"
            if needs_image_rendering(quote) or needs_image_rendering(author):
                quote_img = render_text_image(quote_text, font_size=TEXT_FONT_SIZE, align="left")
                if quote_img:
                    p.set(align='center')
                    p.image(quote_img, impl="bitImageColumn")
                author_img = render_text_image(author_text, font_size=AUTHOR_FONT_SIZE, align="right")
                if author_img:
                    p.image(author_img, impl="bitImageColumn")
                p.text("\n")
            else:
                p.set(align='left', bold=False)
                wrapped = textwrap.fill(f'"{quote}"', width=32)
                p.text(wrapped + "\n\n")
                p.set(align='right', bold=False)
                p.text(f"-- {author}\n\n")
        else:
            # Image only - just add some spacing
            p.text("\n")

        # Print image if provided
        if image_base64:
            img = process_image_for_thermal(image_base64)
            if img:
                p.set(align='center')
                p.image(img, impl="bitImageColumn")
                p.text("\n")

        # Footer
        p.set(align='center', underline=1)
        p.text("CERTIFIED STUPID\n")
        p.set(underline=0)
        p.text("No refunds. No context.\n")
        p.text("Memories printed. Dignity sold.\n")
        p.text("receipt.onethreenine.net\n\n")

        # Cut
        p.cut()
        # Close connection to release USB resource
        p.close()

        return True

    except Exception as e:
        print(f"Print error: {e}")
        return False

@app.route('/')
def index():
    return render_template('index.html', show_about=False)

@app.route('/about')
def about():
    return render_template('index.html', show_about=True)

@app.route('/status')
def status():
    paper_status, paper_label = check_paper()
    return jsonify({'status': 'online', 'paper': paper_label})

@app.route('/print', methods=['POST'])
def print_receipt():
    data = request.json
    quote = data.get('quote', '').strip()
    author = data.get('author', 'Anonymous').strip()
    image_base64 = data.get('image')  # Optional base64 encoded image

    # Allow printing if either quote or image is provided
    if not quote and not image_base64:
        return jsonify({'success': False, 'error': 'Quote or image required'}), 400

    # Check paper before printing
    paper_status, paper_label = check_paper()
    if paper_status == 0:
        return jsonify({'success': False, 'error': 'Out of paper', 'paper': 'out'}), 503

    success = print_quote(quote, author, image_base64)

    # Re-check paper after printing
    _, paper_label_after = check_paper()

    if success:
        return jsonify({'success': True, 'message': 'Receipt printed!', 'paper': paper_label_after})
    else:
        return jsonify({'success': False, 'error': 'Printer error. Check server logs.', 'paper': paper_label_after}), 500

if __name__ == '__main__':
    # Running on port 5000. HTTPS is recommended for modern browser features.
    # To generate certs: openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
    import os
    if os.path.exists('cert.pem') and os.path.exists('key.pem'):
        print(" * Running in HTTPS mode")
        app.run(host='0.0.0.0', port=5000, debug=True, ssl_context=('cert.pem', 'key.pem'))
    else:
        print(" * Running in HTTP mode (Generate cert.pem and key.pem for HTTPS)")
        app.run(host='0.0.0.0', port=5000, debug=True)

