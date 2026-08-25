from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..catalog import (
    CatalogConflictError,
    CatalogValidationError,
    archive_catalog_record,
    create_catalog_record,
    create_category,
    get_category,
    get_service,
    list_categories,
    list_services,
    normalize_service_payload,
    replace_catalog_record,
    replace_category,
    service_to_dict,
    set_catalog_record_active,
)
from ..database import get_db
from ..models import CatalogService, Category
from ..schemas import (
    BulkCatalogImportReport,
    CatalogServiceInput,
    CatalogServiceOut,
    CategoryInput,
    CategoryOut,
    ServiceActiveUpdate,
)
from ..security import require_admin

router = APIRouter(
    prefix="/api/admin",
    tags=["admin catalog"],
    dependencies=[Depends(require_admin)],
)


def _not_found(kind: str = "Service") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{kind} not found")


def _validation_detail(exc: ValidationError | CatalogValidationError) -> Any:
    if isinstance(exc, CatalogValidationError) and exc.fields:
        return {"message": str(exc), "fields": exc.fields}
    if isinstance(exc, ValidationError):
        return exc.errors(include_url=False)
    return str(exc)


def _service_input_snapshot(service: CatalogService) -> dict[str, Any]:
    data = service_to_dict(service, include_inactive_options=True)
    return {
        "name": data["name"],
        "slug": data["slug"],
        "logo": data["logo_url"],
        "description": data["description"],
        "accent": data["accent"],
        "currency": data["currency"],
        "category_id": data["category_id"],
        "requires_access_token": data["requires_access_token"],
        "token_label": data["token_label"],
        "token_hint": data["token_hint"],
        "instructions": data["instructions"],
        "is_active": data["is_active"],
        "sort_order": data["sort_order"],
        "levels": [
            {
                "id": item["id"],
                "name": item["name"],
                "description": item["description"],
                "currency": item["currency"],
                "prices": item["prices"],
                "is_active": item["is_active"],
                "sort_order": item["sort_order"],
            }
            for item in data["levels"]
        ],
        "periods": [
            {
                "id": item["id"],
                "name": item["name"],
                "duration": item["duration"],
                "is_active": item["is_active"],
                "sort_order": item["sort_order"],
            }
            for item in data["periods"]
        ],
        "fields": [
            {
                "id": item["id"],
                "field_name": item["field_name"],
                "field_label": item["field_label"],
                "field_type": item["field_type"],
                "required": item["required"],
                "placeholder": item["placeholder"],
                "help_text": item["help_text"],
                "validation_rules": item["validation_rules"],
                "options": item["options"],
                "order": item["order"],
                "sensitive": item["sensitive"],
                "temporary_only": item["temporary_only"],
                "is_active": item["is_active"],
            }
            for item in data["fields"]
        ],
        "workflow": {
            "execution_type": data["workflow"]["execution_type"],
            "active": data["workflow"]["active"],
            "requires_manual_action": data["workflow"]["requires_manual_action"],
            "description": data["workflow"]["description"],
        },
    }


