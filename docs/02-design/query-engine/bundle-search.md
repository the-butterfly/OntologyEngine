# Bundle Search 四阶段算法

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/08-knowledge-retrieval.md` + `docs/02-design/schema/mutual-index-edges.md` | **last_verified**: 2026-04-19

## 目的

定义 OntologyEngine Bundle Search 的四阶段算法实现，将 m_flow 的 Episode-Facet-Point-Entity 四层结构映射到 OntologyEngine 的 EntityInstance-Categorization-AnalyticalElement-KnowledgeFragment 四层结构，并扩展互索引边作为跨层跳转边。Bundle Search 是 Layer-S 图遍历的核心评分算法，通过路径成本传播实现"一条强证据链即可证明相关性"的检索语义。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 当前图遍历无成本模型 | 所有路径等权，无法区分强证据链和弱关联 |
| 2 | 边语义未参与检索评分 | 边只是类型标签，无法通过语义匹配提升路径质量 |
| 3 | 跨层跳转无成本 | Layer-R 与 Layer-S 之间跳转无代价，可能导致大量低质量跨层结果 |
| 4 | 直接命中惩罚缺失 | 直接命中摘要级信息优先于精确证据，降低结果可信度 |

---

## 核心原则

**Minimum not Average**：一条强证据链即可证明相关性，而非要求所有路径都支持。

**直接命中惩罚**：直接命中 EntityInstance 摘要的路径需要额外惩罚，优先使用 AnalyticalElement/Categorization 级别的精确证据。

**边语义参与评分**：每条边的 edge_text 向量化后与查询计算距离，作为路径成本的一部分。

---

## 四阶段算法

### Phase 1：宽网撒播（Wide Net Casting）

#### 目的

查询嵌入同时搜索多个 ChromaDB 集合，获取候选节点和边的初始集合。

#### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 单集合检索召回不足 | 多集合并行搜索 |
| 2 | 时间查询候选不足 | 时间查询时候选池翻倍 |

#### 实现

```python
COLLECTIONS_FOR_BUNDLE = [
    "entity_name",
    "entity_summary",
    "facet_search_text",
    "edge_relationship_name",
    "edge_text",
    "knowledge_fragment",
    "rule_definition",
]

async def phase1_wide_search(
    query_embedding: list[float],
    top_k: int = 100,
    domain_id: str | None = None,
    is_temporal: bool = False,
) -> dict[str, list]:
    effective_top_k = top_k
    if is_temporal:
        effective_top_k = min(top_k * 2, 300)

    results = {}
    for collection_name in COLLECTIONS_FOR_BUNDLE:
        where = {"domain_id": domain_id} if domain_id else None
        results[collection_name] = await vector_store.search(
            collection_name=collection_name,
            query_embeddings=[query_embedding],
            n_results=effective_top_k,
            where=where,
        )
    return results
```

#### 与 m_flow 对齐

| m_flow 集合 | OntologyEngine 集合 | 说明 |
|-------------|---------------------|------|
| Episode_summary | entity_summary | 实体摘要 |
| Facet_search_text | facet_search_text | 切面文本 |
| Facet_anchor_text | facet_search_text | 合并到切面文本 |
| FacetPoint_search_text | facet_search_text | 合并到切面文本 |
| Entity_name | entity_name | 实体名称 |
| Concept_name | entity_name | 合并到实体名称 |
| RelationType_relationship_name | edge_text | 边语义文本 |

---

### Phase 2：投影到图（Project to Graph）

#### 目的

将 Phase 1 命中的向量结果投影到 KuzuDB 图结构，提取子图并扩展一跳邻居。

#### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 向量结果缺乏图结构信息 | 投影到 KuzuDB 获取邻域 |
| 2 | 一跳邻居可能包含关键证据 | 两阶段投影扩展邻居 |

#### 两阶段投影

```
阶段 1 — 命中 ID 投影：
  收集所有命中 ID → KuzuDB 查询这些节点的邻域
  → 获取初始子图 fragment_1

阶段 2 — 邻居扩展：
  从 fragment_1 中提取未命中的邻居节点
  按类型优先级排序：EntityInstance > Categorization > AnalyticalElement > KnowledgeFragment
  扩展到 fragment_2
```

#### KuzuDB 投影查询

```cypher
MATCH (e:EntityNode)-[r]-(n)
WHERE e.id IN $hit_ids
  AND r.confidence >= $min_confidence
