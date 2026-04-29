"""Rule executor for KGML rules."""
from __future__ import annotations

from typing import Any, cast

from ontology_engine.core.schema.models import KGMLSchema, RuleDefinition, ActionType
from ontology_engine.engine.rule.models import (
    ExecutionContext,
    RuleResult,
    Alert,
    AnalysisResult,
    RuleGroupDefinition,
    RuleStep,
    ActionClause,
    ConditionClause,
    StructuredActionClause,
    RuleDefinitionDecl,
    RuleLogicDecl,
)
from ontology_engine.engine.rule.evaluator import ExpressionEvaluator

# Import operators to register them
from ontology_engine.engine.rule.operators import OperatorRegistry

# Import DAG components for execute_rule_group
from ontology_engine.engine.rule.dag_builder import DAGBuilder
from ontology_engine.engine.rule.dag_executor import DAGExecutor


class RuleExecutor:
    """Executes KGML rules against entities."""

    def __init__(self, schema: KGMLSchema, metric_engine: Any = None):
        self.schema = schema
        self.evaluator = ExpressionEvaluator()
        self._metric_engine = metric_engine

    def _get_eval_context(self, context: ExecutionContext) -> dict:
        """Get evaluation context combining entity_data and computed_metrics."""
        eval_context = dict(context.entity_data)
        eval_context.update(context.computed_metrics)
        return eval_context

    def get_eval_context(self, context: ExecutionContext) -> dict:
        """Public interface for _get_eval_context.

        Used by visualization and simulation modules that need
        to evaluate conditions against the current execution context.
        """
        return self._get_eval_context(context)

    async def execute_rule(
        self,
        rule: RuleDefinition,
        context: ExecutionContext
    ) -> RuleResult:
        """Execute a single rule."""
        try:
            condition_met = True

            # Check if rule has a when condition
            if rule.when:
                eval_context = self._get_eval_context(context)
                condition_met = self.evaluator.evaluate(rule.when, eval_context)

            if condition_met:
                # Execute the then action
                if rule.then:
                    output = await self._execute_then_action(rule, context)
                    return RuleResult(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        passed=True,
                        output=output
                    )
            else:
                # Execute the else action if condition is not met
                if rule.else_:
                    else_action = rule.else_.get("action")
                    else_output = rule.else_.get("output", {})
                    if else_action:
                        output = await self._execute_action(else_action, else_output, context, rule.id)
                        return RuleResult(
                            rule_id=rule.id,
                            rule_name=rule.name,
                            passed=False,
                            output=output
                        )

                return RuleResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    passed=False,
                    output={"skipped": "condition not met"}
                )

            return RuleResult(
                rule_id=rule.id,
                rule_name=rule.name,
                passed=True,
                output={}
            )

        except Exception as e:
            return RuleResult(
                rule_id=rule.id,
                rule_name=rule.name,
                passed=False,
                error=str(e)
            )

    async def _execute_action(
        self,
        action: str | None,
        output: dict,
        context: ExecutionContext,
        rule_id: str | None = None
    ) -> dict:
        """Execute rule action using OperatorRegistry.

        First tries to use OperatorRegistry for new-style operators.
        Falls back to legacy action constants for backward compatibility.
        """
        if output is None:
            output = {}

        # If action is None (computation-only rule), skip action handling
        if action is None:
            return output

        # Try to use OperatorRegistry
        try:
            operator = OperatorRegistry.get(action)
            # Build context dict for operator
            eval_context = self._get_eval_context(context)
            op_context = {
                **eval_context,
                "entity_id": context.entity_id,
                "dimension": context.dimension,
                "computed_metrics": context.computed_metrics,
                "alerts": [{"level": a.level, "type": a.type, "message": a.message} for a in context.alerts],
            }
            result = await operator.execute(output.copy(), {}, op_context)

            # Update context with computed metrics
            for key, value in result.items():
                if key not in ("error", "alert_triggered"):
                    context.computed_metrics[key] = value

            # Handle alert triggering
            if result.get("alert_triggered"):
                alert = Alert(
                    level=str(result.get("level", "WARNING")),
                    type=str(result.get("type", "general")),
                    message=str(result.get("message", "")),
                    data=result.get("data", {}),
                )
                context.alerts.append(alert)

            return result

        except KeyError:
            raise ValueError(f"Unknown operator: {action}. Register it in OperatorRegistry first.")

    async def _execute_then_action(
        self,
        rule: RuleDefinition,
        context: ExecutionContext
    ) -> dict:
        """Execute rule's then action with computation support."""
        then_clause = rule.then
        assert then_clause is not None, "rule.then should not be None when _execute_then_action is called"
        action = then_clause.action
        output = then_clause.output.copy() if then_clause.output else {}

        eval_context = self._get_eval_context(context)

        if then_clause.computation:
            # Handle formula-based computation
            formula = then_clause.computation.get("formula")
            if formula:
                result = self.evaluator.evaluate(formula, eval_context)
                output["computed_value"] = result
                # Store computed value in context
                if rule.id:
                    context.computed_metrics[f"{rule.id}_result"] = result

        # Delegate to _execute_action for the actual action handling
        return await self._execute_action(action, output, context, rule.id)

    async def execute_rule_group(
        self,
        rule_group: "RuleGroupDefinition",
        steps: list["RuleStep"],
        context: ExecutionContext,
    ) -> AnalysisResult:
        """Execute rules using DAG topology (new) or priority (legacy).

        When RuleSteps have depends_on declarations, use DAGExecutor for
        topological execution. Otherwise, fall back to priority-based
        execution for backward compatibility.

        Args:
            rule_group: The rule group definition containing metadata.
            steps: List of RuleSteps to execute.
            context: The ExecutionContext for rule execution.

        Returns:
            AnalysisResult with all rule results and computed metrics.
        """
        # Check if any step has dependencies
        has_dependencies = any(len(step.depends_on) > 0 for step in steps)

        if has_dependencies:
            # Use DAG execution for steps with dependencies
            builder = DAGBuilder()
            dag = builder.build(steps)

            executor = DAGExecutor()

            result = await executor.execute(dag, context)

            # Convert StepResult -> RuleResult
            rule_results = []
            for step in steps:
                step_result = result.results.get(step.id)
                if step_result:
                    rule_results.append(RuleResult(
                        rule_id=step.id,
                        rule_name=step.name,
                        passed=(
                            not step_result.skipped
                            and not step_result.rejected
                            and step_result.error is None
                        ),
                        output=step_result.output or {},
                        error=step_result.error,
                    ))
                else:
                    # Step was not executed (shouldn't happen in normal flow)
                    rule_results.append(RuleResult(
                        rule_id=step.id,
                        rule_name=step.name,
                        passed=False,
                        output={},
                        error=f"Step '{step.id}' was not executed",
                    ))

            return AnalysisResult(
                entity_id=context.entity_id,
                dimension=context.dimension,
                rule_results=rule_results,
                computed_metrics=context.computed_metrics,
                alerts=context.alerts,
                decision=context.computed_metrics.get("final_decision"),
                decision_reasoning=context.computed_metrics.get("decision_reasoning"),
            )
        else:
            # Fall back to priority-based execution (backward compatibility)
            return await self._execute_with_priority(rule_group, steps, context)

    async def _execute_with_priority(
        self,
        rule_group: "RuleGroupDefinition",
        steps: list["RuleStep"],
        context: ExecutionContext,
    ) -> AnalysisResult:
        """Execute steps sorted by priority (legacy mode).

        Args:
            rule_group: The rule group definition.
            steps: List of RuleSteps to execute.
            context: The ExecutionContext for rule execution.

        Returns:
            AnalysisResult with all rule results and computed metrics.
        """
        # Sort by priority and order
        sorted_steps = sorted(steps, key=lambda s: (-s.order, -rule_group.priority))

        for step in sorted_steps:
            if not step.enabled:
                continue

            # Evaluate condition
            condition_passed = await self._evaluate_step_condition(step, context)

            if condition_passed:
                # Execute then clause
                output = await self._execute_step_action(step.then, context)
                rule_result = RuleResult(
                    rule_id=step.id,
                    rule_name=step.name,
                    passed=True,
                    output=output,
                )
            else:
                # Execute else clause if condition is false
                if step.else_:
                    output = await self._execute_step_action(step.else_, context)
                    rule_result = RuleResult(
                        rule_id=step.id,
                        rule_name=step.name,
                        passed=False,
                        output=output,
                    )
                else:
                    rule_result = RuleResult(
                        rule_id=step.id,
                        rule_name=step.name,
                        passed=False,
                        output={"skipped": "condition not met"},
                    )

            context.rule_results.append(rule_result)

            # Check if step output indicates rejection
            if rule_result.output.get("_rejected") or rule_result.output.get("rejected") or rule_result.output.get("eligible") is False:
                # Early termination on rejection
                break

        return AnalysisResult(
            entity_id=context.entity_id,
            dimension=context.dimension,
            rule_results=context.rule_results,
            computed_metrics=context.computed_metrics,
            alerts=context.alerts,
            decision=context.computed_metrics.get("final_decision"),
            decision_reasoning=context.computed_metrics.get("decision_reasoning"),
        )

    async def _evaluate_step_condition(
        self,
        step: "RuleStep",
        context: ExecutionContext,
    ) -> bool:
        """Evaluate a RuleStep's when condition.

        Args:
            step: The RuleStep to evaluate.
            context: The ExecutionContext.

        Returns:
            True if condition passes or has no condition, False otherwise.
        """
        when = step.when
        if not when:
            return True

        if when.type == "expression":
            if not when.expression:
                return True
            eval_context = self._get_eval_context(context)
            try:
                return bool(self.evaluator.evaluate(when.expression, eval_context))
            except Exception:
                return False

        elif when.type == "all_of":
            for sub_expr in when.sub_conditions:
                eval_context = self._get_eval_context(context)
                try:
                    if not bool(self.evaluator.evaluate(sub_expr, eval_context)):
                        return False
                except Exception:
                    return False
            return True

        elif when.type == "any_of":
            for sub_expr in when.sub_conditions:
                eval_context = self._get_eval_context(context)
                try:
                    if bool(self.evaluator.evaluate(sub_expr, eval_context)):
                        return True
                except Exception:
                    continue
            return False

        return True

    async def _execute_step_action(
        self,
        action: "ActionClause",
        context: ExecutionContext,
    ) -> dict:
        """Execute a RuleStep's action clause.

        Args:
            action: The ActionClause to execute.
            context: The ExecutionContext.

        Returns:
            Output dict from the operator execution.
        """
        operator_name = action.operator

        # Build context for operator
        eval_context = self._get_eval_context(context)
        operator_context = {
            **eval_context,
            "entity_id": context.entity_id,
            "dimension": context.dimension,
            "entity_data": context.entity_data,
            "computed_metrics": context.computed_metrics,
            "flags": context.flags,
            "alerts": [a.__dict__ for a in context.alerts],
            "categories": context.categories,
        }

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
        for key, value in output.items():
            if key not in ("error", "alert_triggered", "alerts"):
                if isinstance(value, bool):
                    context.flags[key] = value
                else:
                    context.computed_metrics[key] = value

        # Handle alert triggering
        if output.get("alert_triggered"):
            alert = Alert(
                level=str(output.get("level", "WARNING")),
                type=str(output.get("type", "general")),
                message=str(output.get("message", "")),
                data=cast(dict[str, Any] | None, output.get("data")),
            )
            context.alerts.append(alert)

        return output

    async def execute_dimension(
        self,
        dimension: str,
        entity_id: str,
        entity_data: dict
    ) -> AnalysisResult:
        """Execute all rules for a dimension on an entity."""
        context = ExecutionContext(
            entity_id=entity_id,
            dimension=dimension,
            entity_data=entity_data
        )

        # Get rules for this dimension
        rules = self.schema.get_rules_for_dimension(dimension) if self.schema.rules else []

        # Sort by priority
        rules = sorted(rules, key=lambda r: -r.priority)  # Descending: higher priority first

        # Execute each rule
        for rule in rules:
            if not rule.enabled:
                continue

            # Check if rule applies to this entity type
            entity_type = entity_data.get("_concept", "")
            if rule.scope and entity_type:
                entity_types = rule.scope.get("entity_types", [])
                if entity_types and entity_type not in entity_types:
                    continue

            result = await self.execute_rule(rule, context)
            context.rule_results.append(result)

        # Determine overall decision
        decision = None
        reasoning = None

        eligible = context.computed_metrics.get("eligible")
        if eligible is False:
            decision = "REJECT"
            reasoning = context.computed_metrics.get("rejection_reason", "Did not meet eligibility criteria")

        critical_alerts = [a for a in context.alerts if a.level == "critical"]
        if critical_alerts:
            decision = "REJECT" if decision else "REVIEW"
            reasoning = f"Critical alerts: {', '.join(a.type for a in critical_alerts)}"

        if eligible is True and not critical_alerts:
            credit_score = context.computed_metrics.get("credit_score", 0)
            guarantee_chain_depth = context.computed_metrics.get("guarantee_chain_depth", 0)

            if credit_score >= 80 and guarantee_chain_depth < 2:
                decision = "APPROVE"
                reasoning = "Credit score excellent, minimal guarantee chain risk"
            elif credit_score >= 60:
                decision = "APPROVE_WITH_CONDITIONS"
                reasoning = "Credit score acceptable but requires guarantee"
            else:
                decision = "APPROVE_RESTRICTED"
                reasoning = "Credit score below recommended threshold"

        return AnalysisResult(
            entity_id=entity_id,
            dimension=dimension,
            rule_results=context.rule_results,
            computed_metrics=context.computed_metrics,
            alerts=context.alerts,
            decision=decision,
            decision_reasoning=reasoning
        )

    # ============== V3 Execution Methods (RFC-018 / RFC-019) ==============

    async def execute_v3(
        self,
        definition: RuleDefinitionDecl,
        logic: RuleLogicDecl,
        context: ExecutionContext,
    ) -> AnalysisResult:
        """Execute rules using V3 models (RuleDefinitionDecl + RuleLogicDecl).

        This is the new execution path that uses StructuredActionClause
        with ActionType enum for type-safe dispatch.
        """
        sorted_steps = sorted(logic.steps, key=lambda s: -s.priority)

        for step in sorted_steps:
            if not step.enabled:
                continue

            condition_passed = await self._evaluate_v3_condition(step.condition, context)

            if condition_passed:
                output = await self._execute_structured_action(step.action, context)
                rule_result = RuleResult(
                    rule_id=step.id,
                    rule_name=step.name,
                    passed=True,
                    output=output,
                )
            else:
                if step.else_action:
                    output = await self._execute_structured_action(step.else_action, context)
                    rule_result = RuleResult(
                        rule_id=step.id,
                        rule_name=step.name,
                        passed=False,
                        output=output,
                    )
                else:
                    rule_result = RuleResult(
                        rule_id=step.id,
                        rule_name=step.name,
                        passed=False,
                        output={"skipped": "condition not met"},
                    )

            context.rule_results.append(rule_result)

            if rule_result.output.get("_rejected") or rule_result.output.get("eligible") is False:
                break

        return AnalysisResult(
            entity_id=context.entity_id,
            dimension=context.dimension,
            rule_results=context.rule_results,
            computed_metrics=context.computed_metrics,
            alerts=context.alerts,
            decision=context.computed_metrics.get("final_decision"),
            decision_reasoning=context.computed_metrics.get("decision_reasoning"),
        )

    async def _evaluate_v3_condition(
        self,
        condition: ConditionClause | None,
        context: ExecutionContext,
    ) -> bool:
        """Evaluate a V3 step condition."""
        if condition is None:
            return True

        from ontology_engine.engine.rule.models import ConditionClause
        if isinstance(condition, ConditionClause):
            if condition.type == "expression" and condition.expression:
                try:
                    eval_context = self._get_eval_context(context)
                    result = self.evaluator.evaluate(condition.expression, eval_context)
                    return bool(result)
                except Exception:
                    return False
            elif condition.type in ("all_of", "any_of") and condition.sub_conditions:
                results = []
                for sub in condition.sub_conditions:
                    if isinstance(sub, str):
                        try:
                            eval_context = self._get_eval_context(context)
                            results.append(bool(self.evaluator.evaluate(sub, eval_context)))
                        except Exception:
                            results.append(False)
                    elif isinstance(sub, dict):
                        expr = sub.get("expression", "")
                        try:
                            eval_context = self._get_eval_context(context)
                            results.append(bool(self.evaluator.evaluate(expr, eval_context)))
                        except Exception:
                            results.append(False)
                if condition.type == "all_of":
                    return all(results)
                else:
                    return any(results)

        return True

    async def _execute_structured_action(
        self,
        action: StructuredActionClause | None,
        context: ExecutionContext,
    ) -> dict[str, Any]:
        """Execute a StructuredActionClause using match action.type dispatch (RFC-019).

        This replaces _execute_action (str+dict) and _execute_step_action (ActionClause)
        with a unified, type-safe dispatch based on ActionType enum.
        """
        if action is None:
            return {}

        eval_context = self._get_eval_context(context)

        match action.type:
            case ActionType.SET_FLAG:
                flag_name = action.flag if action.flag is not None else "default_flag"
                flag_value = action.value if action.value is not None else True
                context.flags[flag_name] = flag_value
                context.computed_metrics[flag_name] = flag_value
                return {flag_name: flag_value}

            case ActionType.COMPUTE:
                if action.operator:
                    try:
                        operator = OperatorRegistry.get(action.operator.value)
                        operator_context = {
                            **eval_context,
                            "entity_id": context.entity_id,
                            "dimension": context.dimension,
                            "entity_data": context.entity_data,
                            "computed_metrics": context.computed_metrics,
                            "flags": context.flags,
                            "categories": context.categories,
                        }
                        output = await operator.execute(
                            inputs=action.params,
                            config={},
                            context=operator_context,
                        )
                    except Exception as e:
                        output = {"error": str(e)}
                elif action.formula:
                    try:
                        result = self.evaluator.evaluate(action.formula, eval_context)
                        output = {action.output or "result": result}
                    except Exception as e:
                        output = {"error": str(e)}
                else:
                    output = {}

                if action.output_mapping:
                    mapped = {}
                    for target_key, source_key in action.output_mapping.items():
                        mapped[target_key] = output.get(source_key, output.get(target_key))
                    output = mapped

                for key, value in output.items():
                    if key not in ("error", "alert_triggered", "alerts"):
                        if isinstance(value, bool):
                            context.flags[key] = value
                        else:
                            context.computed_metrics[key] = value

                if output.get("alert_triggered"):
                    alert = Alert(
                        level=str(output.get("level", "WARNING")),
                        type=str(output.get("type", "general")),
                        message=str(output.get("message", "")),
                        data=cast(dict[str, Any] | None, output.get("data")),
                    )
                    context.alerts.append(alert)

                return output

            case ActionType.REJECT:
                context.flags["rejected"] = True
                context.computed_metrics["rejected"] = True
                result: dict[str, Any] = {"_rejected": True}
                if action.reason:
                    result["reason"] = action.reason
                    context.computed_metrics["rejection_reason"] = action.reason
                return result

            case ActionType.EMIT_ALERT:
                alert = Alert(
                    level=action.severity or "WARNING",
                    type="general",
                    message=action.reason or "",
                    data={},
                )
                context.alerts.append(alert)
                return {"_alert": {"severity": action.severity or "WARNING", "reason": action.reason or ""}}

            case ActionType.ASSIGN_CATEGORY:
                if action.category:
                    context.categories[action.category] = action.category
                    context.computed_metrics["assigned_category"] = action.category
                return {"_category": action.category}

            case _:
                raise ValueError(f"Unknown ActionType: {action.type}")
