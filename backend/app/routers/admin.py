from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..catalog import (
    get_service,
    next_order_reference,
    order_to_admin_dict,
    resolve_level_period,
)
from ..database import get_db
from ..models import Order
from ..schemas import STATUSES, OrderCreate, OrderOut, StatusUpdate
from ..security import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/health")
def admin_health():
    return {"ok": True}


@router.get("/orders", response_model=list[OrderOut])
def list_orders(
    q: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    execution_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = select(Order).order_by(Order.created_at.desc())
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    if execution_status:
        stmt = stmt.where(Order.execution_status == execution_status)
    if q and q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Order.id.ilike(like),
                Order.reference.ilike(like),
                Order.customer_email.ilike(like),
                Order.service.ilike(like),
                Order.subscription_level.ilike(like),
            )
        )
    return [order_to_admin_dict(db, order) for order in db.scalars(stmt).all()]


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: str, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order_to_admin_dict(db, order)


@router.patch("/orders/{order_id}/status", response_model=OrderOut)
def update_status(order_id: str, payload: StatusUpdate, db: Session = Depends(get_db)):
    if payload.status not in STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown status")
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    order.status = payload.status
    db.commit()
    db.refresh(order)
    return order_to_admin_dict(db, order)


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    service = get_service(db, payload.service_key)
    if not service:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown service")
    try:
        level, period, amount = resolve_level_period(
            service, payload.level_id, payload.period_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan selection"
        ) from exc

    order = Order(
        reference=next_order_reference(db),
        customer_email=str(payload.customer_email) if payload.customer_email else None,
        service=service.name,
        service_key=service.slug,
        subscription_level=level.name,
        payment_period=period.name,
        amount=amount,
        currency=level.currency or service.currency,
        status="В работе",
        execution_status="pending",
        catalog_service_id=service.id,
        catalog_plan_id=level.id,
        catalog_period_id=period.id,
    )
    db.add(order)
    try:
        db.commit()
    except IntegrityError as exc:
        # A concurrent creator may have claimed the sequential reference. The
        # UUID remains authoritative; retry once with a freshly computed label.
        db.rollback()
        order.reference = next_order_reference(db)
        db.add(order)
        try:
            db.commit()
        except IntegrityError as retry_exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not allocate an order reference",
            ) from retry_exc
    db.refresh(order)
    return order_to_admin_dict(db, order)
