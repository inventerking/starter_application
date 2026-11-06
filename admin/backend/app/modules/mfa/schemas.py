"""MFA request and response schemas."""

from pydantic import BaseModel, Field, model_validator

from app.core.security import PASSWORD_MAX_LENGTH

Code = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class MfaSetupRequest(BaseModel):
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class MfaSetupResponse(BaseModel):
    """The only response that carries the secret, and only before enrollment is confirmed."""

    secret: str
    provisioning_uri: str
    qr_code: str
    issuer: str
    account: str


class MfaConfirmRequest(BaseModel):
    code: str = Code


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class MfaVerifyLoginRequest(BaseModel):
    challenge_token: str = Field(min_length=1, max_length=256)
    code: str | None = Field(default=None, max_length=6)
    recovery_code: str | None = Field(default=None, max_length=16)

    @model_validator(mode="after")
    def _exactly_one(self) -> "MfaVerifyLoginRequest":
        if bool(self.code) == bool(self.recovery_code):
            raise ValueError("Provide either a code or a recovery code.")
        return self


class MfaDisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    code: str = Code


class MfaRegenerateRequest(BaseModel):
    code: str = Code


class MfaStatusResponse(BaseModel):
    enabled: bool
    confirmed_at: str | None
    recovery_codes_remaining: int
