"""DAG Executor for rule step parallel execution with error strategies."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ontology_engine.engine.rule.dag_builder import ExecutionDAG, DAGNode, DAGLayer
from ontology_engine.engine.rule.models import (
    ExecutionContext,
    ConditionClause,
    ActionClause,
    Alert,
)
from ontology_engine.engine.rule.transaction import RuleTransaction, ContextSnapshot
from ontology_engine.engine.expression.engine import ExpressionEngine
from ontology_engine.engine.rule.operators.base import OperatorRegistry


class ErrorStrategy(Enum):
    """Error handling strategy when a step fails."""
    STOP_LAYER = "stop_layer"
    CONTINUE = "continue"
    ABORT_ALL = "abort_all"


class LayerExecutionError(Exception):
    """Raised when a layer fails with STOP_LAYER strategy."""

    def __init__(self, layer_index: int, errors: list[Exception]):
        self.layer_index = layer_index
        self.errors = errors
        step_ids = [e.step_id for e in errors if hasattr(e, 'step_id')]
        super().__init__(
            f"Layer {layer_index} failed with {len(errors)} error(s): "
            f"{', '.join(step_ids) if step_ids else str(errors)}"
        )


class StepExecutionError(Exception):
    """Raised when a step execution fails."""

    def __init__(self, step_id: str, message: str):
        self.step_id = step_id
        super().__init__(f"Step '{step_id}' failed: {message}")


class ExecutionAbortedError(Exception):
    """Raised when execution is aborted with ABORT_ALL strategy."""
    pass


@dataclass
class StepResult:
    """Result of a single step execution."""
    step_id: str
    step_name: str = ""
    skipped: bool = False
    rejected: bool = False
    reason: str | None = None
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    alert_emitted: bool = False
    condition_result: bool | None = None
    condition_detail: dict[str, Any] | None = None
    input_values_used: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


@dataclass
class ExecutionResult:
    """Result of DAG execution."""
    results: dict[str, StepResult]
    context: ExecutionContext


class DAGExecutor:
    """Execute rule steps in DAG with parallel layer execution.

    Executes steps in topological order, with parallel execution
    within each layer. Supports three error strategies.
    """

    def __init__(
        self,
        max_concurrency: int = 8,
        error_strategy: ErrorStrategy = ErrorStrategy.STOP_LAYER,
        pipeline_state_manager: Any = None,
    ):
        self.max_concurrency = max_concurrency
        self.error_strategy = error_strategy
        self.expression_engine = ExpressionEngine()
        self._semaphore: asyncio.Semaphore | None = None
        self._psm = pipeline_state_manager

    async def execute(
        self,
        dag: ExecutionDAG,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Execute the DAG.

        Args:
            dag: The ExecutionDAG to execute.
            context: The ExecutionContext for rule execution.

        Returns:
            ExecutionResult with all step results and final context.

        Raises:
            LayerExecutionError: When STOP_LAYER and a layer fails.
            ExecutionAbortedError: When ABORT_ALL and an error occurs.
        """
        results: dict[str, StepResult] = {}
        transaction = RuleTransaction(context)

        run_id = None
        if self._psm:
            try:
                run = await self._psm.create_run(
                    rule_logic_name="dag_execution",
                    rule_definition_name="dag_execution",
                    entity_id=context.entity_id if hasattr(context, 'entity_id') else "",
                    dimension=context.dimension if hasattr(context, 'dimension') else "",
                )
                run_id = run.id
                await self._psm.start_run(run_id)
            except Exception:
                run_id = None

        try:
            for layer in dag.layers:
                snapshot = transaction.snapshot()

                layer_results = await self._execute_layer(
                    layer, context, results, transaction, snapshot
                )

                failures = [
                    r for r in layer_results if r.error is not None
                ]

                if failures and self.error_strategy == ErrorStrategy.STOP_LAYER:
                    transaction.restore(snapshot)
                    if self._psm and run_id:
                        await self._psm.fail_run(run_id, f"Layer {layer.index} failed")
                    raise LayerExecutionError(layer.index, [
                        StepExecutionError(r.step_id, r.error) for r in failures
                    ])

                if failures and self.error_strategy == ErrorStrategy.ABORT_ALL:
                    transaction.restore(snapshot)
                    if self._psm and run_id:
                        await self._psm.fail_run(run_id, f"Aborted at layer {layer.index}")
                    raise ExecutionAbortedError(
                        f"Execution aborted at layer {layer.index} due to {len(failures)} failure(s)"
                    )

                transaction.commit()

            if self._psm and run_id:
                await self._psm.complete_run(run_id)

        except (LayerExecutionError, ExecutionAbortedError):
            raise
        except Exception as e:
            if self._psm and run_id:
                await self._psm.fail_run(run_id, str(e))
            raise

        return ExecutionResult(results=results, context=context)

    async def _execute_layer(
        self,
        layer: "DAGLayer",
        context: ExecutionContext,
        results: dict[str, StepResult],
        transaction: RuleTransaction,
        snapshot: "ContextSnapshot",
    ) -> list[StepResult]:
        """Execute all nodes in a layer with concurrency control.

        Args:
            layer: The DAGLayer to execute.
            context: The ExecutionContext.
            results: Dict to accumulate step results.
            transaction: The RuleTransaction.
            snapshot: Snapshot to restore on error.

        Returns:
            List of StepResults for all nodes in the layer.
        """
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrency)

        tasks = [
            self._execute_with_semaphore(node, context, results, transaction, snapshot)
            for node in layer.nodes
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        processed: list[StepResult] = []
        for r in raw_results:
            if isinstance(r, Exception):
                processed.append(StepResult(
                    step_id="unknown",
                    error=str(r),
                ))
            else:
                processed.append(r)
        return processed

    async def _execute_with_semaphore(
        self,
        node: DAGNode,
        context: ExecutionContext,
        results: dict[str, StepResult],
        transaction: RuleTransaction,
        snapshot: "ContextSnapshot",
    ) -> StepResult:
        """Execute a single node with semaphore control.

        Args:
            node: The DAGNode to execute.
            context: The ExecutionContext.
            results: Dict to accumulate step results.
            transaction: The RuleTransaction.
            snapshot: Snapshot to restore on error.

        Returns:
            StepResult for the executed node.
        """
        async with self._semaphore:
            return await self._execute_step(node, context, results)

    async def _execute_step(
        self,
        node: DAGNode,
        context: ExecutionContext,
        results: dict[str, StepResult],
    ) -> StepResult:
        """Execute a single step.

        Evaluates the condition and executes the appropriate action.

        Args:
            node: The DAGNode containing the step.
            context: The ExecutionContext.
            results: Dict to accumulate step results.

        Returns:
            StepResult for the executed step.
        """
        step = node.step
        step_id = step.id
        step_name = step.name or step_id
        start_time = time.time()

        try:
            if not step.enabled:
                result = StepResult(step_id=step_id, step_name=step_name, skipped=True, reason="Step disabled", duration_ms=int((time.time() - start_time) * 1000))
                results[step_id] = result
                return result

            condition_passed = await self._evaluate_condition(step.when, context)

            input_values_used = {}
            eval_ctx = self._build_expression_context(context)
            if step.when and step.when.expression:
                for token in _extract_variable_names(step.when.expression):
                    if token in eval_ctx:
                        input_values_used[token] = eval_ctx[token]

            if not condition_passed:
                if step.else_:
                    output = await self._execute_action(step.else_, context)
                    result = StepResult(
                        step_id=step_id,
                        step_name=step_name,
                        skipped=False,
                        output=output,
                        reason="Condition false, else branch executed",
                        condition_result=False,
                        condition_detail=_build_condition_detail(step.when, False),
                        input_values_used=input_values_used,
                        duration_ms=int((time.time() - start_time) * 1000),
                    )
                else:
                    result = StepResult(
                        step_id=step_id,
                        step_name=step_name,
                        skipped=True,
                        reason="Condition not met",
                        condition_result=False,
                        condition_detail=_build_condition_detail(step.when, False),
                        input_values_used=input_values_used,
                        duration_ms=int((time.time() - start_time) * 1000),
                    )
                results[step_id] = result
                return result

            output = await self._execute_action(step.then, context)

            if "error" in output:
                result = StepResult(
                    step_id=step_id,
                    step_name=step_name,
                    skipped=False,
                    error=output.get("error"),
                    output=output,
                    condition_result=True,
                    condition_detail=_build_condition_detail(step.when, True),
                    input_values_used=input_values_used,
                    duration_ms=int((time.time() - start_time) * 1000),
                )
                results[step_id] = result
                return result

            result = StepResult(
                step_id=step_id,
                step_name=step_name,
                skipped=False,
                output=output,
                condition_result=True,
                condition_detail=_build_condition_detail(step.when, True),
                input_values_used=input_values_used,
                duration_ms=int((time.time() - start_time) * 1000),
            )

            if output.get("_rejected") or output.get("rejected") or output.get("eligible") is False:
                result.rejected = True
                result.reason = output.get("rejection_reason", "Rejected by rule")

            if output.get("alerts") or output.get("alert_triggered"):
                result.alert_emitted = True

            results[step_id] = result
            return result

        except Exception as e:
            result = StepResult(
                step_id=step_id,
                step_name=step_name,
                skipped=False,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )
            results[step_id] = result
            return result

    async def _evaluate_condition(
        self,
        condition: ConditionClause,
        context: ExecutionContext,
    ) -> bool:
        """Evaluate a condition clause.

        Args:
            condition: The ConditionClause to evaluate.
            context: The ExecutionContext.

        Returns:
            True if condition passes, False otherwise.
        """
        if condition is None:
            return True

        if condition.type == "expression":
            if not condition.expression:
                return True
            # Build context for expression evaluation
            eval_context = self._build_expression_context(context)
            try:
                return bool(self.expression_engine.evaluate(condition.expression, eval_context))
            except Exception:
                return False

        elif condition.type == "all_of":
            # All sub-conditions must be true
            for sub_expr in condition.sub_conditions:
                eval_context = self._build_expression_context(context)
                try:
                    if not bool(self.expression_engine.evaluate(sub_expr, eval_context)):
                        return False
                except Exception:
                    return False
            return True

        elif condition.type == "any_of":
            # Any sub-condition must be true
            for sub_expr in condition.sub_conditions:
                eval_context = self._build_expression_context(context)
                try:
                    if bool(self.expression_engine.evaluate(sub_expr, eval_context)):
                        return True
                except Exception:
                    continue
            return False

        return True

    async def _execute_action(
        self,
        action: ActionClause,
        context: ExecutionContext,
    ) -> dict[str, Any]:
        """Execute an action clause.

        Args:
            action: The ActionClause to execute.
            context: The ExecutionContext.

        Returns:
            Output dict from the operator execution.
        """
        operator_name = action.operator

        # Build context for operator
        operator_context = self._build_operator_context(context)

        try:
            operator = OperatorRegistry.get(operator_name)
            output = await operator.execute(
                inputs=action.params,
                config={},
                context=operator_context,
            )
        except Exception as e:
            output = {"error": str(e)}

        # Apply output mapping if present
        if action.output_mapping:
            mapped_output = {}
            for target_key, source_key in action.output_mapping.items():
                if source_key in output:
                    mapped_output[target_key] = output[source_key]
                else:
                    mapped_output[target_key] = output.get(target_key)
            output = mapped_output

        # Update context with computed metrics from operator output
        # (similar to RuleExecutor behavior)
        for key, value in output.items():
            if key not in ("error", "alert_triggered", "alerts"):
                # Set flag if key is a boolean-like flag result
                if isinstance(value, bool):
                    context.flags[key] = value
                else:
                    context.computed_metrics[key] = value

        # Handle alert triggering
        if output.get("alert_triggered"):
            alert = Alert(
                level=output.get("level", "info"),
                type=output.get("type", "general"),
                message=output.get("message", ""),
                data=output.get("data", {})
            )
            context.alerts.append(alert)

        return output

    def _build_expression_context(self, context: ExecutionContext) -> dict[str, Any]:
        """Build a flat context for expression evaluation.

        Args:
            context: The ExecutionContext.

        Returns:
            Flat dict with entity_data, computed_metrics, flags, and categories.
        """
        eval_context: dict[str, Any] = {}

        # Add entity data
        eval_context.update(context.entity_data)

        # Add computed metrics
        eval_context.update(context.computed_metrics)

        # Add flags
        eval_context.update(context.flags)

        # Add categories
        eval_context.update(context.categories)

        return eval_context

    def _build_operator_context(self, context: ExecutionContext) -> dict[str, Any]:
        """Build context dict for operator execution.

        Args:
            context: The ExecutionContext.

        Returns:
            Dict with all context data for operators.
        """
        return {
            "entity_id": context.entity_id,
            "dimension": context.dimension,
            "entity_data": context.entity_data,
            "computed_metrics": context.computed_metrics,
            "flags": context.flags,
            "alerts": [a.__dict__ for a in context.alerts],
            "categories": context.categories,
        }


_VAR_PATTERN = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")


def _extract_variable_names(expression: str) -> list[str]:
    """Extract potential variable names from an expression string."""
    if not expression:
        return []
    return _VAR_PATTERN.findall(expression)


def _build_condition_detail(condition: ConditionClause | None, result: bool) -> dict[str, Any]:
    """Build condition detail dict for frontend display."""
    if condition is None:
        return {"type": "none", "result": result, "explanation": "No condition"}
    if condition.type == "expression":
        return {
            "type": "expression",
            "expression": condition.expression or "",
            "result": result,
            "explanation": f"Condition '{condition.expression}' evaluated to {result}",
        }
    if condition.type == "all_of":
        return {
            "type": "all_of",
            "sub_conditions": condition.sub_conditions,
            "result": result,
            "explanation": f"All conditions evaluated to {result}",
        }
    if condition.type == "any_of":
        return {
            "type": "any_of",
            "sub_conditions": condition.sub_conditions,
            "result": result,
            "explanation": f"Any condition evaluated to {result}",
        }
    return {"type": condition.type, "result": result}
