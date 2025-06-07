#!/usr/bin/env python3
"""
Manual testing script for the distributed scheduler.
Run this to test various scheduling scenarios.
"""
import asyncio
import json
import requests
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8787"

def test_immediate_search():
    """Test 1: Immediate search execution"""
    print("🧪 Test 1: Immediate Search")
    
    data = {
        "name": "Immediate Test Search",
        "search_term": "software engineer",
        "location": "San Francisco, CA",
        "site_names": ["indeed"],
        "results_wanted": 3,
        "country_indeed": "USA"
    }
    
    response = requests.post(f"{BASE_URL}/admin/searches", json=data)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Search ID: {result.get('id')}")
        print(f"Status: {result.get('status')}")
        print(f"Scheduled for: {result.get('scheduled_time')}")
        return result.get('id')
    else:
        print(f"Error: {response.text}")
        return None

def test_future_search():
    """Test 2: Future scheduled search"""
    print("\n🧪 Test 2: Future Scheduled Search (2 minutes from now)")
    
    future_time = datetime.now() + timedelta(minutes=2)
    
    data = {
        "name": "Future Test Search",
        "search_term": "data scientist",
        "location": "New York, NY",
        "site_names": ["indeed"],
        "results_wanted": 2,
        "country_indeed": "USA",
        "schedule_time": future_time.isoformat()
    }
    
    response = requests.post(f"{BASE_URL}/admin/searches", json=data)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Search ID: {result.get('id')}")
        print(f"Status: {result.get('status')}")
        print(f"Scheduled for: {result.get('scheduled_time')}")
        return result.get('id')
    else:
        print(f"Error: {response.text}")
        return None

def test_recurring_search():
    """Test 3: Recurring daily search"""
    print("\n🧪 Test 3: Recurring Daily Search")
    
    start_time = datetime.now() + timedelta(minutes=1)
    
    data = {
        "name": "Daily Python Jobs",
        "search_term": "python developer",
        "location": "Austin, TX",
        "site_names": ["indeed"],
        "results_wanted": 5,
        "country_indeed": "USA",
        "recurring": True,
        "recurring_interval": "daily",
        "schedule_time": start_time.isoformat()
    }
    
    response = requests.post(f"{BASE_URL}/admin/searches", json=data)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Search ID: {result.get('id')}")
        print(f"Status: {result.get('status')}")
        print(f"Recurring: {result.get('recurring')}")
        print(f"Interval: {result.get('recurring_interval')}")
        return result.get('id')
    else:
        print(f"Error: {response.text}")
        return None

def check_all_searches():
    """Test 4: Check all scheduled searches"""
    print("\n🧪 Test 4: Check All Scheduled Searches")
    
    response = requests.get(f"{BASE_URL}/admin/searches")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        searches = result.get('searches', [])
        print(f"Total searches: {len(searches)}")
        
        for search in searches:
            print(f"  ID: {search.get('id')}")
            print(f"  Name: {search.get('name')}")
            print(f"  Status: {search.get('status')}")
            print(f"  Jobs Found: {search.get('jobs_found')}")
            print(f"  Scheduled: {search.get('scheduled_time')}")
            print(f"  Completed: {search.get('completed_time')}")
            print("  ---")
        
        return searches
    else:
        print(f"Error: {response.text}")
        return []

def test_search_cancellation(search_id):
    """Test 5: Cancel a search"""
    if not search_id:
        print("\n⚠️  Skipping cancellation test - no search ID")
        return
    
    print(f"\n🧪 Test 5: Cancel Search {search_id}")
    
    response = requests.post(f"{BASE_URL}/admin/searches/{search_id}/cancel")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Message: {result.get('message')}")
    else:
        print(f"Error: {response.text}")

def check_search_details(search_id):
    """Test 6: Get search details"""
    if not search_id:
        print("\n⚠️  Skipping search details test - no search ID")
        return
    
    print(f"\n🧪 Test 6: Get Search Details {search_id}")
    
    response = requests.get(f"{BASE_URL}/admin/searches/{search_id}")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Name: {result.get('name')}")
        print(f"Status: {result.get('status')}")
        print(f"Search Term: {result.get('search_term')}")
        print(f"Location: {result.get('location')}")
    else:
        print(f"Error: {response.text}")

def check_admin_stats():
    """Test 7: Check admin statistics"""
    print("\n🧪 Test 7: Admin Statistics")
    
    response = requests.get(f"{BASE_URL}/admin/stats")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Total searches: {result.get('total_searches')}")
        print(f"Searches today: {result.get('searches_today')}")
        print(f"Active searches: {result.get('active_searches')}")
        print(f"Failed searches today: {result.get('failed_searches_today')}")
        print(f"System health: {result.get('system_health')}")
    else:
        print(f"Error: {response.text}")

def wait_and_monitor(search_ids, duration_minutes=3):
    """Monitor searches for a period of time"""
    print(f"\n⏱️  Monitoring searches for {duration_minutes} minutes...")
    
    end_time = datetime.now() + timedelta(minutes=duration_minutes)
    
    while datetime.now() < end_time:
        print(f"\n📊 Status check at {datetime.now().strftime('%H:%M:%S')}")
        searches = check_all_searches()
        
        # Show pending/running searches
        pending = [s for s in searches if s.get('status') in ['pending', 'running']]
        completed = [s for s in searches if s.get('status') == 'completed']
        
        print(f"Pending/Running: {len(pending)}")
        print(f"Completed: {len(completed)}")
        
        if not pending:
            print("✅ All searches completed!")
            break
        
        print("⏳ Waiting 30 seconds...")
        asyncio.sleep(30)

def main():
    """Run all tests"""
    print("🚀 Starting Distributed Scheduler Testing")
    print("=" * 50)
    
    try:
        # Test basic connectivity
        response = requests.get(f"{BASE_URL}/admin/stats")
        if response.status_code != 200:
            print("❌ Cannot connect to admin API. Is the server running?")
            return
        
        # Run tests
        immediate_id = test_immediate_search()
        future_id = test_future_search()
        recurring_id = test_recurring_search()
        
        # Check initial status
        check_all_searches()
        check_admin_stats()
        
        # Test search details
        check_search_details(immediate_id)
        
        # Monitor for execution
        wait_and_monitor([immediate_id, future_id, recurring_id])
        
        # Test cancellation on future search if still pending
        test_search_cancellation(future_id)
        
        # Final status check
        print("\n📋 Final Status:")
        check_all_searches()
        check_admin_stats()
        
        print("\n✅ Testing completed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection error. Make sure the server is running on localhost:8787")
    except Exception as e:
        print(f"❌ Test error: {e}")

if __name__ == "__main__":
    main()