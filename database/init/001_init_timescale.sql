-- Initialize TimescaleDB extension and create hypertables
-- This script runs automatically when the container starts

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enable PostGIS for future geographic features (optional)
-- CREATE EXTENSION IF NOT EXISTS postgis;

-- Create function for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- This file is for TimescaleDB-specific initialization
-- The actual table creation will be handled by Alembic migrations