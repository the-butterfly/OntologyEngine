"""Graph data builders - convert KGML Schema to G6/X6 formats."""
from __future__ import annotations

import re
from typing import Any

from ontology_engine.core.schema.models import (
    ConceptDefinition,
    KGMLSchema,
    MetricDefinition,
    RelationDefinition,
    RuleDefinition,
    RuleWhen,
)
from ontology_engine.visualization.models import (
    DimensionInfo,
    GraphEdge,
    GraphMetadata,
    GraphNode,
    LayoutConfig,
    RuleChainEdge,
    RuleChainGraphData,
    RuleChainNode,
    SchemaGraphData,
)


# ============== Chinese label mappings ==============

CONCEPT_LABELS: dict[str, str] = {
    "Supplier": "供应商",
    "CoreEnterprise": "核心企业",
    "Invoice": "发票",
    "Contract": "合同",
    "LogisticsRecord": "物流记录",
    "GuaranteeRelation": "担保关系",
}

METRIC_LABELS: dict[str, str] = {
    "total_invoice_amount_90d": "近90天发票总额",
    "invoice_count_90d": "近90天发票数",
    "overdue_invoice_amount": "逾期发票金额",
    "total_contract_amount": "合同总金额",
    "avg_monthly_tax_revenue": "月均纳税额",
    "tax_compliance_score": "税务合规评分",
    "negative_news_count_90d": "近90天负面新闻数",
    "core_enterprise_count": "合作核心企业数",
    "overdue_invoice_ratio": "逾期发票占比",
    "avg_invoice_amount": "平均发票金额",
    "contract_utilization_rate": "合同执行率",
    "business_stability_score": "业务稳定性评分",
    "guarantee_chain_depth": "担保链深度",
    "has_guarantee_circle": "是否存在担保圈",
    "network_centrality_score": "网络中心性得分",
    "credit_score": "综合信用评分",
    "reputation_score": "声誉风险评分",
    "guarantee_risk_score": "担保风险评分",
    "credit_grade": "信用等级",
    "guarantee_risk_adjustment": "担保风险调整",
}

RULE_LABELS: dict[str, str] = {
    "R001_basic_eligibility": "基础准入检查",
    "R002_credit_score_calculation": "信用评分计算",
    "R003_guarantee_circle_detection": "担保圈风险检测",
    "R004_credit_limit_calculation": "授信额度计算",
    "R005_risk_early_warning": "风险预警触发",
    "R006_interest_rate_pricing": "利率定价",
    "R007_comprehensive_credit_decision": "综合授信决策",
    "R008_large_transaction_monitor": "大额交易监控",
    "R009_transaction_volatility": "交易波动性检测",
}

# Weights extracted from schema.yaml credit_score components
CREDIT_SCORE_WEIGHTS: dict[str, float] = {
    "business_stability_score": 0.30,
    "tax_compliance_score": 0.25,
    "network_centrality_score": 0.15,
    "reputation_score": 0.15,
    "guarantee_chain_depth": 0.15,
}

# Known metric → weight mapping for composite metrics
COMPOSITE_WEIGHT_MAPS: dict[str, dict[str, float]] = {
    "credit_score": CREDIT_SCORE_WEIGHTS,
}


