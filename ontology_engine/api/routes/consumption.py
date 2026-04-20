# ontology_engine/api/routes/consumption.py
"""Consumption API routes for semantic spaces.

Prefix: /v1/consumption/{viewId}/
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ontology_engine.api.dto.responses import error_response, success_response
from ontology_engine.core.semantic_space import (
    SemanticSpace,
    SpaceType,
    SemanticSpaceStorage,
)
from ontology_engine.services.simulation_service import SimulationService

router = APIRouter(prefix="/v1", tags=["Consumption"])


# ============================================================================
# Canonical Field Helpers (support both legacy and canonical names)
# ============================================================================

def _metric_type(element: dict) -> str:
    """Get metric type, supporting both canonical and legacy field names."""
    return element.get("type") or element.get("element_type") or "derived"


def _rule_inputs(rule: dict) -> list[dict]:
    """Get rule inputs, supporting both canonical and legacy field names."""
    return rule.get("inputs") or rule.get("input_elements") or []


def _rule_outputs(rule: dict) -> list[dict]:
    """Get rule outputs, supporting both canonical and legacy field names."""
    return rule.get("outputs") or rule.get("output_elements") or []


# ============================================================================
# Storage Helper
# ============================================================================

def _get_storage() -> SemanticSpaceStorage:
    return SemanticSpaceStorage()


# ============================================================================
# Request/Response Models
# ============================================================================

class ExecuteAnalyzeRequest(BaseModel):
    entity_id: str
    dimension: str = "credit_assessment"
    include_trace: bool = True


class ExecuteSimulateRequest(BaseModel):
    entity_id: str
    dimension: str = "credit_assessment"
    overrides: dict[str, Any] | None = None
    include_trace: bool = True


# ============================================================================
# View Management
# ============================================================================

@router.get("/views", response_model=dict)
async def list_views():
    """List all consumption views."""
    storage = _get_storage()
    all_metadata = await storage.list()

    consumption_views = [
        m for m in all_metadata if m.space_type == SpaceType.CONSUMPTION
    ]

    views = []
    for metadata in consumption_views:
        space = await storage.load(metadata.id)
        if space:
            views.append({
                "id": space.metadata.id,
                "name": space.metadata.name,
                "description": space.metadata.description,
                "status": space.metadata.status.value,
                "entity_count": len(space.instances.entities),
                "rule_count": len(space.layers.L4_business_logic.rule_definitions),
                "created_at": space.metadata.created_at.isoformat(),
            })

    return success_response(data=views)


@router.get("/views/{view_id}", response_model=dict)
async def get_view(view_id: str):
    """Get a consumption view by ID."""
    storage = _get_storage()
    space = await storage.load(view_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found")

    if space.metadata.space_type != SpaceType.CONSUMPTION:
        return error_response(code="NOT_FOUND", message=f"{view_id} is not a consumption view")

    return success_response(data={
        "id": space.metadata.id,
        "name": space.metadata.name,
        "description": space.metadata.description,
        "status": space.metadata.status.value,
        "entity_count": len(space.instances.entities),
        "relation_count": len(space.instances.relations),
        "rule_definition_count": len(space.layers.L4_business_logic.rule_definitions),
        "L1_count": len(space.layers.L1_fact_objects),
        "L2_count": len(space.layers.L2_categorizations),
        "L3_count": len(space.layers.L3_analytical_elements),
        "created_at": space.metadata.created_at.isoformat(),
    })


# ============================================================================
# Entities in View
# ============================================================================

@router.get("/views/{view_id}/entities", response_model=dict)
async def list_view_entities(
    view_id: str,
    concept: str | None = Query(default=None),
):
    """List all entity instances in a consumption view."""
    storage = _get_storage()
    space = await storage.load(view_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found")

    entities = space.instances.entities
    if concept:
        entities = [e for e in entities if (e.get("_fact_object") or e.get("_concept")) == concept]

    return success_response(data=entities)


# ============================================================================
# Visualization
# ============================================================================

@router.get("/views/{view_id}/schema-graph", response_model=dict)
async def get_schema_graph(
    view_id: str,
    graph_type: str = Query(default="entity_relation"),
    layer_filter: str | None = Query(default=None),
):
    """Get schema visualization graph data for a consumption view."""
    storage = _get_storage()
    space = await storage.load(view_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found")

    nodes = []
    edges = []

    # L1: Fact Objects
    for entity in space.layers.L1_fact_objects:
        entity_id = entity.get("id", entity.get("name", "unknown"))
        nodes.append({
            "id": entity_id,
            "type": "entity",
            "data": {
                "label": entity.get("name", entity_id),
                "category": "entity",
                "layer": "L1",
                "properties": entity.get("properties", []),
                "description": entity.get("description", ""),
            }
        })
        for rel in entity.get("relations", []):
            rel_id = f"{entity_id}__{rel.get('target')}__{rel.get('name')}"
            edges.append({
                "id": rel_id,
                "source": entity_id,
                "target": rel.get("target", ""),
                "type": "relation",
                "data": {
                    "label": rel.get("name", ""),
                    "cardinality": rel.get("cardinality", ""),
                },
            })

    # L2: Categorizations
    for cat in space.layers.L2_categorizations:
        cat_id = cat.get("id", cat.get("name", "unknown"))
        nodes.append({
            "id": cat_id,
            "type": "category",
            "data": {
                "label": cat.get("name", cat_id),
                "category": "categorization",
                "layer": "L2",
                "applicable_to": cat.get("applicable_to", []),
                "description": cat.get("description", ""),
            }
        })

    # L3: Analytical Elements
    for element in space.layers.L3_analytical_elements:
        elem_id = element.get("id", element.get("name", "unknown"))
        elem_type = _metric_type(element)
        nodes.append({
            "id": elem_id,
            "type": "metric",
            "data": {
                "label": element.get("name", elem_id),
                "category": "element",
                "layer": "L3",
                "type": elem_type,  # canonical field name
                "formula": element.get("formula", ""),
                "dependencies": element.get("dependencies", []),
                "overridable": element.get("overridable", False),
                "description": element.get("description", ""),
            }
        })
        # Add dependency edges between L3 elements
        for dep in element.get("dependencies", []):
            edges.append({
                "id": f"{dep}__{elem_id}__dep",
                "source": dep,
                "target": elem_id,
                "type": "dependency",
                "data": {"label": "依赖"},
            })
        # Add weighted edges for composite metrics
        for comp in element.get("components", []) or []:
            comp_metric = comp.get("metric", "")
            if comp_metric:
                edges.append({
                    "id": f"{comp_metric}__{elem_id}__component",
                    "source": comp_metric,
                    "target": elem_id,
                    "type": "component",
                    "data": {
                        "label": f"权重{comp.get('weight', 1.0)}",
                        "weight": comp.get("weight", 1.0),
                    },
                })

    # L4: Rules
    for rule in space.layers.L4_business_logic.rule_definitions:
        rule_id = rule.get("id", "unknown")
        nodes.append({
            "id": rule_id,
            "type": "rule",
            "data": {
                "label": rule.get("name", rule_id),
                "category": "rule_definition",
                "layer": "L4",
                "rule_type": rule.get("rule_type", "constraint"),
                "priority": rule.get("priority", 100),
                "enabled": rule.get("enabled", True),
                "applies_to": rule.get("applies_to") or rule.get("target_objects") or [],
                "inputs": [
                    e.get("name") or e.get("id", "") for e in _rule_inputs(rule)
                ],
                "outputs": [
                    e.get("name") or e.get("id", "") for e in _rule_outputs(rule)
                ],
                "logic_count": len(rule.get("logic_ids", [])),
                "description": rule.get("description", ""),
            }
        })
        # Add edges from L3 elements to L4 rules (input relationship)
        for in_elem in _rule_inputs(rule):
            elem_name = in_elem.get("name") or in_elem.get("id", "")
            if elem_name:
                edges.append({
                    "id": f"{elem_name}__{rule_id}__input",
                    "source": elem_name,
                    "target": rule_id,
                    "type": "rule_input",
                    "data": {"label": "输入"},
                })

    # Parse layer filter
    if layer_filter:
        layers = [lyr.strip() for lyr in layer_filter.split(",")]
        layer_type_map = {"L1": "entity", "L2": "category", "L3": "metric", "L4": "rule"}
        allowed_types = {layer_type_map[lyr] for lyr in layers if lyr in layer_type_map}
        node_ids_in_filter = {n["id"] for n in nodes if n["type"] in allowed_types}
        nodes = [n for n in nodes if n["id"] in node_ids_in_filter]
        edges = [
            e for e in edges
            if e["source"] in node_ids_in_filter and e["target"] in node_ids_in_filter
        ]

    return success_response(data={
        "view_id": view_id,
        "graph_type": graph_type,
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "entity_count": len([n for n in nodes if n["type"] == "entity"]),
            "category_count": len([n for n in nodes if n["type"] == "category"]),
            "metric_count": len([n for n in nodes if n["type"] == "metric"]),
            "rule_count": len([n for n in nodes if n["type"] == "rule"]),
            "edge_count": len(edges),
        }
    })


# ============================================================================
# Rule Dependency Graph (Consumption)
# ============================================================================

@router.get("/views/{view_id}/rules/dependency-graph", response_model=dict)
async def get_rule_dependency_graph(view_id: str):
    """Get rule dependency graph for a consumption view.

    Returns DAG of rules with dependency edges (input→output chains)
    and mutual exclusion information.
    """
    storage = _get_storage()
    space = await storage.load(view_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found")

    rules = space.layers.L4_business_logic.rule_definitions
    rule_logics = space.layers.L4_business_logic.rule_logics

    # Build nodes
    nodes = []
    for rule in rules:
        logic_ids = rule.get("logic_ids", [])
        logics = [rl for rl in rule_logics if rl.get("id") in logic_ids]

        nodes.append({
            "id": rule["id"],
            "label": rule.get("name") or rule["id"],
            "rule_type": rule.get("rule_type", "constraint"),
            "priority": rule.get("priority", 100),
            "enabled": rule.get("enabled", True),
            "applies_to": rule.get("applies_to") or rule.get("target_objects") or [],
            "applicable_categorizations": rule.get("applicable_categorizations", []),
            "inputs": _rule_inputs(rule),
            "outputs": _rule_outputs(rule),
            "logic_count": len(logics),
            "logics": [
                {
                    "id": lg.get("id"),
                    "name": lg.get("name"),
                    "applicable_conditions": lg.get("applicable_conditions", []),
                    "when": lg.get("when"),
                    "then_action": lg.get("then_action"),
                }
                for lg in logics
            ],
        })

    # Build dependency edges
    edges = []
    output_map: dict[str, list[str]] = {}
    for rule in rules:
        for out_elem in _rule_outputs(rule):
            elem_name = out_elem.get("name") or out_elem.get("id", "")
            if elem_name:
                output_map.setdefault(elem_name, []).append(rule["id"])

    for rule in rules:
        for in_elem in _rule_inputs(rule):
            elem_name = in_elem.get("name") or in_elem.get("id", "")
            producers = output_map.get(elem_name, [])
            for producer_id in producers:
                if producer_id != rule["id"]:
                    edges.append({
                        "id": f"{producer_id}__{rule['id']}__{elem_name}",
                        "source": producer_id,
                        "target": rule["id"],
                        "element": elem_name,
                        "type": "data_dependency",
                        "label": elem_name,
                    })

    # Detect mutual exclusions
    exclusion_pairs = []
    for i, rule_a in enumerate(rules):
        for rule_b in rules[i + 1:]:
            cats_a = set(rule_a.get("applicable_categorizations", []))
            cats_b = set(rule_b.get("applicable_categorizations", []))
            if cats_a and cats_b and not (cats_a & cats_b):
                exclusion_pairs.append({
                    "rule_a": rule_a["id"],
                    "rule_b": rule_b["id"],
                    "reason": f"适用分类不重叠: {list(cats_a)} vs {list(cats_b)}",
                    "type": "categorization_exclusive",
                })
            # Output conflict
            outputs_a = {(e.get("name") or e.get("id", "")) for e in _rule_outputs(rule_a)}
            outputs_b = {(e.get("name") or e.get("id", "")) for e in _rule_outputs(rule_b)}
            shared = outputs_a & outputs_b - {""}
            if shared:
                exclusion_pairs.append({
                    "rule_a": rule_a["id"],
                    "rule_b": rule_b["id"],
                    "reason": f"输出元素冲突: {list(shared)}",
                    "type": "output_conflict",
                })

    # Execution order
    execution_order = _topological_sort_rules(nodes, edges)

    return success_response(data={
        "view_id": view_id,
        "nodes": nodes,
        "edges": edges,
        "mutual_exclusions": exclusion_pairs,
        "execution_order": execution_order,
        "stats": {
            "total_rules": len(nodes),
            "dependency_edges": len(edges),
            "exclusion_pairs": len(exclusion_pairs),
        },
    })


def _topological_sort_rules(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Topological sort helper."""
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    adj: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        if src in in_degree and tgt in in_degree:
            adj[src].append(tgt)
            in_degree[tgt] += 1

    priority_map = {n["id"]: n.get("priority", 100) for n in nodes}
    queue = deque(sorted(
        [nid for nid, deg in in_degree.items() if deg == 0],
        key=lambda nid: -priority_map.get(nid, 100)
    ))

    order = []
    while queue:
        nid = queue.popleft()
        order.append(nid)
        for neighbor in sorted(adj[nid], key=lambda x: -priority_map.get(x, 100)):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    remaining = [n["id"] for n in nodes if n["id"] not in set(order)]
    return order + remaining


