from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from escpos.printer import Usb
from datetime import datetime
import textwrap

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

def print_quote(quote, author="Anonymous"):
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

        # Quote body
        p.set(align='left', bold=False)
        # Wrap text to 32 characters for standard 80mm thermal paper with this font size
        wrapped = textwrap.fill(f'"{quote}"', width=32)
        p.text(wrapped + "\n\n")

        # Attribution
        p.set(align='right', bold=False)
        p.text(f"-- {author}\n\n")

        # Footer
        p.set(align='center', underline=1)
        p.text("CERTIFIED STUPID\n")
        p.set(underline=0)
        p.text("No refunds. No context.\n")
        p.text("Memories printed. Dignity sold.\n\n")

        # QR code (optional) - points to the local server
        p.qr("https://receipt.local", size=6, center=True)
        p.text("\n")

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
    return render_template('index.html')

@app.route('/status')
def status():
    return jsonify({'status': 'online', 'message': 'Printer is ready'})

@app.route('/print', methods=['POST'])
def print_receipt():
    data = request.json
    quote = data.get('quote', '').strip()
    author = data.get('author', 'Anonymous').strip()

    if not quote:
        return jsonify({'success': False, 'error': 'Quote cannot be empty'}), 400

    success = print_quote(quote, author)

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

