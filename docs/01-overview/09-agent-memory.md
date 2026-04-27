# Agent 记忆架构

> **status**: draft | **phase**: phase2 | **source_of_truth**: 本文档 | **last_verified**: 2026-04-25
> **[待扩展]**: 本文档定义 Agent 记忆系统的概念框架，详细设计见 `docs/02-design/agent-memory/`

---

## 目的

定义 OntologyEngine 从「知识管理系统」向「Agent 记忆系统」演进的概念框架，补齐记忆的三大认知操作——巩固（Consolidation）、遗忘（Forgetting）、反思（Reflection），使 Agent 不仅被动消费知识，还能主动形成、演化和利用记忆。

---

## 为什么需要 Agent 记忆层

### 当前差距

OntologyEngine 当前是一个优秀的**知识管理系统**——Schema 驱动的结构化知识、双层认知分工、互索引溯源、时序建模。但从 Agent 视角看，核心差距在于：

| 维度 | 知识管理系统 | 记忆系统 |
|------|-----------|---------|
| 数据观 | 静态存储，CRUD 操作 | 动态演化，形成→演化→检索→利用 |
| 知识来源 | 人工定义 + 批量导入 | 交互中自动提取 + 归纳 |
| 质量保证 | 人工审核 + 矛盾检测 | 自动巩固 + 主动反思 + 选择性遗忘 |
| 检索目标 | 找到匹配的数据 | 找到最相关的上下文 |
| Agent 角色 | 被动消费者 | 主动参与者 |

---

## 记忆架构：双层存储 + 类型标签

### 核心设计原则

**不增加新的存储层，而是在现有 Layer-R / Layer-S 内通过 `memory_type` 标签区分记忆类型。**

原因：
1. **Layer-R 和 Layer-S 的本质差异是存储范式**（向量优先 vs 图优先），不是认知层次
2. Observation、Mental Model、Episode、Procedure 的差异是**语义和生命周期**差异，不是存储范式差异
3. Hindsight 的 SOTA 实现证明了：一张 `memory_units` 表 + `fact_type` 字段足以承载所有记忆类型
4. 对 Agent 暴露的应该是简单的认知操作，而非复杂的层次路由

### 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                    Agent 认知操作                                  │
│  oe_remember │ oe_recall │ oe_reflect │ oe_consolidate │ oe_forget│
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│  Layer-R: KnowledgeFragment（原始碎片）                            │
│  存储: ChromaDB 向量优先 + KuzuDB 知识碎片节点                      │
│  memory_type: fragment                                            │
│  特征: 向量检索为主，原文证据，不可推理                                │
├──────────────────────────────────────────────────────────────────┤
│  Layer-S: MemoryUnit（类型化记忆单元）                              │
│  存储: KuzuDB 图优先 + ChromaDB 向量索引                            │
│                                                                    │
│  memory_type 标签:                                                 │
│  ┌─────────────┬──────────────┬──────────────┬──────────────┐    │
│  │ entity       │ observation  │ mental_model │ episode      │    │
│  │ Schema驱动   │ 自动归纳      │ 高层摘要      │ 经验事件      │    │
│  │ 确定性实例    │ 证据追踪      │ 快速通道      │ 交互轨迹      │    │
│  └─────────────┴──────────────┴──────────────┴──────────────┘    │
│                                                                    │
│  共享字段: id, space_id, memory_type, text, tags, confidence,      │
│           strength, proof_count, source_ids, created_at, ...      │
│  类型特有字段: 存储为 JSON attributes                                │
└──────────────────────────────────────────────────────────────────┘
```

### 为什么不分四层

| 方案 | 层数 | Agent 需理解的层次 | 存储复杂度 | 检索路由 |
|------|------|------------------|-----------|---------|
| 四层架构 | 4 | Layer-R / Layer-O / Layer-S / Layer-M | 4 套存储模型 | 4 路路由 |
| **双层+标签** | 2 | Layer-R / Layer-S | 2 套存储模型 | 2 路路由 + 类型权重 |

四层架构的问题：
1. **Agent 认知负担**：需要理解"我的知识在 Layer-O 还是 Layer-S？"——这不自然
2. **检索路由复杂**：4 层 × 多种查询类型 = 路由组合爆炸
3. **层间边膨胀**：EXTRACTED_FROM + ABSTRACTED_INTO + SUMMARIZED_AS + DERIVED_FROM = 4 种跨层边
4. **存储冗余**：ObservationNode 和 EntityNode 共享 80% 字段，却要独立建表

双层+标签的优势：
1. **Agent 只需理解两种形态**：原文碎片 vs 结构化记忆
2. **类型标签天然支持检索权重**：mental_model 权重 > entity > observation > fragment
3. **巩固 = 类型升级**：fragment → observation → entity，在同层内完成
4. **存储统一**：一个 MemoryUnit 表 + memory_type 字段

---

## memory_type 类型体系

### 类型定义

| memory_type | 含义 | 来源 | 检索权重 | 对应 Hindsight |
|-------------|------|------|---------|---------------|
| `fragment` | 原始知识碎片 | Ingestion 导入 | 1.0（基准） | World/Experience Fact |
| `observation` | 自动归纳知识 | Consolidation 生成 | 1.5 | Observation |
| `entity` | Schema 驱动实例 | Schema 加载 + 提取 | 2.0 | — |
| `rule` | 业务规则定义 | Schema 加载 | 2.0 | — |
| `mental_model` | 高层摘要 | 用户策划 / Reflect 生成 | 3.0 | Mental Model |
| `episode` | 经验事件 | 交互自动记录 | 1.2 | Experience Fact |
| `procedure` | 操作模式 | 从 Episode 归纳 | 1.8 | — |

### 类型间关系（同层内，用边而非层间跳转）

```
fragment ──[CONSOLIDATED_INTO]──▶ observation    巩固归纳
observation ──[MAPPED_TO]──▶ entity              归纳映射到结构化实例
entity ──[SUMMARIZED_AS]──▶ mental_model         实体摘要为高层洞察
episode ──[LEARNED_INTO]──▶ procedure            经验归纳为操作模式
```

这些边都在 Layer-S 内部，不需要跨层跳转。

### 类型升级（Consolidation 的本质）

```
fragment → observation → entity → mental_model
   ↑           ↑           ↑          ↑
 原始碎片    自动归纳    Schema对齐   主题摘要

