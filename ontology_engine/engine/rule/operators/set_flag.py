# ontology_engine/engine/rule/operators/set_flag.py
"""SetFlag operator."""

from typing import Any

from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry


@OperatorRegistry.register("set_flag")
class SetFlagOperator(Operator):
    """Set a flag on the entity or context.

    Inputs:
        - flag_name: Name of the flag to set (default: "eligible")
        - flag_value: Value to set (default: True)

    Example:
        action:
            operator: "set_flag"
            inputs:
                flag_name: "eligible"
                flag_value: true
    """

    @property
    def name(self) -> str:
        return "set_flag"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        flag_name = inputs.get("flag_name", "flag")
        flag_value = inputs.get("flag_value", True)

        return {
            flag_name: flag_value,
            f"{flag_name}_set": True
        }


@OperatorRegistry.register("approve_eligibility")
class ApproveEligibilityOperator(Operator):
    """Approve eligibility - convenience operator for set_flag with eligible=true.

    This operator is kept for backward compatibility with legacy action names.
    """

    @property
    def name(self) -> str:
        return "approve_eligibility"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        rejection_reason = inputs.get("rejection_reason", "Approved")
        return {
            "eligible": True,
            "rejection_reason": rejection_reason
        }


@OperatorRegistry.register("reject_eligibility")
class RejectEligibilityOperator(Operator):
    """Reject eligibility - convenience operator for structured rejection.

    This operator is kept for backward compatibility with legacy action names.
    """

    @property
    def name(self) -> str:
        return "reject_eligibility"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        rejection_reason = inputs.get(
            "rejection_reason",
            "Did not meet eligibility criteria"
        )
        return {
            "eligible": False,
            "rejection_reason": rejection_reason
        }
