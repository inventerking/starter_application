"""Standard TOTP (RFC 6238): SHA1, 6 digits, 30 seconds. No dependency on any external service."""

import hashlib
import hmac
import re
import time

import pyotp
import segno

_DIGITS = 6
_PERIOD = 30
_CODE = re.compile(r"^\d{6}$")


def generate_secret() -> str:
    return pyotp.random_base32()  # 160 bits from a cryptographically secure source


def _totp(secret: str) -> pyotp.TOTP:
    return pyotp.TOTP(secret, digits=_DIGITS, digest=hashlib.sha1, interval=_PERIOD)  # noqa: S324


def provisioning_uri(secret: str, account: str, title: str) -> str:
    """Authenticator apps display this as ``<title>:<account>``."""
    return _totp(secret).provisioning_uri(name=account, issuer_name=title)


def qr_code_data_uri(uri: str) -> str:
    """Generated locally: the QR code contains the secret, so it must not go to a QR service."""
    return segno.make(uri, error="m").svg_data_uri(scale=6, border=2)


def matching_step(secret: str, code: str, window: int, now: float | None = None) -> int | None:
    """Return the time-step the code belongs to, allowing for clock skew, or None."""
    if not _CODE.match(code):
        return None
    now = time.time() if now is None else now
    totp = _totp(secret)
    current = int(now) // _PERIOD
    for step in range(current - window, current + window + 1):
        if hmac.compare_digest(totp.at(step * _PERIOD), code):
            return step
    return None
