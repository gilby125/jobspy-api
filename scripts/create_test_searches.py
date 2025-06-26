#!/usr/bin/env python3
"""
Script to create hourly recurring searches for testing duplicate tracking.

This script creates several recurring searches across multiple job platforms
for popular job titles and locations to maximize the chance of finding 
duplicate jobs for testing the tracking schema.
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict

# Add parent directory to path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_db
from app.models.admin_models import ScheduledSearchRequest, BulkSearchRequest
from app.services.admin_service import AdminService


async def create_test_searches():
    """Create hourly recurring searches for testing duplicate detection"""
    
    # Popular job titles that are likely to appear on multiple platforms
    job_titles = [
        "software engineer",
        "data scientist", 
        "product manager",
        "frontend developer",
        "python developer",
        "machine learning engineer",
        "devops engineer",
        "full stack developer",
        "backend developer",
        "marketing manager"
    ]
    
    # Major tech hub locations where jobs are likely to be posted on multiple sites
    locations = [
        "San Francisco, CA",
        "New York, NY", 
        "Seattle, WA",
        "Austin, TX",
        "Boston, MA"
    ]
    
    # Job sites to search across
    all_sites = ["indeed", "linkedin", "glassdoor"]
    
    searches_to_create = []
    
    # Create searches that will maximize duplicate detection
    for i, title in enumerate(job_titles[:5]):  # Start with 5 titles
        for j, location in enumerate(locations[:3]):  # Start with 3 locations
            
            # Create a search that uses multiple sites (high chance of duplicates)
            search = ScheduledSearchRequest(
                name=f"Hourly {title.title()} - {location}",
                search_term=title,
                location=location,
                site_names=all_sites,  # Search all sites to maximize duplicates
                country_indeed="USA",
                results_wanted=30,  # Get more results to increase chance of overlap
                recurring=True,
                recurring_interval="hourly",
                schedule_time=datetime.now() + timedelta(minutes=5 + (i * j))  # Stagger start times
            )
            searches_to_create.append(search)
    
    # Create some searches for just single sites to mix the data
    for i, title in enumerate(job_titles[5:8]):  # Next 3 titles
        for site in all_sites:
            search = ScheduledSearchRequest(
                name=f"Hourly {title.title()} - {site.title()} Only",
                search_term=title,
                location="Remote",  # Remote jobs often posted on multiple sites
                site_names=[site],
                country_indeed="USA", 
                results_wanted=20,
                recurring=True,
                recurring_interval="hourly",
                schedule_time=datetime.now() + timedelta(minutes=10 + i)
            )
            searches_to_create.append(search)
    
    # Create some broader searches that are very likely to have duplicates
    broad_searches = [
        {
            "name": "Hourly Tech Jobs - SF Bay Area (All Sites)",
            "search_term": "software",
            "location": "San Francisco Bay Area, CA",
            "site_names": all_sites,
            "results_wanted": 50
        },
        {
            "name": "Hourly Data Jobs - NYC (All Sites)", 
            "search_term": "data",
            "location": "New York, NY",
            "site_names": all_sites,
            "results_wanted": 40
        },
        {
            "name": "Hourly Remote Engineering Jobs (All Sites)",
            "search_term": "engineer",
            "location": "Remote",
            "site_names": all_sites,
            "results_wanted": 35
        }
    ]
    
    for i, search_config in enumerate(broad_searches):
        search = ScheduledSearchRequest(
            name=search_config["name"],
            search_term=search_config["search_term"],
            location=search_config["location"],
            site_names=search_config["site_names"],
            country_indeed="USA",
            results_wanted=search_config["results_wanted"],
            recurring=True,
            recurring_interval="hourly",
            schedule_time=datetime.now() + timedelta(minutes=15 + i * 2)
        )
        searches_to_create.append(search)
    
    print(f"Created {len(searches_to_create)} test searches for duplicate tracking")
    
    # Print summary
    print("\n=== SEARCH SUMMARY ===")
    for search in searches_to_create:
        sites_str = ", ".join(search.site_names)
        schedule_time = search.schedule_time.strftime("%H:%M:%S") if search.schedule_time else "Now"
        print(f"• {search.name}")
        print(f"  Term: '{search.search_term}' | Location: {search.location}")
        print(f"  Sites: {sites_str} | Results: {search.results_wanted}")
        print(f"  Starts: {schedule_time} | Recurring: {search.recurring_interval}")
        print()
    
    return searches_to_create


async def submit_searches_to_admin(searches: List[ScheduledSearchRequest]):
    """Submit the searches using the admin API"""
    
    # Create bulk request
    bulk_request = BulkSearchRequest(
        searches=searches,
        batch_name=f"Duplicate Testing Searches - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    
    # Get database session
    db = next(get_db())
    
    try:
        # Create admin service
        admin_service = AdminService(db)
        
        successful = 0
        failed = 0
        
        # Create each search individually 
        for search in searches:
            try:
                # Generate a unique search ID
                search_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{successful}"
                
                # Create the scheduled search
                result = await admin_service.create_scheduled_search(search_id, search)
                
                print(f"✅ Created: {search.name}")
                print(f"   ID: {result.id}")
                print(f"   Status: {result.status}")
                print(f"   Scheduled: {result.scheduled_time}")
                print()
                
                successful += 1
                
            except Exception as e:
                print(f"❌ Failed: {search.name}")
                print(f"   Error: {str(e)}")
                print()
                failed += 1
        
        print(f"\n=== RESULTS ===")
        print(f"✅ Successfully created: {successful} searches")
        print(f"❌ Failed: {failed} searches") 
        print(f"📊 Total: {len(searches)} searches")
        
        if successful > 0:
            print(f"\n🔄 Hourly recurring searches are now active!")
            print(f"🔍 These will help populate the tracking schema with duplicate job data")
            print(f"📈 Check the admin interface to see deduplication metrics")
            
    finally:
        db.close()


async def main():
    """Main function to create and submit test searches"""
    print("🚀 Creating hourly recurring searches for duplicate tracking testing...")
    print("=" * 60)
    
    try:
        # Create the search configurations
        searches = await create_test_searches()
        
        print(f"\n🚀 Creating {len(searches)} recurring hourly searches...")
        print("These searches will run every hour to test duplicate tracking.")
        
        print("\n📤 Submitting searches to admin system...")
        await submit_searches_to_admin(searches)
        
        print("\n🎯 NEXT STEPS:")
        print("1. Visit /admin/scheduler to see your new recurring searches")
        print("2. Visit /admin/jobs/page to see jobs as they are found")
        print("3. Watch the deduplication metrics in the admin dashboard") 
        print("4. Check tracking statistics after a few hours of data collection")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)