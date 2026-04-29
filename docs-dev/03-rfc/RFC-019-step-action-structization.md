# RFC-019: Step.action 结构化 — ActionType 枚举 + 结构化 Action 模型

> **状态**: implemented
> **父 RFC**: [RFC-010](./RFC-010-phase2-roadmap.md)
> **前置 RFC**: [RFC-018](./RFC-018-rule-model-dual-separation.md)
> **创建日期**: 2026-04-29
> **最后更新**: 2026-04-29
> **实施进度**: Phase A ✅ Phase B ✅ Phase C ✅ Phase D ✅ Phase E ✅
> **作者**: the-butterfly
> **评审截止**: 待定
> **关联文档**: [L4 Grammar Step.action](../../02-design/schema/L1-L4-declarations.md) · [DAG 执行设计](../../02-design/rule-engine/dag-execution.md) · [规则引擎设计 D7](../../02-design/rule-engine/README.md) · [ADR-008 D12](../../04-adr/ADR-008-phase1-4-review-decisions.md)

---

## 摘要

将 Step.action 从当前的 `str + dict` 扁平表示重构为结构化的 `ActionClause` 模型，引入 `ActionType` 枚举（set_flag / compute / reject / emit_alert / assign_category），与 L4 grammar `steps[].action` 定义完全对齐。

**核心目标**：让执行引擎可以针对不同动作类型优化处理，消除硬编码 `ACTION_*` 常量，支持算子扩展。

---

## 一、现状与痛点

### 1.1 当前 Step.action 的四种表示

| 层级 | 模型 | action 表示 | 文件 |
|------|------|-------------|------|
| Schema 层 `RuleStep` | `action: str \| None` + `computation: dict \| None` | 算子名 + 计算配置分离 | `core/schema/models.py` |
| Schema 层 `RuleThen` | `action: str \| None` + `output: dict \| None` + `computation: dict \| None` | 三字段分离 | `core/schema/models.py` |
| Engine 层 `RuleStep` | `then: ActionClause` (operator + params + output_mapping) | 结构化但无 type 区分 | `engine/rule/models.py` |
| Semantic Space `RuleAction` | `action_type: str` + `output: dict` + `formula: str` + `operator: str` | 四字段混合 | `core/semantic_space/rule_models.py` |

### 1.2 核心问题

| 问题 | 表现 | 影响 |
|------|------|------|
| 无 ActionType 枚举 | `action_type` / `action` 是自由字符串 | 无法静态校验，拼写错误不报错 |
| 四种表示并存 | 同一概念在不同层有不同结构 | 转换逻辑分散，易出 bug |
| 硬编码 ACTION_* 常量 | `ACTION_APPROVE_ELIGIBILITY` 等 7 个常量 | 不可扩展，新增动作需改代码 |
| 元数据丢失 | `RuleThen.action` 是纯字符串，丢失 reason/severity 等 | reject/emit_alert 无法携带原因和严重级别 |
| 与 L4 grammar 不对齐 | L4 定义了 5 种 action.type + 6 种 operator | 代码仅用 str+dict |

### 1.3 设计决策溯源

- **L4 grammar 设计决策 #7**：`action.type` 分类（set_flag/compute/reject/emit_alert/assign_category）替代扁平的 then/else
- **规则引擎设计决策 D7**：L4 `action.type` 驱动 + OperatorRegistry，替代硬编码 ACTION_*
- **规则引擎审查偏差 D3**：硬编码 ACTION_* 需迁移到 action.type 枚举 + OperatorRegistry
- **ADR-008 D12**：P1-1 与 P0-3 同为大型重构项，需 RFC 先行

---

## 二、目标模型定义

### 2.1 ActionType 枚举

```python
from enum import Enum

class ActionType(str, Enum):
    SET_FLAG = "set_flag"
    COMPUTE = "compute"
    REJECT = "reject"
    EMIT_ALERT = "emit_alert"
    ASSIGN_CATEGORY = "assign_category"
```

