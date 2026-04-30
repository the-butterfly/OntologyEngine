# KuzuDB Schema 设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/02-design/schema/instance-layer.md` + `docs/02-design/schema/mutual-index-edges.md` + `docs/01-overview/10-kb-process.md` | **last_verified**: 2026-04-30

---

## 目的

定义 OntologyEngine 在 KuzuDB 中的节点表和边表 Schema，对齐 Schema v2 Instance 层数据结构、互索引边类型，以及认知分层（CognitiveNode）和双轨治理（SUPERSEDES/CONTRADICTS）的新要求。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | DuckDB 表结构无法表达图遍历语义 | 多跳推理依赖 JOIN 递归，性能 O(n^k) |
| 2 | 节点类型无区分，所有实体混在一张表 | 无法利用 KuzuDB 的类型约束和索引优化 |
| 3 | 边缺乏语义字段（edge_text、weight） | 边只是类型标签，无法参与 Bundle Search |
| 4 | 时序字段（valid_from/valid_to）缺失 | 无法支持时间切片查询 |
| 5 | 互索引边无存储实现 | Layer-R 与 Layer-S 数据层断连 |
| 6 | 无认知分层字段（cognitive_layer） | 无法支持分层漏斗检索 |
| 7 | 无双时序支持（recorded_at） | 无法区分"事件何时发生"与"系统何时知晓" |
| 8 | 无信念状态（belief_status） | 无法支持待审区和双轨治理 |
| 9 | 无版本字段（version） | 无法支持乐观并发控制 |
| 10 | 无矛盾/更正边（SUPERSEDES/CONTRADICTS） | 更正传播和矛盾链无法在图中表达 |

---

## 设计原则

| # | 原则 | 说明 |
|---|------|------|
| P-KZ-1 | 渐进式统一节点表 | Phase 1 增加 CognitiveNode 与 EntityNode 并存；Phase 2 验证性能后逐步合并 |
| P-KZ-2 | 边分区写入 | m_flow 发现 UNWIND+MERGE 共享端点时触发 write-write conflict，需端点分区 |
| P-KZ-3 | MAP 类型存储动态属性 | KuzuDB MAP(STRING, STRING) 承载 attributes，避免 ALTER TABLE |
| P-KZ-4 | MERGE 幂等写入 | 基于 id 主键 MERGE，保证同一业务实体幂等 |
| P-KZ-5 | 核心字段强类型 | 高频查询字段（entity_name, entity_type, schema_ref）保留为强类型列，其余存 JSON |
| P-KZ-6 | 双时序分离 | valid_from/valid_to 表达事实有效时间，recorded_at 表达系统记录时间 |

---

## 迁移策略

> **[关键设计点]**：采用渐进式迁移，Phase 1 CognitiveNode 与 EntityNode 并存，Phase 2 逐步合并。

```
Phase 1（当前）:
  EntityNode            ← 保持不变，Schema 驱动的结构化实例
  CognitiveNode (新增)   ← 统一认知节点，cognitive_layer 分区
  两者通过 ALIGNED_WITH 边关联

Phase 2（验证后）:
  EntityNode 废弃，所有数据迁移到 CognitiveNode
  ALIGNED_WITH 边删除
```

---

## 节点表

### CognitiveNode [新增]

> **[关键设计点]**：统一认知节点，替代 EntityNode + MemoryUnitNode(MAPPED_TO 影子节点)。
> 通过 cognitive_layer 分区实现认知分层，通过 memory_type 区分语义类型。

