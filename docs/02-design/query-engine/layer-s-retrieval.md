# Layer-S 图遍历检索

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/08-knowledge-retrieval.md` + `docs/02-design/storage/kuzudb-schema.md` | **last_verified**: 2026-04-19

## 目的

定义 Layer-S 图遍历检索的完整流程，包括 KuzuDB Cypher 查询、不同查询类型的遍历策略、edge_text 向量化评分、时序过滤和 StructuredResult 结果格式。Layer-S 是结构化知识层的检索入口，服务于确定性计算、规则执行和合规审计场景。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 当前无图遍历检索实现 | 无法执行多跳推理和关系查询 |
| 2 | 不同查询类型使用相同遍历策略 | multi-hop 无法利用因果边，temporal 无法利用时序边 |
| 3 | 边语义未参与评分 | 图遍历退化为简单邻域查询，无法区分强证据链和弱关联 |
| 4 | 时序过滤缺失 | 无法查询特定时间点的实体状态 |
| 5 | 结果格式未定义 | 上层无法统一消费图遍历结果 |

---

## 适用场景

| 场景 | 说明 |
|------|------|
| 确定性计算 | 已知 Schema，需要精确查询实体和关系 |
| 规则执行和推理 | 需要遍历关系链执行推理 |
| 合规审计 | 需要完整追溯链 |
| multi-hop 查询类型 | "为什么/如何/关系"类多跳查询 |
| temporal 查询类型 | "什么时候/历史变化"类时序查询 |

---

## 检索流程

```
query_structured(query, params)
     │
     ▼
┌─────────────────────────────┐
│ 1. Schema 路由               │
│    根据 entity type 定位     │
│    FactObjectDefinition      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 2. 时序过滤（temporal 类型） │
│    WHERE valid_to IS NULL    │
│    或 WHERE as_of 过滤       │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 3. KuzuDB 图遍历            │
│    Cypher 查询 + 深度控制    │
│    边权重偏好应用            │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 4. edge_text 向量化评分      │
│    边语义参与排序            │
│    confidence 阈值过滤       │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ 5. 组装 StructuredResult     │
│    实体 + 边 + 路径 + 元数据 │
└─────────────────────────────┘
```

---

## Cypher 查询模式

### 目的

定义不同查询类型的 Cypher 查询模板，严格对齐 `kuzudb-schema.md` 中的节点表和边表设计。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 查询模板未定义 | 按查询类型定义 Cypher 模板 |
| 2 | 遍历深度无控制 | 参数化 max_depth |
| 3 | 边类型无过滤 | WHERE 子句约束 relation_name |

### 实体邻域查询（factual）

```cypher
MATCH (e:EntityNode {id: $entity_id})-[r]-(n)
WHERE r.confidence >= $min_confidence
RETURN e, r, n
LIMIT $limit
```

### 多跳关系查询（multi-hop）

```cypher
MATCH path = (e:EntityNode {id: $entity_id})-[r*1..$max_depth]-(n)
WHERE ALL(rel IN relationships(path) WHERE rel.confidence >= $min_confidence)
  AND ALL(rel IN relationships(path) WHERE rel.relation_name IN $allowed_relations)
RETURN path, 
       [rel IN relationships(path) | rel.relation_name] AS relation_names,
       [rel IN relationships(path) | rel.weight] AS weights
ORDER BY reduce(s = 0, rel IN relationships(path) | s + rel.weight) DESC
LIMIT $limit
```

### 时序切片查询（temporal）

```cypher
MATCH (e:EntityNode {_fact_object: $fact_object})
WHERE e.valid_from <= $as_of 
  AND (e.valid_to IS NULL OR e.valid_to > $as_of)
  AND e.domain_id = $domain_id
RETURN e
ORDER BY e.valid_from DESC
```

### 时序链查询

```cypher
MATCH (e:EntityNode {id: $entity_id})
WHERE e.valid_from IS NOT NULL
RETURN e.valid_from, e.valid_to, e.attributes
ORDER BY e.valid_from ASC
```

### 分类标注查询

```cypher
MATCH (e:EntityNode {id: $entity_id})-[r:CATEGORIZED_AS]->(ct:CategoryTagNode)
RETURN ct.dimension_name, ct.value_code, ct.confidence
```

### 指标值查询

```cypher
MATCH (e:EntityNode {id: $entity_id})-[r:HAS_METRIC]->(mv:MetricValueNode)
WHERE mv.valid_from <= $as_of
  AND (mv.valid_to IS NULL OR mv.valid_to > $as_of)
