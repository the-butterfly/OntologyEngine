# 知识检索机制

> **status**: accepted | **phase**: mvp+phase1 | **source_of_truth**: 本文档 | **last_verified**: 2026-04-18

## 检索架构：Layer-R 与 Layer-S 双路检索

OntologyEngine 的 QueryEngine 支持两条独立的检索路径，以及一条协同路径：

```
┌─────────────────────────────────────────────────────────────┐
│                    QueryEngine                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  query_raw(query, filters)     → Layer-R 检索           │
│  └── FaissVectorStore → fragment 向量检索                 │
│      → 返回 FragmentResult                                  │
│                                                             │
│  query_structured(query)      → Layer-S 检索            │
│  └── DuckDB + Kuzu → entity/relation 查询                │
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
Faiss 向量检索：top_k=10
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

---

## RRF 融合（Reciprocal Rank Fusion）

Layer-R 向量检索 + Layer-S 图遍历的多路结果通过 RRF 融合：

```
RRF_score(d) = Σ 1 / (k + rank_i)

k = 60（经验最优值）
```

融合后统一排序，返回 top-k 结果。

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
| MemPalace | ChromaDB 向量 + wing/room 元数据过滤 | Layer-R Faiss + Dataset 过滤 |
| MAMGA | 多阶段检索 + RRF + 自适应图遍历 | QueryEngine RRF + 查询路由 |
| m_flow | Bundle Search 成本传播 | Layer-S edge_text 向量参与评分 |
| KAG | DPR + PPR + RRF 五步混合检索 | Layer-R/S 双路 + RRF 融合 |
| LLM-Wiki | Wikilink 遍历 + 关键词匹配 | Layer-S extracted_from 扩展 |

---

## 非目标

- 不实现通用 NLP 解析（专注结构化知识推理）
- 不实现通用文档检索（RAG 广度层由外部系统提供）
- 不实现全文本搜索（Layer-R 检索是语义向量检索，非关键词倒排）
