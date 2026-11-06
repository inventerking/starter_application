# Architecture

**Modular monolith, two independent applications, two independent security domains, one PostgreSQL
database with schema isolation.**

```text
Admin frontend :5173 -> Admin backend :8000 -> admin.*  (read/write)
                                            -> client.* (only via client_domain, for User Management)
Client frontend :5174 -> Client backend :8001 -> client.*
```

## Decisions

| Decision | Reasoning |
|---|---|
| No shared Python or frontend package | Either application can change or ship alone. Security code is intentionally duplicated. |
| The Admin backend accesses `client.*` directly and never calls the Client API | Specified by the control-plane design; neither backend needs the other running. |
| Synchronous SQLAlchemy with psycopg 3 | Route handlers run in a thread pool, so Argon2id hashing never blocks an event loop. |
| Schema name from configuration (`DATABASE_SCHEMA`) | Tests run real migrations in throwaway schemas without creating a database. |
| Business logic in services, explicit commits | Every multi-step sensitive operation is one transaction. |
| Admin never holds the Client MFA key | Resetting Client MFA only clears data, so a compromised Admin backend cannot read Client secrets. |
| Neither domain stores the other's details | The Client audit trail omits the Admin's identity. The Admin trail stores only the Client record's UUID. |

## Module contract

Backend modules use `models.py`, `schemas.py`, `repository.py`, `service.py`, `routes.py` and
`exceptions.py`, and only the files they need. Routes authorize and delegate, services hold rules and
own transactions, and repositories hold queries.

## Layout

```text
admin/backend/app/modules/
  authentication, mfa, audit      this domain's security
  permissions, roles              Admin RBAC
  admins                          Admin Management (admin.users only)
  users, client_roles             User Management (client.* only)
  client_domain                   the only mapping of client.* tables
  dashboard                       permission-aware summary

client/backend/app/modules/
  authentication, mfa, audit, permissions, roles, users
```

Tests enforce these boundaries (`tests/test_hardening.py`).
