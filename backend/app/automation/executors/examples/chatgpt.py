"""Safe ChatGPT workflow example.

This class demonstrates the real executor lifecycle and isolated browser
allocation, but intentionally never navigates to OpenAI, signs in, or purchases
anything. Production actions require a separately reviewed adapter.
"""

from ..base import ACTION_REQUIRED, ExecutionOutcome
from ..browser_session import BrowserSessionExecutor


class ChatGPTExecutor(BrowserSessionExecutor):
    execution_type = "browser_session"

    def execute(self) -> ExecutionOutcome:
        self.ensure_not_stopped()
        if self.browser_session is None or self.browser_session.closed:
            raise RuntimeError("The isolated browser session is unavailable")
        return ExecutionOutcome(
            ACTION_REQUIRED,
            "ChatGPT isolated session is ready for a reviewed fulfillment adapter",
        )
