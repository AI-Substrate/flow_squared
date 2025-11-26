-- Sample SQL file for tree-sitter exploration
-- Includes DDL, DML, and various SQL constructs

-- ============================================
-- Database and Schema Setup
-- ============================================

-- Create database (if supported)
-- CREATE DATABASE sample_db;

-- Create schema
CREATE SCHEMA IF NOT EXISTS app;

-- Set search path
SET search_path TO app, public;

-- ============================================
-- Table Definitions (DDL)
-- ============================================

-- Users table with various constraints
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT gen_random_uuid() NOT NULL UNIQUE,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'inactive', 'banned')),
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',

    CONSTRAINT users_email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Create index
CREATE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_status ON users (status) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_metadata ON users USING GIN (metadata);

-- Posts table with foreign key
CREATE TABLE IF NOT EXISTS posts (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    content TEXT,
    excerpt TEXT,
    status VARCHAR(20) DEFAULT 'draft',
    published_at TIMESTAMP WITH TIME ZONE,
    view_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (user_id, slug)
);

-- Tags table
CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    slug VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    post_count INTEGER DEFAULT 0
);

-- Junction table (many-to-many)
CREATE TABLE IF NOT EXISTS post_tags (
    post_id BIGINT REFERENCES posts(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (post_id, tag_id)
);

-- ============================================
-- Views
-- ============================================

-- Simple view
CREATE OR REPLACE VIEW active_users AS
SELECT id, username, email, first_name, last_name, created_at
FROM users
WHERE status = 'active' AND deleted_at IS NULL;

-- Complex view with joins
CREATE OR REPLACE VIEW post_details AS
SELECT
    p.id,
    p.title,
    p.slug,
    p.excerpt,
    p.status,
    p.published_at,
    p.view_count,
    u.username AS author_username,
    u.email AS author_email,
    ARRAY_AGG(t.name) FILTER (WHERE t.name IS NOT NULL) AS tags
FROM posts p
INNER JOIN users u ON p.user_id = u.id
LEFT JOIN post_tags pt ON p.id = pt.post_id
LEFT JOIN tags t ON pt.tag_id = t.id
GROUP BY p.id, u.username, u.email;

-- Materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS user_stats AS
SELECT
    u.id AS user_id,
    u.username,
    COUNT(p.id) AS post_count,
    COALESCE(SUM(p.view_count), 0) AS total_views,
    MAX(p.published_at) AS last_published
FROM users u
LEFT JOIN posts p ON u.id = p.user_id AND p.status = 'published'
GROUP BY u.id, u.username
WITH DATA;

-- ============================================
-- Functions and Procedures
-- ============================================

-- Scalar function
CREATE OR REPLACE FUNCTION full_name(first_name VARCHAR, last_name VARCHAR)
RETURNS VARCHAR AS $$
BEGIN
    RETURN COALESCE(first_name, '') || ' ' || COALESCE(last_name, '');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Table function
CREATE OR REPLACE FUNCTION get_user_posts(p_user_id INTEGER)
RETURNS TABLE (
    post_id BIGINT,
    title VARCHAR,
    status VARCHAR,
    published_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT p.id, p.title, p.status, p.published_at
    FROM posts p
    WHERE p.user_id = p_user_id
    ORDER BY p.created_at DESC;
END;
$$ LANGUAGE plpgsql STABLE;

-- Procedure with transaction control
CREATE OR REPLACE PROCEDURE create_user_with_profile(
    p_username VARCHAR,
    p_email VARCHAR,
    p_password_hash VARCHAR
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_user_id INTEGER;
BEGIN
    -- Insert user
    INSERT INTO users (username, email, password_hash)
    VALUES (p_username, p_email, p_password_hash)
    RETURNING id INTO v_user_id;

    -- Log action (assuming audit table exists)
    -- INSERT INTO audit_log (action, entity, entity_id)
    -- VALUES ('CREATE', 'user', v_user_id);

    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE;
END;
$$;

-- ============================================
-- Triggers
-- ============================================

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger
CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER posts_updated_at
    BEFORE UPDATE ON posts
    FOR EACH ROW
    EXECUTE FUNCTION update_timestamp();

-- ============================================
-- DML Operations
-- ============================================

-- Insert with returning
INSERT INTO users (username, email, password_hash, first_name, last_name, status)
VALUES
    ('johndoe', 'john@example.com', 'hash123', 'John', 'Doe', 'active'),
    ('janedoe', 'jane@example.com', 'hash456', 'Jane', 'Doe', 'active')
RETURNING id, username, created_at;

-- Insert with conflict handling (upsert)
INSERT INTO tags (name, slug)
VALUES ('Technology', 'technology')
ON CONFLICT (slug) DO UPDATE SET
    name = EXCLUDED.name;

-- Update with subquery
UPDATE users
SET status = 'inactive'
WHERE id IN (
    SELECT u.id
    FROM users u
    LEFT JOIN posts p ON u.id = p.user_id
    WHERE p.id IS NULL
    AND u.created_at < CURRENT_TIMESTAMP - INTERVAL '1 year'
);

-- Delete with cascade
DELETE FROM users WHERE status = 'banned';

-- ============================================
-- Complex Queries
-- ============================================

-- CTE (Common Table Expression)
WITH monthly_posts AS (
    SELECT
        DATE_TRUNC('month', published_at) AS month,
        COUNT(*) AS post_count,
        SUM(view_count) AS total_views
    FROM posts
    WHERE status = 'published'
    GROUP BY DATE_TRUNC('month', published_at)
),
ranked_months AS (
    SELECT
        month,
        post_count,
        total_views,
        ROW_NUMBER() OVER (ORDER BY total_views DESC) AS rank
    FROM monthly_posts
)
SELECT * FROM ranked_months WHERE rank <= 12;

-- Recursive CTE
WITH RECURSIVE category_tree AS (
    -- Base case
    SELECT id, name, parent_id, 1 AS level, ARRAY[id] AS path
    FROM categories
    WHERE parent_id IS NULL

    UNION ALL

    -- Recursive case
    SELECT c.id, c.name, c.parent_id, ct.level + 1, ct.path || c.id
    FROM categories c
    INNER JOIN category_tree ct ON c.parent_id = ct.id
    WHERE NOT c.id = ANY(ct.path)  -- Prevent cycles
)
SELECT * FROM category_tree ORDER BY path;

-- Window functions
SELECT
    user_id,
    title,
    view_count,
    SUM(view_count) OVER (PARTITION BY user_id ORDER BY published_at) AS running_total,
    AVG(view_count) OVER (PARTITION BY user_id) AS avg_views,
    RANK() OVER (PARTITION BY user_id ORDER BY view_count DESC) AS view_rank,
    LAG(view_count) OVER (PARTITION BY user_id ORDER BY published_at) AS prev_views,
    LEAD(view_count) OVER (PARTITION BY user_id ORDER BY published_at) AS next_views
FROM posts
WHERE status = 'published';

-- CASE expression
SELECT
    username,
    CASE status
        WHEN 'active' THEN 'Active User'
        WHEN 'pending' THEN 'Awaiting Verification'
        WHEN 'inactive' THEN 'Inactive'
        ELSE 'Unknown'
    END AS status_label,
    CASE
        WHEN created_at > CURRENT_TIMESTAMP - INTERVAL '30 days' THEN 'New'
        WHEN created_at > CURRENT_TIMESTAMP - INTERVAL '1 year' THEN 'Regular'
        ELSE 'Veteran'
    END AS user_type
FROM users;

-- Lateral join
SELECT u.username, p.*
FROM users u
CROSS JOIN LATERAL (
    SELECT title, view_count
    FROM posts
    WHERE user_id = u.id
    ORDER BY view_count DESC
    LIMIT 3
) p;

-- JSON operations
SELECT
    id,
    username,
    metadata->>'theme' AS theme,
    metadata->'notifications'->>'email' AS email_notifications,
    jsonb_array_length(metadata->'interests') AS interest_count
FROM users
WHERE metadata @> '{"premium": true}';

-- ============================================
-- Transactions
-- ============================================

BEGIN;

SAVEPOINT before_insert;

INSERT INTO posts (user_id, title, slug, content, status)
VALUES (1, 'New Post', 'new-post', 'Content here', 'draft');

-- Rollback to savepoint if needed
-- ROLLBACK TO SAVEPOINT before_insert;

COMMIT;

-- ============================================
-- Permissions
-- ============================================

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON users TO app_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA app TO admin_user;

-- Revoke permissions
REVOKE DELETE ON users FROM app_user;
