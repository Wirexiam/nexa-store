from .base import ACTION_REQUIRED, BaseExecutor, ExecutionOutcome


class ManualExecutor(BaseExecutor):
    execution_type = "manual"

    def execute(self) -> ExecutionOutcome:
        return ExecutionOutcome(
            ACTION_REQUIRED,
            "The order is ready for manual fulfillment",
        )
