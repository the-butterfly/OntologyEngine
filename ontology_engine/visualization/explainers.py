"""Condition explainer and impact analyzer for execution explainability."""
from __future__ import annotations

import re
from typing import Any

from ontology_engine.core.schema.models import KGMLSchema, RuleWhen
from ontology_engine.engine.rule.evaluator import ExpressionEvaluator
from ontology_engine.visualization.models import (
    ConditionDetail,
    DiffEntry,
    ImpactChain,
)


# ============== Label mappings (shared with builders) ==============

METRIC_LABELS: dict[str, str] = {
    "total_invoice_amount_90d": "近90天发票总额",
    "invoice_count_90d": "近90天发票数",
    "overdue_invoice_amount": "逾期发票金额",
    "total_contract_amount": "合同总金额",
    "avg_monthly_tax_revenue": "月均纳税额",
    "tax_compliance_score": "税务合规评分",
    "negative_news_count_90d": "近90天负面新闻数",
    "core_enterprise_count": "合作核心企业数",
    "overdue_invoice_ratio": "逾期发票占比",
    "avg_invoice_amount": "平均发票金额",
    "contract_utilization_rate": "合同执行率",
    "business_stability_score": "业务稳定性评分",
    "guarantee_chain_depth": "担保链深度",
    "has_guarantee_circle": "是否存在担保圈",
    "network_centrality_score": "网络中心性得分",
    "credit_score": "综合信用评分",
    "reputation_score": "声誉风险评分",
    "guarantee_risk_score": "担保风险评分",
    "credit_grade": "信用等级",
    "eligible": "准入资格",
    "credit_limit": "授信额度",
    "interest_rate": "利率",
    "final_decision": "最终决策",
    "approved_credit_limit": "批准额度",
}

RULE_TYPE_LABELS: dict[str, str] = {
    "constraint": "约束规则",
    "inference": "推理规则",
    "alert": "预警规则",
    "decision": "决策规则",
}


