from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from escpos.printer import Usb
from datetime import datetime
import textwrap
import base64
import io
from PIL import Image, ImageEnhance, ImageFilter
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
            p.set(align='left', bold=False)
            # Wrap text to 32 characters for standard 80mm thermal paper with this font size
            wrapped = textwrap.fill(f'"{quote}"', width=32)
            p.text(wrapped + "\n\n")

            # Attribution
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
    return jsonify({'status': 'online', 'message': 'Printer is ready'})

@app.route('/print', methods=['POST'])
def print_receipt():
    data = request.json
    quote = data.get('quote', '').strip()
    author = data.get('author', 'Anonymous').strip()
    image_base64 = data.get('image')  # Optional base64 encoded image

    # Allow printing if either quote or image is provided
    if not quote and not image_base64:
        return jsonify({'success': False, 'error': 'Quote or image required'}), 400

    success = print_quote(quote, author, image_base64)

    if success:
        return jsonify({'success': True, 'message': 'Receipt printed!'})
    else:
        return jsonify({'success': False, 'error': 'Printer error. Check server logs.'}), 500

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

