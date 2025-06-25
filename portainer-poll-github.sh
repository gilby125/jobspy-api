#!/bin/bash
# Script to check GitHub for new commits and trigger Portainer update

GITHUB_API="https://api.github.com/repos/gilby125/jobspy-api/commits/main"
PORTAINER_WEBHOOK="YOUR_PORTAINER_WEBHOOK_URL_HERE"
LAST_COMMIT_FILE="/tmp/last_commit_jobspy"

# Get latest commit SHA from GitHub
latest_commit=$(curl -s "$GITHUB_API" | jq -r '.sha[:7]')

# Read last known commit
if [ -f "$LAST_COMMIT_FILE" ]; then
    last_commit=$(cat "$LAST_COMMIT_FILE")
else
    last_commit=""
fi

# Check if there's a new commit
if [ "$latest_commit" != "$last_commit" ] && [ "$latest_commit" != "null" ]; then
    echo "New commit detected: $latest_commit (was: $last_commit)"
    
    # Trigger Portainer webhook
    curl -X POST "$PORTAINER_WEBHOOK"
    
    # Save new commit
    echo "$latest_commit" > "$LAST_COMMIT_FILE"
    
    echo "Portainer update triggered"
else
    echo "No new commits"
fi