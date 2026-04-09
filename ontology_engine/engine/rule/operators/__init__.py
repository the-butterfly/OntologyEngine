# ontology_engine/engine/rule/operators/__init__.py
"""Rule operators module."""

from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry

# Import all operators to register them
from ontology_engine.engine.rule.operators.set_flag import (
    SetFlagOperator,
    ApproveEligibilityOperator,
    RejectEligibilityOperator,
)
from ontology_engine.engine.rule.operators.compute import (
    ComputeFormulaOperator,
    CalculateCreditScoreOperator,
    CalculateCreditLimitOperator,
    DetermineInterestRateOperator,
)
from ontology_engine.engine.rule.operators.switch import (
    SwitchOperator,
    BinningOperator,
    ScorecardOperator,
)
from ontology_engine.engine.rule.operators.alert import (
    TriggerAlertOperator,
    GraphTraversalOperator,
)

__all__ = [
    "Operator",
    "OperatorRegistry",
    "SetFlagOperator",
    "ApproveEligibilityOperator",
    "RejectEligibilityOperator",
    "ComputeFormulaOperator",
    "CalculateCreditScoreOperator",
    "CalculateCreditLimitOperator",
    "DetermineInterestRateOperator",
    "SwitchOperator",
    "BinningOperator",
    "ScorecardOperator",
    "TriggerAlertOperator",
    "GraphTraversalOperator",
]
