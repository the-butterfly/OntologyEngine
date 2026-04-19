# ChromaDB 集合设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/02-design/schema/instance-layer.md` + `docs/02-design/schema/mutual-index-edges.md` | **last_verified**: 2026-04-19

---

## 目的

定义 OntologyEngine 在 ChromaDB 中的向量集合设计，实现实体名称、实体摘要、切面文本、边语义、知识碎片、规则定义的语义检索能力。ChromaDB 是 Layer-R 向量检索和 Bundle Search 的核心引擎。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 当前 LocalVectorStore 内存实现无持久化 | 重启后向量索引丢失，无法支撑语义检索 |
| 2 | 实体名称和摘要混在一起索引 | 名称检索和摘要检索的语义空间不同，混合索引降低精度 |
| 3 | 边语义无法被向量检索 | 边只是类型标签，无法参与 Bundle Search |
| 4 | 互索引边的 edge_text 无向量索引 | 互索引边无法参与向量检索，跨层跳转依赖精确匹配 |
| 5 | 缺乏 metadata 过滤 | 无法按 domain_id、confidence、edge_type 等维度过滤检索结果 |

---

## 集合总览

| # | 集合名称 | 索引内容 | 向量维度 | 对齐 Instance 层 |
|---|---------|---------|---------|-----------------|
| 1 | `entity_name` | EntityInstance.name | 1536 | EntityInstance |
| 2 | `entity_summary` | EntityInstance 摘要文本 | 1536 | EntityInstance |
| 3 | `facet_search_text` | CategoryTag + MetricValue 组合文本 | 1536 | CategoryTag + MetricValue |
| 4 | `edge_relationship_name` | EdgeInstance.relation_name | 1536 | EdgeInstance |
| 5 | `edge_text` | EdgeInstance.edge_text | 1536 | EdgeInstance |
| 6 | `knowledge_fragment` | KnowledgeFragment.text | 1536 | KnowledgeFragment |
| 7 | `rule_definition` | RuleDefinition 条件+动作文本 | 1536 | RuleDefinition |

**互索引边向量**：互索引边的 edge_text 向量存储在 `edge_text` 集合中，通过 metadata.edge_type 区分。

---

## 嵌入策略

### 默认模型

| 参数 | 值 |
|------|-----|
| 主模型 | OpenAI text-embedding-3-small |
| 维度 | 1536 |
| 备选模型 | sentence-transformers/all-MiniLM-L6-v2 |
| 备选维度 | 384 |
| 选择逻辑 | 有 OpenAI API Key → text-embedding-3-small；否则 → all-MiniLM-L6-v2 |

### 嵌入函数

```python
class EmbeddingFunction:
    def __init__(self, config: StorageConfig):
        if config.openai_api_key:
            self._fn = chromadb.utils.embedding_functions.OpenAIEmbeddingFunction(
                api_key=config.openai_api_key,
                model_name="text-embedding-3-small",
            )
        else:
            self._fn = chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2",
            )

    def __call__(self, input: list[str]) -> list[list[float]]:
        return self._fn(input)
```

### 与参考项目的对齐

| 设计点 | MemPalace | m_flow VectorProvider | OntologyEngine |
|--------|-----------|----------------------|----------------|
| 嵌入模型 | all-MiniLM-L6-v2 | text-embedding-3-small | text-embedding-3-small + all-MiniLM-L6-v2 fallback |
| 向量维度 | 384 | 1536 | 1536（主）/ 384（备选） |
| 集合数量 | 1（Drawer） | 多集合 | 7 |
| metadata 过滤 | Wing/Room | 无 | domain_id + confidence + edge_type |

---

## 集合详细设计

### 1. entity_name

**目的**：支持实体名称的精确语义匹配，用于实体消歧和链接。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | EntityInstance.id |
| embedding | float[1536] | name 字段的向量嵌入 |
| document | string | EntityInstance.name |
| metadata | dict | 见下表 |

**metadata 字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| _fact_object | string | 引用 L1 EntityDeclaration.name |
| domain_id | string | 语义空间域 |
| confidence | float | 置信度 |
| source_pipeline | string | 来源管道 |

**检索场景**：

```
查询：find_entity("华为技术有限公司")
→ ChromaDB.search("entity_name", query_embedding, n_results=10, where={"domain_id": "finance"})
→ 返回名称语义最接近的实体列表
```

---

### 2. entity_summary

**目的**：支持实体摘要的语义检索，用于 Bundle Search 宽网撒播阶段。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | EntityInstance.id + ":summary" |
| embedding | float[1536] | 摘要文本的向量嵌入 |
| document | string | 实体摘要（由 attributes 生成） |
| metadata | dict | 见下表 |

**metadata 字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| entity_id | string | 引用 EntityInstance.id |
| _fact_object | string | 引用 L1 EntityDeclaration.name |
| domain_id | string | 语义空间域 |
| feedback_weight | float | 反馈权重 |