```cypher
CREATE NODE TABLE CognitiveNode (
    id                STRING PRIMARY KEY,
    space_id          STRING,
    cognitive_layer   STRING,
    memory_type       STRING,
    entity_name       STRING,
    entity_type       STRING,
    schema_ref        STRING,
    text              STRING,
    tags              STRING[],
    attributes        MAP(STRING, STRING),

    version           INT64 DEFAULT 1,
    confidence        DOUBLE DEFAULT 1.0,
    strength          DOUBLE DEFAULT 1.0,
    feedback_weight   DOUBLE DEFAULT 0.5,
    proof_count       INT64 DEFAULT 1,
    access_count      INT64 DEFAULT 0,
    source_fragment_ids STRING[],
    history           STRING,

    belief_status     STRING DEFAULT 'accepted',
    visibility        STRING DEFAULT 'shared',

    valid_from        DATETIME,
    valid_to          DATETIME,
    recorded_at       DATETIME,
    occurred_at       DATETIME,

    compiled_at       DATETIME,
    superseded_by     STRING,

    source_pipeline   STRING,
    source_content_hash STRING,
    created_at        DATETIME,
    updated_at        DATETIME,
    consolidated_at   DATETIME
)
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | STRING PK | UUID5 确定性生成 |
| `space_id` | STRING | 所属语义空间 |
| `cognitive_layer` | STRING | 认知分层：perception / semantic / opinion / procedure |
| `memory_type` | STRING | 语义类型：entity / observation / opinion / mental_model / episode / procedure / rule / fragment |
| `entity_name` | STRING | **强类型列**——实体显示名称，高频查询字段 |
| `entity_type` | STRING | **强类型列**——实体类型标识（对应 _fact_object） |
| `schema_ref` | STRING | **强类型列**——引用 Schema L1 EntityDeclaration.name |
| `text` | STRING | 核心文本内容 |
| `tags` | STRING[] | 标签（隔离、分类、巩固分组） |
| `attributes` | MAP(STRING, STRING) | 类型特有字段，值统一序列化为 STRING |
| `version` | INT64 | 乐观并发控制版本号，每次写入 +1 |
| `confidence` | DOUBLE | 置信度 [0, 1] |
| `strength` | DOUBLE | 记忆强度 [0, 1] |
| `feedback_weight` | DOUBLE | 反馈权重 [0, 1]，≥0.9 时永不遗忘 |
| `proof_count` | INT64 | 支撑此知识的证据数量 |
| `access_count` | INT64 | 访问次数 |
| `source_fragment_ids` | STRING[] | 支撑此知识的碎片 ID 数组（Consolidation 产物，替代/补充 CONSOLIDATED_INTO 边遍历） |
| `history` | STRING | JSONB 变更历史（内联快照，避免高频 SUPERSEDES 边遍历） |
| `belief_status` | STRING | 信念状态：accepted / pending_review / rejected / superseded |
| `visibility` | STRING | 可见性：private / shared / public |
| `valid_from` | DATETIME | 事实有效起始时间（T） |
| `valid_to` | DATETIME | 事实有效终止时间（T），NULL 表示当前有效 |
| `recorded_at` | DATETIME | **双时序**——系统记录时间（T'），区分"何时发生"与"何时知晓" |
| `occurred_at` | DATETIME | 事件实际发生时间（episode/observation） |
| `compiled_at` | DATETIME | 编译产物编译时间，用于一致性标记 |
| `superseded_by` | STRING | 被哪条记忆取代（SUPERSEDES 链的反向引用） |
| `source_pipeline` | STRING | 来源管道标识 |
| `source_content_hash` | STRING | SHA256 哈希 |
| `created_at` | DATETIME | 创建时间 |
| `updated_at` | DATETIME | 更新时间 |
| `consolidated_at` | DATETIME | 巩固时间 |

**cognitive_layer 与 memory_type 的映射**：

| cognitive_layer | 包含的 memory_type | 说明 |
|----------------|-------------------|------|
| perception | fragment | 原始感知碎片 |
| semantic | entity, rule | 结构化语义知识 |
| opinion | observation, opinion, mental_model | 归纳观点与高层摘要 |
| procedure | episode, procedure | 经验与操作模式 |

**belief_status 状态机**：

```
accepted ──[矛盾检测]──▶ pending_review ──[人工确认]──▶ accepted
                                              │
                                              ├──[人工拒绝]──▶ rejected
                                              └──[人工修改]──▶ accepted (modified)

accepted ──[更正写入]──▶ superseded (superseded_by 指向新版本)
superseded ──[更正撤销]──▶ accepted (superseded_by 清空)

pending_review ──[超时未审+confidence>0.9]──▶ accepted (自动晋升)
rejected ──[重新提交]──▶ pending_review
```

**history 字段格式**：

```json
[
  {
    "previous_text": "Alice works at Google",
    "previous_tags": ["company:google"],
    "previous_belief_status": "accepted",
    "changed_at": "2026-04-30T10:00:00Z",
    "change_reason": "consolidation",
    "changed_by": "agent_001",
    "new_source_fragment_ids": ["frag_001", "frag_002"]
  }
]
```

| change_reason | 说明 |
|---------------|------|
| consolidation | 巩固归纳产生变更 |
| correction | 更正写入产生变更 |
| manual | 人工审批修改产生变更 |

**证据链查询模式**：

```cypher
MATCH (n:CognitiveNode {id: $node_id})
WHERE n.source_fragment_ids IS NOT NULL
UNWIND n.source_fragment_ids AS frag_id
MATCH (kf:KnowledgeFragmentNode {id: frag_id})
RETURN n, kf

UNION

