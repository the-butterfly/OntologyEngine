# QueryService 完整接口设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/04-modules.md` | **last_verified**: 2026-04-19

---

## 目的

定义 QueryService 的完整接口，将当前 pattern_match / graph_traverse / find_path 重写为支持 Layer-R 向量检索、Layer-S 图遍历、双路协同检索、查询路由和互索引协同的完整查询服务。

## 解决的问题

| # | 问题 | 当前表现 | 本文如何解决 |
|---|------|----------|-------------|
| 1 | **无 Layer-R 检索** | 仅有 pattern_match 属性过滤 | query_raw 接口：ChromaDB 向量检索 + metadata 过滤 + EXTRACTED_FROM 扩展 |
| 2 | **无 Layer-S 图遍历** | graph_traverse 仅做邻域查询 | query_structured 接口：KuzuDB Cypher 图遍历 + 时序过滤 + edge_text 评分 |
| 3 | **无双路协同** | 无 Layer-R → Layer-S 跨层导航 | query_hybrid 接口：Layer-R → Layer-S → trace_to 回溯 |
| 4 | **无查询路由** | 所有查询使用同一策略 | QueryRouter 自动识别查询类型，选择最优检索路径 |
| 5 | **无查询解释** | 无法了解查询执行计划 | explain 接口返回查询计划和预计成本 |
| 6 | **硬编码关系类型** | find_path 默认 "has_invoice" | 由 Schema 声明驱动，不再硬编码 |

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│  QueryService                                                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  query_raw(query, filters, top_k)                                    │
│       │  Layer-R 向量检索                                            │
│       ▼                                                              │
│  ┌──────────────┐                                                    │
│  │ Layer-R      │  ChromaDB 向量检索 + metadata 过滤                 │
│  │ Retriever    │  + EXTRACTED_FROM 扩展                             │
│  └──────────────┘                                                    │
│                                                                      │
│  query_structured(query, entity_id, relation_types, as_of)           │
│       │  Layer-S 图遍历                                              │
│       ▼                                                              │
│  ┌──────────────┐                                                    │
│  │ Layer-S      │  KuzuDB Cypher 图遍历                              │
│  │ Retriever    │  + 时序过滤 + edge_text 向量化评分                  │
│  └──────────────┘                                                    │
│                                                                      │
│  query_hybrid(query, query_type, filters, top_k)                     │
│       │  双路协同检索                                                │
│       ▼                                                              │
│  ┌──────────────┐                                                    │
│  │ QueryRouter   │  查询类型识别 + 参数映射                          │
│  └──────┬───────┘                                                    │
│    ┌────┴────┬──────────┐                                            │
│    ▼         ▼          ▼                                            │
│  Layer-R   Layer-S   Bundle Search                                   │
│    │         │          │                                            │
│    └────┬────┴─────┬────┘                                            │
│         ▼          ▼                                                 │
│    ┌──────────┐  ┌──────────────┐                                    │
│    │ RRF融合   │  │ 互索引协同    │                                    │
│    └──────────┘  └──────────────┘                                    │
│         │                                                            │
│         ▼                                                            │
│  QueryResult                                                        │
│                                                                      │
│  explain(query, query_type)                                          │
│       │  查询计划解释                                                │
│       ▼                                                              │
│  QueryPlan                                                          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 接口定义

### query_raw：Layer-R 向量检索

```python
async def query_raw(
    self,
    query: str,
    filters: dict[str, Any] | None = None,
    top_k: int = 10,
    expand_extracted_from: bool = True,
) -> RawQueryResult
```

**职责**：纯 Layer-R 向量检索，返回 KnowledgeFragment 及其关联的 EntityInstance。

**流程**：

```
1. query 向量化
2. ChromaDB knowledge_fragment 集合检索
3. metadata 过滤（domain_id, dataset_id, tags）
4. expand_extracted_from=True 时：沿 EXTRACTED_FROM 边扩展到关联 EntityInstance
5. 返回 RawQueryResult
```

**返回模型**：

