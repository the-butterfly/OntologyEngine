# RRF 融合排序

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/08-knowledge-retrieval.md` | **last_verified**: 2026-04-19

## 目的

定义 OntologyEngine 的 RRF（Reciprocal Rank Fusion）融合排序机制，将 Layer-R 向量检索、Layer-S 图遍历和 BM25 关键词检索三路结果统一融合排序。RRF 是查询引擎多路检索结果合并的核心算法，确保不同检索路径的结果可以公平竞争、互补增强。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 多路检索结果无法统一排序 | Layer-R 和 Layer-S 结果各自独立，无法交叉比较 |
| 2 | 单路检索召回不足 | 向量检索可能遗漏关键词精确匹配，关键词检索可能遗漏语义相关结果 |
| 3 | 不同检索路径的分数不可直接比较 | 向量距离、图遍历成本、BM25 分数量纲不同 |
| 4 | 查询类型无法影响融合权重 | factual 查询应偏向 Layer-R，multi-hop 应偏向 Layer-S |

---

## RRF 公式

### 核心公式

```
RRF_score(d) = Σ_i  1 / (k + rank_i)

k = 60（经验最优值，与 KAG/MAMGA/QMD 一致）
```

### 公式特性

| 特性 | 说明 |
|------|------|
| 分数量纲统一 | 所有路的分数归一化为排名的倒数，消除量纲差异 |
| 对异常值鲁棒 | 单路极端高分不会主导最终结果 |
| 排名敏感 | 排名越靠前贡献越大，但不会无限放大 |
| k 值平滑 | k=60 使排名差异适度衰减，避免 Top-1 过度主导 |

### k 值选择依据

| k 值 | Top-1 贡献 | Top-10 贡献 | 说明 |
|------|-----------|------------|------|
| 1 | 0.500 | 0.091 | 过度放大 Top-1 |
| 10 | 0.091 | 0.048 | 中等平滑 |
| **60** | **0.016** | **0.014** | **经验最优，适度平滑** |
| 100 | 0.010 | 0.009 | 过度平滑 |

---

## 三路融合架构

### 目的

定义 Layer-R + Layer-S + BM25 三路检索结果的融合流程。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 三路结果格式不同 | 统一归一化为排名序列 |
| 2 | 查询类型影响缺失 | 查询路由决定各路权重 |

### 融合流程

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Layer-R     │  │  Layer-S     │  │  BM25        │
│  向量检索     │  │  图遍历       │  │  关键词检索   │
│  top_k=10    │  │  top_k=10    │  │  top_k=10    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       ▼                 ▼                 ▼
  FragmentResult    StructuredResult   BM25Result
       │                 │                 │
       ▼                 ▼                 ▼
  排名序列 R1        排名序列 R2        排名序列 R3
       │                 │                 │
       └────────┬────────┘────────┬────────┘
                │                 │
                ▼                 ▼
         ┌──────────────────────────┐
         │  RRF 融合                │
         │  score(d) = w1×1/(k+r1) │
         │         + w2×1/(k+r2)   │
         │         + w3×1/(k+r3)   │
         └──────────┬───────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │  去重 + 排序 + 截断       │
         │  top_k 最终结果           │
         └──────────────────────────┘
```

---

## BM25 关键词检索

### 目的

定义基于 SQLite FTS5 的 BM25 关键词检索，作为向量检索的互补路径。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 向量检索可能遗漏精确匹配 | BM25 关键词检索补充精确匹配 |
| 2 | 需要额外数据库依赖 | SQLite FTS5 无需额外依赖 |

### BM25 实现

```
SQLite FTS5 全文索引：
  表：knowledge_fragment_fts
  列：text, document_id, dataset_id
  分词：unicode61（支持中文）

BM25 分数转换：
  raw_score = bm25(k1=1.2, b=0.75)
  normalized_score = |raw_score| / (1 + |raw_score|)  → 映射到 [0, 1)
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
```

### BM25 检索接口

```python
async def search_bm25(
    query: str,
    top_k: int = 10,
    dataset_id: str | None = None,
) -> list[BM25Result]:
    sql = """
        SELECT fragment_id, text, dataset_id, document_id,
               bm25(knowledge_fragment_fts) AS score
        FROM knowledge_fragment_fts
        WHERE knowledge_fragment_fts MATCH ?
    """
    params = [query]
    if dataset_id:
        sql += " AND dataset_id = ?"
        params.append(dataset_id)
    sql += " ORDER BY score ASC LIMIT ?"
    params.append(top_k)
    ...
```

---

## 查询路由驱动的权重分配

### 目的

定义不同查询类型的 RRF 融合权重，使查询路由影响最终排序结果。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 三路权重固定 | 查询类型驱动的权重映射 |
| 2 | factual 查询被图遍历结果稀释 | factual 偏向 Layer-R |

### 权重映射表

