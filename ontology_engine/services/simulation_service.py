# ontology_engine/services/simulation_service.py
"""Simulation service for rule execution with dry-run mode."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

from ontology_engine.engine.rule.models import (
    RuleGroupDefinition,
    RuleStep,
    ActionClause,
    ConditionClause,
)
from ontology_engine.engine.rule.evaluator import ExpressionEvaluator
from ontology_engine.engine.rule.operators import OperatorRegistry


@dataclass
class SimulationStep:
    """Single step in a simulation with input/output/source tracking.

    Records the complete execution trace for a rule step including:
    - step metadata (id, name)
    - input values used in evaluation
    - output values produced
    - source of data (entity_data, computed_metrics, previous_step)
    - execution order and layer (for DAG visualization)
    """
    step_id: str
    step_name: str
    layer_index: int = 0  # DAG layer index for parallel execution
    execution_order: int = 0  # Global execution order

    # Input tracking
    input_values: dict[str, Any] = field(default_factory=dict)
    input_sources: dict[str, str] = field(default_factory=dict)  # key -> source (entity_data, computed_metrics, step_id)

    # Output tracking
    output_values: dict[str, Any] = field(default_factory=dict)
    output_destinations: dict[str, str] = field(default_factory=dict)  # key -> destination

    # Execution result
    condition_result: bool = False
    condition_expression: str = ""
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None
    duration_ms: float = 0.0

    # Source step for dependency tracking
    depends_on: list[str] = field(default_factory=list)
    produced_by: str = ""  # step_id that produced dependent values


@dataclass
class ConditionDetail:
    """Detailed condition evaluation result."""
    type: str  # expression, all_of, any_of
    expression: str | None = None
    sub_conditions: list[dict[str, Any]] = field(default_factory=list)
    result: bool = False
    explanation: str = ""


@dataclass
class StepSimulationResult:
    """Result of a single step simulation."""
    step_id: str
    step_name: str
    condition_result: bool
    condition_detail: ConditionDetail | None = None
    action_taken: str | None = None
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class SimulationResult:
    """Result of a rule group simulation."""
    rule_group_name: str
    steps: list[StepSimulationResult]
    final_output: dict[str, Any] = field(default_factory=dict)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class DAGSimulationResult:
    """Result of a DAG simulation with full trace.

    Contains all simulation steps with complete input/output/source tracking
    for multi-rule-group simulations and agent interactive scenarios.
    """
    # Top-level metadata
    simulation_id: str = ""
    simulation_type: str = "dag"  # dag | what_if | agent_interactive

    # Rule groups involved
    rule_groups: list[str] = field(default_factory=list)  # ordered by execution

    # All steps across all rule groups, in execution order
    steps: list[SimulationStep] = field(default_factory=list)

    # DAG structure for visualization
    dag_layers: list[list[str]] = field(default_factory=list)  # layer_index -> [step_ids]

    # Final computed values (merged from all steps)
    final_output: dict[str, Any] = field(default_factory=dict)

    # Alerts and errors
    alerts: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # Decision (if applicable)
    decision: str | None = None
    decision_reasoning: str | None = None

    # Agent interactive mode: modified inputs for re-simulation
    modified_inputs: dict[str, Any] = field(default_factory=dict)

    # What-if comparison
    baseline_output: dict[str, Any] = field(default_factory=dict)
    comparison: dict[str, Any] = field(default_factory=dict)  # diff between baseline and simulation


class SimulationService:
    """Service for simulating rule execution without persisting results.

    Uses dry_run=True to execute rules in-memory without writing to storage
    or triggering alerts.
    """

    def __init__(self):
        """Initialize SimulationService."""
        self._evaluator = ExpressionEvaluator()

    @staticmethod
    def create_expression_engine() -> Any:
        """Create an ExpressionEngine instance.

        Factory method to avoid direct engine imports in the API layer.
        Follows the module boundary rule: api/ → services/ only.
        """
        from ontology_engine.engine.expression.engine import ExpressionEngine
        return ExpressionEngine()

    @staticmethod
    def create_execution_context(
        entity_id: str = "",
        dimension: str = "",
        entity_data: dict[str, Any] | None = None,
        computed_metrics: dict[str, Any] | None = None,
    ) -> Any:
        """Create an ExecutionContext instance.

        Factory method to avoid direct engine imports in the API layer.
        Follows the module boundary rule: api/ → services/ only.
        """
        from ontology_engine.engine.rule.models import ExecutionContext
        return ExecutionContext(
            entity_id=entity_id,
            dimension=dimension,
            entity_data=entity_data or {},
            computed_metrics=computed_metrics or {},
        )

    @staticmethod
    def list_operator_schemas() -> list[Any]:
        """List all available operator schemas.

        Factory method to avoid direct engine imports in the API layer.
        """
        from ontology_engine.engine.rule.operators import build_operator_schemas
        return build_operator_schemas()

    @staticmethod
    def get_operator_schema(name: str) -> Any:
        """Get a specific operator schema by name.

        Factory method to avoid direct engine imports in the API layer.
        """
        from ontology_engine.engine.rule.operators.registry import get_operator_schema
        return get_operator_schema(name)

    async def simulate_rule_group(
        self,
        rule_group: RuleGroupDefinition,
        steps: list[RuleStep],
        entity_data: dict[str, Any],
        pre_computed: dict[str, Any] | None = None,
        step_filter: list[str] | None = None,
    ) -> SimulationResult:
        """Simulate execution of a rule group.

        Args:
            rule_group: Rule group definition
            steps: List of rule steps to execute
            entity_data: Entity data for evaluation
            pre_computed: Pre-computed metric values
            step_filter: Optional list of step IDs to execute

        Returns:
            SimulationResult with step-by-step details
        """
        pre_computed = pre_computed or {}
        context = {**entity_data, **pre_computed}
        computed: dict[str, Any] = {}
        alerts: list[dict[str, Any]] = []
        errors: list[str] = []
        step_results: list[StepSimulationResult] = []

        # Filter steps if specified
        if step_filter:
            steps = [s for s in steps if s.id in step_filter]

        for step in sorted(steps, key=lambda s: s.order):
            if not step.enabled:
                continue

            step_start = _get_time_ms()
            step_result = await self._simulate_step(step, context, computed)
            step_result.duration_ms = _get_time_ms() - step_start
            step_results.append(step_result)

            # Update context with computed values
            computed.update(step_result.output)

            # Check for errors
            if step_result.error:
                errors.append(f"Step {step.id}: {step_result.error}")

            # Add alerts
            if step_result.output.get("_alert"):
                alerts.append({
                    "level": step_result.output.get("_alert_level", "info"),
                    "type": step_result.output.get("_alert_type", "general"),
                    "message": step_result.output.get("_alert_message", ""),
                    "step_id": step.id,
                })

        # Compute final output
        final_output = dict(computed)
        final_output.update({
            k: v for k, v in context.items()
            if k not in entity_data and k not in computed
        })

        return SimulationResult(
            rule_group_name=rule_group.name,
            steps=step_results,
            final_output=final_output,
            alerts=alerts,
            errors=errors,
        )

    async def _simulate_step(
        self,
        step: RuleStep,
        context: dict[str, Any],
        computed: dict[str, Any],
    ) -> StepSimulationResult:
        """Simulate a single rule step.

        Args:
            step: Rule step to simulate
            context: Evaluation context
            computed: Previously computed values

        Returns:
            StepSimulationResult with details
        """
        try:
            # Evaluate condition
            condition_detail = self._evaluate_condition(step.when, {**context, **computed})
            condition_result = condition_detail.result

            if not condition_result:
                return StepSimulationResult(
                    step_id=step.id,
                    step_name=step.name,
                    condition_result=False,
                    condition_detail=condition_detail,
                    action_taken=None,
                    output={"skipped": "condition not met"},
                )

            # Execute then action
            if step.then:
                output, action_taken = await self._execute_action(
                    step.then, {**context, **computed}
                )
            else:
                output = {}
                action_taken = None

            return StepSimulationResult(
                step_id=step.id,
                step_name=step.name,
                condition_result=True,
                condition_detail=condition_detail,
                action_taken=action_taken,
                output=output,
            )

        except Exception as e:
            return StepSimulationResult(
                step_id=step.id,
                step_name=step.name,
                condition_result=False,
                condition_detail=None,
                action_taken=None,
                output={},
                error=str(e),
            )

    def _evaluate_condition(
        self,
        condition: ConditionClause,
        context: dict[str, Any],
    ) -> ConditionDetail:
        """Evaluate a condition with detailed breakdown.

        Args:
            condition: Condition to evaluate
            context: Evaluation context

        Returns:
            ConditionDetail with results and explanations
        """
        detail = ConditionDetail(
            type=condition.type,
            expression=condition.expression,
        )

        if condition.type == "expression" and condition.expression:
            result = self._evaluator.evaluate(condition.expression, context)
            detail.result = bool(result)
            detail.explanation = self._explain_expression(condition.expression, context, result)
            detail.sub_conditions = [{
                "expr": condition.expression,
                "result": result,
                "explain": detail.explanation,
            }]

        elif condition.type == "all_of" and condition.sub_conditions:
            sub_results = []
            all_passed = True
            for expr in condition.sub_conditions:
                result = self._evaluator.evaluate(expr, context)
                all_passed = all_passed and bool(result)
                sub_results.append({
                    "expr": expr,
                    "result": result,
                    "explain": self._explain_expression(expr, context, result),
                })
            detail.result = all_passed
            detail.sub_conditions = sub_results
            detail.explanation = f"ALL_OF: {all_passed}"

        elif condition.type == "any_of" and condition.sub_conditions:
            sub_results = []
            any_passed = False
            for expr in condition.sub_conditions:
                result = self._evaluator.evaluate(expr, context)
                any_passed = any_passed or bool(result)
                sub_results.append({
                    "expr": expr,
                    "result": result,
                    "explain": self._explain_expression(expr, context, result),
                })
            detail.result = any_passed
            detail.sub_conditions = sub_results
            detail.explanation = f"ANY_OF: {any_passed}"

        else:
            detail.result = True
            detail.explanation = "No condition (always true)"

        return detail

    def _explain_expression(
        self,
        expression: str,
        context: dict[str, Any],
        result: Any,
    ) -> str:
        """Generate human-readable explanation of expression evaluation.

        Args:
            expression: Expression string
            context: Evaluation context
            result: Result of evaluation

        Returns:
            Human-readable explanation
        """
        try:
            # Extract variable names from expression
            from ontology_engine.engine.expression.engine import ExpressionEngine
            var_names = ExpressionEngine._FIELD_PATTERN.findall(expression)

            explanations = []
            for name in var_names:
                if name in context:
                    value = context[name]
                    if isinstance(value, dict) and "value" in value:
                        value = value["value"]
                    explanations.append(f"{name}={value}")

            if explanations:
                return f"{' AND '.join(explanations)} → {result}"
            return f"{expression} → {result}"
        except (ValueError, TypeError, KeyError):
            # Only catch parseable errors, re-raise unexpected ones
            return f"{expression} → {result}"

    async def _execute_action(
        self,
        action: ActionClause,
        context: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        """Execute an action using the operator registry.

        Args:
            action: Action to execute
            context: Evaluation context

        Returns:
            Tuple of (output dict, action_taken string)
        """
        operator_name = action.operator
        params = action.params

        try:
            operator = OperatorRegistry.get(operator_name)
            result = await operator.execute(
                inputs=params,
                config={},
                context=context,
            )
            return result, operator_name
        except KeyError:
            # Unknown operator, return params as output
            return params, operator_name
        except Exception as e:
            # Operator error, return error info
            return {"error": str(e)}, operator_name

    # =========================================================================
    # DAG Simulation Methods
    # =========================================================================

    async def simulate_dag(
        self,
        rule_group: RuleGroupDefinition,
        steps: list[RuleStep],
        entity_data: dict[str, Any],
        pre_computed: dict[str, Any] | None = None,
    ) -> DAGSimulationResult:
        """Simulate a single rule group as DAG execution.

        This method executes rules respecting depends_on declarations,
        building a complete DAG with proper input/output/source tracking.
        No persistence - all in-memory computation only.

        Args:
            rule_group: Rule group definition
            steps: List of rule steps to execute
            entity_data: Entity data for evaluation
            pre_computed: Pre-computed metric values

        Returns:
            DAGSimulationResult with full execution trace
        """
        from ontology_engine.engine.rule.dag_builder import DAGBuilder

        pre_computed = pre_computed or {}
        simulation_id = f"sim_{rule_group.name}_{int(asyncio.get_event_loop().time() * 1000)}"

        # Build DAG from steps
        builder = DAGBuilder()
        dag = builder.build(steps)

        # Initialize execution context
        context: dict[str, Any] = {**entity_data, **pre_computed}
        computed: dict[str, Any] = {}
        simulation_steps: list[SimulationStep] = []
        errors: list[str] = []
        alerts: list[dict[str, Any]] = []
        execution_counter = 0

        # Execute each layer in topological order
        for layer in dag.layers:
            for node in layer.nodes:
                step = node.step
                if not step.enabled:
                    continue

                step_start = _get_time_ms()
                execution_counter += 1

                # Track input sources
                input_sources = self._track_input_sources(
                    step.when, context, computed
                )

                sim_step = await self._simulate_dag_step(
                    step=step,
                    context={**context, **computed},
                    computed=computed,
                    layer_index=layer.index,
                    execution_order=execution_counter,
                    input_sources=input_sources,
                )
                sim_step.duration_ms = _get_time_ms() - step_start

                simulation_steps.append(sim_step)

                # Update computed with new outputs
                computed.update(sim_step.output_values)

                # Track errors and alerts
                if sim_step.error:
                    errors.append(f"Step {step.id}: {sim_step.error}")

                if sim_step.output_values.get("_alert"):
                    alerts.append({
                        "level": sim_step.output_values.get("_alert_level", "info"),
                        "type": sim_step.output_values.get("_alert_type", "general"),
                        "message": sim_step.output_values.get("_alert_message", ""),
                        "step_id": step.id,
                    })

        # Build DAG layers for visualization
        dag_layers = [
            [node.step_id for node in layer.nodes]
            for layer in dag.layers
        ]

        return DAGSimulationResult(
            simulation_id=simulation_id,
            simulation_type="dag",
            rule_groups=[rule_group.name],
            steps=simulation_steps,
            dag_layers=dag_layers,
            final_output=dict(computed),
            alerts=alerts,
            errors=errors,
            decision=computed.get("final_decision"),
            decision_reasoning=computed.get("decision_reasoning"),
        )

    async def _simulate_dag_step(
        self,
        step: RuleStep,
        context: dict[str, Any],
        computed: dict[str, Any],
        layer_index: int,
        execution_order: int,
        input_sources: dict[str, str],
    ) -> SimulationStep:
        """Simulate a single DAG step with full input/output tracking.

        Args:
            step: Rule step to simulate
            context: Full evaluation context (entity_data + computed)
            computed: Previously computed values
            layer_index: DAG layer index
            execution_order: Global execution order
            input_sources: Map of input keys to their sources

        Returns:
            SimulationStep with complete trace
        """
        sim_step = SimulationStep(
            step_id=step.id,
            step_name=step.name,
            layer_index=layer_index,
            execution_order=execution_order,
            input_values=dict({k: context.get(k) for k in input_sources.keys()}),
            input_sources=input_sources,
            depends_on=step.depends_on,
        )

        try:
            # Evaluate condition
            condition_detail = self._evaluate_condition(step.when, context)
            sim_step.condition_result = condition_detail.result
            sim_step.condition_expression = (
                step.when.expression if step.when else ""
            )

            if not condition_detail.result:
                sim_step.skipped = True
                sim_step.skip_reason = "Condition not met"
                return sim_step

            # Execute then action
            if step.then:
                output, action_taken = await self._execute_action(
                    step.then, context
                )
                sim_step.output_values = output
                # Track output destinations (for now, mark as computed_metrics)
                sim_step.output_destinations = {
                    k: "computed_metrics" for k in output.keys()
                }
            else:
                sim_step.output_values = {}

        except Exception as e:
            sim_step.error = str(e)

        return sim_step

    def _track_input_sources(
        self,
        condition: ConditionClause | None,
        entity_data: dict[str, Any],
        computed: dict[str, Any],
    ) -> dict[str, str]:
        """Track which inputs come from entity_data vs computed metrics.

        Args:
            condition: Condition to analyze for variable references
            entity_data: Entity data dictionary
            computed: Previously computed values

        Returns:
            Dict mapping variable names to their sources
        """
        from ontology_engine.engine.expression.engine import ExpressionEngine

        sources = {}

        if condition is None:
            return sources

        # Extract variables from condition expression
        if condition.type == "expression" and condition.expression:
            var_names = ExpressionEngine._FIELD_PATTERN.findall(condition.expression)
            for name in var_names:
                if name in computed:
                    sources[name] = "computed_metrics"
                elif name in entity_data:
                    sources[name] = "entity_data"
                else:
                    sources[name] = "unknown"

        elif condition.type in ("all_of", "any_of") and condition.sub_conditions:
            for expr in condition.sub_conditions:
                var_names = re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_.]*)\b', expr)
                for name in var_names:
                    if name in computed:
                        sources[name] = "computed_metrics"
                    elif name in entity_data:
                        sources[name] = "entity_data"
                    else:
                        sources[name] = "unknown"

        return sources

    async def locate_rules_for_output(
        self,
        output_element: str,
        rule_groups: list[RuleGroupDefinition],
        all_steps: dict[str, list[RuleStep]],
    ) -> list[tuple[RuleGroupDefinition, list[RuleStep]]]:
        """Locate rule groups that produce a given output element.

        Searches rule group outputs and their step outputs to find which
        rule groups/steps contribute to the specified output element.

        Args:
            output_element: The output element name to locate
            rule_groups: List of rule group definitions
            all_steps: Dict mapping rule_group name to its steps

        Returns:
            List of (rule_group, steps) tuples that produce the output
        """
        results: list[tuple[RuleGroupDefinition, list[RuleStep]]] = []

        for rg in rule_groups:
            # Check rule group level outputs
            rg_outputs = [o.name for o in rg.outputs]
            if output_element in rg_outputs:
                steps = all_steps.get(rg.name, [])
                results.append((rg, steps))
                continue

            # Check step level outputs
            steps = all_steps.get(rg.name, [])
            contributing_steps = []

            for step in steps:
                if step.then and step.then.output_mapping:
                    # Check if output_element is in the step's output mapping
                    if output_element in step.then.output_mapping.values():
                        contributing_steps.append(step)

            if contributing_steps:
                results.append((rg, contributing_steps))

        return results

    async def build_rule_tree_simulation(
        self,
        target_output: str,
        rule_groups: list[RuleGroupDefinition],
        all_steps: dict[str, list[RuleStep]],
        entity_data: dict[str, Any],
        pre_computed: dict[str, Any] | None = None,
    ) -> DAGSimulationResult:
        """Build and execute a complete rule tree simulation.

        Starting from a target output element, this method:
        1. Locates all rule groups that produce the target
        2. For each rule group, traces back its input dependencies
        3. Builds a complete DAG execution tree
        4. Executes and returns results

        Args:
            target_output: The output element to simulate
            rule_groups: All available rule groups
            all_steps: Dict mapping rule_group name to its steps
            entity_data: Entity data for evaluation
            pre_computed: Pre-computed metric values

        Returns:
            DAGSimulationResult with complete execution trace
        """
        pre_computed = pre_computed or {}
        simulation_id = f"tree_sim_{int(asyncio.get_event_loop().time() * 1000)}"

        # Phase 1: Locate rule groups that produce the target output
        relevant_groups = await self.locate_rules_for_output(
            target_output, rule_groups, all_steps
        )

        if not relevant_groups:
            return DAGSimulationResult(
                simulation_id=simulation_id,
                simulation_type="dag",
                rule_groups=[],
                steps=[],
                errors=[f"No rule groups found for output: {target_output}"],
            )

        # Phase 2: Build ordered execution list respecting dependencies
        execution_order: list[tuple[RuleGroupDefinition, list[RuleStep]]] = []
        visited = set()
        to_visit = list(relevant_groups)

        while to_visit:
            rg, steps = to_visit.pop(0)

            if rg.id in visited:
                continue

            visited.add(rg.id)

            # Check if all dependencies are satisfied
            # (simplified: just append for now, full impl would trace inputs)
            execution_order.append((rg, steps))

        # Phase 3: Execute all rule groups in order
        all_simulation_steps: list[SimulationStep] = []
        all_dag_layers: list[list[str]] = []
        combined_computed: dict[str, Any] = dict(pre_computed)
        combined_alerts: list[dict[str, Any]] = []
        combined_errors: list[str] = []
        global_order = 0

        for rg, steps in execution_order:
            # Build DAG for this rule group
            from ontology_engine.engine.rule.dag_builder import DAGBuilder

            builder = DAGBuilder()
            dag = builder.build(steps)

            context = {**entity_data, **combined_computed}

            for layer in dag.layers:
                layer_step_ids = []

                for node in layer.nodes:
                    step = node.step
                    if not step.enabled:
                        continue

                    global_order += 1
                    step_start = _get_time_ms()

                    input_sources = self._track_input_sources(
                        step.when, entity_data, combined_computed
                    )

                    sim_step = await self._simulate_dag_step(
                        step=step,
                        context={**context, **combined_computed},
                        computed=combined_computed,
                        layer_index=len(all_dag_layers),
                        execution_order=global_order,
                        input_sources=input_sources,
                    )
                    sim_step.duration_ms = _get_time_ms() - step_start

                    all_simulation_steps.append(sim_step)
                    layer_step_ids.append(step.id)

                    # Update combined computed
                    combined_computed.update(sim_step.output_values)

                    if sim_step.error:
                        combined_errors.append(f"{rg.name}/{step.id}: {sim_step.error}")

                    if sim_step.output_values.get("_alert"):
                        combined_alerts.append({
                            "level": sim_step.output_values.get("_alert_level", "info"),
                            "type": sim_step.output_values.get("_alert_type", "general"),
                            "message": sim_step.output_values.get("_alert_message", ""),
                            "step_id": f"{rg.name}/{step.id}",
                        })

                if layer_step_ids:
                    all_dag_layers.append(layer_step_ids)

        return DAGSimulationResult(
            simulation_id=simulation_id,
            simulation_type="dag",
            rule_groups=[rg.name for rg, _ in execution_order],
            steps=all_simulation_steps,
            dag_layers=all_dag_layers,
            final_output=combined_computed,
            alerts=combined_alerts,
            errors=combined_errors,
            decision=combined_computed.get("final_decision"),
            decision_reasoning=combined_computed.get("decision_reasoning"),
        )

    async def agent_interactive_simulation(
        self,
        baseline_result: DAGSimulationResult,
        modified_inputs: dict[str, Any],
        rule_groups: list[RuleGroupDefinition],
        all_steps: dict[str, list[RuleStep]],
    ) -> DAGSimulationResult:
        """Re-simulate with modified inputs for agent interactive mode.

        Takes a previous simulation result, applies modified inputs,
        and re-executes the simulation without touching storage.

        Args:
            baseline_result: Previous simulation result to modify
            modified_inputs: Input values to change
            rule_groups: Rule groups to re-execute
            all_steps: Dict mapping rule_group name to its steps

        Returns:
            DAGSimulationResult with modified simulation and comparison
        """
        import uuid

        simulation_id = f"agent_{uuid.uuid4().hex[:8]}"

        # Extract entity_data from baseline (best effort - caller should provide full data)
        # For now, use modified inputs + baseline final_output
        entity_data = modified_inputs

        # Re-run tree simulation with modified inputs
        # Use first relevant output as target
        target = baseline_result.rule_groups[0] if baseline_result.rule_groups else ""

        result = await self.build_rule_tree_simulation(
            target_output=target,
            rule_groups=rule_groups,
            all_steps=all_steps,
            entity_data=entity_data,
            pre_computed={},
        )

        result.simulation_id = simulation_id
        result.simulation_type = "agent_interactive"
        result.modified_inputs = modified_inputs
        result.baseline_output = baseline_result.final_output

        # Build comparison
        if result.final_output and baseline_result.final_output:
            comparison = {}
            all_keys = set(result.final_output.keys()) | set(baseline_result.final_output.keys())
            for key in all_keys:
                new_val = result.final_output.get(key)
                old_val = baseline_result.final_output.get(key)
                if new_val != old_val:
                    comparison[key] = {
                        "baseline": old_val,
                        "simulated": new_val,
                        "change": "modified",
                    }
            result.comparison = comparison

        return result


def _get_time_ms() -> float:
    """Get current time in milliseconds."""
    import time
    return time.time() * 1000
