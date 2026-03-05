# Domain: Auth

**Slug**: auth
**Type**: infrastructure
**Created**: 2026-03-05
**Created By**: plan-028-server-mode (new domain)
**Status**: planned

## Purpose

Tenant and API key management, request authentication, and data isolation enforcement. This domain ensures that every API request is authenticated, scoped to a tenant, and that PostgreSQL Row-Level Security prevents any cross-tenant data access — even if application code has bugs.

## Concepts

| Concept | Entry Point | What It Does |
|---------|-------------|-------------|
| Authenticate API requests | Auth middleware | Extract Bearer token → validate → resolve tenant |
| Enforce tenant isolation | RLS middleware | SET app.current_tenant_id per request transaction |
| Manage API keys | AuthService | Generate, validate, scope, rotate, revoke keys |
| Manage tenants | AuthService | Create tenants, assign quotas |

## Boundary

### Owns
- Tenant CRUD (create, read, update, deactivate)
- API key generation, validation, scoping (read-only vs read-write)
- API key rotation and revocation
- FastAPI middleware for auth + RLS context injection
- RLS policy definitions on all data tables
- Request-scoped tenant context lifecycle
- FakeAuthService test double

### Does NOT Own
- HTTP routing (belongs to server domain)
- Dashboard login UI (belongs to server domain, consumes auth service)
- Per-graph permissions within a tenant (future scope)
- User profile management
- SSO provider configuration

## Contracts (Public Interface)

| Contract | Type | Consumers | Description |
|----------|------|-----------|-------------|
| AuthService | Service | Server routes, dashboard | Key validation, tenant resolution |
| Auth middleware | FastAPI Middleware | Server app | Per-request auth + RLS context |
| Tenant model | Pydantic Model | Server, dashboard | Tenant data structure |
| APIKey model | Pydantic Model | Server, dashboard | Key data structure |
| FakeAuthService | Test Double | All tests | Controllable auth for testing |

## Dependencies

### This Domain Depends On
- **configuration** — Auth-related config (if needed)

### Domains That Depend On This
- **server** — All routes use auth middleware for tenant context

## Source Location

Primary: `src/fs2/auth/` (to be created in Phase 2)

## History

| Plan | What Changed | Date |
|------|-------------|------|
| 028-server-mode | Domain created | 2026-03-05 |
