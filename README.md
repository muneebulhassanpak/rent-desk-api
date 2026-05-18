# RentDesk API

Property management backend for small landlords managing 5–50 units. Multi-tenant SaaS with four roles: **landlord**, **manager**, **tenant**, **vendor**.

## Tech Stack

| Layer | Tech |
|-------|------|
| Framework | FastAPI + Pydantic v2 |
| Database | Neon Postgres + SQLAlchemy 2.0 async |
| Migrations | Alembic |
| Auth | JWT (access + refresh) via httpOnly cookies |
| Cache | Upstash Redis |
| Storage | Cloudflare R2 (S3-compatible) |
| Payments | Stripe |
| Email | Resend |
| Lint | Ruff (check + format) |
| Tests | pytest + httpx (async) |

## Architecture

```
Endpoints → Services → Repositories → Models
```

Clean layered architecture. Endpoints handle HTTP, services own business logic, repositories own all database queries. No SQLAlchemy in endpoints, no HTTP concerns in services.

## Security

- **httpOnly cookies** — JWT tokens set as `Secure`, `SameSite=Lax`, `httpOnly` cookies. Fallback to `Authorization` header for API/mobile clients.
- **Rotating refresh tokens** — single-use, revoked on rotation. Password reset revokes all sessions.
- **Multi-tenancy isolation** — every query scoped by `org_id` from JWT claims. Never trusts client-supplied org_id.
- **RBAC** — role-based access via `require_role()` dependency. Manager scoping limits access to assigned properties only.
- **Input sanitization** — `SanitizedStr` Pydantic type strips HTML tags from all free-text fields (XSS prevention).
- **No raw SQL** — all queries via SQLAlchemy ORM, parameterized by default.
- **Security headers** — custom middleware for HSTS, X-Content-Type-Options, X-Frame-Options.
- **Anti-enumeration** — magic link and forgot-password always return success regardless of email existence.

## Conventions

- **Conventional commits** — enforced via git hooks (`feat`, `fix`, `chore`, etc.)
- **Pre-commit hooks** — Ruff fix + format on every commit
- **Pre-push hooks** — block direct pushes to main
- **Ship-it pipeline** — lint → validate commits → merge (no-ff) → validate imports → push
- **Async everywhere** — async engine, async sessions, async endpoints
- **Pydantic v2** — strict schemas with `ConfigDict(from_attributes=True)` for ORM ↔ schema conversion

## Quick Start

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your credentials

# Migrations
alembic upgrade head

# Run
uvicorn app.main:app --reload --port 8000

# Test
pytest

# Lint
ruff check app/ && ruff format app/
```

## API Overview

| Module | Endpoints | Status |
|--------|-----------|--------|
| Auth (login, register, JWT, magic link, password reset) | 9 | Done |
| Properties + Units CRUD | 12 | Done |
| Tenants + Leases (full lifecycle) | 12 | Done |
| Rent Payments | 9 | Planned |
| Maintenance Tickets | 12 | Planned |
| Dashboards | 5 | Planned |
| Documents + Notifications + Settings | 19 | Planned |
| Reports + Billing + Audit | 11 | Planned |
| **Total** | **89** | |

## License

Proprietary. All rights reserved.
