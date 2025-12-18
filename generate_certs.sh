#!/bin/bash
echo "Generating self-signed certificate for receipt.local..."
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj "/C=US/ST=State/L=City/O=Organization/CN=receipt.local"
echo "Done. cert.pem and key.pem created."