RETURN mv.metric_name, mv.value, mv.computed_at, mv.computation_snapshot
```

---

## 边权重偏好

### 目的

定义查询路由如何影响图遍历中的边权重计算，使不同查询类型优先遍历不同语义类型的边。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 所有边权重相同 | 查询类型驱动的边权重偏好 |
| 2 | 无法优先遍历特定语义边 | TEMPORAL/CAUSAL/ENTITY 边类型差异化权重 |

### 边类型分类

| 边类型 | relation_name 示例 | 语义特征 | 默认权重 |
|--------|-------------------|----------|---------|
| TEMPORAL | PRECEDES, SUCCEEDS, TEMPORALLY_CLOSE | 时序关系 | 1.0 |
| CAUSAL | LEADS_TO, BECAUSE_OF, ENABLES, PREVENTS | 因果关系 | 1.0 |
| ENTITY | guarantees, supplies, employs, invests_in | 业务关系 | 1.0 |
| CLASSIFICATION | CATEGORIZED_AS | 分类关系 | 0.5 |
| METRIC | HAS_METRIC | 指标关联 | 0.5 |

### 权重调整规则

```
effective_weight = base_weight × query_type_multiplier

query_type_multiplier:
  factual:    TEMPORAL=1.0, CAUSAL=1.0, ENTITY=1.0
  multi-hop:  TEMPORAL=1.0, CAUSAL=2.0, ENTITY=1.5
  temporal:   TEMPORAL=3.0, CAUSAL=1.0, ENTITY=1.0
  mixed:      TEMPORAL=2.0, CAUSAL=1.5, ENTITY=1.2

路径排序：
  path_score = Σ(edge.effective_weight × edge.weight)
  ORDER BY path_score DESC
```

---

## edge_text 向量化评分

### 目的

定义边语义文本如何参与 Layer-S 检索评分，对齐 m_flow 的 edge_text 向量化模式。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 边只是类型标签，无法参与语义匹配 | edge_text 向量化后与查询嵌入计算距离 |
| 2 | 边权重仅反映业务重要性 | edge_text 向量距离反映语义相关性 |

### 评分流程

```
1. 遍历路径中的每条边，提取 edge_text
2. edge_text 非空 → 计算 edge_text 与查询的向量距离
3. edge_text 为空 → 使用 miss_penalty（默认 0.9）
4. 边评分 = edge_text_vector_distance（或 miss_penalty）
5. 路径评分 = Σ(边评分 × 边权重偏好 × 边业务权重)
```

### ChromaDB 边向量检索

```python
async def score_edge_text(
    query_embedding: list[float],
    edge_texts: list[str],
) -> list[float]:
    collection = client.get_collection("edge_text", embedding_function=embedding_fn)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=len(edge_texts),
        where={"edge_type": "business"},
        include=["distances"],
    )
    return results["distances"][0]
```

---

## 时序过滤

### 目的

定义 temporal 查询类型的时序过滤机制，对齐 `kuzudb-schema.md` 中 EntityNode 的 valid_from/valid_to 字段。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 无法查询特定时间点的实体状态 | as_of 参数 + valid_from/valid_to 过滤 |
| 2 | 无法获取实体历史版本 | include_history 参数 |
| 3 | 时序查询无法利用时序边 | TEMPORAL 边权重偏好 ×3.0 |

### 查询语义

| 查询 | Cypher 条件 | 说明 |
|------|------------|------|
| 当前版本 | `WHERE e.valid_to IS NULL` | 默认行为 |
| 指定时点 | `WHERE e.valid_from <= $as_of AND (e.valid_to IS NULL OR e.valid_to > $as_of)` | as_of 参数 |
| 全部历史 | 无 valid_from/valid_to 过滤 | include_history=true |
| 时间范围 | `WHERE e.valid_from >= $start AND e.valid_to <= $end` | 时间窗口查询 |

### 时间增强（参考 m_flow）

```
查询时间解析：
  提取查询中的时间表达 → time_start_ms, time_end_ms, confidence
  confidence >= time_conf_min（0.4）→ 启用时间增强

