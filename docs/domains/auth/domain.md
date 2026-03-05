# Domain: Auth

**Slug**: auth
**Type**: infrastructure
**Created**: 2026-03-05
**Created By**: plan-028-server-mode (new domain)
**Status**: planned

## Purpose

API key management and request authentication. This domain ensures that every API request carries a valid API key. The auth model is "valid key = full access to all graphs" — there is no Row-Level Security or per-tenant data isolation. API keys authenticate requests and may be scoped to read-only or read-write.

## Concepts

| Concept | Entry Point | What It Does |
|---------|-------------|-------------|
| Authenticate API requests | Auth middleware | Extract Bearer token → validate API key |
| Manage API keys | AuthService | Generate, validate, scope, rotate, revoke keys |
| Manage tenants | AuthService | Create tenants, assign quotas (organizational grouping) |

## Boundary

### Owns
- Tenant CRUD (create, read, update, deactivate) — organizational grouping only
- API key generation, validation, scoping (read-only vs read-write)
- API key rotation and revocation
- FastAPI middleware for API key validation
- FakeAuthService test double

### Does NOT Own
- Row-Level Security (not used — valid key = full access)
- HTTP routing (belongs to server domain)
- Dashboard login UI (belongs to server domain, consumes auth service)
- Per-graph permissions within a tenant (future scope)
- User profile management
- SSO provider configuration

## Contracts (Public Interface)

| Contract | Type | Consumers | Description |
|----------|------|-----------|-------------|
| AuthService | Service | Server routes, dashboard | Key validation, tenant resolution |
| Auth middleware | FastAPI Middleware | Server app | Per-request API key validation |
| Tenant model | Pydantic Model | Server, dashboard | Tenant data structure |
| APIKey model | Pydantic Model | Server, dashboard | Key data structure |
| FakeAuthService | Test Double | All tests | Controllable auth for testing |

## Dependencies

### This Domain Depends On
- **configuration** — Auth-related config (if needed)

### Domains That Depend On This
- **server** — All routes use auth middleware for request validation

## Source Location

Primary: `src/fs2/auth/` (to be created in Phase 2)

## History

| Plan | What Changed | Date |
|------|-------------|------|
| 028-server-mode | Domain created | 2026-03-05 |
| 028-server-mode (Phase 1 DYK) | Removed RLS — auth model is "valid API key = full access" | 2026-03-05 |
