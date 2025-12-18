# Home Assistant Configuration for Quote Receipt Printer

Add this automation to your Home Assistant configuration to receive print requests
from the web frontend and publish them to MQTT for the receipt printer.

## Option 1: Webhook Automation (Recommended)

Add this to your `automations.yaml` or create via the UI:

```yaml
alias: "Quote Receipt Print Webhook"
description: "Receives quote print requests from web and publishes to MQTT"
trigger:
  - platform: webhook
    webhook_id: quote_receipt_print
    allowed_methods:
      - POST
    local_only: false
action:
  - service: mqtt.publish
    data:
      topic: "home/receipt_printer/print"
      payload_template: >
        {
          "quote": "{{ trigger.json.quote }}",
          "author": "{{ trigger.json.author | default('Anonymous') }}"
        }
mode: single
```

## Webhook URL

Once you've added this automation, the webhook will be accessible at:

```
https://your-home-assistant-url/api/webhook/quote_receipt_print
```

For your setup, this would be:
```
https://admin.onethreenine.net/api/webhook/quote_receipt_print
```

## CORS Configuration (Important!)

Since the webhook will be called from a different domain (receipt.onethreenine.net),
you need to enable CORS in your Home Assistant configuration.

Add this to your `configuration.yaml`:

```yaml
http:
  cors_allowed_origins:
    - https://receipt.onethreenine.net
```

Then restart Home Assistant.

## Testing

You can test the webhook with curl:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"quote": "Test quote", "author": "Tester"}' \
  https://admin.onethreenine.net/api/webhook/quote_receipt_print
```

## MQTT Topics

The automation publishes to:
- **Print requests:** `home/receipt_printer/print`

The receipt printer subscriber publishes status to:
- **Status:** `home/receipt_printer/status`

## Option 2: Using a Script (Alternative)

If you prefer using a script instead of an automation:

```yaml
# In scripts.yaml
print_quote_receipt:
  alias: "Print Quote Receipt"
  sequence:
    - service: mqtt.publish
      data:
        topic: "home/receipt_printer/print"
        payload: "{{ quote | tojson }}"
  mode: single
```

Then call it via the REST API:
```
POST /api/services/script/print_quote_receipt
```

This requires authentication with a long-lived access token.