@router.get("/services", response_model=list[CatalogServiceOut])
@router.get("/catalog/services", response_model=list[CatalogServiceOut], include_in_schema=False)
def admin_list_services(
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    include_archived: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    services = list_services(
        db,
        include_inactive=True,
        include_archived=include_archived,
        query=q,
        category=category,
    )
    if active is not None:
        services = [service for service in services if service.is_active is active]
    return [service_to_dict(service, include_inactive_options=True) for service in services]


@router.get("/services/{identifier}", response_model=CatalogServiceOut)
@router.get(
    "/catalog/services/{identifier}", response_model=CatalogServiceOut, include_in_schema=False
)
def admin_get_service(identifier: str, db: Session = Depends(get_db)):
    service = get_service(db, identifier, include_inactive=True, include_archived=True)
    if service is None:
        raise _not_found()
    return service_to_dict(service, include_inactive_options=True)


@router.post("/services", response_model=CatalogServiceOut, status_code=status.HTTP_201_CREATED)
@router.post(
    "/catalog/services",
    response_model=CatalogServiceOut,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def admin_create_service(raw: dict[str, Any], db: Session = Depends(get_db)):
    try:
        payload = CatalogServiceInput.model_validate(
            normalize_service_payload(raw, import_defaults=True)
        )
        service = create_catalog_record(db, payload)
        db.commit()
    except CatalogConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (CatalogValidationError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_validation_detail(exc),
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Catalog conflict") from exc
    service = get_service(db, service.id, include_inactive=True, include_archived=True)
    assert service is not None
    return service_to_dict(service, include_inactive_options=True)


@router.put("/services/{identifier}", response_model=CatalogServiceOut)
@router.put(
    "/catalog/services/{identifier}", response_model=CatalogServiceOut, include_in_schema=False
)
def admin_replace_service(
    identifier: str,
    raw: dict[str, Any],
    db: Session = Depends(get_db),
):
    service = get_service(db, identifier, include_inactive=True, include_archived=True)
    if service is None:
        raise _not_found()
    incoming = normalize_service_payload(raw)
    merged = _service_input_snapshot(service)
    if ("category" in incoming or "category_slug" in incoming) and "category_id" not in incoming:
        merged.pop("category_id", None)
    merged.update(incoming)
    try:
        payload = CatalogServiceInput.model_validate(merged)
        replace_catalog_record(db, service, payload)
        db.commit()
    except CatalogConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (CatalogValidationError, ValidationError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_validation_detail(exc),
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Catalog conflict") from exc
    refreshed = get_service(db, service.id, include_inactive=True, include_archived=True)
    assert refreshed is not None
    return service_to_dict(refreshed, include_inactive_options=True)


@router.patch("/services/{identifier}/active", response_model=CatalogServiceOut)
@router.patch(
    "/catalog/services/{identifier}/active",
    response_model=CatalogServiceOut,
    include_in_schema=False,
)
def admin_set_service_active(
    identifier: str,
    payload: ServiceActiveUpdate,
    db: Session = Depends(get_db),
):
    service = get_service(db, identifier, include_inactive=True, include_archived=True)
    if service is None:
        raise _not_found()
    set_catalog_record_active(service, payload.active)
    db.commit()
    refreshed = get_service(db, service.id, include_inactive=True, include_archived=True)
    assert refreshed is not None
    return service_to_dict(refreshed, include_inactive_options=True)


@router.delete("/services/{identifier}", status_code=status.HTTP_204_NO_CONTENT)
@router.delete(
    "/catalog/services/{identifier}",
    status_code=status.HTTP_204_NO_CONTENT,
    include_in_schema=False,
)
def admin_delete_service(identifier: str, db: Session = Depends(get_db)) -> None:
    service = get_service(db, identifier, include_inactive=True, include_archived=True)
    if service is None:
        raise _not_found()
    archive_catalog_record(service)
    db.commit()


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    raise ValueError("must be true or false")


def _parse_csv(data: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(data.lstrip("\ufeff")))
    if not reader.fieldnames:
        raise ValueError("CSV header is missing")
    records: list[dict[str, Any]] = []
    for row in reader:
        record: dict[str, Any] = {
            str(key).strip(): value.strip()
            for key, value in row.items()
            if key is not None and value is not None and value.strip() != ""
        }
        for bool_key in ("active", "is_active", "requires_access_token"):
            if bool_key in record:
                record[bool_key] = _parse_bool(str(record[bool_key]))
        for json_key in ("levels", "plans", "tariffs", "periods", "fields", "workflow"):
            if json_key in record:
                record[json_key] = json.loads(str(record[json_key]))
        records.append(record)
    return records


async def _read_import_records(request: Request) -> list[dict[str, Any]]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    raw_body = await request.body()
    if len(raw_body) > 5_000_000:
        raise ValueError("Import payload exceeds 5 MB")

    if content_type in {"text/csv", "application/csv"}:
        return _parse_csv(raw_body.decode("utf-8-sig"))

    try:
        body = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid JSON import payload") from exc

    if isinstance(body, list):
        records = body
    elif isinstance(body, dict) and "data" in body:
        import_format = str(body.get("format", "json")).lower()
        payload = body["data"]
        if import_format == "csv":
            if not isinstance(payload, str):
                raise ValueError("CSV import data must be a string")
            return _parse_csv(payload)
        if import_format != "json":
            raise ValueError("Import format must be json or csv")
        if isinstance(payload, str):
            payload = json.loads(payload)
        records = payload
    elif isinstance(body, dict):
        records = [body]
    else:
        raise ValueError("JSON import data must be an object or array")
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ValueError("JSON import data must be an array of objects")
    if len(records) > 10_000:
        raise ValueError("An import may contain at most 10000 services")
    return records


@router.post("/services/import", response_model=BulkCatalogImportReport)
@router.post("/catalog/import", response_model=BulkCatalogImportReport, include_in_schema=False)
async def admin_import_services(request: Request, db: Session = Depends(get_db)):
    try:
        records = await _read_import_records(request)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    existing = {
        service.slug
        for service in list_services(db, include_inactive=True, include_archived=True)
    }
    imported = 0
    duplicates: list[str] = []
    errors: list[dict[str, Any]] = []
    for row_number, raw in enumerate(records, start=1):
        slug = str(raw.get("slug", "")).strip().lower() or None
        if slug is not None and slug in existing:
            duplicates.append(slug)
            continue
        try:
            payload = CatalogServiceInput.model_validate(
                normalize_service_payload(raw, import_defaults=True)
            )
            if payload.slug in existing:
                duplicates.append(payload.slug)
                continue
            with db.begin_nested():
                create_catalog_record(db, payload)
                db.flush()
            existing.add(payload.slug)
            imported += 1
        except CatalogConflictError:
            duplicate_slug = slug or "<unknown>"
            duplicates.append(duplicate_slug)
            existing.add(duplicate_slug)
        except (CatalogValidationError, ValidationError, IntegrityError, ValueError) as exc:
            errors.append(
                {"row": row_number, "slug": slug, "error": str(_validation_detail(exc))}
            )
    db.commit()
    return {
        "imported": imported,
        "skipped": len(duplicates) + len(errors),
        "duplicates": duplicates,
        "errors": errors,
    }


@router.get("/categories", response_model=list[CategoryOut])
def admin_list_categories(db: Session = Depends(get_db)):
    return list_categories(db)


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def admin_create_category(payload: CategoryInput, db: Session = Depends(get_db)):
    try:
        category = create_category(db, payload)
        db.commit()
        db.refresh(category)
        return category
    except CatalogConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.put("/categories/{identifier}", response_model=CategoryOut)
def admin_replace_category(
    identifier: str, payload: CategoryInput, db: Session = Depends(get_db)
):
    category = get_category(db, identifier)
    if category is None:
        raise _not_found("Category")
    try:
        replace_category(db, category, payload)
        db.commit()
        db.refresh(category)
        return category
    except CatalogConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/categories/{identifier}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_category(identifier: str, db: Session = Depends(get_db)) -> None:
    category = get_category(db, identifier)
    if category is None:
        raise _not_found("Category")
    service_count = db.scalar(
        select(func.count(CatalogService.id)).where(CatalogService.category_id == category.id)
    )
    if service_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category is still used by services",
        )
    db.delete(category)
    db.commit()
