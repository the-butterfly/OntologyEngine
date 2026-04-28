"""Rule executor for KGML rules."""
from __future__ import annotations

from typing import Any

from ontology_engine.core.schema.models import KGMLSchema, RuleDefinition
from ontology_engine.engine.rule.models import (
    ExecutionContext,
    RuleResult,
    Alert,
    AnalysisResult,
    RuleGroupDefinition,
    RuleStep,
    ActionClause,
)
from ontology_engine.engine.rule.evaluator import ExpressionEvaluator

# Import operators to register them
from ontology_engine.engine.rule.operators import OperatorRegistry

# Import DAG components for execute_rule_group
from ontology_engine.engine.rule.dag_builder import DAGBuilder
from ontology_engine.engine.rule.dag_executor import DAGExecutor


# Action type constants
ACTION_APPROVE_ELIGIBILITY = "approve_eligibility"
ACTION_REJECT_ELIGIBILITY = "reject_eligibility"
ACTION_TRIGGER_ALERT = "trigger_alert"
ACTION_CALCULATE_CREDIT_SCORE = "calculate_credit_score"
ACTION_CALCULATE_CREDIT_LIMIT = "calculate_credit_limit"
ACTION_DETERMINE_INTEREST_RATE = "determine_interest_rate"
ACTION_GENERATE_DECISION = "generate_decision"

# Credit grade thresholds (score -> grade), sorted descending by score
CREDIT_GRADE_THRESHOLDS = [
    (90, "AAA"),
    (85, "AA"),
    (80, "A"),
    (70, "BBB"),
    (60, "BB"),
    (50, "B"),
    (40, "CCC"),
    (30, "CC"),
    (20, "C"),
]
CREDIT_GRADE_DEFAULT = "D"

# Credit grade multipliers for limit calculation
CREDIT_GRADE_MULTIPLIERS = {
    "AAA": 2.0,
    "AA": 1.8,
    "A": 1.5,
    "BBB": 1.2,
    "BB": 1.0,
    "B": 0.8,
}
CREDIT_GRADE_MULTIPLIER_DEFAULT = 0.5

# Interest rate constants
BASE_INTEREST_RATE = 0.05

# Credit score calculation constants
CREDIT_SCORE_BASE = 50
CREDIT_SCORE_OVERDUE_RATIO_LOW = 5
CREDIT_SCORE_OVERDUE_RATIO_MED = 10
CREDIT_SCORE_BONUS_LOW = 15
CREDIT_SCORE_BONUS_MED = 5
CREDIT_SCORE_CRITICAL_PENALTY = 30
CREDIT_SCORE_CRITICAL_MIN = 20
CREDIT_SCORE_MAX = 100
CREDIT_SCORE_MIN = 0

# Credit limit calculation constants
CREDIT_LIMIT_BASE_RATIO = 0.5
GUARANTEE_CHAIN_PENALTY_RATE = 0.1

# Approval decision thresholds
APPROVAL_SCORE_EXCELLENT = 80
APPROVAL_SCORE_ACCEPTABLE = 60
GUARANTEE_CHAIN_DEPTH_WARNING = 2

