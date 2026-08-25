from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# These names are rejected from durable customer data even when an administrator
# accidentally configures a field incorrectly. The dynamic-field ``sensitive``
# flag is the primary policy; this is a second, deliberately conservative guard.
FORBIDDEN_COLUMNS = frozenset(
    {
        "access_token",
        "session_token",
        "session_data",
        "password",
        "passwords",
        "cookie",
        "cookies",
        "auth_token",
        "authorization",
        "authentication_header",
        "refresh_token",
        "browser_profile",
    }
)


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    services: Mapped[list[CatalogService]] = relationship(back_populates="category")


class CatalogService(Base):
    __tablename__ = "catalog_services"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # ``logo`` is retained for the original React contract. ``logo_url`` is the
    # canonical field and is mirrored to ``logo`` by catalog mutations.
    logo: Mapped[str] = mapped_column(Text, nullable=False, default="")
    logo_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    accent: Mapped[str] = mapped_column(String(16), nullable=False, default="#2563EB")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="RUB")
    # Legacy fields remain readable and are reflected into a generated secure
    # ServiceField during migration. No token value is ever stored here.
    requires_access_token: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    token_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    token_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    category: Mapped[Category | None] = relationship(back_populates="services", lazy="joined")
    plans: Mapped[list[CatalogPlan]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
        order_by="CatalogPlan.sort_order, CatalogPlan.name",
        lazy="selectin",
    )
    periods: Mapped[list[CatalogPeriod]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
        order_by="CatalogPeriod.sort_order, CatalogPeriod.name",
        lazy="selectin",
    )
    fields: Mapped[list[ServiceField]] = relationship(
        back_populates="service",
        cascade="all, delete-orphan",
        order_by="ServiceField.order, ServiceField.field_label",
        lazy="selectin",
    )
    instruction: Mapped[ServiceInstruction | None] = relationship(
        back_populates="service", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    workflow: Mapped[ServiceWorkflow | None] = relationship(
        back_populates="service", cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )


class CatalogPlan(Base):
    __tablename__ = "catalog_plans"
    __table_args__ = (UniqueConstraint("service_id", "key", name="uq_catalog_plan_service_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    service_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="RUB")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    service: Mapped[CatalogService] = relationship(back_populates="plans")
    prices: Mapped[list[CatalogPrice]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )


class CatalogPeriod(Base):
    __tablename__ = "catalog_periods"
    __table_args__ = (UniqueConstraint("service_id", "key", name="uq_catalog_period_service_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    service_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    service: Mapped[CatalogService] = relationship(back_populates="periods")


class CatalogPrice(Base):
    __tablename__ = "catalog_prices"
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_catalog_price_non_negative"),)

    plan_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_plans.id", ondelete="CASCADE"), primary_key=True
    )
    period_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_periods.id", ondelete="CASCADE"), primary_key=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    plan: Mapped[CatalogPlan] = relationship(back_populates="prices")
    period: Mapped[CatalogPeriod] = relationship(lazy="joined")


class ServiceField(Base):
    __tablename__ = "service_fields"
    __table_args__ = (
        UniqueConstraint("service_id", "field_name", name="uq_service_field_name"),
        CheckConstraint(
            "field_type IN ('text', 'email', 'textarea', 'secure_textarea', 'select', 'checkbox')",
            name="ck_service_field_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    service_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    field_label: Mapped[str] = mapped_column(String(160), nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), nullable=False, default="text")
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    placeholder: Mapped[str | None] = mapped_column(String(300), nullable=True)
    help_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    options: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    order: Mapped[int] = mapped_column("field_order", Integer, nullable=False, default=0)
    sensitive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    temporary_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    service: Mapped[CatalogService] = relationship(back_populates="fields")


class ServiceInstruction(Base):
    __tablename__ = "service_instructions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    service_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_services.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    service: Mapped[CatalogService] = relationship(back_populates="instruction")


class ServiceWorkflow(Base):
    __tablename__ = "service_workflows"
    __table_args__ = (
        CheckConstraint(
            "execution_type IN ('manual', 'browser_session', 'uid_topup', 'gift_code', 'api')",
            name="ck_service_workflow_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    service_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_services.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    execution_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_manual_action: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    service: Mapped[CatalogService] = relationship(back_populates="workflow")


class Order(Base):
    """CRM order record. Authentication/session secrets are forbidden here."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reference: Mapped[str | None] = mapped_column(String(24), nullable=True, unique=True, index=True)
    customer_email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    service: Mapped[str] = mapped_column(String(120), nullable=False)
    service_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subscription_level: Mapped[str | None] = mapped_column(String(80), nullable=True)
    payment_period: Mapped[str | None] = mapped_column(String(80), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="RUB")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="В работе", index=True)
    credentials_received: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Only values from non-sensitive, non-temporary ServiceFields are admitted.
    custom_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Snapshots above remain authoritative history; these nullable references
    # provide stable identities even if a plan is later renamed or archived.
    catalog_service_id: Mapped[str | None] = mapped_column(
        ForeignKey("catalog_services.id", ondelete="SET NULL"), nullable=True, index=True
    )
    catalog_plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("catalog_plans.id", ondelete="SET NULL"), nullable=True, index=True
    )
    catalog_period_id: Mapped[str | None] = mapped_column(
        ForeignKey("catalog_periods.id", ondelete="SET NULL"), nullable=True, index=True
    )

    execution_status: Mapped[str] = mapped_column(
        String(48), nullable=False, default="pending", index=True
    )
    execution_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    executor_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    execution_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_stop_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    catalog_service: Mapped[CatalogService | None] = relationship(
        foreign_keys=[catalog_service_id], lazy="selectin"
    )
    catalog_plan: Mapped[CatalogPlan | None] = relationship(
        foreign_keys=[catalog_plan_id], lazy="selectin"
    )
    catalog_period: Mapped[CatalogPeriod | None] = relationship(
        foreign_keys=[catalog_period_id], lazy="selectin"
    )


assert FORBIDDEN_COLUMNS.isdisjoint(set(Order.__table__.columns.keys())), (
    "Order model must not define columns for secrets"
)
