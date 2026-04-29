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
    # V3: RFC-018 / RFC-019 Models
    StructuredActionClause,
    StepDecl,
    RuleDefinitionDecl,
    RuleLogicDecl,
)
from ontology_engine.core.schema.models import ActionType, OperatorType
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
    # V3 Models (RFC-018 / RFC-019)
    "StructuredActionClause",
    "StepDecl",
    "RuleDefinitionDecl",
    "RuleLogicDecl",
    "ActionType",
    "OperatorType",
    # Utilities
    "ExpressionEvaluator",
    "ExpressionSyntaxError",
    "RuleExecutor",
    "RuleEngine",
]
