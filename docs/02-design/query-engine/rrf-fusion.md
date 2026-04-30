# RRF 融合排序

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/08-knowledge-retrieval.md` | **last_verified**: 2026-04-30

## 目的

定义 OntologyEngine 的 RRF（Reciprocal Rank Fusion）融合排序机制，将 Layer-R 向量检索、Layer-S 图遍历、BM25 关键词检索和 Temporal 时序检索四路结果统一融合排序，再叠加认知层权重和 Disposition 动态权重。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 多路检索结果无法统一排序 | Layer-R 和 Layer-S 结果各自独立，无法交叉比较 |
| 2 | 单路检索召回不足 | 向量检索可能遗漏关键词精确匹配，关键词检索可能遗漏语义相关结果 |
| 3 | 不同检索路径的分数不可直接比较 | 向量距离、图遍历成本、BM25 分数、时序邻近性量纲不同 |
| 4 | 查询类型无法影响融合权重 | factual 查询应偏向 Layer-R，temporal 应偏向 Temporal 路径 |
| 5 | 时序查询依赖 BM25 CONTAINS 匹配 | 无法利用 valid_from/valid_to/occurred_at 的结构化时序字段 |
| 6 | BM25 仅覆盖 Layer-R 碎片 | CognitiveNode 的关键词精确匹配能力缺失 |
| 7 | 认知层权重未与 RRF 集成 | memory_type 权重与 RRF 分数分离，无法统一排序 |

---

## RRF 公式

### 核心公式

```
RRF_score(d) = Σ_i  1 / (k + rank_i)

k = 60（经验最优值，与 KAG/MAMGA/QMD/Hindsight 一致）
```

### 公式特性

| 特性 | 说明 |
|------|------|
| 分数量纲统一 | 所有路的分数归一化为排名的倒数，消除量纲差异 |
| 对异常值鲁棒 | 单路极端高分不会主导最终结果 |
| 排名敏感 | 排名越靠前贡献越大，但不会无限放大 |
| k 值平滑 | k=60 使排名差异适度衰减，避免 Top-1 过度主导 |

---

## 四路融合架构

### 融合流程

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Layer-R     │  │  Layer-S     │  │  BM25        │  │  Temporal    │
│  向量检索     │  │  图遍历       │  │  关键词检索   │  │  时序检索     │
│  top_k=10    │  │  top_k=10    │  │  top_k=10    │  │  top_k=10    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                 │
       ▼                 ▼                 ▼                 ▼
  FragmentResult    StructuredResult   BM25Result       TemporalResult
       │                 │                 │                 │
       ▼                 ▼                 ▼                 ▼
  排名序列 R1        排名序列 R2        排名序列 R3        排名序列 R4
       │                 │                 │                 │
       └────────┬────────┴────────┬────────┴────────┬────────┘
                │                 │                 │
                ▼                 ▼                 ▼
         ┌──────────────────────────────────────────────┐
         │  RRF 融合                                     │
         │  score(d) = w1×1/(k+r1) + w2×1/(k+r2)       │
         │         + w3×1/(k+r3) + w4×1/(k+r4)         │
         └──────────────────┬───────────────────────────┘
                            │
                            ▼
         ┌──────────────────────────────────────────────┐
         │  认知层权重 × Disposition 动态权重             │
         │  final_score = RRF_score × type_weight       │
         │              × disposition_adjustment        │
         └──────────────────┬───────────────────────────┘
                            │
                            ▼
         ┌──────────────────────────────────────────────┐
         │  去重 + 认知层排序 + 截断                      │
         │  top_k 最终结果                               │
         └──────────────────────────────────────────────┘
```

---

## BM25 关键词检索

### 双表 BM25 索引

```
SQLite FTS5 全文索引（Layer-R 碎片层）：
  表：knowledge_fragment_fts
  列：text, document_id, dataset_id
  分词：unicode61（支持中文）

SQLite FTS5 全文索引（Layer-S 认知层）：
  表：cognitive_node_fts
  列：text, entity_name, entity_type, tags
  分词：unicode61
  过滤条件：belief_status = 'accepted'
```

### FTS5 创建语句

