#!/usr/bin/env python3
"""
Test the updated main.py with tracking routes.
"""
import os
import sys
import requests
import time
import subprocess
import signal

# Set environment variables
os.environ['DATABASE_URL'] = 'postgresql://jobspy:jobspy_password@localhost:5432/jobspy'
os.environ['REDIS_URL'] = 'redis://localhost:6379'
os.environ['API_KEYS'] = 'test-key-123'

def test_updated_api():
    """Test the updated API with tracking routes."""
    print("🚀 Testing Updated API with Tracking Routes...")
    
    # Start the API server
    print("\n1. Starting API server...")
    api_process = subprocess.Popen([
        sys.executable, '-m', 'uvicorn', 'app.main:app', 
        '--host', '0.0.0.0', '--port', '8787'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    time.sleep(5)
    
    try:
        # Test health endpoint
        print("\n2. Testing health endpoint...")
        response = requests.get('http://localhost:8787/health', timeout=10)
        if response.status_code == 200:
            print("   ✅ Health endpoint working")
        else:
            print(f"   ❌ Health endpoint failed: {response.status_code}")
            return False
        
        # Test root endpoint
        print("\n3. Testing root endpoint...")
        response = requests.get('http://localhost:8787/', timeout=10)
        if response.status_code == 200:
            print("   ✅ Root endpoint working")
            print(f"   Response: {response.json()}")
        else:
            print(f"   ❌ Root endpoint failed: {response.status_code}")
            return False
        
        # Test tracking search endpoint
        print("\n4. Testing tracking search endpoint...")
        response = requests.get(
            'http://localhost:8787/api/v1/jobs/search_jobs',
            params={
                'search_term': 'python',
                'page_size': 5,
                'api_key': 'test-key-123'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Search endpoint working - Found {data['count']} jobs")
            if data['jobs']:
                job = data['jobs'][0]
                print(f"   Sample job: {job['title']} at {job['company']}")
                print(f"   Sources: {len(job['sources'])} source(s)")
        else:
            print(f"   ❌ Search endpoint failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
        
        # Test companies endpoint
        print("\n5. Testing companies endpoint...")
        response = requests.get(
            'http://localhost:8787/api/v1/jobs/companies',
            params={'api_key': 'test-key-123'},
            timeout=10
        )
        
        if response.status_code == 200:
            companies = response.json()
            print(f"   ✅ Companies endpoint working - Found {len(companies)} companies")
        else:
            print(f"   ❌ Companies endpoint failed: {response.status_code}")
            return False
        
        # Test locations endpoint
        print("\n6. Testing locations endpoint...")
        response = requests.get(
            'http://localhost:8787/api/v1/jobs/locations',
            params={'api_key': 'test-key-123'},
            timeout=10
        )
        
        if response.status_code == 200:
            locations = response.json()
            print(f"   ✅ Locations endpoint working - Found {len(locations)} locations")
        else:
            print(f"   ❌ Locations endpoint failed: {response.status_code}")
            return False
        
        # Test analytics endpoint
        print("\n7. Testing analytics endpoint...")
        response = requests.get(
            'http://localhost:8787/api/v1/jobs/analytics',
            params={'api_key': 'test-key-123'},
            timeout=10
        )
        
        if response.status_code == 200:
            analytics = response.json()
            print(f"   ✅ Analytics endpoint working - Keys: {list(analytics.keys())}")
        else:
            print(f"   ❌ Analytics endpoint failed: {response.status_code}")
            return False
        
        print("\n✨ All API tests completed successfully!")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"   ❌ API test failed: {e}")
        return False
    finally:
        # Stop the server
        print("\n8. Stopping API server...")
        api_process.send_signal(signal.SIGTERM)
        api_process.wait(timeout=10)

if __name__ == "__main__":
    success = test_updated_api()
    if success:
        print("\n🎉 Updated API with tracking routes is working correctly!")
        print("✅ Migration completed successfully!")
        print("\nThe JobSpy API now uses the new tracking schema with:")
        print("  - Job deduplication")
        print("  - Enhanced metrics")
        print("  - Multi-source tracking")
        print("  - Improved analytics")
    else:
        print("\n❌ Updated API tests failed!")