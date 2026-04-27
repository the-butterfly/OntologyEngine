# 记忆层次设计

> **status**: draft | **phase**: phase2 | **source_of_truth**: `docs/01-overview/09-agent-memory.md` | **last_verified**: 2026-04-25

---

## 目的

定义 OntologyEngine 记忆的双层存储 + memory_type 类型标签架构，以及统一的 MemoryUnit 数据模型。

## 设计原则

1. **Layer-R 和 Layer-S 的本质差异是存储范式**（向量优先 vs 图优先），不是认知层次
2. **Observation、Mental Model、Episode、Procedure 的差异是语义和生命周期差异**，用类型标签区分，不独立分层
3. **巩固 = 类型升级**：fragment → observation → entity → mental_model，在同层内完成
4. **共享字段统一建表，类型特有字段存为 JSON attributes**

---

## 1. 双层存储架构

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer-R: KnowledgeFragment（原始碎片）                            │
│  存储: ChromaDB 向量优先 + KuzuDB 知识碎片节点                      │
│  memory_type: fragment                                            │
│  特征: 向量检索为主，原文证据，不可推理                                │
│  生命周期: 创建 → 关联 → 巩固升级为 observation → 或归档/遗忘        │
├──────────────────────────────────────────────────────────────────┤
│  Layer-S: MemoryUnit（类型化记忆单元）                              │
│  存储: KuzuDB 图优先 + ChromaDB 向量索引                            │
│  memory_type: entity | observation | mental_model | episode |    │
│               procedure | rule                                    │
│  特征: 图遍历 + 向量检索，可推理，有结构                              │
│  生命周期: 创建 → 类型升级/降级 → 巩固/遗忘 → 归档                   │
└──────────────────────────────────────────────────────────────────┘
```

### 1.1 为什么保持双层而非合并为单层

| 维度 | Layer-R (fragment) | Layer-S (MemoryUnit) |
|------|-------------------|---------------------|
| **存储范式** | 向量优先（ChromaDB 主存储） | 图优先（KuzuDB 主存储） |
| **检索方式** | 语义相似度为主 | 图遍历 + Bundle Search + 向量 |
| **数据结构** | 自由文本 + 元数据 | 类型化节点 + 边 + 属性 |
| **推理能力** | 无 | 有（规则执行、路径查询） |
| **Schema 约束** | 无 | 有（entity/rule 受 Schema 约束） |

这两者的存储范式差异是根本性的，不适合合并。

### 1.2 为什么 Observation/Mental Model 不独立分层

| 维度 | 独立分层 | 类型标签 |
|------|---------|---------|
| Agent 认知负担 | 需理解 4 层 | 只需理解 2 层 + 类型 |
| 存储模型 | 4 套存储模型 | 2 套存储模型 |
| 检索路由 | 4 路路由 | 2 路路由 + 类型权重 |
| 跨层边 | 4 种跨层边 | 同层内边 |
| 字段冗余 | ObservationNode 和 EntityNode 共享 80% 字段 | 共享字段统一，特有字段 JSON |
| 巩固实现 | 跨层创建/删除节点 | 同层内修改 memory_type 字段 |

---

## 2. MemoryUnit 统一数据模型

### 2.1 共享字段

所有 memory_type 共享的字段：

```yaml
MemoryUnit:
  id: string                      # UUID
  space_id: string                # 所属语义空间
  memory_type: string             # entity | observation | mental_model | episode | procedure | rule
  text: string                    # 核心文本内容
  tags: [string]                  # 标签（用于隔离、分类、巩固分组）

  # 证据追踪
  proof_count: integer = 1        # 支撑此知识的证据数量
  source_ids: [string]            # 来源 ID（fragment 或其他 MemoryUnit）

  # 记忆强度
  strength: float = 1.0           # 记忆强度 [0, 1]
  feedback_weight: float = 0.5    # 反馈权重 [0, 1]
  access_count: integer = 0       # 访问次数
  last_accessed_at: datetime?     # 最后访问时间

  # 时序字段
  valid_from: datetime?           # 有效期起始
  valid_to: datetime?             # 有效期终止
  occurred_at: datetime?          # 事件发生时间（episode/observation）

  # 置信度
  confidence: float = 1.0         # 置信度 [0, 1]

  # 变更历史
  history: [HistoryEntry]?        # 变更记录

  # 类型特有字段
  attributes: JSON                # 类型特有字段，见下文

  # 元数据
  created_at: datetime
  updated_at: datetime
  consolidated_at: datetime?      # 巩固时间
