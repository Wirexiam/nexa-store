from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .catalog_seed import DEFAULT_SERVICES
from .models import (
    FORBIDDEN_COLUMNS,
    CatalogPeriod,
    CatalogPlan,
    CatalogPrice,
    CatalogService,
    Category,
    Order,
    ServiceField,
    ServiceInstruction,
    ServiceWorkflow,
)
from .schemas import (
    CatalogServiceInput,
    CategoryInput,
    ServiceFieldInput,
    ServiceWorkflowInput,
)


class CatalogConflictError(ValueError):
    pass


class CatalogValidationError(ValueError):
    def __init__(self, message: str, *, fields: dict[str, str] | None = None):
        super().__init__(message)
        self.fields = fields or {}


def _service_options():
    return (
        selectinload(CatalogService.periods),
        selectinload(CatalogService.plans).selectinload(CatalogPlan.prices),
        selectinload(CatalogService.fields),
        selectinload(CatalogService.instruction),
        selectinload(CatalogService.workflow),
    )


def slugify(value: str, *, fallback_prefix: str = "item") -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    if slug:
        return slug[:64].rstrip("-")
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
    return f"{fallback_prefix}-{digest}"


def list_categories(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name, Category.slug)).all())


def get_category(db: Session, identifier: str) -> Category | None:
    normalized = identifier.strip().lower()
    return db.scalar(
        select(Category).where(or_(Category.id == identifier, Category.slug == normalized))
    )


def create_category(db: Session, payload: CategoryInput) -> Category:
    if db.scalar(select(Category.id).where(Category.slug == payload.slug)) is not None:
        raise CatalogConflictError("A category with this slug already exists")
    category = Category(name=payload.name, slug=payload.slug)
    db.add(category)
    db.flush()
    return category


def replace_category(db: Session, category: Category, payload: CategoryInput) -> Category:
    duplicate = db.scalar(
        select(Category.id).where(Category.slug == payload.slug, Category.id != category.id)
    )
    if duplicate is not None:
        raise CatalogConflictError("A category with this slug already exists")
    category.name = payload.name
    category.slug = payload.slug
    db.flush()
    return category


def get_or_create_category(
    db: Session,
    *,
    category_id: str | None = None,
    name: str | None = None,
    category_slug: str | None = None,
) -> Category:
    if category_id:
        category = db.get(Category, category_id)
        if category is None:
            raise CatalogValidationError("Unknown category")
        return category

    clean_name = (name or "Other").strip() or "Other"
    clean_slug = (category_slug or slugify(clean_name, fallback_prefix="category")).lower()
    category = db.scalar(select(Category).where(Category.slug == clean_slug))
    if category is not None:
        return category
    category = Category(name=clean_name, slug=clean_slug)
    db.add(category)
    db.flush()
    return category


def list_services(
    db: Session,
    *,
    include_inactive: bool = False,
    include_archived: bool = False,
    query: str | None = None,
    category: str | None = None,
) -> list[CatalogService]:
    stmt = select(CatalogService).options(*_service_options()).order_by(
        CatalogService.sort_order, CatalogService.name
    )
    if not include_inactive:
        stmt = stmt.where(CatalogService.is_active.is_(True))
    if not include_archived:
        stmt = stmt.where(CatalogService.deleted_at.is_(None))
    if query and query.strip():
        like = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                CatalogService.name.ilike(like),
                CatalogService.slug.ilike(like),
                CatalogService.description.ilike(like),
            )
        )
    if category and category.strip():
        normalized = category.strip().lower()
        stmt = stmt.join(CatalogService.category).where(
            or_(Category.id == category, Category.slug == normalized)
        )
    return list(db.scalars(stmt).unique().all())


def get_service(
    db: Session,
    identifier: str,
    *,
    include_inactive: bool = False,
    include_archived: bool = False,
) -> CatalogService | None:
    normalized = identifier.strip().lower()
    stmt = (
        select(CatalogService)
        .options(*_service_options())
        .where(or_(CatalogService.id == identifier, CatalogService.slug == normalized))
    )
    if not include_inactive:
        stmt = stmt.where(CatalogService.is_active.is_(True))
    if not include_archived:
        stmt = stmt.where(CatalogService.deleted_at.is_(None))
    return db.scalar(stmt)


