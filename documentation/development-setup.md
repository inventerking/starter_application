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
uv run python -m app.cli.sync_permissions
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

## First Super Admin (Admin backend)

```bash
uv run python -m app.cli.create_superadmin    # prompts for email, username and password
```

## Frontends (repeat in `admin/frontend` and `client/frontend`)

```bash
cp .env.example .env
npm install
npm run dev      # Admin on 5173, Client on 5174
npm run build    # type-checks and builds
npm run lint
```

## Tests and lint

```bash
uv run pytest
uv run ruff check .
```

Tests need the PostgreSQL server. They create uniquely named `test_*` schemas inside `starter_app`
and drop them afterwards, so they never touch `admin` or `client` data.

## Operations

| Command (run in the backend's folder) | Purpose |
|---|---|
| `uv run python -m app.cli.sync_permissions` | Sync the permission registry. Run after every deployment. |
| `uv run python -m app.cli.cleanup_expired` | Delete expired authentication records. Schedule daily. |
| `uv run python -m app.cli.rotate_mfa_key` | Re-encrypt MFA secrets after changing the key |
| `uv run python -m app.cli.create_superadmin` | Admin only: create a Super Admin |
| `uv run python -m app.cli.set_superadmin` | Admin only: grant or revoke Super Admin status |
| `uv run python -m app.cli.recover_admin` | Admin only: break-glass MFA or password recovery |

Set `COOKIE_SECURE=false` only for `http://localhost`. Browsers reject secure cookies over plain HTTP,
and sign-in appears to work until the first refresh.
