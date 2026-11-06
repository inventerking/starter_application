# Authorization Model

RBAC plus direct per-user overrides, implemented independently in each domain and always enforced by
the backend. Frontend checks only decide what to show.

```text
User ─┬─ Roles ── Permissions
      └─ Direct permissions (ALLOW or DENY)
```

## Permission registry

Modules declare permissions in code through `registry.register(resource, action, description)`.
`require_permission` accepts only the resulting definition object and raises `TypeError` for a
string, so a typo can't become a silent check.

`uv run python -m app.cli.sync_permissions` copies the registry to the database. Run it after every
deployment. A definition that leaves the registry is marked `deprecated_at`, never deleted, and is
never effective.

## Admin permissions

| Area | Codes |
|---|---|
| User Management | `users.view`, `.create`, `.update`, `.delete`, `.activate`, `.deactivate`, `users.roles.manage`, `users.permissions.manage`, `users.mfa.view_status`, `users.mfa.reset`, `users.password.reset`, `users.sessions.revoke`, `users.activity.view` |
| Admin Management | `admins.view`, `.create`, `.update`, `.delete`, `.activate`, `.deactivate`, `admins.roles.manage`, `admins.permissions.manage`, `admins.mfa.view_status`, `admins.mfa.reset`, `admins.password.reset`, `admins.sessions.revoke`, `admins.activity.view` |
| Admin roles | `admin_roles.view`, `.create`, `.update`, `.delete` |
| Client roles | `client_roles.view`, `.create`, `.update`, `.delete` |
| Permission registries | `admin_permissions.view`, `client_permissions.view` |
| Audit | `audit.view` |

An Admin account grants nothing by itself. A new account can sign in and manage its own security,
and nothing more until it receives roles or permissions.

The spec's generic `roles.*` and `permissions.view` were split per domain, because Admin and Client
roles are entirely separate systems.

## Rules beyond precedence (Admin domain)

| Rule | Behavior |
|---|---|
| No escalation | A non-Super Admin can't assign a role or override, or give a role a permission, unless they hold that access themselves. |
| No self-service access changes | A non-Super Admin can't change their own roles or overrides. |
| No takeover | A non-Super Admin can't change, reset or deactivate an account that has access they lack. |
| Role limits | A non-Super Admin can't edit or delete a role stronger than themselves, or a system role. |
| Super Admin | `is_superuser` can only change through the CLI. No API can delete a Super Admin. Only another Super Admin can deactivate, update or reset one. |
| Self and last | Nobody can deactivate or delete themselves, or deactivate the last active Super Admin. |

Client role assignment and Client overrides follow only `users.roles.manage` and
`users.permissions.manage`. The escalation rule doesn't apply there, since Client permissions give
the acting Admin nothing.
