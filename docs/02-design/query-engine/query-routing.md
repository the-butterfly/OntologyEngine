# 查询路由设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/08-knowledge-retrieval.md` + `docs/01-overview/05-concepts.md` | **last_verified**: 2026-04-19

## 目的

定义 QueryRouter 的查询类型识别机制、参数映射规则和降级策略，使查询引擎能够根据查询语义自动选择最优检索路径和参数配置。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 所有查询使用同一检索策略 | factual 查询无法利用向量检索优势，multi-hop 查询无法利用图遍历深度 |
| 2 | 边权重无差异化 | temporal 查询无法优先时序边，multi-hop 查询无法优先因果边 |
| 3 | 检索深度固定 | 简单查询浪费计算，复杂查询深度不足 |
| 4 | 无降级策略 | 单路检索失败时无法自动切换到备选路径 |

---

## 五种查询类型

### 总览

| 查询类型 | 特征词（中文） | 特征词（英文） | 检索路径 | 边权重偏好 |
|----------|---------------|---------------|----------|-----------|
| **factual** | 谁/什么/哪个/哪里 | who/what/which/where | Layer-R 向量检索 → EXTRACTED_FROM 扩展 | 无 |
| **multi-hop** | 为什么/如何/...和...的关系/导致 | why/how/relationship between/leads to | Layer-S 图遍历 + ENTITY 边优先 | TEMPORAL×1.0, CAUSAL×2.0 |
| **temporal** | 什么时候/持续多久/历史变化/趋势 | when/how long/history/trend | valid_from/to 过滤 + 时序边 | TEMPORAL×3.0 |
| **analytical** | 计算/分析/占比/评估/评分 | calculate/analyze/ratio/evaluate/score | → L4 RuleEngine 执行 | 无 |
| **mixed** | 复合查询（包含多种特征词） | 复合查询 | Layer-R → Layer-S → trace_to 回溯 | 自适应 |

### 类型识别优先级

```
检测顺序：temporal → analytical → multi-hop → factual → mixed

规则：
1. temporal 优先级最高：只要出现时间特征词，优先走时序路径
2. analytical 次之：计算/分析类查询直接路由到规则引擎
3. multi-hop 第三：关系/因果类查询走图遍历
4. factual 第四：简单事实查询走向量检索
5. mixed 兜底：同时命中多种特征词时走协同路径
```

---

## 特征词检测

### 目的

定义每种查询类型的特征词列表和匹配规则，实现 O(1) 复杂度的查询类型识别。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 依赖 LLM 分类增加延迟和成本 | 特征词匹配 O(1)，无需 LLM 调用 |
| 2 | 分类结果不稳定 | 确定性匹配，相同输入必定相同输出 |
| 3 | 中英文混合查询识别困难 | 同时支持中英文特征词 |

### 特征词定义

#### factual

```python
FACTUAL_PATTERNS = {
    "zh": ["谁", "什么", "哪个", "哪里", "多少", "是否", "有没有"],
    "en": ["who", "what", "which", "where", "how many", "how much", "is there", "does"],
}
```

#### multi-hop

```python
MULTI_HOP_PATTERNS = {
    "zh": ["为什么", "如何", "关系", "导致", "影响", "原因", "结果", "因果", "之间"],
    "en": ["why", "how", "relationship between", "leads to", "causes", "affects", "because", "therefore"],
}
```

#### temporal

```python
TEMPORAL_PATTERNS = {
    "zh": ["什么时候", "何时", "持续多久", "历史", "变化", "趋势", "之前", "之后", "期间", "时间线"],
    "en": ["when", "how long", "history", "change over", "trend", "before", "after", "during", "timeline"],
}
```

#### analytical

```python
ANALYTICAL_PATTERNS = {
    "zh": ["计算", "分析", "占比", "评估", "评分", "评级", "风险等级", "合规"],
    "en": ["calculate", "analyze", "ratio", "evaluate", "score", "rate", "grade", "compliance"],
}
```

### 检测算法

```python
def detect_query_type(query: str) -> QueryType:
    scores = {
        "factual": 0,
        "multi_hop": 0,
        "temporal": 0,
        "analytical": 0,
    }

    query_lower = query.lower()

    for qtype, patterns in ALL_PATTERNS.items():
        for lang, words in patterns.items():
            for word in words:
                if word in query_lower:
                    scores[qtype] += 1

    hit_types = [k for k, v in scores.items() if v > 0]

    if len(hit_types) == 0:
        return QueryType.FACTUAL
    if len(hit_types) >= 2:
        return QueryType.MIXED

    return QueryType(hit_types[0])
```

---

## 参数映射

### 目的

