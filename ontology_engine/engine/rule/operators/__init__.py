# ontology_engine/engine/rule/operators/__init__.py
"""Rule operators module."""

from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry
from ontology_engine.engine.rule.operators.registry import (
    get_operator_schema,
    get_all_operator_schemas,
    validate_operator_params,
    build_operator_schemas,
)

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
from ontology_engine.engine.rule.operators.decision_table import (
    DecisionTableOperator,
)
from ontology_engine.engine.rule.operators.llm_judge import (
    LLMJudgeOperator,
)
from ontology_engine.engine.rule.operators.weighted_sum import (
    WeightedSumOperator,
)

__all__ = [
    "Operator",
    "OperatorRegistry",
    # Registry utilities
    "get_operator_schema",
    "get_all_operator_schemas",
    "validate_operator_params",
    "build_operator_schemas",
    # Operators
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
    "DecisionTableOperator",
    "LLMJudgeOperator",
    "WeightedSumOperator",
]
