# Admin Fix Scripts

This directory contains scripts to fix the identified admin endpoint issues.

## Quick Fix - Run All

To fix all issues at once, run this script in the container:

```bash
python /app/scripts/fix_all_issues.py
```

## Individual Fix Scripts

### 1. Database Issues (`init_database.py`)

Creates missing database tables (`job_postings`, `scraping_runs`, etc.):

```bash
python /app/scripts/init_database.py
```

**What it fixes:**
- Missing `job_postings` table causing admin endpoints to fail
- Missing `scraping_runs` table causing cleanup operations to fail
- Creates all required tables from the SQLAlchemy models

### 2. Redis Connectivity (`test_redis.py`)

Tests Redis connection and provides debugging information:

```bash
python /app/scripts/test_redis.py
```

**What it checks:**
- Redis server connectivity
- Basic set/get operations
- Server information and status

### 3. Job Site Access (`fix_job_sites.py`)

Improves job site connectivity and creates configuration patches:

```bash
python /app/scripts/fix_job_sites.py
```

**What it fixes:**
- 403 errors from job sites (Indeed, Glassdoor, etc.)
- Creates modern user agent configurations
- Tests site connectivity with improved headers

## Running in Container

If you're using Docker/Portainer, you can run these scripts by:

1. **Exec into the container:**
   ```bash
   docker exec -it <container-name> /bin/bash
   ```

2. **Run the fix script:**
   ```bash
   cd /app
   python scripts/fix_all_issues.py
   ```

## Expected Results

After running the fixes:

- ✅ `/admin/health` should show database as "connected"
- ✅ `/admin/stats` should return proper statistics
- ✅ `/admin/jobs` should list jobs without database errors
- ✅ `/admin/searches/cleanup` should work without table errors
- ✅ Job sites should show "accessible" instead of "error_403"

## Troubleshooting

If scripts fail:

1. **Check you're in the container:** Scripts need access to the app environment
2. **Check database connection:** Ensure PostgreSQL is running and accessible
3. **Check Redis connection:** Ensure Redis is running on the configured URL
4. **Check logs:** Look at the detailed error messages in the script output

## Manual Verification

After running fixes, test the admin endpoints:

```bash
# Test database fix
curl "http://localhost:8000/admin/jobs"

# Test Redis (if applicable)
curl "http://localhost:8000/admin/cache/clear" -X POST

# Check health status
curl "http://localhost:8000/admin/health"
```