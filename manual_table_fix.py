#!/usr/bin/env python3
"""
Manual table creation script - can be copied to server and run directly
Creates tables without needing GitHub access
"""
import requests
import json

# SQL to create essential tables
create_tables_sql = """
-- Create companies table
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create locations table  
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(50),
    country VARCHAR(50) NOT NULL DEFAULT 'USA',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create scraping_runs table (this is the missing one causing errors)
CREATE TABLE IF NOT EXISTS scraping_runs (
    id SERIAL PRIMARY KEY,
    source_platform VARCHAR(100) NOT NULL,
    search_terms VARCHAR[] DEFAULT '{}',
    locations VARCHAR[] DEFAULT '{}',
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    jobs_found INTEGER DEFAULT 0,
    jobs_processed INTEGER DEFAULT 0,
    jobs_skipped INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    error_details JSONB,
    config_used JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Create constraints
CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_name_domain ON companies(name, domain);
CREATE UNIQUE INDEX IF NOT EXISTS uq_locations_city_state_country ON locations(city, state, country);
"""

print("Manual table creation for JobSpy API")
print("=" * 50)

# Test if we can reach the API
try:
    response = requests.get("http://192.168.7.10:8787/health", timeout=5)
    print(f"✅ API accessible: {response.status_code}")
except Exception as e:
    print(f"❌ API not accessible: {e}")
    exit(1)

# Show the SQL that needs to be executed
print("\n📋 SQL Commands needed:")
print("=" * 30)
print(create_tables_sql)

print("\n🔧 To fix manually:")
print("1. Connect to PostgreSQL database on the server")
print("2. Run the SQL commands above")
print("3. Or copy this script to the server and modify to connect directly to DB")

print("\n🐳 Alternative: Docker exec approach")
print("If you have container access:")
print("docker exec -it <container-name> psql $DATABASE_URL -c \"<SQL-commands>\"")

# Test current database status
try:
    test_response = requests.post(
        "http://192.168.7.10:8787/admin/searches",
        json={
            "name": "Table Test",
            "search_term": "test",
            "location": "remote",
            "site_names": ["indeed"],
            "results_wanted": 1,
            "schedule_time": "2025-06-25T17:00:00",
            "recurring": False
        },
        timeout=10
    )
    
    if "scraping_runs" in test_response.text and "does not exist" in test_response.text:
        print("\n✅ Database connection confirmed")
        print("❌ Tables missing (as expected)")
        print("💡 Ready for manual table creation!")
    else:
        print(f"\n❓ Unexpected response: {test_response.text[:200]}...")
        
except Exception as e:
    print(f"\n❌ API test failed: {e}")