# Decision constants
DECISION_REJECT = "REJECT"
DECISION_REVIEW = "REVIEW"
DECISION_APPROVE = "APPROVE"
DECISION_APPROVE_WITH_CONDITIONS = "APPROVE_WITH_CONDITIONS"
DECISION_APPROVE_RESTRICTED = "APPROVE_RESTRICTED"


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
                    level=result.get("level", "info"),
                    type=result.get("type", "general"),
                    message=result.get("message", ""),
                    data=result.get("data", {})
                )
                context.alerts.append(alert)

            return result

        except KeyError:
            # Fall back to legacy action handling for backward compatibility
            return self._execute_legacy_action(action, output, context)

    def _execute_legacy_action(
        self,
        action: str | None,
        output: dict,
        context: ExecutionContext,
    ) -> dict:
        """Handle legacy action constants for backward compatibility.

        This method handles the original hardcoded action types
        (ACTION_APPROVE_ELIGIBILITY, ACTION_REJECT_ELIGIBILITY, etc.)
        """
        eval_context = self._get_eval_context(context)

        # Handle special actions
        if action == ACTION_APPROVE_ELIGIBILITY:
            output["eligible"] = True
            context.computed_metrics["eligible"] = True

        elif action == ACTION_REJECT_ELIGIBILITY:
            output["eligible"] = False
            context.computed_metrics["eligible"] = False
            output["rejection_reason"] = output.get("rejection_reason", "Did not meet eligibility criteria")

        elif action == ACTION_TRIGGER_ALERT and output:
            alert_level = output.get("alert_level", "warning")
            message = output.get("message", "")
            message_template = output.get("message_template")
            if message_template:
                try:
                    message = message_template.format(**eval_context)
                except (KeyError, ValueError):
                    message = message_template
            alert = Alert(
                level=alert_level,
                type=output.get("alert_type", "general"),
                message=message,
                data=output
            )
            context.alerts.append(alert)

        elif action == ACTION_CALCULATE_CREDIT_SCORE:
            score = self._calculate_credit_score(context)
            output["credit_score"] = score
            context.computed_metrics["credit_score"] = score

            grade = self._get_credit_grade(score)
            output["credit_grade"] = grade
            context.computed_metrics["credit_grade"] = grade

        elif action == ACTION_CALCULATE_CREDIT_LIMIT:
            credit_score = context.computed_metrics.get("credit_score", CREDIT_SCORE_BASE)
            credit_grade = context.computed_metrics.get("credit_grade", "B")
            registered_capital = eval_context.get("registered_capital", {}).get("value", 0) if isinstance(eval_context.get("registered_capital"), dict) else 0
            guarantee_chain_depth = context.computed_metrics.get("guarantee_chain_depth", 0)

            base = registered_capital * CREDIT_LIMIT_BASE_RATIO
            multiplier = CREDIT_GRADE_MULTIPLIERS.get(credit_grade, CREDIT_GRADE_MULTIPLIER_DEFAULT)

            if guarantee_chain_depth > 0:
                multiplier = multiplier * (1 - guarantee_chain_depth * GUARANTEE_CHAIN_PENALTY_RATE)

            credit_limit = base * multiplier
            output["credit_limit"] = round(credit_limit, 2)
            output["level"] = credit_grade
            context.computed_metrics["credit_limit"] = round(credit_limit, 2)

        elif action == ACTION_DETERMINE_INTEREST_RATE:
            credit_score = context.computed_metrics.get("credit_score", 50)
            risk_premium = (100 - credit_score) / 100 * BASE_INTEREST_RATE
            rate = (BASE_INTEREST_RATE + risk_premium) * 100
            output["interest_rate"] = round(rate, 2)
            context.computed_metrics["interest_rate"] = round(rate, 2)

        elif action == ACTION_GENERATE_DECISION:
            # Implement R007 comprehensive credit decision logic
            credit_score = context.computed_metrics.get("credit_score", 0)
            guarantee_chain_depth = context.computed_metrics.get("guarantee_chain_depth", 0)
            registered_capital = eval_context.get("registered_capital", {}).get("value", 0) if isinstance(eval_context.get("registered_capital"), dict) else 0
            
            # R007 rule chain logic
            decision = None
            limit_multiplier = 0.0
            requires_guarantee = True
            reasoning = ""
            
            if credit_score >= 80 and guarantee_chain_depth < 2:
                decision = DECISION_APPROVE
                limit_multiplier = 1.5
                requires_guarantee = False
                reasoning = "Credit score excellent, minimal guarantee chain risk"
            elif credit_score >= 60 and guarantee_chain_depth < 3:
                decision = DECISION_APPROVE_WITH_CONDITIONS
                limit_multiplier = 1.0
                requires_guarantee = True
                reasoning = "Credit score acceptable but requires guarantee"
            elif credit_score >= 40:
                decision = DECISION_APPROVE_RESTRICTED
                limit_multiplier = 0.5
                requires_guarantee = True
                reasoning = "Credit score below recommended threshold"
            else:
                decision = DECISION_REJECT
                limit_multiplier = 0.0
                requires_guarantee = True
                reasoning = "Credit score too low for approval"
            
            # Calculate approved limit
            base_limit = registered_capital * CREDIT_LIMIT_BASE_RATIO
            approved_limit = base_limit * limit_multiplier
            
            output["final_decision"] = decision
            output["approved_credit_limit"] = round(approved_limit, 2)
            output["requires_additional_guarantee"] = requires_guarantee
            output["decision_reasoning"] = reasoning
            
            # Update context
            context.computed_metrics["final_decision"] = decision
            context.computed_metrics["approved_credit_limit"] = approved_limit
            context.computed_metrics["requires_additional_guarantee"] = requires_guarantee

        return output

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

    def _calculate_credit_score(self, context: ExecutionContext) -> int:
        """Calculate credit score based on Schema-defined composite formula.

        Components (from schema.yaml):
        - business_stability_score: 30%
        - tax_compliance_score: 25%
        - network_centrality_score: 15%
        - reputation_score: 15%
        - guarantee_risk_adjustment: 15%
        """
        eval_context = self._get_eval_context(context)

        # Get component scores with defaults
        business_stability = eval_context.get("business_stability_score", 50)
        tax_compliance = eval_context.get("tax_compliance_score", 60)
        network_centrality = eval_context.get("network_centrality_score", 50)
        reputation = eval_context.get("reputation_score", 80)
        guarantee_chain_depth = eval_context.get("guarantee_chain_depth", 0)

        # Calculate guarantee_risk_adjustment (0-100, higher is better)
        if guarantee_chain_depth >= 5:
            guarantee_risk = 20
        elif guarantee_chain_depth >= 3:
            guarantee_risk = 40
        elif guarantee_chain_depth >= 1:
            guarantee_risk = 70
        else:
            guarantee_risk = 100

        # Apply Schema-defined weights
        score = (
            business_stability * 0.30 +
            tax_compliance * 0.25 +
            network_centrality * 0.15 +
            reputation * 0.15 +
            guarantee_risk * 0.15
        )

        # Critical alerts penalty
        if any(a.level == "critical" for a in context.alerts):
            score = max(20, score - 30)

        return int(min(100, max(0, score)))

    def _get_credit_grade(self, score: int) -> str:
        """Get credit grade from score using threshold table."""
        for threshold, grade in CREDIT_GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return CREDIT_GRADE_DEFAULT

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
            if rule_result.output.get("rejected") or rule_result.output.get("eligible") is False:
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
                level=output.get("level", "info"),
                type=output.get("type", "general"),
                message=output.get("message", ""),
                data=output.get("data", {}),
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

        # Check computed eligibility first
        eligible = context.computed_metrics.get("eligible")
        if eligible is False:
            decision = DECISION_REJECT
            reasoning = context.computed_metrics.get("rejection_reason", "Did not meet eligibility criteria")

        # Check for critical alerts
        critical_alerts = [a for a in context.alerts if a.level == "critical"]
        if critical_alerts:
            decision = DECISION_REJECT if decision else DECISION_REVIEW
            reasoning = f"Critical alerts: {', '.join(a.type for a in critical_alerts)}"

        # If eligible and no critical alerts, determine approval level
        if eligible is True and not critical_alerts:
            credit_score = context.computed_metrics.get("credit_score", 0)
            guarantee_chain_depth = context.computed_metrics.get("guarantee_chain_depth", 0)

            if credit_score >= APPROVAL_SCORE_EXCELLENT and guarantee_chain_depth < GUARANTEE_CHAIN_DEPTH_WARNING:
                decision = DECISION_APPROVE
                reasoning = "Credit score excellent, minimal guarantee chain risk"
            elif credit_score >= APPROVAL_SCORE_ACCEPTABLE:
                decision = DECISION_APPROVE_WITH_CONDITIONS
                reasoning = "Credit score acceptable but requires guarantee"
            else:
                decision = DECISION_APPROVE_RESTRICTED
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
