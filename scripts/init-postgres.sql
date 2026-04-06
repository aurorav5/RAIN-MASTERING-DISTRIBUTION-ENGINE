-- RAIN PostgreSQL initialization script
-- Enables required extensions and configures RLS baseline

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- The rain_app role is created by Docker's POSTGRES_USER env var.
-- This script only ensures extensions are loaded and privileges are granted.
-- DO NOT hardcode passwords here — use POSTGRES_PASSWORD env var instead.

-- Grant privileges on the rain database
GRANT ALL PRIVILEGES ON DATABASE rain TO rain_app;
