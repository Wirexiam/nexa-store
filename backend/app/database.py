from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {"pool_pre_ping": True}


engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SQLITE_ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "catalog_services": {
        "logo_url": "TEXT NOT NULL DEFAULT ''",
        "category_id": "VARCHAR(36)",
    },
    "catalog_plans": {
        "description": "TEXT NOT NULL DEFAULT ''",
        "currency": "VARCHAR(8) NOT NULL DEFAULT 'RUB'",
    },
    "catalog_periods": {
        "duration": "INTEGER",
    },
    "orders": {
        "reference": "VARCHAR(24)",
        "catalog_service_id": "VARCHAR(36)",
        "catalog_plan_id": "VARCHAR(36)",
        "catalog_period_id": "VARCHAR(36)",
        "custom_data": "JSON NOT NULL DEFAULT '{}'",
        "execution_status": "VARCHAR(48) NOT NULL DEFAULT 'pending'",
        "execution_error": "TEXT",
        "execution_result": "TEXT",
        "executor_name": "VARCHAR(120)",
        "execution_started_at": "DATETIME",
        "execution_finished_at": "DATETIME",
        "execution_attempts": "INTEGER NOT NULL DEFAULT 0",
        "execution_stop_requested": "BOOLEAN NOT NULL DEFAULT 0",
    },
}


def migrate_sqlite_schema(target_engine: Engine = engine) -> None:
    """Idempotently extend databases created by the original MVP.

    SQLAlchemy's ``create_all`` creates new tables but intentionally does not
    alter existing ones. Nexa Store originally shipped without a migration
    framework, so these fixed additive changes are applied at startup. No table
    is rebuilt and no user data is deleted. Production non-SQLite deployments
    should use their normal migration tooling.
    """

    if target_engine.dialect.name != "sqlite":
        return

    inspector = inspect(target_engine)
    tables = set(inspector.get_table_names())
    with target_engine.begin() as connection:
        for table_name, additions in SQLITE_ADDITIVE_COLUMNS.items():
            if table_name not in tables:
                continue
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, sql_type in additions.items():
                if column_name not in existing:
                    # Identifiers are fixed constants above, never user input.
                    connection.exec_driver_sql(
                        f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {sql_type}'
                    )

        if "catalog_services" in tables:
            connection.exec_driver_sql(
                "UPDATE catalog_services SET logo_url = logo "
                "WHERE (logo_url IS NULL OR logo_url = '') AND logo IS NOT NULL"
            )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_catalog_services_category_id "
                "ON catalog_services (category_id)"
            )

        if "catalog_plans" in tables:
            connection.exec_driver_sql(
                "UPDATE catalog_plans SET currency = COALESCE(("
                "SELECT currency FROM catalog_services "
                "WHERE catalog_services.id = catalog_plans.service_id"
                "), 'RUB') WHERE currency IS NULL OR currency = ''"
            )

        if "orders" in tables:
            for column_name in (
                "catalog_service_id",
                "catalog_plan_id",
                "catalog_period_id",
                "execution_status",
            ):
                connection.exec_driver_sql(
                    f"CREATE INDEX IF NOT EXISTS ix_orders_{column_name} ON orders ({column_name})"
                )
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_orders_reference ON orders (reference)"
            )
            connection.exec_driver_sql(
                "UPDATE orders SET execution_status = 'pending' "
                "WHERE execution_status IS NULL OR execution_status = ''"
            )
            connection.exec_driver_sql(
                "UPDATE orders SET custom_data = '{}' WHERE custom_data IS NULL"
            )

            rows = connection.exec_driver_sql(
                "SELECT id FROM orders WHERE reference IS NULL OR reference = '' "
                "ORDER BY created_at, id"
            ).fetchall()
            used_rows = connection.exec_driver_sql(
                "SELECT reference FROM orders WHERE reference LIKE 'NX-%'"
            ).fetchall()
            used_numbers: set[int] = set()
            for (reference,) in used_rows:
                try:
                    used_numbers.add(int(str(reference).removeprefix("NX-")))
                except ValueError:
                    continue
            next_number = 1
            for (order_id,) in rows:
                while next_number in used_numbers:
                    next_number += 1
                reference = f"NX-{next_number:06d}"
                connection.exec_driver_sql(
                    "UPDATE orders SET reference = ? WHERE id = ?", (reference, order_id)
                )
                used_numbers.add(next_number)
                next_number += 1


def migrate_sqlite_order_catalog_refs(target_engine: Engine = engine) -> None:
    """Backward-compatible name retained for older callers/tests."""

    migrate_sqlite_schema(target_engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
