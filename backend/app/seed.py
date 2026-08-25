from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .catalog import get_service, next_order_reference, resolve_level_period
from .models import Order


DEMO_ORDERS = [
    {
        "email": "anna.k@example.com",
        "service_key": "chatgpt",
        "level_id": "plus",
        "period_id": "1m",
        "status": "В работе",
        "submitted": True,
    },
    {
        "email": "ivan.p@example.com",
        "service_key": "chatgpt",
        "level_id": "pro",
        "period_id": "12m",
        "status": "Оплачено",
        "submitted": True,
    },
    {
        "email": "maria.s@example.com",
        "service_key": "claude",
        "level_id": "pro",
        "period_id": "3m",
        "status": "Оплачено",
        "submitted": True,
    },
    {
        "email": None,
        "service_key": "midjourney",
        "level_id": "standard",
        "period_id": "1m",
        "status": "В работе",
        "submitted": False,
    },
    {
        "email": "kirill.n@example.com",
        "service_key": "notion",
        "level_id": "business",
        "period_id": "12m",
        "status": "Отменено",
        "submitted": True,
    },
    {
        "email": "elena.v@example.com",
        "service_key": "claude",
        "level_id": "team",
        "period_id": "1m",
        "status": "Ошибка",
        "submitted": True,
    },
]


def seed_if_empty(db: Session) -> None:
    """Retain the original demo CRM rows for a brand-new local database."""

    if db.scalar(select(Order.id).limit(1)) is not None:
        return
    now = datetime.now(timezone.utc)
    for item in DEMO_ORDERS:
        service = get_service(db, item["service_key"])
        if not service:
            continue
        level, period, amount = resolve_level_period(
            service, item["level_id"], item["period_id"]
        )
        order = Order(
            reference=next_order_reference(db),
            customer_email=item["email"],
            service=service.name,
            service_key=service.slug,
            subscription_level=level.name,
            payment_period=period.name,
            amount=amount,
            currency=level.currency or service.currency,
            status=item["status"],
            credentials_received=bool(item["submitted"] and service.requires_access_token),
            submitted_at=now if item["submitted"] else None,
            catalog_service_id=service.id,
            catalog_plan_id=level.id,
            catalog_period_id=period.id,
            execution_status="pending",
        )
        db.add(order)
        db.flush()
    db.commit()
