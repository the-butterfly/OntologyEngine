# 跨模块一致性验证报告

> **status**: draft | **phase**: Phase 9 | **source_of_truth**: 本文档 | **last_verified**: 2026-04-19

---

## 目的

对 OntologyEngine 设计文档进行跨模块一致性验证，确保 Schema grammar、Storage、Engine、Service、API 五层之间的字段、接口、术语完全对齐。

## 验证范围

| 层 | 文档 |
|----|------|
| Schema 层 | instance-layer.md, mutual-index-edges.md, temporal-modeling.md |
| Storage 层 | kuzudb-schema.md, chromadb-collections.md |
| Engine 层 | dag-execution.md, mutual-index-retrieval.md |
| Service 层 | ingestion-service.md, query-service.md |
| API 层 | query-routes.md, spaces-routes.md |

---

## 验证一：Schema grammar ↔ Storage schema 对齐

### 1.1 EntityInstance 字段对齐

| 字段 | Schema grammar | KuzuDB EntityNode | 状态 | 说明 |
|------|---------------|-------------------|------|------|
| id | string (UUID5) | STRING PK | ✅ 通过 | — |
| _fact_object | string | STRING | ✅ 通过 | — |
| name | — | STRING | ⚠️ 偏差 | KuzuDB 冗余存储 `name` 字段，Schema grammar 未定义。文档已说明为"从 attributes 提取冗余存储"，属存储优化 |
| attributes | dict | MAP(STRING, STRING) | ✅ 通过 | 类型差异为存储序列化选择，语义一致 |
| valid_from | datetime? | DATETIME | ✅ 通过 | — |
| valid_to | datetime? | DATETIME | ✅ 通过 | — |
| created_at | datetime | DATETIME | ✅ 通过 | — |
| updated_at | datetime | DATETIME | ✅ 通过 | — |
| domain_id | string? | STRING | ✅ 通过 | — |
| confidence | float | DOUBLE | ✅ 通过 | — |
| source_pipeline | string? | STRING | ✅ 通过 | — |
| source_content_hash | string? | STRING | ✅ 通过 | — |
| feedback_weight | float | DOUBLE | ✅ 通过 | — |

**结论**：✅ 基本通过。`name` 冗余字段为已知存储优化，建议在 Schema grammar 中补充说明。

### 1.2 EdgeInstance 字段对齐

| 字段 | Schema grammar | KuzuDB RELATES_TO | 状态 | 说明 |
|------|---------------|-------------------|------|------|
| id | string | STRING | ✅ 通过 | — |
| from_id | string | 隐式（FROM 约束） | ✅ 通过 | 图数据库标准做法 |
| to_id | string | 隐式（TO 约束） | ✅ 通过 | 图数据库标准做法 |
| relation_name | string | STRING | ✅ 通过 | — |
| attributes | dict? | MAP(STRING, STRING) | ✅ 通过 | — |
| edge_text | string? | STRING | ✅ 通过 | — |
| weight | float? | DOUBLE | ✅ 通过 | — |
| valid_from | datetime? | DATETIME | ✅ 通过 | — |
| valid_to | datetime? | DATETIME | ✅ 通过 | — |
| confidence | float | DOUBLE | ✅ 通过 | — |
| source_pipeline | string? | STRING | ✅ 通过 | — |
| source_content_hash | string? | STRING | ✅ 通过 | — |

**结论**：✅ 通过。

### 1.3 CategoryTag 字段对齐

| 字段 | Schema grammar | KuzuDB CategoryTagNode | 状态 | 说明 |
|------|---------------|----------------------|------|------|
| id | 不设独立 id | STRING PK | ⚠️ 偏差 | Schema 声明"不设独立 id"，KuzuDB 因技术约束需 PK，使用 `entity_id + ":" + dimension_name` 拼接。文档已说明 |
| entity_id | string | STRING | ✅ 通过 | — |
| dimension_name | string | STRING | ✅ 通过 | — |
| value_code | string | STRING | ✅ 通过 | — |
| assigned_at | datetime | DATETIME | ✅ 通过 | — |
| assigned_by | string? | STRING | ✅ 通过 | — |
| confidence | float | DOUBLE | ✅ 通过 | — |

