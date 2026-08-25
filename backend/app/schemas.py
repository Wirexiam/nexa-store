from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from .models import FORBIDDEN_COLUMNS

STATUSES = ("В работе", "Оплачено", "Отменено", "Ошибка")
EXECUTION_STATUSES = ("pending", "running", "action_required", "completed", "failed", "stopped")
FIELD_TYPES = ("text", "email", "textarea", "secure_textarea", "select", "checkbox")
WORKFLOW_TYPES = ("manual", "browser_session", "uid_topup", "gift_code", "api")
KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FIELD_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
ACCENT_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_PRICE = Decimal("9999999999.99")


class CRMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    def model_dump(self, *args, **kwargs):  # type: ignore[override]
        data = super().model_dump(*args, **kwargs)
        leaked = FORBIDDEN_COLUMNS.intersection(data)
        if leaked:
            raise ValueError(f"Refusing to serialize secret fields: {sorted(leaked)}")
        return data


def _catalog_key(value: str) -> str:
    normalized = value.strip().lower()
    if not KEY_PATTERN.fullmatch(normalized):
        raise ValueError("Use lowercase letters, digits and single hyphens")
    return normalized


def _is_secret_like_field_name(value: str) -> bool:
    normalized = value.strip().lower()
    compact = re.sub(r"[^a-z0-9]", "", normalized)
    forbidden_compact = {re.sub(r"[^a-z0-9]", "", item) for item in FORBIDDEN_COLUMNS}
    if compact in forbidden_compact:
        return True
    return any(
        marker in compact
        for marker in ("password", "accesstoken", "sessiontoken", "cookie", "authheader", "browserprofile")
    )


def _validate_price(amount: Decimal) -> Decimal:
    if not amount.is_finite() or amount < 0 or amount > MAX_PRICE:
        raise ValueError("Prices must be finite values between 0 and 9999999999.99")
    if amount.as_tuple().exponent < -2:
        raise ValueError("Prices may have at most two decimal places")
    return amount


class CategoryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        return _catalog_key(value)


class CategoryOut(CRMModel):
    id: str
    name: str
    slug: str
    created_at: datetime | None = None


class CatalogPeriodInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(validation_alias=AliasChoices("id", "key", "slug"), min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    duration: int | None = Field(
        default=None, validation_alias=AliasChoices("duration", "duration_days"), ge=1, le=100_000
    )
    is_active: bool = Field(default=True, validation_alias=AliasChoices("is_active", "active"))
    sort_order: int = Field(
        default=0, validation_alias=AliasChoices("sort_order", "order"), ge=0, le=1_000_000
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _catalog_key(value)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class CatalogPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str = Field(validation_alias=AliasChoices("id", "key", "slug"), min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=4000)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    prices: dict[str, Decimal] = Field(default_factory=dict)
    price: Decimal | None = None
    is_active: bool = Field(default=True, validation_alias=AliasChoices("is_active", "active"))
    sort_order: int = Field(
        default=0, validation_alias=AliasChoices("sort_order", "order"), ge=0, le=1_000_000
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _catalog_key(value)

    @field_validator("name", "description")
    @classmethod
    def clean_strings(cls, value: str) -> str:
        return value.strip()

    @field_validator("currency")
    @classmethod
    def validate_optional_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if not value.isascii() or not value.isalpha():
            raise ValueError("Currency must contain ASCII letters")
        return value

    @field_validator("price")
    @classmethod
    def validate_single_price(cls, amount: Decimal | None) -> Decimal | None:
        return None if amount is None else _validate_price(amount)

    @field_validator("prices")
    @classmethod
    def validate_prices(cls, prices: dict[str, Decimal]) -> dict[str, Decimal]:
        normalized: dict[str, Decimal] = {}
        for period_id, amount in prices.items():
            key = _catalog_key(period_id)
            normalized[key] = _validate_price(amount)
        return normalized


class ServiceFieldInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str | None = Field(default=None, max_length=36)
    field_name: str = Field(
        validation_alias=AliasChoices("field_name", "name", "key"), min_length=1, max_length=64
    )
    field_label: str = Field(
        validation_alias=AliasChoices("field_label", "label"), min_length=1, max_length=160
    )
    field_type: Literal["text", "email", "textarea", "secure_textarea", "select", "checkbox"] = Field(
        default="text", validation_alias=AliasChoices("field_type", "type")
    )
    required: bool = False
    placeholder: str | None = Field(default=None, max_length=300)
    help_text: str | None = Field(default=None, max_length=4000)
    validation_rules: dict[str, Any] = Field(default_factory=dict)
    options: list[str] = Field(default_factory=list)
    order: int = Field(
        default=0, validation_alias=AliasChoices("order", "sort_order"), ge=0, le=1_000_000
    )
    sensitive: bool = False
    temporary_only: bool = False
    is_active: bool = Field(default=True, validation_alias=AliasChoices("is_active", "active"))

    @field_validator("field_name")
    @classmethod
    def validate_field_name(cls, value: str) -> str:
        value = value.strip().lower()
        if not FIELD_NAME_PATTERN.fullmatch(value):
            raise ValueError("Field name must use lowercase letters, digits and underscores")
        return value

    @field_validator("field_label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        return value.strip()

    @field_validator("options")
    @classmethod
    def clean_options(cls, options: list[str]) -> list[str]:
        cleaned = [item.strip() for item in options if item.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Select options must be unique")
        if len(cleaned) > 200:
            raise ValueError("A field may have at most 200 options")
        return cleaned

    @model_validator(mode="after")
    def validate_security_and_rules(self):
        rule_options = self.validation_rules.get("options")
        if not self.options and isinstance(rule_options, list):
            self.options = self.clean_options([str(item) for item in rule_options])
        if self.field_type == "select" and not self.options:
            raise ValueError("Select fields require options")
        pattern = self.validation_rules.get("pattern")
        if pattern is not None:
            if not isinstance(pattern, str) or len(pattern) > 500:
                raise ValueError("Validation pattern must be a string up to 500 characters")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValueError("Invalid validation pattern") from exc
        for key in ("min_length", "max_length"):
            if key in self.validation_rules:
                value = self.validation_rules[key]
                if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 100_000:
                    raise ValueError(f"{key} must be an integer between 0 and 100000")
        if (
            "min_length" in self.validation_rules
            and "max_length" in self.validation_rules
            and self.validation_rules["min_length"] > self.validation_rules["max_length"]
        ):
            raise ValueError("min_length may not exceed max_length")

        if self.field_type == "secure_textarea":
            self.sensitive = True
            self.temporary_only = True
        if _is_secret_like_field_name(self.field_name) and not self.sensitive:
            raise ValueError("Authentication/session fields must be marked sensitive")
        return self


class ServiceInstructionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(default="", max_length=10_000)


class ServiceWorkflowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_type: Literal["manual", "browser_session", "uid_topup", "gift_code", "api"] = "manual"
    active: bool = True
    requires_manual_action: bool = True
    description: str = Field(default="", max_length=4000)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        return value.strip()


class CatalogServiceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=64)
    logo: str = Field(default="", validation_alias=AliasChoices("logo", "logo_url"), max_length=2048)
    description: str = Field(default="", max_length=4000)
    accent: str = Field(default="#2563EB", max_length=16)
    currency: str = Field(default="RUB", min_length=3, max_length=8)
    category_id: str | None = Field(default=None, max_length=36)
    category: str | None = Field(
        default=None, validation_alias=AliasChoices("category", "category_name"), max_length=120
    )
    category_slug: str | None = Field(default=None, max_length=64)
    requires_access_token: bool = False
    token_label: str | None = Field(default=None, max_length=120)
    token_hint: str | None = Field(default=None, max_length=2000)
    instructions: str = Field(default="", max_length=10_000)
    instruction: ServiceInstructionInput | None = None
    is_active: bool = Field(default=True, validation_alias=AliasChoices("is_active", "active"))
    sort_order: int = Field(
        default=0, validation_alias=AliasChoices("sort_order", "order"), ge=0, le=1_000_000
    )
    levels: list[CatalogPlanInput] = Field(
        default_factory=list, validation_alias=AliasChoices("levels", "plans", "tariffs")
    )
    periods: list[CatalogPeriodInput] = Field(default_factory=list)
    fields: list[ServiceFieldInput] = Field(default_factory=list)
    workflow: ServiceWorkflowInput = Field(default_factory=ServiceWorkflowInput)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        return _catalog_key(value)

    @field_validator("category_slug")
    @classmethod
    def validate_category_slug(cls, value: str | None) -> str | None:
        return None if value is None else _catalog_key(value)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("logo")
    @classmethod
    def validate_logo(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return ""
        if value.startswith("/uploads/") and ".." not in value.split("/"):
            return value
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Logo must be an HTTPS URL or a root-relative /uploads/... path")
        return value

    @field_validator("accent")
    @classmethod
    def validate_accent(cls, value: str) -> str:
        if not ACCENT_PATTERN.fullmatch(value):
            raise ValueError("Accent must be a six-digit hex color")
        return value.upper()

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        value = value.strip().upper()
        if not value.isascii() or not value.isalpha():
            raise ValueError("Currency must contain ASCII letters")
        return value

    @model_validator(mode="after")
    def validate_matrix(self):
        # Keep the old string field and the new one-to-one record synchronized.
        if self.instruction is not None:
            self.instructions = self.instruction.content

        period_ids = [period.id for period in self.periods]
        level_ids = [level.id for level in self.levels]
        field_names = [field.field_name for field in self.fields]
        if len(period_ids) != len(set(period_ids)):
            raise ValueError("Period IDs must be unique")
        if len(level_ids) != len(set(level_ids)):
            raise ValueError("Plan IDs must be unique")
        if len(field_names) != len(set(field_names)):
            raise ValueError("Field names must be unique")

        known_periods = set(period_ids)
        active_periods = {period.id for period in self.periods if period.is_active}
        active_levels = [level for level in self.levels if level.is_active]
        if self.is_active and (not active_levels or not active_periods):
            raise ValueError("An active service needs at least one active plan and period")

        for level in self.levels:
            if level.price is not None and not level.prices:
                level.prices = {period_id: level.price for period_id in period_ids}
            unknown = set(level.prices) - known_periods
            if unknown:
                raise ValueError(f"Plan {level.id} has prices for unknown periods: {sorted(unknown)}")
            missing = active_periods - set(level.prices) if level.is_active else set()
            if missing:
                raise ValueError(f"Plan {level.id} is missing prices for periods: {sorted(missing)}")
            if level.currency is None:
                level.currency = self.currency

        if self.requires_access_token and not any(field.sensitive for field in self.fields):
            self.fields.append(
                ServiceFieldInput(
                    field_name="access_token",
                    field_label=self.token_label or "Access token",
                    field_type="secure_textarea",
                    required=True,
                    help_text=self.token_hint,
                    order=max((field.order for field in self.fields), default=0) + 1,
                )
            )
        self.requires_access_token = any(field.sensitive for field in self.fields)
        return self


class CatalogPeriodOut(BaseModel):
    record_id: str | None = None
    id: str
    key: str
    name: str
    duration: int | None = None
    is_active: bool
    active: bool
    sort_order: int


class CatalogPlanOut(BaseModel):
    record_id: str | None = None
    id: str
    key: str
    name: str
    description: str = ""
    currency: str = "RUB"
    price: Decimal | None = None
    prices: dict[str, Decimal]
    is_active: bool
    active: bool
    sort_order: int


class ServiceFieldOut(BaseModel):
    id: str
    field_name: str
    field_label: str
    field_type: str
    required: bool
    placeholder: str | None
    help_text: str | None
    validation_rules: dict[str, Any]
    options: list[str]
    order: int
    sensitive: bool
    temporary_only: bool
    is_active: bool
    active: bool


class ServiceInstructionOut(BaseModel):
    id: str | None = None
    content: str
    updated_at: datetime | None = None


class ServiceWorkflowOut(BaseModel):
    id: str | None = None
    execution_type: str
    active: bool
    requires_manual_action: bool
    description: str


class CatalogServiceOut(BaseModel):
    id: str
    key: str
    slug: str
    name: str
    logo: str
    logo_url: str
    description: str
    tagline: str
    accent: str
    currency: str
    category_id: str | None
    category: CategoryOut | None
    category_name: str | None
    requires_access_token: bool
    token_label: str | None
    token_hint: str | None
    instructions: str
    instruction: ServiceInstructionOut
    workflow: ServiceWorkflowOut
    fields: list[ServiceFieldOut]
    is_active: bool
    active: bool
    sort_order: int
    levels: list[CatalogPlanOut]
    plans: list[CatalogPlanOut]
    periods: list[CatalogPeriodOut]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ServiceActiveUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool


class BulkCatalogImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["json", "csv"] = "json"
    data: list[dict[str, Any]] | str


class ImportIssue(BaseModel):
    row: int
    slug: str | None = None
    error: str


class BulkCatalogImportReport(BaseModel):
    imported: int
    skipped: int
    duplicates: list[str] = Field(default_factory=list)
    errors: list[ImportIssue] = Field(default_factory=list)


class OrderOut(CRMModel):
    id: str
    reference: str | None = None
    customer_email: str | None
    service: str
    service_key: str
    subscription_level: str | None
    payment_period: str | None
    amount: Decimal
    currency: str
    status: str
    credentials_received: bool
    custom_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    catalog_service_id: str | None = None
    catalog_plan_id: str | None = None
    catalog_period_id: str | None = None
    level_id: str | None = None
    period_id: str | None = None
    workflow: str | None = None
    execution_status: str = "pending"
    execution_error: str | None = None
    execution_result: str | None = None
    executor_name: str | None = None
    execution_started_at: datetime | None = None
    execution_finished_at: datetime | None = None
    execution_attempts: int = 0
    execution_stop_requested: bool = False


class OrderPublic(CRMModel):
    id: str
    reference: str | None = None
    customer_email: str | None
    service: str
    service_key: str
    subscription_level: str | None
    payment_period: str | None
    amount: Decimal
    currency: str
    status: str
    created_at: datetime
    submitted_at: datetime | None = None
    catalog_service_id: str | None = None
    catalog_plan_id: str | None = None
    catalog_period_id: str | None = None
    level_id: str | None = None
    period_id: str | None = None
    execution_status: str = "pending"
    catalog_service: CatalogServiceOut | None = None


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    service_key: str = Field(validation_alias=AliasChoices("service_key", "service_id", "service"))
    level_id: str | None = Field(default=None, validation_alias=AliasChoices("level_id", "plan_id", "tariff_id"))
    period_id: str | None = None
    customer_email: EmailStr | None = Field(default=None, validation_alias=AliasChoices("customer_email", "email"))


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class OrderSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    level_id: str | None = None
    period_id: str | None = None
    access_token: str | None = Field(default=None, max_length=200_000)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def merge_field_aliases(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        data = dict(raw)
        fields = data.pop("fields", None)
        custom = data.get("custom_fields")
        if fields is not None and not isinstance(fields, dict):
            raise ValueError("fields must be an object")
        if custom is not None and not isinstance(custom, dict):
            raise ValueError("custom_fields must be an object")
        if fields is not None and custom is not None:
            conflicts = {key for key in fields if key in custom and fields[key] != custom[key]}
            if conflicts:
                raise ValueError(f"Conflicting field values: {sorted(conflicts)}")
            data["custom_fields"] = {**fields, **custom}
        elif fields is not None:
            data["custom_fields"] = fields
        return data

    @field_validator("custom_fields")
    @classmethod
    def limit_custom_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        if len(values) > 100:
            raise ValueError("At most 100 custom fields are accepted")
        for key in values:
            if not isinstance(key, str) or not FIELD_NAME_PATTERN.fullmatch(key):
                raise ValueError("Invalid custom field name")
        return values
