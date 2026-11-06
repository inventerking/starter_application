# Starter Application

A reusable, secure foundation for new software projects: two independently runnable applications
(Admin and Client) with independent security domains, sharing one PostgreSQL database through
strict schema isolation.

| Application | Frontend | Backend | API docs (development) | Schema |
|---|---|---|---|---|
| Admin | http://localhost:5173 | http://localhost:8000 | http://localhost:8000/docs | `admin` |
| Client | http://localhost:5174 | http://localhost:8001 | http://localhost:8001/docs | `client` |

Start with [documentation/development-setup.md](documentation/development-setup.md).
Architecture and security decisions are in [documentation/](documentation/).

## Quick start

```bash
# In client/backend first, then admin/backend:
cp .env.example .env     # set DATABASE_PASSWORD and a unique MFA_ENCRYPTION_KEY
uv sync
uv run alembic upgrade head
uv run python -m app.cli.sync_permissions

# In admin/backend, create the first Super Admin:
uv run python -m app.cli.create_superadmin

# Start each backend, then each frontend (cp .env.example .env; npm install; npm run dev):
uv run uvicorn app.main:app --reload --port 8000   # admin/backend
uv run uvicorn app.main:app --reload --port 8001   # client/backend
```

Run the tests with `uv run pytest` in each backend.
