# KuzuDB Schema 设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/02-design/schema/instance-layer.md` + `docs/02-design/schema/mutual-index-edges.md` | **last_verified**: 2026-04-19

---

## 目的

定义 OntologyEngine 在 KuzuDB 中的节点表和边表 Schema，严格对齐 Schema v2 Instance 层的五种数据结构（EntityInstance、EdgeInstance、CategoryTag、MetricValue、KnowledgeFragment）以及互索引边的四种类型。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | DuckDB 表结构无法表达图遍历语义 | 多跳推理依赖 JOIN 递归，性能 O(n^k) |
| 2 | 节点类型无区分，所有实体混在一张表 | 无法利用 KuzuDB 的类型约束和索引优化 |
| 3 | 边缺乏语义字段（edge_text、weight） | 边只是类型标签，无法参与 Bundle Search |
| 4 | 时序字段（valid_from/valid_to）缺失 | 无法支持时间切片查询 |
| 5 | 互索引边无存储实现 | Layer-R 与 Layer-S 数据层断连 |

---

## 设计原则

| # | 原则 | 说明 |
|---|------|------|
| P-KZ-1 | 多节点表而非 2 表极简 | Cognee 使用 2 表（DataPoint + Edge），OntologyEngine 有 5 种节点类型，多表支持类型约束 |
| P-KZ-2 | 边分区写入 | m_flow 发现 UNWIND+MERGE 共享端点时触发 write-write conflict，需端点分区 |
| P-KZ-3 | MAP 类型存储动态属性 | KuzuDB MAP(STRING, STRING) 承载 attributes，避免 ALTER TABLE |
| P-KZ-4 | MERGE 幂等写入 | 基于 id 主键 MERGE，保证同一业务实体幂等 |

---

## 节点表

### EntityNode

对齐 Schema v2 `EntityInstance`。

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

| 字段 | Instance 层映射 | KuzuDB 类型 | 说明 |
|------|----------------|-------------|------|
| `id` | EntityInstance.id | STRING PK | UUID5 确定性生成 |
| `_fact_object` | EntityInstance._fact_object | STRING | 引用 L1 EntityDeclaration.name |
| `name` | EntityInstance.attributes["name"] | STRING | 实体显示名称，从 attributes 提取冗余存储 |
| `attributes` | EntityInstance.attributes | MAP(STRING, STRING) | 动态属性，值统一序列化为 STRING |
| `valid_from` | EntityInstance.valid_from | DATETIME | 时序生效时间 |
| `valid_to` | EntityInstance.valid_to | DATETIME | NULL 表示当前有效 |
| `domain_id` | EntityInstance.domain_id | STRING | 语义空间域隔离 |
| `confidence` | EntityInstance.confidence | DOUBLE | 置信度 [0, 1] |
| `source_pipeline` | EntityInstance.source_pipeline | STRING | 来源管道标识 |
| `source_content_hash` | EntityInstance.source_content_hash | STRING | SHA256 哈希 |
| `feedback_weight` | EntityInstance.feedback_weight | DOUBLE | 反馈权重 [0, 1] |

**索引**：

```cypher
CREATE INDEX idx_entity_fact_object ON EntityNode(_fact_object);
CREATE INDEX idx_entity_domain_id ON EntityNode(domain_id);
CREATE INDEX idx_entity_valid_from ON EntityNode(valid_from);
CREATE INDEX idx_entity_source_pipeline ON EntityNode(source_pipeline);
```

**与参考项目的对齐**：

| 设计点 | Cognee KuzuAdapter | m_flow GraphProvider | OntologyEngine |
|--------|-------------------|---------------------|----------------|
| 节点表数量 | 1（DataPoint） | 多表（Entity、Concept 等） | 5（EntityNode、RuleDefinitionNode 等） |
| ID 生成 | UUID5 | UUID | UUID5（确定性） |
| 动态属性 | properties MAP | attributes MAP | attributes MAP(STRING, STRING) |
| 时序字段 | 无 | 无 | valid_from/valid_to |
| 溯源字段 | source_pipeline + source_content_hash | 无 | source_pipeline + source_content_hash |
| 反馈权重 | feedback_weight | 无 | feedback_weight |

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

| 字段 | 说明 |
|------|------|
| `id` | 规则唯一标识 |
| `name` | 规则名称，引用 L4 RuleDeclaration.name |
| `rule_type` | 规则类型：threshold / composite / override |
| `condition_expr` | 条件表达式（CEL 或 DSL） |
| `action_expr` | 动作表达式 |
| `priority` | 优先级，数值越大越优先 |
| `enabled` | 是否启用 |
| `domain_id` | 语义空间域隔离 |
| `source_pipeline` | 来源管道 |
| `source_content_hash` | SHA256 哈希 |