| 查询类型 | w_layer_r | w_layer_s | w_bm25 | 说明 |
|----------|-----------|-----------|--------|------|
| factual | 0.6 | 0.2 | 0.2 | 向量检索为主 |
| multi-hop | 0.3 | 0.5 | 0.2 | 图遍历为主 |
| temporal | 0.3 | 0.5 | 0.2 | 图遍历为主（时序过滤） |
| analytical | 0.0 | 0.0 | 0.0 | 不走 RRF，直接路由到 RuleEngine |
| mixed | 0.4 | 0.4 | 0.2 | 双路均衡 |

### 加权 RRF 公式

```
RRF_score(d) = w_layer_r × 1/(k + rank_layer_r(d))
             + w_layer_s × 1/(k + rank_layer_s(d))
             + w_bm25    × 1/(k + rank_bm25(d))

当某路未返回文档 d 时，该路贡献为 0
```

---

## 结果合并与去重

### 目的

定义三路结果的合并和去重策略，确保同一知识单元不会重复出现。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 碎片和实体可能指向同一知识 | 按 fragment_id / entity_id 去重 |
| 2 | 不同路返回相同结果 | ID 级去重，保留最高 RRF 分数 |

### 去重规则

```
1. FragmentResult 去重：按 fragment_id 去重
2. EntityResult 去重：按 entity_id 去重
3. 跨类型去重：FragmentResult 和 EntityResult 不互去除（类型不同）
4. 保留策略：同一 ID 出现在多路时，取 RRF 分数最高的记录
```

### 合并后排序

```
1. 按 RRF_score 降序排列
2. 取 top_k 结果
3. 分类型组装：
   - FragmentResult 列表
   - EntityResult 列表
   - EdgeResult 列表
   - EvidenceChain 列表
```

---

## 分数归一化

### 目的

定义各路检索结果的分数归一化方法，确保 RRF 融合前各路分数可比。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 向量距离和 BM25 分数量纲不同 | RRF 基于排名而非原始分数，天然消除量纲差异 |
| 2 | 同路内分数需要归一化 | 各路内部分数归一化到 [0, 1] |

### 归一化方法

| 检索路径 | 原始分数 | 归一化方法 |
|----------|---------|-----------|
| Layer-R | cosine_distance ∈ [0, 2] | `1 - cosine_distance` → [0, 1] |
| Layer-S | path_cost ∈ [0, +∞) | `1 / (1 + path_cost)` → (0, 1] |
| BM25 | raw_score ∈ (-∞, 0] | `\|score\| / (1 + \|score\|)` → [0, 1) |

### RRF 不依赖归一化

RRF 基于排名而非原始分数，因此各路归一化仅用于内部排序和展示，不影响 RRF 融合结果。

---

## 可选：Reranker 重排序

### 目的

定义可选的本地 reranker 重排序步骤，在 RRF 融合后进一步优化排序质量。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | RRF 融合可能不够精确 | 本地 reranker 模型交叉编码精排 |
| 2 | 需要额外 GPU 资源 | 可选功能，默认关闭 |

### 实现策略

```
参考 QMD 本地 GGUF reranker：
  模型：qwen3-reranker-0.6b（本地 GGUF 格式）
  输入：query + top_k 候选文档
  输出：精排分数
  触发条件：配置启用 + 候选数 > 0

流程：
  RRF 融合 → top_k 候选 → Reranker 精排 → 最终排序
```

---

## 与参考项目的对齐

| 维度 | KAG | MAMGA | QMD | OntologyEngine |
|------|-----|-------|-----|----------------|
| 融合路数 | 2（DPR + PPR） | 3（向量+关键词+全扫描） | 3（BM25+向量+HyDE） | 3（Layer-R+Layer-S+BM25） |
| RRF k 值 | 60 | 60 | 60 | 60 |
| 权重调整 | 无 | 自适应参数 | 无 | 查询路由驱动 |
| BM25 实现 | 无 | 无 | SQLite FTS5 | SQLite FTS5 |
| Reranker | 无 | 无 | GGUF 本地模型 | 可选 GGUF 本地模型 |
| 去重策略 | Chunk 级去重 | Edge 级去重 | 文档级去重 | fragment_id/entity_id 去重 |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-RRF-1 | RRF k=60 | 业界经验最优值，KAG/MAMGA/QMD 一致使用 |
| D-RRF-2 | 三路融合而非两路 | BM25 补充精确匹配，参考 QMD 验证的三路融合有效性 |
| D-RRF-3 | 查询路由驱动权重 | 不同查询类型应偏向不同检索路径，MAMGA 验证了自适应参数的有效性 |
| D-RRF-4 | BM25 基于 SQLite FTS5 | 本地优先原则，无需额外依赖 |
| D-RRF-5 | Reranker 为可选功能 | 本地 reranker 需要 GPU 资源，默认关闭降低部署门槛 |
