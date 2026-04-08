"""Rule engine data models."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionContext:
    """Context for rule execution."""
    entity_id: str
    dimension: str
    entity_data: dict[str, Any]  # The entity's data
    computed_metrics: dict[str, Any] = field(default_factory=dict)
    rule_results: list[RuleResult] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)


@dataclass
class RuleResult:
    """Result of a rule execution."""
    rule_id: str
    rule_name: str | None
    passed: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class Alert:
    """Alert/warning generated during execution."""
    level: str  # "warning", "high", "critical"
    type: str
    message: str
    data: dict[str, Any] | None = None


@dataclass
class AnalysisResult:
    """Complete analysis result for a dimension."""
    entity_id: str
    dimension: str
    rule_results: list[RuleResult]
    computed_metrics: dict[str, Any]
    alerts: list[Alert]
    decision: str | None = None
    decision_reasoning: str | None = None