**结论**：✅ 基本通过。PK 偏差为 KuzuDB 技术约束，已文档化。

### 1.4 MetricValue 字段对齐

| 字段 | Schema grammar | KuzuDB MetricValueNode | 状态 | 说明 |
|------|---------------|----------------------|------|------|
| id | 不设独立 id | STRING PK | ⚠️ 偏差 | 同 CategoryTag，使用复合键拼接 |
| entity_id | string | STRING | ✅ 通过 | — |
| metric_name | string | STRING | ✅ 通过 | — |
| value | any | STRING | ⚠️ 偏差 | Schema 为 `any`，KuzuDB 序列化为 STRING。类型由 MetricDeclaration.result_type 约束 |
| computed_at | datetime | DATETIME | ✅ 通过 | — |
| valid_from | datetime? | DATETIME | ✅ 通过 | — |
| valid_to | datetime? | DATETIME | ✅ 通过 | — |
| computed_by | string? | STRING | ✅ 通过 | — |
| computation_snapshot | dict? | MAP(STRING, STRING) | ⚠️ 偏差 | Schema 为 `dict?`，KuzuDB 为 MAP(STRING, STRING)。序列化选择 |

**结论**：✅ 基本通过。类型序列化偏差为存储层标准做法。

### 1.5 KnowledgeFragment 字段对齐

| 字段 | Schema grammar | KuzuDB KnowledgeFragmentNode | 状态 | 说明 |
|------|---------------|----------------------------|------|------|
| id | string | STRING PK | ✅ 通过 | — |
| dataset_id | string | STRING | ✅ 通过 | — |
| document_id | string | STRING | ✅ 通过 | — |
| chunk_index | integer | INT64 | ✅ 通过 | — |
| offset_start | integer | INT64 | ✅ 通过 | — |
| offset_end | integer | INT64 | ✅ 通过 | — |
| text | string | STRING | ✅ 通过 | — |
| vector_id | string? | STRING | ✅ 通过 | — |
| metadata | dict? | MAP(STRING, STRING) | ✅ 通过 | — |
| extraction_status | enum | STRING | ✅ 通过 | — |
| content_hash | string? | STRING | ✅ 通过 | — |
| created_at | datetime | DATETIME | ✅ 通过 | — |
| updated_at | datetime | DATETIME | ✅ 通过 | — |

**结论**：✅ 通过。

### 1.6 ChromaDB 集合与 Schema 对齐

| ChromaDB 集合 | 对齐 Schema 类型 | 状态 | 说明 |
|--------------|----------------|------|------|
| entity_name | EntityInstance | ✅ 通过 | — |
| entity_summary | EntityInstance | ✅ 通过 | 派生索引，Schema 未定义但合理 |
| facet_search_text | CategoryTag + MetricValue | ✅ 通过 | 派生索引 |
| edge_relationship_name | EdgeInstance | ✅ 通过 | — |
| edge_text | EdgeInstance + 互索引边 | ⚠️ 偏差 | 业务边和互索引边混合存储，通过 metadata.edge_type 区分。Schema 中两者为不同概念 |
| knowledge_fragment | KnowledgeFragment | ✅ 通过 | — |
| rule_definition | RuleDefinition | ✅ 通过 | Schema L4 类型 |

**结论**：✅ 基本通过。`edge_text` 集合混合存储为已知设计选择，需注意查询时必须带 edge_type 过滤。

---

## 验证二：API 路由 ↔ 服务层接口 ↔ 引擎层接口 ↔ 存储层接口对齐

### 2.1 查询接口对齐