MATCH (n:CognitiveNode {id: $node_id})-[r:COG_EXTRACTED_FROM]->(kf:KnowledgeFragmentNode)
RETURN n, kf
```

**索引**：

```cypher
CREATE INDEX idx_cog_space_id ON CognitiveNode(space_id);
CREATE INDEX idx_cog_cognitive_layer ON CognitiveNode(cognitive_layer);
CREATE INDEX idx_cog_memory_type ON CognitiveNode(memory_type);
CREATE INDEX idx_cog_entity_name ON CognitiveNode(entity_name);
CREATE INDEX idx_cog_entity_type ON CognitiveNode(entity_type);
CREATE INDEX idx_cog_schema_ref ON CognitiveNode(schema_ref);
CREATE INDEX idx_cog_belief_status ON CognitiveNode(belief_status);
CREATE INDEX idx_cog_valid_from ON CognitiveNode(valid_from);
CREATE INDEX idx_cog_recorded_at ON CognitiveNode(recorded_at);
CREATE INDEX idx_cog_strength ON CognitiveNode(strength);
CREATE INDEX idx_cog_compiled_at ON CognitiveNode(compiled_at);
```

**复合索引（待 KuzuDB 性能基准验证）**：

```cypher
CREATE INDEX idx_cog_layer_type ON CognitiveNode(cognitive_layer, memory_type);
CREATE INDEX idx_cog_space_layer ON CognitiveNode(space_id, cognitive_layer);
CREATE INDEX idx_cog_space_type_status ON CognitiveNode(space_id, memory_type, belief_status);
```

---

### EntityNode（Phase 1 保留）

> **[已过期入口]**：Phase 1 保留，Phase 2 废弃迁移到 CognitiveNode。
> 对齐 Schema v2 `EntityInstance`。

```cypher
CREATE NODE TABLE EntityNode (
    id              STRING PRIMARY KEY,
    _fact_object    STRING,
    name            STRING,
    attributes      MAP(STRING, STRING),
    valid_from      DATETIME,
    valid_to        DATETIME,
    created_at      DATETIME,
    updated_at      DATETIME,
    domain_id       STRING,
    confidence      DOUBLE DEFAULT 1.0,
    source_pipeline STRING,
    source_content_hash STRING,
    feedback_weight DOUBLE DEFAULT 0.5
)
```

**索引**：

```cypher
CREATE INDEX idx_entity_fact_object ON EntityNode(_fact_object);
CREATE INDEX idx_entity_domain_id ON EntityNode(domain_id);
CREATE INDEX idx_entity_valid_from ON EntityNode(valid_from);
CREATE INDEX idx_entity_source_pipeline ON EntityNode(source_pipeline);
```

---

### RuleDefinitionNode

对齐 Schema v2 L4 RuleDefinition。

```cypher
CREATE NODE TABLE RuleDefinitionNode (
    id              STRING PRIMARY KEY,
    name            STRING,
    rule_type       STRING,
    condition_expr  STRING,
    action_expr     STRING,
    priority        INT64 DEFAULT 0,
    enabled         BOOLEAN DEFAULT true,
    domain_id       STRING,
    source_pipeline STRING,
    source_content_hash STRING,
    created_at      DATETIME,
    updated_at      DATETIME
)
```

**索引**：

```cypher
CREATE INDEX idx_rule_name ON RuleDefinitionNode(name);
CREATE INDEX idx_rule_domain_id ON RuleDefinitionNode(domain_id);
CREATE INDEX idx_rule_enabled ON RuleDefinitionNode(enabled);
```

---

### KnowledgeFragmentNode

对齐 Schema v2 `KnowledgeFragment`。Layer-R 原始碎片。

```cypher
CREATE NODE TABLE KnowledgeFragmentNode (
    id                STRING PRIMARY KEY,
    dataset_id        STRING,
    document_id       STRING,
    chunk_index       INT64,
    offset_start      INT64,
    offset_end        INT64,
    text              STRING,
    vector_id         STRING,
    metadata          MAP(STRING, STRING),
    extraction_status STRING DEFAULT 'pending',
    content_hash      STRING,
    created_at        DATETIME,
    updated_at        DATETIME
)
```

**索引**：

```cypher
CREATE INDEX idx_kf_dataset_id ON KnowledgeFragmentNode(dataset_id);
CREATE INDEX idx_kf_document_id ON KnowledgeFragmentNode(document_id);
CREATE INDEX idx_kf_extraction_status ON KnowledgeFragmentNode(extraction_status);
CREATE INDEX idx_kf_content_hash ON KnowledgeFragmentNode(content_hash);
```

---

### CategoryTagNode

对齐 Schema v2 `CategoryTag`。

```cypher
CREATE NODE TABLE CategoryTagNode (
    id              STRING PRIMARY KEY,
    entity_id       STRING,
    dimension_name  STRING,
    value_code      STRING,
    assigned_at     DATETIME,
    assigned_by     STRING,
    confidence      DOUBLE DEFAULT 1.0
)
```

**索引**：

```cypher
CREATE INDEX idx_ct_entity_id ON CategoryTagNode(entity_id);
CREATE INDEX idx_ct_dimension_name ON CategoryTagNode(dimension_name);
```

---

### MetricValueNode

对齐 Schema v2 `MetricValue`。

```cypher
CREATE NODE TABLE MetricValueNode (
    id                    STRING PRIMARY KEY,
    entity_id             STRING,
    metric_name           STRING,
    value                 STRING,
    computed_at           DATETIME,
    valid_from            DATETIME,
    valid_to              DATETIME,
    computed_by           STRING,
    computation_snapshot  MAP(STRING, STRING)
)
```

**索引**：

```cypher
CREATE INDEX idx_mv_entity_id ON MetricValueNode(entity_id);
CREATE INDEX idx_mv_metric_name ON MetricValueNode(metric_name);
CREATE INDEX idx_mv_valid_from ON MetricValueNode(valid_from);
```

---

### DispositionProfileNode [新增]

> Agent/用户的检索偏好配置，驱动分层漏斗的动态权重和短路策略。

```cypher
CREATE NODE TABLE DispositionProfileNode (
    id          STRING PRIMARY KEY,
    space_id    STRING,
    profile_name STRING,
    skepticism  DOUBLE DEFAULT 0.5,
    evidence_demand DOUBLE DEFAULT 0.5,
    abstraction_preference DOUBLE DEFAULT 0.5,
    thoroughness DOUBLE DEFAULT 0.5,
    recency_bias DOUBLE DEFAULT 0.5,
    empathy     DOUBLE DEFAULT 0.5,
    risk_tolerance DOUBLE DEFAULT 0.5,
    is_default  BOOLEAN DEFAULT false,
    created_at  DATETIME,
    updated_at  DATETIME
)
```

**索引**：

```cypher
CREATE INDEX idx_dp_space_id ON DispositionProfileNode(space_id);
CREATE INDEX idx_dp_is_default ON DispositionProfileNode(is_default);
```

---

## 边表

### 业务关系边（RELATES_TO）

对齐 Schema v2 `EdgeInstance`。

```cypher
CREATE REL TABLE RELATES_TO (
    FROM EntityNode TO EntityNode,
    id                  STRING,
    relation_name       STRING,
    attributes          MAP(STRING, STRING),
    edge_text           STRING,
    weight              DOUBLE,
    valid_from          DATETIME,
    valid_to            DATETIME,
    confidence          DOUBLE DEFAULT 1.0,
    source_pipeline     STRING,
    source_content_hash STRING
)
```

> **[关键设计点]**：RELATES_TO 是通用业务关系边表。当某类关系的查询频率或属性差异足够大时，应拆分为独立关系表。初始阶段使用单一 RELATES_TO 表，通过 `relation_name` 区分关系类型。

**索引**：

```cypher
CREATE INDEX idx_rel_relation_name ON RELATES_TO(relation_name);
CREATE INDEX idx_rel_confidence ON RELATES_TO(confidence);
CREATE INDEX idx_rel_valid_from ON RELATES_TO(valid_from);
```

---

### 认知关系边 [新增]

#### COGNITIVE_RELATES_TO

CognitiveNode 之间的业务关系边，对齐 RELATES_TO 语义。

```cypher
CREATE REL TABLE COGNITIVE_RELATES_TO (
    FROM CognitiveNode TO CognitiveNode,
    id                  STRING,
    relation_name       STRING,
    attributes          MAP(STRING, STRING),
    edge_text           STRING,
    weight              DOUBLE,
    valid_from          DATETIME,
    valid_to            DATETIME,
    confidence          DOUBLE DEFAULT 1.0,
    source_pipeline     STRING,
    source_content_hash STRING
)
```

**索引**：

```cypher
CREATE INDEX idx_crel_relation_name ON COGNITIVE_RELATES_TO(relation_name);
CREATE INDEX idx_crel_confidence ON COGNITIVE_RELATES_TO(confidence);
CREATE INDEX idx_crel_valid_from ON COGNITIVE_RELATES_TO(valid_from);
```

#### SUPERSEDES [新增]

> **[关键设计点]**：更正链边。新记忆取代旧记忆时创建，支持更正传播和回退。

```cypher
CREATE REL TABLE SUPERSEDES (
    FROM CognitiveNode TO CognitiveNode,
    id              STRING,
    supersede_reason STRING,
    supersede_type  STRING,
    confidence      DOUBLE DEFAULT 1.0,
    recorded_at     DATETIME,
    created_at      DATETIME
)
```

| 字段 | 说明 |
|------|------|
| `supersede_reason` | 更正原因：correction / update / invalidation |
| `supersede_type` | 更正类型：full（完全取代）/ partial（部分取代） |
| `recorded_at` | 系统记录更正的时间（T'） |

**索引**：

```cypher
CREATE INDEX idx_sup_supersede_type ON SUPERSEDES(supersede_type);
CREATE INDEX idx_sup_recorded_at ON SUPERSEDES(recorded_at);
```

#### CONTRADICTS [新增]

> **[关键设计点]**：矛盾链边。两条记忆存在矛盾时创建，触发双轨治理流程。

```cypher
CREATE REL TABLE CONTRADICTS (
    FROM CognitiveNode TO CognitiveNode,
    id                  STRING,
    contradiction_type  STRING,
    contradiction_field STRING,
    old_value           STRING,
    new_value           STRING,
    confidence          DOUBLE DEFAULT 1.0,
    resolution_status   STRING DEFAULT 'pending',
    created_at          DATETIME
)
```

| 字段 | 说明 |
|------|------|
| `contradiction_type` | 矛盾类型：factual（事实矛盾）/ temporal（时序矛盾）/ semantic（语义矛盾） |
| `contradiction_field` | 矛盾字段名 |
| `resolution_status` | 解决状态：pending / resolved_track_a / resolved_track_b / ignored |

**索引**：

```cypher
CREATE INDEX idx_contra_type ON CONTRADICTS(contradiction_type);
CREATE INDEX idx_contra_resolution ON CONTRADICTS(resolution_status);
CREATE INDEX idx_contra_created_at ON CONTRADICTS(created_at);
```

#### CONSOLIDATED_INTO

碎片归纳为记忆单元。

```cypher
CREATE REL TABLE CONSOLIDATED_INTO (
    FROM KnowledgeFragmentNode TO CognitiveNode,
    consolidation_batch_id STRING,
    consolidated_at STRING
)
```

#### SUMMARIZED_AS

实体摘要为高层洞察。

```cypher
CREATE REL TABLE SUMMARIZED_AS (
    FROM CognitiveNode TO CognitiveNode,
    summarized_at STRING
)
```

#### LEARNED_INTO

经验归纳为操作模式。

```cypher
CREATE REL TABLE LEARNED_INTO (
    FROM CognitiveNode TO CognitiveNode,
    learned_at STRING
)
```

#### ALIGNED_WITH [新增]

> Phase 1 过渡边：CognitiveNode 与 EntityNode 的关联。Phase 2 废弃。

```cypher
CREATE REL TABLE ALIGNED_WITH (
    FROM CognitiveNode TO EntityNode,
    aligned_at DATETIME
)
```

---

### 互索引边

对齐 `docs/02-design/schema/mutual-index-edges.md`。

#### EXTRACTED_FROM

```cypher
CREATE REL TABLE EXTRACTED_FROM (
    FROM EntityNode TO KnowledgeFragmentNode,
    id            STRING,
    source_file   STRING,
    offset_start  INT64,
    offset_end    INT64,
    confidence    DOUBLE,
    edge_text     STRING,
    created_at    DATETIME
)
```

#### SUPPORTED_BY

```cypher
CREATE REL TABLE SUPPORTED_BY (
    FROM KnowledgeFragmentNode TO EntityNode,
    id            STRING,
    source_file   STRING,
    offset_start  INT64,
    offset_end    INT64,
    confidence    DOUBLE,
    edge_text     STRING,
    created_at    DATETIME
)
```

#### COG_EXTRACTED_FROM [新增]

CognitiveNode 版本的互索引边。

```cypher
CREATE REL TABLE COG_EXTRACTED_FROM (
    FROM CognitiveNode TO KnowledgeFragmentNode,
    id            STRING,
    source_file   STRING,
    offset_start  INT64,
    offset_end    INT64,
    confidence    DOUBLE,
    edge_text     STRING,
    created_at    DATETIME
)
```

#### COG_SUPPORTED_BY [新增]

```cypher
CREATE REL TABLE COG_SUPPORTED_BY (
    FROM KnowledgeFragmentNode TO CognitiveNode,
    id            STRING,
    source_file   STRING,
    offset_start  INT64,
    offset_end    INT64,
    confidence    DOUBLE,
    edge_text     STRING,
    created_at    DATETIME
)
```

#### DEFINED_IN

```cypher
CREATE REL TABLE DEFINED_IN (
    FROM RuleDefinitionNode TO KnowledgeFragmentNode,
    id            STRING,
    source_file   STRING,
    offset_start  INT64,
    offset_end    INT64,
    confidence    DOUBLE,
    edge_text     STRING,
    created_at    DATETIME
)
```

#### TRACE_TO

```cypher
CREATE REL TABLE TRACE_TO (
    FROM EntityNode TO KnowledgeFragmentNode,
    id            STRING,
    source_file   STRING,
    offset_start  INT64,
    offset_end    INT64,
    confidence    DOUBLE,
    edge_text     STRING,
    created_at    DATETIME
)
```

> **[待扩展]**：TRACE_TO 的源端应为 ExecutionStepSnapshot，当前暂用 EntityNode 作为源端。

**互索引边索引**：

```cypher
CREATE INDEX idx_ef_confidence ON EXTRACTED_FROM(confidence);
CREATE INDEX idx_sb_confidence ON SUPPORTED_BY(confidence);
CREATE INDEX idx_cogef_confidence ON COG_EXTRACTED_FROM(confidence);
CREATE INDEX idx_cogsb_confidence ON COG_SUPPORTED_BY(confidence);
CREATE INDEX idx_di_confidence ON DEFINED_IN(confidence);
CREATE INDEX idx_tt_confidence ON TRACE_TO(confidence);
```

#### CO_OCCURS_WITH [新增]

实体共现追踪边，支撑实体消歧的共现重叠度计算（占消歧评分 30% 权重）。

```cypher
CREATE REL TABLE CO_OCCURS_WITH (
    FROM CognitiveNode TO CognitiveNode,
    weight    DOUBLE DEFAULT 1.0,
    count     INT64 DEFAULT 1,
    last_seen DATETIME,
    space_id  STRING
)
```

```cypher
CREATE INDEX idx_cooc_space ON CO_OCCURS_WITH(space_id);
CREATE INDEX idx_cooc_weight ON CO_OCCURS_WITH(weight);
```

| 字段 | 类型 | 语义 |
|------|------|------|
| `weight` | DOUBLE | 共现权重（指数衰减：weight = weight × 0.9 + 0.1） |
| `count` | INT64 | 共现次数 |
| `last_seen` | DATETIME | 最近共现时间 |
| `space_id` | STRING | 空间隔离 |

---

### 分类标注边（CATEGORIZED_AS）

```cypher
CREATE REL TABLE CATEGORIZED_AS (
    FROM EntityNode TO CategoryTagNode,
    assigned_at DATETIME
)
```

### 指标关联边（HAS_METRIC）

```cypher
CREATE REL TABLE HAS_METRIC (
    FROM EntityNode TO MetricValueNode,
    computed_at DATETIME
)
```

---

## Schema 初始化

```cypher
CALL clear_db();

