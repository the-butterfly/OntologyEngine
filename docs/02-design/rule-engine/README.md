# 规则引擎设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: [01-overview/05-concepts.md](../../01-overview/05-concepts.md) | **last_verified**: 2026-04-19

---

## 目的

本文档是规则引擎重写的设计入口，定义规则引擎从当前优先级排序执行到 DAG 执行的完整架构，协调 DAG 执行、逻辑边按需计算、管道状态持久化三个子系统的设计。

## 解决的问题

| # | 问题 | 当前表现 | 重写后解决方式 |
|---|------|----------|---------------|
| 1 | **无 DAG 执行** | `RuleExecutor.execute_dimension()` 按 `priority` 降序排序执行规则，步骤间依赖靠优先级隐式保证 | `DAGBuilder` 从 `Step.depends_on` 构建依赖图，拓扑排序 + 并行执行无依赖步骤 |
| 2 | **无回滚机制** | 规则执行失败仅捕获异常继续执行，无 snapshot/restore | `RuleTransaction` 提供 context 快照，失败时回滚到一致状态 |
| 3 | **逻辑边缺失** | 推理关系（`inference` 类型）无按需计算机制，事实数据变更不会触发重新推导 | 三类逻辑边（business/inference/traceability），事实边变更触发推理边重算 |
| 4 | **无管道状态持久化** | 规则执行结果仅在内存中，进程崩溃即丢失 | `PipelineRun` + `ExecutionStepSnapshot` 持久化，支持断点续跑 |
| 5 | **硬编码动作** | `RuleExecutor` 内嵌 7 个 `ACTION_*` 常量和 `_execute_legacy_action()` 方法 | 全部迁移到 `OperatorRegistry`，动作类型由 L4 grammar `action.type` 驱动 |
| 6 | **与 L4 grammar 不对齐** | 当前代码使用 `RuleDefinition.when/then/else_/scope` 模型，与 L4 `rule_definitions + rule_logics` 分离结构不匹配 | 重写为 `RuleDefinitionDeclaration` + `RuleLogicDeclaration` 双模型 |

---

## 架构概览

```
┌──────────────────────────────────────────────────────────────────────┐
│                        RuleEngine (重写)                             │
│                                                                      │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────────┐  │
│  │ DAGBuilder   │   │ DAGExecutor  │   │ LogicalEdgeEngine        │  │
│  │              │   │              │   │                          │  │
│  │ depends_on   │   │ 拓扑分层     │   │ business 边 (事实)       │  │
│  │ → 依赖图     │   │ → 并行执行   │   │ inference 边 (推理)      │  │
│  │ → 环检测     │   │ → Semaphore  │   │ traceability 边 (溯源)   │  │
│  │ → 拓扑排序   │   │ → 快照回滚   │   │ → 按需计算 + 缓存       │  │
│  └─────────────┘   └──────────────┘   └──────────────────────────┘  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ PipelineStateManager                                            │ │
│  │                                                                 │ │
│  │ PipelineRun (管道运行记录)                                       │ │
│  │ ExecutionStepSnapshot (步骤快照)                                 │ │
│  │ 状态机: PENDING → RUNNING → COMPLETED / FAILED                   │ │
│  │ 断点续跑 + 审计追踪                                              │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────────┐  │
│  │ OperatorRegistry │   │ ExpressionEngine  │   │ RuleTransaction  │  │
│  │ (6+1 算子)       │   │ (L0/L1 两级)      │   │ (快照/回滚)      │  │
│  └─────────────────┘   └──────────────────┘   └──────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 子系统关系

```
SchemaLoader
  ↓ 解析 L4 grammar
  ↓ rule_definitions + rule_logics
RuleEngine
  ├─ DAGBuilder ← rule_logics.steps[].depends_on
  ├─ DAGExecutor ← DAGBuilder 产出 + OperatorRegistry + ExpressionEngine
  ├─ LogicalEdgeEngine ← DAGExecutor 推理结果 → inference 边写入
  └─ PipelineStateManager ← DAGExecutor 步骤快照 → 持久化
