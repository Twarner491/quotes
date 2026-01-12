# Update Guide - Image Printing Feature



## 2. Raspberry Pi Update

### Prerequisites
- SSH access to your Raspberry Pi
- The Pi should already have the quote receipt printer code

### Update Steps:

```bash
# SSH into your Raspberry Pi
ssh pi@receipt.local
# (or use the IP address if .local doesn't work)

# Navigate to the quotes directory
cd ~/quotes

# Pull the latest changes from git
git pull origin main

# Ensure Pillow is installed for image processing
pip3 install --upgrade Pillow

# Restart the MQTT subscriber service
sudo systemctl restart receipt-printer-mqtt.service

# Check the service status
sudo systemctl status receipt-printer-mqtt.service

# View logs to verify it's running
journalctl -u receipt-printer-mqtt.service -f
```

### If the Pi doesn't have the code yet:

```bash
# SSH into Pi
ssh pi@receipt.local

# Clone the repository
git clone https://github.com/Twarner491/quotes.git
cd quotes

# Install dependencies
pip3 install -r requirements.txt

# Copy the systemd service file
sudo cp system-config/receipt-printer-mqtt.service /etc/systemd/system/

# Edit the service file to match your paths
sudo nano /etc/systemd/system/receipt-printer-mqtt.service

# Enable and start the service
sudo systemctl enable receipt-printer-mqtt.service
sudo systemctl start receipt-printer-mqtt.service
```

---

## 3. Testing the Full Pipeline

### Test Local (receipt.local):
1. Open http://receipt.local:5000
2. Enter a quote
3. Click the image icon and upload a small test image
4. Click print
5. Receipt should print with the image

### Test Public (receipt.onethreenine.net):
1. Open https://receipt.onethreenine.net
2. Enter a quote
3. Upload an image
4. Click print
5. Request goes: Browser → HA Webhook → MQTT → Pi → Printer

---

## Troubleshooting

### Image not printing?
```bash
# Check MQTT subscriber logs on Pi
journalctl -u receipt-printer-mqtt.service -n 50

# Common issues:
# - Pillow not installed: pip3 install Pillow
# - Image too large: Try a smaller image (< 500KB)
# - USB permissions: Check printer USB connection
```

### Home Assistant not forwarding?
- Check HA logs for webhook errors
- Verify MQTT broker is connected
- Test MQTT manually: Developer Tools → MQTT

### Print button errors?
- Check browser console (F12) for errors
- Verify network connectivity
- Check if HA webhook URL is correct in the HTML (public site)