**索引**：

```cypher
CREATE INDEX idx_rule_name ON RuleDefinitionNode(name);
CREATE INDEX idx_rule_domain_id ON RuleDefinitionNode(domain_id);
CREATE INDEX idx_rule_enabled ON RuleDefinitionNode(enabled);
```

---

### KnowledgeFragmentNode

对齐 Schema v2 `KnowledgeFragment`。

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

| 字段 | Instance 层映射 | KuzuDB 类型 | 说明 |
|------|----------------|-------------|------|
| `id` | KnowledgeFragment.id | STRING PK | 唯一标识 |
| `dataset_id` | KnowledgeFragment.dataset_id | STRING | 引用 Dataset.id |
| `document_id` | KnowledgeFragment.document_id | STRING | 文档标识 |
| `chunk_index` | KnowledgeFragment.chunk_index | INT64 | 文档内分片序号 |
| `offset_start` | KnowledgeFragment.offset_start | INT64 | 字符偏移起始 |
| `offset_end` | KnowledgeFragment.offset_end | INT64 | 字符偏移终止 |
| `text` | KnowledgeFragment.text | STRING | 原文内容 |
| `vector_id` | KnowledgeFragment.vector_id | STRING | ChromaDB 向量 ID |
| `metadata` | KnowledgeFragment.metadata | MAP(STRING, STRING) | 扩展元数据 |
| `extraction_status` | KnowledgeFragment.extraction_status | STRING | pending/extracted/failed |
| `content_hash` | KnowledgeFragment.content_hash | STRING | SHA256 内容哈希 |

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
    entity_id       STRING,
    dimension_name  STRING,
    value_code      STRING,
    assigned_at     DATETIME,
    assigned_by     STRING,
    confidence      DOUBLE DEFAULT 1.0
)
```

> **注意**：CategoryTagNode 不设独立 PRIMARY KEY，以 (entity_id, dimension_name) 作为逻辑复合主键。KuzuDB 要求节点表必须有 PK，实际实现中使用 `entity_id + ":" + dimension_name` 拼接作为 id 字段。

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

| 字段 | 说明 |
|------|------|
| `id` | `entity_id + ":" + metric_name + ":" + valid_from` 拼接 |
| `value` | 序列化为 STRING，类型由 MetricDeclaration.result_type 约束 |
| `computation_snapshot` | MAP(STRING, STRING) 存储执行快照 |

**索引**：

```cypher
CREATE INDEX idx_mv_entity_id ON MetricValueNode(entity_id);
CREATE INDEX idx_mv_metric_name ON MetricValueNode(metric_name);
CREATE INDEX idx_mv_valid_from ON MetricValueNode(valid_from);
```

---

## 边表

### 业务关系边（RELATES_TO）

对齐 Schema v2 `EdgeInstance`。使用多关系表设计，每种 RelationDeclaration 对应一张边表。

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

> **[关键设计点]**：RELATES_TO 是通用业务关系边表。当某类关系的查询频率或属性差异足够大时，应拆分为独立关系表（如 `GUARANTEES`、`INVESTS_IN`）。初始阶段使用单一 RELATES_TO 表，通过 `relation_name` 区分关系类型。

**索引**：

```cypher
CREATE INDEX idx_rel_relation_name ON RELATES_TO(relation_name);
CREATE INDEX idx_rel_confidence ON RELATES_TO(confidence);
CREATE INDEX idx_rel_valid_from ON RELATES_TO(valid_from);
```

**与参考项目的对齐**：

| 设计点 | Cognee KuzuAdapter | m_flow GraphProvider | OntologyEngine |
|--------|-------------------|---------------------|----------------|
| 边表设计 | 单一 Edge 表 | 多关系表 | 单一 RELATES_TO + 预留拆分 |
| 边语义文本 | 无 | edge_text | edge_text（向量化后参与 Bundle Search） |
| 边权重 | weight | weight | weight（参与推理成本传播） |
| 边属性 | properties MAP | attributes MAP | attributes MAP(STRING, STRING) |
| 时序字段 | 无 | 无 | valid_from/valid_to |

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
    FROM ExecutionStepSnapshotNode TO KnowledgeFragmentNode,
    id            STRING,
    source_file   STRING,
    offset_start  INT64,
    offset_end    INT64,
    confidence    DOUBLE,
    edge_text     STRING,
    created_at    DATETIME
)
```

> **[待扩展]**：TRACE_TO 的源端应为 ExecutionStepSnapshot，当前尚未定义 ExecutionStepSnapshotNode 节点表。Phase 1 暂用 EntityNode 作为源端，Phase 2 增加 ExecutionStepSnapshotNode 后修改 FROM 约束。

