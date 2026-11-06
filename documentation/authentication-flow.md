# Authentication Flow

Admin and Client implement this flow independently, with separate tables, cookies and keys.

## Credentials

| Credential | Lifetime | Where the browser keeps it | Server storage |
|---|---|---|---|
| Access token (opaque, 256-bit) | 15 minutes | JavaScript memory only | SHA-256 digest in `sessions` |
| Refresh token (opaque, 256-bit) | Rotated on each use, bounded by the session | `HttpOnly`, `SameSite=Strict` cookie | SHA-256 digest in `refresh_tokens` |
| Session | 7 days | n/a | `sessions` row |

Opaque tokens are used instead of JWTs because each request loads the session and the account from
the database anyway. Deactivation or revocation therefore takes effect on the next request.

## Login

1. `POST /api/v1/auth/login` with `identifier` (email or username) and `password`.
2. Rate limits apply per IP and per identifier.
3. Unknown account, wrong password, locked account and inactive account all return the same `401`.
4. The response `status` is one of:
   - `authenticated`: full session.
   - `mfa_required`: a challenge token only, with no session (see `mfa-architecture.md`).
   - `mfa_enrollment_required`: a session restricted to MFA enrollment.

An outdated Argon2id hash is upgraded automatically after a successful password check.

## Refresh token rotation

Each `POST /api/v1/auth/refresh` marks the presented token as used and issues a new access and
refresh token.

- **Reuse within the grace period (10 seconds):** returns `409 refresh_in_progress` and issues
  nothing. This covers two browser tabs refreshing at the same moment.
- **Reuse after the grace period:** treated as theft. The session is revoked and
  `REFRESH_TOKEN_REUSE` is audited.
- The previous access token stays valid until its own expiry, so other tabs keep working.

## CSRF

The access token travels in the `Authorization` header, which browsers never attach automatically.
Cookie-using endpoints (`login`, `refresh`, `logout`, `mfa/verify-login`) require all of:
`SameSite=Strict`, an `Origin` in the allowlist, and an `X-Requested-With` header.

## Restricted access

`get_restricted_principal` accepts any valid session and is used only for `/me`, logout, password
change and MFA enrollment. `get_current_principal` is the default for everything else and rejects:

- `403 mfa_enrollment_required` until a required enrollment is finished.
- `403 password_change_required` while a temporary password is in use.

## Password change and reset

- **Change:** needs the current password, then revokes all other sessions.
- **Self-service reset:** `request` always answers `202`, so it cannot reveal accounts. It creates
  a token only when a `PasswordResetDelivery` is configured. No email provider is included, so this
  is off by default.
- **Administrator reset:** issues a one-time temporary password and sets `must_change_password`.

## First Super Admin

```bash
uv run python -m app.cli.create_superadmin                      # first one
uv run python -m app.cli.create_superadmin --additional         # another one
uv run python -m app.cli.set_superadmin --email a@b.c --revoke  # grant or revoke
```

No API can create a Super Admin or change `is_superuser`.
