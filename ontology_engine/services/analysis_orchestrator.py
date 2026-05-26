from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Any

from ontology_engine.core.semantic_space import SemanticSpace, SemanticSpaceStorage
from ontology_engine.core.types import apply_overrides, deep_copy_entity_data
from ontology_engine.services.rule_execution_service import RuleExecutionService
from ontology_engine.services.simulation_orchestrator import SimulationOrchestrator
from ontology_engine.services.simulation_service import SimulationService
from ontology_engine.services.space_service import SpaceService

logger = logging.getLogger(__name__)


def _rule_applies_to(rule: dict) -> list:
    applies = rule.get("applies_to") or rule.get("target_objects") or []
    if isinstance(applies, dict):
        return applies.get("fact_objects", [])
    return applies


def _rule_outputs(rule: dict) -> list[dict]:
    return rule.get("outputs") or rule.get("output_elements") or []


def _metric_type(element: dict) -> str:
    return element.get("type") or element.get("element_type") or "derived"


class AnalysisOrchestrator:

    def __init__(
        self,
        storage: SemanticSpaceStorage | None = None,
        rule_execution: RuleExecutionService | None = None,
    ) -> None:
        self._storage = storage or SemanticSpaceStorage()
        self._rule_execution = rule_execution or RuleExecutionService()

    async def run_full_analysis(
        self,
        space: SemanticSpace,
        entity: dict,
        dimension: str,
        overrides: dict[str, Any],
        include_trace: bool,
    ) -> dict[str, Any]:
        expression_engine = SimulationService.create_expression_engine()

        entity_data = deep_copy_entity_data(entity)
        entity_data["_fact_object"] = entity.get("_fact_object") or entity.get(
            "_concept", "Unknown"
        )
        apply_overrides(entity_data, overrides)

        context = SimulationService.create_execution_context(
            entity_id=entity.get("entity_id", ""),
            dimension=dimension,
            entity_data=entity_data,
            computed_metrics={},
        )

        steps: list[dict[str, Any]] = []
        final_outputs: dict[str, Any] = {}

        l3_computed = self._precompute_l3_elements(space, entity_data)
        entity_data.update(l3_computed)
        context.computed_metrics.update(l3_computed)

        all_rules = space.layers.L4_business_logic.rule_definitions
        enabled_rules = [r for r in all_rules if r.get("enabled", True)]
        skipped_disabled = [
            r for r in all_rules if not r.get("enabled", True)
        ]

        for rule in skipped_disabled:
            steps.append({
                "step": len(steps) + 1,
                "rule_id": rule["id"],
                "rule_name": rule.get("name", rule["id"]),
                "rule_type": rule.get("rule_type", "constraint"),
                "status": "skipped",
                "explanation": "规则已禁用",
                "inputs": [],
                "outputs": [],
            })

        if not enabled_rules:
            return {
                "entity_id": entity.get("entity_id", ""),
                "dimension": dimension,
                "steps": steps,
                "execution_path": [],
                "skipped_rules": [
                    r["id"] for r in skipped_disabled
                ],
                "final_outputs": final_outputs,
                "decision": "REVIEW",
                "computed_metrics": context.computed_metrics,
            }

        try:
            _orchestrator = SimulationOrchestrator(
                SpaceService(self._storage)
            )
            result = await _orchestrator.analyze_dependencies(
                enabled_rules
            )
            rule_levels = result["levels"]
        except ValueError as e:
            logger.warning(
                f"DAG execution failed, falling back to priority mode: {e}"
            )

            sorted_rules = sorted(
                enabled_rules,
                key=lambda r: r.get("priority", 100),
                reverse=True,
            )

            for rule in sorted_rules:
                step = await self._rule_execution.execute_single_rule(
                    rule,
                    space,
                    entity_data,
                    context,
                    expression_engine,
                    len(steps) + 1,
                    include_trace,
                )
                steps.append(step)
                if step["status"] == "passed":
                    for item in step.get("outputs", []):
                        if isinstance(item, dict):
                            final_outputs[
                                item.get("name", item.get("id", ""))
                            ] = item.get("value")
                        elif (
                            isinstance(item, (list, tuple))
                            and len(item) == 2
                        ):
                            final_outputs[item[0]] = item[1]

            return self._build_result(
                entity, dimension, steps, final_outputs, context
            )

        max_level = max(rule_levels.values()) if rule_levels else 0
        rule_map = {r["id"]: r for r in enabled_rules}

        level_groups: dict[int, list[dict]] = defaultdict(list)
        for rule_id, level in rule_levels.items():
            level_groups[level].append(rule_map[rule_id])

        for level in range(max_level + 1):
            level_rules = level_groups.get(level, [])
            level_rules.sort(
                key=lambda r: r.get("priority", 100), reverse=True
            )

            entity_type = entity_data.get("_fact_object") or entity_data.get(
                "_concept", ""
            )

            for rule in level_rules:
                target_objects = _rule_applies_to(rule)
                if (
                    target_objects
                    and entity_type
                    and entity_type not in target_objects
                ):
                    steps.append({
                        "step": len(steps) + 1,
                        "rule_id": rule["id"],
                        "rule_name": rule.get("name", rule["id"]),
                        "rule_type": rule.get("rule_type", "constraint"),
                        "status": "skipped",
                        "explanation": f"实体类型 {entity_type} 不在目标范围 {target_objects}",
                        "inputs": [],
                        "outputs": [],
                        "level": level,
                    })
                    continue

                step = await self._rule_execution.execute_single_rule(
                    rule,
                    space,
                    entity_data,
                    context,
                    expression_engine,
                    len(steps) + 1,
                    include_trace,
                )
                step["level"] = level
                steps.append(step)

                if step["status"] == "passed":
                    for item in step.get("outputs", []):
                        final_outputs[item["name"]] = item["value"]

        return self._build_result(
            entity, dimension, steps, final_outputs, context
        )

    def topological_sort_rules(
        self, nodes: list[dict], edges: list[dict]
    ) -> list[str]:
        in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
        adj: dict[str, list[str]] = defaultdict(list)

        for edge in edges:
            src = edge["source"]
            tgt = edge["target"]
            if src in in_degree and tgt in in_degree:
                adj[src].append(tgt)
                in_degree[tgt] += 1

        priority_map = {
            n["id"]: n.get("priority", 100) for n in nodes
        }
        queue = deque(
            sorted(
                [nid for nid, deg in in_degree.items() if deg == 0],
                key=lambda nid: -priority_map.get(nid, 100),
            )
        )

        order: list[str] = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for neighbor in sorted(
                adj[nid],
                key=lambda x: -priority_map.get(x, 100),
            ):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        remaining = [
            n["id"] for n in nodes if n["id"] not in set(order)
        ]
        return order + remaining

    def _precompute_l3_elements(
        self, space: SemanticSpace, entity_data: dict
    ) -> dict[str, Any]:
        computed: dict[str, Any] = {}

        for elem in space.layers.L3_analytical_elements:
            elem_id = elem.get("id", "")
            elem_type = _metric_type(elem)
            source = elem.get("source", {})
            dependencies = elem.get("dependencies", [])

            if elem_id in computed:
                continue

            if elem_type == "atomic":
                attr_path = source.get("attribute", "")
                if attr_path:
                    value = self._get_nested_path(entity_data, attr_path)
                    computed[elem_id] = value
                else:
                    computed[elem_id] = None

            elif elem_type == "derived":
                if dependencies:
                    first_dep = dependencies[0]
                    if first_dep in computed:
                        computed[elem_id] = computed[first_dep]
                    elif first_dep in entity_data:
                        computed[elem_id] = entity_data[first_dep]
                    else:
                        computed[elem_id] = None
                else:
                    computed[elem_id] = None

            elif elem_type in ("composite", "graph"):
                computed[elem_id] = None

            else:
                computed[elem_id] = None

        return computed

    def _get_nested_path(self, data: dict, path: str) -> Any:
        value: Any = data
        for key in path.split("."):
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _build_rule_dependency_graph(
        self, rules: list[dict]
    ) -> tuple[dict[str, list[str]], dict[str, int], list[dict]]:
        output_map: dict[str, list[str]] = defaultdict(list)
        for rule in rules:
            for out_elem in _rule_outputs(rule):
                elem_name = out_elem.get("name") or out_elem.get("id", "")
                if elem_name:
                    output_map[elem_name].append(rule["id"])

        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {r["id"]: 0 for r in rules}
        dep_edges: list[dict[str, Any]] = []

        for rule in rules:
            rule_id = rule["id"]
            for in_elem in _rule_outputs(rule):
                elem_name = (
                    in_elem.get("name") or in_elem.get("id", "")
                )
                producers = output_map.get(elem_name, [])
                for producer_id in producers:
                    if (
                        producer_id != rule_id
                        and producer_id in in_degree
                    ):
                        adj[producer_id].append(rule_id)
                        in_degree[rule_id] += 1
                        dep_edges.append({
                            "source": producer_id,
                            "target": rule_id,
                            "via_element": elem_name,
                        })

        return dict(adj), in_degree, dep_edges

    def _compute_rule_levels(
        self,
        rules: list[dict],
        adj: dict[str, list[str]],
        in_degree: dict[str, int],
    ) -> dict[str, int]:
        rule_levels: dict[str, int] = {}
        remaining_in_degree = dict(in_degree)
        level_queue: deque[str] = deque()

        for rule_id, deg in remaining_in_degree.items():
            if deg == 0:
                level_queue.append(rule_id)

        while level_queue:
            current_level_size = len(level_queue)
            for _ in range(current_level_size):
                rule_id = level_queue.popleft()
                if rule_id not in rule_levels:
                    rule_levels[rule_id] = len(
                        [
                            r
                            for r in rules
                            if rule_id in adj.get(r["id"], [])
                        ]
                    )

                for neighbor in adj.get(rule_id, []):
                    remaining_in_degree[neighbor] -= 1
                    if remaining_in_degree[neighbor] == 0:
                        level_queue.append(neighbor)

        unassigned = [
            r["id"] for r in rules if r["id"] not in rule_levels
        ]
        if unassigned:
            raise ValueError(
                f"Circular dependency detected involving rules: {unassigned}"
            )

        return rule_levels

    def _detect_circular_dependencies(
        self,
        rules: list[dict],
        adj: dict[str, list[str]],
        in_degree: dict[str, int],
    ) -> list[list[str]]:
        cycles: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])

            path.pop()
            rec_stack.remove(node)
            return False

        for rule in rules:
            rule_id = rule["id"]
            if rule_id not in visited:
                dfs(rule_id)

        return cycles

    def _build_result(
        self,
        entity: dict,
        dimension: str,
        steps: list[dict[str, Any]],
        final_outputs: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        decision = context.computed_metrics.get("decision")
        if not decision:
            if context.computed_metrics.get("eligible") is False:
                decision = "REJECTED"
            elif context.computed_metrics.get("eligible") is True:
                decision = "APPROVED"
            elif context.computed_metrics.get("decision") == "APPROVED":
                decision = "APPROVED"
            else:
                decision = "REVIEW"

        return {
            "entity_id": entity.get("entity_id", ""),
            "dimension": dimension,
            "steps": steps,
            "execution_path": [
                s["rule_id"]
                for s in steps
                if s["status"] == "passed"
            ],
            "skipped_rules": [
                s["rule_id"]
                for s in steps
                if s["status"] == "skipped"
            ],
            "final_outputs": final_outputs,
            "decision": decision,
            "computed_metrics": context.computed_metrics,
        }
