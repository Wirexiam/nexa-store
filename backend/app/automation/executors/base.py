"""Executor interface and lifecycle shared by all workflow types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Event
from typing import Any, MutableMapping

PENDING = "pending"
RUNNING = "running"
ACTION_REQUIRED = "action_required"
COMPLETED = "completed"
FAILED = "failed"
STOPPED = "stopped"

EXECUTION_STATUSES = frozenset(
    {PENDING, RUNNING, ACTION_REQUIRED, COMPLETED, FAILED, STOPPED}
)
EXECUTION_STATUS_LABELS = {
    PENDING: "Ожидает выполнения",
    RUNNING: "Выполняется",
    ACTION_REQUIRED: "Требует действия",
    COMPLETED: "Завершено",
    FAILED: "Ошибка выполнения",
    STOPPED: "Остановлено",
}
TERMINAL_EXECUTION_STATUSES = frozenset(
    {ACTION_REQUIRED, COMPLETED, FAILED, STOPPED}
)


class ExecutionValidationError(ValueError):
    """Safe validation error whose message may be shown in CRM."""


class ExecutionStopRequested(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ExecutionOrder:
    """Non-sensitive order snapshot passed to executors instead of an ORM row."""

    id: str
    service: str
    service_key: str
    subscription_level: str | None = None
    payment_period: str | None = None
    amount: str = "0.00"
    currency: str = "RUB"
    workflow_description: str = ""
    requires_manual_action: bool = False


@dataclass(frozen=True, slots=True)
class ExecutionOutcome:
    status: str
    message: str | None = None

    def __post_init__(self) -> None:
        if self.status not in TERMINAL_EXECUTION_STATUSES:
            raise ValueError("Executor outcomes must use a terminal execution status")


class BaseExecutor(ABC):
    """Template-method executor with unconditional transient-data cleanup."""

    execution_type = "manual"

    def __init__(
        self,
        order: ExecutionOrder,
        transient_data: MutableMapping[str, Any],
        stop_event: Event,
    ) -> None:
        self.order = order
        # Ownership is transferred to the executor. Do not copy this mapping:
        # reducing duplicate references makes prompt cleanup more reliable.
        self.transient_data = transient_data
        self.stop_event = stop_event
        self._status = PENDING

    def validate(self) -> None:
        """Validate transient input without persisting or logging its values."""

    def prepare(self) -> None:
        """Allocate workflow resources."""

    @abstractmethod
    def execute(self) -> ExecutionOutcome:
        """Run the workflow without returning raw customer secrets."""

    def cleanup(self) -> None:
        """Release executor-specific resources."""

    def get_status(self) -> str:
        return self._status

    def request_stop(self) -> None:
        self.stop_event.set()

    def ensure_not_stopped(self) -> None:
        if self.stop_event.is_set():
            raise ExecutionStopRequested()

    def run(self) -> ExecutionOutcome:
        outcome: ExecutionOutcome | None = None
        try:
            self.ensure_not_stopped()
            self.validate()
            self.ensure_not_stopped()
            self._status = RUNNING
            self.prepare()
            self.ensure_not_stopped()
            outcome = self.execute()
            self.ensure_not_stopped()
            self._status = outcome.status
            return outcome
        except ExecutionStopRequested:
            self._status = STOPPED
            outcome = ExecutionOutcome(STOPPED, "Execution stopped")
            return outcome
        finally:
            try:
                self.cleanup()
            finally:
                discard_transient_mapping(self.transient_data)


def discard_transient_mapping(payload: MutableMapping[str, Any]) -> None:
    """Promptly remove references to temporary input values.

    CPython strings cannot be securely zeroed, but recursively clearing mutable
    containers ensures the application does not retain or persist them.
    """

    for value in list(payload.values()):
        _discard_mutable(value)
    payload.clear()


def _discard_mutable(value: Any) -> None:
    if isinstance(value, MutableMapping):
        for nested in list(value.values()):
            _discard_mutable(nested)
        value.clear()
    elif isinstance(value, list):
        for nested in value:
            _discard_mutable(nested)
        value.clear()
    elif isinstance(value, bytearray):
        value[:] = b"\x00" * len(value)
