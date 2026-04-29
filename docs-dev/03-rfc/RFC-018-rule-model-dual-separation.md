# RFC-018: 规则模型双分离 — RuleDefinitionDeclaration + RuleLogicDeclaration

> **状态**: implemented
> **父 RFC**: [RFC-010](./RFC-010-phase2-roadmap.md)
> **创建日期**: 2026-04-29
> **最后更新**: 2026-04-29
> **实施进度**: Phase A ✅ Phase B ✅ Phase C ✅ Phase D ✅ Phase E ✅
> **作者**: the-butterfly
> **评审截止**: 待定
> **关联文档**: [RFC-011](./RFC-011-rule-executor-dag.md) · [RFC-014](./RFC-014-rule-orchestration-system.md) · [RFC-016](./RFC-016-rule-orchestration-gap-analysis.md) · [L4 Grammar](../../02-design/schema/L1-L4-declarations.md) · [规则引擎设计](../../02-design/rule-engine/README.md) · [ADR-008 D8/D12](../../04-adr/ADR-008-phase1-4-review-decisions.md)

---

## 摘要

将当前一体化的 `RuleDefinition` 模型拆分为 `RuleDefinitionDeclaration`（规则定义）和 `RuleLogicDeclaration`（规则逻辑）两个独立模型，与 L4 grammar 的 `rule_definitions` + `rule_logics` 双层结构对齐。

**核心目标**：一个规则定义可关联多个规则逻辑（不同行业/场景），提升规则复用性和可维护性。

---

## 一、现状与痛点

### 1.1 当前模型结构

项目中存在 **三套并行的规则模型**，术语和结构不统一：

| 层级 | 模型 | 结构 | 文件 |
|------|------|------|------|
| Schema 层 | `RuleDefinition` | 一体模型：when/then/else_ + logic_ids 前向兼容字段 | `core/schema/models.py` |
| Engine 层 | `RuleGroupDefinition` + `RuleStep` | 两级分层：框架 + 实例 | `engine/rule/models.py` |
| Semantic Space 层 | `RuleGroupDefinition` + `RuleStep` | 同 Engine 层 | `core/semantic_space/rule_models.py` |

### 1.2 核心问题

| 问题 | 表现 | 影响 |
|------|------|------|
| 定义与逻辑耦合 | `RuleDefinition` 包含 when/then/else_，定义和逻辑混为一体 | 无法为同一规则定义配置不同行业逻辑 |
| 三套模型并存 | Schema/Engine/SemanticSpace 三处各有规则模型 | 术语混乱、转换逻辑分散 |
| logic_ids 前向兼容不完整 | `RuleDefinition.logic_ids` 已添加但无实际消费逻辑 | 半成品状态 |
| 与 L4 grammar 不对齐 | L4 要求 `rule_definitions` + `rule_logics` 分离 | 代码偏离设计规范 |

### 1.3 设计决策溯源

- **L4 grammar 设计决策 #1**：选择规则定义与规则逻辑分离，理由是"一个定义可关联多个逻辑（不同行业/场景），提升复用性"
- **规则引擎设计决策 D8**：`RuleDefinitionDeclaration` + `RuleLogicDeclaration` 替代一体模型
- **ADR-008 D8**：确认双分离为关键设计决策
- **ADR-008 D12**：P0-3 和 P1-1 涉及核心数据模型变更，需先写 RFC 冻结设计

---

## 二、目标模型定义

### 2.1 RuleDefinitionDeclaration

对应 L4 grammar `rule_definitions[]`，定义规则的"对谁、输入什么、输出什么"：

```python
@dataclass
class RuleDefinitionDeclaration:
    name: str                                    # 规则定义名，全局唯一
    description: str | None = None
    type: str = "constraint"                     # constraint | inference | alert | decision
    priority: int = 100

    applies_to: AppliesToConfig                  # 规则适用对象
    preconditions: list[Precondition] = field(default_factory=list)
    inputs: list[IOElement] = field(default_factory=list)
    outputs: list[IOElement] = field(default_factory=list)

    overrides: str | None = None                 # 覆盖 L3 overridable 指标
    applicability: Applicability | None = None   # 六维度适用性描述

    enabled: bool = True
```

### 2.2 RuleLogicDeclaration

对应 L4 grammar `rule_logics[]`，定义"怎么算"：

```python
@dataclass
class RuleLogicDeclaration:
    name: str                                    # 规则逻辑名，全局唯一
    description: str | None = None
    type: str = "decision_table"                 # decision_table | scorecard | switch | binning | graph_op | custom
    steps: list[Step] = field(default_factory=list)  # 步骤序列，支持 DAG 依赖

    definition_ref: str = ""                     # 引用 RuleDefinitionDeclaration.name
    enabled: bool = True
```

### 2.3 关联关系

```
RuleDefinitionDeclaration 1──N RuleLogicDeclaration
     (name)                      (definition_ref → name)
```

- 一个 `RuleDefinitionDeclaration` 可关联多个 `RuleLogicDeclaration`
- `RuleLogicDeclaration.definition_ref` 引用 `RuleDefinitionDeclaration.name`
- 执行时，根据实体分类选择匹配的 `RuleLogicDeclaration`

### 2.4 Applicability 六维度

