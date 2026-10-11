"""Logging setup with a redaction filter so credentials never reach log output."""

from __future__ import annotations

import logging
import re

_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|apikey|token|x-api-key|authorization)([\"'=:\s]+)([^\s&\"',]+)"),
    re.compile(r"sk-ant-[A-Za-z0-9_\-]+"),
]


class RedactingFilter(logging.Filter):
    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        self.secrets = [s for s in (secrets or []) if s]

    def redact(self, text: str) -> str:
        for s in self.secrets:
            text = text.replace(s, "***REDACTED***")
        text = _PATTERNS[0].sub(lambda m: f"{m.group(1)}{m.group(2)}***REDACTED***", text)
        return _PATTERNS[1].sub("***REDACTED***", text)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - malformed log call
            return True
        redacted = self.redact(message)
        if redacted != message:
            record.msg, record.args = redacted, ()
        return True


def configure_logging(level: str, secrets: list[str]) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    if not any(getattr(h, "_fig_handler", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler._fig_handler = True  # type: ignore[attr-defined]
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
    redactor = RedactingFilter(secrets)
    for h in root.handlers:
        h.filters = [f for f in h.filters if not isinstance(f, RedactingFilter)]
        h.addFilter(redactor)
    # httpx logs full request URLs, which can contain provider tokens (e.g. Finnhub ?token=).
    for noisy in ("httpx", "httpx2", "httpcore", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
