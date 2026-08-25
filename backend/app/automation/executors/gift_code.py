from .base import ACTION_REQUIRED, BaseExecutor, ExecutionOutcome


class GiftCodeExecutor(BaseExecutor):
    execution_type = "gift_code"

    def execute(self) -> ExecutionOutcome:
        return ExecutionOutcome(
            ACTION_REQUIRED,
            "Gift-code fulfillment awaits a reviewed inventory integration",
        )
