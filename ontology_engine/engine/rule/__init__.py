"""Rule engine for executing KGML rules."""
from ontology_engine.engine.rule.models import (
    ExecutionContext,
    RuleResult,
    Alert,
    AnalysisResult,
)
from ontology_engine.engine.rule.evaluator import ExpressionEvaluator, ExpressionSyntaxError
from ontology_engine.engine.rule.executor import RuleExecutor

# Alias for backward compatibility
RuleEngine = RuleExecutor

__all__ = [
    "ExecutionContext",
    "RuleResult",
    "Alert",
    "AnalysisResult",
    "ExpressionEvaluator",
    "ExpressionSyntaxError",
    "RuleExecutor",
    "RuleEngine",
]
