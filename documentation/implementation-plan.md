# Implementation Plan and Status

All phases below are implemented. "Verified" means covered by the automated tests or the browser run
described at the end.

| Phase | Scope | Status |
|---|---|---|
| 0 | Repository analysis and plan | Done |
| 1 | Foundation: uv projects, FastAPI, settings, logging, health, tests | Done |
| 2 | Database isolation: both schemas, separate metadata and migrations | Done |
| 3 | Security foundation: Argon2id, encryption, rate limits, CSRF, audit | Done |
| 4 | Admin authentication and Super Admin CLI | Done |
| 5 | Admin MFA | Done |
| 6 | Admin authorization and roles | Done |
| 7 | Admin Management | Done |
| 8 | User Management and Client roles through the Admin backend | Done |
| 9 | Admin frontend | Done |
| 10 | Client authentication, MFA and authorization | Done |
| 11 | Client frontend | Done |
| 12 | Hardening, sweep tests, documentation | Done |

## Deviations from the original specification

| Change | Reason |
|---|---|
| Client tables created in Phase 2, not Phase 10 | Phase 8 needs them |
| Added `refresh_tokens`, `mfa_challenges`, `password_reset_tokens`, `rate_limit_counters` per schema | Approved. Needed for reuse detection, single-use challenges, reset tokens and rate limits. |
| `roles.*` and `permissions.view` split into `admin_roles.*`, `client_roles.*`, `admin_permissions.view`, `client_permissions.view` | Approved. The two role systems are entirely separate. |
| Added `users.mfa.*`, `users.password.reset`, `users.sessions.revoke`, `users.activity.view`, `admins.password.reset`, `admins.sessions.revoke`, `admins.activity.view`, `audit.view` | Each new operation needs its own permission. |
| `users.mfa_enrollment_required` column | A reset must force re-enrollment even when MFA isn't globally mandatory. |
| Opaque access tokens instead of JWTs | The database is checked on each request anyway. |
| Tests use throwaway schemas | Rule: no additional database. |
| `tests/` beside `app/`, and `modules/client_domain` as its own module | Keeps tests out of the deployed package; shared by `users` and `client_roles`. |
| Client audit records hold no Admin identity | Approved principle: neither domain keeps the other's data. |
| Added `recover_admin`, `cleanup_expired`, `set_superadmin`, `rotate_mfa_key`, `sync_permissions` CLIs | Lockout recovery, table growth, and operations with no API by design. |

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| 1 | Admin and Client run independently | Separate uv projects and apps; the Client backend imports nothing from Admin |
| 2 | Both connect to the existing PostgreSQL | Both migrated into `starter_app` |
| 3 | Separate schemas | `admin`, `client`; `test_migrations.py` |
| 4-7 | Independent authentication, users, roles, permissions, MFA | Browser run; `test_hardening.py`; `test_user_management.py` |
| 8 | Argon2id everywhere | `test_security_foundation.py`, and creation paths in each management test |
| 9 | Google Authenticator-compatible TOTP | Standard `otpauth://` URI and RFC 6238 parameters, verified with codes from an independent library (pyotp). **Not yet scanned with a physical authenticator app.** |
| 10 | `MFA_TITLE` controls the issuer | `test_mfa.py`; browser run |
| 11 | Secrets encrypted at rest | `test_mfa.py` |
| 12 | Recovery codes | `test_mfa.py` |
| 13-14 | Super Admin through CLI, no public registration | `test_authentication.py`; CLI run through a pseudo-terminal |
| 15-16 | Super Admin manages both | `test_admin_management.py`, `test_user_management.py`; browser run |
| 17-18 | Separate sections, independent permissions | `TestManagementSeparation`; browser run |
| 19-20 | Roles and direct overrides | `test_authorization.py`; browser run |
| 21 | Backend authorization on every protected operation | `TestRouteSweep` |
| 22 | Audit logging | Asserted throughout the management tests |
| 23 | Independent migrations | `test_migrations.py` |
| 24 | Automated security tests pass | `uv run pytest` in each backend |
| 25 | Documentation matches the implementation | This folder |

## Browser verification

Both applications were run together in Chrome against throwaway schemas. The run covered sign-in, MFA
with real codes, forced password change, permission-limited navigation, role and override changes
taking effect across applications, immediate deactivation, and cross-domain rejection of credentials,
tokens and cookies. These scripts are not part of the repository, because they would add Playwright
as a dependency. The frontends have no automated tests of their own.