# ============================================================================
# Rule Retrieval by Entity Instance
# ============================================================================

@router.get("/views/{view_id}/rules/for-entity/{entity_id}", response_model=dict)
async def get_rules_for_entity(
    view_id: str,
    entity_id: str,
    dimension: str | None = Query(default=None),
):
    """Retrieve and locate applicable rules for a specific entity instance.

    Filters rules based on:
    1. target_objects matching entity's concept
    2. applicable_categorizations matching entity's classification tags
    3. Optional dimension filter
    """
    storage = _get_storage()
    space = await storage.load(view_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found")

    # Find the entity
    entity = next((e for e in space.instances.entities if e.get("entity_id") == entity_id), None)
    if not entity:
        return error_response(code="NOT_FOUND", message=f"Entity {entity_id} not found")

    entity_concept = entity.get("_fact_object") or entity.get("_concept", "")
    rules = space.layers.L4_business_logic.rule_definitions
    rule_logics = space.layers.L4_business_logic.rule_logics

    applicable_rules = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue

        # Check target_objects
        target_objects = rule.get("target_objects", [])
        if target_objects and entity_concept and entity_concept not in target_objects:
            continue

        # Find applicable logics
        logic_ids = rule.get("logic_ids", [])
        matching_logics = []
        for logic_id in logic_ids:
            logic = next((rl for rl in rule_logics if rl.get("id") == logic_id), None)
            if logic:
                conditions = logic.get("applicable_conditions", [])
                match = True
                for cond in conditions:
                    classification = cond.get("classification", "")
                    operator = cond.get("operator", "eq")
                    value = cond.get("value")
                    entity_value = entity.get(classification, "")
                    if operator == "eq" and entity_value != value:
                        match = False
                        break
                    elif operator == "in" and entity_value not in (value if isinstance(value, list) else [value]):
                        match = False
                        break
                if match:
                    matching_logics.append({
                        "id": logic.get("id"),
                        "name": logic.get("name"),
                        "when": logic.get("when"),
                        "then_action": logic.get("then_action"),
                    })

        applicable_rules.append({
            "id": rule["id"],
            "name": rule.get("name") or rule["id"],
            "rule_type": rule.get("rule_type", "constraint"),
            "priority": rule.get("priority", 100),
            "applies_to": target_objects,
            "inputs": _rule_inputs(rule),
            "outputs": _rule_outputs(rule),
            "matching_logics": matching_logics,
            "applicable_logics_count": len(matching_logics),
        })

    # Sort by priority
    applicable_rules.sort(key=lambda r: -r["priority"])

    # Build execution order
    output_map: dict[str, list[str]] = {}
    for rule in applicable_rules:
        for out_elem in _rule_outputs(rule):
            elem_name = out_elem.get("name") or out_elem.get("id", "")
            if elem_name:
                output_map.setdefault(elem_name, []).append(rule["id"])

    dependency_edges = []
    for rule in applicable_rules:
        for in_elem in _rule_inputs(rule):
            elem_name = in_elem.get("name") or in_elem.get("id", "")
            for producer_id in output_map.get(elem_name, []):
                if producer_id != rule["id"]:
                    dependency_edges.append({
                        "from": producer_id,
                        "to": rule["id"],
                        "via_element": elem_name,
                    })

    return success_response(data={
        "entity_id": entity_id,
        "entity_concept": entity_concept,
        "view_id": view_id,
        "applicable_rules": applicable_rules,
        "dependency_edges": dependency_edges,
        "total": len(applicable_rules),
    })


# ============================================================================
# Metric Snapshot
# ============================================================================

@router.get("/views/{view_id}/metrics/{entity_id}/snapshot", response_model=dict)
async def get_metric_snapshot(
    view_id: str,
    entity_id: str,
    dimension: str = Query(default="credit_assessment"),
):
    """Get metric snapshot for an entity in a consumption view.

    Returns the computed metrics, outputs, and decision for the entity
    without full execution trace.
    """
    storage = _get_storage()
    space = await storage.load(view_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found")

    entity = next(
        (e for e in space.instances.entities if e.get("entity_id") == entity_id),
        None,
    )
    if not entity:
        return error_response(code="NOT_FOUND", message=f"Entity {entity_id} not found")

    # Run analysis without trace for performance
    result = await _run_full_analysis(space, entity, dimension, {}, include_trace=False)

    # Map to MetricSnapshot structure
    return success_response(data={
        "entity_id": entity_id,
        "dimension": dimension,
        "metrics": result.get("computed_metrics", {}),
        "outputs": result.get("final_outputs", {}),
        "decision": result.get("decision", None),
        "decision_reasoning": None,  # Reasoning not computed in MVP
    })


# ============================================================================
# Execution
# ============================================================================

@router.post("/views/{view_id}/execute/analyze", response_model=dict)
async def execute_analyze(view_id: str, request: ExecuteAnalyzeRequest):
    """Execute rules on an entity and return detailed analysis results."""
    storage = _get_storage()
    space = await storage.load(view_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found")

    entity = next(
        (e for e in space.instances.entities if e.get("entity_id") == request.entity_id),
        None,
    )
    if not entity:
        return error_response(code="NOT_FOUND", message=f"Entity {request.entity_id} not found")

    result = await _run_full_analysis(space, entity, request.dimension, {}, request.include_trace)

    return success_response(data=result)


@router.post("/views/{view_id}/execute/simulate", response_model=dict)
async def execute_simulate(view_id: str, request: ExecuteSimulateRequest):
    """Execute what-if simulation with variable overrides and full diff analysis."""
    storage = _get_storage()
    space = await storage.load(view_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found")

    entity = next(
        (e for e in space.instances.entities if e.get("entity_id") == request.entity_id),
        None,
    )
    if not entity:
        return error_response(code="NOT_FOUND", message=f"Entity {request.entity_id} not found")

    # Run baseline
    baseline = await _run_full_analysis(space, entity, request.dimension, {}, request.include_trace)
    # Run simulated
    simulated = await _run_full_analysis(
        space, entity, request.dimension, request.overrides or {}, request.include_trace
    )

    # Build diffs
    baseline_outputs = baseline.get("final_outputs", {})
    simulated_outputs = simulated.get("final_outputs", {})
    all_keys = set(baseline_outputs.keys()) | set(simulated_outputs.keys())

    diffs = []
    for key in sorted(all_keys):
        bv = baseline_outputs.get(key)
        sv = simulated_outputs.get(key)
        if bv != sv:
            # Determine change direction
            change_type = "changed"
            if key not in baseline_outputs:
                change_type = "new"
            elif key not in simulated_outputs:
                change_type = "removed"
            elif isinstance(bv, (int, float)) and isinstance(sv, (int, float)):
                change_type = "increased" if sv > bv else "decreased"

            diffs.append({
                "field": key,
                "baseline_value": bv,
                "simulated_value": sv,
                "change_type": change_type,
                "impact": f"{bv} → {sv}",
            })

    # Build impact chains: trace which overridden inputs affected which outputs
    impact_chains = _compute_impact_chains(
        space, entity, request.overrides or {}, baseline_outputs, simulated_outputs
    )

    return success_response(data={
        "entity_id": request.entity_id,
        "dimension": request.dimension,
        "simulation_type": "what_if",
        "overrides": request.overrides or {},
        "baseline_outputs": baseline_outputs,
        "simulated_outputs": simulated_outputs,
        "final_outputs": simulated_outputs,
        "steps": simulated.get("steps", []),
        "execution_path": simulated.get("execution_path", []),
        "skipped_rules": simulated.get("skipped_rules", []),
        "comparison": {
            "diffs": diffs,
            "impact_chains": impact_chains,
            "changed_fields": len(diffs),
        },
    })


# ============================================================================
# DAG Execution Support
# ============================================================================

def _build_rule_dependency_graph(
    rules: list[dict],
) -> tuple[dict[str, list[str]], dict[str, int], list[dict]]:
    """Build rule dependency graph based on inputs/outputs element matching.

    Rule A depends on Rule B if A's inputs overlap with B's outputs.

    Returns:
        Tuple of (adjacency_list, in_degree_map, edges)
    """
    # Build output_map: element_name -> [rule_ids that produce it]
    output_map: dict[str, list[str]] = defaultdict(list)
    for rule in rules:
        for out_elem in _rule_outputs(rule):
            elem_name = out_elem.get("name") or out_elem.get("id", "")
            if elem_name:
                output_map[elem_name].append(rule["id"])

    # Build dependency edges and adjacency list
    adj: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {r["id"]: 0 for r in rules}
    edges = []

    for rule in rules:
        rule_id = rule["id"]
        for in_elem in _rule_inputs(rule):
            elem_name = in_elem.get("name") or in_elem.get("id", "")
            producers = output_map.get(elem_name, [])
            for producer_id in producers:
                if producer_id != rule_id and producer_id in in_degree:
                    adj[producer_id].append(rule_id)
                    in_degree[rule_id] += 1
                    edges.append({
                        "source": producer_id,
                        "target": rule_id,
                        "via_element": elem_name,
                    })

    return dict(adj), in_degree, edges


def _compute_rule_levels(
    rules: list[dict],
    adj: dict[str, list[str]],
    in_degree: dict[str, int],
) -> dict[str, int]:
    """Compute execution level for each rule based on dependency graph.

    Level 0 = rules with no dependencies (in_degree = 0)
    Level N = rules that depend only on rules in levels 0..N-1

    Returns:
        Dict mapping rule_id -> level number

    Raises:
        ValueError if circular dependency is detected.
    """
    rule_levels: dict[str, int] = {}
    remaining_in_degree = dict(in_degree)
    level_queue = deque()

    # Find all rules with in_degree = 0 (no dependencies)
    for rule_id, deg in remaining_in_degree.items():
        if deg == 0:
            level_queue.append(rule_id)

    while level_queue:
        current_level_size = len(level_queue)
        for _ in range(current_level_size):
            rule_id = level_queue.popleft()
            # Assign level if not already assigned
            if rule_id not in rule_levels:
                # Level is determined by max level of all prerequisites + 1
                rule_levels[rule_id] = len([r for r in rules if rule_id in adj.get(r["id"], [])])

            # Process all rules that depend on this one
            for neighbor in adj.get(rule_id, []):
                remaining_in_degree[neighbor] -= 1
                if remaining_in_degree[neighbor] == 0:
                    level_queue.append(neighbor)

    # Check for cycles - rules not in rule_levels have circular dependencies
    unassigned = [r["id"] for r in rules if r["id"] not in rule_levels]
    if unassigned:
        raise ValueError(f"Circular dependency detected involving rules: {unassigned}")

    return rule_levels


def _detect_circular_dependencies(
    rules: list[dict],
    adj: dict[str, list[str]],
    in_degree: dict[str, int],
) -> list[list[str]]:
    """Detect circular dependencies in rule graph using DFS.

    Returns:
        List of cycles, where each cycle is a list of rule IDs.
    """
    cycles = []
    visited = set()
    rec_stack = set()
    path = []

    def dfs(node: str) -> bool:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in rec_stack:
                # Found a cycle
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


def _precompute_l3_elements(
    space: SemanticSpace,
    entity_data: dict,
) -> dict[str, Any]:
    """Precompute L3 Analytical Elements from entity data.

    Handles:
    - atomic: extracts value from fact attribute via source.path
    - derived: resolves dependencies (simplified for MVP)
    - composite/graph: returns None for MVP
    """
    computed = {}

    for elem in space.layers.L3_analytical_elements:
        elem_id = elem.get("id", "")
        elem_type = _metric_type(elem)
        source = elem.get("source", {})
        dependencies = elem.get("dependencies", [])

        if elem_id in computed:
            continue  # Already computed

        if elem_type == "atomic":
            # Extract from fact attribute
            attr_path = source.get("attribute", "")
            if attr_path:
                value = _get_nested_path(entity_data, attr_path)
                computed[elem_id] = value
            else:
                computed[elem_id] = None

        elif elem_type == "derived":
            # Simplified: use first dependency's value
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

        elif elem_type == "composite":
            # Composite is computed from components, skip for MVP
            computed[elem_id] = None

        elif elem_type == "graph":
            # Graph metrics require traversal, skip for MVP
            computed[elem_id] = None

        else:
            computed[elem_id] = None

    return computed


def _get_nested_path(data: dict, path: str) -> Any:
    """Get nested value from dict using dot-separated path.

    Example: _get_nested_path({"a": {"b": "c"}}, "a.b") -> "c"
    """
    value = data
    for key in path.split("."):
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


# ============================================================================
# Core Execution Logic
# ============================================================================

async def _run_full_analysis(
    space: SemanticSpace,
    entity: dict,
    dimension: str,
    overrides: dict[str, Any],
    include_trace: bool,
) -> dict[str, Any]:
    """Execute all applicable rules with DAG-driven ordering and full tracing.

    Execution order is determined by:
    1. DAG levels (rules with no dependencies execute first, then rules that
       depend on them, etc.)
    2. Within the same level: priority order
    3. Circular dependencies are detected and result in an error

    This ensures that when rule A's output is rule B's input, A always executes
    before B, regardless of priority settings.
    """
    expression_engine = SimulationService.create_expression_engine()

    entity_data = dict(entity)
    entity_data["_fact_object"] = entity.get("_fact_object") or entity.get("_concept", "Unknown")
    entity_data.update(overrides)

    context = SimulationService.create_execution_context(
        entity_id=entity.get("entity_id", ""),
        dimension=dimension,
        entity_data=entity_data,
        computed_metrics={},
    )

    steps = []
    final_outputs: dict[str, Any] = {}

    # Step 1: Precompute L3 Analytical Elements
    l3_computed = _precompute_l3_elements(space, entity_data)
    entity_data.update(l3_computed)
    context.computed_metrics.update(l3_computed)

    # Step 2: Build dependency graph and compute levels
    all_rules = space.layers.L4_business_logic.rule_definitions
    enabled_rules = [r for r in all_rules if r.get("enabled", True)]
    skipped_disabled = [r for r in all_rules if not r.get("enabled", True)]

    # Record disabled rules as skipped
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
        # No enabled rules, return early
        return {
            "entity_id": entity.get("entity_id", ""),
            "dimension": dimension,
            "steps": steps,
            "execution_path": [],
            "skipped_rules": [r["id"] for r in skipped_disabled],
            "final_outputs": final_outputs,
            "decision": "REVIEW",
            "computed_metrics": context.computed_metrics,
        }

    # Build dependency graph
    try:
        adj, in_degree, dep_edges = _build_rule_dependency_graph(enabled_rules)
        rule_levels = _compute_rule_levels(enabled_rules, adj, in_degree)
    except ValueError as e:
        # Circular dependency detected - fall back to priority-only ordering
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"DAG execution failed, falling back to priority mode: {e}")

        # Fall back to priority-based execution
        sorted_rules = sorted(
            enabled_rules,
            key=lambda r: r.get("priority", 100),
            reverse=True,
        )

        for rule in sorted_rules:
            step = await _execute_single_rule(
                rule, space, entity_data, context, expression_engine,
                len(steps) + 1, include_trace
            )
            steps.append(step)
            if step["status"] == "passed":
                for k, v in step.get("outputs", []):
                    final_outputs[k] = v

        return _build_result(entity, dimension, steps, final_outputs, context)

    # Step 3: Execute rules by DAG level
    max_level = max(rule_levels.values()) if rule_levels else 0
    rule_map = {r["id"]: r for r in enabled_rules}

    # Group rules by level
    level_groups: dict[int, list[dict]] = defaultdict(list)
    for rule_id, level in rule_levels.items():
        level_groups[level].append(rule_map[rule_id])

    # Execute level by level
    for level in range(max_level + 1):
        level_rules = level_groups.get(level, [])

        # Within the same level, sort by priority (higher first)
        level_rules.sort(key=lambda r: r.get("priority", 100), reverse=True)

        # Check target objects filter first
        entity_type = entity_data.get("_fact_object") or entity_data.get("_concept", "")

        for rule in level_rules:
            # Additional filter: check if entity type matches target_objects
            target_objects = rule.get("target_objects", [])
            if target_objects and entity_type and entity_type not in target_objects:
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

            step = await _execute_single_rule(
                rule, space, entity_data, context, expression_engine,
                len(steps) + 1, include_trace
            )
            step["level"] = level  # Add level info for traceability
            steps.append(step)

            if step["status"] == "passed":
                for item in step.get("outputs", []):
                    final_outputs[item["name"]] = item["value"]

    return _build_result(entity, dimension, steps, final_outputs, context)


async def _execute_single_rule(
    rule: dict,
    space: SemanticSpace,
    entity_data: dict,
    context: Any,
    expression_engine: Any,
    step_num: int,
    include_trace: bool,
) -> dict:
    """Execute a single rule and return the step result.

    This is the core rule execution logic extracted for reuse in DAG mode.
    """
    rule_id = rule["id"]
    rule_name = rule.get("name", rule_id)
    rule_type = rule.get("rule_type", "constraint")

    # Find matching rule logic
    logic_ids = rule.get("logic_ids", [])
    matching_logic = _find_matching_logic(
        logic_ids,
        space.layers.L4_business_logic.rule_logics,
        entity_data,
    )

    # Gather current inputs
    current_inputs = _gather_inputs(rule, entity_data, context.computed_metrics)

    # Evaluate when condition
    when_expr = _extract_when_expr(matching_logic, rule)
    condition_result = True
    condition_explanation = "无条件，默认执行"
    condition_sub_conditions: list[dict] = []

    if when_expr:
        try:
            eval_ctx = {**entity_data, **context.computed_metrics}
            condition_result = bool(expression_engine.evaluate(when_expr, eval_ctx))
            condition_explanation = f"条件: {when_expr} → {'满足' if condition_result else '不满足'}"
        except Exception as exc:
            condition_result = False
            condition_explanation = f"条件评估出错: {exc}"

    # Evaluate allOf/anyOf conditions for explainability
    if matching_logic and matching_logic.get("when"):
        when_obj = matching_logic["when"]
        condition_sub_conditions = _explain_conditions(when_obj, entity_data, context.computed_metrics, expression_engine)
    elif rule.get("when"):
        condition_sub_conditions = _explain_conditions(rule["when"], entity_data, context.computed_metrics, expression_engine)

    context_before = dict(context.computed_metrics)
    step_outputs: dict[str, Any] = {}

    if condition_result:
        then_action = None
        if matching_logic:
            then_action = matching_logic.get("then_action")
        if not then_action:
            then_action = rule.get("then_action")

        if then_action:
            step_outputs = _execute_action(
                then_action, entity_data, context.computed_metrics, expression_engine
            )
            context.computed_metrics.update(step_outputs)

        status = "passed"
        action_type = (then_action or {}).get("action_type", "")
        explanation = _build_explanation(action_type, step_outputs, condition_explanation)
    else:
        else_action = (matching_logic or {}).get("else_action") if matching_logic else rule.get("else_action")
        if else_action:
            else_outputs = _execute_action(
                else_action, entity_data, context.computed_metrics, expression_engine
            )
            context.computed_metrics.update(else_outputs)
            step_outputs = else_outputs
            explanation = f"条件不满足，执行else分支: {_build_explanation(else_action.get('action_type',''), else_outputs, '')}"
        else:
            explanation = "条件不满足，规则跳过"
        status = "skipped"

    step = {
        "step": step_num,
        "rule_id": rule_id,
        "rule_name": rule_name,
        "rule_type": rule_type,
        "condition_expression": when_expr or "",
        "condition_result": condition_result,
        "condition_sub_conditions": condition_sub_conditions,
        "status": status,
        "explanation": explanation,
        "inputs": current_inputs,
        "outputs": [{"name": k, "value": v} for k, v in step_outputs.items()],
        "matching_logic_id": matching_logic.get("id") if matching_logic else None,
    }

    if include_trace:
        step["context_before"] = context_before
        step["context_after"] = dict(context.computed_metrics)

    return step


def _build_result(
    entity: dict,
    dimension: str,
    steps: list,
    final_outputs: dict,
    context: Any,
) -> dict:
    """Build the final result dict from execution steps."""
    # Determine final decision
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
        "execution_path": [s["rule_id"] for s in steps if s["status"] == "passed"],
        "skipped_rules": [s["rule_id"] for s in steps if s["status"] == "skipped"],
        "final_outputs": final_outputs,
        "decision": decision,
        "computed_metrics": context.computed_metrics,
    }


def _find_matching_logic(
    logic_ids: list[str],
    rule_logics: list[dict],
    entity_data: dict,
) -> dict | None:
    """Find the first matching rule logic."""
    for logic_id in logic_ids:
        logic = next((rl for rl in rule_logics if rl.get("id") == logic_id), None)
        if not logic:
            continue
        conditions = logic.get("applicable_conditions", [])
        match = True
        for cond in conditions:
            classification = cond.get("classification", "")
            operator = cond.get("operator", "eq")
            value = cond.get("value")
            entity_value = entity_data.get(classification, "")
            if operator == "eq" and entity_value != value:
                match = False
                break
            elif operator == "in":
                values_list = value if isinstance(value, list) else [value]
                if entity_value not in values_list:
                    match = False
                    break
        if match:
            return logic
    return None


def _extract_when_expr(logic: dict | None, rule: dict) -> str | None:
    """Extract the when expression from logic or rule."""
    if logic and logic.get("when"):
        when = logic["when"]
        if isinstance(when, dict):
            return when.get("expression")
        return str(when)
    if rule.get("when"):
        when = rule["when"]
        if isinstance(when, dict):
            return when.get("expression")
    return None


def _explain_conditions(
    when_obj: dict,
    entity_data: dict,
    computed: dict,
    expression_engine: Any,
) -> list[dict]:
    """Explain condition evaluation sub-conditions."""
    sub_conditions = []
    eval_ctx = {**entity_data, **computed}

    if isinstance(when_obj, dict):
        if "expression" in when_obj and when_obj["expression"]:
            try:
                result = bool(expression_engine.evaluate(when_obj["expression"], eval_ctx))
                sub_conditions.append({
                    "type": "expression",
                    "expr": when_obj["expression"],
                    "result": result,
                })
            except Exception as exc:
                sub_conditions.append({
                    "type": "expression",
                    "expr": when_obj["expression"],
                    "result": False,
                    "error": str(exc),
                })

        for item in when_obj.get("allOf", []) or []:
            expr = item.get("expression", "")
            if expr:
                try:
                    result = bool(expression_engine.evaluate(expr, eval_ctx))
                    sub_conditions.append({"type": "allOf", "expr": expr, "result": result})
                except Exception as exc:
                    sub_conditions.append({"type": "allOf", "expr": expr, "result": False, "error": str(exc)})

        for item in when_obj.get("anyOf", []) or []:
            expr = item.get("expression", "")
            if expr:
                try:
                    result = bool(expression_engine.evaluate(expr, eval_ctx))
                    sub_conditions.append({"type": "anyOf", "expr": expr, "result": result})
                except Exception as exc:
                    sub_conditions.append({"type": "anyOf", "expr": expr, "result": False, "error": str(exc)})

    return sub_conditions


def _gather_inputs(rule: dict, entity_data: dict, computed: dict) -> list[dict]:
    """Gather current input element values for a rule."""
    inputs = []
    for in_elem in _rule_inputs(rule):
        name = in_elem.get("name") or in_elem.get("id", "")
        if name:
            value = computed.get(name, entity_data.get(name))
            inputs.append({"name": name, "value": value, "type": in_elem.get("type", "")})
    return inputs


def _execute_action(
    action: dict,
    entity_data: dict,
    computed: dict,
    expression_engine: Any,
) -> dict[str, Any]:
    """Execute an action and return produced outputs."""
    outputs: dict[str, Any] = {}
    action_type = action.get("action_type", "")
    eval_ctx = {**entity_data, **computed}

    if action_type == "set_flag":
        for key, value in (action.get("output") or {}).items():
            outputs[key] = value

    elif action_type == "compute":
        for key, formula in (action.get("output") or {}).items():
            if isinstance(formula, str):
                try:
                    outputs[key] = expression_engine.evaluate(formula, eval_ctx)
                except Exception:
                    pass
            else:
                outputs[key] = formula

    elif action_type == "approve":
        outputs["decision"] = "APPROVED"
        for key, value in (action.get("output") or {}).items():
            outputs[key] = value

    elif action_type == "reject":
        outputs["decision"] = "REJECTED"
        outputs["eligible"] = False
        for key, value in (action.get("output") or {}).items():
            outputs[key] = value

    elif action_type == "alert":
        alert_msg = action.get("output", {}).get("message", "alert triggered")
        existing_alerts = computed.get("alerts", [])
        outputs["alerts"] = existing_alerts + [alert_msg]
        for key, value in (action.get("output") or {}).items():
            if key != "message":
                outputs[key] = value

    elif action_type == "recommend":
        for key, value in (action.get("output") or {}).items():
            if isinstance(value, str) and ("${" in value or "{" in value):
                try:
                    outputs[key] = expression_engine.evaluate(value, eval_ctx)
                except Exception:
                    outputs[key] = value
            else:
                outputs[key] = value

    return outputs


def _build_explanation(action_type: str, outputs: dict, condition_explanation: str) -> str:
    """Build human-readable explanation of rule execution."""
    if not outputs:
        return condition_explanation or "无操作"

    parts = []
    for key, value in outputs.items():
        if key == "decision":
            parts.append(f"决策 → {value}")
        elif key == "eligible":
            parts.append(f"准入 → {'是' if value else '否'}")
        elif key == "alerts":
            if isinstance(value, list):
                parts.append(f"告警 → {'; '.join(str(a) for a in value[-3:])}")
        else:
            parts.append(f"{key} = {value}")

    return "；".join(parts) if parts else condition_explanation


def _compute_impact_chains(
    space: SemanticSpace,
    entity: dict,
    overrides: dict[str, Any],
    baseline_outputs: dict,
    simulated_outputs: dict,
) -> list[dict]:
    """Compute impact chains showing how overrides affected outputs."""
    impact_chains = []

    if not overrides:
        return impact_chains

    # Build a mapping of element -> rules that use it as input
    elem_to_rules: dict[str, list[str]] = defaultdict(list)
    rule_outputs: dict[str, list[str]] = {}

    for rule in space.layers.L4_business_logic.rule_definitions:
        rule_id = rule["id"]
        out_names = [e.get("name") or e.get("id", "") for e in _rule_outputs(rule)]
        rule_outputs[rule_id] = [n for n in out_names if n]
        for in_elem in _rule_inputs(rule):
            name = in_elem.get("name") or in_elem.get("id", "")
            if name:
                elem_to_rules[name].append(rule_id)

    # For each override, trace its downstream impact
    for override_field in overrides:
        affected_outputs = []
        visited_rules: set[str] = set()
        queue = deque([override_field])
        chain_path = [override_field]

        while queue:
            current = queue.popleft()
            for rule_id in elem_to_rules.get(current, []):
                if rule_id not in visited_rules:
                    visited_rules.add(rule_id)
                    for out in rule_outputs.get(rule_id, []):
                        if out in baseline_outputs or out in simulated_outputs:
                            bv = baseline_outputs.get(out)
                            sv = simulated_outputs.get(out)
                            if bv != sv:
                                affected_outputs.append({
                                    "field": out,
                                    "baseline": bv,
                                    "simulated": sv,
                                    "via_rule": rule_id,
                                })
                        queue.append(out)
                        chain_path.append(out)

        if affected_outputs:
            impact_chains.append({
                "source_field": override_field,
                "override_value": overrides[override_field],
                "original_value": entity.get(override_field),
                "affected_fields": [a["field"] for a in affected_outputs],
                "affected_details": affected_outputs,
                "description": f"覆盖 {override_field} → 影响 {len(affected_outputs)} 个输出字段",
            })

    return impact_chains
