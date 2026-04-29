# ontology_engine/services/dag_executor.py
"""DAG Executor - Executes rule tree layer by layer using Kahn algorithm.

This module provides a services-layer adapter that converts execution_tree
(SemanticSpace-based) into engine-layer ExecutionDAG format and delegates
to engine.rule.dag_executor.DAGExecutor for actual execution.
"""

from __future__ import annotations

from typing import Any

from ontology_engine.core.semantic_space import SemanticSpace
from ontology_engine.core.types import apply_overrides, deep_copy_entity_data
from ontology_engine.engine.rule.dag_builder import DAGBuilder
from ontology_engine.engine.rule.dag_executor import (
    DAGExecutor as EngineDAGExecutor,
    ErrorStrategy,
    StepResult,
)
from ontology_engine.engine.rule.models import (
    ExecutionContext,
    RuleStep,
    ActionClause,
    ConditionClause,
)


class DAGExecutor:
    """Executes rules following Kahn algorithm layer ordering.

    Adapts the services-layer execution_tree format to the engine-layer
    DAGExecutor, providing a unified execution path with proper error
    handling, transaction support, and parallel execution.
    """

    def __init__(self, semantic_space: SemanticSpace):
        self._space = semantic_space
        self._engine_executor = EngineDAGExecutor(
            max_concurrency=1,
            error_strategy=ErrorStrategy.CONTINUE,
        )

    async def execute(
        self,
        execution_tree: dict[str, Any],
        entity_data: dict[str, Any],
        input_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute rule tree from entity data with optional overrides.

        Args:
            execution_tree: Tree with layers and steps from RuleTreeBuilder
            entity_data: Entity's current attribute values
            input_overrides: Override values for what-if analysis

        Returns:
            Execution result with final_outputs, step_results, errors
        """
        working_data = deep_copy_entity_data(entity_data)
        if input_overrides:
            apply_overrides(working_data, input_overrides)

        rule_steps = self._build_rule_steps(execution_tree)
        if not rule_steps:
            return {
                "final_outputs": {},
                "step_results": [],
                "errors": None,
            }

        context = ExecutionContext(
            entity_id="simulation",
            dimension="simulation",
            entity_data=working_data,
        )

        builder = DAGBuilder()
        dag = builder.build(rule_steps)

        if dag.has_cycle:
            return {
                "final_outputs": {},
                "step_results": [],
                "errors": ["Cycle detected in execution tree"],
            }

        engine_result = await self._engine_executor.execute(dag, context)

        return self._convert_result(engine_result, execution_tree)

    def _build_rule_steps(self, execution_tree: dict[str, Any]) -> list[RuleStep]:
        """Convert execution_tree steps to RuleStep models.

        Maps each step in the execution tree to a RuleStep with proper
        condition and action clauses derived from the SemanticSpace rules.
        """
        steps = []
        step_map: dict[str, dict] = {}

        for layer in execution_tree.get("layers", []):
            for step in layer.get("steps", []):
                step_id = step.get("step_id", "")
                step_map[step_id] = step

        for layer in execution_tree.get("layers", []):
            for step_dict in layer.get("steps", []):
                step_id = step_dict.get("step_id", "")
                step_name = step_dict.get("step_name", step_id)

                condition = self._build_condition(step_dict)
                then_action = self._build_then_action(step_dict)
                else_action = self._build_else_action(step_dict)
                depends_on = step_dict.get("depends_on", [])

                rule_step = RuleStep(
                    id=step_id,
                    name=step_name,
                    when=condition,
                    then=then_action,
                    else_=else_action,
                    enabled=True,
                    depends_on=depends_on,
                )
                steps.append(rule_step)

        return steps

    def _build_condition(self, step_dict: dict) -> ConditionClause | None:
        """Build ConditionClause from step dict."""
        condition = step_dict.get("condition")
        if not condition:
            return None
        if isinstance(condition, dict):
            return ConditionClause.from_dict(condition)
        return None

    def _build_then_action(self, step_dict: dict) -> ActionClause:
        """Build ActionClause from step dict, enriched with SemanticSpace data."""
        action = step_dict.get("action", {})
        operator = action.get("operator", "EXECUTE")
        params = action.get("params", {})
        output_mapping = action.get("output_mapping", {})

        step_id = step_dict.get("step_id", "")
        rd = self._find_rule_definition(step_id)
        if rd:
            logic_ids = rd.get("logic_ids", [])
            if logic_ids:
                rule_logics = self._space.layers.L4_business_logic.rule_logics
                logic = next((rl for rl in rule_logics if rl.get("id") == logic_ids[0]), None)
                if logic:
                    then_action = logic.get("then_action", {})
                    if then_action:
                        operator = then_action.get("operator", operator)
                        params = {**params, **then_action.get("params", {})}

        return ActionClause(
            operator=operator,
            params=params,
            output_mapping=output_mapping,
        )

    def _build_else_action(self, step_dict: dict) -> ActionClause | None:
        """Build else ActionClause from step dict, enriched with SemanticSpace data."""
        else_action = step_dict.get("else_action")
        if not else_action:
            step_id = step_dict.get("step_id", "")
            rd = self._find_rule_definition(step_id)
            if rd:
                logic_ids = rd.get("logic_ids", [])
                if logic_ids:
                    rule_logics = self._space.layers.L4_business_logic.rule_logics
                    logic = next((rl for rl in rule_logics if rl.get("id") == logic_ids[0]), None)
                    if logic:
                        else_action = logic.get("else_action")
        if not else_action or not isinstance(else_action, dict):
            return None
        return ActionClause(
            operator=else_action.get("operator", "EXECUTE"),
            params=else_action.get("params", {}),
            output_mapping=else_action.get("output_mapping", {}),
        )

    def _find_rule_definition(self, step_id: str) -> dict | None:
        """Find rule definition in SemanticSpace by step_id."""
        rule_defs = self._space.layers.L4_business_logic.rule_definitions
        return next((r for r in rule_defs if r.get("id") == step_id), None)

    def _convert_result(
        self,
        engine_result: Any,
        execution_tree: dict[str, Any],
    ) -> dict[str, Any]:
        """Convert engine ExecutionResult to services-layer format."""
        all_step_results = []
        final_outputs = {}
        errors = []

        for layer in execution_tree.get("layers", []):
            layer_steps = []
            for step_dict in layer.get("steps", []):
                step_id = step_dict.get("step_id", "")
                sr: StepResult | None = engine_result.results.get(step_id)

                if sr is None:
                    continue

                step_output = {
                    "step_id": sr.step_id,
                    "step_name": sr.step_name,
                    "condition_result": sr.condition_result,
                    "condition_detail": sr.condition_detail,
                    "action_taken": "compute" if not sr.skipped and sr.output else "none",
                    "output": sr.output,
                    "input_values_used": sr.input_values_used,
                    "duration_ms": sr.duration_ms,
                }

                if sr.skipped:
                    step_output["action_taken"] = "skipped"
                elif sr.rejected:
                    step_output["action_taken"] = "rejected"
                elif sr.error:
                    step_output["action_taken"] = "error"
                    step_output["error"] = sr.error
                    errors.append(f"{sr.step_id}: {sr.error}")

                if sr.output and not sr.error:
                    for k, v in sr.output.items():
                        final_outputs[k] = v

                layer_steps.append(step_output)

            all_step_results.append({
                "layer_index": layer.get("layer_index", 0),
                "layer_name": layer.get("rule_groups", []),
                "step_results": layer_steps,
            })

        return {
            "final_outputs": final_outputs,
            "step_results": all_step_results,
            "errors": errors if errors else None,
        }
