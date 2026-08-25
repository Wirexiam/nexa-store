from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import settings
from .database import Base, SessionLocal, engine
from .routers import admin, catalog, orders
from .seed import seed_if_empty

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(orders.router)
app.include_router(admin.router)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}


FRONTEND_DIST = (Path(__file__).resolve().parents[2] / "frontend" / "dist").resolve()


def _frontend_response(frontend_path: str) -> FileResponse:
    """Serve a built asset or the React entry point without exposing files outside dist."""
    if frontend_path == "api" or frontend_path.startswith("api/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    index_path = FRONTEND_DIST / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    requested_path = (FRONTEND_DIST / frontend_path).resolve()
    if requested_path.is_relative_to(FRONTEND_DIST) and requested_path.is_file():
        return FileResponse(requested_path)
    return FileResponse(index_path)


@app.get("/{frontend_path:path}", include_in_schema=False)
def frontend_app(frontend_path: str):
    return _frontend_response(frontend_path)
