#!/bin/bash

# Simple script to notify when containers are ready
echo "🚀 Watching for deployment completion..."

# Check if docker containers are healthy
while true; do
    if docker-compose ps | grep -q "healthy.*jobspy-docker-api"; then
        echo "✅ Deployment complete! Container is healthy."
        
        # Desktop notification (Linux)
        if command -v notify-send &> /dev/null; then
            notify-send "JobSpy API" "Deployment complete! 🚀" --icon=applications-development
        fi
        
        # Desktop notification (macOS) 
        if command -v osascript &> /dev/null; then
            osascript -e 'display notification "Deployment complete! 🚀" with title "JobSpy API"'
        fi
        
        # Terminal bell
        echo -e "\a"
        
        break
    else
        echo "⏳ Waiting for containers to be ready..."
        sleep 10
    fi
done