CREATE NODE TABLE CognitiveNode (...);
CREATE NODE TABLE EntityNode (...);
CREATE NODE TABLE RuleDefinitionNode (...);
CREATE NODE TABLE KnowledgeFragmentNode (...);
CREATE NODE TABLE CategoryTagNode (...);
CREATE NODE TABLE MetricValueNode (...);

CREATE REL TABLE COGNITIVE_RELATES_TO (...);
CREATE REL TABLE SUPERSEDES (...);
CREATE REL TABLE CONTRADICTS (...);
CREATE REL TABLE CONSOLIDATED_INTO (...);
CREATE REL TABLE SUMMARIZED_AS (...);
CREATE REL TABLE LEARNED_INTO (...);
CREATE REL TABLE ALIGNED_WITH (...);
CREATE REL TABLE RELATES_TO (...);
CREATE REL TABLE EXTRACTED_FROM (...);
CREATE REL TABLE SUPPORTED_BY (...);
CREATE REL TABLE COG_EXTRACTED_FROM (...);
CREATE REL TABLE COG_SUPPORTED_BY (...);
CREATE REL TABLE DEFINED_IN (...);
CREATE REL TABLE TRACE_TO (...);
CREATE REL TABLE CATEGORIZED_AS (...);
CREATE REL TABLE HAS_METRIC (...);