```

---

## 关键设计决策

| # | 决策 | 选择 | 备选 | 理由 | 对齐参考 |
|---|------|------|------|------|----------|
| D1 | 执行模型 | DAG 拓扑排序 + 并行执行 | 优先级排序 | `depends_on` 显式声明依赖，消除优先级隐式耦合 | L4 grammar `Step.depends_on` |
| D2 | 并行策略 | `asyncio.gather` + `Semaphore` | 线程池 | 规则执行以 I/O 为主（存储读写），asyncio 足够 | Cognee `run_tasks_parallel` |
| D3 | 回滚机制 | Context 快照 + 事务恢复 | 数据库事务 | 规则执行涉及内存 context + 存储写入，需两层回滚 | 事务模式 |
| D4 | 逻辑边分类 | business / inference / traceability | 无分类 | KAG IND# 证明逻辑边分类对规则引擎过滤至关重要 | KAG `IND#belongTo` |
| D5 | 逻辑边触发 | 事实边变更 → 推理边重算 | 全量重算 | 增量触发效率远高于全量重算 | KAG STRUCTURE 块 |
| D6 | 管道状态 | PipelineRun + StepSnapshot | 仅日志 | 支持断点续跑和审计追踪 | Cognee `PipelineRun` |
| D7 | 动作模型 | L4 `action.type` 驱动 + OperatorRegistry | 硬编码 ACTION_* | 与 L4 grammar 对齐，可扩展 | L4 grammar `action.type` |
| D8 | 规则定义与逻辑分离 | `RuleDefinitionDeclaration` + `RuleLogicDeclaration` | 一体模型 | 一个定义可关联多个逻辑（不同行业/场景），提升复用性 | L4 grammar 设计决策 #1 |

---

## 与 L4 Grammar 对齐

规则引擎重写的核心约束：**所有执行语义必须与 L4 grammar 定义一致**。

### 对齐映射

| L4 Grammar 元素 | 规则引擎组件 | 说明 |
|-----------------|-------------|------|
| `rule_definitions` | `RuleDefinitionDeclaration` 模型 | 规则定义：作用域、输入输出、适用性 |
| `rule_logics` | `RuleLogicDeclaration` 模型 | 规则逻辑：步骤序列、算子类型 |
| `steps[].depends_on` | `DAGBuilder` 输入 | 步骤依赖声明 → DAG 边 |
| `steps[].condition` | `ExpressionEvaluator` 输入 | 条件表达式评估 |
| `steps[].action.type` | `OperatorRegistry` 路由 | 动作类型 → 算子分发 |
| `steps[].action.operator` | `OperatorRegistry.get()` | 算子名 → 算子实例 |
| `applies_to.fact_objects` | 规则筛选器 | 实体类型过滤 |
| `applies_to.categories` | 规则筛选器 | 分类维度过滤 |
| `preconditions` | 前置条件检查 | 不满足时 reject 或跳过 |
| `overrides` | L3 覆盖机制 | 覆盖 overridable 指标计算逻辑 |
| `applicability` | 规则可解释性 | 六维度描述，不参与执行但参与解释 |

### 不对齐项（偏差）

| 偏差 | 当前代码 | L4 grammar 要求 | 迁移计划 |
|------|---------|----------------|---------|
| 规则模型一体 | `RuleDefinition` 包含 when/then/else_ | `rule_definitions` + `rule_logics` 分离 | 重写为双模型 |
| 动作硬编码 | `ACTION_APPROVE_ELIGIBILITY` 等 7 个常量 | `action.type` 枚举 (set_flag/compute/reject/emit_alert/assign_category) | 迁移到 OperatorRegistry |
| 优先级排序 | `sorted(rules, key=lambda r: -r.priority)` | `depends_on` DAG 拓扑排序 | 实现 DAGBuilder |
| 无步骤快照 | `RuleResult` 仅内存 | `ExecutionStepSnapshot` 持久化 | 实现 PipelineStateManager |
| scope 硬编码 | `rule.scope.entity_types` | `applies_to.fact_objects + categories` | 对齐 L4 grammar |

---

## 子文档索引

| 文档 | 内容 | 状态 |
|------|------|------|
| [dag-execution.md](./dag-execution.md) | DAG 执行设计：DAGBuilder、并行执行、快照回滚 | draft |
| [logical-edges.md](./logical-edges.md) | 逻辑边按需计算：三类边、触发机制、缓存策略 | draft |
| [pipeline-state.md](./pipeline-state.md) | 管道状态持久化：PipelineRun、StepSnapshot、断点续跑 | draft |

---

## 参考文档

| 主题 | 文档 |
|------|------|
| L4 grammar 定义 | [L1-L4-declarations.md](../schema/L1-L4-declarations.md) |
| 核心概念 | [05-concepts.md](../../01-overview/05-concepts.md) |
| 模块架构 | [04-modules.md](../../01-overview/04-modules.md) |
| 旧规则引擎设计 | [04-rule-engine-design.md](./04-rule-engine-design.md) |
| KAG Expert Rules DSL | [KAG-Schema.md](file:///Users/dingxuxu/Projects/github/GraphRAGs/KAG-Docs/KAG-Schema.md) |
| Cognee Pipeline Task | [task.py](file:///Users/dingxuxu/Projects/github/GraphRAGs/cognee/cognee/modules/pipelines/tasks/task.py) |
| m_flow Procedure | [Procedure.py](file:///Users/dingxuxu/Projects/github/GraphRAGs/m_flow/m_flow/core/domain/models/Procedure.py) |
