"""Safe browser-session foundation; no service login or purchase actions."""

from __future__ import annotations

from ..browser import BrowserManager, BrowserSession
from .base import ACTION_REQUIRED, BaseExecutor, ExecutionOutcome


class BrowserSessionExecutor(BaseExecutor):
    execution_type = "browser_session"

    def __init__(self, *args, browser_manager: BrowserManager | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.browser_manager = browser_manager or BrowserManager()
        self.browser_session: BrowserSession | None = None

    def prepare(self) -> None:
        self.browser_session = self.browser_manager.open_session()

    def execute(self) -> ExecutionOutcome:
        # The generic executor intentionally does not navigate, authenticate,
        # or call a third party. Service-specific, reviewed adapters can use
        # self.browser_session.page in the future.
        return ExecutionOutcome(
            ACTION_REQUIRED,
            "An isolated browser session was prepared; reviewed service automation is required",
        )

    def cleanup(self) -> None:
        if self.browser_session is not None:
            self.browser_session.close()
            self.browser_session = None
