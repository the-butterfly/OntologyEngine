"""Rule engine for executing KGML rules."""
from ontology_engine.engine.rule.models import (
    ExecutionContext,
    RuleResult,
    Alert,
    AnalysisResult,
    # Phase 2: Rule Orchestration Models
    RuleGroupDefinition,
    RuleStep,
    ActionClause,
    ConditionClause,
    OperatorSchema,
    AppliesToConfig,
    Precondition,
    IOElement,
)
from ontology_engine.engine.rule.evaluator import ExpressionEvaluator, ExpressionSyntaxError
from ontology_engine.engine.rule.executor import RuleExecutor

# Alias for backward compatibility
RuleEngine = RuleExecutor

__all__ = [
    # Phase 1 Models
    "ExecutionContext",
    "RuleResult",
    "Alert",
    "AnalysisResult",
    # Phase 2 Models
    "RuleGroupDefinition",
    "RuleStep",
    "ActionClause",
    "ConditionClause",
    "OperatorSchema",
    "AppliesToConfig",
    "Precondition",
    "IOElement",
    # Utilities
    "ExpressionEvaluator",
    "ExpressionSyntaxError",
    "RuleExecutor",
    "RuleEngine",
]
