-- Direct SQL script to create job tracking tables
-- Run this if the Python table creation scripts aren't working

-- Companies table
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),
    industry VARCHAR(100),
    company_size VARCHAR(50),
    headquarters_location VARCHAR(255),
    founded_year INTEGER,
    revenue_range VARCHAR(50),
    description TEXT,
    logo_url TEXT,
    linkedin_company_id INTEGER,
    glassdoor_company_id VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Locations table  
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(50),
    country VARCHAR(50) NOT NULL DEFAULT 'USA',
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Job postings table
CREATE TABLE IF NOT EXISTS job_postings (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    company_id INTEGER REFERENCES companies(id),
    location_id INTEGER REFERENCES locations(id),
    description TEXT,
    job_type VARCHAR(50),
    salary_min DECIMAL(12, 2),
    salary_max DECIMAL(12, 2),
    salary_currency VARCHAR(3) DEFAULT 'USD',
    is_remote BOOLEAN DEFAULT FALSE,
    job_url TEXT,
    source_platform VARCHAR(50) NOT NULL,
    date_posted DATE,
    date_scraped TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Scraping runs table
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

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(name);
CREATE INDEX IF NOT EXISTS idx_companies_domain ON companies(domain);
CREATE INDEX IF NOT EXISTS idx_companies_industry ON companies(industry);
CREATE INDEX IF NOT EXISTS idx_companies_linkedin_id ON companies(linkedin_company_id);

CREATE INDEX IF NOT EXISTS idx_locations_city_state ON locations(city, state);
CREATE INDEX IF NOT EXISTS idx_locations_country ON locations(country);

CREATE INDEX IF NOT EXISTS idx_job_postings_external_platform ON job_postings(external_id, source_platform);
CREATE INDEX IF NOT EXISTS idx_job_postings_title ON job_postings(title);
CREATE INDEX IF NOT EXISTS idx_job_postings_company ON job_postings(company_id);
CREATE INDEX IF NOT EXISTS idx_job_postings_location ON job_postings(location_id);
CREATE INDEX IF NOT EXISTS idx_job_postings_date_posted ON job_postings(date_posted);
CREATE INDEX IF NOT EXISTS idx_job_postings_source ON job_postings(source_platform);
CREATE INDEX IF NOT EXISTS idx_job_postings_active ON job_postings(is_active);

CREATE INDEX IF NOT EXISTS idx_scraping_runs_platform ON scraping_runs(source_platform);
CREATE INDEX IF NOT EXISTS idx_scraping_runs_status ON scraping_runs(status);
CREATE INDEX IF NOT EXISTS idx_scraping_runs_start_time ON scraping_runs(start_time);

-- Create unique constraints
CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_name_domain ON companies(name, domain);
CREATE UNIQUE INDEX IF NOT EXISTS uq_locations_city_state_country ON locations(city, state, country);
CREATE UNIQUE INDEX IF NOT EXISTS uq_job_postings_external_platform ON job_postings(external_id, source_platform);

-- Insert a test company and location for immediate testing
INSERT INTO companies (name, domain, created_at) 
VALUES ('Test Company', 'test.com', NOW()) 
ON CONFLICT (name, domain) DO NOTHING;

INSERT INTO locations (city, state, country, created_at) 
VALUES ('Remote', '', 'USA', NOW()) 
ON CONFLICT (city, state, country) DO NOTHING;

-- Verify tables were created
SELECT 'Tables created successfully' as status;
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;