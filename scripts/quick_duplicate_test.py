#!/usr/bin/env python3
"""
Quick duplicate test - run a few immediate searches to populate tracking data.

This script runs several overlapping searches immediately to quickly generate
some duplicate job data for testing the tracking schema functionality.
"""

import os
import sys
import subprocess
import json
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def run_search(search_params):
    """Run a job search using the main jobspy functionality"""
    try:
        from jobspy import scrape_jobs
        
        print(f"🔍 Searching: {search_params['search_term']} on {', '.join(search_params['site_name'])}")
        print(f"   Location: {search_params['location']} | Results: {search_params['results_wanted']}")
        
        # Run the search
        jobs_df = scrape_jobs(**search_params)
        
        if jobs_df is not None and not jobs_df.empty:
            print(f"   ✅ Found {len(jobs_df)} jobs")
            return jobs_df
        else:
            print(f"   ❌ No jobs found")
            return None
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return None

def main():
    """Run quick duplicate detection tests"""
    print("🚀 Quick Duplicate Detection Test")
    print("=" * 40)
    print("Running overlapping searches to generate duplicate job data for testing...")
    print()
    
    # Define test searches that are likely to have overlaps
    test_searches = [
        {
            "search_term": "software engineer",
            "location": "Remote",
            "site_name": ["indeed", "linkedin"],
            "results_wanted": 20,
            "country_indeed": "USA",
            "verbose": 1
        },
        {
            "search_term": "python developer", 
            "location": "Remote",
            "site_name": ["indeed", "glassdoor"],
            "results_wanted": 15,
            "country_indeed": "USA",
            "verbose": 1
        },
        {
            "search_term": "remote developer",
            "location": "United States",
            "site_name": ["linkedin", "glassdoor"],
            "results_wanted": 15,
            "country_indeed": "USA", 
            "verbose": 1
        },
        {
            "search_term": "full stack developer",
            "location": "Remote",
            "site_name": ["indeed"],
            "results_wanted": 10,
            "country_indeed": "USA",
            "verbose": 1
        },
        {
            "search_term": "full stack developer",
            "location": "Remote", 
            "site_name": ["linkedin"],
            "results_wanted": 10,
            "country_indeed": "USA",
            "verbose": 1
        }
    ]
    
    total_jobs = 0
    all_results = []
    
    for i, search in enumerate(test_searches, 1):
        print(f"\n📋 Search {i}/{len(test_searches)}:")
        result = run_search(search)
        
        if result is not None:
            total_jobs += len(result)
            all_results.append({
                'search': search,
                'jobs': len(result),
                'data': result
            })
    
    print(f"\n📊 RESULTS SUMMARY:")
    print(f"   Total searches: {len(test_searches)}")
    print(f"   Successful searches: {len(all_results)}")
    print(f"   Total jobs found: {total_jobs}")
    
    if all_results:
        print(f"\n🎯 NEXT STEPS:")
        print(f"1. These jobs should now be in your database")
        print(f"2. Check the admin interface at /admin/jobs/page")
        print(f"3. Look for duplicate indicators and tracking metrics")
        print(f"4. Review deduplication statistics in the dashboard")
        
        # Show some sample job titles to look for
        print(f"\n🔍 SAMPLE JOB TITLES TO LOOK FOR:")
        sample_titles = set()
        for result in all_results[:2]:  # First 2 results
            if 'data' in result and not result['data'].empty:
                titles = result['data']['title'].head(3).tolist()
                sample_titles.update(titles)
        
        for title in list(sample_titles)[:5]:
            print(f"   • {title}")
        
        print(f"\nThese titles may appear multiple times if found on different sites.")
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)