CREATE INDEX idx_cog_space_id ON CognitiveNode(space_id);
CREATE INDEX idx_cog_cognitive_layer ON CognitiveNode(cognitive_layer);
CREATE INDEX idx_cog_memory_type ON CognitiveNode(memory_type);
CREATE INDEX idx_cog_entity_name ON CognitiveNode(entity_name);
CREATE INDEX idx_cog_entity_type ON CognitiveNode(entity_type);
CREATE INDEX idx_cog_schema_ref ON CognitiveNode(schema_ref);
CREATE INDEX idx_cog_belief_status ON CognitiveNode(belief_status);
CREATE INDEX idx_cog_valid_from ON CognitiveNode(valid_from);
CREATE INDEX idx_cog_recorded_at ON CognitiveNode(recorded_at);
CREATE INDEX idx_cog_strength ON CognitiveNode(strength);
CREATE INDEX idx_cog_compiled_at ON CognitiveNode(compiled_at);
CREATE INDEX idx_entity_fact_object ON EntityNode(_fact_object);
CREATE INDEX idx_entity_domain_id ON EntityNode(domain_id);
CREATE INDEX idx_entity_valid_from ON EntityNode(valid_from);
CREATE INDEX idx_entity_source_pipeline ON EntityNode(source_pipeline);
CREATE INDEX idx_rule_name ON RuleDefinitionNode(name);
CREATE INDEX idx_rule_domain_id ON RuleDefinitionNode(domain_id);
CREATE INDEX idx_rule_enabled ON RuleDefinitionNode(enabled);
CREATE INDEX idx_kf_dataset_id ON KnowledgeFragmentNode(dataset_id);
CREATE INDEX idx_kf_document_id ON KnowledgeFragmentNode(document_id);
CREATE INDEX idx_kf_extraction_status ON KnowledgeFragmentNode(extraction_status);
CREATE INDEX idx_kf_content_hash ON KnowledgeFragmentNode(content_hash);
CREATE INDEX idx_ct_entity_id ON CategoryTagNode(entity_id);
CREATE INDEX idx_ct_dimension_name ON CategoryTagNode(dimension_name);
CREATE INDEX idx_mv_entity_id ON MetricValueNode(entity_id);
CREATE INDEX idx_mv_metric_name ON MetricValueNode(metric_name);
CREATE INDEX idx_mv_valid_from ON MetricValueNode(valid_from);
CREATE INDEX idx_crel_relation_name ON COGNITIVE_RELATES_TO(relation_name);
CREATE INDEX idx_crel_confidence ON COGNITIVE_RELATES_TO(confidence);
CREATE INDEX idx_sup_supersede_type ON SUPERSEDES(supersede_type);
CREATE INDEX idx_sup_recorded_at ON SUPERSEDES(recorded_at);
CREATE INDEX idx_contra_type ON CONTRADICTS(contradiction_type);
CREATE INDEX idx_contra_resolution ON CONTRADICTS(resolution_status);
CREATE INDEX idx_rel_relation_name ON RELATES_TO(relation_name);
CREATE INDEX idx_rel_confidence ON RELATES_TO(confidence);
CREATE INDEX idx_rel_valid_from ON RELATES_TO(valid_from);
CREATE INDEX idx_ef_confidence ON EXTRACTED_FROM(confidence);
CREATE INDEX idx_sb_confidence ON SUPPORTED_BY(confidence);
CREATE INDEX idx_cogef_confidence ON COG_EXTRACTED_FROM(confidence);
CREATE INDEX idx_cogsb_confidence ON COG_SUPPORTED_BY(confidence);
CREATE INDEX idx_di_confidence ON DEFINED_IN(confidence);
CREATE INDEX idx_tt_confidence ON TRACE_TO(confidence);
```

---

## Cypher 查询模式

### 认知分层查询（分层漏斗）

```cypher
MATCH (n:CognitiveNode {space_id: $space_id, cognitive_layer: 'opinion',
       belief_status: 'accepted'})
