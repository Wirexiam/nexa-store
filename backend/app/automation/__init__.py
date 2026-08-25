"""Order fulfillment infrastructure.

The public entry points live in :mod:`app.automation.service`.  Browser
dependencies are intentionally imported lazily so the API can still serve
manual workflows when Playwright is not installed.
"""

from .service import (
    ExecutionSnapshot,
    get_execution_status,
    retry_execution,
    start_execution,
    stop_execution,
)

__all__ = [
    "ExecutionSnapshot",
    "get_execution_status",
    "retry_execution",
    "start_execution",
    "stop_execution",
]
