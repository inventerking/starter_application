# API Contracts

Each backend serves its own API under `/api/v1`. Interactive documentation is at `/docs` in
development and test only.

| Application | Base URL |
|---|---|
| Admin | `http://localhost:8000/api/v1` |
| Client | `http://localhost:8001/api/v1` |

## Conventions

**Errors** always have this shape, and never include internal details:

```json
{ "error": { "code": "permission_denied", "message": "...", "details": [] } }
```

| Status | Meaning |
|---|---|
| 400 | Invalid MFA code or reset token |
| 401 | Not authenticated. Only code `authentication_required` means a refresh may help. |
| 403 | Authenticated but not allowed, or `csrf_rejected`, `mfa_enrollment_required`, `password_change_required` |
| 404 | Not found |
| 409 | Conflict, such as a duplicate identity or `refresh_in_progress` |
| 422 | Validation failed. `details` lists fields and messages, never submitted values. |
| 429 | Rate limited, with a `Retry-After` header |
| 503 | Readiness check failed |

**Pagination:** `?page=1&page_size=20` (maximum 100) returns `{ items, total, page, page_size }`.

**Browser requests** that use the refresh cookie (`login`, `refresh`, `logout`, `mfa/verify-login`,
`register`) need an allowed `Origin` and an `X-Requested-With` header.

**Authentication** is `Authorization: Bearer <access_token>`.

## Endpoints in both backends

| Method and path | Access | Purpose |
|---|---|---|
| `GET /health`, `GET /health/ready` | Public | Liveness and database readiness |
| `POST /auth/login` | Public | Returns `status`: `authenticated`, `mfa_required` or `mfa_enrollment_required` |
| `POST /auth/refresh` | Cookie | Rotates credentials |
| `POST /auth/logout` | Cookie or bearer | Revokes the session |
| `GET /auth/me` | Any session | Current account and effective permissions |
| `POST /auth/password/change` | Any session | Needs the current password |
| `POST /auth/password/reset/request` | Public | Always `202` |
| `POST /auth/password/reset/confirm` | Public | Needs a valid reset token |
| `GET /auth/sessions` | Full session | Active sessions |
| `DELETE /auth/sessions/{id}` | Full session | Revoke one of your sessions |
| `POST /auth/sessions/revoke-others` | Full session | Revoke all your other sessions |
| `GET /auth/mfa/status` | Any session | Enabled state and remaining recovery codes |
| `POST /auth/mfa/setup` | Any session | Needs the password. Returns the secret, URI and QR code. |
| `POST /auth/mfa/confirm` | Any session | First code. Enables MFA and returns recovery codes. |
| `POST /auth/mfa/verify-login` | Challenge token | `code` or `recovery_code` |
| `POST /auth/mfa/disable` | Full session | Needs password and code |
| `POST /auth/mfa/recovery-codes/regenerate` | Full session | Needs a code |

"Any session" includes sessions restricted by required MFA enrollment or a forced password change.

## Admin backend only

| Path | Permission |
|---|---|
| `/users/**` | See [user-management.md](user-management.md) |
| `/admins/**` | See [admin-management.md](admin-management.md) |
| `GET`, `POST /admin-roles`, `GET`, `PATCH`, `DELETE /admin-roles/{id}`, `PUT /admin-roles/{id}/permissions` | `admin_roles.*` |
| `GET`, `POST /client-roles`, `GET`, `PATCH`, `DELETE /client-roles/{id}`, `PUT /client-roles/{id}/permissions` | `client_roles.*` |
| `GET /admin-permissions` | `admin_permissions.view` |
| `GET /client-permissions` | `client_permissions.view` |
| `GET /audit-logs` (`action`, `involving` filters) | `audit.view` |
| `GET /dashboard/summary` | Full session. Sections the caller may not see are `null`. |

## Client backend only

| Method and path | Access |
|---|---|
| `POST /auth/register` | Public, but `403` unless `REGISTRATION_ENABLED=true` |
| `GET /users/me` | `profile.view` |
| `PATCH /users/me` | `profile.update` |
| `GET /users/me/activity` | `activity.view` |
| `GET /roles/me`, `GET /permissions/me` | Full session |

Administering Client users and roles belongs to the Admin backend, so the Client API has no
management endpoints.
