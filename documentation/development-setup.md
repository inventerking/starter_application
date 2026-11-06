# Development Setup

## Prerequisites

- [uv](https://docs.astral.sh/uv/) for Python, Node.js 24 with npm for the frontends.
- The existing PostgreSQL server with the `starter_app` database. The project never creates a
  database or a container, and does not use Docker.

## Backend setup (repeat in `admin/backend` and `client/backend`)

```bash
cp .env.example .env     # then set DATABASE_PASSWORD and MFA_ENCRYPTION_KEY
uv sync
uv run alembic upgrade head
```

Generate an MFA key, using **a different key for each backend**:

```bash
python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

## Running

```bash
# admin/backend
uv run uvicorn app.main:app --reload --port 8000
# client/backend
uv run uvicorn app.main:app --reload --port 8001
```

## Tests and lint

```bash
uv run pytest
uv run ruff check .
```

Tests need the PostgreSQL server. They create uniquely named `test_*` schemas inside `starter_app`
and drop them afterwards, so they never touch `admin` or `client` data.
