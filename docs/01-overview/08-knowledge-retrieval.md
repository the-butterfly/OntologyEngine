# 知识检索机制

> **status**: accepted | **phase**: mvp+phase1 | **source_of_truth**: 本文档 | **last_verified**: 2026-04-19

## 检索架构：Layer-R 与 Layer-S 双路检索

OntologyEngine 的 QueryEngine 支持两条独立的检索路径，以及一条协同路径：

```
┌─────────────────────────────────────────────────────────────┐
│                    QueryEngine                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  query_raw(query, filters)     → Layer-R 检索           │
│  └── ChromaVectorStore → fragment 向量检索（<100K）        │
│      → 返回 FragmentResult                                  │
│                                                             │
│  query_structured(query)      → Layer-S 检索            │
│  └── SQLite + Kuzu → entity/relation 查询                 │
│      → 返回 StructuredResult                                │
│                                                             │
│  query_hybrid(query)          → 协同模式 [Phase 2]      │
│  └── Layer-R 检索 → extracted_from 扩展到 entity          │
│      → Layer-S 执行推理 → trace_to 回溯碎片               │
│      → 返回结果 + 证据链                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer-R 检索

### 适用场景

- 探索性查询（不知道精确答案在哪里）
- 需要原文证据的查询
- 历史文档问答（无结构化索引的 PDF/HTML）

### 检索流程

```
query_raw("制造业 担保 风险 客户")
     ↓
ChromaDB 向量检索：top_k=10
     ↓
metadata 过滤：dataset_id、date、type
     ↓
extracted_from 扩展（可选）：
  frag → 对应 EntityInstance
     ↓
返回：FragmentResult列表
```

---

## Layer-S 检索

### 适用场景

- 确定性计算（已知 Schema）
- 规则执行和推理
- 合规审计（需要完整追溯链）

### 检索流程

```
query_structured("企业A 担保敞口")
     ↓
Schema 路由：根据 entity type 定位 Schema
     ↓
时序过滤：WHERE valid_to IS NULL（当前版本）
     ↓
图遍历（Kuzu）：
  traverse(entity_id="ent_A", relation_type="guarantees", depth=3)
     ↓
edge_text 向量化参与评分（Bundle Search 机制）
     ↓
返回：StructuredResult（含 EntityInstance + EdgeInstance）
```

---

## 查询路由（Query Routing）

参考 MAMGA，QueryEngine 根据查询类型选择最优检索参数：

| 查询类型 | 特征词 | 检索策略 | 边权重偏好 |
|----------|--------|---------|-----------|
| **factual** | 谁/什么/哪个 | Layer-R 向量检索 + extracted_from 扩展 | 无 |
| **multi-hop** | 为什么/如何/...和...的关系 | Layer-S 图遍历 + ENTITY 边优先 | TEMPORAL×1.0, CAUSAL×2.0 |
| **temporal** | 什么时候/持续多久 | valid_from/to 过滤 + 时序边 | TEMPORAL×3.0 |
| **analytical** | 计算/分析/占比 | → L4 RuleEngine 执行 | 无 |
| **mixed** | 复合查询 | Layer-R → Layer-S → trace_to 回溯 | 自适应 |

---

## Bundle Search 成本传播（边语义参与检索）

参考 m_flow，Layer-S 图遍历时边语义参与评分：

```
路径成本 = 起始节点向量距离
         + Σ(边向量距离 + 跳数惩罚)
         + miss_penalty（边未被向量检索命中的惩罚）

Episode 最终得分 = min(所有路径成本)
```

**核心思想**：一条强证据链即可证明相关性（Minimum not Average）。

**直接命中惩罚**：直接命中 Episode Summary 的路径需要额外惩罚，优先使用 FacetPoint 级别的精确证据。

### 技术实现框架

```
Bundle Search 四阶段算法（参考 m_flow bundle_search.py + bundle_scorer.py）：

Phase 1 — 宽网撒播：
  查询嵌入同时搜索多个向量集合：
  [Episode_summary, Facet_search_text, Facet_anchor_text,
   FacetPoint_search_text, Entity_name, Edge_relationship_name]
  每个集合返回最多 100 个候选（wide_search_top_k=100）
  时间查询时候选池翻倍

Phase 2 — 投影到图：
  命中节点作为入口，提取周围子图，再扩展一跳邻居
  两阶段投影：命中 ID 投影 → 邻居扩展并按类型优先级排序

Phase 3 — 代价传播：
  从尖端向基底传播代价，对每个 Episode 评估所有可能路径
  路径代价 = 起始代价(锚点向量距离) + Σ(边代价 + 跳惩罚 0.05) + 未命中惩罚(0.9)
  Episode 最终得分 = min(所有路径成本) ← 一条强证据链即可证明相关性

Phase 4 — 排序组装：
  按 bundle cost 排序取 top-k，根据 display_mode 组装输出

五种路径类型及 OntologyEngine 映射：
  direct_episode  → 直接命中 EntityInstance（惩罚 0.3）
  facet           → Categorization → EntityInstance
  point           → AnalyticalElement → Categorization → EntityInstance
  entity          → EntityInstance 直接命中
  facet_entity    → EntityInstance → Categorization → EntityInstance

