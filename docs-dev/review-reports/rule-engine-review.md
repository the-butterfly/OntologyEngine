# 规则引擎设计评审报告

> **status**: draft | **phase**: rewrite | **review_date**: 2026-04-19 | **reviewer**: Agent

---

## 目的

对规则引擎当前实现与目标设计之间的偏差进行系统性评审，标记所有偏差项，记录重写决策和参考项目对齐情况。

## 解决的问题

| # | 问题 | 表现 | 本文如何解决 |
|---|------|------|-------------|
| 1 | **偏差不透明** | 当前代码与设计文档的偏差散落在各处注释中 | 系统性梳理所有偏差，统一记录 |
| 2 | **参考项目洞察未落地** | KAG/Cognee/m_flow 的设计洞察仅停留在概念层 | 逐项对齐参考项目，标注落地位置 |
| 3 | **重写优先级不清** | 6 个偏差项无优先级排序 | 按影响范围和依赖关系排序 |

---

## 评审流程

```
Overview 对齐 → Baseline 审查 → 参考项目对齐 → 偏差标记 → 重写方案
```

---

## 1. Overview 对齐

### 概念层对齐

| 05-concepts.md 概念 | 当前代码 | 对齐状态 | 偏差说明 |
|---------------------|---------|---------|---------|
| L4 Business Logic: Rule Definition + Rule Logic 分离 | `RuleDefinition` 一体模型 | ❌ 不对齐 | 当前 `RuleDefinition` 包含 when/then/else_，与 L4 `rule_definitions + rule_logics` 分离结构不匹配 |
| 规则依赖 DAG 自动拓扑排序执行 | `sorted(rules, key=lambda r: -r.priority)` | ❌ 不对齐 | 优先级排序替代 DAG，步骤间依赖靠优先级隐式保证 |
| ExecutionStepSnapshot 全链路追溯 | `RuleResult` 仅内存 | ❌ 不对齐 | 无持久化快照，无法断点续跑 |
| 逻辑边按需计算 | 无 `logical_type` 区分 | ❌ 不对齐 | 所有关系同等对待，推理边无按需计算 |
| 规则适用性六维度 | `rule.scope` 仅 entity_types | ⚠️ 部分对齐 | 缺少 categories 过滤和 applicability 六维度 |
| 规则生命周期管理 | 无生命周期模型 | ❌ 不对齐 | 无 active/deprecated/supersedes 状态管理 |

### 模块层对齐

| 04-modules.md 定义 | 当前代码 | 对齐状态 | 偏差说明 |
|-------------------|---------|---------|---------|
| RuleEngine: DAG 解析、拓扑执行、回滚 | 仅优先级排序执行 | ❌ 不对齐 | DAGBuilder 和 RuleTransaction 未实现 |
| OperatorRegistry: 算子发现与注册 | ✅ 已实现 | ✅ 对齐 | 16 个算子已注册 |
| ExpressionEngine: L0/L1 两级安全执行 | simpleeval + asteval fallback | ⚠️ 部分对齐 | 无独立 ASTSandboxExecutor |
| MetricEngine → RuleEngine 直接调用 | 无 MetricEngine 集成 | ❌ 不对齐 | 当前 RuleExecutor 无 MetricEngine 依赖 |

---

## 2. Baseline 审查

### 旧设计文档 (04-rule-engine-design.md) vs 当前代码

| 旧设计组件 | 设计描述 | 当前实现 | 偏差 |
|-----------|---------|---------|------|
| RuleParser | 解析 YAML 规则为内部模型 | `SchemaLoader` 承担部分职责 | ⚠️ 职责分散 |
| DAGBuilder | 构建规则依赖图 | ❌ 未实现 | ❌ 严重偏差 |
| ExpressionEngine | L0 simpleeval + L1 AST 沙箱 | simpleeval + asteval fallback | ⚠️ 部分偏差 |
| OperatorRegistry | 算子注册与执行 | ✅ 已实现 | ✅ 对齐 |
| RuleExecutor | DAG 拓扑执行 | 优先级排序执行 | ❌ 严重偏差 |
| rule_transaction | snapshot/restore 回滚 | ❌ 未实现 | ❌ 严重偏差 |
| CategorizationEngine | L2 归类复用 L4 规则引擎 | ❌ 未实现 | ❌ 偏差 |

### 当前代码问题清单