```

### 2.2 类型特有字段（attributes JSON）

每种 memory_type 的特有字段存储在 `attributes` JSON 中：

#### observation 特有字段

```json
{
  "fact_type": "world | experience",
  "consolidation_batch_id": "batch_001",
  "source_fragment_ids": ["frag_001", "frag_002"]
}
```

#### mental_model 特有字段

```json
{
  "name": "Company A Risk Summary",
  "query_pattern": "risk level of Company A",
  "scope": "personal | team | organization",
  "shared": false,
  "is_stale": false,
  "last_refreshed_at": "2026-04-25T10:00:00Z",
  "source_entity_ids": ["ent_001", "ent_002"],
  "source_observation_ids": ["obs_001"]
}
```

#### episode 特有字段

```json
{
  "title": "Risk Assessment for Company A",
  "description": "User requested risk assessment...",
  "outcome": "Completed with D grade",
  "lessons_learned": ["Need more financial data"],
  "participants": ["agent_001", "user_001"],
  "success": true,
  "duration_minutes": 15,
  "related_entity_ids": ["ent_001"]
}
```

#### procedure 特有字段

```json
{
  "name": "Risk Assessment Procedure",
  "precondition": "Entity has financial data",
  "steps": [
    {"order": 1, "action": "Query financial metrics", "tool": "oe_recall"},
    {"order": 2, "action": "Execute risk rule", "tool": "oe_execute_rule"},
    {"order": 3, "action": "Summarize result", "tool": "reflect"}
  ],
  "postcondition": "Risk grade assigned",
  "invocation_count": 12,
  "success_count": 10,
  "success_rate": 0.83,
  "last_used_at": "2026-04-24T15:00:00Z",
  "source_episode_ids": ["ep_001", "ep_003"]
}
```

#### entity 特有字段

```json
{
  "schema_name": "Company",
  "identity_fields": {"name": "Company A", "unified_code": "91110000MA01XXXX"},
  "version": 3,
  "version_reason": "Q4 financial data update"
}
```

#### rule 特有字段

```json
{
  "schema_name": "RiskGradeRule",
  "rule_logic": "IF debt_ratio > 0.7 THEN grade = 'D'",
  "priority": 100,
  "is_active": true
}
```

---

## 3. KuzuDB 存储

### 3.1 统一 MemoryUnitNode 表

```cypher
CREATE NODE TABLE MemoryUnitNode (
    unit_id STRING PRIMARY KEY,
    space_id STRING,
    memory_type STRING,
    text STRING,
    tags STRING[],
    proof_count INT64 DEFAULT 1,
    strength DOUBLE DEFAULT 1.0,
    feedback_weight DOUBLE DEFAULT 0.5,
    access_count INT64 DEFAULT 0,
    last_accessed_at STRING,
    valid_from STRING,
    valid_to STRING,
    occurred_at STRING,
    confidence DOUBLE DEFAULT 1.0,
    attributes STRING,
    created_at STRING,
    updated_at STRING,
    consolidated_at STRING
)
```

### 3.2 类型间边

```cypher
CREATE REL TABLE CONSOLIDATED_INTO (
    FROM KnowledgeFragNode TO MemoryUnitNode,
    consolidation_batch_id STRING,
    consolidated_at STRING
)

CREATE REL TABLE MAPPED_TO (
    FROM MemoryUnitNode TO MemoryUnitNode,
    mapped_at STRING
)

CREATE REL TABLE SUMMARIZED_AS (
    FROM MemoryUnitNode TO MemoryUnitNode,
    summarized_at STRING
)

CREATE REL TABLE LEARNED_INTO (
    FROM MemoryUnitNode TO MemoryUnitNode,
    learned_at STRING
)
```

### 3.3 与现有 EntityNode 的兼容

现有 EntityNode 保持不变（Schema 驱动的结构化实例），MemoryUnitNode(type=entity) 是 EntityNode 的**影子节点**，两者通过 `MAPPED_TO` 边关联：

```
EntityNode (KuzuDB 已有)
  ↕ MAPPED_TO
MemoryUnitNode(type=entity) (新增)
```

这样做的理由：
- EntityNode 有 Schema 约束的强类型属性，不适合改为 JSON attributes
- MemoryUnitNode 提供统一的记忆操作接口（强度、遗忘、巩固）
- 检索时：MemoryUnitNode 提供记忆元信息，EntityNode 提供结构化属性

---

## 4. ChromaDB 存储

### 4.1 统一 memory_unit_text 集合

```
Collection: "memory_unit_text"

