#!/bin/bash

# Wait for deployment completion
# Usage: ./scripts/wait-for-deployment.sh [URL] [max_wait_minutes]

URL=${1:-"http://localhost:8787/health"}
MAX_WAIT=${2:-5}
MAX_ATTEMPTS=$((MAX_WAIT * 6))  # Check every 10 seconds

echo "🚀 Waiting for deployment to complete..."
echo "📍 Checking: $URL"
echo "⏱️  Max wait time: $MAX_WAIT minutes"
echo ""

attempt=1
start_time=$(date +%s)

while [ $attempt -le $MAX_ATTEMPTS ]; do
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    
    if curl -f -s "$URL" > /dev/null 2>&1; then
        echo "✅ SUCCESS! Deployment complete after ${elapsed}s"
        echo "🌐 API is now available at: $URL"
        
        # Optional: Open in browser
        # open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null || echo "Manual check: $URL"
        
        # Optional: Send desktop notification (macOS)
        # osascript -e 'display notification "Deployment complete!" with title "JobSpy API"' 2>/dev/null || true
        
        # Optional: Send desktop notification (Linux)
        # notify-send "JobSpy API" "Deployment complete!" 2>/dev/null || true
        
        exit 0
    else
        printf "\r⏳ Attempt %d/%d (${elapsed}s elapsed)..." $attempt $MAX_ATTEMPTS
        sleep 10
        attempt=$((attempt + 1))
    fi
done

echo ""
echo "❌ TIMEOUT: Deployment not detected after $MAX_WAIT minutes"
echo "🔍 Manual check required: $URL"
exit 1