def get_service_by_id(db: Session, service_id: str) -> CatalogService | None:
    return get_service(db, service_id, include_inactive=True, include_archived=True)


def _field_to_dict(field: ServiceField) -> dict[str, Any]:
    return {
        "id": field.id,
        "field_name": field.field_name,
        "field_label": field.field_label,
        "field_type": field.field_type,
        "required": field.required,
        "placeholder": field.placeholder,
        "help_text": field.help_text,
        "validation_rules": field.validation_rules or {},
        "options": field.options or [],
        "order": field.order,
        "sensitive": field.sensitive,
        "temporary_only": field.temporary_only,
        "is_active": field.is_active,
        "active": field.is_active,
    }


def service_to_dict(
    service: CatalogService,
    *,
    include_inactive_options: bool = False,
) -> dict[str, Any]:
    periods = sorted(service.periods, key=lambda item: (item.sort_order, item.name, item.key))
    plans = sorted(service.plans, key=lambda item: (item.sort_order, item.name, item.key))
    fields = sorted(service.fields, key=lambda item: (item.order, item.field_label, item.field_name))
    if not include_inactive_options:
        periods = [period for period in periods if period.is_active]
        plans = [plan for plan in plans if plan.is_active]
        fields = [field for field in fields if field.is_active]

    period_by_db_id = {period.id: period for period in periods}
    levels: list[dict[str, Any]] = []
    for plan in plans:
        prices = {
            period_by_db_id[price.period_id].key: Decimal(price.amount)
            for price in plan.prices
            if price.period_id in period_by_db_id
        }
        price = min(prices.values()) if prices else None
        levels.append(
            {
                "record_id": plan.id,
                "id": plan.key,
                "key": plan.key,
                "name": plan.name,
                "description": plan.description,
                "currency": plan.currency or service.currency,
                "price": price,
                "prices": prices,
                "is_active": plan.is_active,
                "active": plan.is_active,
                "sort_order": plan.sort_order,
            }
        )

    category = None
    if service.category is not None:
        category = {
            "id": service.category.id,
            "name": service.category.name,
            "slug": service.category.slug,
            "created_at": service.category.created_at,
        }
    instruction_content = (
        service.instruction.content if service.instruction is not None else service.instructions
    )
    instruction = {
        "id": service.instruction.id if service.instruction else None,
        "content": instruction_content,
        "updated_at": service.instruction.updated_at if service.instruction else service.updated_at,
    }
    workflow = {
        "id": service.workflow.id if service.workflow else None,
        "execution_type": service.workflow.execution_type if service.workflow else "manual",
        "active": service.workflow.active if service.workflow else True,
        "requires_manual_action": (
            service.workflow.requires_manual_action if service.workflow else True
        ),
        "description": service.workflow.description if service.workflow else "",
    }
    field_rows = [_field_to_dict(field) for field in fields]
    requires_secret = service.requires_access_token or any(field.sensitive for field in fields)
    logo_url = service.logo_url or service.logo

    result = {
        "id": service.id,
        "key": service.slug,
        "slug": service.slug,
        "name": service.name,
        "logo": logo_url,
        "logo_url": logo_url,
        "description": service.description,
        "tagline": service.description,
        "accent": service.accent,
        "currency": service.currency,
        "category_id": service.category_id,
        "category": category,
        "category_name": category["name"] if category else None,
        "requires_access_token": requires_secret,
        "token_label": service.token_label,
        "token_hint": service.token_hint,
        "instructions": instruction_content,
        "instruction": instruction,
        "workflow": workflow,
        "fields": field_rows,
        "is_active": service.is_active,
        "active": service.is_active,
        "sort_order": service.sort_order,
        "levels": levels,
        "plans": levels,
        "periods": [
            {
                "record_id": period.id,
                "id": period.key,
                "key": period.key,
                "name": period.name,
                "duration": period.duration,
                "is_active": period.is_active,
                "active": period.is_active,
                "sort_order": period.sort_order,
            }
            for period in periods
        ],
        "created_at": service.created_at,
        "updated_at": service.updated_at,
    }
    return result


