"""Stable, failure-isolated notification hooks."""

from __future__ import annotations

from typing import Any

from .telegram import TelegramConfig, TelegramNotifier, notifier


def notify_new_order(order: Any) -> bool:
    """Notify the administrator without ever interrupting order processing."""

    try:
        return notifier.notify_new_order(order)
    except Exception:
        # Custom/test notifier replacements receive the same isolation
        # guarantee as the built-in Telegram transport.
        return False


__all__ = ["TelegramConfig", "TelegramNotifier", "notify_new_order", "notifier"]
