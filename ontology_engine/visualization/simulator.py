"""Rule chain simulation engine with step-by-step snapshots."""
from __future__ import annotations

import json
import logging
import math
import re
import time
import traceback
from dataclasses import asdict, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)

from ontology_engine.core.schema.models import KGMLSchema, RuleDefinition
from ontology_engine.engine.rule.evaluator import ExpressionEvaluator
from ontology_engine.engine.rule.executor import RuleExecutor
from ontology_engine.engine.rule.models import (
    ExecutionContext,
)
from ontology_engine.visualization.explainers import ConditionExplainer, ImpactAnalyzer
from ontology_engine.visualization.models import (
    ComparisonResult,
    ConditionDetail,
    ExecutionStepSnapshot,
    SimulationResult,
)


class SchemaNotLoadedError(Exception):
    """Raised when schema is not loaded."""


class EntityNotFoundError(Exception):
    """Raised when entity is not found."""

    def __init__(self, entity_id: str) -> None:
        self.entity_id = entity_id
        super().__init__(f"Entity not found: {entity_id}")


class RuleChainSimulator:
    """Rule chain simulation engine.

    Core capabilities:
    1. dry_run mode: execute rules without writing to storage
    2. what_if mode: override variable values and compare with baseline
    3. Step-by-step snapshots: record full context at each step
    4. Explainability: generate natural language explanations
    """

    def __init__(
        self,
        rule_executor: RuleExecutor,
        storage: Any,
        schema: KGMLSchema,
        metric_engine: Any | None = None,
    ) -> None:
        self.rule_executor = rule_executor
        self.storage = storage
        self.schema = schema
        self.metric_engine = metric_engine
        self.explainer = ConditionExplainer(rule_executor.evaluator)
        self.impact_analyzer = ImpactAnalyzer(schema)

    async def simulate(
        self,
        entity_id: str,
        dimension: str,
        overrides: dict[str, Any] | None = None,
        dry_run: bool = True,
    ) -> SimulationResult:
        """Execute simulation with optional variable overrides.

        Flow:
        1. Get entity data
        2. If overrides present → execute baseline simulation first
        3. Apply overrides to entity_data
        4. Execute rules with step-by-step snapshots
        5. Build What-if comparison if needed
        """
        try:
            # 1. Get entity
            logger.info(f"Finding entity: {entity_id}")
            entity = await self._find_entity(entity_id)
            if entity is None:
                raise EntityNotFoundError(entity_id)
            logger.info(f"Found entity: {entity_id}, concept: {entity.concept}")

            entity_data = dict(entity.data)
            entity_data["_concept"] = entity.concept

            # 2. Baseline execution for What-if comparison
            baseline_result: SimulationResult | None = None
            if overrides:
                logger.info("Executing baseline simulation")
                baseline_result = await self._execute_with_snapshots(
                    entity_id, dimension, dict(entity_data)
                )

            # 3. Apply overrides
            if overrides:
                logger.info(f"Applying overrides: {overrides}")
                self._apply_overrides(entity_data, overrides)

            # 4. Execute with snapshots
            logger.info(f"Executing simulation with dimension: {dimension}")
            simulation = await self._execute_with_snapshots(
                entity_id, dimension, entity_data
            )

            # 5. Build comparison
            if baseline_result and overrides:
                logger.info("Building comparison")
                comparison = self._build_comparison(baseline_result, simulation)
                simulation.comparison = comparison

            simulation.simulation_type = "what_if" if overrides else "dry_run"
            logger.info("Simulation completed successfully")

            return simulation
        except Exception as e:
            logger.error(f"Simulation error: {e}")
            logger.error(traceback.format_exc())
            raise

    async def _execute_with_snapshots(
        self,
        entity_id: str,
        dimension: str,
        entity_data: dict[str, Any],
    ) -> SimulationResult:
        """Execute rules with step-by-step snapshot recording."""
        try:
            rules = (
                self.schema.get_rules_for_dimension(dimension)
                if self.schema.rules
                else []
            )
            rules = sorted(rules, key=lambda r: -r.priority)
            logger.info(f"Found {len(rules)} rules for dimension: {dimension}")

            snapshots: list[ExecutionStepSnapshot] = []
            execution_path: list[str] = []
            skipped: list[str] = []

            # Initialize execution context
            context = ExecutionContext(
                entity_id=entity_id,
                dimension=dimension,
                entity_data=entity_data,
            )

            for step_idx, rule in enumerate(rules):
                logger.debug(f"Processing rule {step_idx + 1}: {rule.id}")
                if not rule.enabled:
                    snapshots.append(self._build_skipped_snapshot(step_idx + 1, rule))
                    skipped.append(rule.id)
                    continue

                # Check entity type scope
                entity_type = entity_data.get("_concept", "")
                if rule.scope and entity_type:
                    entity_types = rule.scope.get("entity_types", [])
                    if entity_types and entity_type not in entity_types:
                        snapshots.append(
                            self._build_skipped_snapshot(step_idx + 1, rule)
                        )
                        skipped.append(rule.id)
                        continue

                # Execute single rule with snapshot
                try:
                    step_snapshot = await self._execute_rule_with_snapshot(
                        step_idx + 1, rule, context
                    )
                    snapshots.append(step_snapshot)
                except Exception as e:
                    logger.error(f"Error executing rule {rule.id}: {e}")
                    logger.error(traceback.format_exc())
                    # Create error snapshot
                    step_snapshot = ExecutionStepSnapshot(
                        step=step_idx + 1,
                        rule_id=rule.id,
                        rule_name=rule.name or "",
                        rule_type=rule.type,
                        condition_expression="",
                        condition_result=False,
                        condition_details=[],
                        context_before={},
                        context_after={},
                        inputs={},
                        outputs={"error": str(e)},
                        status="failed",
                        duration_ms=0.0,
                        explanation=f"执行出错: {str(e)}",
                        affected_metrics=[],
                    )
                    snapshots.append(step_snapshot)

                if step_snapshot.status in ("passed", "failed"):
                    execution_path.append(rule.id)

            logger.info(f"Executed {len(snapshots)} steps, building result")

            # Build result with safe serialization
            result = SimulationResult(
                entity_id=entity_id,
                dimension=dimension,
                simulation_type="dry_run",
                steps=snapshots,
                execution_path=execution_path,
                skipped_rules=skipped,
                final_outputs=dict(context.computed_metrics),
                decision=self._determine_decision(context),
                decision_reasoning=self._generate_reasoning(context),
                alerts=[
                    {"level": a.level, "type": a.type, "message": a.message}
                    for a in context.alerts
                ],
                comparison=None,
            )
            logger.info("SimulationResult built successfully")
            return result
        except Exception as e:
            logger.error(f"Error in _execute_with_snapshots: {e}")
            logger.error(traceback.format_exc())
            raise

    async def _execute_rule_with_snapshot(
        self,
        step: int,
        rule: RuleDefinition,
        context: ExecutionContext,
    ) -> ExecutionStepSnapshot:
        """Execute a single rule and record a full step snapshot."""
        # Record context before execution
        context_before = self._snapshot_context(context)

        # Evaluate condition
        condition_result: bool | None = None
        condition_details: list[ConditionDetail] = []

        if rule.when:
            eval_context = self.rule_executor._get_eval_context(context)
            try:
                condition_result = self.rule_executor.evaluator.evaluate(
                    rule.when, eval_context
                )
                if not isinstance(condition_result, bool):
                    condition_result = bool(condition_result)
            except Exception:
                condition_result = False

            # Decompose condition and explain
            condition_details = self.explainer.explain(rule.when, eval_context)

        # Execute the rule (reusing RuleExecutor)
        start_time = time.monotonic()
        try:
            rule_result = await self.rule_executor.execute_rule(rule, context)
            duration_ms = (time.monotonic() - start_time) * 1000
            status = "passed" if rule_result.passed else "failed"
            outputs = rule_result.output
        except Exception as e:
            duration_ms = (time.monotonic() - start_time) * 1000
            status = "failed"
            outputs = {"error": str(e)}
            rule_result = None  # type: ignore[assignment]

        # Record context after execution
        context_after = self._snapshot_context(context)

        # Extract inputs (fields referenced in condition)
        inputs = self._extract_inputs(rule, context_before)

        # Generate explanation
        explanation = self._generate_step_explanation(
            rule, condition_result, rule_result
        )

        # Determine affected metrics
        affected_metrics = self._get_affected_metrics(context_before, context_after)

        return ExecutionStepSnapshot(
            step=step,
            rule_id=rule.id,
            rule_name=rule.name or "",
            rule_type=rule.type,
            condition_expression=self._serialize_condition(rule.when),
            condition_result=condition_result,
            condition_details=condition_details,
            context_before=context_before,
            context_after=context_after,
            inputs=inputs,
            outputs=outputs,
            status=status,
            duration_ms=round(duration_ms, 2),
            explanation=explanation,
            affected_metrics=affected_metrics,
        )

    def _build_skipped_snapshot(
        self, step: int, rule: RuleDefinition
    ) -> ExecutionStepSnapshot:
        """Build a snapshot for a skipped rule."""
        return ExecutionStepSnapshot(
            step=step,
            rule_id=rule.id,
            rule_name=rule.name or "",
            rule_type=rule.type,
            condition_expression=self._serialize_condition(rule.when),
            condition_result=None,
            condition_details=[],
            context_before={},
            context_after={},
            inputs={},
            outputs={"skipped": True},
            status="skipped",
            duration_ms=0.0,
            explanation=f"规则 {rule.id} 被跳过（禁用或实体类型不匹配）",
            affected_metrics=[],
        )

    def _snapshot_context(self, context: ExecutionContext) -> dict[str, Any]:
        """Create a safe snapshot of the execution context.

        Uses shallow copy for performance and to avoid deep recursion issues.
        Assumes entity_data and computed_metrics contain simple JSON-serializable types.
        """
        # Use dict.copy() for shallow copy - safe for JSON data from storage
        entity_data_snapshot = dict(context.entity_data) if context.entity_data else {}
        computed_metrics_snapshot = dict(context.computed_metrics) if context.computed_metrics else {}

        return {
            "entity_data": entity_data_snapshot,
            "computed_metrics": computed_metrics_snapshot,
            "alerts_count": len(context.alerts),
            "rule_results_count": len(context.rule_results),
        }

    def _extract_inputs(
        self, rule: RuleDefinition, context_before: dict[str, Any]
    ) -> dict[str, Any]:
        """Extract input fields referenced in the rule's condition."""
        if not rule.when:
            return {}

        inputs: dict[str, Any] = {}
        entity_data = context_before.get("entity_data", {})
        computed_metrics = context_before.get("computed_metrics", {})

        merged = {**entity_data, **computed_metrics}

        expression = self._serialize_condition(rule.when)
        # Find field references
        for match in re.finditer(
            r"\b([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\b",
            expression,
        ):
            field = match.group(1)
            if field.lower() in (
                "and",
                "or",
                "not",
                "true",
                "false",
                "null",
                "none",
            ):
                continue
            value = self._get_nested_value(merged, field)
            if value is not None:
                inputs[field] = value

        return inputs

    def _determine_decision(self, context: ExecutionContext) -> str | None:
        """Determine the final decision from execution context."""
        eligible = context.computed_metrics.get("eligible")
        if eligible is False:
            return "REJECT"

        critical_alerts = [a for a in context.alerts if a.level == "critical"]
        if critical_alerts:
            return "REVIEW"

        if eligible is True and not critical_alerts:
            credit_score = context.computed_metrics.get("credit_score", 0)
            guarantee_depth = context.computed_metrics.get(
                "guarantee_chain_depth", 0
            )

            if credit_score >= 80 and guarantee_depth < 2:
                return "APPROVE"
            elif credit_score >= 60:
                return "APPROVE_WITH_CONDITIONS"
            else:
                return "APPROVE_RESTRICTED"

        # Check for generate_decision output
        final_decision = context.computed_metrics.get("final_decision")
        if final_decision:
            return final_decision

        return None

    def _generate_reasoning(self, context: ExecutionContext) -> str | None:
        """Generate decision reasoning from execution context."""
        eligible = context.computed_metrics.get("eligible")
        if eligible is False:
            reason = context.computed_metrics.get(
                "rejection_reason", "不符合基础准入条件"
            )
            return f"拒绝: {reason}"

        critical_alerts = [a for a in context.alerts if a.level == "critical"]
        if critical_alerts:
            alert_types = ", ".join(a.type for a in critical_alerts)
            return f"需人工审核: 检测到关键预警 ({alert_types})"

        credit_score = context.computed_metrics.get("credit_score", 0)
        guarantee_depth = context.computed_metrics.get("guarantee_chain_depth", 0)

        if eligible is True and not critical_alerts:
            if credit_score >= 80 and guarantee_depth < 2:
                return "信用评分优秀，担保链风险低，建议批准"
            elif credit_score >= 60:
                return "信用评分可接受，需追加担保"
            else:
                return "信用评分低于推荐阈值，限制性批准"

        return None

    def _generate_step_explanation(
        self,
        rule: RuleDefinition,
        condition_result: bool | None,
        rule_result: Any,
    ) -> str:
        """Generate a natural language explanation for a rule step."""
        rule_label = rule.name or rule.id

        if condition_result is None:
            # No condition (always executes)
            return f"执行{rule_label}（无条件）"

        if condition_result:
            # Condition met
            if rule_result and hasattr(rule_result, "passed") and rule_result.passed:
                action = rule.then.action if rule.then else ""
                if action == "approve_eligibility":
                    return f"{rule_label}: 条件满足，通过准入检查"
                elif action == "calculate_credit_score":
                    score = (
                        rule_result.output.get("credit_score", "")
                        if rule_result
                        else ""
                    )
                    return f"{rule_label}: 计算信用评分为 {score}"
                elif action == "calculate_credit_limit":
                    limit = (
                        rule_result.output.get("credit_limit", "")
                        if rule_result
                        else ""
                    )
                    return f"{rule_label}: 计算授信额度为 {limit}"
                elif action == "trigger_alert":
                    return f"{rule_label}: 触发预警"
                elif action == "determine_interest_rate":
                    rate = (
                        rule_result.output.get("interest_rate", "")
                        if rule_result
                        else ""
                    )
                    return f"{rule_label}: 确定利率为 {rate}%"
                elif action == "generate_decision":
                    decision = (
                        rule_result.output.get("final_decision", "")
                        if rule_result
                        else ""
                    )
                    return f"{rule_label}: 生成决策 {decision}"
                else:
                    return f"{rule_label}: 条件满足，执行动作 {action}"
            else:
                return f"{rule_label}: 条件满足"
        else:
            # Condition not met
            if rule.else_:
                else_action = rule.else_.get("action", "")
                if else_action == "reject_eligibility":
                    return f"{rule_label}: 条件不满足，拒绝准入"
                return f"{rule_label}: 条件不满足，执行else分支 {else_action}"
            return f"{rule_label}: 条件不满足，跳过"

    def _get_affected_metrics(
        self,
        context_before: dict[str, Any],
        context_after: dict[str, Any],
    ) -> list[str]:
        """Get metrics that changed between before and after snapshots."""
        before_metrics = context_before.get("computed_metrics", {})
        after_metrics = context_after.get("computed_metrics", {})

        affected: list[str] = []
        all_keys = set(list(before_metrics.keys()) + list(after_metrics.keys()))
        for key in all_keys:
            if before_metrics.get(key) != after_metrics.get(key):
                affected.append(key)
        return affected

    def _build_comparison(
        self,
        baseline: SimulationResult,
        simulated: SimulationResult,
    ) -> ComparisonResult:
        """Build comparison result between baseline and simulation."""
        baseline_outputs = baseline.final_outputs
        simulated_outputs = simulated.final_outputs

        # Compute diffs
        diffs = self.impact_analyzer.compute_diffs(baseline_outputs, simulated_outputs)

        # Trace impact chains
        changed_fields = [
            d.field for d in diffs if d.change_type != "unchanged"
        ]
        impact_chains = self.impact_analyzer.analyze_impact(changed_fields)

        return ComparisonResult(
            baseline=baseline_outputs,
            simulated=simulated_outputs,
            diffs=diffs,
            impact_chains=impact_chains,
        )

    def _apply_overrides(
        self,
        entity_data: dict[str, Any],
        overrides: dict[str, Any],
    ) -> None:
        """Apply override values to entity data.

        Supports nested paths like "registered_capital.value".
        """
        for key, value in overrides.items():
            if "." in key:
                # Nested path
                parts = key.split(".")
                target = entity_data
                for part in parts[:-1]:
                    if part not in target or not isinstance(target[part], dict):
                        target[part] = {}
                    target = target[part]
                target[parts[-1]] = value
            else:
                entity_data[key] = value

    def _serialize_condition(self, when: Any) -> str:
        """Serialize a RuleWhen to string expression."""
        if when is None:
            return ""
        if hasattr(when, "expression") and when.expression:
            return when.expression
        if hasattr(when, "allOf") and when.allOf:
            parts = []
            for cond in when.allOf:
                if isinstance(cond, dict) and "expression" in cond:
                    parts.append(cond["expression"])
            return " AND ".join(parts)
        if hasattr(when, "anyOf") and when.anyOf:
            parts = []
            for cond in when.anyOf:
                if isinstance(cond, dict) and "expression" in cond:
                    parts.append(cond["expression"])
            return " OR ".join(parts)
        return ""

    async def _find_entity(self, entity_id: str) -> Any:
        """Find entity by ID, trying common concept types."""
        concept_types = [
            "Supplier",
            "Invoice",
            "Contract",
            "Enterprise",
            "Company",
        ]

        for concept in concept_types:
            entity = await self.storage.get_entity(concept, entity_id)
            if entity:
                return entity

        # Try querying all entities
        try:
            entities = await self.storage.query_entities(
                concept=None, filters=None
            )
            for entity in entities:
                if entity.entity_id == entity_id:
                    return entity
        except Exception:
            pass

        return None

    @staticmethod
    def _get_nested_value(data: dict[str, Any], path: str) -> Any:
        """Get nested value from dict using dot notation."""
        keys = path.split(".")
        value: Any = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value


