#!/usr/bin/env python3
"""
Test script for the new tracking API routes.
"""
import os
import sys
import asyncio
from fastapi.testclient import TestClient

# Set environment variables
os.environ['DATABASE_URL'] = 'postgresql://jobspy:jobspy_password@localhost:5432/jobspy'
os.environ['REDIS_URL'] = 'redis://localhost:6379'
os.environ['API_KEYS'] = 'test-key-123'  # Set a test API key

# Add current directory to path
sys.path.insert(0, '.')

from app.db.database import init_database

def test_tracking_api():
    """Test the tracking API routes."""
    print("🔍 Testing Tracking API Routes...")
    
    # Initialize database
    init_database()
    
    # Create a test app with only tracking routes
    from fastapi import FastAPI
    from app.api.routes.jobs_tracking import router as tracking_router
    
    app = FastAPI()
    app.include_router(tracking_router, prefix="/api/v1")
    
    client = TestClient(app)
    
    # Test 1: Search jobs endpoint
    print("\n1. Testing /api/v1/search_jobs endpoint...")
    response = client.get(
        "/api/v1/search_jobs",
        params={
            "search_term": "python",
            "page": 1,
            "page_size": 10,
            "api_key": "test-key-123"
        }
    )
    
    print(f"   Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Found {data['count']} jobs")
        print(f"   Total pages: {data['total_pages']}")
        print(f"   Current page: {data['current_page']}")
        
        if data['jobs']:
            job = data['jobs'][0]
            print(f"   Sample job: {job['title']} at {job['company']}")
            print(f"   Sources: {len(job['sources'])} source(s)")
            print(f"   Metrics: {job['metrics']}")
    else:
        print(f"   ❌ Error: {response.text}")
        return False
    
    # Test 2: Companies endpoint
    print("\n2. Testing /api/v1/companies endpoint...")
    response = client.get(
        "/api/v1/companies",
        params={
            "limit": 5,
            "api_key": "test-key-123"
        }
    )
    
    print(f"   Status Code: {response.status_code}")
    if response.status_code == 200:
        companies = response.json()
        print(f"   ✅ Found {len(companies)} companies")
        if companies:
            print(f"   Sample company: {companies[0]['name']} ({companies[0]['active_jobs_count']} jobs)")
    else:
        print(f"   ❌ Error: {response.text}")
        return False
    
    # Test 3: Locations endpoint
    print("\n3. Testing /api/v1/locations endpoint...")
    response = client.get(
        "/api/v1/locations",
        params={
            "limit": 5,
            "api_key": "test-key-123"
        }
    )
    
    print(f"   Status Code: {response.status_code}")
    if response.status_code == 200:
        locations = response.json()
        print(f"   ✅ Found {len(locations)} locations")
        if locations:
            location = locations[0]
            print(f"   Sample location: {location['city']}, {location['state']}, {location['country']} ({location['active_jobs_count']} jobs)")
    else:
        print(f"   ❌ Error: {response.text}")
        return False
    
    # Test 4: Analytics endpoint
    print("\n4. Testing /api/v1/analytics endpoint...")
    response = client.get(
        "/api/v1/analytics",
        params={
            "days_back": 30,
            "api_key": "test-key-123"
        }
    )
    
    print(f"   Status Code: {response.status_code}")
    if response.status_code == 200:
        analytics = response.json()
        print(f"   ✅ Analytics data retrieved")
        print(f"   Keys: {list(analytics.keys())}")
    else:
        print(f"   ❌ Error: {response.text}")
        return False
    
    print("\n✨ All tracking API tests completed successfully!")
    return True

if __name__ == "__main__":
    success = test_tracking_api()
    if success:
        print("\n🎉 Tracking API is working correctly!")
        print("Ready to update main.py to use tracking routes.")
    else:
        print("\n❌ Tracking API tests failed!")