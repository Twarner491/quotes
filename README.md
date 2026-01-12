# Quote Receipts

*"Did I really say that?" Why yes, you did.*

A thermal receipt printer for capturing silly quotes. Full project writeup at [teddywarner.org/Projects/Quotes](https://teddywarner.org/Projects/Quotes/).

---

## BOM

| Qty | Description | Price | Link |
|-----|-------------|-------|------|
| 1 | miemieyo Thermal Receipt Printer 80mm | $65.99 | [Amazon](https://www.amazon.com/dp/B0DFB82NPF) |
| 1 | MPRT 5 Rolls Thermal Paper 3-1/8" x 230' | $15.99 | [Amazon](https://www.amazon.com/dp/B0D14DYMHQ) |
| 1 | LM2596 Buck Converter | $7.99 | [Amazon](https://www.amazon.com/dp/B0DBVYP91F) |
| 1 | Raspberry Pi (any model) | ~$35-80 | [Raspberry Pi](https://www.raspberrypi.com/products/) |

---

## 1. Raspberry Pi Setup

Flash Raspberry Pi OS Lite (64-bit) and configure WiFi. SSH in:

```bash
ssh pi@raspberrypi.local
sudo apt update && sudo apt upgrade -y
```

Set hostname to `receipt`:

```bash
sudo hostnamectl set-hostname receipt
sudo nano /etc/hosts  # Change 127.0.1.1 to receipt
sudo reboot
```

Install dependencies:

```bash
sudo apt install -y python3-pip libusb-1.0-0-dev avahi-daemon
sudo systemctl enable avahi-daemon
```

---

## 2. Clone Repository

```bash
git clone https://github.com/Twarner491/quotes.git ~/quotes
cd ~/quotes
sudo pip3 install -r requirements.txt --break-system-packages
```

---

## 3. Printer Configuration

Find your printer's USB IDs:

```bash
lsusb                                              # e.g., ID 0483:5720
lsusb -v -d 0483:5720 | grep "bEndpointAddress"    # e.g., 0x03 OUT, 0x81 IN
```

Edit `src/app.py` with your values:

```python
VENDOR_ID = 0x0483
PRODUCT_ID = 0x5720
OUT_EP = 0x03
IN_EP = 0x81
```

Set USB permissions:

```bash
sudo cp system-config/99-thermal-printer.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

---

## 4. Local Flask Server

Start the service:

```bash
sudo cp system-config/receipt-printer-flask.service /etc/systemd/system/receipt-printer.service
sudo systemctl daemon-reload
sudo systemctl enable --now receipt-printer.service
```

Access at `http://receipt.local:5000`

---

## 5. Home Assistant Integration (Optional)

For external access via Home Assistant webhook → MQTT → Pi.

### Home Assistant Automation

Add to `automations.yaml`:

```yaml
alias: "Quote Receipt Print"
trigger:
  - platform: webhook
    webhook_id: quote_receipt_print
    allowed_methods: [POST]
    local_only: false
action:
  - service: mqtt.publish
    data:
      topic: "home/receipt_printer/print"
      payload_template: >
        {"quote": "{{ trigger.json.quote }}", "author": "{{ trigger.json.author | default('Anonymous') }}", "image": "{{ trigger.json.image | default('') }}"}
```

### Enable CORS

Add to `configuration.yaml`:

```yaml
http:
  cors_allowed_origins:
    - https://your-frontend-domain.com
```

### Pi MQTT Setup

Edit `src/mqtt_print_subscriber.py` with your MQTT broker IP and printer IDs, then:

```bash
sudo cp system-config/receipt-printer-mqtt.service /etc/systemd/system/receipt-printer.service
sudo systemctl daemon-reload
sudo systemctl enable --now receipt-printer.service
```

### Frontend

To enable remote access on your fork, add your HA webhook URL as a GitHub Secret:
   - Go to Settings → Secrets and variables → Actions
   - Add secret: `HA_WEBHOOK_URL` = Your Home Assistant webhook URL (e.g., `https://your-ha.com/api/webhook/quote_receipt_print`)

---

- [Fork this repository](https://github.com/Twarner491/quotes/fork)
- [Watch this repo](https://github.com/Twarner491/quotes/subscription)
- [Create issue](https://github.com/Twarner491/quotes/issues/new)
