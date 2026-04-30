# 查询路由设计

> **status**: draft | **phase**: rewrite | **source_of_truth**: `docs/01-overview/08-knowledge-retrieval.md` + `docs/01-overview/10-kb-process.md` | **last_verified**: 2026-04-30

## 目的

定义 QueryRouter 的分层漏斗检索 + 查询类型策略机制，使查询引擎能够按认知层次优先返回高层摘要，同时根据查询语义选择最优检索路径和参数配置。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 所有查询使用同一检索策略 | factual 查询无法利用向量检索优势，multi-hop 查询无法利用图遍历深度 |
| 2 | 边权重无差异化 | temporal 查询无法优先时序边，multi-hop 查询无法优先因果边 |
| 3 | 检索深度固定 | 简单查询浪费计算，复杂查询深度不足 |
| 4 | 无降级策略 | 单路检索失败时无法自动切换到备选路径 |
| 5 | 无分层漏斗 | 无法优先返回高层摘要（mental_model），总是返回碎片 |
| 6 | 无场景感知短路 | 审计场景可能遗漏底层证据 |
| 7 | 无 Disposition 动态权重 | 所有 Agent/用户使用相同权重，无法个性化 |

---

## 设计原则

> **[关键设计点]**：分层漏斗是主流程（决定"返回什么层次"），查询类型是内部检索策略参数（决定"怎么找"）。

```
查询输入
  ↓
分层漏斗（主流程）── 决定按什么顺序返回
  ├── 第1层 opinion（mental_model, opinion）
  ├── 第2层 semantic（entity, rule）
  ├── 第3层 procedure（episode, procedure）
  └── 第4层 perception（fragment）
  ↓
查询类型（内部策略）── 决定每层内怎么检索
  ├── factual → 向量检索
  ├── multi-hop → 图遍历
  ├── temporal → 时序过滤
  ├── analytical → 规则引擎
  └── mixed → 协同检索
  ↓
DispositionProfile（动态权重）── 个性化调整
  ├── abstraction_preference → 调整短路阈值
  ├── evidence_demand → 调整证据展开深度
  └── skepticism → 调整矛盾敏感度
```

---

## 分层漏斗检索

### 漏斗流程

```
查询输入
  ↓
第1层：opinion（mental_model, opinion）
  ├── 命中且 confidence ≥ 阈值
  │   ├── 场景允许短路 → 返回 + 异步验证低层
  │   └── 场景禁止短路 → 继续低层检索
  └── 未命中或 confidence < 阈值 → 继续
  ↓
第2层：semantic（entity, rule）
  ├── 命中 → 合并第1层结果返回
  └── 未命中 → 继续
  ↓
第3层：procedure（episode, procedure）
  ├── 命中 → 合并上层结果返回
  └── 未命中 → 继续
  ↓
第4层：perception（fragment）—— 兜底
  └── 总有结果 → 合并所有层结果返回
```

### 场景感知短路策略

| 场景 | 判定条件 | 短路行为 | 异步验证 |
|------|---------|---------|---------|
| 快速回答 | abstraction_preference > 0.7 | 允许短路 | 否 |
| 审计/合规 | evidence_demand > 0.8 | 禁止短路，必须全层检索 | — |
| 默认 | 其他 | 短路后异步验证低层 | 是 |

### 短路后异步验证

```python
async def recall_with_async_verify(query, space_id, disposition):
    results = await funnel_retrieve(query, space_id, allow_short_circuit=True)
    
    if results.short_circuited and disposition.evidence_demand <= 0.8:
        asyncio.create_task(
            async_verify_lower_layers(
                query, space_id, results,
                callback=notify_contradiction_if_found
            )
        )
    
    return results
```

### 冷启动降级

```
空知识库场景（无 mental_model/entity）：
  漏斗全层 miss → 降级到并行池检索
  → ChromaDB 全量向量搜索，不做类型权重排序
  → 返回碎片化结果，附注"知识库尚未充分构建"
```

---

## 五种查询类型（内部策略）

