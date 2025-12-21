-- Database schema for user management system.
-- Includes tables for users, roles, and audit logging.
-- Compatible with PostgreSQL 14+.

-- ==============================================================================
-- Extensions
-- ==============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- Custom Types
-- ==============================================================================

-- User status enumeration
CREATE TYPE user_status AS ENUM (
    'pending',
    'active',
    'suspended',
    'deactivated'
);

-- Audit action types
CREATE TYPE audit_action AS ENUM (
    'create',
    'update',
    'delete',
    'login',
    'logout',
    'password_change'
);

-- ==============================================================================
-- Tables
-- ==============================================================================

-- Roles table for RBAC
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create index on role name for fast lookups
CREATE INDEX idx_roles_name ON roles(name);

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) NOT NULL,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    display_name VARCHAR(200),
    avatar_url TEXT,
    status user_status NOT NULL DEFAULT 'pending',
    role_id UUID NOT NULL REFERENCES roles(id),
    last_login_at TIMESTAMPTZ,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- Unique constraint on email (case-insensitive)
CREATE UNIQUE INDEX idx_users_email_unique ON users(LOWER(email)) WHERE deleted_at IS NULL;

-- Indexes for common queries
CREATE INDEX idx_users_role ON users(role_id);
CREATE INDEX idx_users_status ON users(status) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_created_at ON users(created_at DESC);

-- User sessions table
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    ip_address INET,
    user_agent TEXT,
    is_valid BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for token lookups
CREATE INDEX idx_sessions_token ON user_sessions(token_hash) WHERE is_valid = TRUE;
CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);

-- Audit log table
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action audit_action NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Partition audit logs by month for performance
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);

-- ==============================================================================
-- Functions
-- ==============================================================================

-- Automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Hash password with bcrypt
CREATE OR REPLACE FUNCTION hash_password(password TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN crypt(password, gen_salt('bf', 12));
END;
$$ LANGUAGE plpgsql;

-- Verify password against hash
CREATE OR REPLACE FUNCTION verify_password(password TEXT, password_hash TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN password_hash = crypt(password, password_hash);
END;
$$ LANGUAGE plpgsql;

-- Record audit log entry
CREATE OR REPLACE FUNCTION record_audit_log(
    p_user_id UUID,
    p_action audit_action,
    p_entity_type VARCHAR(100),
    p_entity_id UUID,
    p_old_values JSONB DEFAULT NULL,
    p_new_values JSONB DEFAULT NULL,
    p_ip_address INET DEFAULT NULL
)
RETURNS BIGINT AS $$
DECLARE
    log_id BIGINT;
BEGIN
    INSERT INTO audit_logs (user_id, action, entity_type, entity_id, old_values, new_values, ip_address)
    VALUES (p_user_id, p_action, p_entity_type, p_entity_id, p_old_values, p_new_values, p_ip_address)
    RETURNING id INTO log_id;

    RETURN log_id;
END;
$$ LANGUAGE plpgsql;

-- ==============================================================================
-- Triggers
-- ==============================================================================

-- Update timestamps automatically
CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER roles_updated_at
    BEFORE UPDATE ON roles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ==============================================================================
-- Initial Data
-- ==============================================================================

-- Default system roles
INSERT INTO roles (name, description, permissions, is_system) VALUES
    ('superadmin', 'Full system access', '["*"]'::jsonb, TRUE),
    ('admin', 'Administrative access', '["users:read", "users:write", "roles:read"]'::jsonb, TRUE),
    ('user', 'Standard user access', '["profile:read", "profile:write"]'::jsonb, TRUE),
    ('guest', 'Limited guest access', '["public:read"]'::jsonb, TRUE);

-- ==============================================================================
-- Views
-- ==============================================================================

-- Active users with role information
CREATE OR REPLACE VIEW v_active_users AS
SELECT
    u.id,
    u.email,
    u.display_name,
    u.status,
    r.name AS role_name,
    r.permissions,
    u.last_login_at,
    u.created_at
FROM users u
JOIN roles r ON u.role_id = r.id
WHERE u.deleted_at IS NULL
  AND u.status = 'active';

-- User statistics
CREATE OR REPLACE VIEW v_user_stats AS
SELECT
    r.name AS role_name,
    u.status,
    COUNT(*) AS user_count,
    COUNT(*) FILTER (WHERE u.last_login_at > NOW() - INTERVAL '30 days') AS active_30d
FROM users u
JOIN roles r ON u.role_id = r.id
WHERE u.deleted_at IS NULL
GROUP BY r.name, u.status
ORDER BY r.name, u.status;