**摘要生成策略**：

```
摘要 = f"{name}: " + "; ".join(f"{k}={v}" for k, v in sorted(attributes.items()) if k != "name")
```

**检索场景**：

```
查询：search("资产负债率高的企业")
→ ChromaDB.search("entity_summary", query_embedding, n_results=50, where={"_fact_object": "finance:Counterparty"})
→ 返回摘要语义最接近的实体列表
```

---

### 3. facet_search_text

**目的**：支持分类标注和指标值的组合语义检索，用于 Bundle Search 的切面路径。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | CategoryTag.id 或 MetricValue.id |
| embedding | float[1536] | 切面文本的向量嵌入 |
| document | string | 切面描述文本 |
| metadata | dict | 见下表 |

**metadata 字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| entity_id | string | 引用 EntityInstance.id |
| facet_type | string | "category" 或 "metric" |
| dimension_name | string | 维度名称 |
| value_code | string | 值码（category）或值（metric） |
| domain_id | string | 语义空间域 |

**切面文本生成**：

```
CategoryTag: f"{dimension_name}={value_code}"
MetricValue: f"{metric_name}={value}"
```

---

### 4. edge_relationship_name

**目的**：支持关系名称的语义检索，用于 Bundle Search 的边类型匹配。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | EdgeInstance.id + ":rel" |
| embedding | float[1536] | relation_name 的向量嵌入 |
| document | string | EdgeInstance.relation_name |
| metadata | dict | 见下表 |

**metadata 字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| edge_id | string | EdgeInstance.id |
| from_id | string | 源实体 ID |
| to_id | string | 目标实体 ID |
| relation_name | string | 关系名称 |
| confidence | float | 置信度 |
| edge_type | string | "business" |

---

### 5. edge_text

**目的**：支持边语义文本的向量检索，用于 Bundle Search 的边语义匹配。互索引边的 edge_text 也存储在此集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | EdgeInstance.id + ":text" 或互索引边 id |
| embedding | float[1536] | edge_text 的向量嵌入 |
| document | string | EdgeInstance.edge_text |
| metadata | dict | 见下表 |

**metadata 字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| edge_id | string | 边 ID |
| from_id | string | 源端 ID |
| to_id | string | 目标端 ID |
| edge_type | string | "business" / "EXTRACTED_FROM" / "SUPPORTED_BY" / "DEFINED_IN" / "TRACE_TO" |
| confidence | float | 置信度 |
| source_file | string | 来源文件（互索引边） |

**检索场景**：

```
查询：search("担保关系")
→ ChromaDB.search("edge_text", query_embedding, n_results=20, where={"edge_type": "business"})
→ 返回边语义最接近的关系列表

查询：search("风险评级依据")
→ ChromaDB.search("edge_text", query_embedding, n_results=20, where={"edge_type": "DEFINED_IN"})
→ 返回规则定义来源的互索引边
```

---

### 6. knowledge_fragment

**目的**：支持 KnowledgeFragment 原文的语义检索，是 Layer-R 检索的核心集合。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | KnowledgeFragment.vector_id |
| embedding | float[1536] | KnowledgeFragment.text 的向量嵌入 |
| document | string | KnowledgeFragment.text |
| metadata | dict | 见下表 |

**metadata 字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| fragment_id | string | KnowledgeFragment.id |
| dataset_id | string | 数据集 ID |
| document_id | string | 文档 ID |
| chunk_index | int | 分片序号 |
| offset_start | int | 字符偏移起始 |
| offset_end | int | 字符偏移终止 |
| extraction_status | string | pending/extracted/failed |
| content_hash | string | SHA256 哈希 |

**检索场景**：

```
查询：search("企业A 财务 风险")
→ ChromaDB.search("knowledge_fragment", query_embedding, n_results=100, where={"dataset_id": "ds_001"})
→ 返回语义最接近的知识碎片列表
```

**与参考项目的对齐**：

| 设计点 | MemPalace | m_flow VectorProvider | OntologyEngine |
|--------|-----------|----------------------|----------------|
| 集合名称 | Drawer | 多集合 | knowledge_fragment |
| 文本来源 | verbatim 原文 | ContentFragment.text | KnowledgeFragment.text |
| metadata | Wing/Room/Trunk | 无 | dataset_id + document_id + offset |
| 检索模式 | 单集合 | 多集合并行 | 单集合 + metadata 过滤 |

---

### 7. rule_definition

**目的**：支持规则定义的语义检索，用于规则推荐和冲突检测。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | RuleDefinitionNode.id |
| embedding | float[1536] | 条件+动作文本的向量嵌入 |
| document | string | 规则描述文本 |
| metadata | dict | 见下表 |