```python
@dataclass
class FragmentResult:
    fragment_id: str
    text: str
    score: float
    dataset_id: str
    document_id: str
    offset_start: int
    offset_end: int
    metadata: dict[str, Any]

@dataclass
class RawQueryResult:
    fragments: list[FragmentResult]
    related_entities: list[EntityResult]
    total_count: int
    latency_ms: float
```

---

### query_structured：Layer-S 图遍历

```python
async def query_structured(
    self,
    entity_id: str | None = None,
    relation_types: list[str] | None = None,
    as_of: datetime | None = None,
    direction: str = "outgoing",
    depth: int = 1,
    edge_weight_preference: dict[str, float] | None = None,
) -> StructuredQueryResult
```

**职责**：纯 Layer-S 图遍历，返回 EntityInstance 和 EdgeInstance。

**流程**：

```
1. KuzuDB Cypher 图遍历
2. 时序过滤：as_of 参数 → WHERE valid_from <= as_of AND (valid_to IS NULL OR valid_to > as_of)
3. edge_text 向量化评分：边语义参与排序
4. edge_weight_preference：按查询类型调整边权重偏好
5. 返回 StructuredQueryResult
```

**边权重偏好**：

| 查询类型 | TEMPORAL | CAUSAL | BUSINESS |
|----------|----------|--------|----------|
| factual | ×1.0 | ×1.0 | ×1.0 |
| multi-hop | ×1.0 | ×2.0 | ×1.5 |
| temporal | ×3.0 | ×1.0 | ×1.0 |

**返回模型**：

```python
@dataclass
class EntityResult:
    entity_id: str
    fact_object: str
    attributes: dict[str, Any]
    valid_from: datetime | None
    valid_to: datetime | None
    feedback_weight: float

@dataclass
class EdgeResult:
    edge_id: str
    from_id: str
    to_id: str
    relation_name: str
    edge_text: str | None
    weight: float | None
    confidence: float

@dataclass
class StructuredQueryResult:
    entities: list[EntityResult]
    edges: list[EdgeResult]
    traversal_depth: int
    latency_ms: float
```

---

### query_hybrid：双路协同检索

```python
async def query_hybrid(
    self,
    query: str,
    query_type: str | None = None,
    filters: dict[str, Any] | None = None,
    top_k: int = 10,
    semantic_weight: float = 0.6,
    graph_weight: float = 0.4,
    trace_to_evidence: bool = True,
) -> HybridQueryResult
```

**职责**：Layer-R → Layer-S → trace_to 协同检索，返回融合结果和证据链。

**流程**：

```
1. QueryRouter 识别查询类型（factual / multi-hop / temporal / analytical / mixed）
2. 根据查询类型选择检索路径：
   - factual: Layer-R 向量检索 → extracted_from 扩展
   - multi-hop: Layer-S 图遍历 + Bundle Search
   - temporal: Layer-S 时序过滤 + TEMPORAL×3.0 边权重
   - analytical: → AnalysisService.execute_analysis
   - mixed: Layer-R → Layer-S → trace_to 回溯
3. RRF 融合多路结果
4. 互索引协同：沿 EXTRACTED_FROM / SUPPORTED_BY / DEFINED_IN / TRACE_TO 边跨层导航
5. trace_to_evidence=True 时：推理步骤 → 来源碎片（提供证据链）
6. 返回 HybridQueryResult
```

**查询路由规则**：

| 查询类型 | 特征词 | 检索路径 | 边权重偏好 |
|----------|--------|---------|-----------|
| factual | 谁/什么/哪个 | Layer-R → extracted_from | 无 |
| multi-hop | 为什么/如何/关系 | Layer-S + Bundle Search | CAUSAL×2.0 |
| temporal | 什么时候/持续多久/历史 | Layer-S 时序过滤 | TEMPORAL×3.0 |
| analytical | 计算/分析/占比/趋势 | → AnalysisService | 无 |
| mixed | 复合查询 | Layer-R → Layer-S → trace_to | 自适应 |

**返回模型**：