def public_catalog(db: Session) -> list[dict[str, Any]]:
    return [service_to_dict(service) for service in list_services(db)]


def resolve_level_period(
    service: CatalogService,
    level_id: str | None,
    period_id: str | None,
    *,
    require_active: bool = True,
) -> tuple[CatalogPlan, CatalogPeriod, Decimal]:
    levels = [plan for plan in service.plans if plan.is_active or not require_active]
    periods = [period for period in service.periods if period.is_active or not require_active]
    levels.sort(key=lambda item: (item.sort_order, item.name, item.key))
    periods.sort(key=lambda item: (item.sort_order, item.name, item.key))
    if not levels or not periods:
        raise ValueError("Service has no selectable plan or payment period")

    level = levels[0] if level_id is None else next(
        (item for item in levels if item.key == level_id or item.id == level_id), None
    )
    period = periods[0] if period_id is None else next(
        (item for item in periods if item.key == period_id or item.id == period_id), None
    )
    if level is None or period is None:
        raise ValueError("Unknown subscription level or payment period")
    price = next((item for item in level.prices if item.period_id == period.id), None)
    if price is None:
        raise ValueError("No price for subscription level and payment period")
    return level, period, Decimal(price.amount)


def _ensure_slug_available(db: Session, slug: str, *, excluding_id: str | None = None) -> None:
    stmt = select(CatalogService.id).where(CatalogService.slug == slug)
    if excluding_id:
        stmt = stmt.where(CatalogService.id != excluding_id)
    if db.scalar(stmt) is not None:
        raise CatalogConflictError("A service with this slug already exists")


def _category_for_payload(db: Session, payload: CatalogServiceInput) -> Category:
    return get_or_create_category(
        db,
        category_id=payload.category_id,
        name=payload.category,
        category_slug=payload.category_slug,
    )


def _set_service_fields(db: Session, service: CatalogService, payload: CatalogServiceInput) -> None:
    service.name = payload.name
    service.slug = payload.slug
    service.logo = payload.logo
    service.logo_url = payload.logo
    service.description = payload.description
    service.accent = payload.accent
    service.currency = payload.currency
    service.requires_access_token = payload.requires_access_token
    service.token_label = payload.token_label if payload.requires_access_token else None
    service.token_hint = payload.token_hint if payload.requires_access_token else None
    service.instructions = payload.instructions
    service.category = _category_for_payload(db, payload)
    service.is_active = payload.is_active
    service.sort_order = payload.sort_order
    if payload.is_active:
        service.deleted_at = None


def _sync_service_options(db: Session, service: CatalogService, payload: CatalogServiceInput) -> None:
    existing_periods = {period.key: period for period in service.periods}
    incoming_period_keys = {item.id for item in payload.periods}
    period_by_key: dict[str, CatalogPeriod] = {}
    for item in payload.periods:
        period = existing_periods.get(item.id)
        if period is None:
            period = CatalogPeriod(service=service, key=item.id)
            db.add(period)
        period.name = item.name
        period.duration = item.duration
        period.is_active = item.is_active
        period.sort_order = item.sort_order
        period_by_key[item.id] = period
    for key, period in existing_periods.items():
        if key not in incoming_period_keys:
            period.is_active = False

    existing_plans = {plan.key: plan for plan in service.plans}
    incoming_plan_keys = {item.id for item in payload.levels}
    plan_by_key: dict[str, CatalogPlan] = {}
    for item in payload.levels:
        plan = existing_plans.get(item.id)
        if plan is None:
            plan = CatalogPlan(service=service, key=item.id)
            db.add(plan)
        plan.name = item.name
        plan.description = item.description
        plan.currency = item.currency or payload.currency
        plan.is_active = item.is_active
        plan.sort_order = item.sort_order
        plan_by_key[item.id] = plan
    for key, plan in existing_plans.items():
        if key not in incoming_plan_keys:
            plan.is_active = False

    db.flush()

    for item in payload.levels:
        plan = plan_by_key[item.id]
        existing_prices = {price.period_id: price for price in plan.prices}
        supplied_period_db_ids: set[str] = set()
        for period_key, amount in item.prices.items():
            period = period_by_key[period_key]
            supplied_period_db_ids.add(period.id)
            price = existing_prices.get(period.id)
            if price is None:
                price = CatalogPrice(plan=plan, period=period)
                db.add(price)
            price.amount = amount
        for period_db_id, price in existing_prices.items():
            if period_db_id not in supplied_period_db_ids:
                db.delete(price)