| API 路由 | 服务层方法 | 引擎层 | 存储层 | 状态 | 说明 |
|----------|-----------|--------|--------|------|------|
| POST /v1/query/search | QueryService.query_raw | Layer-R Retriever | ChromaDB.search | ❌ 不对齐 | API 称 `semantic_search`，服务层称 `query_raw`，命名不一致 |
| POST /v1/query/graph | QueryService.query_structured | Layer-S Retriever | KuzuDB Cypher | ❌ 不对齐 | API 称 `graph_traverse`，服务层称 `query_structured`，命名不一致 |
| POST /v1/query/hybrid | QueryService.query_hybrid | Bundle Search + RRF | ChromaDB + KuzuDB | ⚠️ 部分对齐 | API 称 `hybrid_search`，服务层称 `query_hybrid`，命名接近但不一致 |
| POST /v1/query/explain | QueryService.explain | — | — | ✅ 通过 | — |
| GET /v1/query/trace/{entity_id} | — | — | — | ❌ 缺失 | API 定义了 trace 端点，但服务层无对应方法 |

### 2.2 摄入接口对齐

| API 路由 | 服务层方法 | 状态 | 说明 |
|----------|-----------|------|------|
| POST /v1/spaces/{id}/instances/entities | IngestionService.ingest_entity | ⚠️ 部分对齐 | API 使用 `concept_type`，服务层使用 `fact_object` |
| POST /v1/spaces/{id}/instances/entities/batch | IngestionService.ingest_entities_batch | ⚠️ 部分对齐 | 同上术语问题 |
| — | IngestionService.register_dataset | ❌ 缺失 | API 无 Dataset 注册端点 |
| — | IngestionService.ingest_document | ❌ 缺失 | API 无文档摄入端点 |
| — | IngestionService.resolve_contradiction | ❌ 缺失 | API 无矛盾解决端点 |

### 2.3 引擎层 ↔ 存储层对齐

| 引擎层组件 | 存储层调用 | 状态 | 说明 |
|-----------|-----------|------|------|
| DAGExecutor | KuzuDB 写入 | ⚠️ 隐式 | DAG 执行结果写入存储，但无显式接口契约 |
| RuleTransaction | KuzuDB 事务 | ⚠️ 隐式 | 快照/回滚机制未定义存储层接口 |
| RetrieverRegistry | ChromaDB + KuzuDB | ⚠️ 隐式 | 检索器注册后调用存储，但接口未形式化 |

**结论**：❌ 不通过。主要问题：(1) API 与服务层方法命名不一致；(2) API 缺少 Dataset 注册、文档摄入、矛盾解决端点；(3) API 使用旧术语 `concept_type`；(4) 引擎层与存储层缺乏显式接口契约。

---

## 验证三：互索引边在 grammar/storage/query/API 四层对齐

### 3.1 EXTRACTED_FROM 对齐

| 层 | 定义 | 状态 | 说明 |
|----|------|------|------|
| Grammar | EntityInstance → KnowledgeFragment | — | — |
| KuzuDB | EntityNode → KnowledgeFragmentNode | ✅ 通过 | — |
| ChromaDB | edge_text 集合，edge_type="EXTRACTED_FROM" | ✅ 通过 | — |
| Query Engine | Cypher 查询模板定义 | ✅ 通过 | — |
| API | 无直接端点 | ⚠️ 缺失 | 仅通过 query_hybrid 间接使用 |

### 3.2 SUPPORTED_BY 对齐

| 层 | 定义 | 状态 | 说明 |
|----|------|------|------|
| Grammar | KnowledgeFragment → EntityInstance | — | — |
| KuzuDB | KnowledgeFragmentNode → EntityNode | ✅ 通过 | — |
| ChromaDB | edge_text 集合，edge_type="SUPPORTED_BY" | ✅ 通过 | — |
| Query Engine | Cypher 查询模板定义 | ✅ 通过 | — |
| API | 无直接端点 | ⚠️ 缺失 | 仅通过 query_hybrid 间接使用 |

