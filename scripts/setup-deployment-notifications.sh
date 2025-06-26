#!/bin/bash

# Setup deployment notifications for JobSpy API
echo "Setting up deployment notifications..."

# Create git hook for post-push notification
HOOK_FILE=".git/hooks/post-push"

cat > "$HOOK_FILE" << 'EOF'
#!/bin/bash
# Auto-check deployment after push to main

if [[ "$1" == *"main"* ]]; then
    echo ""
    echo "🚀 Push to main detected. Checking deployment status..."
    
    # Run in background so git command completes
    (
        sleep 5
        ./scripts/wait-for-deployment.sh "http://localhost:8787/health" 3
    ) &
fi
EOF

chmod +x "$HOOK_FILE"

echo "✅ Git hook installed at: $HOOK_FILE"
echo ""
echo "Now you can also:"
echo "1. Run manually: ./scripts/wait-for-deployment.sh"
echo "2. Set up Discord/Slack webhooks in GitHub Actions"
echo "3. Use desktop notifications (uncomment lines in wait script)"
echo ""
echo "Edit the URL in the scripts to match your deployment domain!"