class ConditionExplainer:
    """Decompose condition expressions and generate explanations."""

    def __init__(self, evaluator: ExpressionEvaluator) -> None:
        self.evaluator = evaluator

    def explain(
        self,
        when: RuleWhen | None,
        eval_context: dict[str, Any],
    ) -> list[ConditionDetail]:
        """Decompose a condition into sub-conditions with explanations.

        Example:
            Input:  when.expression = "status == 'ACTIVE' AND credit_score >= 80"
                    eval_context = {"status": "ACTIVE", "credit_score": 92}

            Output: [
                ConditionDetail(
                    expression="status == 'ACTIVE'",
                    resolved="'ACTIVE' == 'ACTIVE'",
                    result=True,
                    explanation="企业状态为活跃(ACTIVE)"
                ),
                ConditionDetail(
                    expression="credit_score >= 80",
                    resolved="92 >= 80",
                    result=True,
                    explanation="综合信用评分(92) >= 80，满足要求"
                ),
            ]
        """
        if when is None:
            return []

        if when.allOf:
            return self._explain_allOf(when.allOf, eval_context)

        if when.anyOf:
            return self._explain_anyOf(when.anyOf, eval_context)

        if when.expression:
            return self._explain_expression(when.expression, eval_context)

        return []

    def _explain_allOf(
        self,
        conditions: list[dict],
        eval_context: dict[str, Any],
    ) -> list[ConditionDetail]:
        """Explain allOf conditions (all must be true)."""
        details: list[ConditionDetail] = []
        for cond in conditions:
            if isinstance(cond, dict) and "expression" in cond:
                details.extend(
                    self._explain_expression(cond["expression"], eval_context)
                )
        return details

    def _explain_anyOf(
        self,
        conditions: list[dict],
        eval_context: dict[str, Any],
    ) -> list[ConditionDetail]:
        """Explain anyOf conditions (at least one must be true)."""
        details: list[ConditionDetail] = []
        for cond in conditions:
            if isinstance(cond, dict) and "expression" in cond:
                sub_details = self._explain_expression(
                    cond["expression"], eval_context
                )
                for d in sub_details:
                    # Mark as anyOf context
                    if not d.result:
                        d.explanation += " (anyOf: 其他条件可能满足)"
                details.extend(sub_details)
        return details

    def _explain_expression(
        self,
        expression: str,
        eval_context: dict[str, Any],
    ) -> list[ConditionDetail]:
        """Split a single expression and explain each sub-condition."""
        sub_exprs = self._split_condition(expression)

        details: list[ConditionDetail] = []
        for sub_expr in sub_exprs:
            sub_expr = sub_expr.strip()
            if not sub_expr:
                continue

            # Resolve variables
            resolved = self._resolve_expression(sub_expr, eval_context)

            # Evaluate
            try:
                result = self.evaluator._evaluate_expression(sub_expr, eval_context)
                if not isinstance(result, bool):
                    result = bool(result)
            except Exception:
                result = False

            # Generate explanation
            explanation = self._generate_explanation(
                sub_expr, resolved, result, eval_context
            )

            details.append(
                ConditionDetail(
                    expression=sub_expr,
                    resolved=resolved,
                    result=result,
                    explanation=explanation,
                )
            )

        return details

    def _split_condition(self, expression: str) -> list[str]:
        """Split expression by AND/OR while respecting string literals."""
        parts: list[str] = []

        # Try AND first
        if " AND " in expression.upper():
            and_parts = self._split_outside_strings(expression, " AND ")
            if len(and_parts) > 1:
                for part in and_parts:
                    parts.extend(self._split_condition(part.strip()))
                return parts

        # Try OR
        if " OR " in expression.upper():
            or_parts = self._split_outside_strings(expression, " OR ")
            if len(or_parts) > 1:
                for part in or_parts:
                    parts.extend(self._split_condition(part.strip()))
                return parts

        # Atomic condition
        return [expression]

    def _split_outside_strings(self, expression: str, delimiter: str) -> list[str]:
        """Split expression by delimiter while respecting string literals."""
        string_ranges = self.evaluator.engine._find_string_ranges(expression)
        parts: list[str] = []
        cursor = 0
        delim_upper = delimiter.upper()

        while cursor < len(expression):
            # Check if we're inside a string
            inside_string = any(start <= cursor < end for start, end in string_ranges)

            if not inside_string:
                # Check for delimiter match
                remaining = expression[cursor:].upper()
                if remaining.startswith(delim_upper):
                    parts.append(expression[:cursor].strip())
                    expression = expression[cursor + len(delimiter):]
                    cursor = 0
                    string_ranges = self.evaluator.engine._find_string_ranges(expression)
                    continue

            cursor += 1

        parts.append(expression.strip())
        return parts

    def _resolve_expression(
        self, expression: str, eval_context: dict[str, Any]
    ) -> str:
        """Resolve field references in expression to actual values."""
        return self.evaluator.engine._resolve_fields(expression, eval_context)

    def _generate_explanation(
        self,
        original: str,
        resolved: str,
        result: bool,
        eval_context: dict[str, Any],
    ) -> str:
        """Generate a natural language explanation for a condition."""
        # Pattern: field == 'value'
        match = re.match(
            r"(\w+(?:\.\w+)*)\s*==\s*'([^']*)'", original, re.IGNORECASE
        )
        if match:
            return self._explain_eq_string(match, resolved, result, eval_context)

        # Pattern: field >= number
        match = re.match(
            r"(\w+(?:\.\w+)*)\s*>=\s*(-?\d+(?:\.\d+)?)", original
        )
        if match:
            return self._explain_gte_numeric(match, resolved, result, eval_context)

        # Pattern: field > number
        match = re.match(
            r"(\w+(?:\.\w+)*)\s*>\s*(-?\d+(?:\.\d+)?)", original
        )
        if match:
            return self._explain_gt_numeric(match, resolved, result, eval_context)

        # Pattern: field <= number
        match = re.match(
            r"(\w+(?:\.\w+)*)\s*<=\s*(-?\d+(?:\.\d+)?)", original
        )
        if match:
            return self._explain_lte_numeric(match, resolved, result, eval_context)

        # Pattern: field < number
        match = re.match(
            r"(\w+(?:\.\w+)*)\s*<\s*(-?\d+(?:\.\d+)?)", original
        )
        if match:
            return self._explain_lt_numeric(match, resolved, result, eval_context)

        # Pattern: field IS NOT NULL
        match = re.search(r"(\w+(?:\.\w+)*)\s+IS\s+NOT\s+NULL", original, re.IGNORECASE)
        if match:
            field = match.group(1)
            label = METRIC_LABELS.get(field, field)
            if result:
                return f"{label}已填写"
            else:
                return f"{label}未填写"

        # Pattern: field IS NULL
        match = re.search(r"(\w+(?:\.\w+)*)\s+IS\s+NULL", original, re.IGNORECASE)
        if match:
            field = match.group(1)
            label = METRIC_LABELS.get(field, field)
            if result:
                return f"{label}未填写"
            else:
                return f"{label}已填写"

        # Pattern: field != 'value'
        match = re.match(
            r"(\w+(?:\.\w+)*)\s*!=\s*'([^']*)'", original, re.IGNORECASE
        )
        if match:
            field = match.group(1)
            expected = match.group(2)
            label = METRIC_LABELS.get(field, field)
            if result:
                return f"{label}不等于'{expected}'"
            else:
                return f"{label}等于'{expected}'，不满足要求"

        # Generic fallback
        label = self._extract_field_label(original)
        if result:
            return f"{label}条件满足: {original}"
        else:
            return f"{label}条件不满足: {original}"

    def _explain_eq_string(
        self,
        match: re.Match[str],
        resolved: str,
        result: bool,
        eval_context: dict[str, Any],
    ) -> str:
        """Explain field == 'value' condition."""
        field = match.group(1)
        expected = match.group(2)
        label = METRIC_LABELS.get(field, field)

        if field == "status":
            if result:
                return f"企业状态为{expected}，满足要求"
            else:
                return f"企业状态不为{expected}，不满足要求"

        if result:
            return f"{label}为'{expected}'，满足要求"
        else:
            return f"{label}不为'{expected}'，不满足要求"

    def _explain_gte_numeric(
        self,
        match: re.Match[str],
        resolved: str,
        result: bool,
        eval_context: dict[str, Any],
    ) -> str:
        """Explain field >= number condition."""
        field = match.group(1)
        threshold = float(match.group(2))
        label = METRIC_LABELS.get(field, field)
        actual = self._extract_left_value(resolved)

        if field == "registered_capital.value":
            if result:
                return f"注册资本{self._format_money(actual)}满足最低{self._format_money(threshold)}要求"
            else:
                return f"注册资本{self._format_money(actual)}低于最低{self._format_money(threshold)}要求"

        if result:
            return f"{label}({actual}) >= {self._format_number(threshold)}，满足要求"
        else:
            return f"{label}({actual}) < {self._format_number(threshold)}，不满足要求"

    def _explain_gt_numeric(
        self,
        match: re.Match[str],
        resolved: str,
        result: bool,
        eval_context: dict[str, Any],
    ) -> str:
        """Explain field > number condition."""
        field = match.group(1)
        threshold = float(match.group(2))
        label = METRIC_LABELS.get(field, field)
        actual = self._extract_left_value(resolved)

        if result:
            return f"{label}({actual}) > {self._format_number(threshold)}，满足要求"
        else:
            return f"{label}({actual}) <= {self._format_number(threshold)}，不满足要求"

    def _explain_lte_numeric(
        self,
        match: re.Match[str],
        resolved: str,
        result: bool,
        eval_context: dict[str, Any],
    ) -> str:
        """Explain field <= number condition."""
        field = match.group(1)
        threshold = float(match.group(2))
        label = METRIC_LABELS.get(field, field)
        actual = self._extract_left_value(resolved)

        if result:
            return f"{label}({actual}) <= {self._format_number(threshold)}，满足要求"
        else:
            return f"{label}({actual}) > {self._format_number(threshold)}，不满足要求"

    def _explain_lt_numeric(
        self,
        match: re.Match[str],
        resolved: str,
        result: bool,
        eval_context: dict[str, Any],
    ) -> str:
        """Explain field < number condition."""
        field = match.group(1)
        threshold = float(match.group(2))
        label = METRIC_LABELS.get(field, field)
        actual = self._extract_left_value(resolved)

        if result:
            return f"{label}({actual}) < {self._format_number(threshold)}，满足要求"
        else:
            return f"{label}({actual}) >= {self._format_number(threshold)}，不满足要求"

    def _extract_left_value(self, resolved: str) -> str:
        """Extract the left-side value from a resolved expression."""
        for op in [">=", "<=", "!=", "==", ">", "<"]:
            if op in resolved:
                return resolved.split(op)[0].strip()
        return resolved

    def _extract_field_label(self, expression: str) -> str:
        """Extract the primary field label from an expression."""
        match = re.search(r"(\w+(?:\.\w+)*)", expression)
        if match:
            return METRIC_LABELS.get(match.group(1), match.group(1))
        return ""

    @staticmethod
    def _format_money(value: Any) -> str:
        """Format a money value in Chinese yuan."""
        try:
            num = float(str(value).replace(",", ""))
            if num >= 100_000_000:
                return f"{num / 100_000_000:.2f}亿元"
            elif num >= 10_000:
                return f"{num / 10_000:.2f}万元"
            else:
                return f"{num:.0f}元"
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def _format_number(value: float) -> str:
        """Format a number for display."""
        if value == int(value):
            return str(int(value))
        return f"{value:.2f}"


