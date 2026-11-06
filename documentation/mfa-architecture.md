# MFA Architecture

Standard TOTP (RFC 6238): SHA1, 6 digits, 30 seconds. It works with Google Authenticator, Microsoft
Authenticator, Authy, 1Password and any compliant app, and contacts no external service. QR codes
are generated locally.

## Authenticator title

`MFA_TITLE` alone sets the issuer. The entry appears as `<MFA_TITLE>:<USER_EMAIL>`. Changing it
affects newly generated provisioning data only; entries already in authenticator apps keep their
old name. Admin and Client each have their own `MFA_TITLE`.

## Secret storage

- AES-256-GCM, format `v1.<key_id>.<nonce>.<ciphertext>`.
- Associated data is `<domain>:<user_id>`, so a ciphertext copied to another account or domain
  fails to decrypt.
- The backend refuses to start if `MFA_ENCRYPTION_KEY` is missing or isn't a 32-byte urlsafe-base64
  value. Each domain has its own key. The Admin backend never holds the Client key: resetting
  Client MFA only clears data.

### Rotating the key

1. Move the old key to `MFA_ENCRYPTION_PREVIOUS_KEYS` as `old_id:old_key`.
2. Set the new `MFA_ENCRYPTION_KEY` and `MFA_ENCRYPTION_KEY_ID`, then restart.
3. Run `uv run python -m app.cli.rotate_mfa_key`.
4. Remove the old key.

## Enrollment

1. `POST /auth/mfa/setup` (with current password) stores an encrypted pending secret and returns the
   QR code, URI and manual secret. **MFA stays disabled.**
2. `POST /auth/mfa/confirm` verifies a first code, enables MFA, returns 10 recovery codes (once), and
   revokes other sessions. The secret can never be read again.

## Login challenge

After a correct password on an MFA account, the backend returns a challenge token and no session.
The challenge:

- Expires after 5 minutes (`MFA_CHALLENGE_EXPIRE_SECONDS`).
- Is single-use and allows 5 attempts (`MFA_CHALLENGE_MAX_ATTEMPTS`).
- Is only accepted by `POST /auth/mfa/verify-login`; it is rejected by every protected API.

Failed attempts also count toward the account lockout, so an attacker who knows the password can't
keep guessing with fresh challenges.

## Replay protection

`users.mfa_last_used_step` is updated atomically and only moves forward, so a code works once even
while it is still inside the ±1 step clock-skew window.

## Recovery codes

Ten single-use codes (`ABCD-1234`, 40 bits of secure randomness), shown once and stored as Argon2id
hashes. Regenerating needs a current TOTP code and replaces all old codes. Attempts are limited by
the same challenge and lockout rules.

## Disable and reset

- **Disable (self):** needs current password and TOTP code. Clears the secret and recovery codes,
  revokes other sessions, and audits `MFA_DISABLED`.
- **Reset (by an authorized Admin):** `admins.mfa.reset`. Clears everything, sets
  `mfa_enrollment_required`, revokes all the target's sessions, and audits `MFA_RESET`. Only a Super
  Admin can reset a Super Admin.

## Enforcement

`ADMIN_MFA_REQUIRED` and `CLIENT_MFA_REQUIRED` are independent. When on, or after a reset, an
unenrolled user gets a session limited to enrollment. The check runs on every request, so turning
the setting on also restricts existing sessions.
