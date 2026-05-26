from __future__ import annotations

from typing import Any

from ontology_engine.core.semantic_space import SemanticSpace


def _rule_inputs(rule: dict) -> list[dict]:
    return rule.get("inputs") or rule.get("input_elements") or []


class RuleExecutionService:

    async def execute_single_rule(
        self,
        rule: dict,
        space: SemanticSpace,
        entity_data: dict,
        context: Any,
        expression_engine: Any,
        step_num: int,
        include_trace: bool,
    ) -> dict[str, Any]:
        rule_id = rule["id"]
        rule_name = rule.get("name", rule_id)
        rule_type = rule.get("rule_type", "constraint")

        logic_ids = rule.get("logic_ids", [])
        matching_logic = self._find_matching_logic(
            logic_ids,
            space.layers.L4_business_logic.rule_logics,
            entity_data,
        )

        current_inputs = self._gather_inputs(
            rule, entity_data, context.computed_metrics
        )

        when_expr = self._extract_when_expr(matching_logic, rule)
        condition_result = True
        condition_explanation = "无条件，默认执行"
        condition_sub_conditions: list[dict[str, Any]] = []

        if when_expr:
            try:
                eval_ctx = {**entity_data, **context.computed_metrics}
                condition_result = bool(
                    expression_engine.evaluate(when_expr, eval_ctx)
                )
                condition_explanation = f"条件: {when_expr} → {'满足' if condition_result else '不满足'}"
            except Exception as exc:
                condition_result = False
                condition_explanation = f"条件评估出错: {exc}"

        if matching_logic and matching_logic.get("when"):
            when_obj = matching_logic["when"]
            condition_sub_conditions = self._explain_conditions(
                when_obj,
                entity_data,
                context.computed_metrics,
                expression_engine,
            )
        elif rule.get("when"):
            condition_sub_conditions = self._explain_conditions(
                rule["when"],
                entity_data,
                context.computed_metrics,
                expression_engine,
            )

        context_before = dict(context.computed_metrics)
        step_outputs: dict[str, Any] = {}

        if condition_result:
            then_action = None
            if matching_logic:
                then_action = matching_logic.get("then_action")
            if not then_action:
                then_action = rule.get("then_action")

            if then_action:
                step_outputs = self._execute_action(
                    then_action,
                    entity_data,
                    context.computed_metrics,
                    expression_engine,
                )
                context.computed_metrics.update(step_outputs)

            status = "passed"
            action_type = (then_action or {}).get("action_type", "")
            explanation = self._build_explanation(
                action_type, step_outputs, condition_explanation
            )
        else:
            else_action = (
                (matching_logic or {}).get("else_action")
                if matching_logic
                else rule.get("else_action")
            )
            if else_action:
                else_outputs = self._execute_action(
                    else_action,
                    entity_data,
                    context.computed_metrics,
                    expression_engine,
                )
                context.computed_metrics.update(else_outputs)
                step_outputs = else_outputs
                explanation = f"条件不满足，执行else分支: {self._build_explanation(else_action.get('action_type', ''), else_outputs, '')}"
            else:
                explanation = "条件不满足，规则跳过"
            status = "skipped"

        step: dict[str, Any] = {
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
            "outputs": [
                {"name": k, "value": v} for k, v in step_outputs.items()
            ],
            "matching_logic_id": (
                matching_logic.get("id") if matching_logic else None
            ),
        }

        if include_trace:
            step["context_before"] = context_before
            step["context_after"] = dict(context.computed_metrics)

        return step

    def _find_matching_logic(
        self,
        logic_ids: list[str],
        rule_logics: list[dict],
        entity_data: dict,
    ) -> dict | None:
        for logic_id in logic_ids:
            logic = next(
                (
                    rl
                    for rl in rule_logics
                    if rl.get("id") == logic_id
                ),
                None,
            )
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
                    values_list = (
                        value if isinstance(value, list) else [value]
                    )
                    if entity_value not in values_list:
                        match = False
                        break
            if match:
                return logic
        return None

    def _extract_when_expr(
        self, logic: dict | None, rule: dict
    ) -> str | None:
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
        self,
        when_obj: dict,
        entity_data: dict,
        computed: dict,
        expression_engine: Any,
    ) -> list[dict[str, Any]]:
        sub_conditions: list[dict[str, Any]] = []
        eval_ctx = {**entity_data, **computed}

        if isinstance(when_obj, dict):
            if "expression" in when_obj and when_obj["expression"]:
                try:
                    result = bool(
                        expression_engine.evaluate(
                            when_obj["expression"], eval_ctx
                        )
                    )
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
                        result = bool(
                            expression_engine.evaluate(expr, eval_ctx)
                        )
                        sub_conditions.append({
                            "type": "allOf",
                            "expr": expr,
                            "result": result,
                        })
                    except Exception as exc:
                        sub_conditions.append({
                            "type": "allOf",
                            "expr": expr,
                            "result": False,
                            "error": str(exc),
                        })

            for item in when_obj.get("anyOf", []) or []:
                expr = item.get("expression", "")
                if expr:
                    try:
                        result = bool(
                            expression_engine.evaluate(expr, eval_ctx)
                        )
                        sub_conditions.append({
                            "type": "anyOf",
                            "expr": expr,
                            "result": result,
                        })
                    except Exception as exc:
                        sub_conditions.append({
                            "type": "anyOf",
                            "expr": expr,
                            "result": False,
                            "error": str(exc),
                        })

        return sub_conditions

    def _gather_inputs(
        self,
        rule: dict,
        entity_data: dict,
        computed: dict,
    ) -> list[dict[str, Any]]:
        inputs: list[dict[str, Any]] = []
        for in_elem in _rule_inputs(rule):
            name = in_elem.get("name") or in_elem.get("id", "")
            if name:
                value = computed.get(name, entity_data.get(name))
                inputs.append({
                    "name": name,
                    "value": value,
                    "type": in_elem.get("type", ""),
                })
        return inputs

    def _execute_action(
        self,
        action: dict,
        entity_data: dict,
        computed: dict,
        expression_engine: Any,
    ) -> dict[str, Any]:
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
                        outputs[key] = expression_engine.evaluate(
                            formula, eval_ctx
                        )
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
            alert_msg = action.get("output", {}).get(
                "message", "alert triggered"
            )
            existing_alerts = computed.get("alerts", [])
            outputs["alerts"] = existing_alerts + [alert_msg]
            for key, value in (action.get("output") or {}).items():
                if key != "message":
                    outputs[key] = value

        elif action_type == "recommend":
            for key, value in (action.get("output") or {}).items():
                if isinstance(value, str) and (
                    "${" in value or "{" in value
                ):
                    try:
                        outputs[key] = expression_engine.evaluate(
                            value, eval_ctx
                        )
                    except Exception:
                        outputs[key] = value
                else:
                    outputs[key] = value

        return outputs

    def _build_explanation(
        self,
        action_type: str,
        outputs: dict[str, Any],
        condition_explanation: str,
    ) -> str:
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
                    parts.append(
                        f"告警 → {'; '.join(str(a) for a in value[-3:])}"
                    )
            else:
                parts.append(f"{key} = {value}")

        return "；".join(parts) if parts else condition_explanation