class SchemaGraphBuilder:
    """Build G6-compatible graph data from KGML Schema."""

    def __init__(self, schema: KGMLSchema) -> None:
        self.schema = schema
        self._metric_index: dict[str, MetricDefinition] = {
            m.name: m for m in schema.metrics
        }
        self._rule_index: dict[str, RuleDefinition] = {}
        if schema.rules:
            for r in schema.rules.ruleset:
                self._rule_index[r.id] = r

    def build(
        self,
        graph_type: str,
        layer_filter: list[str] | None = None,
    ) -> SchemaGraphData:
        """Build graph data for the specified view type."""
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        layers = self._resolve_layers(graph_type, layer_filter)

        # L1: Entity nodes + relation edges
        if "L1" in layers:
            for concept in self.schema.concepts:
                if concept.category == "entity":
                    nodes.append(self._build_entity_node(concept))
                    for rel in concept.relations:
                        edges.append(self._build_relation_edge(concept.name, rel))

        # L3: Metric nodes + dependency edges
        if "L3" in layers:
            for metric in self.schema.metrics:
                nodes.append(self._build_metric_node(metric))
                for dep in metric.dependencies:
                    edges.append(self._build_metric_dep_edge(dep, metric))

        # L4: Rule nodes
        if "L4" in layers:
            if self.schema.rules:
                for rule in self.schema.rules.ruleset:
                    nodes.append(self._build_rule_node(rule))

        # Cross-layer edges (metric → rule data flow)
        if "L3" in layers or "L4" in layers:
            edges.extend(self._build_cross_layer_edges())

        # Rule execution flow edges for rule_overview
        if graph_type == "rule_overview" and "L4" in layers:
            edges.extend(self._build_rule_execution_flow_edges())

        # Build node id set for filtering edges
        node_ids = {n.id for n in nodes}

        # Filter edges to only include those with existing nodes
        # Also deduplicate by id
        seen_edge_ids: set[str] = set()
        unique_edges: list[GraphEdge] = []
        for edge in edges:
            if edge.id not in seen_edge_ids:
                if edge.source in node_ids and edge.target in node_ids:
                    seen_edge_ids.add(edge.id)
                    unique_edges.append(edge)

        return SchemaGraphData(
            schema_id=self.schema.metadata.id,
            graph_type=graph_type,
            nodes=nodes,
            edges=unique_edges,
            layout_config=self._get_layout_config(graph_type),
            metadata=self._build_metadata(nodes, unique_edges),
        )

    def _resolve_layers(
        self,
        graph_type: str,
        layer_filter: list[str] | None,
    ) -> list[str]:
        """Determine which layers to include based on graph type and filter."""
        type_layers: dict[str, list[str]] = {
            "entity_relation": ["L1"],
            "metric_dependency": ["L3"],
            "full": ["L1", "L3", "L4"],
            "rule_overview": ["L4"],
        }
        layers = type_layers.get(graph_type, ["L1", "L3", "L4"])
        if layer_filter:
            layers = [l for l in layers if l in layer_filter]
        return layers

    def _build_entity_node(self, concept: ConceptDefinition) -> GraphNode:
        """Build an entity node from a concept definition."""
        key_attrs = [
            a.name for a in concept.attributes if a.required or a.unique
        ][:4]
        return GraphNode(
            id=concept.name,
            type="entity",
            data={
                "label": CONCEPT_LABELS.get(concept.name, concept.name),
                "layer": "L1",
                "attribute_count": len(concept.attributes),
                "key_attributes": key_attrs,
                "description": concept.description or "",
            },
        )

    def _build_metric_node(self, metric: MetricDefinition) -> GraphNode:
        """Build a metric node with weight information for cross-validation logic."""
        weight_map = COMPOSITE_WEIGHT_MAPS.get(metric.name, {})
        # Also try to extract weights from dependencies if not in hardcoded map
        if not weight_map and metric.type == "composite":
            weight_map = self._infer_weights_from_dependencies(metric)

        return GraphNode(
            id=metric.name,
            type="metric",
            data={
                "label": METRIC_LABELS.get(metric.name, metric.name),
                "layer": "L3",
                "metric_type": metric.type or "atomic",
                "formula": metric.formula or "",
                "dependencies": list(metric.dependencies),
                "weight_map": weight_map,
                "description": metric.description or "",
            },
        )

    def _infer_weights_from_dependencies(
        self, metric: MetricDefinition
    ) -> dict[str, float]:
        """Try to infer weights from metric formula or return empty dict."""
        # Phase 1: use hardcoded weights; future: parse formula
        return {}

    def _build_rule_node(self, rule: RuleDefinition) -> GraphNode:
        """Build a rule node from a rule definition."""
        condition_preview = self._preview_condition(rule.when)
        action_preview = rule.then.action if rule.then else ""
        label = rule.name or RULE_LABELS.get(rule.id, rule.id)

        return GraphNode(
            id=rule.id,
            type="rule",
            data={
                "label": label,
                "layer": "L4",
                "rule_type": rule.type,
                "priority": rule.priority,
                "condition_preview": condition_preview,
                "action_preview": action_preview,
                "enabled": rule.enabled,
            },
        )

    def _build_relation_edge(
        self,
        source_concept: str,
        rel: RelationDefinition,
    ) -> GraphEdge:
        """Build a relation edge between concepts."""
        return GraphEdge(
            id=f"rel_{source_concept}_{rel.name}_{rel.target}",
            source=source_concept,
            target=rel.target,
            type="relation",
            data={
                "label": rel.name,
                "cardinality": rel.cardinality,
            },
        )

    def _build_metric_dep_edge(
        self,
        dep: str,
        metric: MetricDefinition,
    ) -> GraphEdge:
        """Build a metric dependency edge with weight for cross-validation logic."""
        weight = COMPOSITE_WEIGHT_MAPS.get(metric.name, {}).get(dep)
        return GraphEdge(
            id=f"dep_{dep}_{metric.name}",
            source=dep,
            target=metric.name,
            type="metric_dep",
            data={
                "weight": weight,
            },
        )

    def _build_cross_layer_edges(self) -> list[GraphEdge]:
        """Build cross-layer edges: metric → rule data flow."""
        edges: list[GraphEdge] = []
        if not self.schema.rules:
            return edges

        for rule in self.schema.rules.ruleset:
            referenced_metrics = self._extract_referenced_metrics(rule)
            for metric_name in referenced_metrics:
                if metric_name in self._metric_index:
                    edges.append(
                        GraphEdge(
                            id=f"flow_{metric_name}_{rule.id}",
                            source=metric_name,
                            target=rule.id,
                            type="rule_input",
                            data={},
                        )
                    )
        return edges

    def _build_rule_execution_flow_edges(self) -> list[GraphEdge]:
        """Build rule execution flow edges for rule_overview visualization.

        Creates edges representing the execution order between rules:
        - Sequential edges between consecutive priority rules
        - Data flow edges between related rules
        """
        edges: list[GraphEdge] = []
        if not self.schema.rules:
            return edges

        # Sort rules by priority (higher priority executes first)
        rules = sorted(
            self.schema.rules.ruleset,
            key=lambda r: (-r.priority, r.id)
        )

        # Known data flow dependencies between rules
        KNOWN_RULE_FLOWS: list[tuple[str, str, str]] = [
            ("R001_basic_eligibility", "R002_credit_score_calculation", "基础准入后→信用评分"),
            ("R002_credit_score_calculation", "R003_guarantee_circle_detection", "信用评分后→担保圈检查"),
            ("R002_credit_score_calculation", "R004_credit_limit_calculation", "信用评分后→额度计算"),
            ("R003_guarantee_circle_detection", "R007_comprehensive_credit_decision", "担保圈影响→综合决策"),
            ("R004_credit_limit_calculation", "R006_interest_rate_pricing", "额度计算后→利率定价"),
            ("R004_credit_limit_calculation", "R007_comprehensive_credit_decision", "额度计算后→综合决策"),
            ("R005_risk_early_warning", "R007_comprehensive_credit_decision", "风险预警→综合决策"),
            ("R006_interest_rate_pricing", "R007_comprehensive_credit_decision", "利率定价后→综合决策"),
        ]

        rule_ids = {r.id for r in rules}
        existing_edges: set[tuple[str, str]] = set()

        # Add known flow edges if both endpoints exist
        for src, tgt, desc in KNOWN_RULE_FLOWS:
            if src in rule_ids and tgt in rule_ids:
                edges.append(
                    GraphEdge(
                        id=f"flow_{src}_{tgt}",
                        source=src,
                        target=tgt,
                        type="rule_flow",
                        data={
                            "label": desc,
                            "flow_type": "data_dependency",
                        },
                    )
                )
                existing_edges.add((src, tgt))

        # Add sequential edges for consecutive rules without existing flow
        for i in range(len(rules) - 1):
            src = rules[i].id
            tgt = rules[i + 1].id
            if (src, tgt) not in existing_edges and (tgt, src) not in existing_edges:
                edges.append(
                    GraphEdge(
                        id=f"seq_{src}_{tgt}",
                        source=src,
                        target=tgt,
                        type="rule_flow",
                        data={
                            "label": "执行顺序",
                            "flow_type": "sequential",
                        },
                    )
                )

        return edges

    def _extract_referenced_metrics(self, rule: RuleDefinition) -> set[str]:
        """Extract metric names referenced in a rule's condition."""
        referenced: set[str] = set()
        if not rule.when:
            return referenced

        expressions: list[str] = []
        if rule.when.expression:
            expressions.append(rule.when.expression)
        if rule.when.allOf:
            for cond in rule.when.allOf:
                if isinstance(cond, dict) and "expression" in cond:
                    expressions.append(cond["expression"])
        if rule.when.anyOf:
            for cond in rule.when.anyOf:
                if isinstance(cond, dict) and "expression" in cond:
                    expressions.append(cond["expression"])

        # Find field references that match known metric names
        for expr in expressions:
            matches = re.findall(
                r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b", expr
            )
            for match in matches:
                if match in self._metric_index:
                    referenced.add(match)

        return referenced

    def _preview_condition(self, when: RuleWhen | None) -> str:
        """Generate a short preview of the condition expression."""
        if when is None:
            return ""
        if when.expression:
            return self._truncate(when.expression, 60)
        if when.allOf:
            parts = []
            for cond in when.allOf[:2]:
                if isinstance(cond, dict) and "expression" in cond:
                    parts.append(cond["expression"])
            preview = " AND ".join(parts)
            if len(when.allOf) > 2:
                preview += " AND ..."
            return self._truncate(preview, 60)
        if when.anyOf:
            parts = []
            for cond in when.anyOf[:2]:
                if isinstance(cond, dict) and "expression" in cond:
                    parts.append(cond["expression"])
            preview = " OR ".join(parts)
            if len(when.anyOf) > 2:
                preview += " OR ..."
            return self._truncate(preview, 60)
        return ""

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Truncate text with ellipsis."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    def _get_layout_config(self, graph_type: str) -> LayoutConfig:
        """Return layout configuration based on graph type."""
        configs: dict[str, LayoutConfig] = {
            "entity_relation": LayoutConfig(
                type="force", rankdir="LR", nodesep=50, ranksep=80
            ),
            "metric_dependency": LayoutConfig(
                type="dagre", rankdir="TB", nodesep=40, ranksep=60
            ),
            "full": LayoutConfig(
                type="dagre", rankdir="LR", nodesep=50, ranksep=80
            ),
            "rule_overview": LayoutConfig(
                type="dagre", rankdir="TB", nodesep=50, ranksep=80
            ),
        }
        return configs.get(graph_type, LayoutConfig())

    def _build_metadata(
        self,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> GraphMetadata:
        """Build metadata statistics from nodes and edges."""
        entity_count = sum(1 for n in nodes if n.type == "entity")
        metric_count = sum(1 for n in nodes if n.type == "metric")
        rule_count = sum(1 for n in nodes if n.type == "rule")
        relation_count = sum(1 for e in edges if e.type == "relation")
        return GraphMetadata(
            entity_count=entity_count,
            relation_count=relation_count,
            metric_count=metric_count,
            rule_count=rule_count,
        )


class RuleChainGraphBuilder:
    """Build X6-compatible rule chain DAG data from KGML Schema."""

    def __init__(self, schema: KGMLSchema) -> None:
        self.schema = schema

    def build(self, dimension: str) -> RuleChainGraphData:
        """Build rule chain DAG for the specified dimension."""
        rules = self.schema.get_rules_for_dimension(dimension)
        rules = sorted(rules, key=lambda r: -r.priority)

        nodes = [
            self._build_rule_node(rule, idx) for idx, rule in enumerate(rules)
        ]
        edges = self._build_data_flow_edges(rules)
        dim_info = self._get_dimension_info(dimension)

        return RuleChainGraphData(
            dimension=dimension,
            nodes=nodes,
            edges=edges,
            dimension_info=dim_info,
        )

    def _build_rule_node(
        self, rule: RuleDefinition, index: int
    ) -> RuleChainNode:
        """Build a rule chain node with auto-positioning."""
        y = index * 140 + 100
        x = 300

        condition_str = self._serialize_condition(rule.when)
        action_str = rule.then.action if rule.then else ""
        label = rule.name or RULE_LABELS.get(rule.id, rule.id)

        return RuleChainNode(
            id=rule.id,
            position={"x": float(x), "y": float(y)},
            data={
                "ruleId": rule.id,
                "ruleName": label,
                "ruleType": rule.type,
                "priority": rule.priority,
                "condition": condition_str,
                "action": action_str,
                "enabled": rule.enabled,
                "dimensions": (
                    rule.scope.get("dimensions", []) if rule.scope else []
                ),
            },
        )

    def _build_data_flow_edges(
        self, rules: list[RuleDefinition]
    ) -> list[RuleChainEdge]:
        """Build edges representing data flow between rules.

        Rules execute in priority order; later rules may depend on
        outputs from earlier rules.
        """
        edges: list[RuleChainEdge] = []

        # Known data flow dependencies (from schema logic)
        KNOWN_FLOWS: dict[str, list[tuple[str, str, str]]] = {
            "credit_assessment": [
                ("R001_basic_eligibility", "R002_credit_score_calculation", "R001通过后→执行信用评分"),
                ("R002_credit_score_calculation", "R003_guarantee_circle_detection", "信用评分后→检查担保圈"),
                ("R002_credit_score_calculation", "R004_credit_limit_calculation", "信用评分后→计算额度"),
                ("R003_guarantee_circle_detection", "R007_comprehensive_credit_decision", "担保圈影响决策"),
                ("R004_credit_limit_calculation", "R006_interest_rate_pricing", "额度计算后→利率定价"),
                ("R004_credit_limit_calculation", "R007_comprehensive_credit_decision", "额度计算后→综合决策"),
            ],
            "transaction_monitoring": [
                ("R008_large_transaction_monitor", "R009_transaction_volatility", "大额交易后→波动性检测"),
            ],
            "risk_early_warning": [],
        }

        # Get the dimensions in these rules
        rule_ids = {r.id for r in rules}
        dimensions: set[str] = set()
        for rule in rules:
            if rule.scope and "dimensions" in rule.scope:
                for dim in rule.scope["dimensions"]:
                    dimensions.add(dim)

        # Add known flow edges if both endpoints exist
        for dim in dimensions:
            for src, tgt, desc in KNOWN_FLOWS.get(dim, []):
                if src in rule_ids and tgt in rule_ids:
                    edges.append(
                        RuleChainEdge(
                            id=f"{src}-{tgt}",
                            source=src,
                            target=tgt,
                            data={
                                "dependency_type": "data_flow",
                                "description": desc,
                            },
                        )
                    )

        # Also add sequential edges for consecutive rules
        # (if no known flow exists between them)
        existing_edges = {(e.source, e.target) for e in edges}
        for i in range(len(rules) - 1):
            src = rules[i].id
            tgt = rules[i + 1].id
            if (src, tgt) not in existing_edges:
                edges.append(
                    RuleChainEdge(
                        id=f"{src}-{tgt}",
                        source=src,
                        target=tgt,
                        data={
                            "dependency_type": "sequential",
                            "description": f"顺序执行: {src} → {tgt}",
                        },
                    )
                )

        return edges

    def _serialize_condition(self, when: RuleWhen | None) -> str:
        """Serialize a RuleWhen to a string expression."""
        if when is None:
            return ""
        if when.expression:
            return when.expression
        if when.allOf:
            parts = []
            for cond in when.allOf:
                if isinstance(cond, dict) and "expression" in cond:
                    parts.append(cond["expression"])
                elif hasattr(cond, "expression") and cond.expression:
                    parts.append(cond.expression)
            return " AND ".join(parts)
        if when.anyOf:
            parts = []
            for cond in when.anyOf:
                if isinstance(cond, dict) and "expression" in cond:
                    parts.append(cond["expression"])
                elif hasattr(cond, "expression") and cond.expression:
                    parts.append(cond.expression)
            return " OR ".join(parts)
        return ""

    def _get_dimension_info(self, dimension: str) -> DimensionInfo:
        """Get dimension metadata from schema."""
        if not self.schema.rules:
            return DimensionInfo(name=dimension, rule_count=0)

        rules = self.schema.get_rules_for_dimension(dimension)

        # Find dimension definition
        applicable_entities: list[str] = []
        description: str | None = None
        if self.schema.rules.rule_dimensions:
            for dim in self.schema.rules.rule_dimensions:
                if hasattr(dim, "name") and dim.name == dimension:
                    description = dim.description
                    applicable_entities = dim.applicable_entities
                    break

        return DimensionInfo(
            name=dimension,
            description=description,
            applicable_entities=applicable_entities,
            rule_count=len(rules),
        )
