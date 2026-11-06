"""Authenticated encryption for secrets at rest (AES-256-GCM).

Stored format: ``v1.<key_id>.<nonce>.<ciphertext>``. The key ID lets old values stay readable
during rotation. Associated data binds a ciphertext to its owner, so it cannot be moved to another
account or domain.
"""

import base64
import binascii
import os
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings, decode_key, get_settings

_VERSION = "v1"


class DecryptionError(Exception):
    """A stored secret could not be decrypted. Carries no secret material."""


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class SecretCipher:
    def __init__(self, key_id: str, key: bytes, previous_keys: dict[str, bytes] | None = None):
        self.key_id = key_id
        self._keys = {**(previous_keys or {}), key_id: key}

    def encrypt(self, plaintext: str, associated_data: str) -> str:
        nonce = os.urandom(12)
        sealed = AESGCM(self._keys[self.key_id]).encrypt(
            nonce, plaintext.encode(), associated_data.encode())
        return f"{_VERSION}.{self.key_id}.{_encode(nonce)}.{_encode(sealed)}"

    def decrypt(self, stored: str, associated_data: str) -> str:
        try:
            version, key_id, nonce, sealed = stored.split(".")
            if version != _VERSION:
                raise DecryptionError
            opened = AESGCM(self._keys[key_id]).decrypt(
                _decode(nonce), _decode(sealed), associated_data.encode())
            return opened.decode()
        except (ValueError, KeyError, InvalidTag, binascii.Error) as exc:
            raise DecryptionError from exc


@lru_cache
def get_mfa_cipher() -> SecretCipher:
    settings: Settings = get_settings()
    return SecretCipher(
        settings.mfa_encryption_key_id,
        decode_key(settings.mfa_encryption_key.get_secret_value()),
        settings.mfa_previous_keys,
    )
