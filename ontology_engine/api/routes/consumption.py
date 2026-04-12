# ontology_engine/api/routes/consumption.py
"""Consumption API routes for semantic spaces.

Prefix: /v1/consumption/{viewId}/
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ontology_engine.api.dto.responses import error_response, success_response
from ontology_engine.core.semantic_space import (
    SemanticSpace,
    SpaceMetadata,
    SpaceType,
    SemanticSpaceStorage,
    SemanticSpaceStorageError,
)
from ontology_engine.engine.expression.engine import ExpressionEngine
from ontology_engine.engine.rule.models import ExecutionContext

router = APIRouter(prefix="/v1/consumption", tags=["Consumption"])


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

    # Filter only consumption views
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
        "created_at": space.metadata.created_at.isoformat(),
    })


# ============================================================================
# Visualization
# ============================================================================

@router.get("/views/{view_id}/visualize/schema-graph", response_model=dict)
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

    # Build graph nodes and edges from semantic space layers
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
                "properties": entity.get("properties", []),
            }
        })
        for rel in entity.get("relations", []):
            rel_id = f"{entity_id}__{rel.get('target')}__{rel.get('name')}"
            edges.append({
                "id": rel_id,
                "source": entity_id,
                "target": rel.get("target", ""),
                "type": "relation",
                "data": {"label": rel.get("name", "")},
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
                "values": cat.get("values", []),
            }
        })

    # L3: Analytical Elements
    for element in space.layers.L3_analytical_elements:
        elem_id = element.get("id", element.get("name", "unknown"))
        nodes.append({
            "id": elem_id,
            "type": "metric",
            "data": {
                "label": element.get("name", elem_id),
                "category": "element",
                "element_type": element.get("element_type", "metric"),
            }
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
                "rule_type": rule.get("rule_type", "constraint"),
            }
        })

    # Parse layer filter
    if layer_filter:
        layers = [l.strip() for l in layer_filter.split(",")]
        layer_type_map = {"L1": "entity", "L2": "category", "L3": "metric", "L4": "rule"}
        allowed_types = {layer_type_map[l] for l in layers if l in layer_type_map}
        nodes = [n for n in nodes if n["type"] in allowed_types]

    return success_response(data={
        "view_id": view_id,
        "graph_type": graph_type,
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "entity_count": len([n for n in nodes if n["type"] == "entity"]),
            "metric_count": len([n for n in nodes if n["type"] == "metric"]),
            "rule_count": len([n for n in nodes if n["type"] == "rule"]),
        }
    })


# ============================================================================
# Execution
# ============================================================================

@router.post("/views/{view_id}/execute/analyze", response_model=dict)
async def execute_analyze(view_id: str, request: ExecuteAnalyzeRequest):
    """Execute rules on an entity and return analysis results."""
    storage = _get_storage()
    space = await storage.load(view_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found")

    # Find the entity
    entity = None
    for e in space.instances.entities:
        if e.get("entity_id") == request.entity_id:
            entity = e
            break

    if not entity:
        return error_response(code="NOT_FOUND", message=f"Entity {request.entity_id} not found")

    # Build execution context
    entity_data = dict(entity)
    entity_data["_concept"] = entity.get("_concept", "Unknown")

    context = ExecutionContext(
        entity_id=request.entity_id,
        dimension=request.dimension,
        entity_data=entity_data,
        computed_metrics={},
    )

    expression_engine = ExpressionEngine()
    steps = []
    final_outputs = {}

    # Execute rule definitions in priority order
    sorted_rules = sorted(
        space.layers.L4_business_logic.rule_definitions,
        key=lambda r: r.get("priority", 100),
        reverse=True
    )

    for rule in sorted_rules:
        rule_id = rule["id"]
        rule_name = rule.get("name", rule_id)
        rule_type = rule.get("rule_type", "constraint")

        # Check if rule is enabled
        if not rule.get("enabled", True):
            steps.append({
                "step": len(steps) + 1,
                "rule_id": rule_id,
                "rule_name": rule_name,
                "rule_type": rule_type,
                "status": "skipped",
                "explanation": "规则已禁用",
            })
            continue

        # Check applicable scope
        target_objects = rule.get("target_objects", [])
        if target_objects:
            entity_type = entity.get("_concept", "")
            if entity_type and entity_type not in target_objects:
                steps.append({
                    "step": len(steps) + 1,
                    "rule_id": rule_id,
                    "rule_name": rule_name,
                    "rule_type": rule_type,
                    "status": "skipped",
                    "explanation": f"实体类型 {entity_type} 不在适用范围内",
                })
                continue

        # Find matching rule logic
        logic_ids = rule.get("logic_ids", [])
        matching_logic = None

        for logic_id in logic_ids:
            for logic in space.layers.L4_business_logic.rule_logics:
                if logic.get("id") == logic_id:
                    # Check applicable_conditions
                    conditions = logic.get("applicable_conditions", [])
                    match = True
                    for cond in conditions:
                        classification = cond.get("classification", "")
                        operator = cond.get("operator", "eq")
                        value = cond.get("value")
                        entity_value = entity.get(classification, "")

                        if operator == "eq":
                            if entity_value != value:
                                match = False
                                break
                        elif operator == "in":
                            if entity_value not in (value if isinstance(value, list) else [value]):
                                match = False
                                break

                    if match:
                        matching_logic = logic
                        break

        # Evaluate condition
        when_expr = None
        condition_result = True
        explanation = "规则执行完成"

        if matching_logic and matching_logic.get("when"):
            when_expr = matching_logic["when"].get("expression")
        elif rule.get("when"):
            when_expr = rule["when"].get("expression")

        if when_expr:
            try:
                eval_context = {**entity_data, **context.computed_metrics}
                condition_result = expression_engine.evaluate(when_expr, eval_context)
                explanation = f"条件表达式: {when_expr} = {condition_result}"
            except Exception as e:
                condition_result = False
                explanation = f"条件评估错误: {str(e)}"

        # Execute action
        context_before = dict(context.computed_metrics)

        then_action = None
        if matching_logic:
            then_action = matching_logic.get("then_action")
        if not then_action:
            then_action = rule.get("then_action")

        if condition_result and then_action:
            action_type = then_action.get("action_type", "")

            if action_type == "set_flag":
                output = then_action.get("output", {})
                for key, value in output.items():
                    context.computed_metrics[key] = value
                    final_outputs[key] = value
                    explanation = f"设置 {key} = {value}"

            elif action_type == "compute":
                output = then_action.get("output", {})
                for key, formula in output.items():
                    if isinstance(formula, str):
                        try:
                            eval_context = {**entity_data, **context.computed_metrics}
                            result = expression_engine.evaluate(formula, eval_context)
                            context.computed_metrics[key] = result
                            final_outputs[key] = result
                            explanation = f"计算 {key} = {result}"
                        except Exception as e:
                            explanation = f"计算错误: {str(e)}"
                    else:
                        context.computed_metrics[key] = formula
                        final_outputs[key] = formula

            elif action_type == "approve":
                context.computed_metrics["decision"] = "APPROVED"
                final_outputs["decision"] = "APPROVED"
                explanation = "批准通过"

            elif action_type == "reject":
                context.computed_metrics["decision"] = "REJECTED"
                context.computed_metrics["eligible"] = False
                final_outputs["decision"] = "REJECTED"
                final_outputs["eligible"] = False
                explanation = "拒绝"

        elif not condition_result:
            else_action = None
            if matching_logic:
                else_action = matching_logic.get("else_action")
            if else_action:
                explanation = "条件不满足，执行 else 分支"
            else:
                explanation = "条件不满足，规则跳过"

        steps.append({
            "step": len(steps) + 1,
            "rule_id": rule_id,
            "rule_name": rule_name,
            "rule_type": rule_type,
            "condition_expression": when_expr or "",
            "condition_result": condition_result,
            "context_before": context_before if request.include_trace else {},
            "context_after": dict(context.computed_metrics) if request.include_trace else {},
            "status": "passed" if condition_result else "skipped",
            "explanation": explanation,
            "outputs": final_outputs.copy(),
        })

    # Determine final decision
    decision = context.computed_metrics.get("decision")
    if not decision:
        if context.computed_metrics.get("eligible") is False:
            decision = "REJECTED"
        elif context.computed_metrics.get("eligible") is True:
            decision = "APPROVED"
        else:
            decision = "REVIEW"

    return success_response(data={
        "entity_id": request.entity_id,
        "dimension": request.dimension,
        "steps": steps,
        "execution_path": [s["rule_id"] for s in steps if s["status"] == "passed"],
        "skipped_rules": [s["rule_id"] for s in steps if s["status"] == "skipped"],
        "final_outputs": final_outputs,
        "decision": decision,
        "computed_metrics": context.computed_metrics,
    })


@router.post("/views/{view_id}/execute/simulate", response_model=dict)
async def execute_simulate(view_id: str, request: ExecuteSimulateRequest):
    """Execute what-if simulation with variable overrides."""
    storage = _get_storage()
    space = await storage.load(view_id)

    if not space:
        return error_response(code="NOT_FOUND", message=f"View {view_id} not found")

    # Find the entity
    entity = None
    for e in space.instances.entities:
        if e.get("entity_id") == request.entity_id:
            entity = e
            break

    if not entity:
        return error_response(code="NOT_FOUND", message=f"Entity {request.entity_id} not found")

    # Execute baseline analysis
    baseline_overrides = {}
    baseline_result = await _execute_analysis(
        space, entity, request.dimension, baseline_overrides, request.include_trace
    )

    # Execute simulated analysis with overrides
    simulated_result = await _execute_analysis(
        space, entity, request.dimension, request.overrides or {}, request.include_trace
    )

    # Build diffs
    diffs = []
    all_keys = set(baseline_result.keys()) | set(simulated_result.keys())
    for key in all_keys:
        baseline_val = baseline_result.get(key)
        simulated_val = simulated_result.get(key)
        if baseline_val != simulated_val:
            diffs.append({
                "field": key,
                "baseline_value": baseline_val,
                "simulated_value": simulated_val,
                "change_type": "changed" if key in baseline_result else "new",
                "impact": f"{baseline_val} → {simulated_val}",
            })

    return success_response(data={
        "entity_id": request.entity_id,
        "dimension": request.dimension,
        "simulation_type": "what_if",
        "baseline_outputs": baseline_result,
        "simulated_outputs": simulated_result,
        "comparison": {
            "diffs": diffs,
        },
        "final_context": {
            "entity_data": entity,
            "computed_metrics": simulated_result,
        },
    })


async def _execute_analysis(
    space: SemanticSpace,
    entity: dict,
    dimension: str,
    overrides: dict[str, Any],
    include_trace: bool
) -> dict[str, Any]:
    """Execute analysis with optional overrides."""
    expression_engine = ExpressionEngine()

    # Apply overrides
    entity_data = dict(entity)
    entity_data["_concept"] = entity.get("_concept", "Unknown")
    entity_data.update(overrides)

    context = ExecutionContext(
        entity_id=entity.get("entity_id"),
        dimension=dimension,
        entity_data=entity_data,
        computed_metrics={},
    )

    computed = {}

    # Execute rules
    sorted_rules = sorted(
        space.layers.L4_business_logic.rule_definitions,
        key=lambda r: r.get("priority", 100),
        reverse=True
    )

    for rule in sorted_rules:
        rule_id = rule["id"]
        if not rule.get("enabled", True):
            continue

        # Find matching logic
        logic_ids = rule.get("logic_ids", [])
        matching_logic = None

        for logic_id in logic_ids:
            for logic in space.layers.L4_business_logic.rule_logics:
                if logic.get("id") == logic_id:
                    conditions = logic.get("applicable_conditions", [])
                    match = True
                    for cond in conditions:
                        classification = cond.get("classification", "")
                        value = cond.get("value")
                        entity_value = entity.get(classification, "")
                        if entity_value != value:
                            match = False
                            break
                    if match:
                        matching_logic = logic
                        break

        # Evaluate condition
        when_expr = None
        if matching_logic and matching_logic.get("when"):
            when_expr = matching_logic["when"].get("expression")
        elif rule.get("when"):
            when_expr = rule["when"].get("expression")

        condition_result = True
        if when_expr:
            try:
                eval_context = {**entity_data, **computed}
                condition_result = expression_engine.evaluate(when_expr, eval_context)
            except Exception:
                condition_result = False

        # Execute action
        if condition_result:
            then_action = None
            if matching_logic:
                then_action = matching_logic.get("then_action")
            if not then_action:
                then_action = rule.get("then_action")

            if then_action:
                action_type = then_action.get("action_type", "")

                if action_type == "set_flag":
                    output = then_action.get("output", {})
                    computed.update(output)

                elif action_type == "compute":
                    output = then_action.get("output", {})
                    for key, formula in output.items():
                        if isinstance(formula, str):
                            try:
                                eval_context = {**entity_data, **computed}
                                result = expression_engine.evaluate(formula, eval_context)
                                computed[key] = result
                            except Exception:
                                pass
                        else:
                            computed[key] = formula

                elif action_type == "approve":
                    computed["decision"] = "APPROVED"

                elif action_type == "reject":
                    computed["decision"] = "REJECTED"
                    computed["eligible"] = False

    return computed
