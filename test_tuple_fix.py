#!/usr/bin/env python3
"""
Test script to verify the JobService tuple handling fix works correctly.
"""
import sys
import os
sys.path.append('/home/gilby/Code/Jobspy/jobspy-api')

import asyncio
from app.services.job_service import JobService

async def test_tuple_handling():
    """Test that JobService.search_jobs returns a tuple correctly."""
    print("🔧 Testing JobService tuple handling...")
    
    # Test search parameters
    search_params = {
        'search_term': 'python developer',
        'location': 'remote',
        'site_name': 'indeed',
        'results_wanted': 5
    }
    
    try:
        # Execute search
        print("🔍 Executing search...")
        result = await JobService.search_jobs(search_params)
        
        # Check if result is a tuple
        if isinstance(result, tuple):
            print("✅ JobService.search_jobs() returns a tuple")
            jobs_df, is_cached = result
            print(f"✅ Tuple unpacking successful: DataFrame with {len(jobs_df)} jobs, cached={is_cached}")
            
            # Test the admin code logic
            jobs_count = len(jobs_df) if not jobs_df.empty else 0
            print(f"✅ Jobs count calculation: {jobs_count}")
            
            return {
                "results_count": jobs_count,
                "cached": is_cached,
                "success": True
            }
        else:
            print(f"❌ JobService.search_jobs() returns {type(result)}, not a tuple")
            return {"success": False, "error": f"Wrong return type: {type(result)}"}
            
    except Exception as e:
        print(f"❌ Error during search: {e}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    print("🧪 JobService Tuple Handling Test")
    print("==================================")
    
    result = asyncio.run(test_tuple_handling())
    
    if result.get("success"):
        print("\n✅ Tuple handling fix is working correctly!")
        print(f"   - Results count: {result.get('results_count', 0)}")
        print(f"   - Cached: {result.get('cached', False)}")
    else:
        print(f"\n❌ Tuple handling fix failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)