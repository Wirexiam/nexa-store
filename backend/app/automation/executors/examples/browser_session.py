"""Example extension point that deliberately performs no third-party action."""

from ..base import ACTION_REQUIRED, ExecutionOutcome
from ..browser_session import BrowserSessionExecutor


class ExampleBrowserSessionExecutor(BrowserSessionExecutor):
    """Shows where a reviewed adapter would use its one-use browser page."""

    def execute(self) -> ExecutionOutcome:
        self.ensure_not_stopped()
        # Do not add customer login or purchase automation to this example.
        return ExecutionOutcome(
            ACTION_REQUIRED,
            "Example isolated session completed without contacting a third party",
        )