### 2.2 OperatorType 枚举

```python
class OperatorType(str, Enum):
    GRAPH = "GRAPH"
    BINNING = "BINNING"
    SWITCH = "SWITCH"
    SCORECARD = "SCORECARD"
    WEIGHTED_SUM = "WEIGHTED_SUM"
    FORMULA = "FORMULA"
```

### 2.3 结构化 ActionClause

```python
@dataclass
class ActionClause:
    type: ActionType                              # 动作类型（必填）

    # set_flag 专用
    flag: str | None = None                       # flag 名称
    value: Any | None = None                      # flag 值

    # compute 专用
    output: str | None = None                     # 输出变量名
    operator: OperatorType | None = None          # 算子类型
    params: dict[str, Any] = field(default_factory=dict)  # 算子参数
    formula: str | None = None                    # 通用计算公式

    # compute + operator 专用子结构
    query: dict[str, Any] | None = None           # GRAPH 算子查询定义
    aggregation: list[dict] | None = None         # GRAPH 算子聚合定义
    bins: list[dict] | None = None                # BINNING 分箱定义
    branches: list[dict] | None = None            # SWITCH 分支定义
    variables: list[dict] | None = None           # SCORECARD/WEIGHTED_SUM 变量

    # reject / emit_alert 专用
    reason: str | None = None                     # 拒绝/告警原因
    severity: str | None = None                   # 告警级别: INFO | WARNING | CRITICAL

    # assign_category 专用
    category: str | None = None                   # 分类维度值

    # 通用
    output_mapping: dict[str, str] = field(default_factory=dict)  # 输出变量别名映射
```

### 2.4 Step 模型更新

```python
@dataclass
class Step:
    id: str
    name: str
    description: str | None = None
    priority: int = 100
    depends_on: list[str] = field(default_factory=list)

    condition: ConditionClause | None = None      # 触发条件
    action: ActionClause | None = None            # 触发动作（结构化）
    else_action: ActionClause | None = None       # 条件不满足时的备选动作

    enabled: bool = True
```

---

## 三、ActionType 分发逻辑

### 3.1 DAGExecutor._execute_action 分发

```python
async def _execute_action(self, action: ActionClause, context: dict) -> dict:
    match action.type:
        case ActionType.SET_FLAG:
            context[action.flag] = action.value
            return {action.flag: action.value}

        case ActionType.COMPUTE:
            if action.operator:
                operator = OperatorRegistry.get(action.operator.value)
                return await operator.execute(action.params, {}, context)
            elif action.formula:
                result = self._evaluate_formula(action.formula, context)
                return {action.output: result}

        case ActionType.REJECT:
            return {"_rejected": True, "reason": action.reason}

        case ActionType.EMIT_ALERT:
            return {"_alert": {"severity": action.severity, "reason": action.reason}}

        case ActionType.ASSIGN_CATEGORY:
            return {"_category": action.category}
```

### 3.2 OperatorRegistry 扩展

| OperatorType | 算子类 | 说明 |
|-------------|--------|------|
| GRAPH | GraphOperator | 图遍历 + 聚合 |
| BINNING | BinningOperator | 分箱映射 |
| SWITCH | SwitchOperator | 条件分支 |
| SCORECARD | ScorecardOperator | 评分卡 |
| WEIGHTED_SUM | WeightedSumOperator | 加权求和 |
| FORMULA | FormulaOperator | 公式计算 |

---

## 四、与现有模型映射

### 4.1 旧 → 新转换