WHERE n.text CONTAINS $keyword
RETURN n ORDER BY n.strength DESC LIMIT $limit
```

### 双时序查询

```cypher
MATCH (n:CognitiveNode {space_id: $space_id, entity_name: $entity_name})
WHERE n.valid_from <= $as_of AND (n.valid_to IS NULL OR n.valid_to > $as_of)
RETURN n ORDER BY n.recorded_at DESC
```

### 更正历史查询

```cypher
MATCH (new:CognitiveNode)-[r:SUPERSEDES]->(old:CognitiveNode)
WHERE new.space_id = $space_id AND old.entity_name = $entity_name
RETURN new, old, r ORDER BY r.recorded_at DESC
```

### 矛盾链查询

```cypher
MATCH (a:CognitiveNode)-[r:CONTRADICTS]->(b:CognitiveNode)
WHERE a.space_id = $space_id AND r.resolution_status = 'pending'
RETURN a, b, r
```

### 待审区查询

```cypher
MATCH (n:CognitiveNode {space_id: $space_id, belief_status: 'pending_review'})
RETURN n ORDER BY n.created_at DESC
```

### 编译产物一致性检查

```cypher
MATCH (n:CognitiveNode {space_id: $space_id, memory_type: 'mental_model'})
WHERE n.compiled_at < n.updated_at
RETURN n, n.compiled_at, n.updated_at
```

### 实体邻域查询

```cypher
MATCH (e:EntityNode {id: $entity_id})-[r]-(n)
RETURN e, r, n
LIMIT $limit
```

### 时序切片查询

```cypher
MATCH (e:EntityNode {_fact_object: $fact_object})
WHERE e.valid_from <= $as_of AND (e.valid_to IS NULL OR e.valid_to > $as_of)
RETURN e
```

### 互索引边溯源

```cypher
MATCH (n:CognitiveNode {id: $node_id})-[r:COG_EXTRACTED_FROM]->(kf:KnowledgeFragmentNode)
RETURN kf.document_id, kf.offset_start, kf.offset_end, r.confidence
```

### Bundle Search 投影

```cypher
MATCH path = (n:CognitiveNode {id: $node_id})-[r*1..3]-(m:CognitiveNode)
WHERE ALL(rel IN relationships(path) WHERE rel.confidence >= $min_confidence)
RETURN path
LIMIT $limit
```

### 跨层导航

```cypher
MATCH (kf:KnowledgeFragmentNode {id: $fragment_id})-[r:COG_SUPPORTED_BY]->(n:CognitiveNode)
RETURN n, r
```

---

## 批量写入策略

### 端点分区（对齐 m_flow）

```
1. 将边按端点分组
2. 同一端点的所有边在同一次事务中写入
3. 不同端点的边可以并行写入