```sql
CREATE VIRTUAL TABLE knowledge_fragment_fts USING fts5(
    text,
    document_id,
    dataset_id,
    content='knowledge_fragment',
    content_rowid='rowid',
    tokenize='unicode61'
);

CREATE VIRTUAL TABLE cognitive_node_fts USING fts5(
    text,
    entity_name,
    entity_type,
    tags,
    content='cognitive_node',
    content_rowid='rowid',
    tokenize='unicode61'
);
```

### BM25 检索接口

```python
async def search_bm25(
    query: str,
    top_k: int = 10,
    space_id: str | None = None,
    search_scope: str = "both",
) -> list[BM25Result]:
    results = []
    if search_scope in ("fragment", "both"):
        frag_sql = """
            SELECT fragment_id, text, dataset_id, document_id,
                   bm25(knowledge_fragment_fts) AS score
            FROM knowledge_fragment_fts
            WHERE knowledge_fragment_fts MATCH ?
        """
        results.extend(await _execute_bm25(frag_sql, query, top_k, "fragment"))

    if search_scope in ("cognitive", "both"):
        cog_sql = """
            SELECT node_id, text, entity_name, entity_type,
                   bm25(cognitive_node_fts) AS score
            FROM cognitive_node_fts
            WHERE cognitive_node_fts MATCH ?
        """
        results.extend(await _execute_bm25(cog_sql, query, top_k, "cognitive"))

    return sorted(results, key=lambda r: r.score, reverse=True)[:top_k]
```

---

## Temporal 时序检索

### 目的

利用 CognitiveNode 的结构化时序字段（valid_from/valid_to/occurred_at/recorded_at）进行时序感知检索，替代 BM25 的 CONTAINS 时序匹配。

### 时序约束自动提取

```python
TEMPORAL_PATTERNS = [
    (r'\b(20\d{2})\b', 'year'),
    (r'\b(20\d{2})\s*[-–]\s*(20\d{2})\b', 'range'),
    (r'\b(since|from|after)\s+(20\d{2})\b', 'since'),
    (r'\b(before|until|by)\s+(20\d{2})\b', 'before'),
    (r'\b(last|recent)\s+(year|month|quarter)\b', 'relative'),
]

def extract_temporal_constraint(query: str) -> TemporalConstraint | None:
    for pattern, kind in TEMPORAL_PATTERNS:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return TemporalConstraint(kind=kind, groups=match.groups())
    return None
```

### 时序检索实现

```python
async def search_temporal(
    constraint: TemporalConstraint,
    space_id: str,
    top_k: int = 10,
) -> list[TemporalResult]:
    cypher = """
        MATCH (n:CognitiveNode {space_id: $space_id, belief_status: 'accepted'})
        WHERE n.valid_from <= $period_end
          AND (n.valid_to IS NULL OR n.valid_to > $period_start)
        RETURN n
        ORDER BY n.recorded_at DESC
        LIMIT $top_k
    """
    params = {
        "space_id": space_id,
        "period_start": constraint.period_start,
        "period_end": constraint.period_end,
        "top_k": top_k,
    }
    results = await execute_cypher(cypher, params)
    for r in results:
        r.temporal_score = _compute_temporal_proximity(r, constraint)
    return sorted(results, key=lambda r: r.temporal_score, reverse=True)[:top_k]
```

### 时序邻近性评分

```
temporal_score = 0.1 * (1 - normalized_distance)

normalized_distance = |occurred_at - query_midpoint| / window_size

窗口：±2年有效，超出窗口 temporal_score = 0
```

---

## 查询路由驱动的权重分配

### 四路权重映射表

| 查询类型 | w_layer_r | w_layer_s | w_bm25 | w_temporal | 说明 |
|----------|-----------|-----------|--------|------------|------|
| factual | 0.5 | 0.2 | 0.2 | 0.1 | 向量检索为主 |
| multi-hop | 0.2 | 0.5 | 0.1 | 0.2 | 图遍历为主 |
| temporal | 0.1 | 0.2 | 0.1 | 0.6 | 时序检索为主 |
| analytical | 0.0 | 0.0 | 0.0 | 0.0 | 不走 RRF，直接路由到 RuleEngine |
| mixed | 0.3 | 0.3 | 0.2 | 0.2 | 四路均衡 |