class JSONSafeEncoder(json.JSONEncoder):
    """JSON encoder that handles common non-serializable types."""

    def default(self, obj: Any) -> Any:
        # Handle datetime
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        # Handle Decimal
        if isinstance(obj, Decimal):
            return float(obj)
        # Handle float nan/inf
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        # Handle bytes
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        # Handle sets - convert to list
        if isinstance(obj, set):
            return list(obj)
        # For any other type, convert to string
        try:
            return str(obj)
        except Exception:
            return repr(obj)


def convert_to_json_safe(obj: Any) -> Any:
    """Convert an object to JSON-safe types.

    Uses JSON encoder/decoder round-trip to ensure all types are serializable.
    """
    try:
        # Use JSON round-trip to convert all types
        return json.loads(json.dumps(obj, cls=JSONSafeEncoder))
    except (TypeError, ValueError) as e:
        # If JSON conversion fails, try to convert to string
        try:
            return str(obj)
        except Exception:
            return repr(obj)


def dataclasses_asdict(obj: Any) -> Any:
    """Convert dataclasses to dicts for JSON serialization.

    Uses standard library asdict with custom conversion for JSON safety.
    """
    if obj is None:
        return None

    # Handle primitive types
    if isinstance(obj, (str, int, bool)):
        return obj

    # Handle float specially for nan/inf
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj

    # Handle datetime
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    # Handle Decimal
    if isinstance(obj, Decimal):
        return float(obj)

    # Handle collections
    if isinstance(obj, list):
        return [dataclasses_asdict(item) for item in obj]

    if isinstance(obj, tuple):
        return [dataclasses_asdict(item) for item in obj]

    if isinstance(obj, set):
        return [dataclasses_asdict(item) for item in obj]

    if isinstance(obj, dict):
        return {str(k): dataclasses_asdict(v) for k, v in obj.items()}

    # Handle dataclasses using standard library
    if is_dataclass(obj) and not isinstance(obj, type):
        try:
            # Use standard asdict then convert to JSON-safe
            d = asdict(obj)
            return dataclasses_asdict(d)
        except (TypeError, ValueError, RecursionError):
            # Fallback: convert to string representation
            return str(obj)

    # For any other type
    try:
        return str(obj)
    except Exception:
        return repr(obj)
