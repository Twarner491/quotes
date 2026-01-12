#!/usr/bin/env python3
"""
MQTT Subscriber for Quote Receipt Printer
Listens for print jobs from Home Assistant via MQTT and prints them.
"""

import json
import paho.mqtt.client as mqtt
from escpos.printer import Usb
from datetime import datetime
import textwrap
import base64
import io
from PIL import Image

# ============================================================================
# CONFIGURATION
# ============================================================================
# MQTT Settings
MQTT_BROKER = "192.168.4.240"
MQTT_PORT = 1883
MQTT_TOPIC = "home/receipt_printer/print"
MQTT_STATUS_TOPIC = "home/receipt_printer/status"
# If your MQTT broker requires authentication, uncomment and set these:
# MQTT_USERNAME = "your_username"
# MQTT_PASSWORD = "your_password"

# Printer Settings - UPDATE THESE WITH YOUR PRINTER'S VALUES
# Run `lsusb` to find these values for your specific printer.
VENDOR_ID = 0x0483      # Your vendor ID
PRODUCT_ID = 0x5720     # Your product ID
OUT_EP = 0x03           # Your OUT endpoint
IN_EP = 0x81            # Your IN endpoint

# Image settings for thermal printer
# 80mm paper at 203 DPI = ~384 pixels width, leave margins
PRINTER_WIDTH_PIXELS = 384
MAX_IMAGE_WIDTH = 370  # Leave small margin on edges

# ============================================================================
# IMAGE PROCESSING
# ============================================================================
def process_image_for_thermal(image_base64):
    """
    Process a base64 encoded image for thermal printing.
    Converts to black & white, resizes to fit paper width.
    Returns a PIL Image ready for printing.
    """
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
        
        # Convert to grayscale then to 1-bit black & white with dithering
        img = img.convert('L')  # Grayscale
        img = img.point(lambda x: 0 if x < 128 else 255, '1')  # Simple threshold
        
        return img
    except Exception as e:
        print(f"[ERROR] Image processing error: {e}")
        return None

# ============================================================================
# PRINTER FUNCTION
# ============================================================================
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

        # Quote body
        p.set(align='left', bold=False)
        wrapped = textwrap.fill(f'"{quote}"', width=32)
        p.text(wrapped + "\n\n")

        # Attribution
        p.set(align='right', bold=False)
        p.text(f"-- {author}\n\n")

        # Print image if provided
        if image_base64:
            img = process_image_for_thermal(image_base64)
            if img:
                p.set(align='center')
                p.image(img, impl="bitImageColumn")
                p.text("\n")
                print(f"[OK] Printed image ({img.width}x{img.height})")

        # Footer
        p.set(align='center', underline=1)
        p.text("CERTIFIED STUPID\n")
        p.set(underline=0)
        p.text("No refunds. No context.\n")
        p.text("Memories printed. Dignity sold.\n")
        p.text("receipt.onethreenine.net\n\n")

        # Cut
        p.cut()
        p.close()

        print(f"[OK] Printed quote: \"{quote[:30]}...\" by {author}")
        return True

    except Exception as e:
        print(f"[ERROR] Print error: {e}")
        return False

# ============================================================================
# MQTT CALLBACKS
# ============================================================================
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[OK] Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        print(f"[OK] Subscribed to topic: {MQTT_TOPIC}")
        # Publish online status
        client.publish(MQTT_STATUS_TOPIC, json.dumps({"status": "online"}), retain=True)
    else:
        print(f"[ERROR] Failed to connect to MQTT broker. Return code: {rc}")

def on_disconnect(client, userdata, rc, properties=None):
    print(f"[WARN] Disconnected from MQTT broker. Return code: {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        quote = payload.get("quote", "").strip()
        author = payload.get("author", "Anonymous").strip()
        image_base64 = payload.get("image")  # Optional base64 encoded image

        if not quote:
            print("[WARN] Received empty quote, ignoring.")
            return

        has_image = " (with image)" if image_base64 else ""
        print(f"[INFO] Received print job{has_image}: \"{quote[:50]}...\" by {author}")
        
        success = print_quote(quote, author, image_base64)
        
        # Publish result back to status topic
        result = {"last_print": "success" if success else "failed", "quote": quote[:50], "had_image": bool(image_base64)}
        client.publish(MQTT_STATUS_TOPIC, json.dumps(result))

    except json.JSONDecodeError:
        print(f"[ERROR] Invalid JSON payload: {msg.payload}")
    except Exception as e:
        print(f"[ERROR] Error processing message: {e}")

# ============================================================================
# MAIN
# ============================================================================
def main():
    print("=" * 50)
    print("Quote Receipt Printer - MQTT Subscriber")
    print("=" * 50)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    
    # Uncomment if authentication is required:
    # client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Set Last Will and Testament (LWT) for offline status
    client.will_set(MQTT_STATUS_TOPIC, json.dumps({"status": "offline"}), retain=True)

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        print(f"[INFO] Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down...")
        client.publish(MQTT_STATUS_TOPIC, json.dumps({"status": "offline"}), retain=True)
        client.disconnect()
    except Exception as e:
        print(f"[ERROR] Connection error: {e}")

if __name__ == "__main__":
    main()
