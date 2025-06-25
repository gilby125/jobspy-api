#!/bin/bash
# Script to update version.json with current git information before deployment

echo "Updating version.json with current git info..."

# Get git information
COMMIT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
BUILD_DATE=$(date -Iseconds)

echo "Commit: $COMMIT_HASH"
echo "Branch: $BRANCH"
echo "Build Date: $BUILD_DATE"

# Create temporary version file with current info
cat > version.json << EOF
{
  "version": "1.1.0",
  "build_number": "$(date +%s)",
  "build_date": "$BUILD_DATE",
  "commit_hash": "$COMMIT_HASH",
  "branch": "$BRANCH",
  "features": [
    "Job Search API",
    "Admin Interface", 
    "Scheduled Searches",
    "Quick Search Fix",
    "Comprehensive Test Suite",
    "Version Display System",
    "GitHub Actions Deployment",
    "Portainer Polling"
  ]
}
EOF

echo "✅ version.json updated successfully"