# Duplicate Tracking Test Setup

This document describes the setup for testing the duplicate tracking and deduplication features in the JobSpy tracking schema.

## Overview

We've created several scripts and configurations to help test the duplicate detection capabilities:

1. **Comprehensive Remote Job Searches** - 21 recurring hourly searches focused on remote US jobs
2. **Quick Test Script** - Immediate searches to generate initial duplicate data
3. **Setup Scripts** - Easy configuration and deployment tools

## Files Created

### 📋 Configuration Files

- **`scripts/remote_job_searches.json`** - Complete configuration for 21 recurring searches
- **`scripts/submit_remote_searches.py`** - Setup guide and JSON generator
- **`scripts/quick_duplicate_test.py`** - Quick test to generate immediate duplicate data

### 🎯 Search Strategy

The searches are designed to maximize duplicate detection:

#### Multi-Site Searches (High Duplicate Potential)
- Software Engineer, Frontend Developer, Backend Developer, Full Stack Developer
- Python Developer, JavaScript Developer, Data Scientist, Machine Learning Engineer  
- DevOps Engineer, Product Manager, UI/UX Designer, Data Engineer
- **Strategy**: Same job titles across Indeed, LinkedIn, and Glassdoor

#### Single-Site Searches (Baseline Data)
- React Developer (3 separate searches - one per site)
- Node.js Developer (3 separate searches - one per site)
- **Strategy**: Compare same roles across different platforms

#### Broad Searches (Maximum Coverage)
- "software", "engineer", "developer" terms
- **Strategy**: Cast wide net to catch maximum job overlap

## Expected Results

### 📊 Volume Projections
- **Total results per hour**: ~665 job postings
- **Expected duplicates per hour**: ~100-200 (15-30% duplication rate)
- **High-overlap searches**: React and Node.js developers across 3 sites

### 🔍 Duplicate Detection Scenarios

1. **Same Job, Multiple Sites**: Company posts same job on Indeed, LinkedIn, and Glassdoor
2. **Similar Titles**: "Frontend Developer" vs "Front-end Developer" vs "Front End Developer"
3. **Location Variations**: "Remote" vs "United States" vs specific city with remote option
4. **Company Variations**: Full company name vs abbreviated vs subsidiary names

## Setup Instructions

### Method 1: Admin Interface (Recommended)

1. Navigate to `/admin/searches` in your JobSpy admin panel
2. Click on "Bulk Search" or similar bulk import feature
3. Copy the JSON configuration from `scripts/submit_remote_searches.py` output
4. Paste and submit to create all 21 recurring searches

### Method 2: API Direct Submission

```bash
# Run the setup script to get the curl command
python scripts/submit_remote_searches.py

# Use the generated curl command with your API key
curl -X POST http://localhost:8787/admin/searches/bulk \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: YOUR_API_KEY' \
  -d @scripts/remote_job_searches.json
```

### Method 3: Quick Test (Immediate Results)

```bash
# Run quick searches to get immediate duplicate data
python scripts/quick_duplicate_test.py
```

## Monitoring Duplicate Detection

### 📈 Admin Dashboard Metrics

Visit `/admin/jobs/page` to see:
- **Duplicate Job Indicators**: Yellow highlighting and 🔄 badges
- **Multi-Source Jobs**: Blue badges showing jobs found on multiple sites  
- **Tracking Metrics**: Days active, repost count, total seen count
- **Deduplication Rate**: Percentage in the statistics dashboard

### 🔍 Key Indicators to Watch

1. **Job Hash Collisions**: Same `job_hash` appearing multiple times
2. **Source Site Lists**: Jobs showing "2 sites", "3 sites" etc.
3. **Repost Counts**: Jobs with repost_count > 0
4. **Total Seen Count**: Jobs with total_seen_count > 1

### 📊 Statistics to Monitor

- **Total Jobs**: Overall job count in tracking schema
- **Duplicate Jobs**: Jobs found on multiple sites  
- **Multi-Source Jobs**: Jobs posted to multiple platforms
- **Deduplication Rate**: Percentage of jobs that are duplicates

## Testing the Tracking Schema

### ✅ Success Criteria

1. **Duplicate Detection**: Jobs with same title+company appear as duplicates
2. **Multi-Source Tracking**: Same job from different sites linked together
3. **Metrics Accuracy**: Correct counts for days active, reposts, etc.
4. **UI Display**: Proper badges and indicators in admin interface
5. **Performance**: Fast queries and responsive admin interface

### 🔧 Troubleshooting

If duplicates aren't being detected:

1. **Check Job Hashing**: Verify `job_hash` generation in tracking schema
2. **Review Deduplication Logic**: Check `JobTrackingService.process_scraped_jobs()`
3. **Database Queries**: Ensure tracking schema tables have proper relationships
4. **Admin Interface**: Verify frontend is using tracking endpoints

## Next Steps

1. **Run Setup**: Use one of the methods above to create recurring searches
2. **Wait 2-3 Hours**: Allow searches to run and collect data
3. **Review Results**: Check admin interface for duplicate indicators
4. **Analyze Data**: Look at deduplication rates and multi-source jobs
5. **Fine-tune**: Adjust search parameters based on results

## Notes

- All searches focus on **remote jobs in the US** to maximize overlap potential
- Searches run **hourly** to continuously generate fresh duplicate data
- **Staggered start times** prevent all searches from running simultaneously
- **Varied result counts** (20-50 per search) to balance coverage vs performance