### 3.3 DEFINED_IN 对齐

| 层 | 定义 | 状态 | 说明 |
|----|------|------|------|
| Grammar | RuleDefinition / MetricDeclaration → KnowledgeFragment | — | — |
| KuzuDB | RuleDefinitionNode → KnowledgeFragmentNode | ❌ 不对齐 | KuzuDB 仅支持 RuleDefinitionNode 作为源端，不支持 MetricDeclaration。KuzuDB 无 MetricDeclarationNode 节点表 |
| ChromaDB | edge_text 集合，edge_type="DEFINED_IN" | ✅ 通过 | — |
| Query Engine | Cypher 查询模板定义 | ✅ 通过 | — |
| API | 无直接端点 | ⚠️ 缺失 | — |

### 3.4 TRACE_TO 对齐

| 层 | 定义 | 状态 | 说明 |
|----|------|------|------|
| Grammar | ExecutionStepSnapshot → KnowledgeFragment | — | — |
| KuzuDB | EntityNode → KnowledgeFragmentNode | ❌ 不对齐 | 源端类型不匹配。KuzuDB 无 ExecutionStepSnapshotNode，暂用 EntityNode 替代。已标注 [待扩展] |
| ChromaDB | edge_text 集合，edge_type="TRACE_TO" | ✅ 通过 | — |
| Query Engine | Cypher 查询使用 EntityNode | ⚠️ 部分对齐 | 与 KuzuDB 一致，但与 Grammar 不一致 |
| API | GET /v1/query/trace/{entity_id} | ⚠️ 部分对齐 | API 端点存在但参数和语义与 Grammar 不完全匹配 |

### 3.5 互索引边公共字段对齐

| 字段 | Grammar | KuzuDB | ChromaDB | 状态 | 说明 |
|------|---------|--------|----------|------|------|
| id | string | STRING | — | ✅ 通过 | — |
| from_id | string | 隐式 | metadata | ✅ 通过 | — |
| to_id | string | 隐式 | metadata | ✅ 通过 | — |
| edge_type | enum | 隐式（表名） | metadata.edge_type | ⚠️ 偏差 | KuzuDB 无显式字段，ChromaDB 有。跨存储查询时需注意映射 |
| source_file | string | STRING | metadata | ✅ 通过 | — |
| offset_start | integer | INT64 | metadata | ✅ 通过 | — |
| offset_end | integer | INT64 | metadata | ✅ 通过 | — |
| confidence | float | DOUBLE | metadata | ✅ 通过 | — |
| edge_text | string? | STRING | embedding | ✅ 通过 | — |
| created_at | datetime | DATETIME | — | ✅ 通过 | — |

**结论**：❌ 不通过。关键问题：(1) TRACE_TO 源端类型 Grammar 与 Storage 不一致（ExecutionStepSnapshot vs EntityNode）；(2) DEFINED_IN 不支持 MetricDeclaration 源端（KuzuDB 无 MetricDeclarationNode）；(3) API 缺少互索引边直接查询端点；(4) edge_type 在 KuzuDB 与 ChromaDB 间表达方式不同。

---

## 验证四：时态字段在 grammar/storage/query/API 四层对齐

### 4.1 valid_from / valid_to 字段对齐

| 数据类型 | Grammar | KuzuDB | ChromaDB | Query Engine | Service | API | 状态 |
|---------|---------|--------|----------|-------------|---------|-----|------|
| EntityInstance | ✅ 定义 | ✅ DATETIME | ❌ 无 | ✅ as_of 过滤 | ✅ as_of 参数 | ❌ 无 as_of | ❌ 不对齐 |
| EdgeInstance | ✅ 定义 | ✅ DATETIME | ❌ 无 | ✅ as_of 过滤 | ✅ as_of 参数 | ❌ 无 as_of | ❌ 不对齐 |
| MetricValue | ✅ 定义 | ✅ DATETIME | ❌ 无 | — | — | ❌ 无 | ⚠️ 部分对齐 |