时间匹配奖励：
  实体 mentioned_time 与查询时间重叠 → 降低路径成本（bonus 最多 0.06）

时间不匹配惩罚：
  查询包含时间但实体时间不匹配 → 增加路径成本（penalty 最多 0.03）

候选池扩展：
  时间查询时 wide_search_top_k × 2（上限 300）
```

---

## StructuredResult 结果格式

### 目的

定义 Layer-S 检索的标准化输出格式，供 RRF 融合和上层 API 消费。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 图遍历结果格式不统一 | StructuredResult 标准化输出 |
| 2 | 路径信息缺失 | 包含完整路径和边语义 |

### 数据结构

```python
@dataclass
class StructuredResult:
    entities: List[EntityResult]
    edges: List[EdgeResult]
    paths: List[PathResult]
    metadata: QueryMetadata

@dataclass
class EntityResult:
    entity_id: str
    name: str
    fact_object: str
    attributes: Dict[str, str]
    valid_from: str | None
    valid_to: str | None
    domain_id: str
    confidence: float
    feedback_weight: float

@dataclass
class EdgeResult:
    edge_id: str
    from_id: str
    to_id: str
    relation_name: str
    edge_text: str
    weight: float
    confidence: float
    valid_from: str | None
    valid_to: str | None

@dataclass
class PathResult:
    nodes: List[str]
    edges: List[str]
    path_score: float
    path_type: str
```

### 结果示例

```json
{
    "entities": [
        {
            "entity_id": "ent_A",
            "name": "企业A",
            "fact_object": "finance:Counterparty",
            "attributes": {"risk_grade": "D", "registered_capital": "50000000"},
            "valid_from": "2025-06-01",
            "valid_to": null,
            "domain_id": "risk_control",
            "confidence": 1.0,
            "feedback_weight": 0.5
        }
    ],
    "edges": [
        {
            "edge_id": "edge_001",
            "from_id": "ent_A",
            "to_id": "ent_B",
            "relation_name": "guarantees",
            "edge_text": "企业A为企业B提供500万元担保",
            "weight": 0.8,
            "confidence": 0.95,
            "valid_from": "2024-01-01",
            "valid_to": null
        }
    ],
    "paths": [
        {
            "nodes": ["ent_A", "ent_B", "ent_C"],
            "edges": ["edge_001", "edge_002"],
            "path_score": 2.4,
            "path_type": "multi_hop"
        }
    ],
    "metadata": {
        "query_type": "multi_hop",
        "max_depth": 3,
        "total_entities": 3,
        "total_edges": 2,
        "execution_time_ms": 45
    }
}
```

---

## 与参考项目的对齐

| 维度 | m_flow | KAG | Cognee | OntologyEngine |
|------|--------|-----|--------|----------------|
| 图存储 | KuzuDB MemoryGraph | OpenSPG | KuzuDB DataPoint | KuzuDB 5 节点表 |
| 遍历方式 | MemoryGraph 投影 | PPR 概率传播 | GraphEngine | Cypher 参数化查询 |
| 边语义 | edge_text 向量化 | 无 | 无 | edge_text 向量化 + 权重偏好 |
| 时序支持 | mentioned_time + created_at | 无 | 无 | valid_from/valid_to + 时间增强 |
| 自适应评分 | AdaptiveScoringContext | 无 | feedback_weight | 查询路由 + 边权重偏好 |
| 结果格式 | Edge 列表 | SubGraph | DataPoint 列表 | StructuredResult |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-LS-1 | Cypher 查询模板参数化 | 避免拼接 SQL，防止注入；支持查询路由动态调整参数 |
| D-LS-2 | 边权重偏好由查询路由驱动 | 不同查询类型需要不同的遍历策略，MAMGA 验证了自适应参数的有效性 |
| D-LS-3 | edge_text 向量化参与评分 | 对齐 m_flow 的边语义评分模式，使边成为检索的一等公民 |
| D-LS-4 | 时序过滤默认返回当前版本 | 大多数查询关心当前状态，历史版本需显式请求 |
