import json
import tempfile
import threading
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.automation.browser import BrowserHandles, BrowserManager
from app.automation.executors.base import (
    ACTION_REQUIRED,
    COMPLETED,
    BaseExecutor,
    ExecutionOrder,
    ExecutionOutcome,
)
from app.automation.executors.examples import ChatGPTExecutor
from app.automation.manager import ExecutionManager
from app.automation.service import ExecutionService
from app.notifications.telegram import TelegramConfig, TelegramNotifier


class _FakeResource:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakeRuntime:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class _FakeBrowserBackend:
    def __init__(self):
        self.created_paths = []
        self.bundles = []

    def create(self, storage_path, *, headless):
        self.created_paths.append((Path(storage_path), headless))
        bundle = SimpleNamespace(
            runtime=_FakeRuntime(),
            browser=_FakeResource(),
            context=_FakeResource(),
            page=_FakeResource(),
        )
        self.bundles.append(bundle)
        return BrowserHandles(
            runtime=bundle.runtime,
            browser=bundle.browser,
            context=bundle.context,
            page=bundle.page,
        )


class _FailingBrowserBackend:
    def __init__(self):
        self.storage_path = None

    def create(self, storage_path, *, headless):
        self.storage_path = Path(storage_path)
        raise RuntimeError("browser startup failed")


class BrowserLifecycleTests(unittest.TestCase):
    def test_each_session_is_unique_and_cleanup_removes_temporary_storage(self):
        backend = _FakeBrowserBackend()
        with tempfile.TemporaryDirectory() as temporary_root:
            manager = BrowserManager(
                backend,
                headless=True,
                temporary_root=temporary_root,
            )
            first = manager.open_session()
            first_path = first.storage_path
            self.assertTrue(first_path.is_dir())
            first.close()

            second = manager.open_session()
            second_path = second.storage_path
            second.close()

        self.assertNotEqual(first_path, second_path)
        self.assertFalse(first_path.exists())
        self.assertFalse(second_path.exists())
        for bundle in backend.bundles:
            self.assertTrue(bundle.page.closed)
            self.assertTrue(bundle.context.closed)
            self.assertTrue(bundle.browser.closed)
            self.assertTrue(bundle.runtime.stopped)

    def test_failed_browser_startup_still_removes_temporary_storage(self):
        backend = _FailingBrowserBackend()
        with tempfile.TemporaryDirectory() as temporary_root:
            manager = BrowserManager(backend, temporary_root=temporary_root)
            with self.assertRaises(RuntimeError):
                manager.open_session()

            self.assertIsNotNone(backend.storage_path)
            self.assertFalse(backend.storage_path.exists())

    def test_chatgpt_example_uses_browser_lifecycle_and_drops_transient_input(self):
        backend = _FakeBrowserBackend()
        transient = {"temporary_session": "never-persist-this"}
        with tempfile.TemporaryDirectory() as temporary_root:
            browser_manager = BrowserManager(
                backend,
                temporary_root=temporary_root,
            )
            executor = ChatGPTExecutor(
                ExecutionOrder(id="order-1", service="ChatGPT", service_key="chatgpt"),
                transient,
                threading.Event(),
                browser_manager=browser_manager,
            )
            outcome = executor.run()

        self.assertEqual(outcome.status, ACTION_REQUIRED)
        self.assertEqual(transient, {})
        self.assertTrue(backend.bundles[0].context.closed)
        self.assertTrue(backend.bundles[0].runtime.stopped)


class _CompletedExecutor(BaseExecutor):
    def execute(self):
        # Deliberately echoes a temporary value to verify service-level
        # redaction protects future custom executors too.
        return ExecutionOutcome(
            COMPLETED,
            f"completed with {self.transient_data['access_token']}",
        )


class _BlockingExecutor(BaseExecutor):
    started = threading.Event()

    def execute(self):
        self.started.set()
        self.stop_event.wait(timeout=3)
        return ExecutionOutcome(COMPLETED, "should be converted to stopped")


class _FakeDB:
    def __init__(self, order):
        self.order = order
        self.commits = 0
        self.closed = False

    def get(self, _model, order_id):
        return self.order if order_id == self.order.id else None

    def scalar(self, _statement):
        return None

    def commit(self):
        self.commits += 1

    def refresh(self, _order):
        return None

    def rollback(self):
        return None

    def close(self):
        self.closed = True