### 总览

| 查询类型 | 特征词（中文） | 特征词（英文） | 检索路径 | 边权重偏好 |
|----------|---------------|---------------|----------|-----------|
| **factual** | 谁/什么/哪个/哪里 | who/what/which/where | Layer-R 向量检索 → COG_EXTRACTED_FROM 扩展 | 无 |
| **multi-hop** | 为什么/如何/...和...的关系/导致 | why/how/relationship between/leads to | Layer-S 图遍历 + COGNITIVE_RELATES_TO 优先 | TEMPORAL×1.0, CAUSAL×2.0 |
| **temporal** | 什么时候/持续多久/历史变化/趋势 | when/how long/history/trend | valid_from/to + recorded_at 过滤 + 时序边 | TEMPORAL×3.0 |
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

### 参数映射表

| 参数 | factual | multi-hop | temporal | analytical | mixed |
|------|---------|-----------|----------|------------|-------|
| **检索路径** | Layer-R | Layer-S | Layer-S | RuleEngine | 协同 |
| **ChromaDB top_k** | 10 | 5 | 5 | 0 | 10 |
| **KuzuDB 遍历深度** | 1 | 3 | 2 | 0 | 3 |
| **TEMPORAL 边权重** | 1.0 | 1.0 | 3.0 | — | 2.0 |
| **CAUSAL 边权重** | 1.0 | 2.0 | 1.0 | — | 1.5 |
| **COGNITIVE_RELATES_TO 权重** | 1.0 | 1.5 | 1.0 | — | 1.2 |
| **时序过滤** | 否 | 否 | 是 | 否 | 可选 |
| **COG_EXTRACTED_FROM 扩展** | 是 | 否 | 是 | 否 | 是 |
| **COG_SUPPORTED_BY 回溯** | 否 | 否 | 否 | 是 | 是 |
| **Bundle Search** | 否 | 是 | 是 | 否 | 是 |
| **RRF 权重（Layer-R）** | 0.5 | 0.2 | 0.1 | 0.0 | 0.3 |
| **RRF 权重（Layer-S）** | 0.2 | 0.5 | 0.2 | 0.0 | 0.3 |
| **RRF 权重（BM25）** | 0.2 | 0.1 | 0.1 | 0.0 | 0.2 |
| **RRF 权重（Temporal）** | 0.1 | 0.2 | 0.6 | 0.0 | 0.2 |
| **confidence 阈值** | 0.5 | 0.4 | 0.4 | — | 0.4 |
| **belief_status 过滤** | accepted | accepted | accepted | — | accepted |
| **双时序排序** | 否 | 否 | recorded_at DESC | — | 可选 |

### RetrievalParams 数据结构

```python
@dataclass
class RetrievalParams:
    query_type: QueryType
    cognitive_layers: List[str]
    memory_types: List[str]
    chroma_top_k: int
    kuzu_max_depth: int
    edge_weights: Dict[str, float]
    temporal_filter: bool
    cog_extracted_from_expansion: bool
    cog_supported_by_backtrack: bool
    bundle_search_enabled: bool
    rrf_weights: Dict[str, float]
    confidence_threshold: float
    belief_status_filter: str
    allow_short_circuit: bool
    disposition: DispositionProfile
```

---

## DispositionProfile 动态权重

### 动态权重计算

