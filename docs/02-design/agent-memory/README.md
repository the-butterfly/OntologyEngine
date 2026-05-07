# Agent 记忆系统设计

> **status**: draft | **phase**: phase2 | **source_of_truth**: `docs/01-overview/09-agent-memory.md` | **last_verified**: 2026-04-25

---

## 目的

定义 OntologyEngine Agent 记忆系统的完整架构，在现有知识管理能力基础上，增加记忆的三大认知操作——巩固（Consolidation）、遗忘（Forgetting）、反思（Reflection），以及 memory_type 类型标签和认知操作 API，使系统从「知识管理」升级为「Agent 记忆」。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 原始碎片无法自动归纳为持久知识 | 知识停留在碎片层，无法形成跨碎片的归纳结论 |
| 2 | 所有知识平等存储，无衰减和淘汰 | 存储膨胀，低价值知识占据检索资源 |
| 3 | 系统不会主动审视已有知识 | 矛盾和过时知识依赖人工发现 |
| 4 | 缺少经验记忆和操作模式 | Agent 无法从历史交互中学习 |
| 5 | 仅支持确定性 ID 生成，无模糊匹配 | 非结构化提取时同名实体无法合并 |
| 6 | API 是 CRUD 范式，不符合 Agent 认知习惯 | Agent 需理解底层概念才能使用 |
| 7 | 证据链追踪不够深入 | 无法表达"多少证据支撑此知识" |

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                    Agent 认知操作                                  │
│         oe_remember │ oe_recall │ oe_reflect                      │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│              Memory Operation Layer                               │
│  IngestionService  QueryService  ReflectAgent                    │
│  ConsolidationEngine          ForgettingEngine                   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Layer-R: KnowledgeFragment（原始碎片）                            │
│  memory_type: fragment | 向量检索为主 | 原文证据                    │
├──────────────────────────────────────────────────────────────────┤
│  Layer-S: MemoryUnit（类型化记忆单元）                              │
│  memory_type: entity | observation | mental_model | episode |    │
│               procedure | rule                                    │
│  图优先存储 + 类型标签区分 + 共享字段 + 类型特有 JSON attributes     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 关键设计决策

| # | 决策 | 理由 | 参考 |
|---|------|------|------|
| D-AM-1 | 双层存储 + memory_type 标签，而非四层架构 | Observation/Mental Model 的差异是语义和生命周期差异，不是存储范式差异；Hindsight 用一张表 + fact_type 证明了统一存储可行 | Hindsight memory_units |
| D-AM-2 | 巩固 = memory_type 类型升级 | fragment → observation → entity → mental_model，在同层内完成，无需跨层跳转 | Hindsight Consolidation |
| D-AM-3 | 遗忘采用价值感知 Ebbinghaus 衰减 | 统一衰减不合理，高价值记忆应慢遗忘 | FSFM |
| D-AM-4 | 反思采用按类型权重递减检索 | mental_model(3.0) > entity(2.0) > observation(1.5) > fragment(1.0) | Hindsight forced_sequence |
| D-AM-5 | 认知操作 3 个而非 5 个 | consolidate/forget 合并到 reflect 内部；Agent 只需 remember/recall/reflect | MemOS + Hindsight |
| D-AM-6 | 类型特有字段存为 JSON attributes | 共享字段统一建表，类型特有字段灵活扩展，避免多表冗余 | Hindsight memory_units_view |
| D-AM-7 | 实体消歧三级策略 | 精确匹配覆盖结构化数据，模糊匹配覆盖非结构化提取，LLM 辅助覆盖高不确定性 | Hindsight EntityResolver |
| D-AM-8 | 四建模对象 × 四认知层正交分类 | memory_type 解决"是什么"，model_domain 解决"属于谁" | lencx 批判框架 |
| D-AM-9 | 治理优先于容量 | 权限治理、来源可信层级、策略性遗忘是核心挑战 | lencx 批判框架 |
| D-AM-10 | 记忆 ≠ 蒸馏 | Consolidation 是管理环节，不是记忆终极目标；需保留推理轨迹 | lencx 批判框架 |

---

## memory_type 类型体系

| memory_type | 含义 | 来源 | 检索权重 | 巩固方向 |
|-------------|------|------|---------|---------|
| `fragment` | 原始知识碎片 | Ingestion 导入 | 1.0 | → observation |
| `observation` | 自动归纳知识 | Consolidation 生成 | 1.5 | → entity |
| `entity` | Schema 驱动实例 | Schema 加载 + 提取 | 2.0 | → mental_model |
| `rule` | 业务规则定义 | Schema 加载 | 2.0 | — |
| `mental_model` | 高层摘要 | 用户策划 / Reflect 生成 | 3.0 | — |
| `episode` | 经验事件 | 交互自动记录 | 1.2 | → procedure |
| `procedure` | 操作模式 | 从 Episode 归纳 | 1.8 | — |
| `commitment` | 承诺/待办 | Agent 对用户的承诺 | 1.4 | — | [Phase 2c]
| `constraint` | 环境约束 | 不可违反的边界条件 | 1.6 | — | [Phase 2c]
| `self_experience` | 自我经验 | Agent 工具调用记录 | 1.1 | — | [Phase 2c]
| `task_state` | 任务状态 | 任务快照/方案历史 | 1.3 | — | [Phase 2c]

