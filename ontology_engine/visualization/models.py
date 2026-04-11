"""Visualization data models for OntologyEngine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


# ============== Schema Graph Models (G6) ==============


@dataclass
class GraphNode:
    """G6-compatible graph node."""

    id: str
    type: str  # entity | metric | rule
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """G6-compatible graph edge."""

    id: str
    source: str
    target: str
    type: str  # relation | metric_dep | rule_input
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class LayoutConfig:
    """Layout configuration for graph rendering."""

    type: str = "dagre"  # dagre | force | concentric
    rankdir: str = "LR"  # LR | TB | RL | BT
    nodesep: int = 50
    ranksep: int = 80


@dataclass
class GraphMetadata:
    """Graph metadata statistics."""

    entity_count: int = 0
    relation_count: int = 0
    metric_count: int = 0
    rule_count: int = 0


@dataclass
class SchemaGraphData:
    """Complete Schema graph data for G6 rendering."""

    schema_id: str
    graph_type: str  # entity_relation | metric_dependency | full | rule_overview
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    layout_config: LayoutConfig = field(default_factory=LayoutConfig)
    metadata: GraphMetadata = field(default_factory=GraphMetadata)


# ============== Rule Chain Graph Models (X6) ==============


@dataclass
class RuleChainNode:
    """X6-compatible rule chain node."""

    id: str
    position: dict[str, float] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleChainEdge:
    """X6-compatible rule chain edge."""

    id: str
    source: str
    target: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class DimensionInfo:
    """Dimension metadata for rule chain."""

    name: str = ""
    description: str | None = None
    applicable_entities: list[str] = field(default_factory=list)
    rule_count: int = 0


@dataclass
class RuleChainGraphData:
    """Complete rule chain DAG data for X6 rendering."""

    dimension: str
    nodes: list[RuleChainNode] = field(default_factory=list)
    edges: list[RuleChainEdge] = field(default_factory=list)
    dimension_info: DimensionInfo = field(default_factory=DimensionInfo)


# ============== Execution Explainability Models ==============


@dataclass
class ConditionDetail:
    """Sub-condition evaluation detail."""

    expression: str
    resolved: str
    result: bool
    explanation: str


@dataclass
class ExecutionStepSnapshot:
    """Complete snapshot of a single rule execution step."""

    step: int
    rule_id: str
    rule_name: str
    rule_type: str  # constraint | inference | alert | decision

    # Condition evaluation
    condition_expression: str = ""
    condition_result: bool | None = None
    condition_details: list[ConditionDetail] = field(default_factory=list)

    # Context snapshots
    context_before: dict[str, Any] = field(default_factory=dict)
    context_after: dict[str, Any] = field(default_factory=dict)

    # Inputs / Outputs
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)

    # Status
    status: str = "pending"  # pending | executing | passed | failed | skipped
    duration_ms: float = 0.0

    # Explanation
    explanation: str = ""
    affected_metrics: list[str] = field(default_factory=list)


# ============== Simulation Models ==============


@dataclass
class DiffEntry:
    """Single difference between baseline and simulation."""

    field: str
    baseline_value: Any = None
    simulated_value: Any = None
    change_type: str = "unchanged"  # increased | decreased | new | removed | unchanged
    change_magnitude: float | None = None
    impact: str = ""


@dataclass
class ImpactChain:
    """Impact propagation path."""

    source_field: str
    affected_fields: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class ComparisonResult:
    """Baseline vs simulation comparison."""

    baseline: dict[str, Any] = field(default_factory=dict)
    simulated: dict[str, Any] = field(default_factory=dict)
    diffs: list[DiffEntry] = field(default_factory=list)
    impact_chains: list[ImpactChain] = field(default_factory=list)


@dataclass
class VisualizationEntityOption:
    """Selectable entity option for visualization pages."""

    entity_id: str
    concept_type: str
    label: str
    active_dimensions: list[str] = field(default_factory=list)


@dataclass
class MetricSnapshot:
    """Real metric values for one entity and dimension."""

    entity_id: str
    dimension: str
    metrics: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    decision: str | None = None
    decision_reasoning: str | None = None


@dataclass
class SimulationResult:
    """Complete simulation execution result."""

    entity_id: str
    dimension: str
    simulation_type: str = "dry_run"  # dry_run | what_if

    steps: list[ExecutionStepSnapshot] = field(default_factory=list)
    execution_path: list[str] = field(default_factory=list)
    skipped_rules: list[str] = field(default_factory=list)
    final_outputs: dict[str, Any] = field(default_factory=dict)

    # Decision
    decision: str | None = None
    decision_reasoning: str | None = None
    alerts: list[dict[str, Any]] = field(default_factory=list)

    # What-if comparison
    comparison: ComparisonResult | None = None

    # Full execution context with all computed metrics (including intermediate sub-metrics)
    final_context: dict[str, Any] = field(default_factory=dict)