### 4.2 时序边类型对齐

| 边类型 | Grammar | KuzuDB | IngestionService | 状态 | 说明 |
|--------|---------|--------|-----------------|------|------|
| PRECEDES | ✅ 定义 | ❌ 未定义 | ✅ 提及创建 | ❌ 不对齐 | Grammar 和 Service 定义了，但 KuzuDB 无对应边表 |
| SUCCEEDS | ✅ 定义 | ❌ 未定义 | ✅ 提及创建 | ❌ 不对齐 | 同上 |
| LEADS_TO | ✅ 定义 | ❌ 未定义 | ✅ 慢速通道产出 | ❌ 不对齐 | 同上 |
| BECAUSE_OF | ✅ 定义 | ❌ 未定义 | ✅ 慢速通道产出 | ❌ 不对齐 | 同上 |
| ENABLES | ✅ 定义 | ❌ 未定义 | — | ❌ 不对齐 | — |
| PREVENTS | ✅ 定义 | ❌ 未定义 | — | ❌ 不对齐 | — |
| same_entity_as | ✅ 定义 | ❌ 未定义 | — | ❌ 不对齐 | — |

### 4.3 时序查询语义对齐

| 查询语义 | Grammar | Query Engine | Service | API | 状态 |
|----------|---------|-------------|---------|-----|------|
| 当前版本 | ✅ valid_to IS NULL | ✅ Cypher 模式 | ✅ 默认行为 | ❌ 无参数 | ❌ 不对齐 |
| 指定时点 | ✅ as_of 过滤 | ✅ Cypher 模式 | ✅ as_of 参数 | ❌ 无 as_of 参数 | ❌ 不对齐 |
| 全量历史 | ✅ include_history | ✅ 支持 | ✅ 支持 | ❌ 无参数 | ❌ 不对齐 |
| 变更轨迹 | ✅ ORDER BY valid_from | — | — | ❌ 无端点 | ❌ 不对齐 |

### 4.4 ChromaDB 时序过滤

| 集合 | 时序字段 | 状态 | 说明 |
|------|---------|------|------|
| entity_name | ❌ 无 valid_from/valid_to | ❌ 缺失 | 无法按时序过滤向量检索结果 |
| entity_summary | ❌ 无 valid_from/valid_to | ❌ 缺失 | 同上 |
| knowledge_fragment | ❌ 无 valid_from/valid_to | ⚠️ 可接受 | KnowledgeFragment 本身无时序字段 |
| edge_text | ❌ 无 valid_from/valid_to | ❌ 缺失 | 无法按时序过滤边向量检索 |

**结论**：❌ 不通过。关键问题：(1) API 查询路由缺少 `as_of`、`include_history` 等时序查询参数；(2) KuzuDB 未定义 7 种时序边表（PRECEDES/SUCCEEDS/LEADS_TO 等），但 Grammar 和 Service 层已引用；(3) ChromaDB 集合 metadata 缺少 valid_from/valid_to 字段，无法在向量检索中进行时序过滤。

---

## 验证五：术语一致性

### 5.1 核心术语一致性

| 概念 | Schema grammar | Storage | Service | API | 状态 | 说明 |
|------|---------------|---------|---------|-----|------|------|
| 要素对象类型 | _fact_object | _fact_object | fact_object | concept_type | ❌ 不一致 | API 使用旧术语 `concept_type`，其余层使用 `_fact_object`/`fact_object` |
| 关系名称 | relation_name | relation_name | — | relation_type | ❌ 不一致 | Schema/Storage 用 `relation_name`，API 用 `relation_type` |
| 实体实例 | EntityInstance | EntityNode | EntityResult | entity | ⚠️ 可接受 | 各层命名约定不同，但语义清晰 |
| 边实例 | EdgeInstance | RELATES_TO | EdgeResult | relation | ⚠️ 可接受 | 同上 |
| 知识碎片 | KnowledgeFragment | KnowledgeFragmentNode | FragmentResult | — | ⚠️ 可接受 | — |
| 规则定义 | RuleDefinition | RuleDefinitionNode | — | RuleGroup (Phase 2) | ⚠️ 过渡期 | API 文档标注 Phase 2 统一 |
| 规则逻辑 | RuleLogic | — | — | RuleStep (Phase 2) | ⚠️ 过渡期 | 同上 |

