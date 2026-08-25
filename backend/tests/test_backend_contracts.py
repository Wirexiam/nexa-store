import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.catalog import get_service, resolve_level_period
from app.main import _frontend_response, app
from app.routers.admin import create_order
from app.routers.orders import submit_customer_order
from app.schemas import OrderCreate, OrderPublic, OrderSubmit


class OrderPublicTests(unittest.TestCase):
    def test_validates_orm_style_object_and_keeps_public_shape(self):
        order = SimpleNamespace(
            id="order-1",
            customer_email="customer@example.com",
            service="Claude",
            service_key="claude",
            subscription_level="Pro",
            payment_period="1 month",
            amount=Decimal("2490.00"),
            currency="RUB",
            status="In progress",
            created_at=datetime.now(timezone.utc),
            access_token="must-not-serialize",
        )

        public = OrderPublic.model_validate(order)

        self.assertEqual(public.id, "order-1")
        self.assertNotIn("access_token", public.model_dump())


class PlanResolutionTests(unittest.TestCase):
    def setUp(self):
        self.service = get_service("claude")
        assert self.service is not None

    def test_none_ids_keep_first_option_defaults(self):
        level, period, amount = resolve_level_period(self.service, None, None)

        self.assertEqual(level["id"], self.service["levels"][0]["id"])
        self.assertEqual(period["id"], self.service["periods"][0]["id"])
        self.assertEqual(amount, Decimal(level["prices"][period["id"]]))

    def test_unknown_ids_are_rejected(self):
        for level_id, period_id in (("unknown", "1m"), ("pro", "unknown")):
            with self.subTest(level_id=level_id, period_id=period_id):
                with self.assertRaises(ValueError):
                    resolve_level_period(self.service, level_id, period_id)

    def test_admin_create_converts_invalid_selection_to_400(self):
        payload = OrderCreate(service_key="claude", level_id="unknown", period_id="1m")

        with self.assertRaises(HTTPException) as raised:
            create_order(payload, db=SimpleNamespace())

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "Invalid plan selection")

    def test_customer_submit_converts_invalid_selection_to_400(self):
        order = SimpleNamespace(service_key="claude", credentials_received=False)
        db = SimpleNamespace(get=lambda _model, _order_id: order)
        payload = OrderSubmit(
            email="customer@example.com",
            level_id="pro",
            period_id="unknown",
        )

        with self.assertRaises(HTTPException) as raised:
            submit_customer_order("order-1", payload, db=db)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "Invalid plan selection")


class FrontendFallbackTests(unittest.TestCase):
    def test_serves_assets_and_falls_back_to_index_safely(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            dist = Path(temporary_directory).resolve()
            index = dist / "index.html"
            asset = dist / "assets" / "app.js"
            asset.parent.mkdir()
            index.write_text("<main>app</main>", encoding="utf-8")
            asset.write_text("console.log('app')", encoding="utf-8")

            with patch("app.main.FRONTEND_DIST", dist):
                self.assertEqual(Path(_frontend_response("assets/app.js").path), asset)
                self.assertEqual(Path(_frontend_response("admin/orders/123").path), index)
                self.assertEqual(Path(_frontend_response("../outside.txt").path), index)

                with self.assertRaises(HTTPException) as raised:
                    _frontend_response("api/missing")
                self.assertEqual(raised.exception.status_code, 404)

    def test_frontend_catch_all_is_registered_after_api_routes(self):
        paths = [route.path for route in app.routes]

        self.assertLess(paths.index("/api/health"), paths.index("/{frontend_path:path}"))


if __name__ == "__main__":
    unittest.main()
