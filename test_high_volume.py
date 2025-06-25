#!/usr/bin/env python3
"""
Test high volume job searches to see actual limits.
"""
import sys
import os
sys.path.append('/home/gilby/Code/Jobspy/jobspy-api')

import asyncio
import time
from app.services.job_service import JobService

async def test_high_volume_search():
    """Test with high volume search parameters."""
    print("🔧 Testing high volume job searches...")
    
    # Test with 200 jobs per search
    test_cases = [
        {
            'name': 'Software Engineer - Remote (200 jobs)',
            'params': {
                'search_term': 'software engineer',
                'location': 'remote',
                'site_name': 'indeed',
                'results_wanted': 200
            }
        },
        {
            'name': 'Python Developer - United States (200 jobs)',
            'params': {
                'search_term': 'python developer',
                'location': 'United States',
                'site_name': 'indeed',
                'results_wanted': 200
            }
        },
        {
            'name': 'Data Scientist - New York (200 jobs)',
            'params': {
                'search_term': 'data scientist',
                'location': 'New York, NY',
                'site_name': 'indeed',
                'results_wanted': 200
            }
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        print(f"\n🔍 Testing: {test_case['name']}")
        print(f"   Parameters: {test_case['params']}")
        
        start_time = time.time()
        
        try:
            result = await JobService.search_jobs(test_case['params'])
            
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            
            if isinstance(result, tuple):
                jobs_df, is_cached = result
                jobs_count = len(jobs_df) if not jobs_df.empty else 0
                
                print(f"   ✅ Found {jobs_count} jobs in {duration}s (cached: {is_cached})")
                
                # Show sample data if available
                if not jobs_df.empty:
                    print(f"   📋 Sample job titles:")
                    for i, title in enumerate(jobs_df['title'].head(3)):
                        print(f"      {i+1}. {title}")
                    
                    # Show some stats
                    unique_companies = jobs_df['company'].nunique() if 'company' in jobs_df.columns else 0
                    unique_locations = jobs_df['location'].nunique() if 'location' in jobs_df.columns else 0
                    print(f"   📊 Stats: {unique_companies} unique companies, {unique_locations} unique locations")
                
                results.append({
                    'name': test_case['name'],
                    'jobs_count': jobs_count,
                    'cached': is_cached,
                    'duration': duration,
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
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            print(f"   ❌ Error after {duration}s: {e}")
            results.append({
                'name': test_case['name'],
                'success': False,
                'error': str(e),
                'duration': duration
            })
    
    return results

if __name__ == "__main__":
    print("🧪 High Volume JobSpy Search Test")
    print("==================================")
    
    results = asyncio.run(test_high_volume_search())
    
    print("\n📊 Summary:")
    print("===========")
    
    total_jobs = 0
    successful_searches = 0
    total_time = 0
    
    for result in results:
        if result.get('success'):
            jobs = result.get('jobs_count', 0)
            cached = result.get('cached', False)
            duration = result.get('duration', 0)
            cache_status = "(cached)" if cached else "(fresh)"
            print(f"✅ {result['name']}: {jobs} jobs in {duration}s {cache_status}")
            total_jobs += jobs
            successful_searches += 1
            total_time += duration
        else:
            duration = result.get('duration', 0)
            print(f"❌ {result['name']}: {result.get('error', 'Unknown error')} (after {duration}s)")
    
    print(f"\n📈 Total jobs found: {total_jobs}")
    print(f"📈 Successful searches: {successful_searches}/{len(results)}")
    print(f"⏱️  Total time: {round(total_time, 2)}s")
    print(f"📊 Average jobs per search: {round(total_jobs/successful_searches, 1) if successful_searches > 0 else 0}")
    print(f"⚡ Average time per search: {round(total_time/len(results), 2)}s")