Facet 近似匹配折扣：
  当 Facet 向量距离 < 0.1 时，边代价和跳代价大幅折扣（分别降至 0.1 和 0.05）

KAG DPR+PPR+RRF 五步混合检索（参考 KAG 检索文档）：
  1. DPR 初始检索：向量相似性匹配 Top-k Chunk
  2. 种子节点聚焦：Top-k KnowledgeUnit + Top-k AtomicQuery + Top-k Entity
  3. PPR 概率传播：个性化 PageRank 算法，通过路径概率传播识别 Top-k Chunk
  4. RRF 重排序：DPR 和 PPR 的 Top-k Chunk 通过互惠排名融合全局重排序
  5. 事实收集：Top-k Chunk + 逻辑形式匹配的 Top-k SPO → 生成答案

QMD BM25+向量混合检索（参考 QMD store.ts）：
  BM25 搜索：SQLite FTS5 全文索引，BM25 分数转换 |x|/(1+|x|) 映射到 [0,1)
  向量搜索：sqlite-vec 向量索引，余弦相似度
  RRF 融合：RRF_score(d) = Σ 1/(k+rank_i)，k=60
  重排序：本地 GGUF reranker 模型（qwen3-reranker-0.6b）
  查询扩展：本地 GGUF 微调模型（qmd-query-expansion-1.7B）
```

---

## RRF 融合（Reciprocal Rank Fusion）

Layer-R 向量检索 + Layer-S 图遍历的多路结果通过 RRF 融合：

```
RRF_score(d) = Σ 1 / (k + rank_i)

k = 60（经验最优值）
```

融合后统一排序，返回 top-k 结果。

### 技术实现框架

```
RRF 融合实现（参考 KAG + MAMGA + QMD）：

KAG 五步混合检索中的 RRF：
  - DPR 检索 Top-k Chunk + PPR 检索 Top-k Chunk
  - 两路结果通过 RRF 融合，k=60
  - 逻辑形式还被翻译为"模拟命题"查询知识单元节点，实现多路召回互补

MAMGA 多阶段检索中的 RRF：
  - 向量搜索 → 关键词搜索 → 全扫描 → RRF 融合 → 自适应图遍历 → 重排序
  - 自适应参数：根据查询类型调整 max_depth、similarity_threshold、scoring_weights

QMD 混合检索中的 RRF：
  - BM25（FTS5）+ 向量搜索（sqlite-vec）+ HyDE 查询扩展
  - 三路结果通过 RRF 融合
  - 本地 GGUF reranker 重排序

OntologyEngine RRF 实现策略：
  - Layer-R 向量检索 + Layer-S 图遍历 + BM25 关键词检索（三路融合）
  - RRF k=60，与 KAG/MAMGA/QMD 一致
  - 查询路由决定各路权重：factual 偏向 Layer-R，multi-hop 偏向 Layer-S
  - 可选：本地 reranker 重排序（参考 QMD）
```

---

## 互索引驱动的协同检索

Layer-R 和 Layer-S 通过互索引边实现双向导航：

```
Layer-R 检索结果
     ↓ extracted_from
Layer-S EntityInstance
     ↓
Layer-S 推理执行
     ↓ trace_to
Layer-R 碎片证据
     ↓
输出：结果 + 完整证据链
```

### 示例：客户风险分析

```
查询：explain_risk(customer_id="A")

Layer-R：
  query_raw("企业A 财务 风险")
  → frag_001: "2024年报：营收3.2亿，资产负债率65%..."
  → frag_002: "征信报告：逾期2次，最高90天..."

Layer-S（extracted_from 扩展）：
  frag_001 → ent_A_financial
  frag_002 → ent_A_credit

Layer-S 推理：
  MetricEngine 计算：debt_ratio=0.65, credit_score=0.55
  RuleEngine 执行：IF compliance_score < 40 → risk_level = "D"

Layer-R 回溯（trace_to）：
  risk_level="D" → frag_001, frag_002（来源证据）

最终输出：
  risk_level: D
  evidence: [frag_001, frag_002]
  execution_snapshot: {...}
```

---

## 与业界系统的对齐

| 系统 | 检索机制 | OntologyEngine 对齐 |
|------|---------|---------------------|
| MemPalace | ChromaDB 向量 + wing/room 元数据过滤 | Layer-R ChromaDB + Dataset 过滤 |
| MAMGA | 多阶段检索 + RRF + 自适应图遍历 | QueryEngine RRF + 查询路由 |
| m_flow | Bundle Search 成本传播 | Layer-S edge_text 向量参与评分 |
| KAG | DPR + PPR + RRF 五步混合检索 | Layer-R/S 双路 + RRF 融合 |
| LLM-Wiki | Wikilink 遍历 + 关键词匹配 | Layer-S extracted_from 扩展 |

---

## 非目标

- 不实现通用 NLP 解析（专注结构化知识推理）
- 不实现通用文档检索（RAG 广度层由外部系统提供）
- 不实现全文本搜索（Layer-R 检索是语义向量检索，非关键词倒排）
