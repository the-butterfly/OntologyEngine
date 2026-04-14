# RFC-011: RuleExecutor DAG 引擎

> **状态**: draft
> **父 RFC**: [RFC-010](./RFC-010-phase2-roadmap.md)
> **创建日期**: 2026-04-14
> **作者**: the-butterfly
> **评审截止**: 待定

## 动机

Phase 1 的 RuleExecutor 按 `priority` 顺序执行，每条 Rule Logic 内部是 `when` + `then_action` / `else_action` 单分支判断。这在简单场景下够用，但以下需求无法满足：

1. **跨规则依赖**: Rule B 需要 Rule A 的输出作为输入，但两者是不同 rule_definition 的 logic_instance
2. **多步 DAG**: 一个逻辑实例需要多个步骤按拓扑顺序执行（A → B → C）
3. **算子组合**: 同一规则需要 SCOREBOARD + DECISION_TABLE + COMPUTE 串联使用

Canonical grammar 中 `RuleStep` 模型（`id/depends_on/condition/action/operator/computation/output_field`）已在 `models.py` 实现，但 `RuleExecutor` 尚未使用。

## 设计目标

1. **向后兼容**: 现有 `when/then_action/else_action` 格式仍然有效，作为 DAG 的单节点特殊情况
2. **显式依赖**: `depends_on` 字段声明步骤间的数据依赖关系
3. **拓扑排序**: 按 `depends_on` 构建 DAG，保证执行顺序
4. **循环检测**: 执行前检测环形依赖并报错

## 数据模型

```python
class RuleStep(BaseModel):
    id: str
    name: str | None = None
    description: str | None = None
    priority: int = 100
    depends_on: list[str] = []        # 前置步骤 ID 列表
    condition: RuleWhen | None = None  # 执行条件
    action: dict | None = None        # 动作类型（set_flag / compute / alert / reject）
    operator: str | None = None       # 算子类型（SWITCH / SCOREBOARD / DECISION_TABLE）
    computation: str | None = None     # 计算表达式
    output_field: str | None = None   # 输出字段名
    enabled: bool = True
```

### 与现有格式的映射

```yaml
# Phase 1 现有格式（向下兼容）
- id: RL001_logic_1
  when:
    expression: "credit_score >= 60"
  then_action:
    action_type: set_flag
    output: {eligible: true}

# Phase 2 DAG 格式（等价的 steps[] 表示）
- id: RL001_logic_1
  steps:
    - id: step_1
      condition:
        expression: "credit_score >= 60"
      action:
        type: set_flag
      output_field: eligible
      output_value: true
```

## 执行流程

```
输入: RuleDefinitionV2 + RuleLogic + Entity Context
         │
         ▼
  1. 解析 steps[]（若存在）或降级为 when/then_action 单步
         │
         ▼
  2. 构建 DAG：节点 = steps，边 = depends_on
         │
         ▼
  3. 拓扑排序（Kahn 算法）
         │
         ▼
  4. 循环检测（DFS）→ 有环则报错
         │
         ▼
  5. 按拓扑序执行每个 step
         │
    ┌────┴────┐
    │         │
 condition   condition
  false       true
    │         │
    ▼         ▼
 else_action  action
    │         │
    └────┬────┘
         ▼
  6. 聚合 outputs，输出最终决策
```

## 关键设计决策

### Q1: DAG 执行与现有 priority 字段的关系？

**决策**: `depends_on` 优先于 `priority`。若 step A depends_on B，则 A 总在 B 之后执行，无论 priority 高低。`priority` 仅在无依赖时决定同层 step 的相对顺序。

### Q2: 循环依赖如何处理？

**决策**: 执行前检测。若检测到环，执行中止并抛出 `CircularDependencyError`，包含环形路径信息。

### Q3: 中间结果如何在 steps 间传递？

**决策**: RuleExecutionContext 内部维护 `outputs` 字典，每个 step 执行后将 `{step_id: result}` 写入 context，后续 step 可通过 `inputs` 字段引用：`"inputs": ["step_1.result"]`

## 开放问题

| 问题 | 选项 | 推荐 |
|------|------|------|
| DAG 可视化输出格式？ | A) JSON DAG B) DOT C) Mermaid | A) JSON，兼容前端渲染 |
| 循环依赖是 ERROR 还是 WARN？ | A) ERROR（阻断执行）B) WARN（记录后跳过） | A) ERROR |
| 是否需要 DAG 执行历史记录？ | A) 是（用于追溯）B) 否 | A) 复用 rule_execution_log |

## 实现范围

### 包含
- [ ] `RuleExecutorV2` 类：DAG 拓扑排序执行
- [ ] 循环依赖检测算法
- [ ] 中间结果传递（RuleExecutionContext 扩展）
- [ ] 降级路径：若无 steps[]，降级为现有 when/then_action 执行

### 不包含
- 算子增强（SCOREBOARD / DECISION_TABLE 已在 Phase 1 实现）
- 图存储相关（RFC-012）
- MCP 工具相关（RFC-013）

## 相关文档

- **ADR-008** — [Rule 模型统一](../architecture/decisions/008-rule-model-unification.md)
- **ADR-007** — [L3-L4 计算边界](../architecture/decisions/007-l3-l4-computation-boundary.md)
- **models.py** — `RuleStep` 模型定义（`ontology_engine/core/schema/models.py`）
