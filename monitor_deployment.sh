#!/bin/bash

# JobSpy API Deployment Monitor
# Quick status check for deployment health

set -e

DEPLOYMENT_URL="http://192.168.7.10:8787"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🔍 JobSpy Deployment Monitor"
echo "============================"

# Function to check endpoint
check_endpoint() {
    local endpoint=$1
    local name=$2
    
    if curl -s --max-time 5 "$DEPLOYMENT_URL$endpoint" >/dev/null 2>&1; then
        echo -e "✅ ${GREEN}$name${NC}"
        return 0
    else
        echo -e "❌ ${RED}$name${NC}"
        return 1
    fi
}

# Check all critical endpoints
endpoints=(
    "/health:Health Check"
    "/docs:API Documentation"
    "/admin/:Admin Dashboard"
    "/admin/analytics:Analytics Page"
    "/admin/api/stats:Admin API"
)

all_healthy=true

for endpoint_info in "${endpoints[@]}"; do
    IFS=':' read -r endpoint name <<< "$endpoint_info"
    if ! check_endpoint "$endpoint" "$name"; then
        all_healthy=false
    fi
done

echo
if $all_healthy; then
    echo -e "${GREEN}🎉 All systems operational!${NC}"
    echo -e "${GREEN}🌐 Deployment URL: $DEPLOYMENT_URL${NC}"
else
    echo -e "${RED}⚠️  Some systems have issues${NC}"
    echo -e "${YELLOW}📋 Check Portainer logs for details${NC}"
fi

# Show current version if available
echo
echo "📊 System Info:"
if version_info=$(curl -s --max-time 5 "$DEPLOYMENT_URL/health" 2>/dev/null); then
    echo "$version_info" | grep -E '"(version|status)"' || echo "Version info not available"
else
    echo "Could not retrieve version info"
fi