-- =============================================================================
-- PostgreSQL dbt Target Schema Setup
-- Run as: psql -U postgres -d crypto_analytics -f sql/schema.sql
-- =============================================================================

\c crypto_analytics;

-- ---------------------------------------------------------------------------
-- Schemas for Medallion Architecture (dbt targets)
-- ---------------------------------------------------------------------------

-- Bronze: Raw or closely-mapped raw data (often just views on public.raw_klines)
CREATE SCHEMA IF NOT EXISTS bronze;

-- Silver: Cleaned, filtered, enriched, and standardized data
CREATE SCHEMA IF NOT EXISTS silver;

-- Gold: Aggregated business-level metrics and facts for Superset
CREATE SCHEMA IF NOT EXISTS gold;

-- ---------------------------------------------------------------------------
-- Permissions
-- ---------------------------------------------------------------------------
-- In a real production setup, we would grant specific usage to dbt roles.
-- For this local stack, the 'postgres' superuser handles everything.
GRANT ALL ON SCHEMA bronze TO postgres;
GRANT ALL ON SCHEMA silver TO postgres;
GRANT ALL ON SCHEMA gold TO postgres;

-- ---------------------------------------------------------------------------
-- dbt will create the tables/views automatically, but laying out the schemas
-- ensures dbt can logically separate the medallion layers.
-- ---------------------------------------------------------------------------
