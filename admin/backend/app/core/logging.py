"""Logging configuration with a redaction filter as a last line of defence."""

import logging
import re

_SENSITIVE = re.compile(
    r"(?i)(password|passwd|secret|token|recovery_code|authorization|cookie|encryption_key)"
    r"(['\"]?\s*[=:]\s*['\"]?)[^\s,'\"}&]+"
)


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except (TypeError, ValueError):
            return True
        record.msg = _SENSITIVE.sub(r"\1\2[REDACTED]", message)
        record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactSecretsFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
