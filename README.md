# Quote Receipt Printer

A locally hosted web server that prints submitted quotes on a thermal receipt printer.

**Original Project & Tutorial:** [https://teddywarner.org/Projects/Quotes/](https://teddywarner.org/Projects/Quotes/)

## Hardware Requirements
- Raspberry Pi (tested on Pi 5, but any model with network + USB should work)
- USB Thermal Receipt Printer (80mm)
- Power supply for Printer & Pi

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
# Edit hosts file to point 127.0.1.1 to receipt
sudo nano /etc/hosts
sudo reboot
```

### 2. Install Dependencies
```bash
# System packages
sudo apt install -y python3-pip python3-dev python3-pil libusb-1.0-0-dev avahi-daemon git

# Enable mDNS
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
# Install with break-system-packages if on newer Debian/PiOS versions or use a venv
sudo pip3 install -r requirements.txt --break-system-packages
```

### 4. Printer Configuration
Plug in your printer and find its Vendor and Product IDs:
```bash
lsusb
# Look for your printer (e.g., STMicroelectronics)
# Example output: Bus 001 Device 005: ID 0483:5720
```

Find the Endpoint Addresses:
```bash
lsusb -v -d VENDOR:PRODUCT | grep -A 5 "bEndpointAddress"
# Note the OUT endpoint (e.g., 0x03) and IN endpoint (e.g., 0x81)
```

**Update `src/app.py`:**
Open `src/app.py` and update the constants at the top with your values:
```python
VENDOR_ID = 0x0483      # Your vendor ID
PRODUCT_ID = 0x5720     # Your product ID
OUT_EP = 0x03           # Your OUT endpoint
IN_EP = 0x81            # Your IN endpoint
```

**Set USB Permissions:**
Update the udev rule with your Vendor/Product IDs:
```bash
sudo nano system-config/99-thermal-printer.rules
```
Copy it to the system rules directory:
```bash
sudo cp system-config/99-thermal-printer.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 5. HTTPS & SSL Certificates
To host the frontend on the public web (GitHub Pages) while printing locally, the local server MUST run over HTTPS to avoid "Mixed Content" errors.

Generate self-signed certificates:
```bash
chmod +x generate_certs.sh
./generate_certs.sh
```
This creates `cert.pem` and `key.pem`. The Flask app will automatically detect them and switch to HTTPS port 5000.

### 6. Auto-Start Service
Configure the systemd service to run the app on boot.

1. Edit `system-config/receipt-printer.service` to match your username and path if different from defaults.
2. Install and enable the service:

```bash
sudo cp system-config/receipt-printer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable receipt-printer.service
sudo systemctl restart receipt-printer.service
```