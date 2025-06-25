#!/bin/bash

echo "📊 JobSpy Recurring Search Monitor"
echo "=================================="

# Configuration
SERVER_URL="http://192.168.7.10:8787"
API_KEY="test-key"

# Function to check server health
check_server() {
    if curl -s --connect-timeout 3 "$SERVER_URL/health" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to get search statistics
get_search_stats() {
    curl -s -H "x-api-key: $API_KEY" "$SERVER_URL/admin/searches/api" | jq '.'
}

# Function to get admin stats
get_admin_stats() {
    curl -s "$SERVER_URL/admin/stats" | jq '.'
}

# Function to display search summary
display_search_summary() {
    echo "🔍 Current Scheduled Searches:"
    echo "==============================="
    
    searches=$(curl -s -H "x-api-key: $API_KEY" "$SERVER_URL/admin/searches/api")
    
    if echo "$searches" | jq -e '.searches' > /dev/null 2>&1; then
        total=$(echo "$searches" | jq '.searches | length')
        echo "📊 Total Searches: $total"
        echo ""
        
        # Group by status
        pending=$(echo "$searches" | jq '.searches | map(select(.status == "pending")) | length')
        running=$(echo "$searches" | jq '.searches | map(select(.status == "running")) | length')
        completed=$(echo "$searches" | jq '.searches | map(select(.status == "completed")) | length')
        failed=$(echo "$searches" | jq '.searches | map(select(.status == "failed")) | length')
        
        echo "📈 Status Breakdown:"
        echo "  ⏳ Pending: $pending"
        echo "  🔄 Running: $running"
        echo "  ✅ Completed: $completed"
        echo "  ❌ Failed: $failed"
        
        echo ""
        echo "📋 Search Details:"
        echo "$searches" | jq -r '.searches[] | "  • \(.name) (\(.status)) - \(.jobs_found // 0) jobs found"'
        
        # Show recurring searches
        echo ""
        echo "🔄 Recurring Searches:"
        recurring_count=$(echo "$searches" | jq '.searches | map(select(.recurring == true)) | length')
        echo "  📊 Total Recurring: $recurring_count"
        
        if [ $recurring_count -gt 0 ]; then
            echo "$searches" | jq -r '.searches[] | select(.recurring == true) | "    • \(.name) - \(.recurring_interval // "unknown interval")"'
        fi
        
    else
        echo "❌ Unable to retrieve search data"
    fi
}

# Function to display system health
display_system_health() {
    echo ""
    echo "🏥 System Health:"
    echo "================="
    
    admin_stats=$(get_admin_stats)
    
    if echo "$admin_stats" | jq -e '.' > /dev/null 2>&1; then
        total_searches=$(echo "$admin_stats" | jq -r '.total_searches // 0')
        total_jobs=$(echo "$admin_stats" | jq -r '.total_jobs_found // 0')
        jobs_today=$(echo "$admin_stats" | jq -r '.jobs_found_today // 0')
        db_health=$(echo "$admin_stats" | jq -r '.system_health.database // "unknown"')
        
        echo "  📊 Total Searches Executed: $total_searches"
        echo "  💼 Total Jobs Found: $total_jobs"
        echo "  📅 Jobs Found Today: $jobs_today"
        echo "  🗄️  Database Health: $db_health"
    else
        echo "  ❌ Unable to retrieve system stats"
    fi
}

# Function to show recent activity
show_recent_activity() {
    echo ""
    echo "📅 Recent Activity (Last 24 Hours):"
    echo "==================================="
    
    searches=$(curl -s -H "x-api-key: $API_KEY" "$SERVER_URL/admin/searches/api?limit=20")
    
    if echo "$searches" | jq -e '.searches' > /dev/null 2>&1; then
        # Show recent completed searches
        recent_completed=$(echo "$searches" | jq '.searches | map(select(.status == "completed")) | sort_by(.completed_time) | reverse | .[0:5]')
        
        if [ "$(echo "$recent_completed" | jq 'length')" -gt 0 ]; then
            echo "  ✅ Recently Completed:"
            echo "$recent_completed" | jq -r '.[] | "    • \(.name) - \(.jobs_found // 0) jobs (\(.completed_time // "unknown time"))"'
        fi
        
        # Show any failed searches
        recent_failed=$(echo "$searches" | jq '.searches | map(select(.status == "failed"))')
        
        if [ "$(echo "$recent_failed" | jq 'length')" -gt 0 ]; then
            echo ""
            echo "  ❌ Recent Failures:"
            echo "$recent_failed" | jq -r '.[] | "    • \(.name) - \(.created_at // "unknown time")"'
        fi
    fi
}

# Main execution
echo "🔍 Checking server status..."

if ! check_server; then
    echo "❌ Server not accessible at $SERVER_URL"
    echo "   Please ensure the server is running and try again."
    exit 1
fi

echo "✅ Server is accessible"
echo ""

# Display all monitoring information
display_search_summary
display_system_health
show_recent_activity

echo ""
echo "🔗 Admin Interface: $SERVER_URL/admin/scheduler"
echo "📊 Full Dashboard: $SERVER_URL/admin/"
echo ""
echo "💡 To refresh this report, run: ./monitor_searches.sh"