def _sync_service_fields(db: Session, service: CatalogService, payload: CatalogServiceInput) -> None:
    existing_by_name = {field.field_name: field for field in service.fields}
    existing_by_id = {field.id: field for field in service.fields}
    retained_ids: set[str] = set()
    for item in payload.fields:
        field = existing_by_id.get(item.id or "") or existing_by_name.get(item.field_name)
        if field is None:
            field = ServiceField(service=service)
            db.add(field)
        elif field.id:
            retained_ids.add(field.id)
        field.field_name = item.field_name
        field.field_label = item.field_label
        field.field_type = item.field_type
        field.required = item.required
        field.placeholder = item.placeholder
        field.help_text = item.help_text
        field.validation_rules = dict(item.validation_rules)
        field.options = list(item.options)
        field.order = item.order
        field.sensitive = item.sensitive
        field.temporary_only = item.temporary_only
        field.is_active = item.is_active
    for field in existing_by_name.values():
        if field.id not in retained_ids and not any(
            item.field_name == field.field_name for item in payload.fields
        ):
            field.is_active = False


def _sync_service_instruction_and_workflow(
    db: Session, service: CatalogService, payload: CatalogServiceInput
) -> None:
    if service.instruction is None:
        service.instruction = ServiceInstruction(content=payload.instructions)
        db.add(service.instruction)
    else:
        service.instruction.content = payload.instructions

    if service.workflow is None:
        service.workflow = ServiceWorkflow()
        db.add(service.workflow)
    service.workflow.execution_type = payload.workflow.execution_type
    service.workflow.active = payload.workflow.active
    service.workflow.requires_manual_action = payload.workflow.requires_manual_action
    service.workflow.description = payload.workflow.description


def create_catalog_record(db: Session, payload: CatalogServiceInput) -> CatalogService:
    _ensure_slug_available(db, payload.slug)
    service = CatalogService()
    _set_service_fields(db, service, payload)
    db.add(service)
    _sync_service_options(db, service, payload)
    _sync_service_fields(db, service, payload)
    _sync_service_instruction_and_workflow(db, service, payload)
    db.flush()
    return service


def replace_catalog_record(
    db: Session,
    service: CatalogService,
    payload: CatalogServiceInput,
) -> CatalogService:
    _ensure_slug_available(db, payload.slug, excluding_id=service.id)
    _set_service_fields(db, service, payload)
    _sync_service_options(db, service, payload)
    _sync_service_fields(db, service, payload)
    _sync_service_instruction_and_workflow(db, service, payload)
    db.flush()
    return service


def archive_catalog_record(service: CatalogService) -> None:
    service.is_active = False
    if service.deleted_at is None:
        service.deleted_at = datetime.now(timezone.utc)


def set_catalog_record_active(service: CatalogService, active: bool) -> None:
    service.is_active = active
    if active:
        service.deleted_at = None


