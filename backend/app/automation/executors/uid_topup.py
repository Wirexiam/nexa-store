from .base import ACTION_REQUIRED, BaseExecutor, ExecutionOutcome


class UIDTopupExecutor(BaseExecutor):
    execution_type = "uid_topup"

    def execute(self) -> ExecutionOutcome:
        return ExecutionOutcome(
            ACTION_REQUIRED,
            "UID top-up details were validated and await a reviewed provider integration",
        )
