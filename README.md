# 🏠 RentDesk API

> Property management backend for small landlords managing 5–50 units.
> Multi-tenant SaaS with four roles: **landlord** · **manager** · **tenant** · **vendor**

---

## ⚡ Tech Stack

| Layer | Tech |
|-------|------|
| 🧩 Framework | FastAPI + Pydantic v2 |
| 🗄️ Database | Neon Postgres + SQLAlchemy 2.0 async |
| 📦 Migrations | Alembic |
| 🔐 Auth | JWT via httpOnly cookies (access + refresh) |
| 💾 Cache | Upstash Redis |
| ☁️ Storage | Cloudflare R2 (S3-compatible) |
| 💳 Payments | Stripe |
| 📧 Email | Resend |
| 🧹 Lint | Ruff (check + format) |
| 🧪 Tests | pytest + httpx (async) |

---

## 🏗️ Architecture

```
Endpoints → Services → Repositories → Models
```

Clean layered architecture. Endpoints handle HTTP, services own business logic, repositories own all database queries. No SQLAlchemy in endpoints, no HTTP concerns in services.

---

## 🔒 Security

| | Feature | Detail |
|---|---------|--------|
| 🍪 | **httpOnly cookies** | `Secure`, `SameSite=Lax`, `httpOnly`. Fallback to `Authorization` header for API/mobile. |
| 🔄 | **Rotating refresh tokens** | Single-use, revoked on rotation. Password reset kills all sessions. |
| 🏢 | **Multi-tenancy isolation** | Every query scoped by `org_id` from JWT. Never trusts client-supplied org_id. |
| 🛡️ | **RBAC** | `require_role()` dependency. Managers scoped to assigned properties only. |
| 🧼 | **Input sanitization** | `SanitizedStr` Pydantic type strips HTML from all free-text fields. |
| 🚫 | **No raw SQL** | All queries via SQLAlchemy ORM, parameterized by default. |
| 📋 | **Security headers** | HSTS, X-Content-Type-Options, X-Frame-Options via middleware. |
| 🕵️ | **Anti-enumeration** | Magic link & forgot-password always return success. |

---

## 📐 Conventions

- 📝 **Conventional commits** — enforced via git hooks (`feat`, `fix`, `chore`, etc.)
- 🧹 **Pre-commit** — Ruff fix + format on every commit
- 🚧 **Pre-push** — blocks direct pushes to main
- 🚀 **Ship-it pipeline** — lint → validate commits → merge (no-ff) → validate imports → push
- ⚡ **Async everywhere** — async engine, async sessions, async endpoints
- 📋 **Pydantic v2** — strict schemas with `from_attributes=True` for ORM ↔ schema conversion

---

## 🚀 Quick Start

```bash
# 📦 Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your credentials

# 🗄️ Migrations
alembic upgrade head

# ▶️ Run
uvicorn app.main:app --reload --port 8000

# 🧪 Test
pytest

# 🧹 Lint
ruff check app/ && ruff format app/
```

---

## 📡 API Overview

| Module | Endpoints | Status |
|--------|-----------|--------|
| 🔐 Auth (login, register, JWT, magic link, password reset) | 9 | ✅ Done |
| 🏘️ Properties + Units CRUD | 12 | ✅ Done |
| 👥 Tenants + Leases (full lifecycle) | 12 | ✅ Done |
| 💰 Rent Payments | 9 | 🔜 Planned |
| 🔧 Maintenance Tickets | 12 | 🔜 Planned |
| 📊 Dashboards | 5 | 🔜 Planned |
| 📄 Documents + Notifications + Settings | 19 | 🔜 Planned |
| 📈 Reports + Billing + Audit | 11 | 🔜 Planned |
| | **89 total** | |

---

## 📄 License

Proprietary. All rights reserved.
