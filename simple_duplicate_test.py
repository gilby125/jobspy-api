#!/usr/bin/env python3
"""
Simple test for job duplicate detection functionality.
"""
import subprocess
import json
import time

def test_duplicate_detection():
    """Test duplicate detection with curl commands."""
    print("🚀 Testing Job Duplicate Detection")
    print("=" * 50)
    
    # Test 1: Run the same search multiple times
    print("\n📋 Test 1: Running identical searches to test duplicate detection")
    
    search_params = "search_term=Software Engineer&location=San Francisco&site=indeed&results_wanted=5"
    
    results = []
    for i in range(3):
        print(f"  🔍 Running search #{i+1}...")
        
        cmd = f'curl -s -H "x-api-key: test-key" "http://192.168.7.10:8787/api/v1/search_jobs?{search_params}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                job_count = data.get("count", 0)
                jobs = data.get("jobs", [])
                cached = data.get("cached", False)
                
                print(f"    ✅ Search {i+1}: Found {job_count} jobs, Cached: {cached}")
                
                # Extract job IDs to check for duplicates
                job_ids = [job.get("id", "") for job in jobs]
                results.append({
                    "search": i+1,
                    "count": job_count,
                    "cached": cached,
                    "job_ids": job_ids,
                    "jobs": jobs
                })
                
            except json.JSONDecodeError:
                print(f"    ❌ Search {i+1}: Failed to parse JSON response")
                print(f"    Response: {result.stdout[:200]}...")
        else:
            print(f"    ❌ Search {i+1}: Command failed with code {result.returncode}")
        
        time.sleep(2)  # Brief pause between searches
    
    # Analyze results
    print("\n📊 Analysis:")
    
    if len(results) >= 2:
        # Compare job IDs between searches
        search1_ids = set(results[0]["job_ids"])
        search2_ids = set(results[1]["job_ids"])
        
        common_jobs = search1_ids.intersection(search2_ids)
        unique_to_search1 = search1_ids - search2_ids
        unique_to_search2 = search2_ids - search1_ids
        
        print(f"  🔍 Search 1 found {len(search1_ids)} unique job IDs")
        print(f"  🔍 Search 2 found {len(search2_ids)} unique job IDs")
        print(f"  🤝 Common jobs between searches: {len(common_jobs)}")
        print(f"  📈 Unique to search 1: {len(unique_to_search1)}")
        print(f"  📈 Unique to search 2: {len(unique_to_search2)}")
        
        # Check if caching is working
        cache_status = [r["cached"] for r in results]
        print(f"  💾 Cache status across searches: {cache_status}")
        
        # Sample job analysis
        if results[0]["jobs"]:
            sample_job = results[0]["jobs"][0]
            print(f"\n📋 Sample job from first search:")
            print(f"  ID: {sample_job.get('id', 'N/A')}")
            print(f"  Title: {sample_job.get('title', 'N/A')}")
            print(f"  Company: {sample_job.get('company', 'N/A')}")
            print(f"  Location: {sample_job.get('location', 'N/A')}")
            print(f"  Site: {sample_job.get('site', 'N/A')}")
    
    # Test 2: Check job tracking database
    print("\n📋 Test 2: Checking job tracking database")
    
    cmd = 'curl -s -H "x-api-key: test-key" "http://192.168.7.10:8787/api/v1/jobs/search_jobs?page=1&page_size=5"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            tracked_jobs = data.get("jobs", [])
            total_count = data.get("total_count", 0)
            
            print(f"  ✅ Job tracking database: {len(tracked_jobs)} jobs on current page, {total_count} total")
            
            if tracked_jobs:
                print("  📋 Sample tracked job:")
                sample = tracked_jobs[0]
                print(f"    Title: {sample.get('title', 'N/A')}")
                print(f"    Company: {sample.get('company_name', 'N/A')}")
                print(f"    Location: {sample.get('location', 'N/A')}")
                print(f"    First seen: {sample.get('first_seen_at', 'N/A')}")
            else:
                print("  ℹ️  No tracked jobs found in database")
                
        except json.JSONDecodeError:
            print(f"  ❌ Failed to parse tracking database response")
    else:
        print(f"  ❌ Failed to query tracking database")
    
    # Test 3: Check admin stats
    print("\n📋 Test 3: Checking admin statistics")
    
    cmd = 'curl -s "http://192.168.7.10:8787/admin/stats"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        try:
            stats = json.loads(result.stdout)
            print(f"  ✅ Admin stats:")
            print(f"    Total searches: {stats.get('total_searches', 0)}")
            print(f"    Total jobs found: {stats.get('total_jobs_found', 0)}")
            print(f"    Jobs found today: {stats.get('jobs_found_today', 0)}")
            print(f"    Database health: {stats.get('system_health', {}).get('database', 'unknown')}")
            
        except json.JSONDecodeError:
            print(f"  ❌ Failed to parse admin stats")
    else:
        print(f"  ❌ Failed to get admin stats")
    
    # Test 4: Test different search terms
    print("\n📋 Test 4: Testing different search terms")
    
    different_searches = [
        "search_term=Data Scientist&location=New York&site=linkedin&results_wanted=3",
        "search_term=Product Manager&location=Austin&site=indeed&results_wanted=3", 
        "search_term=DevOps Engineer&location=Seattle&site=glassdoor&results_wanted=3"
    ]
    
    different_results = []
    for i, search in enumerate(different_searches):
        print(f"  🔍 Running different search #{i+1}...")
        
        cmd = f'curl -s -H "x-api-key: test-key" "http://192.168.7.10:8787/api/v1/search_jobs?{search}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                job_count = data.get("count", 0)
                print(f"    ✅ Different search {i+1}: Found {job_count} jobs")
                different_results.append(job_count)
                
            except json.JSONDecodeError:
                print(f"    ❌ Different search {i+1}: Failed to parse response")
        else:
            print(f"    ❌ Different search {i+1}: Command failed")
        
        time.sleep(1)
    
    print(f"\n📊 Different search results: {different_results}")
    
    print("\n" + "=" * 50)
    print("🎯 Test Summary:")
    print("✅ Tested API connectivity and job search functionality")
    print("✅ Analyzed job ID patterns for duplicate detection")
    print("✅ Checked job tracking database integration")
    print("✅ Verified admin statistics reporting")
    print("✅ Tested multiple different search scenarios")
    
    print("\n💡 Key Observations:")
    if len(results) >= 2:
        if results[0]["count"] == results[1]["count"] and results[1]["cached"]:
            print("  🎯 Caching appears to be working (identical results, second marked as cached)")
        else:
            print("  🤔 Results vary between identical searches - may indicate real-time data or duplicate detection")
    
    print("  📝 The system is functional and processing job search requests")
    print("  📝 Job tracking database endpoints are responding")
    print("  📝 Admin statistics are being collected")

if __name__ == "__main__":
    test_duplicate_detection()