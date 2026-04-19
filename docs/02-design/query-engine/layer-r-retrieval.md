# Layer-R 向量检索

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/08-knowledge-retrieval.md` + `docs/02-design/storage/chromadb-collections.md` | **last_verified**: 2026-04-19

## 目的

定义 Layer-R 向量检索的完整流程，包括 ChromaDB 向量搜索、metadata 过滤、EXTRACTED_FROM 边扩展到 Layer-S，以及 FragmentResult 结果格式。Layer-R 是原始知识层的检索入口，服务于探索性查询和需要原文证据的场景。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 当前无向量检索实现 | 无法对 KnowledgeFragment 执行语义搜索 |
| 2 | 检索结果无法扩展到结构化知识 | 向量检索返回碎片后无法自动关联到 EntityInstance |
| 3 | 缺乏 metadata 过滤 | 无法按 dataset_id、domain_id、extraction_status 等维度过滤 |
| 4 | 结果格式未定义 | 上层无法统一消费检索结果 |

---

## 适用场景

| 场景 | 说明 |
|------|------|
| 探索性查询 | 不知道精确答案在哪里，需要语义匹配 |
| 原文证据查询 | 需要返回原文段落作为证据支撑 |
| 历史文档问答 | 无结构化索引的 PDF/HTML 文档 |
| factual 查询类型 | "谁/什么/哪个"类事实查询 |
| 协同检索的 Layer-R 阶段 | mixed 查询的碎片检索阶段 |

---

## 检索流程

```
query_raw(query, filters)
     │
     ▼
┌─────────────────────────────┐
│ 1. 查询嵌入                  │
│    query → embedding         │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 2. ChromaDB 向量检索         │
│    collection: knowledge_fragment │
│    top_k: 由查询路由决定      │
│    where: metadata 过滤      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 3. 结果排序与截断            │
│    cosine_distance 排序      │
│    confidence 阈值过滤       │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 4. EXTRACTED_FROM 扩展（可选）│
│    frag → EntityInstance     │
│    KuzuDB 溯源查询           │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 5. 组装 FragmentResult       │
│    碎片 + 关联实体 + 元数据   │
└─────────────────────────────┘
```

---

## ChromaDB 向量检索

### 目的

定义 Layer-R 核心的 ChromaDB 向量检索操作，严格对齐 `chromadb-collections.md` 中的 `knowledge_fragment` 集合设计。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 向量检索接口未定义 | 定义 search 接口对齐 ChromaDB API |
| 2 | metadata 过滤语法不明确 | 对齐 ChromaDB where 子句语法 |

### 检索接口

```python
async def search_knowledge_fragments(
    query_embedding: list[float],
    top_k: int = 10,
    where: dict | None = None,
    where_document: dict | None = None,
) -> ChromaQueryResult:
    collection = client.get_collection("knowledge_fragment", embedding_function=embedding_fn)
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
        where_document=where_document,
    )
```

### metadata 过滤场景

| 场景 | where 条件 |
|------|-----------|
| 按数据集过滤 | `{"dataset_id": "ds_001"}` |
| 按文档过滤 | `{"document_id": "doc_042"}` |
| 已提取碎片 | `{"extraction_status": "extracted"}` |
| 按内容哈希去重 | `{"content_hash": "sha256:abc123"}` |
| 组合过滤 | `{"$and": [{"dataset_id": "ds_001"}, {"extraction_status": "extracted"}]}` |

### 评分公式

```
semantic_score = 1 - cosine_distance

final_score = λ × semantic_score + (1 - λ) × feedback_weight

λ = 0.7（默认，可配置）
feedback_weight 来自 EntityNode.feedback_weight（通过 EXTRACTED_FROM 关联获取）
```

---

## EXTRACTED_FROM 扩展

### 目的

定义从 Layer-R 检索结果通过 EXTRACTED_FROM 互索引边扩展到 Layer-S EntityInstance 的流程。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 向量检索结果停留在碎片层 | EXTRACTED_FROM 边导航到关联实体 |
| 2 | 碎片缺乏业务语义 | 关联实体提供业务上下文 |

### 扩展流程

```
FragmentResult[frag_001]
     │
     ▼ KuzuDB 查询
