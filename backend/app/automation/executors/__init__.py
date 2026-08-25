from .api import APIExecutor
from .base import (
    ACTION_REQUIRED,
    COMPLETED,
    EXECUTION_STATUSES,
    EXECUTION_STATUS_LABELS,
    FAILED,
    PENDING,
    RUNNING,
    STOPPED,
    BaseExecutor,
    ExecutionOrder,
    ExecutionOutcome,
)
from .browser_session import BrowserSessionExecutor
from .gift_code import GiftCodeExecutor
from .manual import ManualExecutor
from .uid_topup import UIDTopupExecutor

EXECUTOR_TYPES = {
    "manual": ManualExecutor,
    "browser_session": BrowserSessionExecutor,
    "uid_topup": UIDTopupExecutor,
    "gift_code": GiftCodeExecutor,
    "api": APIExecutor,
}

__all__ = [
    "ACTION_REQUIRED",
    "APIExecutor",
    "BaseExecutor",
    "BrowserSessionExecutor",
    "COMPLETED",
    "EXECUTION_STATUSES",
    "EXECUTION_STATUS_LABELS",
    "EXECUTOR_TYPES",
    "ExecutionOrder",
    "ExecutionOutcome",
    "FAILED",
    "GiftCodeExecutor",
    "ManualExecutor",
    "PENDING",
    "RUNNING",
    "STOPPED",
    "UIDTopupExecutor",
]