定义每种查询类型到检索参数的映射关系，使查询路由的输出可直接驱动检索模块。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 检索参数硬编码 | 查询类型驱动的参数映射表 |
| 2 | 不同查询类型无法差异化调参 | 每种类型有独立的参数集 |

### 参数映射表

| 参数 | factual | multi-hop | temporal | analytical | mixed |
|------|---------|-----------|----------|------------|-------|
| **检索路径** | Layer-R | Layer-S | Layer-S | RuleEngine | 协同 |
| **ChromaDB top_k** | 10 | 5 | 5 | 0 | 10 |
| **KuzuDB 遍历深度** | 1 | 3 | 2 | 0 | 3 |
| **TEMPORAL 边权重** | 1.0 | 1.0 | 3.0 | — | 2.0 |
| **CAUSAL 边权重** | 1.0 | 2.0 | 1.0 | — | 1.5 |
| **ENTITY 边权重** | 1.0 | 1.5 | 1.0 | — | 1.2 |
| **时序过滤** | 否 | 否 | 是 | 否 | 可选 |
| **EXTRACTED_FROM 扩展** | 是 | 否 | 是 | 否 | 是 |
| **TRACE_TO 回溯** | 否 | 否 | 否 | 是 | 是 |
| **Bundle Search** | 否 | 是 | 是 | 否 | 是 |
| **RRF 权重（Layer-R）** | 0.6 | 0.3 | 0.3 | 0.0 | 0.4 |
| **RRF 权重（Layer-S）** | 0.2 | 0.5 | 0.5 | 0.0 | 0.4 |
| **RRF 权重（BM25）** | 0.2 | 0.2 | 0.2 | 0.0 | 0.2 |
| **confidence 阈值** | 0.5 | 0.4 | 0.4 | — | 0.4 |

### RetrievalParams 数据结构

```python
@dataclass
class RetrievalParams:
    query_type: QueryType
    chroma_top_k: int
    kuzu_max_depth: int
    edge_weights: Dict[str, float]
    temporal_filter: bool
    extracted_from_expansion: bool
    trace_to_backtrack: bool
    bundle_search_enabled: bool
    rrf_weights: Dict[str, float]
    confidence_threshold: float
```

---

## 降级策略

### 目的

定义单路检索失败或结果不足时的自动降级路径，确保查询始终能返回有意义的结果。

### 解决的问题

| # | 问题 | 解决方式 |
|---|------|----------|
| 1 | 单路检索失败导致空结果 | 自动切换到备选路径 |
| 2 | 结果数量不足 | 扩大检索范围或增加备选路径 |
| 3 | 降级策略缺乏优先级 | 按查询类型定义降级链 |

### 降级链

```
factual:
  Layer-R 向量检索 → 结果不足 → BM25 关键词检索 → 结果不足 → Layer-S 邻域查询

multi-hop:
  Layer-S 图遍历 → 结果不足 → Bundle Search → 结果不足 → Layer-R 向量检索

temporal:
  Layer-S 时序过滤 → 结果不足 → 放宽时间窗口 → 结果不足 → Layer-R 向量检索

analytical:
  RuleEngine 执行 → 前置条件不满足 → Layer-S 查找相关指标 → Layer-R 查找相关文档

mixed:
  协同检索 → 任一路失败 → 降级为单路最优路径
```

### 降级触发条件

| 条件 | 阈值 | 动作 |
|------|------|------|
| 结果数量 | < 3 | 触发降级 |
| 最高置信度 | < 0.3 | 触发降级 |
| 检索超时 | > 5s | 终止当前路径，切换备选 |
| 存储不可用 | 连接失败 | 跳过该路，使用其他路 |

---

## 与参考项目的对齐

| 维度 | MAMGA | m_flow | KAG | OntologyEngine |
|------|-------|--------|-----|----------------|
| 路由方式 | 查询类型自适应参数 | MemoryOrchestrator 软路由 | IndexManager 配置化 | 特征词 + 参数映射 |
| 参数调整 | max_depth, similarity_threshold, scoring_weights | top_k 预算分配 | extractor + retriever 配置 | RetrievalParams 映射表 |
| 降级策略 | 无显式降级 | 无显式降级 | 多 retriever 并行 | 降级链 + 触发条件 |
| 意图检测 | LLM 分类 | 无（固定预算） | LLM 规划 | 特征词匹配（O(1)） |

### 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-QR-1 | 特征词匹配而非 LLM 分类 | 本地优先原则；O(1) vs O(tokens)；确定性输出 |
| D-QR-2 | 检测优先级 temporal > analytical > multi-hop > factual | temporal 和 analytical 有明确的专用路径，优先识别可避免误路由 |
| D-QR-3 | mixed 类型走协同路径 | 复合查询需要多路信息，协同路径可同时利用 Layer-R 和 Layer-S |
