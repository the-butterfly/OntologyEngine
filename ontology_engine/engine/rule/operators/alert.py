# ontology_engine/engine/rule/operators/alert.py
"""Alert and graph operators."""

from typing import Any

from ontology_engine.engine.rule.operators.base import Operator, OperatorRegistry


@OperatorRegistry.register("trigger_alert")
class TriggerAlertOperator(Operator):
    """Trigger an alert.

    Inputs:
        - alert_level: Level of alert (info, warning, critical)
        - alert_type: Type/category of alert
        - message: Alert message
        - data: Additional data for the alert

    Example:
        action:
            operator: "trigger_alert"
            inputs:
                alert_level: "warning"
                alert_type: "guarantee_circle"
                message: "Circular guarantee detected"
    """

    @property
    def name(self) -> str:
        return "trigger_alert"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        alert_level = inputs.get("alert_level", "info")
        alert_type = inputs.get("alert_type", "general")
        message = inputs.get("message", "")
        message_template = inputs.get("message_template")
        if message_template:
            try:
                message = message_template.format(**context)
            except (KeyError, ValueError):
                message = message_template
        data = inputs.get("data", {})

        # Create alert object
        alert = {
            "level": alert_level,
            "type": alert_type,
            "message": message,
            "data": data,
            "alert_triggered": True
        }

        return alert


@OperatorRegistry.register("graph_traversal")
class GraphTraversalOperator(Operator):
    """Graph traversal for aggregation.

    Inputs:
        - relation_type: Type of relation to traverse
        - direction: "outgoing" or "incoming"
        - aggregation: Aggregation function (count, sum, avg, min, max)
        - target_field: Field to aggregate from neighbor entities
        - max_depth: Maximum traversal depth (default: 1)

    Example:
        action:
            operator: "graph_traversal"
            inputs:
                relation_type: "guarantees_for"
                direction: "outgoing"
                aggregation: "sum"
                target_field: "amount"
                max_depth: 2
    """

    @property
    def name(self) -> str:
        return "graph_traversal"

    async def execute(
        self,
        inputs: dict[str, Any],
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        relation_type = inputs.get("relation_type")
        direction = inputs.get("direction", "outgoing")
        aggregation = inputs.get("aggregation", "count")
        max_depth = inputs.get("max_depth", 1)

        # For Phase 1, we use storage.get_neighbors if available
        # The actual graph traversal implementation would use NetworkX

        # Placeholder result - actual implementation would do real traversal
        result = {
            "graph_aggregation": None,
            "relation_type": relation_type,
            "direction": direction,
            "aggregation": aggregation,
            "traversal_depth": max_depth,
            "note": "Phase 1: Graph traversal uses storage.get_neighbors"
        }

        return result