### 类型间边

| 边类型 | 方向 | 语义 |
|--------|------|------|
| CONSOLIDATED_INTO | fragment → observation | 碎片归纳为观察 |
| MAPPED_TO | observation → entity | 观察映射到结构化实例 |
| SUMMARIZED_AS | entity → mental_model | 实体摘要为高层洞察 |
| LEARNED_INTO | episode → procedure | 经验归纳为操作模式 |
| FULFILLED_BY | commitment → episode | 承诺履行记录 |
| LIMITS | constraint → observation | 约束限制观察范围 |
| INFORMS | self_experience → procedure | 自我经验指导操作模式 |

---

## 与现有模块的对齐

### 存储层

| memory_type | KuzuDB | ChromaDB | SQLite |
|-------------|--------|----------|--------|
| fragment | KnowledgeFragNode（已有） | knowledge_fragment（已有） | — |
| observation | MemoryUnitNode(type=observation) | memory_unit_text | memory_unit_meta |
| entity | EntityNode（已有） | 7 集合（已有） | — |
| mental_model | MemoryUnitNode(type=mental_model) | memory_unit_text | memory_unit_meta |
| episode | MemoryUnitNode(type=episode) | memory_unit_text | memory_unit_meta |
| procedure | MemoryUnitNode(type=procedure) | memory_unit_text | memory_unit_meta |

### 引擎层

| 新增引擎 | 依赖的现有引擎 | 新增能力 |
|---------|-------------|---------|
| ConsolidationEngine | ExtractionPipeline | 类型升级（fragment → observation → entity） |
| ForgettingEngine | QueryEngine | 价值评估 + 衰减 + 淘汰 |
| ReflectAgent | QueryEngine | 按类型权重递减检索 + 洞察生成 |
| EntityResolver | — | 三级消歧 + 合并策略 |
| DeduplicationGate | QueryEngine | 写入前去重 + 边际价值判断 + 矛盾前置检测 |
| ArbitrationEngine | ReflectAgent | 证据权重自动裁决矛盾 |
| QueryUnderstandingLayer | QueryEngine | 任务约束提取 → 驱动检索策略 |

### 服务层

| 新增服务 | 编排职责 | 依赖引擎 |
|---------|---------|---------|
| MemoryService | 认知操作编排（remember/recall/reflect） | ConsolidationEngine + ForgettingEngine + ReflectAgent |
| EntityResolutionService | 实体消歧编排 | EntityResolver |

---

## 实施路线

| 阶段 | 目标 | 主要输出 | 优先级 |
|------|------|----------|--------|
| Phase 2a | memory_type + 巩固机制 | MemoryUnitNode + ConsolidationEngine + 3 个认知操作 API | P0 |
| Phase 2b | 遗忘 + 反思 | ForgettingEngine + ReflectAgent | P1 |
| Phase 2c | 经验记忆 + 实体消歧 | episode + procedure + EntityResolver | P1 |
| Phase 2d | 多 Agent 共享 + 记忆调度 | Insight 共享 + Memory Scheduling | P3 |
| Phase 2e | 治理层完善 | ArbitrationEngine + PermissionService + DeduplicationGate + QueryUnderstandingLayer | P1 |

---

## 子文档索引

| 文档 | 状态 | 说明 |
|------|------|------|
| [memory-hierarchy.md](memory-hierarchy.md) | draft | 双层存储 + memory_type 类型体系 + 统一数据模型 |
| [memory-lifecycle.md](memory-lifecycle.md) | draft | 巩固 + 遗忘 + 反思 + 实体消歧 + 记忆调度 |
| [memory-api.md](memory-api.md) | draft | 3 个认知操作 API + 管理 API 共存设计 |
| [consolidation-engine.md](consolidation-engine.md) | under-review | Consolidation 引擎实现（Create/Update/Delete 三动作模型） |
| [reflect-agent.md](reflect-agent.md) | draft | Reflect Agent 设计（强制检索序列 + 矛盾检测） |
| [modeling-objects.md](modeling-objects.md) | draft | 四建模对象详细设计（User/Task/World/Self） |
| [query-understanding-layer.md](query-understanding-layer.md) | draft | 任务约束驱动的检索架构（QueryUnderstandingLayer） |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Agent 记忆概念 | `docs/01-overview/09-agent-memory.md` |
| 核心概念 | `docs/01-overview/05-concepts.md` |
| 知识检索机制 | `docs/01-overview/08-knowledge-retrieval.md` |
| 存储设计 | `docs/02-design/storage/README.md` |
| 查询引擎设计 | `docs/02-design/query-engine/README.md` |
| Agent 友好接口 | `docs/02-design/agent-friendly-design.md` |
| Hindsight 深度调研 | `docs-dev/research/hindsight-deep-analysis.md` |
