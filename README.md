# Quote Receipt Printer

A thermal receipt printer for capturing quotes, powered by Home Assistant and MQTT.

**Original Project & Tutorial:** [https://teddywarner.org/Projects/Quotes/](https://teddywarner.org/Projects/Quotes/)

## Architecture

```
┌──────────────────────┐     ┌──────────────────────┐     ┌─────────────┐     ┌─────────────────┐
│ receipt.onethreenine │────▶│ admin.onethreenine   │────▶│ MQTT Broker │────▶│ Receipt Printer │
│      .net            │     │ (Home Assistant)     │     │192.168.4.240│     │   (RPi + USB)   │
│   (GitHub Pages)     │     │    Webhook API       │     │             │     │                 │
└──────────────────────┘     └──────────────────────┘     └─────────────┘     └─────────────────┘
         HTTPS                      HTTPS                      MQTT                  USB
```

## Hardware Requirements
- Raspberry Pi (tested on Pi 5, but any model with network + USB should work)
- USB Thermal Receipt Printer (80mm)
- Power supply for Printer & Pi
- MQTT Broker (e.g., Mosquitto at 192.168.4.240:1883)
- Home Assistant instance with external access

## Installation Guide

### 1. System Setup
Flash Raspberry Pi OS Lite (64-bit) and configure WiFi.
SSH into your Pi:
```bash
ssh pi@raspberrypi.local
```

Update system and set hostname to `receipt`:
```bash
sudo apt update && sudo apt upgrade -y
sudo hostnamectl set-hostname receipt
sudo nano /etc/hosts  # Point 127.0.1.1 to receipt
sudo reboot
```

### 2. Install Dependencies
```bash
sudo apt install -y python3-pip python3-dev python3-pil libusb-1.0-0-dev avahi-daemon git
sudo systemctl enable avahi-daemon
sudo systemctl start avahi-daemon
```

### 3. Project Setup
Clone this repository:
```bash
cd ~
git clone https://github.com/Twarner491/quotes.git
cd quotes
```

Install Python requirements:
```bash
sudo pip3 install -r requirements.txt --break-system-packages
```

### 4. Printer Configuration
Plug in your printer and find its Vendor and Product IDs:
```bash
lsusb
# Example output: Bus 001 Device 005: ID 0483:5720
```

Find the Endpoint Addresses:
```bash
lsusb -v -d 0483:5720 | grep -A 5 "bEndpointAddress"
# Note the OUT endpoint (e.g., 0x03) and IN endpoint (e.g., 0x81)
```

**Update `src/mqtt_print_subscriber.py`:**
```python
VENDOR_ID = 0x0483      # Your vendor ID
PRODUCT_ID = 0x5720     # Your product ID
OUT_EP = 0x03           # Your OUT endpoint
IN_EP = 0x81            # Your IN endpoint
```

**Set USB Permissions:**
```bash
sudo cp system-config/99-thermal-printer.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 5. MQTT Configuration
Update the MQTT settings in `src/mqtt_print_subscriber.py`:
```python
MQTT_BROKER = "192.168.4.240"
MQTT_PORT = 1883
MQTT_TOPIC = "home/receipt_printer/print"
```

If your MQTT broker requires authentication:
```python
MQTT_USERNAME = "your_username"
MQTT_PASSWORD = "your_password"
```

### 6. Home Assistant Setup
See `system-config/home-assistant-config.md` for detailed instructions.

Quick summary:
1. Add the webhook automation to receive print requests
2. Configure CORS to allow requests from `receipt.onethreenine.net`
3. Restart Home Assistant

### 7. Auto-Start Service
```bash
sudo cp system-config/receipt-printer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable receipt-printer.service
sudo systemctl start receipt-printer.service
```

Check status:
```bash
sudo systemctl status receipt-printer.service
```

### 8. Hosting the Frontend (GitHub Pages)
1. Run the build script:
   ```bash
   python3 build_static.py
   ```
2. Commit and push the `docs/` folder to GitHub.
3. In GitHub Repository Settings -> Pages:
   - Source: **Deploy from a branch**
   - Branch: **main**, Folder: **/docs**
4. Set custom domain: `receipt.onethreenine.net`

## Testing

### Test MQTT Subscriber Locally
```bash
cd ~/quotes
python3 src/mqtt_print_subscriber.py
```

### Test Print via MQTT
```bash
mosquitto_pub -h 192.168.4.240 -t "home/receipt_printer/print" \
  -m '{"quote": "Test quote!", "author": "Tester"}'
```

### Test via Home Assistant Webhook
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"quote": "Hello World", "author": "Test"}' \
  https://admin.onethreenine.net/api/webhook/quote_receipt_print
```

## Troubleshooting

- **Printer Error:** Check USB connection and ensure IDs match `lsusb` output.
- **MQTT Connection Failed:** Verify broker IP/port and firewall rules.
- **Webhook 404:** Ensure the automation is enabled in Home Assistant.
- **CORS Error:** Add `receipt.onethreenine.net` to HA's `cors_allowed_origins`.
- **Permission Denied:**
  ```bash
  sudo usermod -a -G lp,dialout $USER
  sudo reboot
  ```
