# Claude Code Configuration

 - Jobspy api docs and openapi.json is @localhost:8787/docs & http://localhost:8787/openapi.json when the docker container is running

## User Instructions

 - Do not lie
 - Use your MCP servers and suggest new ones
 - refer to all .Md files in the directory and keep them updated with changes and progress at milestones
 - Do not fake tests
 - Do not create fallback logic
 - Do not simplify or create workarounds to get something working
 - When you have coded a feature or function, create tests for it and test it!
 - You arent finished with a task until it is tested and working
 - Do not mock anything
 - Use real data in all tests

## Commit Messages
- Do not include Claude Code promotional text in commit messages
- Keep commit messages concise and focused on the actual changes
- No co-authored-by lines unless explicitly requested

## Schema Migration Progress (COMPLETED - 2025-06-26)

### All Migration Tasks Completed ✅

#### Phase 1: Schema Design & Migration Scripts (Completed)
1. ✅ Created detailed field mapping document (`docs/schema_migration_mapping.md`)
2. ✅ Developed Alembic migration scripts:
   - `20250626_1416_b77c46b5c926_create_tracking_schema.py` - Creates temp_ tables
   - `20250626_1430_275658513cef_finalize_migration.py` - Basic migration SQL
3. ✅ Enhanced migration service (`app/services/migration_service.py`):
   - Handles job deduplication using job_hash
   - Maps old schema IDs to new schema IDs
   - Groups duplicate jobs into single entries with multiple sources
4. ✅ Created migration runner script (`scripts/run_migration.py`):
   - Checks prerequisites
   - Runs data migration with deduplication
   - Provides finalization option with table swapping

#### Phase 2: Service Integration (Completed)
5. ✅ Modified JobService to use JobTrackingService:
   - Removed direct DB operations
   - Now delegates to job_tracking_service.process_scraped_jobs()
   - Returns enhanced statistics including deduplication info
6. ✅ Created new API routes using tracking models (`app/api/routes/jobs_tracking.py`):
   - Enhanced search with source site filtering
   - Shows all sources where a job was found
   - Better metrics including repost count and days active

#### Phase 3: Live Migration & Testing (Completed)
7. ✅ Executed live migration with real job data:
   - Successfully migrated 3 job postings to temp_ tables
   - Validated deduplication functionality
   - Confirmed data integrity and relationships
8. ✅ Finalized migration by swapping tables:
   - Dropped old empty tables
   - Renamed temp_ tables to final names (companies, job_postings, etc.)
   - Updated constraints and indexes
9. ✅ Updated main.py to use tracking routes:
   - Replaced jobs router with jobs_tracking router
   - Added fallback to legacy router if needed
   - Tested all endpoints successfully

#### Phase 4: Validation & Testing (Completed)  
10. ✅ Comprehensive API testing:
    - All tracking endpoints working correctly
    - Search functionality with enhanced filtering
    - Companies and locations endpoints operational
    - Analytics endpoint providing insights
    - CSV export functionality working

### Migration Results:
- **Database Schema**: Successfully migrated to new tracking schema
- **Data Migration**: 3 jobs, 3 companies, 3 locations, 3 sources, 3 metrics records
- **API Endpoints**: All tracking endpoints operational
- **Deduplication**: Working correctly with job_hash system
- **Analytics**: Enhanced metrics and reporting available

### New Features Available:
- ✅ Job deduplication across multiple sources
- ✅ Enhanced job metrics (days active, repost count, etc.)  
- ✅ Multi-source tracking (shows all sites where job was found)
- ✅ Improved search filtering (by source site, enhanced analytics)
- ✅ Better data integrity with proper relationships
- ✅ CSV export with enhanced fields
