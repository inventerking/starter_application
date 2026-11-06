# Database Design

One database (`starter_app`), two schemas (`admin`, `client`). The schemas have the same shape but
share nothing: no table, no foreign key and no record crosses the boundary.

## Tables (present in each schema)

| Table | Purpose |
|---|---|
| `users` | Accounts. `lower(email)` and `lower(username)` are unique among non-deleted rows. Holds the encrypted MFA secret and login-failure state. `admin.users` also has `is_superuser` and `created_by`. |
| `roles` | Role definitions. `is_system` protects a role from edits. `client.roles` also has `is_default`. |
| `permissions` | Registry-synchronized definitions (`resource`, `action`, `code`). `deprecated_at` marks removed definitions, which are never effective. |
| `user_roles`, `role_permissions` | RBAC relationships. |
| `user_permissions` | Direct overrides; `effect` is `ALLOW` or `DENY`. The primary key allows one effect per user and permission. |
| `sessions` | Hashed access tokens, scope (`full`, `mfa_enrollment`), expiry and revocation. |
| `refresh_tokens` | One row per issued token, which enables reuse detection. Hashed. |
| `mfa_challenges` | Short-lived, single-use, attempt-limited login challenges. Hashed. |
| `mfa_recovery_codes` | Argon2id hashes and `used_at`. |
| `password_reset_tokens` | Single-use reset tokens. Hashed. |
| `rate_limit_counters` | Fixed-window counters keyed by a SHA-256 digest. |
| `audit_logs` | Append-only (a trigger rejects UPDATE and DELETE). No foreign keys, so records outlive their subjects. |

## Data ownership between the domains

- The Client schema holds **no** Admin identifiers. When an administrator changes a Client user,
  `client.audit_logs` records the actor only as `administrator`, with a correlation ID.
- `admin.audit_logs` records who acted and the Client user's UUID as the target, with no copy of
  the Client user's details.
- The Admin backend writes to `client.*` only through `app/modules/client_domain` and its own
  separate SQLAlchemy `MetaData`, which Alembic ignores.

## Migrations

Each backend has its own Alembic environment and its own `alembic_version` table inside its schema.
`env.py` filters autogenerate by schema, so it cannot see or drop the other domain's tables.

```bash
uv run alembic upgrade head                        # apply
uv run alembic revision --autogenerate -m "..."    # create; replace literal schema names with SCHEMA
uv run alembic downgrade -1                        # roll back one revision
```

Run the Client migrations before using User Management in the Admin application.

## Isolation limits

The local development login is the `postgres` superuser, so the database itself does not stop one
backend from reading the other schema. Isolation is enforced by code structure and tests. For
production, give each backend its own least-privilege role:

- Client role: full DML on `client`, no access to `admin`.
- Admin role: full DML on `admin`, and DML on `client` only for the tables it manages.
- A separate migration role owning each schema's DDL.
