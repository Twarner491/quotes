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

# ============================================================================
# PRINTER FUNCTION
# ============================================================================
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

        # QR code (optional)
        p.qr("https://github.com/Twarner491/quotes", size=6, center=True)
        p.text("\n")

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

        if not quote:
            print("[WARN] Received empty quote, ignoring.")
            return

        print(f"[INFO] Received print job: \"{quote[:50]}...\" by {author}")
        
        success = print_quote(quote, author)
        
        # Publish result back to status topic
        result = {"last_print": "success" if success else "failed", "quote": quote[:50]}
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