### 5.2 方法命名一致性

| 功能 | API 路由方法名 | 服务层方法名 | 状态 | 说明 |
|------|--------------|------------|------|------|
| 语义搜索 | semantic_search | query_raw | ❌ 不一致 | 同一功能三个不同名称 |
| 图遍历 | graph_traverse | query_structured | ❌ 不一致 | 同上 |
| 混合检索 | hybrid_search | query_hybrid | ⚠️ 接近 | 命名风格不统一 |
| 规则追溯 | trace_rule | — | ❌ 缺失 | API 有端点，服务层无方法 |

### 5.3 字段命名一致性

| 字段 | Schema | API | 状态 | 说明 |
|------|--------|-----|------|------|
| 实体类型 | _fact_object | concept_type | ❌ 不一致 | — |
| 关系类型 | relation_name | relation_type | ❌ 不一致 | — |
| 过滤条件 | — | filters | ⚠️ 可接受 | API 层概念 |
| 置信度 | confidence | — | ✅ 一致 | — |
| 反馈权重 | feedback_weight | — | ✅ 一致 | — |
| 域隔离 | domain_id | — | ⚠️ 缺失 | API 未暴露 domain_id 过滤 |

**结论**：❌ 不通过。关键问题：(1) `concept_type` vs `_fact_object` 跨层不一致；(2) `relation_type` vs `relation_name` 跨层不一致；(3) API 与服务层方法命名风格不统一。

---

## 问题汇总与优先级

### 🔴 严重（必须修复）

| # | 问题 | 影响层 | 修复建议 |
|---|------|--------|---------|
| S-1 | TRACE_TO 源端类型不一致：Grammar 定义为 ExecutionStepSnapshot，KuzuDB 使用 EntityNode | Grammar ↔ Storage | 在 KuzuDB schema 中新增 ExecutionStepSnapshotNode 节点表，修改 TRACE_TO 的 FROM 约束。Phase 2 必须完成 |
| S-2 | DEFINED_IN 不支持 MetricDeclaration 源端：KuzuDB 无 MetricDeclarationNode | Grammar ↔ Storage | 在 KuzuDB schema 中新增 MetricDeclarationNode 节点表，修改 DEFINED_IN 的 FROM 约束支持多源端类型 |
| S-3 | API 使用旧术语 `concept_type`，Schema v2 使用 `_fact_object` | API ↔ Schema ↔ Service | 统一 API 请求/响应字段为 `_fact_object` 或 `fact_object`，保留 `concept_type` 作为兼容层别名 |
| S-4 | API 查询路由缺少时序查询参数（as_of、include_history） | API ↔ Service ↔ Grammar | 在 POST /v1/query/graph 和 POST /v1/query/hybrid 请求体中增加 `as_of`、`include_history` 参数 |
| S-5 | KuzuDB 未定义 7 种时序边表（PRECEDES/SUCCEEDS/LEADS_TO/BECAUSE_OF/ENABLES/PREVENTS/same_entity_as） | Grammar ↔ Storage ↔ Service | 在 kuzudb-schema.md 中补充时序边表定义，与 temporal-modeling.md 对齐 |

### 🟡 中等（建议修复）