```python
@dataclass
class EvidenceLink:
    step_description: str
    fragment_ids: list[str]
    fragment_texts: list[str]
    confidence: float

@dataclass
class HybridQueryResult:
    fragments: list[FragmentResult]
    entities: list[EntityResult]
    edges: list[EdgeResult]
    evidence_chain: list[EvidenceLink]
    query_type: str
    retrieval_path: str
    total_count: int
    latency_ms: float
    contradiction_warnings: list[dict] | None = None
```

---

### explain：查询计划解释

```python
async def explain(
    self,
    query: str,
    query_type: str | None = None,
) -> QueryPlan
```

**职责**：返回查询执行计划，供调试和优化。

**返回模型**：

```python
@dataclass
class QueryPlan:
    query_type: str
    retrieval_path: str
    estimated_latency_ms: float
    collections_to_search: list[str]
    edge_weight_preference: dict[str, float]
    fusion_strategy: str
    steps: list[QueryPlanStep]

@dataclass
class QueryPlanStep:
    step_name: str
    backend: str
    estimated_results: int
    cost_estimate: float
```

---

## 与 m_flow Retrieval Orchestrator 对齐

| m_flow 概念 | OntologyEngine 对应 | 说明 |
|------------|-------------------|------|
| MemoryOrchestrator（并行三路） | QueryRouter + 并行双路 | m_flow 并行检索 Episode / Entity / Facet |
| VectorProvider 多集合 | ChromaDB 7 集合 | entity_name, entity_summary, facet_search_text, edge_text, knowledge_fragment, rule_definition |
| MemoryGraph 投影 | KuzuDB Cypher 图遍历 | Layer-S 图遍历 + 邻居扩展 |
| Bundle Search 成本传播 | Bundle Search 四阶段算法 | 宽网撒播→投影到图→代价传播→排序组装 |
| AdaptiveScoringContext | 查询路由 + 边权重偏好 | MAMGA 自适应参数 |
| ContentFragment 检索 | KnowledgeFragment 检索 | Layer-R 原文检索 |

---

## 与 Cognee BaseRetriever 对齐

| Cognee 概念 | OntologyEngine 对应 | 说明 |
|-------------|-------------------|------|
| BaseRetriever 三步管道 | query_hybrid 三步流程 | get_retrieved_objects → get_context → get_completion |
| register_retriever 策略模式 | RetrieverRegistry | 按查询类型注册检索器 |
| used_graph_elements | evidence_chain | 检索使用的图元素追踪 |
| feedback_weight | feedback_weight 参与评分 | final = λ × semantic + (1-λ) × feedback_weight |

---

## 矛盾警告

QueryService 在返回结果时忠实展示，不主动过滤矛盾。可选返回 `contradiction_warnings`：

```python
contradiction_warnings: [
    {
        "type": "value_conflict",
        "entity_id": "ent_001",
        "field": "address",
        "sources": {
            "ds_crm": "北京市朝阳区建国路88号",
            "ds_erp": "北京市海淀区中关村大街1号"
        }
    }
]
```

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-QS-1 | 三层接口而非单一接口 | 不同场景需要不同检索策略：纯向量、纯图、协同 |
| D-QS-2 | 查询路由基于特征词而非 LLM | 本地优先原则，避免每次查询调用 LLM |
| D-QS-3 | explain 接口独立于查询执行 | 调试和优化需要查看计划而不实际执行 |
| D-QS-4 | contradiction_warnings 可选返回 | 不强制过滤矛盾，但提供信息供调用方决策 |
| D-QS-5 | 删除 find_path 硬编码关系类型 | 由 Schema 声明驱动，Bundle Search 自动选择路径 |

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| 查询引擎设计 | `docs/02-design/query-engine/README.md` |
| 查询路由设计 | `docs/02-design/query-engine/query-routing.md` |
| Bundle Search 设计 | `docs/02-design/query-engine/bundle-search.md` |
| 互索引协同检索 | `docs/02-design/query-engine/mutual-index-retrieval.md` |
| 查询路由概念 | `docs/01-overview/05-concepts.md` |
