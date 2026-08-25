"""Database lifecycle for fulfillment execution.

Sensitive customer input is accepted only as an in-memory mapping, transferred
to one executor job, and cleared on every success/failure/cancellation path.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from threading import Event
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import CatalogService, Order
from ..notifications.telegram import notifier
from .browser import BrowserAutomationUnavailable
from .executors import (
    ACTION_REQUIRED,
    EXECUTOR_TYPES,
    FAILED,
    PENDING,
    RUNNING,
    STOPPED,
    BaseExecutor,
    ExecutionOrder,
)
from .executors.examples import ChatGPTExecutor
from .executors.base import ExecutionValidationError, discard_transient_mapping
from .manager import ExecutionAlreadyRunning, ExecutionManager, execution_manager


class ExecutionServiceError(RuntimeError):
    pass


class NoActiveExecution(ExecutionServiceError):
    pass


class InvalidExecutionTransition(ExecutionServiceError):
    pass


@dataclass(frozen=True, slots=True)
class ExecutionSnapshot:
    order_id: str
    execution_status: str
    execution_status_label: str
    execution_error: str | None
    execution_result: str | None
    executor_name: str | None
    execution_started_at: datetime | None
    execution_finished_at: datetime | None
    execution_attempts: int
    execution_stop_requested: bool

    def model_dump(self) -> dict[str, Any]:
        """Small compatibility helper for Pydantic-like consumers."""

        return asdict(self)


class ExecutionService:
    def __init__(
        self,
        *,
        session_factory=SessionLocal,
        manager: ExecutionManager = execution_manager,
        notification_client=notifier,
        executor_types: Mapping[str, type[BaseExecutor]] | None = None,
        service_executor_types: Mapping[tuple[str, str], type[BaseExecutor]] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self.manager = manager
        self.notifier = notification_client
        self.executor_types = dict(executor_types or EXECUTOR_TYPES)
        self.service_executor_types = dict(
            service_executor_types
            if service_executor_types is not None
            else {("chatgpt", "browser_session"): ChatGPTExecutor}
        )

    def start(
        self,
        db: Session,
        order: Order,
        ephemeral_payload: Mapping[str, Any] | None = None,
    ) -> ExecutionSnapshot:
        """Dispatch execution and return immediately.

        If ``ephemeral_payload`` is mutable, ownership transfer clears the
        caller's container before this function returns.
        """

        transient_data: MutableMapping[str, Any] = dict(ephemeral_payload or {})
        if isinstance(ephemeral_payload, MutableMapping):
            # Clear only the outer caller-owned container. Its values are now
            # owned by transient_data and will be recursively discarded by the
            # executor/manager once the job ends.
            ephemeral_payload.clear()

        if self.manager.is_active(order.id) or getattr(order, "execution_status", PENDING) == RUNNING:
            discard_transient_mapping(transient_data)
            raise ExecutionAlreadyRunning("This order already has an active execution")
        if getattr(order, "execution_status", PENDING) == "completed":
            discard_transient_mapping(transient_data)
            raise InvalidExecutionTransition("A completed execution must not be started again")

        execution_type, order_snapshot = self._resolve_workflow(db, order)
        executor_class = self.service_executor_types.get(
            (order_snapshot.service_key, execution_type)
        ) or self.executor_types.get(execution_type)
        if executor_class is None:
            discard_transient_mapping(transient_data)
            raise ExecutionServiceError(f"Unsupported workflow type: {execution_type}")

        order.execution_status = PENDING
        order.execution_error = None
        order.execution_result = None
        order.executor_name = executor_class.__name__
        order.execution_started_at = None
        order.execution_finished_at = None
        order.execution_stop_requested = False
        db.commit()
        db.refresh(order)

        try:
            self.manager.submit(
                order.id,
                lambda stop_event, payload: self._run_job(
                    order.id,
                    executor_class,
                    order_snapshot,
                    stop_event,
                    payload,
                ),
                transient_data,
            )
        except Exception:
            # Harmless if manager.submit already cleared it; also covers an
            # unexpected pool submission failure before ownership transfer.
            discard_transient_mapping(transient_data)
            order.execution_status = FAILED
            order.execution_error = "Execution could not be scheduled"
            order.execution_finished_at = _utcnow()
            db.commit()
            db.refresh(order)
            raise
        return _snapshot(order)

    def stop(self, db: Session, order: Order) -> ExecutionSnapshot:
        current_status = getattr(order, "execution_status", PENDING)
        stop_request = self.manager.request_stop(order.id)
        if not stop_request.found and current_status not in {PENDING, RUNNING}:
            raise NoActiveExecution("This order has no active execution")

        order.execution_stop_requested = True
        if stop_request.canceled_before_start or not stop_request.found:
            # Also resolves a stale pending/running state left after a process
            # restart, when no in-memory job can exist anymore.
            order.execution_status = STOPPED
            order.execution_result = "Execution stopped"
            order.execution_finished_at = _utcnow()
        db.commit()
        db.refresh(order)
        return _snapshot(order)

    def retry(self, db: Session, order: Order) -> ExecutionSnapshot:
        current_status = getattr(order, "execution_status", PENDING)
        if current_status not in {FAILED, STOPPED, ACTION_REQUIRED}:
            raise InvalidExecutionTransition(
                "Only failed, stopped, or action-required executions can be retried"
            )
        return self.start(db, order, None)

    @staticmethod
    def get_status(order: Order) -> ExecutionSnapshot:
        return _snapshot(order)

    def _resolve_workflow(self, db: Session, order: Order) -> tuple[str, ExecutionOrder]:
        service = getattr(order, "catalog_service", None)
        if service is None:
            catalog_service_id = getattr(order, "catalog_service_id", None)
            if catalog_service_id:
                service = db.get(CatalogService, catalog_service_id)
        if service is None:
            service_key = getattr(order, "service_key", "")
            if service_key:
                service = db.scalar(
                    select(CatalogService).where(CatalogService.slug == service_key)
                )

        workflow = getattr(service, "workflow", None) if service is not None else None
        workflow_active = bool(workflow is not None and getattr(workflow, "active", True))
        execution_type = (
            getattr(workflow, "execution_type", "manual") if workflow_active else "manual"
        )
        description = getattr(workflow, "description", "") if workflow_active else ""
        requires_manual_action = bool(
            getattr(workflow, "requires_manual_action", True) if workflow_active else True
        )
        snapshot = ExecutionOrder(
            id=str(order.id),
            service=str(getattr(order, "service", "")),
            service_key=str(getattr(order, "service_key", "")),
            subscription_level=getattr(order, "subscription_level", None),
            payment_period=getattr(order, "payment_period", None),
            amount=_decimal_string(getattr(order, "amount", None)),
            currency=str(getattr(order, "currency", "RUB")),
            workflow_description=str(description or ""),
            requires_manual_action=requires_manual_action,
        )
        return str(execution_type), snapshot

    def _run_job(
        self,
        order_id: str,
        executor_class: type[BaseExecutor],
        order_snapshot: ExecutionOrder,
        stop_event: Event,
        transient_data: MutableMapping[str, Any],
    ) -> None:
        worker_db = self._session_factory()
        order: Order | None = None
        redaction_values: tuple[str, ...] = tuple(_scalar_strings(transient_data))
        try:
            order = worker_db.get(Order, order_id)
            if order is None:
                return
            if stop_event.is_set():
                order.execution_status = STOPPED
                order.execution_result = "Execution stopped"
                order.execution_finished_at = _utcnow()
                worker_db.commit()
                return

            order.execution_status = RUNNING
            order.execution_error = None
            order.execution_result = None
            order.execution_started_at = _utcnow()
            order.execution_finished_at = None
            order.execution_attempts = int(getattr(order, "execution_attempts", 0) or 0) + 1
            worker_db.commit()
            worker_db.refresh(order)
            self._safe_notify("notify_execution_started", order, executor_class.__name__)

            executor = executor_class(order_snapshot, transient_data, stop_event)
            outcome = executor.run()
            safe_message = _redact_values(outcome.message, redaction_values)

            order.execution_status = outcome.status
            order.execution_result = safe_message
            order.execution_error = None
            order.execution_finished_at = _utcnow()
            worker_db.commit()
            worker_db.refresh(order)
            self._safe_notify("notify_execution_result", order, outcome.status)
        except Exception as exc:
            if order is not None:
                safe_error = _safe_execution_error(exc, redaction_values)
                order.execution_status = FAILED
                order.execution_error = safe_error
                order.execution_result = None
                order.execution_finished_at = _utcnow()
                try:
                    worker_db.commit()
                    worker_db.refresh(order)
                except Exception:
                    worker_db.rollback()
                self._safe_notify(
                    "notify_execution_result",
                    order,
                    FAILED,
                    error=safe_error,
                )
        finally:
            discard_transient_mapping(transient_data)
            worker_db.close()

    def _safe_notify(self, method_name: str, *args, **kwargs) -> bool:
        try:
            method = getattr(self.notifier, method_name)
            return bool(method(*args, **kwargs))
        except Exception:
            return False


def _snapshot(order: Order) -> ExecutionSnapshot:
    from .executors import EXECUTION_STATUS_LABELS

    current_status = str(getattr(order, "execution_status", PENDING))
    return ExecutionSnapshot(
        order_id=str(order.id),
        execution_status=current_status,
        execution_status_label=EXECUTION_STATUS_LABELS.get(current_status, current_status),
        execution_error=getattr(order, "execution_error", None),
        execution_result=getattr(order, "execution_result", None),
        executor_name=getattr(order, "executor_name", None),
        execution_started_at=getattr(order, "execution_started_at", None),
        execution_finished_at=getattr(order, "execution_finished_at", None),
        execution_attempts=int(getattr(order, "execution_attempts", 0) or 0),
        execution_stop_requested=bool(
            getattr(order, "execution_stop_requested", False)
        ),
    )


def _safe_execution_error(exc: Exception, redaction_values: tuple[str, ...]) -> str:
    if isinstance(exc, (ExecutionValidationError, BrowserAutomationUnavailable)):
        return _redact_values(str(exc)[:1000], redaction_values) or "Execution validation failed"
    return f"Execution failed ({type(exc).__name__})"


def _redact_values(
    message: str | None,
    redaction_values: tuple[str, ...],
) -> str | None:
    if message is None:
        return None
    cleaned = str(message)[:2000]
    for raw_value in redaction_values:
        if raw_value:
            cleaned = cleaned.replace(raw_value, "[redacted]")
    return cleaned


def _scalar_strings(value: Any):
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _scalar_strings(nested)
    elif isinstance(value, (list, tuple, set)):
        for nested in value:
            yield from _scalar_strings(nested)
    elif isinstance(value, (str, bytes, bytearray)):
        if isinstance(value, str):
            yield value
        else:
            yield bytes(value).decode("utf-8", errors="ignore")


def _decimal_string(value: Any) -> str:
    try:
        return format(Decimal(str(value)), ".2f")
    except Exception:
        return "0.00"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


execution_service = ExecutionService()


def start_execution(
    db: Session,
    order: Order,
    ephemeral_payload: Mapping[str, Any] | None = None,
) -> ExecutionSnapshot:
    return execution_service.start(db, order, ephemeral_payload)


def stop_execution(db: Session, order: Order) -> ExecutionSnapshot:
    return execution_service.stop(db, order)


def retry_execution(db: Session, order: Order) -> ExecutionSnapshot:
    return execution_service.retry(db, order)


def get_execution_status(order: Order) -> ExecutionSnapshot:
    return execution_service.get_status(order)
