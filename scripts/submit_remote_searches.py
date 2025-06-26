#!/usr/bin/env python3
"""
Script to submit remote job searches for duplicate tracking testing.

This script submits the remote job searches configuration to the admin API
to create hourly recurring searches across multiple job platforms.
"""

import json
import requests
import sys
import os
from datetime import datetime, timedelta


def load_search_config():
    """Load the search configuration from JSON file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, "remote_job_searches.json")
    
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: Could not find {config_file}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in {config_file}: {e}")
        return None


def schedule_searches_manually():
    """Instructions for manually scheduling searches via admin interface"""
    config = load_search_config()
    if not config:
        return
    
    print("🚀 Remote US Job Search Configuration for Duplicate Testing")
    print("=" * 65)
    print(f"📋 Batch: {config['batch_name']}")
    print(f"📝 Description: {config['description']}")
    print(f"🔍 Total Searches: {len(config['searches'])}")
    print()
    
    print("📋 SEARCH CONFIGURATION:")
    print("-" * 40)
    
    # Group searches by type
    multi_site_searches = []
    single_site_searches = []
    broad_searches = []
    
    for search in config['searches']:
        if len(search['site_names']) > 1:
            if 'broad' in search['name'].lower():
                broad_searches.append(search)
            else:
                multi_site_searches.append(search)
        else:
            single_site_searches.append(search)
    
    print(f"\n🎯 MULTI-SITE SEARCHES ({len(multi_site_searches)}) - High Duplicate Potential:")
    for search in multi_site_searches:
        sites = ', '.join(search['site_names'])
        print(f"  • {search['search_term']} | Sites: {sites} | Results: {search['results_wanted']}")
    
    print(f"\n🔍 BROAD SEARCHES ({len(broad_searches)}) - Maximum Coverage:")
    for search in broad_searches:
        sites = ', '.join(search['site_names'])
        print(f"  • {search['search_term']} | Sites: {sites} | Results: {search['results_wanted']}")
    
    print(f"\n📌 SINGLE-SITE SEARCHES ({len(single_site_searches)}) - Baseline Data:")
    by_term = {}
    for search in single_site_searches:
        term = search['search_term']
        if term not in by_term:
            by_term[term] = []
        by_term[term].append(search['site_names'][0])
    
    for term, sites in by_term.items():
        print(f"  • {term} | Sites: {', '.join(sites)}")
    
    print(f"\n📊 EXPECTED DUPLICATE DETECTION:")
    print("  • React Developer: 3 sites × 25 results = 75 total, expect ~15-30 duplicates")
    print("  • Node.js Developer: 3 sites × 20 results = 60 total, expect ~10-25 duplicates") 
    print("  • Multi-site searches: High overlap expected between Indeed/LinkedIn")
    print("  • Broad searches: Maximum duplicate potential across all platforms")
    
    print(f"\n🕐 TIMING:")
    print("  • All searches set to run hourly")
    print("  • Total results per hour: ~665 job postings")
    print("  • Expected duplicates per hour: ~100-200 (15-30%)")
    
    print(f"\n📋 TO SET UP THESE SEARCHES:")
    print("1. Navigate to the admin interface: /admin/searches")
    print("2. Use the 'Bulk Search' feature")
    print("3. Copy the search configurations below:")
    print()
    
    # Output for easy copying
    print("=" * 60)
    print("🔗 BULK SEARCH JSON (Copy this to admin interface):")
    print("=" * 60)
    
    # Create the bulk request format
    bulk_request = {
        "batch_name": config['batch_name'],
        "searches": []
    }
    
    current_time = datetime.now()
    
    for i, search in enumerate(config['searches']):
        # Add schedule time (stagger by 2 minutes each)
        schedule_time = current_time + timedelta(minutes=2 + i * 2)
        
        bulk_search = {
            "name": search['name'],
            "search_term": search['search_term'],
            "location": search['location'],
            "site_names": search['site_names'],
            "country_indeed": search['country_indeed'],
            "results_wanted": search['results_wanted'],
            "recurring": search['recurring'],
            "recurring_interval": search['recurring_interval'],
            "schedule_time": schedule_time.isoformat()
        }
        
        if 'job_type' in search:
            bulk_search['job_type'] = search['job_type']
            
        bulk_request['searches'].append(bulk_search)
    
    print(json.dumps(bulk_request, indent=2))
    
    print("\n=" * 60)
    print("🎯 NEXT STEPS AFTER SETUP:")
    print("1. Monitor /admin/scheduler for active searches")
    print("2. Check /admin/jobs/page for duplicate indicators") 
    print("3. Watch deduplication metrics in admin dashboard")
    print("4. After 2-3 hours, review tracking statistics")
    print("5. Analyze job hash collisions and multi-source jobs")


def create_curl_commands():
    """Create curl commands for API submission"""
    config = load_search_config()
    if not config:
        return
    
    print("\n🌐 API SUBMISSION (Alternative Method):")
    print("-" * 45)
    print("If you prefer to use the API directly, here's the curl command:")
    print()
    
    # Create bulk request
    bulk_request = {
        "batch_name": config['batch_name'],
        "searches": []
    }
    
    current_time = datetime.now()
    
    for i, search in enumerate(config['searches'][:5]):  # First 5 for example
        schedule_time = current_time + timedelta(minutes=5 + i)
        bulk_search = {
            "name": search['name'],
            "search_term": search['search_term'],
            "location": search['location'],
            "site_names": search['site_names'],
            "country_indeed": search['country_indeed'],
            "results_wanted": search['results_wanted'],
            "recurring": search['recurring'],
            "recurring_interval": search['recurring_interval'],
            "schedule_time": schedule_time.isoformat()
        }
        bulk_request['searches'].append(bulk_search)
    
    json_data = json.dumps(bulk_request, indent=2)
    
    print("curl -X POST http://localhost:8787/admin/searches/bulk \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -H 'x-api-key: your-admin-api-key' \\")
    print(f"  -d '{json_data}'")
    print()
    print("(Replace 'your-admin-api-key' with your actual API key)")
    print("(This example shows first 5 searches - use full JSON above for all)")


def main():
    """Main function"""
    print("🚀 JobSpy Remote Jobs - Duplicate Tracking Test Setup")
    print("=" * 55)
    
    try:
        schedule_searches_manually()
        create_curl_commands()
        
        print(f"\n✅ Setup guide generated successfully!")
        print("📊 This configuration will generate substantial duplicate data for testing.")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)