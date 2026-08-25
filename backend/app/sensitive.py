"""Transient handling of secrets. Values must never reach the database or logs."""

from collections.abc import Mapping
from typing import Any

from .models import FORBIDDEN_COLUMNS

REDACTED = "[redacted]"


def consume_access_token(raw_token: str | None) -> bool:
    """Return True if a non-empty token was provided, then drop the value."""
    provided = bool(raw_token and raw_token.strip())
    raw_token = None
    del raw_token
    return provided


def strip_secrets(payload: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = {}
    for key, value in payload.items():
        if key.lower() in FORBIDDEN_COLUMNS:
            continue
        cleaned[key] = value
    return cleaned


def redact_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    redacted = {}
    for key, value in payload.items():
        if key.lower() in FORBIDDEN_COLUMNS:
            redacted[key] = REDACTED
        else:
            redacted[key] = value
    return redacted
