"""Rule executor for KGML rules."""
from __future__ import annotations
from typing import TYPE_CHECKING
from ontology_engine.core.schema.models import KGMLSchema, RuleDefinition
from ontology_engine.engine.rule.models import (
    ExecutionContext,
    RuleResult,
    Alert,
    AnalysisResult,
)
from ontology_engine.engine.rule.evaluator import ExpressionEvaluator


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

    def __init__(self, schema: KGMLSchema):
        self.schema = schema
        self.evaluator = ExpressionEvaluator()

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
                    output = self._execute_then_action(rule, context)
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
                        output = self._execute_action(else_action, else_output, context, rule.id)
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

    def _execute_action(
        self,
        action: str | None,
        output: dict,
        context: ExecutionContext,
        rule_id: str | None = None
    ) -> dict:
        """Execute rule action and return output."""
        eval_context = self._get_eval_context(context)

        if output is None:
            output = {}

        # If action is None (computation-only rule), skip action handling
        if action is None:
            return output

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
            alert = Alert(
                level=alert_level,
                type=output.get("alert_type", "general"),
                message=output.get("message", ""),
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
            output["credit_limit"] = credit_limit
            output["level"] = credit_grade
            context.computed_metrics["credit_limit"] = credit_limit

        elif action == ACTION_DETERMINE_INTEREST_RATE:
            credit_score = context.computed_metrics.get("credit_score", 50)
            risk_premium = (100 - credit_score) / 100 * BASE_INTEREST_RATE
            rate = (BASE_INTEREST_RATE + risk_premium) * 100
            output["interest_rate"] = rate
            context.computed_metrics["interest_rate"] = rate

        elif action == ACTION_GENERATE_DECISION:
            # Decision is generated in execute_dimension, this is a no-op here
            pass

        return output

    def _execute_then_action(
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
        return self._execute_action(action, output, context, rule.id)

    def _calculate_credit_score(self, context: ExecutionContext) -> int:
        """Calculate credit score based on available metrics."""
        score = CREDIT_SCORE_BASE

        eval_context = self._get_eval_context(context)

        # Check for overdue invoices
        overdue_ratio = eval_context.get("overdue_invoice_ratio", 0)
        if overdue_ratio < CREDIT_SCORE_OVERDUE_RATIO_LOW:
            score += CREDIT_SCORE_BONUS_LOW
        elif overdue_ratio < CREDIT_SCORE_OVERDUE_RATIO_MED:
            score += CREDIT_SCORE_BONUS_MED

        # Check for alerts
        if any(a.level == "critical" for a in context.alerts):
            score = max(CREDIT_SCORE_CRITICAL_MIN, score - CREDIT_SCORE_CRITICAL_PENALTY)

        return min(CREDIT_SCORE_MAX, max(CREDIT_SCORE_MIN, score))

    def _get_credit_grade(self, score: int) -> str:
        """Get credit grade from score using threshold table."""
        for threshold, grade in CREDIT_GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return CREDIT_GRADE_DEFAULT

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
