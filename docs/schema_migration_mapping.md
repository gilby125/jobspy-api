# Schema Migration Mapping: existing_models.py → tracking_models.py

## Overview
This document provides a detailed mapping of fields from the existing database schema to the new tracking-oriented schema. The new schema introduces deduplication capabilities through job_hash and separates job sources from core job data.

## Table Mappings

### 1. Companies Table
**ExistingCompany → Company**

| Existing Field | Tracking Field | Transformation Notes |
|----------------|----------------|---------------------|
| id | id | Direct mapping |
| name | name | Direct mapping |
| domain | domain | Direct mapping |
| industry | industry | Direct mapping |
| company_size | company_size | Direct mapping |
| headquarters_location | headquarters_location | Direct mapping |
| founded_year | founded_year | Direct mapping |
| revenue_range | revenue_range | Direct mapping |
| description | description | Direct mapping |
| logo_url | logo_url | Direct mapping |
| linkedin_company_id | linkedin_company_id | Direct mapping |
| glassdoor_company_id | glassdoor_company_id | Direct mapping |
| created_at | created_at | Direct mapping |
| updated_at | updated_at | Direct mapping |

**New Fields in tracking_models:**
- `hiring_trends` relationship - No equivalent in existing schema

### 2. Locations Table
**ExistingLocation → Location**

| Existing Field | Tracking Field | Transformation Notes |
|----------------|----------------|---------------------|
| id | id | Direct mapping |
| city | city | Direct mapping |
| state | state | Direct mapping |
| country | country | Direct mapping |
| latitude | coordinates | Combine lat/long into string format |
| longitude | coordinates | Combine lat/long into string format |
| metro_area | - | **DROPPED** - Not in new schema |
| timezone | - | **DROPPED** - Not in new schema |
| created_at | created_at | Direct mapping |

**New Fields in tracking_models:**
- `region` - Will need to be derived or left NULL initially
- `coordinates` - Convert from separate lat/long to string format

### 3. Job Categories Table
**ExistingJobCategory → JobCategory**

| Existing Field | Tracking Field | Transformation Notes |
|----------------|----------------|---------------------|
| id | id | Direct mapping |
| name | name | Direct mapping |
| description | - | **DROPPED** - Not in new schema |
| parent_id | parent_category_id | Rename field |
| created_at | created_at | Direct mapping |

### 4. Job Postings Table (Major Changes)
**ExistingJobPosting → JobPosting + JobSource**

The existing job_postings table will be split into two tables:
- `JobPosting`: Core job data with deduplication
- `JobSource`: Platform-specific information

#### JobPosting Table Mapping

| Existing Field | Tracking Field | Transformation Notes |
|----------------|----------------|---------------------|
| id | - | New IDs will be generated |
| external_id | - | Moved to JobSource.external_job_id |
| title | title | Direct mapping |
| company_id | company_id | Direct mapping |
| location_id | location_id | Direct mapping |
| job_category_id | job_category_id | Direct mapping |
| description | description | Direct mapping |
| requirements | requirements | Direct mapping |
| job_type | job_type | Direct mapping |
| experience_level | experience_level | Direct mapping |
| salary_min | salary_min | Direct mapping |
| salary_max | salary_max | Direct mapping |
| salary_currency | salary_currency | Direct mapping |
| salary_interval | salary_interval | Direct mapping |
| is_remote | is_remote | Direct mapping |
| easy_apply | - | Moved to JobSource.easy_apply |
| job_url | - | Moved to JobSource.job_url |
| application_url | - | Moved to JobSource.apply_url |
| source_platform | - | Moved to JobSource.source_site |
| date_posted | - | Moved to JobSource.post_date |
| date_scraped | first_seen_at | Rename and use for initial timestamp |
| last_seen | last_seen_at | Direct mapping |
| is_active | status | Convert boolean to status string |
| skills | - | **DROPPED** - Not in new schema |
| job_metadata | - | **DROPPED** - Not in new schema |

**New Fields in JobPosting:**
- `job_hash` - **CRITICAL**: Must be generated using DeduplicationService
- `status` - Convert from is_active (true→'active', false→'expired')
- `created_at` - Set to date_scraped value
- `updated_at` - Set to last_seen value

#### JobSource Table Mapping (New Table)

| Source Data | JobSource Field | Transformation Notes |
|-------------|-----------------|---------------------|
| job_posting_id | job_posting_id | Link to new JobPosting.id |
| source_platform | source_site | Direct mapping |
| external_id | external_job_id | Direct mapping |
| job_url | job_url | Direct mapping |
| date_posted | post_date | Direct mapping |
| application_url | apply_url | Rename field |
| easy_apply | easy_apply | Direct mapping |
| - | created_at | Set to current timestamp |
| - | updated_at | Set to current timestamp |

### 5. Job Metrics Table
**ExistingJobMetrics → JobMetrics**

| Existing Field | Tracking Field | Transformation Notes |
|----------------|----------------|---------------------|
| id | id | Direct mapping |
| job_posting_id | job_posting_id | Link to new JobPosting.id |
| view_count | - | **DROPPED** - Not in new schema |
| application_count | - | **DROPPED** - Not in new schema |
| save_count | - | **DROPPED** - Not in new schema |
| search_appearance_count | total_seen_count | Rename and repurpose |
| last_updated | updated_at | Rename field |

**New Fields in JobMetrics:**
- `sites_posted_count` - Count distinct sources for the job
- `days_active` - Calculate from first_seen_at to last_seen_at
- `repost_count` - Initialize to 0
- `last_activity_date` - Set from JobPosting.last_seen_at
- `created_at` - Set to current timestamp

### 6. New Tables (No Existing Equivalent)

#### CompanyHiringTrend
- Completely new table for time-series analytics
- Will be populated by scheduled jobs after migration

#### ScrapingRun
- New table for tracking scraping operations
- Will be populated by new scraping runs

#### WebhookSubscription
- New table for webhook management
- No migration needed, starts empty

## Critical Migration Considerations

### 1. Job Deduplication Strategy
- The `job_hash` field is the cornerstone of the new system
- Must be generated for each job using normalized data:
  - Company name (normalized)
  - Job title (normalized)
  - Location (normalized)
  - Job type
  - Experience level
- Use DeduplicationService._generate_job_hash() method

### 2. Handling Duplicate Jobs
- Multiple ExistingJobPosting records may map to one JobPosting
- Strategy:
  1. Group existing jobs by generated job_hash
  2. Take earliest date_scraped as first_seen_at
  3. Take latest last_seen as last_seen_at
  4. Create one JobPosting per unique job_hash
  5. Create multiple JobSource records for each source

### 3. Data Loss Considerations
Fields that will be lost in migration:
- Location: metro_area, timezone
- JobCategory: description
- JobPosting: skills, job_metadata (JSON)
- JobMetrics: view_count, application_count, save_count

### 4. Migration Order
1. Companies (direct mapping)
2. Locations (with coordinate transformation)
3. JobCategories (simple mapping)
4. JobPostings + JobSources (complex transformation with deduplication)
5. JobMetrics (with calculated fields)

### 5. Rollback Strategy
- Create new tables with different names initially (e.g., tracking_job_postings)
- Keep existing tables intact during migration
- Only drop old tables after verification