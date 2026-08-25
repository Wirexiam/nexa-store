"""Failure-isolated Telegram Bot API notifications using the standard library."""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable
from urllib.parse import quote

from ..config import settings

logger = logging.getLogger(__name__)

OpenUrl = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    bot_token: str = ""
    admin_id: str = ""
    timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> TelegramConfig:
        configured_timeout = float(getattr(settings, "telegram_timeout_seconds", 5.0))
        return cls(
            bot_token=str(getattr(settings, "telegram_bot_token", "")).strip(),
            admin_id=str(getattr(settings, "telegram_admin_id", "")).strip(),
            timeout_seconds=max(0.1, min(30.0, configured_timeout)),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.admin_id)


class TelegramNotifier:
    def __init__(
        self,
        config: TelegramConfig | None = None,
        *,
        opener: OpenUrl = urllib.request.urlopen,
    ) -> None:
        self.config = config or TelegramConfig.from_env()
        self._opener = opener

    def send(self, text: str) -> bool:
        """Send a plain-text notification; return False for every failure."""

        if not self.config.enabled:
            return False

        token = quote(self.config.bot_token, safe=":")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        body = json.dumps(
            {
                "chat_id": self.config.admin_id,
                "text": text[:4000],
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            response = self._opener(request, timeout=self.config.timeout_seconds)
            try:
                response_body = response.read()
            finally:
                response.close()
            parsed = json.loads(response_body.decode("utf-8"))
            return bool(isinstance(parsed, dict) and parsed.get("ok") is True)
        except Exception:
            # Do not include the exception: urllib errors can contain the URL,
            # and therefore the bot token.
            logger.warning("Telegram notification could not be delivered")
            return False

    def notify_new_order(self, order: Any) -> bool:
        return self.send(
            "\n".join(
                [
                    "🆕 Nexa Store Order",
                    "",
                    f"ID: {_order_reference(order)}",
                    f"Service: {_safe_value(order, 'service')}",
                    f"Plan: {_safe_value(order, 'subscription_level')}",
                    f"Amount: {_amount(order)}",
                    f"Email: {_safe_value(order, 'customer_email')}",
                    f"Status: {_safe_value(order, 'status')}",
                ]
            )
        )

    def notify_execution_started(self, order: Any, executor_name: str) -> bool:
        return self.send(
            "\n".join(
                [
                    "⚙️ Execution started",
                    "",
                    f"Order: {_order_reference(order)}",
                    f"Executor: {executor_name[:120]}",
                ]
            )
        )

    def notify_execution_result(
        self,
        order: Any,
        execution_status: str,
        *,
        error: str | None = None,
    ) -> bool:
        icon_and_title = {
            "completed": "✅ Completed",
            "failed": "❌ Error",
            "stopped": "⏹️ Stopped",
            "action_required": "🛠️ Action required",
        }.get(execution_status, "ℹ️ Execution update")
        lines = [
            icon_and_title,
            "",
            f"Order: {_order_reference(order)}",
            f"Execution: {execution_status}",
        ]
        if error:
            lines.append(f"Error: {error[:500]}")
        return self.send("\n".join(lines))


def _safe_value(order: Any, field: str) -> str:
    value = getattr(order, field, None)
    if value is None or value == "":
        return "—"
    return str(value).replace("\r", " ").replace("\n", " ")[:500]


def _order_reference(order: Any) -> str:
    persisted_reference = getattr(order, "reference", None)
    if persisted_reference:
        return str(persisted_reference).replace("\r", " ").replace("\n", " ")[:100]
    order_id = _safe_value(order, "id")
    if order_id == "—":
        return order_id
    compact = order_id.replace("-", "")
    return f"NX-{compact[:8].upper()}"


def _amount(order: Any) -> str:
    value = getattr(order, "amount", None)
    currency = _safe_value(order, "currency")
    if value is None:
        return f"— {currency}"
    try:
        amount = format(Decimal(str(value)), ".2f")
    except Exception:
        amount = "—"
    return f"{amount} {currency}"


notifier = TelegramNotifier()
