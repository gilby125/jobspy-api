#!/usr/bin/env python3
"""
Test realistic job search parameters to see actual job counts.
"""
import sys
import os
sys.path.append('/home/gilby/Code/Jobspy/jobspy-api')

import asyncio
from app.services.job_service import JobService

async def test_realistic_search():
    """Test with realistic search parameters."""
    print("🔧 Testing realistic job search parameters...")
    
    # Test multiple search scenarios
    test_cases = [
        {
            'name': 'Python Developer - Remote',
            'params': {
                'search_term': 'python developer',
                'location': 'remote',
                'site_name': 'indeed',
                'results_wanted': 50
            }
        },
        {
            'name': 'Software Engineer - New York',
            'params': {
                'search_term': 'software engineer',
                'location': 'New York, NY',
                'site_name': 'indeed',
                'results_wanted': 50
            }
        },
        {
            'name': 'Data Scientist - San Francisco',
            'params': {
                'search_term': 'data scientist',
                'location': 'San Francisco, CA',
                'site_name': 'indeed',
                'results_wanted': 50
            }
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        print(f"\n🔍 Testing: {test_case['name']}")
        print(f"   Parameters: {test_case['params']}")
        
        try:
            result = await JobService.search_jobs(test_case['params'])
            
            if isinstance(result, tuple):
                jobs_df, is_cached = result
                jobs_count = len(jobs_df) if not jobs_df.empty else 0
                
                print(f"   ✅ Found {jobs_count} jobs (cached: {is_cached})")
                
                # Show sample data if available
                if not jobs_df.empty:
                    print(f"   📋 Sample job titles:")
                    for i, title in enumerate(jobs_df['title'].head(3)):
                        print(f"      {i+1}. {title}")
                
                results.append({
                    'name': test_case['name'],
                    'jobs_count': jobs_count,
                    'cached': is_cached,
                    'success': True
                })
            else:
                print(f"   ❌ Wrong return type: {type(result)}")
                results.append({
                    'name': test_case['name'],
                    'success': False,
                    'error': f"Wrong return type: {type(result)}"
                })
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append({
                'name': test_case['name'],
                'success': False,
                'error': str(e)
            })
    
    return results

if __name__ == "__main__":
    print("🧪 Realistic JobSpy Search Test")
    print("================================")
    
    results = asyncio.run(test_realistic_search())
    
    print("\n📊 Summary:")
    print("===========")
    
    total_jobs = 0
    successful_searches = 0
    
    for result in results:
        if result.get('success'):
            jobs = result.get('jobs_count', 0)
            cached = result.get('cached', False)
            cache_status = "(cached)" if cached else "(fresh)"
            print(f"✅ {result['name']}: {jobs} jobs {cache_status}")
            total_jobs += jobs
            successful_searches += 1
        else:
            print(f"❌ {result['name']}: {result.get('error', 'Unknown error')}")
    
    print(f"\n📈 Total jobs found: {total_jobs}")
    print(f"📈 Successful searches: {successful_searches}/{len(results)}")
    
    if total_jobs == 0:
        print("\n⚠️  WARNING: No jobs found in any search!")
        print("   This could indicate:")
        print("   1. JobSpy configuration issues")
        print("   2. Network connectivity problems")
        print("   3. Site blocking or rate limiting")
        print("   4. Invalid search parameters")