-- RAIN PostgreSQL initialization script
-- Enables required extensions and configures RLS baseline

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Ensure the application user exists (idempotent)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'rain_app') THEN
    CREATE ROLE rain_app WITH LOGIN PASSWORD 'changeme';
  END IF;
END
$$;

-- Grant privileges on the rain database
GRANT ALL PRIVILEGES ON DATABASE rain TO rain_app;
