"""Rule engine data models."""
from __future__ import annotations
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from ontology_engine.core.schema.models import ActionType, OperatorType

if TYPE_CHECKING:
    from ontology_engine.core.schema.models import StepAction


@dataclass
class ExecutionContext:
    """Context for rule execution."""
    entity_id: str
    dimension: str
    entity_data: dict[str, Any]  # The entity's data
    computed_metrics: dict[str, Any] = field(default_factory=dict)
    rule_results: list[RuleResult] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    categories: dict[str, str] = field(default_factory=dict)


@dataclass
class RuleResult:
    """Result of a rule execution."""
    rule_id: str
    rule_name: str | None
    passed: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class Alert:
    """Alert/warning generated during execution."""
    level: str  # "warning", "high", "critical"
    type: str
    message: str
    data: dict[str, Any] | None = None


@dataclass
class AnalysisResult:
    """Complete analysis result for a dimension."""
    entity_id: str
    dimension: str
    rule_results: list[RuleResult]
    computed_metrics: dict[str, Any]
    alerts: list[Alert]
    decision: str | None = None
    decision_reasoning: str | None = None


# =============================================================================
# Phase 2: Rule Orchestration System Models
# =============================================================================


@dataclass
class AppliesToConfig:
    """规则作用对象配置 - 四元素 ①"""
    fact_objects: list[str] = field(default_factory=list)  # 实体类型列表
    categories: dict[str, list[str]] = field(default_factory=dict)  # 分类过滤条件


@dataclass
class Precondition:
    """前置条件配置 - 四元素 ②"""
    expression: str
    fail: dict[str, Any] | None = None  # 失败时的动作


@dataclass
class IOElement:
    """输入输出要素 - 四元素 ③"""
    name: str
    type: str | None = None
    metric: str | None = None  # 引用指标
    attribute: str | None = None  # 引用属性
    description: str | None = None


