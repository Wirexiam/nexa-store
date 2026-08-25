from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..catalog import get_service, list_categories, public_catalog, service_to_dict
from ..database import get_db
from ..schemas import CatalogServiceOut, CategoryOut, ServiceFieldOut

router = APIRouter(tags=["catalog"])


@router.get("/api/catalog/services", response_model=list[CatalogServiceOut])
@router.get("/api/services", response_model=list[CatalogServiceOut], include_in_schema=False)
@router.get("/services", response_model=list[CatalogServiceOut], include_in_schema=False)
def list_public_services(db: Session = Depends(get_db)):
    return public_catalog(db)


@router.get("/api/categories", response_model=list[CategoryOut])
@router.get("/categories", response_model=list[CategoryOut], include_in_schema=False)
def list_public_categories(db: Session = Depends(get_db)):
    return list_categories(db)


def _public_service(identifier: str, db: Session) -> dict:
    service = get_service(db, identifier)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service_to_dict(service)


@router.get(
    "/api/catalog/services/{identifier}/fields", response_model=list[ServiceFieldOut]
)
@router.get(
    "/api/services/{identifier}/fields",
    response_model=list[ServiceFieldOut],
    include_in_schema=False,
)
@router.get(
    "/services/{identifier}/fields",
    response_model=list[ServiceFieldOut],
    include_in_schema=False,
)
def get_public_service_fields(identifier: str, db: Session = Depends(get_db)):
    return _public_service(identifier, db)["fields"]


@router.get("/api/catalog/services/{identifier}", response_model=CatalogServiceOut)
@router.get(
    "/api/services/{identifier}", response_model=CatalogServiceOut, include_in_schema=False
)
@router.get("/services/{identifier}", response_model=CatalogServiceOut, include_in_schema=False)
def get_public_service(identifier: str, db: Session = Depends(get_db)):
    return _public_service(identifier, db)
