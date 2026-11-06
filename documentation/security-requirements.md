# Security Requirements

How each requirement is met, and where it is tested. Test paths are relative to each backend.

| Area | Implementation | Tests |
|---|---|---|
| Password hashing | Argon2id with a random salt and configurable cost. Hashes upgrade at login. | `test_security_foundation.py`, `test_authentication.py` |
| Password policy | 12-128 characters, must not contain the email or username | `test_security_foundation.py` |
| Account enumeration | Identical `401`s, dummy hash verification, reset always `202` | `test_authentication.py` |
| Brute force | PostgreSQL rate limits per IP and identifier, account lockout, challenge attempt limits | `test_authentication.py`, `test_mfa.py` |
| Sessions | Opaque hashed tokens, checked against the database on every request | `test_authentication.py` |
| Refresh tokens | Rotation with reuse detection | `test_authentication.py` |
| CSRF | SameSite=Strict, Origin allowlist, required custom header | `test_authentication.py` |
| MFA secrets | AES-256-GCM bound to domain and user, key IDs, rotation CLI | `test_security_foundation.py`, `test_mfa.py` |
| TOTP replay | Atomic, forward-only time-step tracking | `test_mfa.py` |
| Recovery codes | Argon2id hashes, single use, replaced on regeneration | `test_mfa.py` |
| Authorization | One resolver, default deny, guards accept only registered definitions | `test_authorization.py`, `test_hardening.py` |
| Route coverage | Sweep test: every non-public route rejects anonymous callers | `test_hardening.py` |
| Privilege escalation | No granting beyond own access, no takeover of stronger accounts | `test_admin_management.py` (Admin) |
| Domain separation | Separate tables, keys and cookies; foreign keys reject crossed IDs; import-boundary tests | `test_user_management.py`, `test_hardening.py` (Admin), `test_authorization.py` (Client) |
| Migrations | Independent histories, schema filters, drift checks | `test_migrations.py` |
| Audit | Append-only trigger, sensitive-key filter, recorded in the same transaction | `test_migrations.py`, `test_security_foundation.py` |
| Safe errors | Generic messages. Validation errors omit submitted values. | `test_foundation.py` |
| Secrets in logs | `hide_parameters`, redaction filter, exception types only | `test_hardening.py`, `test_security_foundation.py` |
| Headers | CSP, `nosniff`, frame denial, `no-store` on the API, HSTS outside development | `test_foundation.py` |
| Configuration | Pydantic validation at startup. Production requires secure cookies and no wildcard CORS. | `test_foundation.py`, `test_mfa.py` |

## Before going to production

These depend on your deployment, so the project cannot enforce them:

1. **Use least-privilege database roles.** Local development uses the `postgres` superuser, so the
   database does not itself stop one backend reading the other's schema, and an operator with that
   login could disable the audit trigger. See [database-design.md](database-design.md).
2. **Set `ENVIRONMENT=production`.** This enables HSTS, requires secure cookies and hides `/docs`.
3. **Pass real client IPs through your proxy,** with uvicorn's `--proxy-headers` and
   `--forwarded-allow-ips`. Otherwise all traffic shares one per-IP rate limit.
4. **Serve frontends and APIs on the same site** (for example `admin.example.com` and
   `admin-api.example.com`), or the `SameSite=Strict` refresh cookie won't be sent.
5. **Add a Content-Security-Policy to the frontend's hosting.** The backend's CSP covers API
   responses only.
6. **Use a different `MFA_ENCRYPTION_KEY` in each backend,** kept in a secret manager.
7. **Schedule** `uv run python -m app.cli.cleanup_expired` daily in both backends.
8. **Run** `sync_permissions` in both backends on every deployment.
9. **Turn on `ADMIN_MFA_REQUIRED`** for production Admin accounts.

## Known trade-offs

- The per-identifier rate limit and account lockout let someone who knows a username temporarily
  block its sign-in. Lockout is short (15 minutes) to limit this.
- Recovery codes have 40 bits of entropy. Their Argon2id hashes plus attempt limits make that
  adequate, and the short format stays easy to type.
- Self-service password reset is off until you add a `PasswordResetDelivery` implementation.
- Audit logs are not tamper-proof against a database superuser.

## Break-glass recovery

If a sole Super Admin loses their authenticator or password, an operator with server access can run:

```bash
uv run python -m app.cli.recover_admin --email a@example.com --mfa --password
```

No API offers this, and each use is audited with a `system` actor.
