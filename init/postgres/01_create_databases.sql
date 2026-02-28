-- =============================================================================
-- PostgreSQL Initialization Script 1: Create Databases
-- The 'airflow' database is created by Airflow-init via env vars.
-- Here we create the analytics database.
-- =============================================================================

SELECT 'CREATE DATABASE crypto_analytics'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'crypto_analytics'
)\gexec

SELECT 'CREATE DATABASE superset'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'superset'
)\gexec