RETURN e, r, n
LIMIT $limit
```

#### 邻居类型优先级

```python
TYPE_PRIORITY = {
    "EntityNode": 0,
    "CategoryTagNode": 1,
    "MetricValueNode": 2,
    "KnowledgeFragmentNode": 3,
    "RuleDefinitionNode": 4,
}
```

#### 与 m_flow 对齐

| m_flow 投影 | OntologyEngine 投影 | 说明 |
|-------------|---------------------|------|
| get_episodic_memory_fragment | KuzuDB 邻域查询 | 图投影方式 |
| Episode/Facet/FacetPoint/Entity 优先级 | EntityNode/CategoryTagNode/MetricValueNode/KnowledgeFragmentNode 优先级 | 类型优先级映射 |

---

### Phase 3：代价传播（Cost Propagation）

#### 目的

从叶节点向根节点传播代价，对每个 EntityInstance 评估所有可能路径，计算路径成本。

#### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 路径无成本模型 | 路径成本 = 起始代价 + Σ(边代价 + 跳惩罚) + 未命中惩罚 |
| 2 | 直接命中缺乏惩罚 | direct_episode_penalty = 0.3 |
| 3 | 跨层跳转无代价 | 互索引边跳数惩罚 = 0.15（同层 0.05） |

#### 路径成本公式

```
路径成本 = 起始节点向量距离
         + Σ(边向量距离 + 跳数惩罚 + 边类型权重调整)
         + miss_penalty（边未被向量检索命中的惩罚）

EntityInstance 最终得分 = min(所有路径成本)  ← Minimum not Average
```

#### 默认参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `edge_miss_cost` | 0.9 | 边未被向量检索命中的惩罚 |
| `hop_cost` | 0.05 | 同层内跳数惩罚 |
| `cross_layer_hop_cost` | 0.15 | 跨层跳转跳数惩罚 |
| `direct_entity_penalty` | 0.3 | 直接命中 EntityInstance 的惩罚 |
| `max_relevant_ids` | 300 | 最大相关 ID 数量 |

#### 互索引边的 miss_penalty

| 边类型 | miss_penalty | 说明 |
|--------|-------------|------|
| EXTRACTED_FROM | 0.5 | 实体通常有明确来源 |
| SUPPORTED_BY | 0.7 | 支撑关系可能不唯一 |
| DEFINED_IN | 0.3 | 规则定义来源通常明确 |
| TRACE_TO | 0.6 | 推理追溯可能多路径 |

#### Categorization 近似匹配折扣

```
当 Categorization 向量距离 < 0.1 时：
  边代价降至 0.1
  跳代价降至 0.05

当 Categorization 向量距离 < 0.2 时：
  边代价 × 0.3
  跳代价 × 0.3

其他：
  使用原始值
```

#### 与 m_flow 对齐

| m_flow 成本计算 | OntologyEngine 成本计算 | 说明 |
|-----------------|------------------------|------|
| EpisodeBundle.score | EntityBundle.score | 最终得分 = min(所有路径成本) |
| direct_episode_penalty = 0.3 | direct_entity_penalty = 0.3 | 直接命中惩罚 |
| edge_miss_cost = 0.9 | edge_miss_cost = 0.9 | 边未命中惩罚 |
| hop_cost = 0.05 | hop_cost = 0.05（同层）/ 0.15（跨层） | 跳数惩罚 |
| Facet 近似匹配折扣 | Categorization 近似匹配折扣 | 精确匹配折扣 |

---

### Phase 4：排序组装（Sort and Assemble）

#### 目的

按 bundle cost 排序取 top-k，根据 display_mode 组装输出。

#### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 结果排序无统一标准 | 按 bundle cost 升序（成本越低越相关） |
| 2 | 输出格式不灵活 | display_mode 支持 summary/detail 两种模式 |

#### 排序

```python
top_bundles = heapq.nsmallest(top_k, bundles, key=lambda b: b.score)
```

#### 组装模式

| display_mode | 输出内容 | 适用场景 |
|-------------|----------|---------|
| `summary` | EntityInstance 摘要 + 关键边 | LLM 上下文，简洁优先 |
| `detail` | Categorization + AnalyticalElement + 边详情 | 审计追溯，完整优先 |

#### 输出控制参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_categorizations_per_entity` | 4 | 每个 EntityInstance 最多返回的分类标注 |
| `max_elements_per_categorization` | 8 | 每个分类标注最多返回的分析要素 |

---

## 五种路径类型映射

### 目的