```python
@dataclass
class Applicability:
    when_text: str | None = None
    why_text: str | None = None
    boundary_text: str | None = None
    outcome_text: str | None = None
    prereq_text: str | None = None
    exception_text: str | None = None
```

---

## 三、与现有模型映射

### 3.1 Schema 层迁移

| 旧模型 (core/schema/models.py) | 新模型 | 迁移动作 |
|------|------|------|
| `RuleDefinition` | 拆分为 `RuleDefinitionDeclaration` + `RuleLogicDeclaration` | 重写 |
| `RuleDefinition.when` | → `RuleLogicDeclaration.steps[].condition` | 字段迁移 |
| `RuleDefinition.then` | → `RuleLogicDeclaration.steps[].action` | 字段迁移 |
| `RuleDefinition.else_` | → `RuleLogicDeclaration.steps[].else_action` | 字段迁移 |
| `RuleDefinition.scope` | → `RuleDefinitionDeclaration.applies_to` | 语义对齐 |
| `RuleDefinition.logic_ids` | → `RuleLogicDeclaration.definition_ref` (反向引用) | 关系反转 |
| `RuleStep` | → `RuleLogicDeclaration.steps[]` 元素类型 | 保留并增强 |
| `RuleWhen` | → Step 内 `condition` 字段 | 保留 |
| `RuleThen` | → Step 内 `action` 字段（结构化） | 重写为 ActionClause |

### 3.2 Engine 层迁移

| 旧模型 (engine/rule/models.py) | 新模型 | 迁移动作 |
|------|------|------|
| `RuleGroupDefinition` | → `RuleDefinitionDeclaration` | 重命名 + 字段对齐 |
| `RuleStep` | → `RuleLogicDeclaration.steps[]` | 保留，增加 `definition_ref` |
| `ActionClause` | → Step 内 `action` 字段 | 保留 |
| `ConditionClause` | → Step 内 `condition` 字段 | 保留 |

### 3.3 Semantic Space 层迁移

| 旧模型 (core/semantic_space/rule_models.py) | 新模型 | 迁移动作 |
|------|------|------|
| `RuleGroupDefinition` | → `RuleDefinitionDeclaration` | 与 Engine 层统一 |
| `RuleStep` | → `RuleLogicDeclaration.steps[]` | 与 Engine 层统一 |
| `RuleAction` | → Step 内 `action` 字段 | 合并到 ActionClause |

---

## 四、迁移策略

### 4.1 阶段划分

| 阶段 | 内容 | 验证标准 |
|------|------|----------|
| Phase A | 定义新模型 `RuleDefinitionDeclaration` + `RuleLogicDeclaration`，放在 `core/schema/models.py` | 新模型字段与 L4 grammar 完全对齐 |
| Phase B | 添加旧模型 → 新模型的适配器/转换函数 | 旧 YAML 可加载为新模型 |
| Phase C | Engine 层消费新模型，`RuleExecutor` 使用 `RuleLogicDeclaration.steps` | 执行结果与旧模型一致 |
| Phase D | Semantic Space 层消费新模型，统一三套模型为一套 | 三处模型代码统一 |
| Phase E | 废弃旧模型，添加 deprecation warning | 所有测试通过，无旧模型直接引用 |

### 4.2 向后兼容

- Phase B-E 期间，旧 `RuleDefinition` 保留但标记 `@deprecated`
- 新增 `from_legacy()` 类方法实现旧→新转换
- YAML 加载器同时支持旧格式和新格式
- API 端点同时返回旧格式和新格式（通过 Accept header 或 version 参数）

### 4.3 存储层影响

- SQLite: `rule_definitions` 表 + `rule_logics` 表（替代原 `rules` 表）
- KuzuDB: `RuleDefinitionNode` + `RuleLogicNode` + `DEFINED_IN` 边
- 迁移脚本: 旧 `rules` 表数据拆分到两个新表

---

## 五、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 三套模型统一工作量大 | Engine + SemanticSpace + Schema 三处需同步修改 | 分阶段执行，Phase B 适配器先行 |
| YAML 格式变更影响用户 | 现有 YAML 规则文件需迁移 | 双格式加载器 + 自动迁移脚本 |
| API 响应格式变更 | 前端需适配 | 版本化 API + 兼容层 |
| 执行器逻辑变更 | RuleExecutor 需从新模型读取 steps | Phase C 充分回归测试 |

---

## 六、与 P1-1 (Step.action 结构化) 的关系

P0-3 和 P1-1 是紧密关联的两个 RFC：

- P0-3 定义了 `RuleLogicDeclaration.steps[]` 的容器结构
- P1-1 定义了 `Step.action` 的内部结构（从 `str + dict` → 结构化 `ActionClause`）
- 建议实施顺序：P0-3 先行（容器结构），P1-1 紧随（内部结构）

---

## 七、验收标准

1. `RuleDefinitionDeclaration` 字段与 L4 grammar `rule_definitions` 完全对齐
2. `RuleLogicDeclaration` 字段与 L4 grammar `rule_logics` 完全对齐
3. 旧 `RuleDefinition` YAML 可通过适配器加载为新模型
4. `RuleExecutor` 使用新模型执行，结果与旧模型一致
5. 三套模型统一为一套，无重复定义
6. 所有现有测试通过
7. mypy --strict + ruff check 无新增错误