def _default_fields(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    slug = str(raw.get("slug", ""))
    if slug == "genshin-impact":
        return [
            {
                "field_name": "uid",
                "field_label": "UID",
                "field_type": "text",
                "required": True,
                "placeholder": "123456789",
                "order": 0,
            },
            {
                "field_name": "server",
                "field_label": "Server",
                "field_type": "select",
                "required": True,
                "options": ["Europe", "America", "Asia"],
                "order": 1,
            },
            {
                "field_name": "email",
                "field_label": "Email",
                "field_type": "email",
                "required": False,
                "order": 2,
            },
        ]
    if slug == "midjourney":
        return [
            {
                "field_name": "email",
                "field_label": "Email",
                "field_type": "email",
                "required": True,
                "order": 0,
            },
            {
                "field_name": "discord_username",
                "field_label": "Discord username",
                "field_type": "text",
                "required": True,
                "order": 1,
            },
        ]

    fields: list[dict[str, Any]] = [
        {
            "field_name": "email",
            "field_label": "Email",
            "field_type": "email",
            "required": True,
            "placeholder": "you@example.com",
            "order": 0,
        }
    ]
    if bool(raw.get("requires_access_token")):
        fields.append(
            {
                "field_name": "access_token",
                "field_label": raw.get("token_label") or "Temporary session/access data",
                "field_type": "secure_textarea",
                "required": True,
                "help_text": raw.get("token_hint"),
                "order": 1,
                "sensitive": True,
                "temporary_only": True,
            }
        )
    return fields


def _default_workflow(raw: Mapping[str, Any]) -> dict[str, Any]:
    slug = str(raw.get("slug", ""))
    if bool(raw.get("requires_access_token")):
        return {
            "execution_type": "browser_session",
            "active": True,
            "requires_manual_action": False,
            "description": "Temporary isolated browser session fulfillment.",
        }
    if slug == "genshin-impact":
        return {
            "execution_type": "uid_topup",
            "active": True,
            "requires_manual_action": True,
            "description": "Top up by UID and regional server.",
        }
    return {
        "execution_type": "manual",
        "active": True,
        "requires_manual_action": True,
        "description": "Manual fulfillment by an administrator.",
    }


def normalize_service_payload(raw: Mapping[str, Any], *, import_defaults: bool = False) -> dict[str, Any]:
    data = dict(raw)
    if "active" in data and "is_active" not in data:
        data["is_active"] = data.pop("active")
    if "logo_url" in data and "logo" not in data:
        data["logo"] = data.pop("logo_url")
    if "plans" in data and "levels" not in data:
        data["levels"] = data.pop("plans")
    if "tariffs" in data and "levels" not in data:
        data["levels"] = data.pop("tariffs")
    if "category_name" in data and "category" not in data:
        data["category"] = data.pop("category_name")

    if import_defaults:
        data.setdefault("description", "")
        data.setdefault("category", "Other")
        if not data.get("periods"):
            data["periods"] = [{"id": "1m", "name": "1 месяц", "duration": 30}]
        if not data.get("levels"):
            price = data.pop("price", "0.00")
            data["levels"] = [
                {"id": "basic", "name": "Базовый", "prices": {"1m": price}}
            ]
        if not data.get("fields"):
            data["fields"] = _default_fields(data)
        data.setdefault("instructions", "Укажите данные, необходимые для выполнения заказа.")
        data.setdefault("workflow", _default_workflow(data))
    return data


def seed_catalog(db: Session) -> None:
    """Upsert the 89-service starter catalog without overwriting CRM edits."""

    existing_by_slug = {
        service.slug: service
        for service in list_services(db, include_inactive=True, include_archived=True)
    }
    changed = False
    for index, raw_service in enumerate(DEFAULT_SERVICES):
        raw = normalize_service_payload(raw_service, import_defaults=True)
        raw.setdefault("sort_order", index)
        service = existing_by_slug.get(raw["slug"])
        if service is None:
            payload = CatalogServiceInput.model_validate(raw)
            service = create_catalog_record(db, payload)
            existing_by_slug[service.slug] = service
            changed = True
            continue

        if not service.logo_url and service.logo:
            service.logo_url = service.logo
            changed = True
        if service.category is None:
            service.category = get_or_create_category(db, name=str(raw.get("category") or "Other"))
            changed = True
        if not service.fields:
            configured_fields = raw.get("fields") or _default_fields(raw)
            field_payloads = [ServiceFieldInput.model_validate(item) for item in configured_fields]
            for field_payload in field_payloads:
                field = ServiceField(service=service)
                db.add(field)
                field.field_name = field_payload.field_name
                field.field_label = field_payload.field_label
                field.field_type = field_payload.field_type
                field.required = field_payload.required
                field.placeholder = field_payload.placeholder
                field.help_text = field_payload.help_text
                field.validation_rules = dict(field_payload.validation_rules)
                field.options = list(field_payload.options)
                field.order = field_payload.order
                field.sensitive = field_payload.sensitive
                field.temporary_only = field_payload.temporary_only
                field.is_active = field_payload.is_active
            changed = True
        if service.instruction is None:
            service.instruction = ServiceInstruction(content=service.instructions or str(raw["instructions"]))
            changed = True
        if service.workflow is None:
            workflow_payload = ServiceWorkflowInput.model_validate(
                raw.get("workflow") or _default_workflow(raw)
            )
            service.workflow = ServiceWorkflow(
                execution_type=workflow_payload.execution_type,
                active=workflow_payload.active,
                requires_manual_action=workflow_payload.requires_manual_action,
                description=workflow_payload.description,
            )
            changed = True
    if changed or db.new or db.dirty:
        db.commit()


def seed_catalog_if_empty(db: Session) -> None:
    """Compatibility alias; seeding is now an idempotent missing-record upsert."""

    seed_catalog(db)


def _catalog_objects_for_order(
    db: Session,
    order: Order,
) -> tuple[CatalogService | None, CatalogPlan | None, CatalogPeriod | None]:
    service = (
        get_service_by_id(db, order.catalog_service_id)
        if order.catalog_service_id
        else get_service(
            db, order.service_key, include_inactive=True, include_archived=True
        )
    )
    if service is None:
        return None, None, None

    plan = next(
        (
            item
            for item in service.plans
            if item.id == order.catalog_plan_id
            or (
                order.catalog_plan_id is None
                and (item.name == order.subscription_level or item.key == order.subscription_level)
            )
        ),
        None,
    )
    period = next(
        (
            item
            for item in service.periods
            if item.id == order.catalog_period_id
            or (
                order.catalog_period_id is None
                and (item.name == order.payment_period or item.key == order.payment_period)
            )
        ),
        None,
    )
    return service, plan, period


def backfill_order_catalog_refs(db: Session) -> None:
    orders = db.scalars(
        select(Order).where(
            (Order.catalog_service_id.is_(None))
            | (Order.catalog_plan_id.is_(None))
            | (Order.catalog_period_id.is_(None))
        )
    ).all()
    changed = False
    for order in orders:
        service, plan, period = _catalog_objects_for_order(db, order)
        if service is not None and order.catalog_service_id is None:
            order.catalog_service_id = service.id
            changed = True
        if plan is not None and order.catalog_plan_id is None:
            order.catalog_plan_id = plan.id
            changed = True
        if period is not None and order.catalog_period_id is None:
            order.catalog_period_id = period.id
            changed = True
    if changed:
        db.commit()


def next_order_reference(db: Session) -> str:
    references = db.scalars(select(Order.reference).where(Order.reference.like("NX-%"))).all()
    highest = 0
    for reference in references:
        if not reference:
            continue
        try:
            highest = max(highest, int(reference.removeprefix("NX-")))
        except ValueError:
            continue
    return f"NX-{highest + 1:06d}"


def _order_dict(db: Session, order: Order) -> tuple[dict[str, Any], CatalogService | None]:
    service, plan, period = _catalog_objects_for_order(db, order)
    data: dict[str, Any] = {
        "id": order.id,
        "reference": order.reference,
        "customer_email": order.customer_email,
        "service": order.service,
        "service_key": order.service_key,
        "subscription_level": order.subscription_level,
        "payment_period": order.payment_period,
        "amount": order.amount,
        "currency": order.currency,
        "status": order.status,
        "created_at": order.created_at,
        "submitted_at": order.submitted_at,
        "catalog_service_id": order.catalog_service_id or (service.id if service else None),
        "catalog_plan_id": order.catalog_plan_id or (plan.id if plan else None),
        "catalog_period_id": order.catalog_period_id or (period.id if period else None),
        "level_id": plan.key if plan else None,
        "period_id": period.key if period else None,
        "execution_status": order.execution_status,
    }
    return data, service


def order_to_admin_dict(db: Session, order: Order) -> dict[str, Any]:
    data, service = _order_dict(db, order)
    data.update(
        {
            "credentials_received": order.credentials_received,
            "custom_data": order.custom_data or {},
            "updated_at": order.updated_at,
            "workflow": (
                service.workflow.execution_type
                if service is not None and service.workflow is not None
                else None
            ),
            "execution_error": order.execution_error,
            "execution_result": order.execution_result,
            "executor_name": order.executor_name,
            "execution_started_at": order.execution_started_at,
            "execution_finished_at": order.execution_finished_at,
            "execution_attempts": order.execution_attempts,
            "execution_stop_requested": order.execution_stop_requested,
        }
    )
    return data


def order_to_public_dict(db: Session, order: Order) -> dict[str, Any]:
    data, service = _order_dict(db, order)
    data["catalog_service"] = (
        service_to_dict(service, include_inactive_options=True) if service else None
    )
    return data


def _secret_like_key(key: str) -> bool:
    normalized = key.strip().lower()
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    forbidden = {re.sub(r"[^a-z0-9]", "", name) for name in FORBIDDEN_COLUMNS}
    return compact in forbidden or any(
        marker in compact
        for marker in ("password", "accesstoken", "sessiontoken", "cookie", "authheader", "browserprofile")
    )


def _validate_field_value(field: ServiceField, raw: Any) -> Any:
    if field.field_type == "checkbox":
        if isinstance(raw, bool):
            value = raw
        elif isinstance(raw, str) and raw.strip().lower() in {"true", "1", "yes", "on"}:
            value = True
        elif isinstance(raw, str) and raw.strip().lower() in {"false", "0", "no", "off"}:
            value = False
        else:
            raise ValueError("must be a boolean")
        if field.required and not value:
            raise ValueError("must be accepted")
        return value

    if not isinstance(raw, str):
        raise ValueError("must be text")
    value = raw.strip()
    rules = field.validation_rules or {}
    if field.required and not value:
        raise ValueError("is required")
    if not value:
        return value
    if len(value) > 200_000:
        raise ValueError("is too long")
    min_length = rules.get("min_length")
    max_length = rules.get("max_length")
    if isinstance(min_length, int) and len(value) < min_length:
        raise ValueError(f"must contain at least {min_length} characters")
    if isinstance(max_length, int) and len(value) > max_length:
        raise ValueError(f"must contain at most {max_length} characters")
    pattern = rules.get("pattern")
    if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
        raise ValueError("has an invalid format")
    if field.field_type == "email":
        value = str(TypeAdapter(EmailStr).validate_python(value))
    if field.field_type == "select" and value not in (field.options or []):
        raise ValueError("must be one of the configured options")
    return value


def validate_dynamic_fields(
    service: CatalogService,
    submitted: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(ephemeral, durable)`` validated values.

    ``ephemeral`` may contain secrets and must only be handed to an executor.
    ``durable`` is limited to fields that are neither sensitive nor temporary.
    """

    configured = {field.field_name: field for field in service.fields if field.is_active}
    unknown = sorted(set(submitted) - set(configured))
    if unknown:
        raise CatalogValidationError(
            "Unknown customer fields", fields={key: "is not configured" for key in unknown}
        )

    errors: dict[str, str] = {}
    ephemeral: dict[str, Any] = {}
    durable: dict[str, Any] = {}
    for name, field in configured.items():
        raw = submitted.get(name)
        missing = raw is None or (isinstance(raw, str) and not raw.strip())
        if missing:
            if field.required:
                errors[name] = "is required"
            continue
        try:
            value = _validate_field_value(field, raw)
        except (ValueError, TypeError) as exc:
            errors[name] = str(exc)
            continue
        ephemeral[name] = value
        if not field.sensitive and not field.temporary_only and not _secret_like_key(name):
            durable[name] = value

    if errors:
        ephemeral.clear()
        durable.clear()
        raise CatalogValidationError("Customer field validation failed", fields=errors)
    return ephemeral, durable
