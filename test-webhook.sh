#!/bin/bash

# Test script to manually trigger Portainer webhook
# Replace YOUR_WEBHOOK_URL with your actual Portainer webhook URL

WEBHOOK_URL="YOUR_WEBHOOK_URL_HERE"

echo "Testing Portainer webhook..."
echo "URL: $WEBHOOK_URL"

response=$(curl -s -w "%{http_code}" -X POST "$WEBHOOK_URL")
http_code="${response: -3}"

echo "Response: $response"
echo "HTTP Code: $http_code"

if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 204 ]; then
    echo "✅ Webhook test successful!"
else
    echo "❌ Webhook test failed!"
fi