"""Isolated, non-persistent Chromium sessions for fulfillment executors."""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..config import settings

logger = logging.getLogger(__name__)


class BrowserAutomationUnavailable(RuntimeError):
    """Raised when Playwright or its Chromium binary is unavailable."""


@dataclass(slots=True)
class BrowserHandles:
    """Resources created by a browser backend.

    Keeping these handles explicit makes cleanup testable and lets production
    use Playwright without importing it at application startup.
    """

    runtime: Any
    browser: Any
    context: Any
    page: Any


class BrowserBackend(Protocol):
    def create(self, storage_path: Path, *, headless: bool) -> BrowserHandles: ...


class PlaywrightChromiumBackend:
    """Create a fresh Chromium process and incognito context for one job."""

    def create(self, storage_path: Path, *, headless: bool) -> BrowserHandles:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise BrowserAutomationUnavailable(
                "Playwright is not installed; install backend requirements and Chromium"
            ) from exc

        runtime = sync_playwright().start()
        browser = None
        context = None
        try:
            # launch(), not launch_persistent_context(), is deliberate: no
            # customer browser profile is accepted or reused.
            browser = runtime.chromium.launch(
                headless=headless,
                downloads_path=str(storage_path / "downloads"),
            )
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            return BrowserHandles(
                runtime=runtime,
                browser=browser,
                context=context,
                page=page,
            )
        except Exception as exc:
            _close_quietly(context)
            _close_quietly(browser)
            _stop_quietly(runtime)
            raise BrowserAutomationUnavailable(
                "An isolated Chromium session could not be started"
            ) from exc


class BrowserSession:
    """Own every browser and temporary-storage resource for a single job."""

    def __init__(self, handles: BrowserHandles, temporary_directory: tempfile.TemporaryDirectory[str]):
        self.runtime = handles.runtime
        self.browser = handles.browser
        self.context = handles.context
        self.page = handles.page
        self._temporary_directory = temporary_directory
        self.storage_path = Path(temporary_directory.name)
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        # Close from the most specific resource outward. Cleanup is best
        # effort, but every remaining step is attempted even if one fails.
        _close_quietly(self.page)
        _close_quietly(self.context)
        _close_quietly(self.browser)
        _stop_quietly(self.runtime)
        try:
            self._temporary_directory.cleanup()
        except Exception:
            logger.warning("Temporary browser storage cleanup failed")

    def __enter__(self) -> BrowserSession:
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()


class BrowserManager:
    """Factory for one-use, isolated browser sessions.

    A new temporary directory, Chromium process, browser context, and page are
    created for every call. The manager never accepts a user-data directory.
    """

    def __init__(
        self,
        backend: BrowserBackend | None = None,
        *,
        headless: bool | None = None,
        temporary_root: str | Path | None = None,
    ) -> None:
        self._backend = backend or PlaywrightChromiumBackend()
        self._headless = (
            bool(getattr(settings, "browser_headless", True)) if headless is None else headless
        )
        self._temporary_root = str(temporary_root) if temporary_root is not None else None

    def open_session(self) -> BrowserSession:
        temporary_directory = tempfile.TemporaryDirectory(
            prefix="nexa-browser-",
            dir=self._temporary_root,
        )
        storage_path = Path(temporary_directory.name)
        try:
            (storage_path / "downloads").mkdir(exist_ok=False)
            handles = self._backend.create(storage_path, headless=self._headless)
        except Exception:
            temporary_directory.cleanup()
            raise
        return BrowserSession(handles, temporary_directory)


def _close_quietly(resource: Any) -> None:
    if resource is None:
        return
    try:
        resource.close()
    except Exception:
        logger.warning("A browser resource did not close cleanly")


def _stop_quietly(resource: Any) -> None:
    if resource is None:
        return
    try:
        resource.stop()
    except Exception:
        logger.warning("The Playwright runtime did not stop cleanly")
