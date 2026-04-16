"""Rule engine data models."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ExecutionContext:
    """Context for rule execution."""
    entity_id: str
    dimension: str
    entity_data: dict[str, Any]  # The entity's data
    computed_metrics: dict[str, Any] = field(default_factory=dict)
    rule_results: list[RuleResult] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)


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
        """Create from dictionary."""
        applies_to = AppliesToConfig(
            fact_objects=data.get("applies_to", {}).get("fact_objects", []),
            categories=data.get("applies_to", {}).get("categories", {}),
        )
        preconditions = [
            Precondition(expression=p.get("expression", ""), fail=p.get("fail"))
            for p in data.get("preconditions", [])
        ]
        inputs = [
            IOElement(
                name=i.get("name", ""),
                type=i.get("type"),
                metric=i.get("metric"),
                attribute=i.get("attribute"),
            )
            for i in data.get("inputs", [])
        ]
        outputs = [
            IOElement(name=o.get("name", ""), type=o.get("type"))
            for o in data.get("outputs", [])
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
            schema_id=data.get("schema_id"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class ActionClause:
    """动作子句：算子配置"""
    operator: str  # 算子名称
    params: dict[str, Any] = field(default_factory=dict)  # 算子参数
    output_mapping: dict[str, str] = field(default_factory=dict)  # 输出变量别名

    def to_dict(self) -> dict[str, Any]:
        return {
            "operator": self.operator,
            "params": self.params,
            "output_mapping": self.output_mapping,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionClause":
        return cls(
            operator=data.get("operator", ""),
            params=data.get("params", {}),
            output_mapping=data.get("output_mapping", {}),
        )


@dataclass
class ConditionClause:
    """条件子句：支持单一/AND/OR"""
    type: Literal["expression", "all_of", "any_of"] = "expression"
    expression: str | None = None  # type=expression 时使用
    sub_conditions: list[str] = field(default_factory=list)  # type=all_of/any_of 时使用

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "expression": self.expression,
            "sub_conditions": self.sub_conditions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConditionClause":
        return cls(
            type=data.get("type", "expression"),
            expression=data.get("expression"),
            sub_conditions=data.get("sub_conditions", []),
        )


@dataclass
class RuleStep:
    """规则实例（具体逻辑）- 对应四元素的 ④

    具体的逻辑表达式，一个 when → then/else 结构。
    使用算子执行计算。
    """
    id: str
    name: str
    rule_group: str  # 所属规则组
    order: int  # 执行顺序
    when: ConditionClause
    then: ActionClause
    else_: ActionClause | None = None
    enabled: bool = True
    description: str = ""
    tags: list[str] = field(default_factory=list)

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
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RuleStep":
        # Support both to_dict() format (when/then/else) and DB storage format (when_clause/then_clause/else_clause)
        when_data = data.get("when", data.get("when_clause", {}))
        then_data = data.get("then", data.get("then_clause", {}))
        else_data = data.get("else", data.get("else_clause"))

        when = ConditionClause.from_dict(when_data) if isinstance(when_data, dict) else when_data
        then = ActionClause.from_dict(then_data) if isinstance(then_data, dict) else then_data
        else_ = ActionClause.from_dict(else_data) if else_data and isinstance(else_data, dict) else else_data

        return cls(
            id=data["id"],
            name=data.get("name", ""),
            rule_group=data.get("rule_group", ""),
            order=data.get("step_order", data.get("order", 0)),
            when=when,
            then=then,
            else_=else_,
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            tags=data.get("tags", []),
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