分区算法：
  partition_key = min(from_id, to_id)
  edges_grouped = group_by(edges, partition_key)
  for group in edges_grouped:
      UNWIND $batch MERGE ...
```

### MERGE 幂等写入（CognitiveNode）

```cypher
UNWIND $batch AS row
MERGE (n:CognitiveNode {id: row.id})
SET n.space_id = row.space_id,
    n.cognitive_layer = row.cognitive_layer,
    n.memory_type = row.memory_type,
    n.entity_name = row.entity_name,
    n.entity_type = row.entity_type,
    n.schema_ref = row.schema_ref,
    n.text = row.text,
    n.tags = row.tags,
    n.attributes = row.attributes,
    n.version = row.version,
    n.confidence = row.confidence,
    n.strength = row.strength,
    n.feedback_weight = row.feedback_weight,
    n.proof_count = row.proof_count,
    n.access_count = row.access_count,
    n.belief_status = row.belief_status,
    n.visibility = row.visibility,
    n.valid_from = row.valid_from,
    n.valid_to = row.valid_to,
    n.recorded_at = row.recorded_at,
    n.occurred_at = row.occurred_at,
    n.compiled_at = row.compiled_at,
    n.superseded_by = row.superseded_by,
    n.source_pipeline = row.source_pipeline,
    n.source_content_hash = row.source_content_hash,
    n.updated_at = row.updated_at,
    n.consolidated_at = row.consolidated_at
