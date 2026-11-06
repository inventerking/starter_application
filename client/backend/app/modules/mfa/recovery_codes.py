"""Single-use recovery codes, shown once in the form ABCD-1234 and stored as Argon2id hashes."""

import secrets

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # No 0/O or 1/I, which are easily confused.
CODE_COUNT = 10


def generate_codes() -> list[str]:
    return [_format("".join(secrets.choice(_ALPHABET) for _ in range(8)))
            for _ in range(CODE_COUNT)]


def _format(raw: str) -> str:
    return f"{raw[:4]}-{raw[4:]}"


def normalize(code: str) -> str:
    return _format(code.strip().upper().replace("-", "").replace(" ", ""))