将 m_flow 的五种路径类型映射到 OntologyEngine 的概念体系，并新增跨层路径类型。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | m_flow 路径类型无法直接复用 | 映射到 OE 的 EntityInstance/Categorization/AnalyticalElement |
| 2 | 跨层路径缺乏定义 | 新增互索引边驱动的跨层路径类型 |

### 映射表

| m_flow 路径类型 | OntologyEngine 映射 | 路径描述 | 涉及的互索引边 |
|-----------------|---------------------|---------|---------------|
| direct_episode | 直接命中 EntityInstance | EntityInstance 摘要直接匹配 | 无 |
| facet | Categorization → EntityInstance | 通过分类标注到达实体 | 无 |
| point | AnalyticalElement → Categorization → EntityInstance | 通过分析要素和分类到达实体 | 无 |
| entity | EntityInstance 直接命中 | 实体名称直接匹配 | 无 |
| facet_entity | EntityInstance → Categorization → EntityInstance | 通过实体关联的分类到达另一实体 | 无 |
| **cross_layer_extracted（新增）** | KnowledgeFragment → EXTRACTED_FROM → EntityInstance | 从碎片导航到实体 | EXTRACTED_FROM |
| **cross_layer_supported（新增）** | EntityInstance → SUPPORTED_BY → KnowledgeFragment | 从实体导航到支撑碎片 | SUPPORTED_BY |
| **cross_layer_defined（新增）** | RuleDefinition → DEFINED_IN → KnowledgeFragment | 从规则导航到定义来源 | DEFINED_IN |
| **cross_layer_trace（新增）** | ExecutionStepSnapshot → TRACE_TO → KnowledgeFragment | 从推理步骤导航到证据碎片 | TRACE_TO |

### 跨层路径成本

```
跨层路径成本 = 起始节点向量距离
             + 互索引边向量距离（或 miss_penalty）
             + cross_layer_hop_cost（0.15）
             + 目标层节点向量距离
```

---

## 自适应评分（参考 m_flow AdaptiveScoringContext）

### 目的

引入 m_flow 的自适应评分机制，根据向量搜索结果的质量动态调整语义信号和结构信号的权重。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 语义信号和结构信号权重固定 | 自适应 lambda 融合系数 |
| 2 | 不同集合的基线距离不同 | 集合级 baseline 归一化 |

### 评分公式

```
Conf = f_dist(raw_distance / baseline) × f_gap(gap)

semantic = W_node × node_score + W_edge × edge_score

final = lambda × semantic + (1 - lambda) × struct

struct = 1 - 1/(1 + rank × decay_factor)
```

### 集合基线

| 集合 | baseline | 说明 |
|------|----------|------|
| facet_search_text | 0.60 | 中等长度文本 |
| edge_text | 0.56 | 边描述文本 |
| entity_name | 0.68 | 实体名称 |
| entity_summary | 1.06 | 长文本摘要 |
| knowledge_fragment | 1.06 | 长文本碎片 |

---

## 与参考项目的对齐总结

| 维度 | m_flow Bundle Search | KAG DPR+PPR | OntologyEngine |
|------|---------------------|-------------|----------------|
| 阶段数 | 4（宽网→投影→传播→组装） | 5（DPR→种子→PPR→RRF→收集） | 4（对齐 m_flow） |
| 核心原则 | Minimum not Average | PPR 概率传播 | Minimum not Average |
| 边语义 | edge_text 向量化 | 无 | edge_text 向量化 + 互索引边 |
| 跨层跳转 | 无 | Chunk→KU 隐式链接 | 互索引边显式跨层跳转 |
| 自适应评分 | AdaptiveScoringContext | 无 | 自适应 lambda 融合 |
| 时间增强 | 时间匹配奖励/惩罚 | 无 | valid_from/to + 时间增强 |
| 直接命中惩罚 | direct_episode_penalty=0.3 | 无 | direct_entity_penalty=0.3 |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-BS-1 | 四阶段算法对齐 m_flow | m_flow 的 Bundle Search 经过生产验证，算法成熟 |
| D-BS-2 | 新增四种跨层路径类型 | 互索引边是 OE 双层架构的核心纽带，必须纳入成本传播 |
| D-BS-3 | 跨层跳数惩罚高于同层 | 跨层跳转引入额外不确定性，需要更高成本抑制低质量跨层结果 |
| D-BS-4 | 引入自适应评分 | m_flow 验证了自适应 lambda 的有效性，可根据搜索质量动态调整权重 |