| # | 文件 | 问题 | 严重度 | 说明 |
|---|------|------|--------|------|
| C1 | [executor.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/rule/executor.py) | 硬编码 7 个 `ACTION_*` 常量 | 高 | 与 L4 `action.type` 枚举不对齐，不可扩展 |
| C2 | [executor.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/rule/executor.py) | `_execute_legacy_action()` 内嵌业务逻辑 | 高 | 信用评分、授信额度等业务逻辑硬编码在引擎中 |
| C3 | [executor.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/rule/executor.py) | `execute_dimension()` 按 priority 排序 | 高 | 不支持 DAG 依赖，步骤间依赖靠优先级隐式保证 |
| C4 | [executor.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/rule/executor.py) | 无回滚机制 | 中 | 规则执行失败仅捕获异常继续执行 |
| C5 | [executor.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/rule/executor.py) | 无管道状态持久化 | 中 | 执行结果仅在内存中 |
| C6 | [evaluator.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/rule/evaluator.py) | 条件评估逻辑正确 | — | ✅ 无问题 |
| C7 | [operators/base.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/rule/operators/base.py) | OperatorRegistry 设计合理 | — | ✅ 无问题 |
| C8 | [executor.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/rule/executor.py) | `_calculate_credit_score()` 硬编码权重 | 高 | 业务规则应在 YAML 定义，非代码中 |
| C9 | [executor.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/rule/executor.py) | `_get_credit_grade()` 硬编码阈值表 | 高 | 同上 |
| C10 | [executor.py](file:///Volumes/Extension/Projects/CodeDev/OntologyEngine/ontology_engine/engine/rule/executor.py) | `execute_dimension()` 内嵌决策逻辑 | 高 | 最终决策逻辑硬编码在引擎中 |

---

## 3. 参考项目对齐

### KAG 对齐

| KAG 概念 | OntologyEngine 目标 | 对齐方式 | 落地文档 |
|----------|-------------------|---------|---------|
| `IND#belongTo` 逻辑边 | `logical_type: inference` | L1 RelationDeclaration.logical_type | [logical-edges.md](../../02-design/rule-engine/logical-edges.md) |
| STRUCTURE 块 | `Step.depends_on` + `action.operator: GRAPH` | DAG 步骤中的 GRAPH 算子声明事实边遍历模式 | [dag-execution.md](../../02-design/rule-engine/dag-execution.md) |
| CONSTRAINT 块 | `Step.condition` + `action.operator: FORMULA` | 条件表达式 + 公式计算 | [dag-execution.md](../../02-design/rule-engine/dag-execution.md) |
| `group(s,o).count(d)` | `GRAPH` 算子 + `aggregation: count` | 聚合统计 | [dag-execution.md](../../02-design/rule-engine/dag-execution.md) |
| 实时计算生成逻辑边 | 按需计算 + 缓存 + 事件触发 | 事实边变更 → 推理边重算 | [logical-edges.md](../../02-design/rule-engine/logical-edges.md) |
| Expert Rules DSL | L4 `rule_logics` YAML 声明 | 结构化配置 + 表达式，非严格 DSL | [L1-L4-declarations.md](../../02-design/schema/L1-L4-declarations.md) |

### Cognee 对齐

| Cognee 概念 | OntologyEngine 目标 | 对齐方式 | 落地文档 |
|-------------|-------------------|---------|---------|
| `Task` 三层结构 | `Step` + `DAGNode` + `ExecutionContext` | 声明式步骤 + 运行时绑定 | [dag-execution.md](../../02-design/rule-engine/dag-execution.md) |
| `batch_size` | `Semaphore(max_concurrency)` | 并发控制 | [dag-execution.md](../../02-design/rule-engine/dag-execution.md) |
| `enriches` | `ErrorStrategy.CONTINUE` | 失败时继续 | [dag-execution.md](../../02-design/rule-engine/dag-execution.md) |
| `Drop` 信号 | `StepResult(skipped=True)` | 跳过下游 | [dag-execution.md](../../02-design/rule-engine/dag-execution.md) |
| `PipelineRun` | `PipelineRun` + `ExecutionStepSnapshot` | 管道状态持久化 | [pipeline-state.md](../../02-design/rule-engine/pipeline-state.md) |
| `PipelineRunStatus` | 5 状态枚举 | PENDING/RUNNING/COMPLETED/FAILED/PARTIALLY_COMPLETED | [pipeline-state.md](../../02-design/rule-engine/pipeline-state.md) |
| `PipelineRunInfo` 事件 | 状态变更事件 | Started/Yield/Completed/Errored | [pipeline-state.md](../../02-design/rule-engine/pipeline-state.md) |
| `source_pipeline/source_task/source_content_hash` | 溯源字段 | PipelineRun 和 StepSnapshot 携带溯源信息 | [pipeline-state.md](../../02-design/rule-engine/pipeline-state.md) |

### m_flow 对齐

| m_flow 概念 | OntologyEngine 目标 | 对齐方式 | 落地文档 |
|-------------|-------------------|---------|---------|
| `Procedure` 版本管理 | 推理边版本链 + `supersedes` | 新推理边替代旧推理边 | [logical-edges.md](../../02-design/rule-engine/logical-edges.md) |
| `Procedure.status` (active/deprecated) | 规则生命周期 | RuleDefinitionDeclaration.status | [L1-L4-declarations.md](../../02-design/schema/L1-L4-declarations.md) |
| `Procedure.confidence` (high/low) | 规则置信度 | RuleDefinitionDeclaration.confidence | [L1-L4-declarations.md](../../02-design/schema/L1-L4-declarations.md) |
| `Procedure.evidence_refs` | 推理边溯源 | ExecutionStepSnapshot.trace_to | [pipeline-state.md](../../02-design/rule-engine/pipeline-state.md) |
| `ContextPack` 六维度 | `applicability` 六维度 | when/why/boundary/outcome/prereq/exception | [L1-L4-declarations.md](../../02-design/schema/L1-L4-declarations.md) |
| `Procedure.write_decision/write_reason` | 规则写入决策 | PipelineRun.run_config 记录 | [pipeline-state.md](../../02-design/rule-engine/pipeline-state.md) |

---

## 4. 偏差标记

### 严重偏差（必须重写）

| # | 偏差 | 当前 | 目标 | 影响范围 | 重写文档 |
|---|------|------|------|---------|---------|
| D1 | 规则模型一体 | `RuleDefinition` (when/then/else_) | `RuleDefinitionDeclaration` + `RuleLogicDeclaration` | SchemaLoader, RuleExecutor, 所有调用方 | [README.md](../../02-design/rule-engine/README.md) |
| D2 | 优先级排序执行 | `sorted(rules, key=lambda r: -r.priority)` | `DAGBuilder` + 拓扑排序 + 并行执行 | RuleExecutor 核心流程 | [dag-execution.md](../../02-design/rule-engine/dag-execution.md) |
| D3 | 硬编码动作 | 7 个 `ACTION_*` + `_execute_legacy_action()` | `action.type` 枚举 + `OperatorRegistry` | RuleExecutor 动作分发 | [dag-execution.md](../../02-design/rule-engine/dag-execution.md) |
| D4 | 无逻辑边分类 | 所有关系同等对待 | `business` / `inference` / `traceability` | 存储层、查询引擎、规则引擎 | [logical-edges.md](../../02-design/rule-engine/logical-edges.md) |

### 中等偏差（需增强）

| # | 偏差 | 当前 | 目标 | 影响范围 | 重写文档 |
|---|------|------|------|---------|---------|
| D5 | 无回滚机制 | 异常捕获继续执行 | `RuleTransaction` snapshot/restore | RuleExecutor 错误处理 | [dag-execution.md](../../02-design/rule-engine/dag-execution.md) |
| D6 | 无管道状态持久化 | 内存中 `AnalysisResult` | `PipelineRun` + `ExecutionStepSnapshot` | 执行可靠性、审计 | [pipeline-state.md](../../02-design/rule-engine/pipeline-state.md) |
| D7 | scope 硬编码 | `rule.scope.entity_types` | `applies_to.fact_objects + categories` | 规则筛选 | [dag-execution.md](../../02-design/rule-engine/dag-execution.md) |

### 轻微偏差（可后续迭代）

| # | 偏差 | 当前 | 目标 | 影响范围 |
|---|------|------|------|---------|
| D8 | ExpressionEngine 无独立 AST 沙箱 | simpleeval + asteval fallback | 独立 `ASTSandboxExecutor` | 表达式安全性 |
| D9 | 无规则生命周期管理 | 无 active/deprecated/supersedes | 规则版本链管理 | 规则运维 |
| D10 | 无 MetricEngine 集成 | RuleExecutor 无 MetricEngine 依赖 | 直接调用 MetricEngine 预计算指标 | L3-L4 协同 |

---

## 5. 重写方案

### 优先级排序

| 优先级 | 偏差 | 依赖 | 工作量 | 理由 |
|--------|------|------|--------|------|
| P0 | D1: 规则模型双分离 | 无 | 大 | 所有其他重写的基础，必须先完成 |
| P0 | D2: DAG 执行 | D1 | 大 | 核心执行模型，影响所有规则执行 |
| P0 | D3: 动作模型对齐 | D1 | 中 | 与 D2 同步完成，消除硬编码 |
| P1 | D5: 回滚机制 | D2 | 中 | 依赖 DAG 层级概念 |
| P1 | D4: 逻辑边分类 | D1 | 中 | 需要新的 RuleLogicDeclaration 模型 |
| P1 | D7: applies_to 对齐 | D1 | 小 | 需要新的 RuleDefinitionDeclaration 模型 |
| P2 | D6: 管道状态持久化 | D2, D5 | 大 | 依赖 DAG 执行和回滚机制 |
| P2 | D8: AST 沙箱 | 无 | 中 | 独立模块，可并行 |
| P3 | D9: 规则生命周期 | D6 | 小 | 依赖 PipelineRun 版本链 |
| P3 | D10: MetricEngine 集成 | D2 | 中 | 依赖 DAG 执行模型 |

### 重写阶段

```
Phase 1 (P0): 模型重写 + DAG 执行
  ├─ D1: RuleDefinitionDeclaration + RuleLogicDeclaration 双模型
  ├─ D2: DAGBuilder + DAGExecutor + 拓扑排序 + 并行执行
  └─ D3: action.type 枚举 + OperatorRegistry 迁移

Phase 2 (P1): 可靠性增强
  ├─ D5: RuleTransaction snapshot/restore
  ├─ D4: LogicalEdgeEngine 三类边 + 触发机制
  └─ D7: applies_to.fact_objects + categories 过滤

Phase 3 (P2): 持久化与安全
  ├─ D6: PipelineRun + ExecutionStepSnapshot + 断点续跑
  └─ D8: ASTSandboxExecutor 独立实现

Phase 4 (P3): 运维与协同
  ├─ D9: 规则生命周期管理
  └─ D10: MetricEngine 集成
```

### 重写风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| D1 模型变更导致现有 Schema 不兼容 | 高 | 提供迁移脚本，v1 → v2 Schema 转换 |
| D2 DAG 执行改变规则执行顺序 | 高 | 保留 priority 作为 fallback，DAG 优先 |
| D3 动作迁移遗漏 | 中 | 逐个迁移 ACTION_*，保留 legacy 兼容层 |
| D6 持久化增加 I/O 开销 | 中 | 异步写入 + 批量提交 |

---

## 评审结论

规则引擎当前实现与目标设计存在 **4 个严重偏差、3 个中等偏差、3 个轻微偏差**。核心问题集中在三个方面：

1. **模型不对齐**：规则定义与逻辑未分离，与 L4 grammar 不匹配
2. **执行模型落后**：优先级排序替代 DAG，无并行执行和回滚
3. **缺乏持久化**：执行结果仅内存，无断点续跑和审计追踪

建议按 Phase 1-4 分阶段重写，Phase 1 优先解决模型和执行核心问题。

---

## 参考文档

| 主题 | 文档 |
|------|------|
| 规则引擎重写设计 | [rule-engine/README.md](../../02-design/rule-engine/README.md) |
| DAG 执行设计 | [rule-engine/dag-execution.md](../../02-design/rule-engine/dag-execution.md) |
| 逻辑边设计 | [rule-engine/logical-edges.md](../../02-design/rule-engine/logical-edges.md) |
| 管道状态设计 | [rule-engine/pipeline-state.md](../../02-design/rule-engine/pipeline-state.md) |
| L4 grammar | [L1-L4-declarations.md](../../02-design/schema/L1-L4-declarations.md) |
| 核心概念 | [05-concepts.md](../../01-overview/05-concepts.md) |
| 模块架构 | [04-modules.md](../../01-overview/04-modules.md) |
| 旧规则引擎设计 | [04-rule-engine-design.md](../../02-design/rule-engine/04-rule-engine-design.md) |