```

### 乐观并发控制（OCC）

```python
async def update_cognitive_node(node_id, updates, expected_version):
    node = await get_cognitive_node(node_id)
    if node.version != expected_version:
        raise ConcurrencyError(
            f"Version mismatch: expected {expected_version}, "
            f"actual {node.version}"
        )
    updates["version"] = expected_version + 1
    await merge_cognitive_node(node_id, updates)
```

---

## 与参考项目的对齐总结

| 维度 | Cognee KuzuAdapter | m_flow GraphProvider | OntologyEngine 设计 |
|------|-------------------|---------------------|-------------------|
| 节点表 | 1（DataPoint） | 多表 | CognitiveNode(统一) + 4辅助表 |
| 边表 | 1（Next/Edge） | 多关系表 | COGNITIVE_RELATES_TO + SUPERSEDES + CONTRADICTS + 互索引边 |
| ID 策略 | UUID5 | UUID | UUID5（确定性） |
| 批量写入 | UNWIND+MERGE | UNWIND+MERGE + 端点分区 | UNWIND+MERGE + 端点分区 + OCC |
| 动态属性 | MAP | MAP | 强类型核心列 + JSON attributes |
| 时序支持 | 无 | 无 | 双时序（valid_from/to + recorded_at） |
| 溯源链 | source_pipeline | 无 | source_pipeline + source_content_hash |
| 边语义 | 无 | edge_text | edge_text + weight |
| 反馈机制 | feedback_weight | 无 | feedback_weight + strength |
| 认知分层 | 无 | 无 | cognitive_layer + memory_type |
| 信念状态 | 无 | 无 | belief_status + SUPERSEDES/CONTRADICTS |
| 并发控制 | 无 | 无 | version (OCC) |