升级 = memory_type 字段变更 + 新增边 + 继承 source_ids
降级 = 遗忘机制（strength 衰减）→ 类型降级或归档
```

---

## 记忆生命周期

### 四阶段模型

```
Formation（形成）    → 从交互中提取记忆
    ↓
Evolution（演化）    → 巩固 + 遗忘 + 重构
    ↓
Retrieval（检索）    → 访问策略
    ↓
Utilization（利用）  → 记忆如何影响行为
```

### 三大认知操作

#### 巩固（Consolidation）

将 fragment 类型记忆自动归纳为 observation 类型，或升级为 entity 类型。

```
fragment → [Consolidation] → observation (create/update/delete)
observation → [Schema 对齐] → entity (类型升级)
entity → [Reflect] → mental_model (摘要生成)
```

**触发方式**：阈值触发 / 定时触发 / 事件触发 / 手动触发

#### 遗忘（Forgetting）

基于记忆强度和价值的选择性衰减，不分类型统一执行。

```
记忆强度 = f(访问频率, 证据强度, 反馈权重, 时间距离)
衰减速率 = λ(记忆价值)  ← 高价值 λ 低（慢遗忘），低价值 λ 高（快遗忘）
```

#### 反思（Reflection）

Agent 主动审视已有知识，发现矛盾，生成新洞察。

```
Reflect Agent:
  recall(type=mental_model) → recall(type=observation) → recall(type=entity) → done
  按类型权重递减检索 → 生成洞察 → 可能产生新 mental_model
```

---

## 记忆操作范式

### 三个核心操作（而非五个）

简化后的认知操作——Agent 只需记住三个动词：

| 操作 | 含义 | 内部编排 |
|------|------|---------|
| **`remember`** | 存储记忆 | Ingestion + Extraction + 自动实体提取 + 可选自动巩固 |
| **`recall`** | 检索记忆 | 自动路由 + 类型权重 + RRF 融合 + 可选重排序 |
| **`reflect`** | 反思记忆 | 分层检索 + 洞察生成 + 巩固 + 遗忘 |

`consolidate` 和 `forget` 合并到 `reflect` 的内部流程——反思的结果自然触发巩固和遗忘。高级用户仍可通过管理 API 单独调用。

### 与管理 API 的关系

```
Agent 日常使用:
  oe_remember  → 记住任何东西
  oe_recall    → 回忆任何东西
  oe_reflect   → 思考、巩固、遗忘

管理员/开发者:
  oe_create_space / oe_load_schema / oe_import_instances / ...
```

---

## 实体消歧

### 三级消歧策略

| 级别 | 方法 | 场景 |
|------|------|------|
| L1 | identity_fields + UUID5 | 结构化数据导入 |
| L2 | trigram + 共现 + 时序 | 非结构化提取 |
| L3 | LLM 辅助判断 | 跨域对齐 |

### 消歧评分

```
score = name_similarity × 0.5 + cooccurrence_overlap × 0.3 + temporal_proximity × 0.2
score ≥ 0.6 → 复用现有实体
score < 0.6 → 创建新实体
```

---

## 与现有概念的关系

| 现有概念 | Agent 记忆视角 | 扩展方向 |
|---------|-------------|---------|
| Layer-R / Layer-S | 记忆的两种存储范式 | 保持不变，在 Layer-S 内增加 memory_type 标签 |
| 互索引边 | 记忆间的溯源链接 | 增加证据强度（proof_count）和变更历史 |
| 时序建模 | 记忆的时间维度 | 增加连续时序邻近性评分 |
| 反馈权重 | 记忆利用的反馈 | 增加记忆强度衰减和遗忘机制 |
| 矛盾检测 | 记忆质量保证 | 增加主动反思发现矛盾 |
| 查询路由 | 记忆检索策略 | 增加 memory_type 权重因子 |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| 记忆层次详细设计 | `docs/02-design/agent-memory/memory-hierarchy.md` |
| 记忆生命周期详细设计 | `docs/02-design/agent-memory/memory-lifecycle.md` |
| 认知操作 API 设计 | `docs/02-design/agent-memory/memory-api.md` |
| 核心概念 | `docs/01-overview/05-concepts.md` |
| 知识检索机制 | `docs/01-overview/08-knowledge-retrieval.md` |
| Hindsight 深度调研 | `docs-dev/research/hindsight-deep-analysis.md` |
