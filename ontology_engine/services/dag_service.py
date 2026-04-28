# ontology_engine/services/dag_service.py
"""DAG service for building metric and rule computation graphs."""
from __future__ import annotations

from collections import deque
from typing import Any

from ontology_engine.engine.rule.models import RuleStep


class DAGNode:
    """Represents a node in the DAG."""

    def __init__(
        self,
        id: str,
        type: str,  # noqa: A002
        label: str,
        layer: str,
        data: dict[str, Any] | None = None,
    ):
        self.id = id
        self.type = type
        self.label = label
        self.layer = layer
        self.data = data or {}


class DAGEdge:
    """Represents an edge in the DAG."""

    def __init__(
        self,
        id: str,
        source: str,
        target: str,
        edge_type: str,  # noqa: A002
        data: dict[str, Any] | None = None,
    ):
        self.id = id
        self.source = source
        self.target = target
        self.type = edge_type
        self.data = data or {}


class DAGGraphData:
    """Graph data structure for visualization."""

    def __init__(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ):
        self.nodes = nodes
        self.edges = edges
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "metadata": self.metadata,
        }


class DAGService:
    """Service for building and querying computation DAGs.

    Builds DAGs for:
    - Metric dependencies (L1 → L3 atomic → L3 derived → L3 composite)
    - Rule execution (L4 rule groups → rule steps → decisions)
    - Full computation graph (L1 → L3 → L4 → decision)
    """

    # Node colors by layer (for G6 visualization)
    LAYER_COLORS = {
        "L1": "#8C8C8C",      # Gray - attributes
        "L3_atomic": "#52C41A",  # Green - atomic metrics
        "L3_derived": "#FA8C16",  # Orange - derived metrics
        "L3_composite": "#722ED1",  # Purple - composite metrics
        "L3_graph": "#F5222D",  # Red - graph metrics
        "L4_rule_group": "#1677FF",  # Blue - rule groups
        "L4_rule_step": "#4096FF",  # Light blue - rule steps
        "decision": "#237804",  # Dark green - decisions
    }

    def __init__(self, storage=None, schema=None):
        """Initialize DAGService.

        Args:
            storage: Optional storage backend
            schema: Optional KGMLSchema for metric information
        """
        self._storage = storage
        self._schema = schema

    def build_metric_dag(
        self,
        target_metric: str | None = None,
        depth: int = 5,
    ) -> DAGGraphData:
        """Build metric dependency DAG.

        Args:
            target_metric: Optional target metric to focus on
            depth: Maximum depth to traverse

        Returns:
            DAGGraphData for visualization
        """
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen_nodes: set[str] = set()
        seen_edges: set[str] = set()

        if self._schema and self._schema.metrics:
            metric_index = {m.name: m for m in self._schema.metrics}

            def add_metric_node(name: str, layer: str) -> None:
                if name in seen_nodes:
                    return
                seen_nodes.add(name)

                metric = metric_index.get(name)
                label = name
                if metric and hasattr(metric, "description") and metric.description:
                    label = f"{name}\n({metric.description[:20]}...)"
                elif metric:
                    label = f"{name}\n({metric.type})"

                nodes.append({
                    "id": name,
                    "type": "metric",
                    "data": {
                        "label": label,
                        "layer": layer,
                        "metric_type": metric.type if metric else "unknown",
                        "color": self.LAYER_COLORS.get(layer, "#8C8C8C"),
                    },
                })

            def traverse_metric(name: str, current_depth: int) -> None:
                if current_depth <= 0 or name in seen_nodes:
                    return

                metric = metric_index.get(name)
                if not metric:
                    return

                # Determine layer type
                metric_type = getattr(metric, "type", "atomic")
                layer = f"L3_{metric_type}"

                add_metric_node(name, layer)

                # Add dependencies
                deps = getattr(metric, "dependencies", [])
                for dep in deps:
                    dep_metric = metric_index.get(dep)
                    dep_type = getattr(dep_metric, "type", "atomic") if dep_metric else "atomic"
                    dep_layer = f"L3_{dep_type}"

                    add_metric_node(dep, dep_layer)

                    edge_id = f"dep_{dep}_{name}"
                    if edge_id not in seen_edges:
                        seen_edges.add(edge_id)
                        weight = None
                        if hasattr(metric, "components"):
                            for comp in getattr(metric, "components", []):
                                if comp.get("name") == dep:
                                    weight = comp.get("weight")
                                    break
                        edges.append({
                            "id": edge_id,
                            "source": dep,
                            "target": name,
                            "type": "metric_dep",
                            "data": {"weight": weight},
                        })

                    traverse_metric(dep, current_depth - 1)

            if target_metric:
                traverse_metric(target_metric, depth)
            else:
                # Add all metrics
                for m in self._schema.metrics:
                    add_metric_node(m.name, f"L3_{getattr(m, 'type', 'atomic')}")

        return DAGGraphData(
            nodes=nodes,
            edges=edges,
            metadata={
                "graph_type": "metric_dependency",
                "target": target_metric,
                "depth": depth,
                "node_count": len(nodes),
                "edge_count": len(edges),
            },
        )

    def build_rule_group_dag(
        self,
        rule_group_name: str,
        steps: list[RuleStep] | None = None,
    ) -> DAGGraphData:
        """Build rule group execution DAG.

        Args:
            rule_group_name: Rule group name
            steps: Optional list of RuleStep objects

        Returns:
            DAGGraphData for visualization
        """
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen_edges: set[str] = set()

        # Add rule group node
        nodes.append({
            "id": rule_group_name,
            "type": "rule_group",
            "data": {
                "label": rule_group_name,
                "layer": "L4_rule_group",
                "color": self.LAYER_COLORS["L4_rule_group"],
            },
        })

        # Add step nodes and edges
        if steps:
            for i, step in enumerate(steps):
                step_id = f"{rule_group_name}.{step.id}"
                nodes.append({
                    "id": step_id,
                    "type": "rule_step",
                    "data": {
                        "label": f"{step.id}: {step.name}",
                        "layer": "L4_rule_step",
                        "color": self.LAYER_COLORS["L4_rule_step"],
                        "operator": step.then.operator if step.then else None,
                        "condition": step.when.expression if step.when else None,
                        "order": step.order,
                    },
                })

                # Edge from rule group to step
                edge_id = f"rg_{rule_group_name}_{step.id}"
                if edge_id not in seen_edges:
                    seen_edges.add(edge_id)
                    edges.append({
                        "id": edge_id,
                        "source": rule_group_name,
                        "target": step_id,
                        "type": "rule_flow",
                        "data": {"flow_type": "contains"},
                    })

                # Edge from previous step to this step (execution order)
                if i > 0:
                    prev_step = steps[i - 1]
                    edge_id = f"flow_{prev_step.id}_{step.id}"
                    if edge_id not in seen_edges:
                        seen_edges.add(edge_id)
                        edges.append({
                            "id": edge_id,
                            "source": f"{rule_group_name}.{prev_step.id}",
                            "target": step_id,
                            "type": "rule_flow",
                            "data": {"flow_type": "sequential"},
                        })

        return DAGGraphData(
            nodes=nodes,
            edges=edges,
            metadata={
                "graph_type": "rule_group",
                "rule_group": rule_group_name,
                "node_count": len(nodes),
                "edge_count": len(edges),
            },
        )

    def build_full_computation_dag(
        self,
        target_output: str | None = None,
        depth: int = 10,
    ) -> DAGGraphData:
        """Build full computation DAG from L1 to decision.

        Args:
            target_output: Optional target output to focus on
            depth: Maximum depth

        Returns:
            DAGGraphData for visualization
        """
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen_nodes: set[str] = set()
        seen_edges: set[str] = set()

        def add_node(node_id: str, node_type: str, layer: str, label: str) -> None:
            if node_id in seen_nodes:
                return
            seen_nodes.add(node_id)
            nodes.append({
                "id": node_id,
                "type": node_type,
                "data": {
                    "label": label,
                    "layer": layer,
                    "color": self.LAYER_COLORS.get(layer, "#8C8C8C"),
                },
            })

        def add_edge(edge_id: str, source: str, target: str, edge_type: str, data: dict | None = None) -> None:
            if edge_id in seen_edges:
                return
            seen_edges.add(edge_id)
            edges.append({
                "id": edge_id,
                "source": source,
                "target": target,
                "type": edge_type,
                "data": data or {},
            })

        # Build metric DAG portion
        if self._schema and self._schema.metrics:
            metric_index = {m.name: m for m in self._schema.metrics}

            # Build upstream from target
            def build_upstream(metric_name: str, current_depth: int) -> None:
                if current_depth <= 0 or metric_name in seen_nodes:
                    return

                metric = metric_index.get(metric_name)
                if not metric:
                    return

                layer = f"L3_{getattr(metric, 'type', 'atomic')}"
                label = f"{metric_name}\n({getattr(metric, 'type', 'unknown')})"
                add_node(metric_name, "metric", layer, label)

                # Add dependencies
                deps = getattr(metric, "dependencies", [])
                for dep in deps:
                    dep_metric = metric_index.get(dep)
                    dep_type = getattr(dep_metric, "type", "atomic") if dep_metric else "atomic"
                    dep_layer = f"L3_{dep_type}"
                    dep_label = f"{dep}\n({dep_type})"
                    add_node(dep, "metric", dep_layer, dep_label)

                    edge_id = f"flow_{dep}_{metric_name}"
                    add_edge(edge_id, dep, metric_name, "data_flow")

                    build_upstream(dep, current_depth - 1)

            if target_output:
                build_upstream(target_output, depth)
            else:
                for m in self._schema.metrics:
                    layer = f"L3_{getattr(m, 'type', 'atomic')}"
                    add_node(m.name, "metric", layer, f"{m.name}\n({getattr(m, 'type', 'unknown')})")

                    for dep in getattr(m, "dependencies", []):
                        dep_metric = metric_index.get(dep)
                        dep_type = getattr(dep_metric, "type", "atomic") if dep_metric else "atomic"
                        dep_layer = f"L3_{dep_type}"
                        add_node(dep, "metric", dep_layer, f"{dep}\n({dep_type})")

                        edge_id = f"flow_{dep}_{m.name}"
                        add_edge(edge_id, dep, m.name, "data_flow")

        return DAGGraphData(
            nodes=nodes,
            edges=edges,
            metadata={
                "graph_type": "full_computation",
                "target": target_output,
                "depth": depth,
                "node_count": len(nodes),
                "edge_count": len(edges),
            },
        )

    def find_path(self, source: str, target: str) -> list[dict[str, Any]] | None:
        """Find path from source to target in the DAG.

        Uses BFS to find the shortest path.

        Args:
            source: Source node ID
            target: Target node ID

        Returns:
            List of edges forming the path, or None if no path found
        """
        if not self._schema:
            return None

        # Build adjacency list from schema
        adj: dict[str, list[str]] = {}
        if self._schema.metrics:
            for m in self._schema.metrics:
                deps = getattr(m, "dependencies", [])
                for dep in deps:
                    if dep not in adj:
                        adj[dep] = []
                    adj[dep].append(m.name)

        # BFS
        visited: set[str] = {source}
        queue: deque[tuple[str, list[dict[str, Any]]]] = deque([(source, [])])

        while queue:
            node, path = queue.popleft()

            if node == target:
                return path

            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    new_path = path + [{
                        "source": node,
                        "target": neighbor,
                        "id": f"path_{node}_{neighbor}",
                    }]
                    queue.append((neighbor, new_path))

        return None

    def to_graph_data(self, graph_type: str, **kwargs) -> dict[str, Any]:
        """Build graph data for visualization.

        Args:
            graph_type: Type of graph to build
            **kwargs: Additional arguments

        Returns:
            Dict with nodes, edges, metadata
        """
        if graph_type == "metric_dependency":
            dag = self.build_metric_dag(
                target_metric=kwargs.get("target"),
                depth=kwargs.get("depth", 5),
            )
        elif graph_type == "rule_group":
            dag = self.build_rule_group_dag(
                rule_group_name=kwargs.get("rule_group", "default"),
                steps=kwargs.get("steps"),
            )
        elif graph_type == "full_computation":
            dag = self.build_full_computation_dag(
                target_output=kwargs.get("target"),
                depth=kwargs.get("depth", 10),
            )
        else:
            dag = DAGGraphData(nodes=[], edges=[])

        return dag.to_dict()

    def build_execution_dag(self, steps: list[RuleStep]) -> dict[str, Any]:
        from ontology_engine.engine.rule.dag_builder import DAGBuilder

        if not steps:
            return {"layers": [], "step_map": {}, "has_cycle": False}

        dag_builder = DAGBuilder()
        try:
            dag = dag_builder.build(steps)
            return {
                "layers": [
                    [{"id": s.id, "name": s.name} for s in layer]
                    for layer in dag.layers
                ],
                "step_map": {sid: {"id": s.id, "name": s.name} for sid, s in dag.step_map.items()},
                "has_cycle": False,
            }
        except Exception as e:
            return {"layers": [], "step_map": {}, "has_cycle": True, "error": str(e)}