| 旧字段 | 新字段 | 转换规则 |
|--------|--------|----------|
| `action: str` (算子名) | `ActionClause.type = ActionType.COMPUTE` + `operator = OperatorType(action)` | 字符串 → 枚举 |
| `computation: dict` | `ActionClause.params` | dict → params |
| `RuleThen.action: str` | `ActionClause.type` | 根据 ACTION_* 常量映射 |
| `RuleThen.output: dict` | `ActionClause.output` + `output_mapping` | 拆分 |
| `RuleAction.action_type: str` | `ActionClause.type = ActionType(action_type)` | 字符串 → 枚举 |
| `RuleAction.formula: str` | `ActionClause.formula` | 直接迁移 |
| `RuleAction.operator: str` | `ActionClause.operator = OperatorType(operator)` | 字符串 → 枚举 |
| `ACTION_APPROVE_ELIGIBILITY` | `ActionType.SET_FLAG` + `flag="eligible"` + `value=True` | 常量 → 结构化 |
| `ACTION_REJECT` | `ActionType.REJECT` + `reason=...` | 常量 → 结构化 |
| `ACTION_ALERT` | `ActionType.EMIT_ALERT` + `severity=...` + `reason=...` | 常量 → 结构化 |

### 4.2 7 个 ACTION_* 常量迁移

| 旧常量 | 新表示 |
|--------|--------|
| `ACTION_APPROVE_ELIGIBILITY` | `ActionType.SET_FLAG, flag="eligible", value=True` |
| `ACTION_REJECT_ELIGIBILITY` | `ActionType.SET_FLAG, flag="eligible", value=False` |
| `ACTION_REJECT` | `ActionType.REJECT, reason=...` |
| `ACTION_ALERT` | `ActionType.EMIT_ALERT, severity="WARNING", reason=...` |
| `ACTION_COMPUTE` | `ActionType.COMPUTE, operator=..., params=...` |
| `ACTION_ASSIGN_CATEGORY` | `ActionType.ASSIGN_CATEGORY, category=...` |
| `ACTION_SET_FLAG` | `ActionType.SET_FLAG, flag=..., value=...` |

---

## 五、迁移策略

### 5.1 阶段划分

| 阶段 | 内容 | 验证标准 |
|------|------|----------|
| Phase A | 定义 `ActionType`、`OperatorType` 枚举和结构化 `ActionClause` | 枚举值与 L4 grammar 完全对齐 |
| Phase B | 添加旧 `action: str` → 新 `ActionClause` 的转换函数 | 旧 YAML/JSON 可转换为新格式 |
| Phase C | `DAGExecutor._execute_action` 使用 `match action.type` 分发 | 执行结果与旧逻辑一致 |
| Phase D | 删除 `_execute_legacy_action()` 和 `ACTION_*` 常量 | 所有测试通过 |
| Phase E | 统一四套表示为单一 `ActionClause` | 无重复定义 |

### 5.2 向后兼容

- Phase B-D 期间，`RuleExecutor._execute_action(str, dict)` 保留但标记 deprecated
- 新增 `ActionClause.from_legacy(action_str, output_dict)` 转换方法
- YAML 加载器同时支持旧格式 (`action: "COMPUTE"`) 和新格式 (`action: {type: compute, ...}`)

---

## 六、与 P0-3 (规则模型双分离) 的关系

- P0-3 定义了 `RuleLogicDeclaration.steps[]` 的容器结构
- 本 RFC 定义了 `Step.action` 的内部结构
- 实施顺序：P0-3 先行（容器），本 RFC 紧随（内部结构）
- 两个 RFC 可在同一会话中实施，但需按顺序

---

## 七、验收标准

1. `ActionType` 枚举值与 L4 grammar `action.type` 完全对齐（5 种类型）
2. `OperatorType` 枚举值与 L4 grammar `action.operator` 完全对齐（6 种算子）
3. `ActionClause` 字段与 L4 grammar `steps[].action` 完全对齐
4. 旧 `ACTION_*` 常量全部迁移到 `ActionType` 枚举
5. `_execute_legacy_action()` 方法删除
6. `DAGExecutor._execute_action` 使用 `match action.type` 分发
7. 四套 action 表示统一为单一 `ActionClause`
8. 所有现有测试通过
9. mypy --strict + ruff check 无新增错误