**metadata 字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| rule_id | string | RuleDefinitionNode.id |
| rule_name | string | 规则名称 |
| rule_type | string | threshold/composite/override |
| domain_id | string | 语义空间域 |
| enabled | bool | 是否启用 |

**规则描述文本生成**：

```
f"规则 {name}: 当 {condition_expr} 时，执行 {action_expr}"
```

---

## CRUD 操作

### Create Collection

```python
async def create_collection(self, name: str, metadata: dict | None = None) -> None:
    self._client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine", **(metadata or {})},
        embedding_function=self._embedding_fn,
    )
```

### Upsert

```python
async def upsert(
    self,
    collection_name: str,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    collection = self._client.get_collection(collection_name, embedding_function=self._embedding_fn)
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
```

### Search

```python
async def search(
    self,
    collection_name: str,
    query_texts: list[str] | None = None,
    query_embeddings: list[list[float]] | None = None,
    n_results: int = 10,
    where: dict | None = None,
    where_document: dict | None = None,
) -> QueryResult:
    collection = self._client.get_collection(collection_name, embedding_function=self._embedding_fn)
    return collection.query(
        query_texts=query_texts,
        query_embeddings=query_embeddings,
        n_results=n_results,
        where=where,
        where_document=where_document,
    )
```

### Delete

```python
async def delete(
    self,
    collection_name: str,
    ids: list[str] | None = None,
    where: dict | None = None,
) -> None:
    collection = self._client.get_collection(collection_name, embedding_function=self._embedding_fn)
    collection.delete(ids=ids, where=where)
```

---

## 语义搜索与 metadata 过滤

### 过滤语法

ChromaDB 支持 `where` 子句进行 metadata 过滤：

```python
where = {"domain_id": "finance"}
where = {"confidence": {"$gte": 0.5}}
where = {"$and": [{"domain_id": "finance"}, {"confidence": {"$gte": 0.5}}]}
where = {"edge_type": {"$in": ["EXTRACTED_FROM", "SUPPORTED_BY"]}}
```

### 典型过滤场景

| 场景 | 集合 | where 条件 |
|------|------|-----------|
| 金融域实体检索 | entity_name | `{"domain_id": "finance"}` |
| 高置信度边检索 | edge_text | `{"confidence": {"$gte": 0.8}}` |
| 互索引边检索 | edge_text | `{"edge_type": {"$in": ["EXTRACTED_FROM", "SUPPORTED_BY"]}}` |
| 已提取碎片检索 | knowledge_fragment | `{"extraction_status": "extracted"}` |
| 启用规则检索 | rule_definition | `{"enabled": true}` |

---

## Bundle Search 集成

### Phase 1：宽网撒播

```python
results = {}
for collection_name in ["entity_name", "entity_summary", "edge_text", "knowledge_fragment"]:
    results[collection_name] = await vector_store.search(
        collection_name=collection_name,
        query_embeddings=[query_embedding],
        n_results=100,
        where={"domain_id": domain_id} if domain_id else None,
    )
```

### Phase 2：投影到图

```
entity_name 命中 → EntityNode.id 列表
entity_summary 命中 → EntityNode.id 列表
edge_text 命中 → 边 from_id/to_id 列表 + 互索引边
knowledge_fragment 命中 → KnowledgeFragmentNode.id 列表
→ 合并为图节点集合
→ KuzuDB get_neighborhood 扩展
```

### 评分公式

```
final_score = λ × semantic_score + (1 - λ) × feedback_weight

λ = 0.7（默认，可配置）
semantic_score = 1 - cosine_distance
feedback_weight 来自 EntityNode.feedback_weight
```

---

## 初始化

```python
COLLECTION_NAMES = [
    "entity_name",
    "entity_summary",
    "facet_search_text",
    "edge_relationship_name",
    "edge_text",
    "knowledge_fragment",
    "rule_definition",
]

async def initialize_collections(self) -> None:
    for name in COLLECTION_NAMES:
        await self.create_collection(name)
```

---

## 与参考项目的对齐总结

| 维度 | MemPalace ChromaDB | m_flow VectorProvider | OntologyEngine |
|------|-------------------|----------------------|----------------|
| 集合数量 | 1（Drawer） | 多集合 | 7 |
| 嵌入模型 | all-MiniLM-L6-v2 | text-embedding-3-small | text-embedding-3-small + fallback |
| metadata 过滤 | Wing/Room | 无 | domain_id + confidence + edge_type |
| 持久化 | PersistentClient | PersistentClient | PersistentClient |
| 检索模式 | 单集合 | 多集合并行 | 多集合并行 + metadata 过滤 |
| 边向量 | 无 | 无 | edge_text 集合 |
| 互索引边向量 | 无 | 无 | edge_text 集合（edge_type 区分） |
| 反馈权重 | 无 | 无 | entity_summary 集合 feedback_weight |
