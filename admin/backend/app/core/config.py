"""Validated environment configuration. Missing or unsafe security settings stop startup."""

import base64
import binascii
import re
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import URL

_SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_KEY_ID = re.compile(r"^[A-Za-z0-9_-]{1,32}$")


def decode_key(value: str) -> bytes:
    """Decode a urlsafe-base64 AES-256 key, raising ValueError when it is not exactly 32 bytes."""
    try:
        raw = base64.urlsafe_b64decode(value.encode() + b"=" * (-len(value) % 4))
    except (binascii.Error, ValueError) as exc:
        raise ValueError("key must be urlsafe base64") from exc
    if len(raw) != 32:
        raise ValueError("key must decode to exactly 32 bytes")
    return raw


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"

    # Database
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "starter_app"
    database_user: str = "postgres"
    database_password: SecretStr
    database_schema: str = "admin"
    client_database_schema: str = "client"

    # Application
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # MFA
    mfa_title: str = "Starter Application"
    mfa_encryption_key: SecretStr
    mfa_encryption_key_id: str = "k1"
    # Comma-separated "key_id:key" pairs still accepted for decryption during rotation.
    mfa_encryption_previous_keys: SecretStr = SecretStr("")
    admin_mfa_required: bool = False
    mfa_challenge_expire_seconds: int = Field(default=300, ge=30, le=900)
    mfa_challenge_max_attempts: int = Field(default=5, ge=1, le=20)
    mfa_totp_valid_window: int = Field(default=1, ge=0, le=2)

    # Authentication
    access_token_expire_minutes: int = Field(default=15, ge=1, le=60)
    refresh_session_expire_days: int = Field(default=7, ge=1, le=90)
    refresh_reuse_grace_seconds: int = Field(default=10, ge=0, le=60)
    password_reset_expire_minutes: int = Field(default=30, ge=5, le=1440)
    password_min_length: int = Field(default=12, ge=8)
    login_max_failures: int = Field(default=5, ge=1)
    login_lockout_minutes: int = Field(default=15, ge=1)
    rate_limit_login_per_minute: int = Field(default=20, ge=1)
    rate_limit_mfa_per_minute: int = Field(default=20, ge=1)
    cookie_secure: bool = True

    # Argon2id (defaults follow RFC 9106's low-memory recommendation)
    argon2_time_cost: int = Field(default=3, ge=1)
    argon2_memory_cost_kib: int = Field(default=65536, ge=8)
    argon2_parallelism: int = Field(default=4, ge=1)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_schema", "client_database_schema")
    @classmethod
    def _valid_schema(cls, value: str) -> str:
        if not _SCHEMA_NAME.match(value):
            raise ValueError("invalid PostgreSQL schema name")
        return value

    @field_validator("mfa_encryption_key")
    @classmethod
    def _valid_mfa_key(cls, value: SecretStr) -> SecretStr:
        decode_key(value.get_secret_value())
        return value

    @field_validator("mfa_encryption_key_id")
    @classmethod
    def _valid_key_id(cls, value: str) -> str:
        if not _KEY_ID.match(value):
            raise ValueError("invalid key id")
        return value

    @field_validator("mfa_title")
    @classmethod
    def _valid_title(cls, value: str) -> str:
        # A colon would corrupt the "<issuer>:<account>" label of the provisioning URI.
        if not value.strip() or ":" in value:
            raise ValueError("MFA_TITLE must be non-empty and must not contain ':'")
        return value.strip()

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        if self.database_schema == self.client_database_schema:
            raise ValueError("Admin and Client schemas must differ")
        self.mfa_previous_keys  # noqa: B018 - validates the rotation key list at startup
        if self.environment in {"staging", "production"}:
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true outside development")
            if any(origin == "*" for origin in self.cors_origins):
                raise ValueError("Wildcard CORS origins are not allowed")
        return self

    @property
    def mfa_previous_keys(self) -> dict[str, bytes]:
        keys: dict[str, bytes] = {}
        for pair in self.mfa_encryption_previous_keys.get_secret_value().split(","):
            if not pair.strip():
                continue
            key_id, separator, key = pair.strip().partition(":")
            if not separator or not _KEY_ID.match(key_id):
                raise ValueError("MFA_ENCRYPTION_PREVIOUS_KEYS must contain key_id:key pairs")
            keys[key_id] = decode_key(key)
        return keys

    @property
    def docs_enabled(self) -> bool:
        return self.environment in {"development", "test"}

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.database_user,
            password=self.database_password.get_secret_value(),
            host=self.database_host,
            port=self.database_port,
            database=self.database_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
