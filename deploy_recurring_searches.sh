#!/bin/bash

echo "🚀 Deploying Recurring Searches for Ongoing Testing"
echo "=================================================="

# Configuration
SERVER_URL="http://192.168.7.10:8787"
API_KEY="test-key"
MAX_RETRIES=10
RETRY_DELAY=30

# Function to wait for server
wait_for_server() {
    echo "🔄 Waiting for server to be ready..."
    
    for i in $(seq 1 $MAX_RETRIES); do
        if curl -s --connect-timeout 5 "$SERVER_URL/health" > /dev/null 2>&1; then
            echo "✅ Server is ready!"
            return 0
        else
            echo "  Attempt $i/$MAX_RETRIES: Server not ready, waiting ${RETRY_DELAY}s..."
            sleep $RETRY_DELAY
        fi
    done
    
    echo "❌ Server not ready after $MAX_RETRIES attempts"
    return 1
}

# Function to create a single search
create_search() {
    local search_data="$1"
    local search_name=$(echo "$search_data" | jq -r '.name')
    
    echo "📝 Creating: $search_name"
    
    response=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -H "x-api-key: $API_KEY" \
        "$SERVER_URL/admin/searches" \
        -d "$search_data")
    
    if echo "$response" | jq -e '.id' > /dev/null 2>&1; then
        search_id=$(echo "$response" | jq -r '.id')
        echo "  ✅ Created successfully (ID: $search_id)"
        return 0
    else
        echo "  ❌ Failed to create: $response"
        return 1
    fi
}

# Main execution
echo "🔍 Checking if server is accessible..."

if ! wait_for_server; then
    echo "❌ Cannot connect to server. Please ensure the server is running and try again."
    exit 1
fi

echo ""
echo "📋 Reading search definitions from recurring_searches.json..."

if [ ! -f "recurring_searches.json" ]; then
    echo "❌ recurring_searches.json not found!"
    exit 1
fi

# Read and validate JSON
if ! jq empty recurring_searches.json 2>/dev/null; then
    echo "❌ Invalid JSON in recurring_searches.json"
    exit 1
fi

total_searches=$(jq length recurring_searches.json)
echo "📊 Found $total_searches searches to create"

# Create each search
successful=0
failed=0

for i in $(seq 0 $((total_searches - 1))); do
    search_data=$(jq ".[$i]" recurring_searches.json)
    
    if create_search "$search_data"; then
        ((successful++))
    else
        ((failed++))
    fi
    
    # Brief pause between creations
    sleep 2
done

echo ""
echo "📊 Deployment Summary:"
echo "  ✅ Successfully created: $successful searches"
echo "  ❌ Failed to create: $failed searches"
echo "  📈 Success rate: $(echo "scale=1; $successful * 100 / $total_searches" | bc)%"

if [ $successful -gt 0 ]; then
    echo ""
    echo "🎯 Next Steps:"
    echo "  1. Check admin interface at $SERVER_URL/admin/scheduler"
    echo "  2. Monitor search execution logs"
    echo "  3. Review job tracking database for results"
    echo "  4. Searches will run automatically according to their schedules"
    
    echo ""
    echo "📅 Search Schedule Summary:"
    jq -r '.[] | "  • \(.name) - \(.recurring_interval)"' recurring_searches.json
fi

echo ""
echo "✅ Recurring search deployment complete!"