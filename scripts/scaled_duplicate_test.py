#!/usr/bin/env python3
"""
Scaled up duplicate test - run many overlapping searches to generate substantial duplicate data.

This script runs a comprehensive set of job searches across multiple job titles,
locations, and platforms to maximize duplicate detection opportunities.
"""

import os
import sys
import time
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def run_search(search_params, search_num, total_searches):
    """Run a job search using the main jobspy functionality"""
    try:
        from jobspy import scrape_jobs
        
        sites_str = ", ".join(search_params['site_name'])
        print(f"🔍 Search {search_num}/{total_searches}: {search_params['search_term']}")
        print(f"   Sites: {sites_str} | Location: {search_params['location']} | Results: {search_params['results_wanted']}")
        
        # Run the search
        jobs_df = scrape_jobs(**search_params)
        
        if jobs_df is not None and not jobs_df.empty:
            print(f"   ✅ Found {len(jobs_df)} jobs")
            return len(jobs_df), jobs_df
        else:
            print(f"   ❌ No jobs found")
            return 0, None
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return 0, None

def main():
    """Run scaled up duplicate detection tests"""
    print("🚀 SCALED UP Duplicate Detection Test")
    print("=" * 50)
    print("Running comprehensive overlapping searches to generate substantial duplicate data...")
    print()
    
    # Popular job titles that are likely to have duplicates
    job_titles = [
        "software engineer",
        "software developer", 
        "full stack developer",
        "frontend developer",
        "backend developer",
        "python developer",
        "javascript developer",
        "react developer",
        "node.js developer",
        "data scientist",
        "data engineer",
        "machine learning engineer",
        "devops engineer",
        "cloud engineer",
        "product manager",
        "engineering manager",
        "senior software engineer",
        "junior developer",
        "web developer",
        "mobile developer"
    ]
    
    # Mix of locations to increase overlap potential
    locations = [
        "Remote",
        "United States", 
        "San Francisco, CA",
        "New York, NY",
        "Seattle, WA",
        "Austin, TX",
        "Boston, MA"
    ]
    
    # Site combinations for maximum overlap detection
    site_combinations = [
        ["indeed"],
        ["linkedin"], 
        ["indeed", "linkedin"],
        ["glassdoor"],
        ["indeed", "glassdoor"],
        ["linkedin", "glassdoor"],
        ["indeed", "linkedin", "glassdoor"]
    ]
    
    # Build comprehensive search list
    searches = []
    
    # 1. High-volume searches for popular terms
    for title in job_titles[:10]:  # Top 10 titles
        for location in locations[:4]:  # Top 4 locations
            for sites in [["indeed", "linkedin"], ["indeed"], ["linkedin"]]:  # Focus on working sites
                search = {
                    "search_term": title,
                    "location": location,
                    "site_name": sites,
                    "results_wanted": 25,
                    "country_indeed": "USA",
                    "verbose": 1
                }
                searches.append(search)
    
    # 2. Broader searches for maximum coverage
    broad_terms = ["engineer", "developer", "software", "python", "react", "data"]
    for term in broad_terms:
        for sites in [["indeed", "linkedin"], ["indeed"], ["linkedin"]]:
            search = {
                "search_term": term,
                "location": "Remote",
                "site_name": sites,
                "results_wanted": 40,
                "country_indeed": "USA", 
                "verbose": 1
            }
            searches.append(search)
    
    # 3. Specific duplicate-prone searches
    duplicate_prone = [
        ("software engineer", "Remote"),
        ("software engineer", "United States"),
        ("full stack developer", "Remote"),
        ("full stack developer", "San Francisco, CA"),
        ("python developer", "Remote"),
        ("python developer", "New York, NY"),
        ("react developer", "Remote"),
        ("react developer", "United States")
    ]
    
    for term, location in duplicate_prone:
        # Search same term/location on multiple sites separately
        for site in ["indeed", "linkedin"]:
            search = {
                "search_term": term,
                "location": location,
                "site_name": [site],
                "results_wanted": 30,
                "country_indeed": "USA",
                "verbose": 1
            }
            searches.append(search)
    
    print(f"📊 SEARCH PLAN:")
    print(f"   Total searches planned: {len(searches)}")
    print(f"   Expected total jobs: ~{len(searches) * 25} jobs")
    print(f"   High duplicate potential searches: {len(duplicate_prone) * 2}")
    print(f"   Estimated runtime: ~{len(searches) * 2} minutes")
    print()
    
    # Run all searches
    total_jobs = 0
    successful_searches = 0
    failed_searches = 0
    all_results = []
    
    start_time = datetime.now()
    
    for i, search in enumerate(searches, 1):
        print(f"\n📋 Search {i}/{len(searches)}:")
        jobs_found, result_data = run_search(search, i, len(searches))
        
        if jobs_found > 0:
            total_jobs += jobs_found
            successful_searches += 1
            all_results.append({
                'search': search,
                'jobs': jobs_found,
                'data': result_data
            })
        else:
            failed_searches += 1
        
        # Small delay between searches to be respectful
        if i < len(searches):
            time.sleep(2)
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n" + "="*60)
    print(f"📊 FINAL RESULTS SUMMARY:")
    print(f"   Total searches attempted: {len(searches)}")
    print(f"   Successful searches: {successful_searches}")
    print(f"   Failed searches: {failed_searches}")
    print(f"   Total jobs found: {total_jobs}")
    print(f"   Average jobs per search: {total_jobs/successful_searches:.1f}" if successful_searches > 0 else "   Average jobs per search: 0")
    print(f"   Total runtime: {duration}")
    
    if total_jobs > 500:
        print(f"\n🎯 EXCELLENT! With {total_jobs} jobs, you should see substantial duplicate detection.")
    elif total_jobs > 200:
        print(f"\n✅ GOOD! With {total_jobs} jobs, you should see some duplicate patterns.")
    else:
        print(f"\n⚠️  MODERATE: With {total_jobs} jobs, there may be limited duplicate detection.")
    
    if successful_searches > 0:
        print(f"\n🎯 NEXT STEPS:")
        print(f"1. Check admin interface: http://localhost:8787/admin/jobs/page")
        print(f"2. Look for duplicate job indicators (🔄 badges)")
        print(f"3. Check deduplication statistics in dashboard")
        print(f"4. Monitor tracking metrics (days active, repost count)")
        print(f"5. Look for multi-source jobs (jobs found on multiple sites)")
        
        # Show high-potential duplicate candidates
        print(f"\n🔍 HIGH DUPLICATE POTENTIAL SEARCHES:")
        duplicate_searches = [s for s in all_results if 'software engineer' in s['search']['search_term'] or 'full stack' in s['search']['search_term']]
        for result in duplicate_searches[:5]:
            search = result['search']
            print(f"   • {search['search_term']} | {search['location']} | {', '.join(search['site_name'])} | {result['jobs']} jobs")
    
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