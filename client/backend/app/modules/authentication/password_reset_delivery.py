"""Delivery boundary for self-service password reset.

No email provider is part of this foundation. Until one is wired in, self-service reset creates no
tokens, and administrators can issue a temporary password instead. Implementations must never log
the token.
"""

from typing import Protocol


class PasswordResetDelivery(Protocol):
    enabled: bool

    def send(self, email: str, token: str) -> None: ...


class DisabledPasswordResetDelivery:
    enabled = False

    def send(self, email: str, token: str) -> None:
        raise RuntimeError("Password reset delivery is not configured.")


def get_password_reset_delivery() -> PasswordResetDelivery:
    return DisabledPasswordResetDelivery()
