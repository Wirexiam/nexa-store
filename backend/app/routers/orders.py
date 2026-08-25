from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..automation.service import start_execution
from ..catalog import (
    CatalogValidationError,
    get_service,
    order_to_public_dict,
    resolve_level_period,
    validate_dynamic_fields,
)
from ..database import get_db
from ..models import Order
from ..notifications import notify_new_order
from ..schemas import OrderPublic, OrderSubmit

router = APIRouter(prefix="/api/orders", tags=["customer"])


@router.get("/{order_id}", response_model=OrderPublic)
def get_customer_order(order_id: str, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order_to_public_dict(db, order)


def _field_payload(service, payload: OrderSubmit) -> dict[str, Any]:
    submitted = dict(payload.custom_fields)
    configured_fields = [field for field in service.fields if field.is_active]
    configured_names = {field.field_name for field in configured_fields}

    if payload.email is not None and "email" in configured_names:
        email = str(payload.email)
        if "email" in submitted and str(submitted["email"]).strip().lower() != email.lower():
            raise CatalogValidationError(
                "Customer field validation failed",
                fields={"email": "conflicts with the top-level email"},
            )
        submitted["email"] = email

    access_token = payload.access_token
    payload.access_token = None
    if access_token is not None and access_token.strip():
        secret_fields = [field for field in configured_fields if field.sensitive]
        target = next(
            (field for field in secret_fields if field.field_name == "access_token"),
            secret_fields[0] if secret_fields else None,
        )
        if target is None:
            raise CatalogValidationError(
                "Customer field validation failed",
                fields={"access_token": "is not configured for this service"},
            )
        if target.field_name in submitted and submitted[target.field_name] != access_token:
            raise CatalogValidationError(
                "Customer field validation failed",
                fields={target.field_name: "conflicts with the top-level access token"},
            )
        submitted[target.field_name] = access_token
    access_token = None
    return submitted


@router.post("/{order_id}/submit", response_model=OrderPublic)
def submit_customer_order(order_id: str, payload: OrderSubmit, db: Session = Depends(get_db)):
    submitted: dict[str, Any] = {}
    ephemeral: dict[str, Any] = {}
    durable: dict[str, Any] = {}
    try:
        order = db.get(Order, order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        service = get_service(
            db,
            order.catalog_service_id or order.service_key,
            include_inactive=True,
            include_archived=True,
        )
        if not service:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown service")

        level_id = payload.level_id or order.catalog_plan_id or None
        period_id = payload.period_id or order.catalog_period_id or None
        try:
            level, period, amount = resolve_level_period(
                service, level_id, period_id, require_active=False
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan selection"
            ) from exc

        try:
            submitted = _field_payload(service, payload)
            ephemeral, durable = validate_dynamic_fields(service, submitted)
        except CatalogValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": str(exc), "fields": exc.fields},
            ) from exc

        email_field = next(
            (
                field
                for field in service.fields
                if field.is_active and field.field_type == "email" and field.field_name in ephemeral
            ),
            None,
        )
        customer_email = (
            str(ephemeral[email_field.field_name])
            if email_field is not None
            else str(payload.email) if payload.email is not None else order.customer_email
        )
        safe_custom_data = dict(durable)
        if email_field is not None:
            safe_custom_data.pop(email_field.field_name, None)

        previously_submitted = order.submitted_at is not None
        order.customer_email = customer_email
        order.service = service.name
        order.service_key = service.slug
        order.subscription_level = level.name
        order.payment_period = period.name
        order.amount = amount
        order.currency = level.currency or service.currency
        order.catalog_service_id = service.id
        order.catalog_plan_id = level.id
        order.catalog_period_id = period.id
        order.custom_data = safe_custom_data
        order.credentials_received = any(
            field.sensitive and field.field_name in ephemeral
            for field in service.fields
            if field.is_active
        )
        order.submitted_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(order)

        if not previously_submitted:
            # Both hooks isolate their own operational failures. The defensive
            # catches keep a customer submission successful if an optional
            # integration has a programming/configuration fault.
            try:
                notify_new_order(order)
            except Exception:
                pass
            try:
                start_execution(db, order, ephemeral)
            except Exception as exc:
                order.execution_status = "failed"
                order.execution_error = f"Execution could not be scheduled ({type(exc).__name__})"
                order.execution_finished_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(order)

        return order_to_public_dict(db, order)
    finally:
        # Pydantic and local containers may otherwise retain sensitive values
        # until garbage collection. None of these mappings is persisted/logged.
        payload.access_token = None
        payload.custom_fields.clear()
        submitted.clear()
        ephemeral.clear()
        durable.clear()
