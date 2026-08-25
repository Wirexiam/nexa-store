"""Private CRM controls for order fulfillment lifecycle."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..automation.manager import ExecutionAlreadyRunning
from ..automation.service import (
    ExecutionServiceError,
    InvalidExecutionTransition,
    NoActiveExecution,
    get_execution_status,
    retry_execution,
    start_execution,
    stop_execution,
)
from ..database import get_db
from ..models import Order
from ..security import require_admin

router = APIRouter(
    prefix="/api/admin/orders",
    tags=["admin-execution"],
    dependencies=[Depends(require_admin)],
)


class ExecutionStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


def _order_or_404(db: Session, order_id: str) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order


def _translate_execution_error(exc: Exception) -> HTTPException:
    if isinstance(
        exc,
        (ExecutionAlreadyRunning, InvalidExecutionTransition, NoActiveExecution),
    ):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, ExecutionServiceError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Execution could not be scheduled",
    )


@router.post(
    "/{order_id}/execute",
    response_model=ExecutionStatusOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def execute_order(order_id: str, db: Session = Depends(get_db)):
    order = _order_or_404(db, order_id)
    try:
        return start_execution(db, order)
    except Exception as exc:
        raise _translate_execution_error(exc) from exc


@router.post("/{order_id}/stop", response_model=ExecutionStatusOut)
def stop_order_execution(order_id: str, db: Session = Depends(get_db)):
    order = _order_or_404(db, order_id)
    try:
        return stop_execution(db, order)
    except Exception as exc:
        raise _translate_execution_error(exc) from exc


@router.post(
    "/{order_id}/retry",
    response_model=ExecutionStatusOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_order_execution(order_id: str, db: Session = Depends(get_db)):
    order = _order_or_404(db, order_id)
    try:
        return retry_execution(db, order)
    except Exception as exc:
        raise _translate_execution_error(exc) from exc


@router.get("/{order_id}/execution-status", response_model=ExecutionStatusOut)
def execution_status(order_id: str, db: Session = Depends(get_db)):
    return get_execution_status(_order_or_404(db, order_id))