| # | 问题 | 影响层 | 修复建议 |
|---|------|--------|---------|
| M-1 | API 与服务层方法命名不一致（semantic_search vs query_raw 等） | API ↔ Service | 统一命名：建议 API 路由名与服务层方法名对齐，或建立显式映射表 |
| M-2 | API 缺少 Dataset 注册、文档摄入、矛盾解决端点 | API ↔ Service | 在 spaces-routes.md 或新增 actions-routes.md 中补充对应端点 |
| M-3 | ChromaDB 集合 metadata 缺少 valid_from/valid_to 字段 | Storage ↔ Query | 在 entity_name、entity_summary、edge_text 集合的 metadata 中增加 valid_from/valid_to 字段 |
| M-4 | API 使用 `relation_type`，Schema/Storage 使用 `relation_name` | API ↔ Schema | 统一为 `relation_name`，与 Schema v2 对齐 |
| M-5 | GET /v1/query/trace/{entity_id} 在服务层无对应方法 | API ↔ Service | 在 QueryService 中补充 `trace_rule` 方法定义 |
| M-6 | API 未暴露 domain_id 过滤能力 | API ↔ Storage | 在查询路由的 filters 中支持 domain_id 过滤 |

### 🟢 轻微（可选修复）

| # | 问题 | 影响层 | 修复建议 |
|---|------|--------|---------|
| L-1 | KuzuDB EntityNode 冗余 `name` 字段，Schema grammar 未定义 | Schema ↔ Storage | 在 instance-layer.md 中补充说明 `name` 为存储层冗余优化字段 |
| L-2 | CategoryTag/MetricValue 的 KuzuDB PK 与 Schema "不设独立 id" 偏差 | Schema ↔ Storage | 已文档化，无需修改，但建议在 Schema grammar 中增加存储映射说明 |
| L-3 | ChromaDB edge_text 集合混合存储业务边和互索引边 | Storage | 已文档化，查询时需带 edge_type 过滤。建议在 chromadb-collections.md 中增加注意事项 |
| L-4 | MetricValue.value 类型为 any（Schema）vs STRING（KuzuDB） | Schema ↔ Storage | 存储序列化选择，建议在 Schema grammar 中增加存储映射说明 |
| L-5 | 引擎层与存储层缺乏显式接口契约 | Engine ↔ Storage | 建议在 storage/interfaces.md 中定义引擎层调用的存储接口 |

---

## 验证结论

| 验证项 | 状态 | 通过率 |
|--------|------|--------|
| 验证一：Schema grammar ↔ Storage schema 对齐 | ✅ 基本通过 | 95% |
| 验证二：API ↔ Service ↔ Engine ↔ Storage 接口对齐 | ❌ 不通过 | 50% |
| 验证三：互索引边四层对齐 | ❌ 不通过 | 65% |
| 验证四：时态字段四层对齐 | ❌ 不通过 | 40% |
| 验证五：术语一致性 | ❌ 不通过 | 55% |

**总体评估**：❌ 不通过。Schema 与 Storage 层对齐较好，但 API 层与 Schema/Service 层存在显著偏差，时态字段和互索引边的跨层对齐存在结构性缺口。需优先修复 5 个严重问题后重新验证。

---

## 修复路线建议

```
Phase 1（紧急）：
  S-3: API concept_type → _fact_object 统一
  S-4: API 增加 as_of / include_history 参数
  S-5: KuzuDB 补充时序边表定义

Phase 2（重要）：
  S-1: KuzuDB 新增 ExecutionStepSnapshotNode
  S-2: KuzuDB 新增 MetricDeclarationNode
  M-1: API ↔ Service 方法命名统一
  M-2: API 补充 Dataset/文档摄入/矛盾解决端点
  M-4: API relation_type → relation_name 统一

Phase 3（改善）：
  M-3: ChromaDB metadata 增加时序字段
  M-5: QueryService 补充 trace_rule 方法
  M-6: API 暴露 domain_id 过滤
  L-1~L-5: 轻微偏差修复
```