**互索引边索引**：

```cypher
CREATE INDEX idx_ef_confidence ON EXTRACTED_FROM(confidence);
CREATE INDEX idx_sb_confidence ON SUPPORTED_BY(confidence);
CREATE INDEX idx_di_confidence ON DEFINED_IN(confidence);
CREATE INDEX idx_tt_confidence ON TRACE_TO(confidence);
```

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

CREATE NODE TABLE EntityNode (...);
CREATE NODE TABLE RuleDefinitionNode (...);
CREATE NODE TABLE KnowledgeFragmentNode (...);
CREATE NODE TABLE CategoryTagNode (...);
CREATE NODE TABLE MetricValueNode (...);

CREATE REL TABLE RELATES_TO (...);
CREATE REL TABLE EXTRACTED_FROM (...);
CREATE REL TABLE SUPPORTED_BY (...);
CREATE REL TABLE DEFINED_IN (...);
CREATE REL TABLE TRACE_TO (...);
CREATE REL TABLE CATEGORIZED_AS (...);
CREATE REL TABLE HAS_METRIC (...);

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
CREATE INDEX idx_rel_relation_name ON RELATES_TO(relation_name);
CREATE INDEX idx_rel_confidence ON RELATES_TO(confidence);
CREATE INDEX idx_rel_valid_from ON RELATES_TO(valid_from);
CREATE INDEX idx_ef_confidence ON EXTRACTED_FROM(confidence);
CREATE INDEX idx_sb_confidence ON SUPPORTED_BY(confidence);
CREATE INDEX idx_di_confidence ON DEFINED_IN(confidence);
CREATE INDEX idx_tt_confidence ON TRACE_TO(confidence);
```

---

## Cypher 查询模式

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
MATCH (e:EntityNode {id: $entity_id})-[r:EXTRACTED_FROM]->(kf:KnowledgeFragmentNode)
RETURN kf.document_id, kf.offset_start, kf.offset_end, r.confidence
```

### Bundle Search 投影

```cypher
MATCH path = (e:EntityNode {id: $entity_id})-[r*1..3]-(n)
WHERE ALL(rel IN relationships(path) WHERE rel.confidence >= $min_confidence)
RETURN path
LIMIT $limit
```

### 跨层导航

```cypher
MATCH (kf:KnowledgeFragmentNode {id: $fragment_id})-[r:SUPPORTED_BY]->(e:EntityNode)
RETURN e, r
```

### 规则溯源

```cypher
MATCH (rd:RuleDefinitionNode {id: $rule_id})-[r:DEFINED_IN]->(kf:KnowledgeFragmentNode)
RETURN kf.document_id, kf.text, r.confidence
```

---

## 批量写入策略

### 端点分区（对齐 m_flow）

m_flow 发现 KuzuDB 在 UNWIND+MERGE 批量写入时，如果多条边共享端点，会触发 write-write conflict。解决方案：

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

### MERGE 幂等写入

```cypher
UNWIND $batch AS row
MERGE (e:EntityNode {id: row.id})
SET e._fact_object = row._fact_object,
    e.name = row.name,
    e.attributes = row.attributes,
    e.valid_from = row.valid_from,
    e.valid_to = row.valid_to,
    e.domain_id = row.domain_id,
    e.confidence = row.confidence,
    e.source_pipeline = row.source_pipeline,
    e.source_content_hash = row.source_content_hash,
    e.feedback_weight = row.feedback_weight,
    e.updated_at = row.updated_at
```

---

## 与参考项目的对齐总结

| 维度 | Cognee KuzuAdapter | m_flow GraphProvider | OntologyEngine 设计 |
|------|-------------------|---------------------|-------------------|
| 节点表 | 1（DataPoint） | 多表 | 5 节点表 |
| 边表 | 1（Next/Edge） | 多关系表 | RELATES_TO + 4 互索引边 + 2 关联边 |
| ID 策略 | UUID5 | UUID | UUID5（确定性） |
| 批量写入 | UNWIND+MERGE | UNWIND+MERGE + 端点分区 | UNWIND+MERGE + 端点分区 |
| 动态属性 | MAP | MAP | MAP(STRING, STRING) |
| 时序支持 | 无 | 无 | valid_from/valid_to |
| 溯源链 | source_pipeline | 无 | source_pipeline + source_content_hash |
| 边语义 | 无 | edge_text | edge_text + weight |
| 反馈机制 | feedback_weight | 无 | feedback_weight |
| 异步执行 | ThreadPoolExecutor | ThreadPoolExecutor | ThreadPoolExecutor |