### 加权 RRF 公式

```
RRF_score(d) = w_layer_r  × 1/(k + rank_layer_r(d))
             + w_layer_s  × 1/(k + rank_layer_s(d))
             + w_bm25     × 1/(k + rank_bm25(d))
             + w_temporal × 1/(k + rank_temporal(d))

当某路未返回文档 d 时，该路贡献为 0
```

---

## 认知层权重与 Disposition 集成

### 认知层基础权重

```
BASE_TYPE_WEIGHTS = {
    "mental_model": 2.0,
    "entity":       1.8,
    "observation":  1.5,
    "opinion":      1.3,
    "rule":         1.5,
    "procedure":    1.2,
    "episode":      1.0,
    "fragment":     0.5,
}
```

### 最终分数计算

```
final_score = RRF_score(d) × type_weight(d.memory_type) × disposition_adjustment(d)

disposition_adjustment = 1.0 + (
    skepticism       × skepticism_effect(d)
  + evidence_demand  × evidence_effect(d)
  + recency_bias     × recency_effect(d)
  + thoroughness     × thoroughness_effect(d)
)

其中：
  skepticism_effect: 对 opinion/mental_model 降权，对 entity/rule 提权
  evidence_effect:   对 proof_count < threshold 的结果降权
  recency_effect:    对 recorded_at 距今较远的结果降权
  thoroughness_effect: 增加返回数量，降低截断阈值
```

---

## 结果合并与去重

### 去重规则

```
1. FragmentResult 去重：按 fragment_id 去重
2. CognitiveNodeResult 去重：按 node_id 去重
3. 跨类型去重：FragmentResult 和 CognitiveNodeResult 不互去除（类型不同）
4. 保留策略：同一 ID 出现在多路时，取 RRF 分数最高的记录
```

### 认知层排序

```
RRF 融合后，按 final_score 降序排列
同分时按认知层优先级：opinion > semantic > procedure > perception
```

---

## 分数归一化

| 检索路径 | 原始分数 | 归一化方法 |
|----------|---------|-----------|
| Layer-R | cosine_distance ∈ [0, 2] | `1 - cosine_distance` → [0, 1] |
| Layer-S | path_cost ∈ [0, +∞) | `1 / (1 + path_cost)` → (0, 1] |
| BM25 | raw_score ∈ (-∞, 0] | `|score| / (1 + |score|)` → [0, 1) |
| Temporal | temporal_score ∈ [0, 0.1] | 直接使用（已在 [0, 0.1] 范围内） |

RRF 基于排名而非原始分数，归一化仅用于内部排序和展示。

---

## 可选：Cross-encoder 重排序

```
参考 QMD 本地 GGUF reranker：
  模型：qwen3-reranker-0.6b（本地 GGUF 格式）
  输入：query + RRF top_k 候选文档
  输出：精排分数
  触发条件：配置启用 + 候选数 > 0

流程：
  RRF 融合 → 认知层权重 → top_k 候选 → Cross-encoder 精排 → 最终排序
```

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-RRF-1 | RRF k=60 | 业界经验最优值，KAG/MAMGA/QMD/Hindsight 一致使用 |
| D-RRF-2 | 四路融合（增加 Temporal） | Hindsight 验证了时序检索臂的有效性，结构化时序字段优于 BM25 CONTAINS |
| D-RRF-3 | BM25 扩展到 CognitiveNode | Layer-S 的关键词精确匹配能力缺失，双表 FTS5 覆盖两层 |
| D-RRF-4 | 查询路由驱动权重 | 不同查询类型应偏向不同检索路径 |
| D-RRF-5 | 认知层权重叠加 RRF | RRF 解决跨路排序，认知层权重解决层内优先级，两者正交 |
| D-RRF-6 | Disposition 动态权重 | 个性化检索偏好应影响最终排序 |
| D-RRF-7 | BM25 基于 SQLite FTS5 | 本地优先原则，无需额外依赖 |
| D-RRF-8 | Cross-encoder 为可选功能 | 本地 reranker 需要 GPU 资源，默认关闭降低部署门槛 |