MATCH (e:EntityNode)-[r:EXTRACTED_FROM]->(kf:KnowledgeFragmentNode {id: "frag_001"})
RETURN e, r.confidence, r.edge_text
     │
     ▼
EntityResult[ent_A_financial]
  confidence: 1.0
  edge_text: "交易对手基本信息从授信管理办法第3.2节提取"
```

### 扩展条件

| 条件 | 说明 |
|------|------|
| 查询类型为 factual | 默认开启 EXTRACTED_FROM 扩展 |
| 查询类型为 mixed | 协同检索中自动执行 |
| 碎片 extraction_status = "extracted" | 只有已提取的碎片才有关联实体 |
| confidence >= 阈值 | 低置信度扩展结果可选过滤 |

### KuzuDB 查询模板

```cypher
MATCH (e:EntityNode)-[r:EXTRACTED_FROM]->(kf:KnowledgeFragmentNode)
WHERE kf.id IN $fragment_ids
  AND r.confidence >= $min_confidence
RETURN e.id, e.name, e._fact_object, r.confidence, r.edge_text
```

---

## FragmentResult 结果格式

### 目的

定义 Layer-R 检索的标准化输出格式，供 RRF 融合和上层 API 消费。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 检索结果格式不统一 | FragmentResult 标准化输出 |
| 2 | 缺乏溯源信息 | 包含 source_document + offset 信息 |

### 数据结构

```python
@dataclass
class FragmentResult:
    fragment_id: str
    text: str
    score: float
    dataset_id: str
    document_id: str
    chunk_index: int
    offset_start: int
    offset_end: int
    extraction_status: str
    content_hash: str
    linked_entities: List[LinkedEntity]
    metadata: Dict[str, Any]

@dataclass
class LinkedEntity:
    entity_id: str
    entity_name: str
    fact_object: str
    confidence: float
    edge_text: str
```

### 结果示例

```json
{
    "fragment_id": "frag_001",
    "text": "2024年报：营收3.2亿，资产负债率65%...",
    "score": 0.82,
    "dataset_id": "ds_annual_reports",
    "document_id": "企业A_2024年报.pdf",
    "chunk_index": 12,
    "offset_start": 4500,
    "offset_end": 4900,
    "extraction_status": "extracted",
    "content_hash": "sha256:abc123",
    "linked_entities": [
        {
            "entity_id": "ent_A_financial",
            "entity_name": "企业A",
            "fact_object": "finance:Counterparty",
            "confidence": 1.0,
            "edge_text": "交易对手基本信息从授信管理办法第3.2节提取"
        }
    ],
    "metadata": {
        "author": "财务部",
        "date": "2024-03-15"
    }
}
```

---

## 与参考项目的对齐

| 维度 | MemPalace | m_flow | KAG | OntologyEngine |
|------|-----------|--------|-----|----------------|
| 向量存储 | ChromaDB Drawer | VectorProvider 多集合 | DPR 向量索引 | ChromaDB knowledge_fragment |
| metadata 过滤 | Wing/Room | 无 | 无 | dataset_id + document_id + offset |
| 结果扩展 | 无 | includes_chunk 反向 | Chunk→KU 链接 | EXTRACTED_FROM 扩展 |
| 评分方式 | cosine similarity | cosine distance + bonus | DPR score | semantic + feedback_weight |
| 溯源粒度 | 文档级 | ContentFragment 级 | Chunk 级 | 块 + 段落偏移（offset_start/end） |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-LR-1 | Layer-R 默认搜索 knowledge_fragment 集合 | 碎片是 Layer-R 的核心检索单元，与 ChromaDB 集合设计对齐 |
| D-LR-2 | EXTRACTED_FROM 扩展为可选操作 | 不是所有碎片都有关联实体；扩展增加 KuzuDB 查询开销 |
| D-LR-3 | feedback_weight 参与评分 | 参考 Cognee 反馈权重机制，使高质量碎片获得更高排名 |
| D-LR-4 | 结果包含 offset 信息 | 支持段落级溯源，对齐互索引边的 offset_start/offset_end |
