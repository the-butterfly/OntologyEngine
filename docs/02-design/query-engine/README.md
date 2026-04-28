# 查询引擎设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/08-knowledge-retrieval.md` | **last_verified**: 2026-04-19 | **[待核对代码]**

## 目的

定义 OntologyEngine 查询引擎的完整架构，将当前占位符实现重写为支持 Layer-R/Layer-S 双路检索、查询路由、Bundle Search、RRF 融合和互索引协同检索的完整查询系统。查询引擎是知识检索层的核心入口，连接上层 API 与底层存储。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 当前 `engine/query/__init__.py` 仅为占位符 | 无法执行任何检索操作 |
| 2 | Layer-R 与 Layer-S 检索路径未实现 | 双层协同架构停留在概念层面 |
| 3 | 查询路由缺失 | 所有查询使用同一检索策略，无法针对 factual/multi-hop/temporal 等类型优化 |
| 4 | Bundle Search 未实现 | 边语义无法参与检索评分，图遍历退化为简单邻域查询 |
| 5 | RRF 融合缺失 | 多路检索结果无法统一排序 |
| 6 | 互索引协同检索未实现 | Layer-R 与 Layer-S 之间无法双向导航 |

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                         QueryEngine                                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  query(query, query_type, filters)                                   │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────┐                                                     │
│  │ QueryRouter  │  查询类型识别 + 参数映射                            │
│  └──────┬──────┘                                                     │
│         │                                                            │
│    ┌────┴────┬──────────┬────────────┐                               │
│    ▼         ▼          ▼            ▼                               │
│  Layer-R   Layer-S   Bundle      Analytical                         │
│  Retriever  Retriever  Search     → RuleEngine                      │
│    │         │          │                                            │
│    └────┬────┴─────┬────┘                                            │
│         ▼          ▼                                                 │
│    ┌──────────┐  ┌──────────────┐                                    │
│    │ RRFFusion │  │ MutualIndex  │                                    │
│    │          │  │ Collaborative│                                    │
│    └────┬─────┘  └──────┬───────┘                                    │
│         │               │                                            │
│         └───────┬───────┘                                            │
│                 ▼                                                    │
│         QueryResult                                                  │
│         ├── fragments: List[FragmentResult]                          │
│         ├── entities: List[EntityResult]                             │
│         ├── edges: List[EdgeResult]                                  │
│         ├── evidence_chain: List[EvidenceLink]                       │
│         └── metadata: QueryMetadata                                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 模块组成

| # | 模块 | 文档 | 职责 |
|---|------|------|------|
| 1 | QueryRouter | [query-routing.md](query-routing.md) | 查询类型识别、参数映射、降级策略 |
| 2 | Layer-R Retriever | [layer-r-retrieval.md](layer-r-retrieval.md) | ChromaDB 向量检索 + metadata 过滤 + EXTRACTED_FROM 扩展 |
| 3 | Layer-S Retriever | [layer-s-retrieval.md](layer-s-retrieval.md) | KuzuDB 图遍历 + 时序过滤 + edge_text 向量化评分 |
| 4 | Bundle Search | [bundle-search.md](bundle-search.md) | 四阶段算法：宽网撒播→投影到图→代价传播→排序组装 |
| 5 | RRF Fusion | [rrf-fusion.md](rrf-fusion.md) | 三路融合：Layer-R + Layer-S + BM25 |
| 6 | Mutual Index Collaborative | [mutual-index-retrieval.md](mutual-index-retrieval.md) | 互索引边驱动的跨层协同检索 |

---

## 关键设计决策