```python
def compute_dynamic_weights(base_weights, disposition, query_type):
    weights = dict(base_weights)
    
    if disposition.abstraction_preference > 0.7:
        weights["mental_model"] *= 1.5
        weights["opinion"] *= 1.3
        weights["fragment"] *= 0.5
    elif disposition.abstraction_preference < 0.3:
        weights["mental_model"] *= 0.7
        weights["fragment"] *= 1.5
    
    if disposition.evidence_demand > 0.8:
        weights["fragment"] *= 1.3
        weights["observation"] *= 1.2
    
    if disposition.skepticism > 0.7:
        weights["mental_model"] *= 0.8
        weights["entity"] *= 1.2
    
    if disposition.thoroughness > 0.7:
        weights["fragment"] *= 1.2
        weights["observation"] *= 1.1
    
    if disposition.recency_bias > 0.7:
        pass  # recency_bias 影响 ORDER BY recorded_at DESC 排序优先级，不影响类型权重
    
    if disposition.risk_tolerance < 0.3:
        weights = {k: v * 0.8 for k, v in weights.items() if v < 1.0}
        # 低risk_tolerance: 提高min_confidence到0.8，过滤低置信度结果
    elif disposition.risk_tolerance > 0.7:
        # 高risk_tolerance: 降低min_confidence到0.3，返回更多可能相关结果
        pass
    
    return weights
```

### 场景强制覆盖

| 场景 | 判定条件 | 强制参数 |
|------|---------|---------|
| 审计/合规 | evidence_demand > 0.8 | allow_short_circuit=False, belief_status_filter='accepted', 全层检索, thoroughness=0.8 |
| 快速回答 | abstraction_preference > 0.7 | allow_short_circuit=True, 优先 mental_model, thoroughness=0.3 |
| 实时监控 | recency_bias > 0.8 | ORDER BY recorded_at DESC, evidence_demand=0.7 |
| 矛盾检查 | skepticism > 0.8 | belief_status_filter='all', 包含 pending_review |

---

## 降级策略

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

冷启动（漏斗全层 miss）:
  降级到并行池检索 → ChromaDB 全量向量搜索
```

### 降级触发条件

| 条件 | 阈值 | 动作 |
|------|------|------|
| 结果数量 | < 3 | 触发降级 |
| 最高置信度 | < 0.3 | 触发降级 |
| 检索超时 | > 5s | 终止当前路径，切换备选 |
| 存储不可用 | 连接失败 | 跳过该路，使用其他路 |
| 漏斗全层 miss | 0 结果 | 降级到并行池检索 |

---

## EvidenceExpander

> **[关键设计点]**：分层漏斗短路返回后，用户可能要求展开证据链。

### 证据展开流程

```
mental_model "华为风险等级B"
  ↓ 展开
entity "华为" (entity_name match)
  ↓ 展开
observation "华为debt_ratio连续3季度上升"
  ↓ 展开
fragment "2024年报：资产负债率65%..."
```

### 展开接口

```python
async def expand_evidence(node_id, space_id, depth=1):
    node = await get_cognitive_node(node_id)
    evidence = []
    
    if depth >= 1:
        sources = await get_source_nodes(node_id, via=["SUMMARIZED_AS", "CONSOLIDATED_INTO"])
        evidence.extend(sources)
    
    if depth >= 2:
        for source in sources:
            deeper = await get_source_nodes(source.id, via=["CONSOLIDATED_INTO", "COG_EXTRACTED_FROM"])
            evidence.extend(deeper)
    
    return evidence
```

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-QR-1 | 特征词匹配而非 LLM 分类 | 本地优先原则；O(1) vs O(tokens)；确定性输出 |
| D-QR-2 | 检测优先级 temporal > analytical > multi-hop > factual | temporal 和 analytical 有明确的专用路径，优先识别可避免误路由 |
| D-QR-3 | mixed 类型走协同路径 | 复合查询需要多路信息，协同路径可同时利用 Layer-R 和 Layer-S |
| D-QR-4 | 分层漏斗为主，查询类型为内部策略 | 漏斗决定"返回什么层次"（用户体验），查询类型决定"怎么找"（检索效率） |
| D-QR-5 | 场景感知短路策略 | 审计场景禁止短路（安全），快速场景允许短路（效率） |
| D-QR-6 | 短路后异步验证 | 平衡速度与准确性，发现矛盾时追加通知 |
| D-QR-7 | DispositionProfile 驱动动态权重 | 个性化检索，不同 Agent/用户有不同的检索偏好 |
| D-QR-8 | 冷启动降级到并行池 | 空知识库下漏斗无效，回退到传统检索保证可用性 |
