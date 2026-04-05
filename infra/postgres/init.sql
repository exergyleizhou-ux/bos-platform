-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
-- BOS Pipeline v9.0 �� PostgreSQL Initialization
--
-- Runs once when the database container is first created.
-- Sets up extensions, roles, and RLS configuration variable.
-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

-- Required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";         -- Trigram indexing for text search
CREATE EXTENSION IF NOT EXISTS "btree_gist";       -- Exclusion constraints

-- Custom configuration parameter for RLS
-- This allows SET LOCAL app.current_tenant_id = '<id>' per transaction
ALTER DATABASE bos_pipeline SET app.current_tenant_id = '0';

-- Read-only role for analytics/BI tools
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'bos_readonly') THEN
        CREATE ROLE bos_readonly LOGIN PASSWORD 'readonly_secret';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE bos_pipeline TO bos_readonly;
GRANT USAGE ON SCHEMA public TO bos_readonly;

-- After tables are created, run:
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO bos_readonly;
-- ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO bos_readonly;

-- Function: auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- NOTE: Triggers are created by Alembic migrations after table creation.
-- Example (applied by migration):
--   CREATE TRIGGER set_updated_at
--     BEFORE UPDATE ON tenants
--     FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