class _ExplodingNotifier:
    def notify_execution_started(self, *_args, **_kwargs):
        raise RuntimeError("telegram unavailable")

    def notify_execution_result(self, *_args, **_kwargs):
        raise RuntimeError("telegram unavailable")


class ExecutionServiceTests(unittest.TestCase):
    @staticmethod
    def _order(order_id="order-1"):
        workflow = SimpleNamespace(
            active=True,
            execution_type="manual",
            description="test workflow",
            requires_manual_action=False,
        )
        return SimpleNamespace(
            id=order_id,
            service="Test Service",
            service_key="test-service",
            subscription_level="Pro",
            payment_period="1 month",
            amount=Decimal("1990.00"),
            currency="RUB",
            catalog_service=SimpleNamespace(workflow=workflow),
            execution_status="pending",
            execution_error=None,
            execution_result=None,
            executor_name=None,
            execution_started_at=None,
            execution_finished_at=None,
            execution_attempts=0,
            execution_stop_requested=False,
        )

    def test_lifecycle_persists_only_sanitized_result_and_ignores_telegram_failure(self):
        order = self._order()
        request_db = _FakeDB(order)
        worker_databases = []

        def session_factory():
            worker_db = _FakeDB(order)
            worker_databases.append(worker_db)
            return worker_db

        manager = ExecutionManager(max_workers=1)
        service = ExecutionService(
            session_factory=session_factory,
            manager=manager,
            notification_client=_ExplodingNotifier(),
            executor_types={"manual": _CompletedExecutor},
            service_executor_types={},
        )
        transient = {"access_token": "super-secret-token"}
        try:
            service.start(request_db, order, transient)
            self.assertEqual(transient, {})
            self.assertTrue(manager.wait_for_idle(order.id, timeout=3))

            self.assertEqual(order.execution_status, COMPLETED)
            self.assertEqual(order.execution_attempts, 1)
            self.assertNotIn("super-secret-token", order.execution_result)
            self.assertIn("[redacted]", order.execution_result)
            self.assertIsNone(order.execution_error)
            self.assertTrue(worker_databases[0].closed)
        finally:
            manager.shutdown()

    def test_running_execution_can_be_stopped_cooperatively(self):
        _BlockingExecutor.started.clear()
        order = self._order("order-stop")
        request_db = _FakeDB(order)
        manager = ExecutionManager(max_workers=1)
        service = ExecutionService(
            session_factory=lambda: _FakeDB(order),
            manager=manager,
            notification_client=_ExplodingNotifier(),
            executor_types={"manual": _BlockingExecutor},
            service_executor_types={},
        )
        transient = {"temporary_session": "drop-me"}
        try:
            service.start(request_db, order, transient)
            self.assertTrue(_BlockingExecutor.started.wait(timeout=2))
            snapshot = service.stop(request_db, order)

            self.assertTrue(snapshot.execution_stop_requested)
            self.assertTrue(manager.wait_for_idle(order.id, timeout=3))
            self.assertEqual(order.execution_status, "stopped")
            self.assertEqual(transient, {})
        finally:
            manager.shutdown()


class _FakeHTTPResponse:
    def __init__(self, payload=b'{"ok": true}'):
        self.payload = payload
        self.closed = False

    def read(self):
        return self.payload

    def close(self):
        self.closed = True


class TelegramNotifierTests(unittest.TestCase):
    def test_notification_uses_persisted_reference_and_whitelisted_metadata(self):
        captured = {}

        def opener(request, *, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _FakeHTTPResponse()

        telegram = TelegramNotifier(
            TelegramConfig("123:token", "999", 1.5),
            opener=opener,
        )
        order = SimpleNamespace(
            id="uuid-value",
            reference="NX-000042",
            service="ChatGPT",
            subscription_level="Plus",
            amount=Decimal("1990.00"),
            currency="RUB",
            customer_email="user@example.com",
            status="In progress",
            access_token="must-never-appear",
        )

        self.assertTrue(telegram.notify_new_order(order))
        message = captured["body"]["text"]
        self.assertIn("NX-000042", message)
        self.assertIn("ChatGPT", message)
        self.assertNotIn("must-never-appear", message)
        self.assertEqual(captured["timeout"], 1.5)

    def test_transport_failure_is_returned_not_raised(self):
        def opener(_request, *, timeout):
            raise OSError("network unavailable")

        telegram = TelegramNotifier(
            TelegramConfig("123:secret", "999"),
            opener=opener,
        )

        self.assertFalse(telegram.send("hello"))


if __name__ == "__main__":
    unittest.main()