| # | 决策 | 理由 | 参考 |
|---|------|------|------|
| D-QE-1 | 查询路由基于特征词而非 LLM 分类 | 本地优先原则，避免每次查询调用 LLM；特征词匹配 O(1)，LLM 分类 O(tokens) | MAMGA 自适应参数 |
| D-QE-2 | Bundle Search 采用 m_flow 四阶段算法 | 经过生产验证的路径成本传播算法，"Minimum not Average" 原则确保一条强证据链即可证明相关性 | m_flow bundle_search.py |
| D-QE-3 | RRF k=60，与 KAG/MAMGA/QMD 一致 | 业界经验最优值，避免重新调参 | KAG DPR+PPR+RRF |
| D-QE-4 | 互索引边作为跨层跳转边纳入 Bundle Search | 边语义向量化后参与成本传播，使跨层跳转有成本模型 | m_flow edge_text + KAG IndexManager |
| D-QE-5 | Retriever 注册机制（策略模式） | 参考 KAG IndexManager + Cognee register_retriever，支持动态扩展检索策略 | KAG IndexManager |
| D-QE-6 | BM25 基于 SQLite FTS5 | 本地优先原则，SQLite FTS5 无需额外依赖 | QMD store.ts |

---

## 与存储设计的对齐

### ChromaDB 集合使用

| 查询模块 | 使用的 ChromaDB 集合 | 用途 |
|----------|---------------------|------|
| Layer-R Retriever | `knowledge_fragment` | 碎片向量检索 |
| Bundle Search Phase 1 | `entity_name`, `entity_summary`, `facet_search_text`, `edge_text`, `knowledge_fragment`, `rule_definition` | 宽网撒播 |
| Bundle Search Phase 3 | `edge_text`（edge_type 区分） | 边语义向量距离计算 |
| Mutual Index | `edge_text`（edge_type=EXTRACTED_FROM/SUPPORTED_BY/DEFINED_IN/TRACE_TO） | 互索引边向量检索 |

### KuzuDB 表使用

| 查询模块 | 使用的 KuzuDB 表 | 用途 |
|----------|-----------------|------|
| Layer-S Retriever | `EntityNode`, `RELATES_TO` | 实体邻域查询 + 图遍历 |
| Layer-S Temporal | `EntityNode`（valid_from/valid_to） | 时序切片查询 |
| Bundle Search Phase 2 | `EntityNode`, `CategoryTagNode`, `MetricValueNode`, `RELATES_TO`, `CATEGORIZED_AS`, `HAS_METRIC` | 投影到图 + 邻居扩展 |
| Mutual Index | `EXTRACTED_FROM`, `SUPPORTED_BY`, `DEFINED_IN`, `TRACE_TO` | 跨层导航 |

---

## 与参考项目的对齐

| 维度 | m_flow | KAG | Cognee | OntologyEngine |
|------|--------|-----|--------|----------------|
| 检索编排 | MemoryOrchestrator（并行三路） | KAG-solver pipeline | register_retriever | QueryRouter + 并行双路 |
| 向量检索 | VectorProvider 多集合 | DPR 初始检索 | VectorEngine | ChromaDB 7 集合 |
| 图遍历 | MemoryGraph 投影 | PPR 概率传播 | GraphEngine | KuzuDB Cypher |
| 融合排序 | 无显式 RRF | RRF k=60 | 无 | RRF 三路融合 |
| 边语义评分 | Bundle Search 成本传播 | 无 | 无 | Bundle Search + 互索引边 |
| 自适应评分 | AdaptiveScoringContext | 无 | feedback_weight | 查询路由 + 边权重偏好 |
| 注册机制 | 无 | IndexManager + RetrieverABC | register_retriever | RetrieverRegistry（策略模式） |

---

## 子文档索引

| 文档 | 状态 | 说明 |
|------|------|------|
| [query-routing.md](query-routing.md) | draft | 查询路由设计 |
| [layer-r-retrieval.md](layer-r-retrieval.md) | draft | Layer-R 向量检索 |
| [layer-s-retrieval.md](layer-s-retrieval.md) | draft | Layer-S 图遍历检索 |
| [bundle-search.md](bundle-search.md) | draft | Bundle Search 四阶段算法 |
| [rrf-fusion.md](rrf-fusion.md) | draft | RRF 融合排序 |
| [mutual-index-retrieval.md](mutual-index-retrieval.md) | draft | 互索引协同检索 |
