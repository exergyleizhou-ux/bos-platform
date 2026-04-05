-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
-- BOS Pipeline v9.0 �� Database Initialization
-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
-- This script runs once when the PostgreSQL container is first created.
-- It sets up extensions, roles, and RLS foundations.

-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
-- 1. Extensions
-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";       -- trigram fuzzy search
CREATE EXTENSION IF NOT EXISTS "btree_gin";      -- GIN index support
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";  -- query performance

-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
-- 2. Custom Types
-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('admin', 'scientist', 'operator', 'viewer', 'billing');
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'batch_status') THEN
        CREATE TYPE batch_status AS ENUM ('logged', 'active', 'completed', 'archived');
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'calculation_status') THEN
        CREATE TYPE calculation_status AS ENUM ('pending', 'running', 'completed', 'failed');
    END IF;
END$$;

-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
-- 3. Row-Level Security Helper Function
-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

-- Function to get current tenant_id from session variable
CREATE OR REPLACE FUNCTION current_tenant_id()
RETURNS INTEGER
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN COALESCE(
        NULLIF(current_setting('app.current_tenant_id', true), '')::INTEGER,
        0
    );
END;
$$;

-- Function to get current user_id from session variable
CREATE OR REPLACE FUNCTION current_app_user_id()
RETURNS INTEGER
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    RETURN COALESCE(
        NULLIF(current_setting('app.current_user_id', true), '')::INTEGER,
        0
    );
END;
$$;

-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
-- 4. Audit Trigger Function
-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

CREATE OR REPLACE FUNCTION audit_trigger_func()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    audit_row RECORD;
    changed_fields JSONB;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (
            table_name, record_id, action, new_data,
            user_id, tenant_id, ip_address
        ) VALUES (
            TG_TABLE_NAME, NEW.id, 'INSERT', to_jsonb(NEW),
            current_app_user_id(), current_tenant_id(),
            COALESCE(NULLIF(current_setting('app.client_ip', true), ''), 'unknown')
        );
        RETURN NEW;

    ELSIF TG_OP = 'UPDATE' THEN
        -- Only log if something actually changed
        IF OLD IS DISTINCT FROM NEW THEN
            changed_fields := jsonb_object_agg(key, value)
                FROM jsonb_each(to_jsonb(NEW))
                WHERE to_jsonb(NEW) -> key IS DISTINCT FROM to_jsonb(OLD) -> key;

            INSERT INTO audit_log (
                table_name, record_id, action, old_data, new_data, changed_fields,
                user_id, tenant_id, ip_address
            ) VALUES (
                TG_TABLE_NAME, NEW.id, 'UPDATE', to_jsonb(OLD), to_jsonb(NEW), changed_fields,
                current_app_user_id(), current_tenant_id(),
                COALESCE(NULLIF(current_setting('app.client_ip', true), ''), 'unknown')
            );
        END IF;
        RETURN NEW;

    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (
            table_name, record_id, action, old_data,
            user_id, tenant_id, ip_address
        ) VALUES (
            TG_TABLE_NAME, OLD.id, 'DELETE', to_jsonb(OLD),
            current_app_user_id(), current_tenant_id(),
            COALESCE(NULLIF(current_setting('app.client_ip', true), ''), 'unknown')
        );
        RETURN OLD;
    END IF;
END;
$$;

-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
-- 5. Temporal Table Support
-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

-- Function to manage valid_from/valid_to for temporal records
CREATE OR REPLACE FUNCTION temporal_update_func()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Close the current version
    UPDATE batches
    SET valid_to = NOW()
    WHERE id = OLD.id AND valid_to IS NULL;

    -- The new version will be inserted with valid_from = NOW()
    NEW.valid_from := NOW();
    NEW.valid_to := NULL;

    RETURN NEW;
END;
$$;

-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
-- 6. Tenant Isolation Guard
-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

-- Prevent tenant_id from being changed after insert
CREATE OR REPLACE FUNCTION prevent_tenant_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
        RAISE EXCEPTION 'tenant_id cannot be changed after creation (attempted: % -> %)',
            OLD.tenant_id, NEW.tenant_id;
    END IF;
    RETURN NEW;
END;
$$;

-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
-- 7. Updated-At Auto-Timestamp
-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T
-- 8. Performance Settings
-- �T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T�T

-- Optimize for our workload (adjust based on available RAM)
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '768MB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET maintenance_work_mem = '128MB';
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET max_worker_processes = 8;
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
ALTER SYSTEM SET max_parallel_workers = 8;

-- Logging
ALTER SYSTEM SET log_min_duration_statement = 200;  -- Log slow queries (>200ms)
ALTER SYSTEM SET log_checkpoints = on;
ALTER SYSTEM SET log_connections = on;
ALTER SYSTEM SET log_disconnections = on;
ALTER SYSTEM SET log_lock_waits = on;
ALTER SYSTEM SET log_temp_files = 0;

-- WAL
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;

-- Statistics
ALTER SYSTEM SET default_statistics_target = 200;
ALTER SYSTEM SET track_activity_query_size = 4096;

-- Notify about settings (requires restart for some)
DO $$ BEGIN RAISE NOTICE 'Database initialization complete. Some settings require a restart.'; END $$;