class ImpactAnalyzer:
    """Analyze impact chains for What-if simulation."""

    def __init__(self, schema: KGMLSchema) -> None:
        self.schema = schema
        self._downstream: dict[str, list[str]] = self._build_dependency_graph()

    def analyze_impact(
        self,
        changed_fields: list[str],
    ) -> list[ImpactChain]:
        """Analyze downstream impact of changed fields.

        Example:
            changed_fields = ["credit_score"]
            → ImpactChain(
                source_field="credit_score",
                affected_fields=["credit_grade", "credit_limit", "interest_rate", "final_decision"],
                description="综合信用评分 → 信用等级 → 授信额度 → 利率 → 最终决策"
            )
        """
        chains: list[ImpactChain] = []
        for field in changed_fields:
            affected = self._trace_downstream(field)
            if affected:
                chains.append(
                    ImpactChain(
                        source_field=field,
                        affected_fields=affected,
                        description=self._build_impact_description(field, affected),
                    )
                )
        return chains

    def compute_diffs(
        self,
        baseline: dict[str, Any],
        simulated: dict[str, Any],
    ) -> list[DiffEntry]:
        """Compute differences between baseline and simulation results."""
        diffs: list[DiffEntry] = []
        all_keys = sorted(set(list(baseline.keys()) + list(simulated.keys())))

        for key in all_keys:
            b_val = baseline.get(key)
            s_val = simulated.get(key)

            if b_val == s_val:
                continue

            change_type = self._classify_change(b_val, s_val)
            magnitude = self._compute_magnitude(b_val, s_val)
            impact = self._describe_impact(key, b_val, s_val)

            diffs.append(
                DiffEntry(
                    field=key,
                    baseline_value=b_val,
                    simulated_value=s_val,
                    change_type=change_type,
                    change_magnitude=magnitude,
                    impact=impact,
                )
            )

        return diffs

    def _build_dependency_graph(self) -> dict[str, list[str]]:
        """Build downstream dependency graph from schema metrics.

        Returns: { metric_name: [metrics that directly depend on it] }
        """
        downstream: dict[str, list[str]] = {}
        for metric in self.schema.metrics:
            for dep in metric.dependencies:
                if dep not in downstream:
                    downstream[dep] = []
                downstream[dep].append(metric.name)

        # Also add rule-output dependencies
        # e.g., eligible → credit_score, credit_score → credit_limit
        rule_downstream: dict[str, list[str]] = {
            "eligible": ["credit_score"],
            "credit_score": ["credit_grade", "credit_limit"],
            "credit_grade": ["credit_limit", "interest_rate"],
            "credit_limit": ["final_decision"],
            "interest_rate": ["final_decision"],
            "guarantee_chain_depth": ["credit_score"],
        }
        for src, targets in rule_downstream.items():
            if src not in downstream:
                downstream[src] = []
            for t in targets:
                if t not in downstream[src]:
                    downstream[src].append(t)

        return downstream

    def _trace_downstream(self, field: str) -> list[str]:
        """Trace all downstream impacts via BFS."""
        visited: set[str] = set()
        queue: list[str] = [field]
        result: list[str] = []

        while queue:
            current = queue.pop(0)
            for downstream_field in self._downstream.get(current, []):
                if downstream_field not in visited:
                    visited.add(downstream_field)
                    result.append(downstream_field)
                    queue.append(downstream_field)

        return result

    def _build_impact_description(
        self, source: str, affected: list[str]
    ) -> str:
        """Build a human-readable impact path description."""
        path = [source] + affected
        labels = [METRIC_LABELS.get(p, p) for p in path]
        return " → ".join(labels)

    def _classify_change(
        self, baseline: Any, simulated: Any
    ) -> str:
        """Classify the type of change."""
        if baseline is None and simulated is not None:
            return "new"
        if baseline is not None and simulated is None:
            return "removed"
        try:
            b = float(baseline)
            s = float(simulated)
            if s > b:
                return "increased"
            elif s < b:
                return "decreased"
            else:
                return "unchanged"
        except (TypeError, ValueError):
            if baseline != simulated:
                return "changed"
            return "unchanged"

    def _compute_magnitude(
        self, baseline: Any, simulated: Any
    ) -> float | None:
        """Compute percentage change magnitude."""
        try:
            b = float(baseline) if baseline is not None else 0
            s = float(simulated) if simulated is not None else 0
            if b == 0:
                return None
            return round((s - b) / abs(b) * 100, 1)
        except (TypeError, ValueError):
            return None

    def _describe_impact(
        self, field: str, baseline: Any, simulated: Any
    ) -> str:
        """Describe the impact of a change."""
        label = METRIC_LABELS.get(field, field)
        change_type = self._classify_change(baseline, simulated)
        magnitude = self._compute_magnitude(baseline, simulated)

        if magnitude is not None:
            direction = "上升" if magnitude > 0 else "下降"
            return f"{label}{direction}{abs(magnitude):.1f}%"
        else:
            if change_type == "new":
                return f"{label}新增"
            elif change_type == "removed":
                return f"{label}移除"
            elif change_type == "changed":
                return f"{label}变更: {baseline} → {simulated}"
            else:
                return f"{label}: {baseline} → {simulated}"