每条记录:
  id: unit_id
  embedding: text 的向量嵌入
  metadata: {
    space_id: string,
    memory_type: string,
    proof_count: int,
    strength: float,
    confidence: float,
    tags: list[str]
  }
```

### 4.2 检索时的类型权重

```python
def apply_type_weight(rrf_score, memory_type):
    type_weights = {
        "mental_model": 3.0,
        "entity": 2.0,
        "rule": 2.0,
        "procedure": 1.8,
        "observation": 1.5,
        "episode": 1.2,
        "fragment": 1.0
    }
    return rrf_score * type_weights.get(memory_type, 1.0)
```

---

## 5. 类型升级与降级

### 5.1 升级路径

```
fragment ──[ConsolidationEngine]──▶ observation ──[Schema对齐]──▶ entity ──[ReflectAgent]──▶ mental_model
episode ──[ConsolidationEngine]──▶ procedure
```

### 5.2 升级操作

```python
async def upgrade_memory(unit_id, new_type, additional_attrs=None):
    unit = await get_memory_unit(unit_id)

    old_type = unit.memory_type
    unit.memory_type = new_type
    unit.attributes.update(additional_attrs or {})
    unit.consolidated_at = datetime.utcnow()

    await update_memory_unit(unit)

    await create_type_edge(
        from_id=unit_id,
        to_id=unit_id,
        edge_type=get_upgrade_edge(old_type, new_type)
    )
```

### 5.3 降级路径

遗忘机制触发降级：

```
mental_model → entity → observation → fragment → archived → deleted
```

降级条件：
- strength < 0.3 → 降一级
- strength < 0.1 → 归档
- strength < 0.01 且 proof_count == 0 → 删除

---

## 6. 检索优先级

### 6.1 按类型权重递减

| 优先级 | memory_type | 权重 | 原因 |
|--------|-------------|------|------|
| 1 | mental_model | 3.0 | 高层摘要，快速通道 |
| 2 | entity / rule | 2.0 | 确定性知识，高可信度 |
| 3 | procedure | 1.8 | 验证过的操作模式 |
| 4 | observation | 1.5 | 归纳知识，中等可信度 |
| 5 | episode | 1.2 | 经验事件，具体但可能非典型 |
| 6 | fragment | 1.0 | 原始碎片，最完整但最慢 |

### 6.2 Reflect Agent 的检索序列

```python
async def reflect_retrieve(query, space_id):
    results = []
    for memory_type in ["mental_model", "entity", "observation", "fragment"]:
        type_results = await recall(query, space_id, memory_type=memory_type)
        results.extend(type_results)
        if len(results) >= min_results:
            break
    return results
```

---

## 7. 与现有 Schema 的兼容性

### 7.1 不修改现有 Schema v2

memory_type 类型标签是 Layer-S 内部的组织方式，不影响 L1-L4 声明。现有 Schema YAML 无需变更。

### 7.2 互索引边扩展

| 新增边类型 | 方向 | 语义 |
|-----------|------|------|
| CONSOLIDATED_INTO | KnowledgeFragment → MemoryUnitNode | 碎片归纳为记忆单元 |
| MAPPED_TO | MemoryUnitNode → EntityNode | 记忆单元映射到结构化实体 |
| SUMMARIZED_AS | MemoryUnitNode → MemoryUnitNode | 实体摘要为高层洞察 |
| LEARNED_INTO | MemoryUnitNode → MemoryUnitNode | 经验归纳为操作模式 |

### 7.3 现有互索引边保持不变

EXTRACTED_FROM / SUPPORTED_BY / DEFINED_IN / TRACE_TO 四种边继续用于 Layer-R ↔ Layer-S 的溯源。

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Agent 记忆概念 | `docs/01-overview/09-agent-memory.md` |
| Agent 记忆设计总览 | `docs/02-design/agent-memory/README.md` |
| 记忆生命周期设计 | `docs/02-design/agent-memory/memory-lifecycle.md` |
| 认知操作 API 设计 | `docs/02-design/agent-memory/memory-api.md` |
| Schema v2 规范 | `docs/02-design/schema/01-schema-spec.md` |
| 互索引边 | `docs/02-design/schema/mutual-index-edges.md` |
| Hindsight 深度调研 | `docs-dev/research/hindsight-deep-analysis.md` |