@dataclass
class RuleGroupDefinition:
    """规则组（框架）- 对应四元素的 ① ② ③

    定义规则的框架结构，包含作用对象、适用场景、I/O 要素声明。
    包含一组有序的规则实例。

    Attributes:
        id: UUID primary key, used by frontend and as URL parameter
        name: Business identifier, unique constraint
    """
    id: str = ""  # UUID primary key for frontend/URL use
    name: str = ""
    description: str = ""
    type: Literal["constraint", "inference", "alert", "decision"] = "decision"
    priority: int = 100
    applies_to: AppliesToConfig = field(default_factory=AppliesToConfig)
    preconditions: list[Precondition] = field(default_factory=list)
    inputs: list[IOElement] = field(default_factory=list)
    outputs: list[IOElement] = field(default_factory=list)
    enabled: bool = True
    schema_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        warnings.warn(
            "RuleGroupDefinition is deprecated. Use RuleDefinitionDecl instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "priority": self.priority,
            "applies_to": {
                "fact_objects": self.applies_to.fact_objects,
                "categories": self.applies_to.categories,
            },
            "preconditions": [
                {"expression": p.expression, "fail": p.fail}
                for p in self.preconditions
            ],
            "inputs": [
                {"name": i.name, "type": i.type, "metric": i.metric, "attribute": i.attribute}
                for i in self.inputs
            ],
            "outputs": [
                {"name": o.name, "type": o.type}
                for o in self.outputs
            ],
            "enabled": self.enabled,
            "schema_id": self.schema_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuleGroupDefinition":
        """Create from dictionary.

        Supports both snake_case (backend to_dict/DB) and camelCase (frontend API).
        """
        # Handle applies_to: snake_case (applies_to.fact_objects) or camelCase (appliesTo.factObjects)
        _applies_to_raw = data.get("applies_to") or data.get("appliesTo") or {}
        if isinstance(_applies_to_raw, dict):
            _fact = _applies_to_raw.get("fact_objects") or _applies_to_raw.get("factObjects") or []
            _cats = _applies_to_raw.get("categories") or {}
        else:
            _fact = []
            _cats = {}
        applies_to = AppliesToConfig(
            fact_objects=_fact,
            categories=_cats,
        )
        preconditions = [
            Precondition(expression=p.get("expression", ""), fail=p.get("fail"))
            for p in (data.get("preconditions") or [])
        ]
        inputs = [
            IOElement(
                name=i.get("name", ""),
                type=i.get("type"),
                metric=i.get("metric"),
                attribute=i.get("attribute"),
            )
            for i in (data.get("inputs") or [])
        ]
        outputs = [
            IOElement(name=o.get("name", ""), type=o.get("type"))
            for o in (data.get("outputs") or [])
        ]
        return cls(
            id=data.get("id", ""),
            name=data["name"],
            description=data.get("description", ""),
            type=data.get("type", "decision"),
            priority=data.get("priority", 100),
            applies_to=applies_to,
            preconditions=preconditions,
            inputs=inputs,
            outputs=outputs,
            enabled=data.get("enabled", True),
            # Support both snake_case and camelCase for schema_id
            schema_id=data.get("schema_id") or data.get("schemaId") or "",
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class ActionClause:
    """动作子句：算子配置

    .. deprecated::
        Use StructuredActionClause instead.
    """
    operator: str
    params: dict[str, Any] = field(default_factory=dict)
    output_mapping: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        warnings.warn(
            "ActionClause is deprecated. Use StructuredActionClause instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "params": self.params,
            "output_mapping": self.output_mapping,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionClause":
        # Support both snake_case (backend to_dict) and camelCase (frontend API)
        _mapping = data.get("output_mapping") or data.get("outputMapping") or {}
        return cls(
            operator=data.get("operator", ""),
            params=data.get("params", {}),
            output_mapping=_mapping,
        )


@dataclass
class ConditionClause:
    """条件子句：支持单一/AND/OR

    .. deprecated::
        Prefer StepCondition (core/schema/models.py) for new code.
    """
    type: Literal["expression", "all_of", "any_of"] = "expression"
    expression: str | None = None
    sub_conditions: list[str | dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        warnings.warn(
            "ConditionClause is deprecated. Prefer StepCondition for new code.",
            DeprecationWarning,
            stacklevel=2,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "expression": self.expression,
            "sub_conditions": self.sub_conditions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConditionClause":
        # Support both snake_case (backend to_dict) and camelCase (frontend API)
        _subs = data.get("sub_conditions") or data.get("subConditions") or []
        return cls(
            type=data.get("type", "expression"),
            expression=data.get("expression"),
            sub_conditions=_subs,
        )


@dataclass
class RuleStep:
    """规则实例（具体逻辑）- 对应四元素的 ④

    具体的逻辑表达式，一个 when → then/else 结构。
    使用算子执行计算。

    .. deprecated::
        Use StepDecl instead.
    """
    id: str
    name: str
    rule_group: str
    order: int
    when: ConditionClause
    then: ActionClause
    else_: ActionClause | None = None
    enabled: bool = True
    description: str = ""
    tags: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        warnings.warn(
            "RuleStep is deprecated. Use StepDecl instead.",
            DeprecationWarning,
            stacklevel=2,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "rule_group": self.rule_group,
            "step_order": self.order,
            "when": self.when.to_dict(),
            "then": self.then.to_dict(),
            "else": self.else_.to_dict() if self.else_ else None,
            "enabled": self.enabled,
            "description": self.description,
            "tags": self.tags,
            "depends_on": self.depends_on,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuleStep":
        # Support both to_dict() format (when/then/else) and DB storage format (when_clause/then_clause/else_clause)
        _when_raw = data.get("when") if "when" in data else data.get("when_clause")
        _then_raw = data.get("then") if "then" in data else data.get("then_clause")
        _else_raw = data.get("else") if "else" in data else data.get("else_clause")
        when_data = _when_raw if isinstance(_when_raw, dict) else None
        then_data = _then_raw if isinstance(_then_raw, dict) else None
        else_data = _else_raw if isinstance(_else_raw, dict) else None

        when = ConditionClause.from_dict(when_data) if isinstance(when_data, dict) else when_data
        then = ActionClause.from_dict(then_data) if isinstance(then_data, dict) else then_data
        else_ = ActionClause.from_dict(else_data) if else_data and isinstance(else_data, dict) else else_data

        return cls(
            id=data["id"],
            name=data.get("name", ""),
            # Support both snake_case (backend to_dict/DB) and camelCase (frontend API)
            rule_group=data.get("rule_group") or data.get("ruleGroup") or "",
            order=data.get("step_order", data.get("order", 0)),
            when=when,
            then=then,
            else_=else_,
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            tags=data.get("tags", []),
            # Support both snake_case (depends_on) and camelCase (dependsOn)
            depends_on=data.get("depends_on") or data.get("dependsOn") or [],
        )


@dataclass
class OperatorSchema:
    """算子注册信息"""
    name: str
    display_name: str
    description: str
    category: Literal[
        "binning", "scorecard", "weighted_sum", "decision_table",
        "llm_judge", "flag", "alert", "compute", "switch", "graph"
    ]
    param_schema: dict[str, Any]  # JSON Schema 约束算子参数
    input_types: list[str]  # 支持的输入类型
    output_types: list[str]  # 产出的输出类型
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "param_schema": self.param_schema,
            "input_types": self.input_types,
            "output_types": self.output_types,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperatorSchema":
        return cls(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            description=data.get("description", ""),
            category=data.get("category", "compute"),
            param_schema=data.get("param_schema", {}),
            input_types=data.get("input_types", []),
            output_types=data.get("output_types", []),
            enabled=data.get("enabled", True),
        )


# ============== V3 Runtime Models (RFC-018 / RFC-019) ==============

_SET_FLAG_OPERATORS = frozenset({"set_flag", "approve_eligibility", "reject_eligibility"})
_REJECT_OPERATORS = frozenset({"reject"})
_ALERT_OPERATORS = frozenset({"trigger_alert", "alert"})
_CATEGORY_OPERATORS = frozenset({"assign_category"})


def _infer_action_type_from_operator(operator: str | None) -> ActionType:
    """Infer ActionType from legacy operator name."""
    if not operator:
        return ActionType.COMPUTE
    lower = operator.lower()
    if lower in _SET_FLAG_OPERATORS:
        return ActionType.SET_FLAG
    if lower in _REJECT_OPERATORS:
        return ActionType.REJECT
    if lower in _ALERT_OPERATORS:
        return ActionType.EMIT_ALERT
    if lower in _CATEGORY_OPERATORS:
        return ActionType.ASSIGN_CATEGORY
    return ActionType.COMPUTE


@dataclass
class StructuredActionClause:
    """Structured action clause (RFC-019).

    Runtime dataclass version of core.schema.models.StepAction.
    Uses ActionType enum for type-safe dispatch.
    """
    type: ActionType

    flag: str | None = None
    value: Any = None

    output: str | None = None
    operator: OperatorType | None = None
    params: dict[str, Any] = field(default_factory=dict)
    formula: str | None = None

    query: dict[str, Any] | None = None
    aggregation: list[dict[str, Any]] | None = None
    bins: list[dict[str, Any]] | None = None
    branches: list[dict[str, Any]] | None = None
    variables: list[dict[str, Any]] | None = None

    reason: str | None = None
    severity: str | None = None

    category: str | None = None

    output_mapping: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_step_action(cls, action: "StepAction") -> "StructuredActionClause":
        """Create from Pydantic StepAction model."""
        return cls(
            type=action.type,
            flag=action.flag,
            value=action.value,
            output=action.output,
            operator=action.operator,
            params=dict(action.params) if action.params else {},
            formula=action.formula,
            query=dict(action.query) if action.query else None,
            aggregation=list(action.aggregation) if action.aggregation else None,
            bins=list(action.bins) if action.bins else None,
            branches=list(action.branches) if action.branches else None,
            variables=list(action.variables) if action.variables else None,
            reason=action.reason,
            severity=action.severity,
            category=action.category,
            output_mapping=dict(action.output_mapping) if action.output_mapping else {},
        )

    @classmethod
    def from_legacy(cls, action_str: str | None, output: dict | None = None, computation: dict | None = None) -> "StructuredActionClause | None":
        """Create from legacy action: str + output: dict pattern.

        Maps old ACTION_* constants and operator names to ActionType enum.
        """
        if action_str is None:
            return None

        output = output or {}
        computation = computation or {}

        action_lower = action_str.lower()

        if action_lower in ("approve_eligibility",):
            return cls(type=ActionType.SET_FLAG, flag="eligible", value=True)
        elif action_lower in ("reject_eligibility",):
            return cls(type=ActionType.SET_FLAG, flag="eligible", value=False, reason=output.get("rejection_reason"))
        elif action_lower in ("trigger_alert", "alert"):
            return cls(
                type=ActionType.EMIT_ALERT,
                severity=output.get("alert_level", "WARNING"),
                reason=output.get("message", ""),
            )
        elif action_lower in ("reject",):
            return cls(type=ActionType.REJECT, reason=output.get("reason", ""))
        elif action_lower in ("assign_category",):
            return cls(type=ActionType.ASSIGN_CATEGORY, category=output.get("category"))
        elif action_lower in ("set_flag",):
            return cls(type=ActionType.SET_FLAG, flag=output.get("flag"), value=output.get("value"))
        else:
            return cls(
                type=ActionType.COMPUTE,
                output=computation.get("output_field") or output.get("output_field"),
                operator=OperatorType(action_str) if action_str in [e.value for e in OperatorType] else None,
                params=computation.get("params", {}),
                formula=computation.get("formula") or output.get("formula"),
            )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"type": self.type.value}
        if self.flag is not None:
            result["flag"] = self.flag
        if self.value is not None:
            result["value"] = self.value
        if self.output is not None:
            result["output"] = self.output
        if self.operator is not None:
            result["operator"] = self.operator.value
        if self.params:
            result["params"] = self.params
        if self.formula is not None:
            result["formula"] = self.formula
        if self.query is not None:
            result["query"] = self.query
        if self.aggregation is not None:
            result["aggregation"] = self.aggregation
        if self.bins is not None:
            result["bins"] = self.bins
        if self.branches is not None:
            result["branches"] = self.branches
        if self.variables is not None:
            result["variables"] = self.variables
        if self.reason is not None:
            result["reason"] = self.reason
        if self.severity is not None:
            result["severity"] = self.severity
        if self.category is not None:
            result["category"] = self.category
        if self.output_mapping:
            result["output_mapping"] = self.output_mapping
        return result


@dataclass
class StepDecl:
    """Step declaration (RFC-018 / RFC-019) runtime model.

    Uses StructuredActionClause for type-safe action dispatch.
    """
    id: str
    name: str = ""
    description: str = ""
    priority: int = 100
    depends_on: list[str] = field(default_factory=list)

    condition: ConditionClause | None = None
    action: StructuredActionClause | None = None
    else_action: StructuredActionClause | None = None

    enabled: bool = True


@dataclass
class RuleDefinitionDecl:
    """Rule definition declaration (RFC-018) runtime model.

    Declares WHAT the rule operates on.
    Aligned with L4 grammar rule_definitions[].
    """
    name: str
    description: str = ""
    type: str = "constraint"
    priority: int = 100

    applies_to: AppliesToConfig = field(default_factory=AppliesToConfig)
    preconditions: list[Precondition] = field(default_factory=list)
    inputs: list[IOElement] = field(default_factory=list)
    outputs: list[IOElement] = field(default_factory=list)

    overrides: str | None = None
    applicability: dict[str, str | None] | None = None

    @property
    def when_text(self) -> str | None:
        if self.applicability:
            return self.applicability.get("when_text")
        return None

    @property
    def why_text(self) -> str | None:
        if self.applicability:
            return self.applicability.get("why_text")
        return None

    @property
    def boundary_text(self) -> str | None:
        if self.applicability:
            return self.applicability.get("boundary_text")
        return None

    @property
    def outcome_text(self) -> str | None:
        if self.applicability:
            return self.applicability.get("outcome_text")
        return None

    @property
    def prereq_text(self) -> str | None:
        if self.applicability:
            return self.applicability.get("prereq_text")
        return None

    @property
    def exception_text(self) -> str | None:
        if self.applicability:
            return self.applicability.get("exception_text")
        return None

    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "priority": self.priority,
            "applies_to": self.applies_to.__dict__ if self.applies_to else {},
            "enabled": self.enabled,
        }
        if self.preconditions:
            result["preconditions"] = [{"expression": p.expression, "fail": p.fail} for p in self.preconditions]
        if self.inputs:
            result["inputs"] = [{"name": i.name, "type": i.type} for i in self.inputs]
        if self.outputs:
            result["outputs"] = [{"name": o.name, "type": o.type} for o in self.outputs]
        if self.overrides is not None:
            result["overrides"] = self.overrides
        if self.applicability is not None:
            result["applicability"] = self.applicability
        return result

    @classmethod
    def from_rule_group(cls, rg: RuleGroupDefinition) -> "RuleDefinitionDecl":
        """Create from RuleGroupDefinition (Phase 2 runtime model)."""
        return cls(
            name=rg.name,
            description=rg.description,
            type=rg.type,
            priority=rg.priority,
            applies_to=rg.applies_to,
            preconditions=rg.preconditions,
            inputs=rg.inputs,
            outputs=rg.outputs,
            enabled=rg.enabled,
        )


@dataclass
class RuleLogicDecl:
    """Rule logic declaration (RFC-018) runtime model.

    Declares HOW the rule is executed.
    Aligned with L4 grammar rule_logics[].
    """
    name: str
    description: str = ""
    type: str = "decision_table"
    steps: list[StepDecl] = field(default_factory=list)

    definition_ref: str = ""
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "type": self.type,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "priority": s.priority,
                    "depends_on": s.depends_on,
                    "action": s.action.to_dict() if s.action else None,
                    "else_action": s.else_action.to_dict() if s.else_action else None,
                    "enabled": s.enabled,
                }
                for s in self.steps
            ],
            "definition_ref": self.definition_ref,
            "enabled": self.enabled,
        }

    @classmethod
    def from_rule_steps(cls, steps: list[RuleStep], definition_ref: str = "") -> "RuleLogicDecl":
        """Create from list of RuleStep (Phase 2 runtime model)."""
        v3_steps = []
        for s in steps:
            action = None
            if s.then:
                action = StructuredActionClause(
                    type=_infer_action_type_from_operator(s.then.operator),
                    operator=OperatorType(s.then.operator) if s.then.operator and s.then.operator in [e.value for e in OperatorType] else None,
                    params=dict(s.then.params) if s.then.params else {},
                    output_mapping=dict(s.then.output_mapping) if s.then.output_mapping else {},
                )
            else_action = None
            if s.else_:
                else_action = StructuredActionClause(
                    type=_infer_action_type_from_operator(s.else_.operator),
                    operator=OperatorType(s.else_.operator) if s.else_.operator and s.else_.operator in [e.value for e in OperatorType] else None,
                    params=dict(s.else_.params) if s.else_.params else {},
                    output_mapping=dict(s.else_.output_mapping) if s.else_.output_mapping else {},
                )
            v3_steps.append(StepDecl(
                id=s.id,
                name=s.name,
                description=s.description,
                priority=s.order if hasattr(s, "order") else 100,
                depends_on=s.depends_on,
                condition=s.when,
                action=action,
                else_action=else_action,
                enabled=s.enabled,
            ))
        return cls(
            name=definition_ref or "",
            definition_ref=definition_ref,
            steps=v3_steps,
        )
