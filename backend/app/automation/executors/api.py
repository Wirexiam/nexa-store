from .base import ACTION_REQUIRED, BaseExecutor, ExecutionOutcome


class APIExecutor(BaseExecutor):
    execution_type = "api"

    def execute(self) -> ExecutionOutcome:
        return ExecutionOutcome(
            ACTION_REQUIRED,
            "API fulfillment awaits a reviewed provider adapter",
        )
