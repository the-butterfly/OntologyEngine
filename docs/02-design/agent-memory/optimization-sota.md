# SOTA 优化方案：Token 效率 / 前瞻性索引 / 信念修正形式化

> **status**: draft | **phase**: phase2 | **source\_of\_truth**: 本文档 | **last\_verified**: 2026-05-12
> **参考方案**: mem0 (Token-Efficient Memory Algorithm), Kumiho (AGM Belief Revision + Prospective Indexing), Hindsight (TEMPR)

***

## 目的

基于 mem0、Kumiho、Hindsight 等 SOTA 方案的深度分析，对 OntologyEngine Agent 记忆系统进行三个方向的优化设计，解决当前设计在 Token 效率、语义鸿沟召回和信念修正形式化方面的差距。

## 解决的问题

| # | 问题                              | 当前状态               | SOTA 对比                                        | 影响            |
| - | ------------------------------- | ------------------ | ---------------------------------------------- | ------------- |
| 1 | 检索 Token 效率低，无预算感知              | token\_budget 仅做截断 | mem0 \~6,950 token/查询，3-4x 效率                  | Agent 上下文窗口浪费 |
| 2 | Cue-Trigger Semantic Disconnect | QUL 仅做检索时约束提取      | Kumiho Prospective Indexing 写入时预索引             | 隐性约束记忆无法召回    |
| 3 | 信念修正缺形式化保证                      | 7 条规则 + eval 执行    | Kumiho AGM K*2-K*6 + Relevance/Core-Retainment | 规则冲突可能产生逻辑不一致 |

***

## 优化一：Token 效率优化

### 1.1 问题分析

当前 recall 管线的 Token 效率问题：

| 环节    | 当前实现                      | 问题                            |
| ----- | ------------------------- | ----------------------------- |
| 检索过取  | RRF 四路过取，无倍率控制            | mem0 用 4x 过取 + 自适应除数，OE 无过取策略 |
| 结果裁剪  | token\_budget 逐条截断        | 无结构化压缩，长文本记忆浪费 token          |
| 证据链展开 | include\_evidence 默认 True | 每条结果都展开证据，token 消耗翻倍          |
| 短路策略  | 仅在 opinion 层短路            | 缺少激进短路模式（只返回 mental\_model）   |
| 结果格式  | 全字段返回                     | 无字段选择机制                       |

### 1.2 优化设计：五层 Token 效率架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: 预算感知检索 (Budget-Aware Retrieval)                  │
│  · token_budget 自动推断（L1 API 默认 4000）                     │
│  · 过取倍率 = f(token_budget, query_type)                        │
│  · mem0: internal_limit = max(limit * 4, 60)                    │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: 结构化压缩 (Structured Compression)                    │
│  · 结果摘要化：长文本 → 核心句 + 关键属性                         │
│  · 证据链折叠：默认只返回 source_fragment_ids，不展开全文          │
│  · 字段选择：Agent 指定需要的字段子集                              │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: 激进短路 (Aggressive Short-Circuit)                    │
│  · thoroughness < 0.3 → 只返回 opinion 层                       │
│  · evidence_demand < 0.5 → 禁止证据链展开                        │
│  · abstraction_preference > 0.7 → mental_model 优先，碎片跳过    │
├─────────────────────────────────────────────────────────────────┤
│  Layer 4: 加性融合打分 (Additive Scoring)                        │
│  · 参考 mem0: semantic + bm25 + entity_boost                    │
│  · 自适应除数: max_possible = 1.0 + has_bm25 + has_entity       │
│  · 语义前置门控: semantic_score < threshold → 排除               │
├─────────────────────────────────────────────────────────────────┤
│  Layer 5: 结果格式化 (Result Formatting)                         │
│  · Token 预算裁剪：按 rank_score 降序逐条纳入                    │
│  · 上下文组装：Zep 式 Token 高效格式化                            │
│  · 元数据分离：核心字段 + additional_metadata 嵌套               │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Layer 1: 预算感知检索

```python
DEFAULT_TOKEN_BUDGETS = {
    "L1": 4000,
    "L2": 8000,
    "L3": 16000,
}

OVERFETCH_MULTIPLIERS = {
    "factual": 4,
    "multi_hop": 6,
    "temporal": 3,
    "analytical": 5,
}

def compute_internal_limit(token_budget: int, query_type: str, avg_tokens_per_result: int = 200) -> int:
    target_results = max(token_budget // avg_tokens_per_result, 5)
    multiplier = OVERFETCH_MULTIPLIERS.get(query_type, 4)
    return max(target_results * multiplier, 20)
```

**与当前实现的差异**：当前 `top_k` 是固定值（默认 10），不考虑 token 预算和查询类型。优化后，`internal_limit` 由 token\_budget 和 query\_type 动态决定。

### 1.4 Layer 2: 结构化压缩

```python
class ResultCompressor:
    async def compress(self, result: dict, budget: int, mode: str = "auto") -> dict:
        if mode == "full":
            return result

        compressed = {
            "id": result["id"],
            "memory_type": result["memory_type"],
            "confidence": result["confidence"],
            "rank_score": result.get("rank_score"),
        }

        if mode == "minimal":
            compressed["text"] = self._extract_core_sentence(result["text"])
            compressed["entity_name"] = result.get("entity_name")
        elif mode == "standard":
            compressed["text"] = result["text"]
            compressed["entity_name"] = result.get("entity_name")
            compressed["tags"] = result.get("tags")

        if budget > 6000 and result.get("evidence"):
            compressed["evidence_ids"] = [e["id"] for e in result["evidence"]]
        else:
            compressed["source_fragment_ids"] = result.get("source_fragment_ids", [])

        return compressed

    def _extract_core_sentence(self, text: str) -> str:
        if len(text) <= 100:
            return text
        first_sentence = text.split("。")[0].split(". ")[0]
        return first_sentence[:100] + "..." if len(first_sentence) > 100 else first_sentence
```

**压缩模式**：

| 模式         | 触发条件              | 包含字段                        | 预估 token/结果 |
| ---------- | ----------------- | --------------------------- | ----------- |
| `full`     | budget > 12000    | 全部字段 + 证据链                  | \~400       |
| `standard` | budget 6000-12000 | text + 核心字段 + evidence\_ids | \~150       |
| `minimal`  | budget < 6000     | 核心句 + id + type             | \~50        |

### 1.5 Layer 3: 激进短路

```python
AGGRESSIVE_SHORT_CIRCUIT_CONDITIONS = {
    "opinion_only": {
        "trigger": lambda d: d.thoroughness < 0.3 and d.abstraction_preference > 0.7,
        "behavior": "只返回 opinion 层 (mental_model, opinion)，跳过 semantic/procedure/perception",
        "max_results": 3,
    },
    "entity_first": {
        "trigger": lambda d: d.evidence_demand < 0.5 and d.abstraction_preference > 0.5,
        "behavior": "entity/rule 优先，不展开证据链",
        "max_results": 5,
        "include_evidence": False,
    },
    "fast_answer": {
        "trigger": lambda d: d.thoroughness < 0.4,
        "behavior": "允许短路后跳过异步验证",
        "skip_verification": True,
    },
}
```

### 1.6 Layer 4: 加性融合打分

参考 mem0 的三信号融合架构，优化当前 RRF 融合：

```python
ENTITY_BOOST_WEIGHT = 0.5

def score_and_rank_v2(
    semantic_results: list[dict],
    bm25_scores: dict[str, float],
    entity_boosts: dict[str, float],
    threshold: float = 0.1,
    top_k: int = 10,
) -> list[dict]:
    has_bm25 = len(bm25_scores) > 0
    has_entity = len(entity_boosts) > 0
    max_possible = 1.0
    if has_bm25:
        max_possible += 1.0
    if has_entity:
        max_possible += ENTITY_BOOST_WEIGHT

    scored = []
    for result in semantic_results:
        semantic_score = result.get("score", 0.0)
        if semantic_score < threshold:
            continue

        mem_id = result["id"]
        bm25_score = bm25_scores.get(mem_id, 0.0)
        entity_boost = entity_boosts.get(mem_id, 0.0)

        raw_combined = semantic_score + bm25_score + entity_boost
        combined = min(raw_combined / max_possible, 1.0)

        result["combined_score"] = combined
        scored.append(result)

    scored.sort(key=lambda r: r["combined_score"], reverse=True)
    return scored[:top_k]
```

**与当前 RRF 的差异**：

- RRF 用 `1/(k+rank)` 融合排名，加性融合用归一化分数融合
- 加性融合有语义前置门控（threshold），RRF 无
- 加性融合的自适应除数根据活跃信号动态调整

### 1.7 Layer 5: 结果格式化

```python
CORE_RESULT_KEYS = {"id", "memory_type", "text", "confidence", "rank_score", "cognitive_layer"}
PROMOTED_KEYS = {"entity_name", "entity_type", "tags", "model_domain", "belief_status"}

def format_result(result: dict, mode: str = "standard") -> dict:
    if mode == "full":
        return result

    core = {k: result[k] for k in CORE_RESULT_KEYS if k in result}
    promoted = {k: result[k] for k in PROMOTED_KEYS if k in result}
    core.update(promoted)

    if mode == "minimal":
        core["text"] = _extract_core_sentence(core.get("text", ""))

    additional = {k: v for k, v in result.items() if k not in core and k not in {"evidence"}}
    if additional:
        core["metadata"] = additional

    return core
```

### 1.8 验收案例

**案例 1：预算感知检索**

```
场景：Agent 上下文窗口仅剩 4000 token，需要检索"华为风险等级"
  · 当前：recall 返回 10 条结果，每条 ~400 token，总计 ~4000 token，可能超出
  · 优化后：token_budget=4000 → internal_limit=80 → 过取后融合 → 压缩模式=minimal
    → 返回 8 条 minimal 结果，每条 ~50 token，总计 ~400 token + 3 条 standard 结果 ~450 token
    → 总计 ~850 token，节省 78%
```

**案例 2：激进短路**

```
场景：快速回答模式，thoroughness=0.2, abstraction_preference=0.8
  · 当前：分层漏斗仍遍历 4 层，返回 10 条混合结果
  · 优化后：触发 opinion_only 短路 → 只返回 mental_model 和 opinion
    → 1 条 mental_model (rank_score=2.8) 直接命中，跳过后续层
    → Token 消耗从 ~4000 降至 ~200
```

**案例 3：结构化压缩**

```
场景：审计模式，需要完整证据链，token_budget=12000
  · 当前：10 条结果 × (正文 + 证据链) = ~8000 token
  · 优化后：mode=full → 完整返回，与当前行为一致
  · 但 budget=8000 时：mode=standard → 10 条 × 150 token = ~1500 token
    → 节省 81%，同时保留 evidence_ids 供后续展开
```

***

## 优化二：前瞻性索引（Prospective Indexing）

### 2.1 问题分析

**Cue-Trigger Semantic Disconnect**：当查询线索与原始记忆在语义上存在鸿沟时，向量检索无法召回。

```
会话 1: 用户提到"我对海鲜过敏"
会话 10: 用户询问"推荐什么晚餐？"

向量相似度("海鲜过敏", "推荐晚餐") ≈ 0.15 → 远低于阈值 0.3 → 召回失败
```

当前 QUL 的局限：QUL 在**检索时**提取任务约束并调整检索策略，是**反应式**方法。当隐性约束从未在查询中被提及（如"海鲜过敏"与"晚餐推荐"的关联），QUL 无法建立桥梁。

### 2.2 设计：写入时前瞻性索引

```
┌─────────────────────────────────────────────────────────────────┐
│  写入路径（oe_remember）                                         │
│                                                                  │
│  原始内容 → 事实提取 → 实体链接 → [新增] 前瞻性索引生成           │
│                                       │                          │
│                                       ▼                          │
│                              LLM 生成假设性未来查询场景            │
│                              · "推荐什么晚餐？" → 需排除海鲜      │
│                              · "这家日料店合适吗？" → 不合适      │
│                              · "能吃虾吗？" → 不能               │
│                                       │                          │
│                                       ▼                          │
│                              场景嵌入 → ProspectiveIndex 存储     │
│                              · prospective_query: 嵌入向量        │
│                              · source_node_id: 原始记忆 ID       │
│                              · reasoning: 推理链摘要              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  检索路径（oe_recall）                                           │
│                                                                  │
│  查询 → 向量检索 → [新增] 前瞻性索引匹配 → 合并候选集             │
│                         │                                        │
│                         ▼                                        │
│              ProspectiveIndex 向量搜索                            │
│              · 查询与 prospective_query 匹配                      │
│              · 返回 source_node_id 指向的原始记忆                  │
│              · boost = similarity × PROSPECTIVE_BOOST_WEIGHT     │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 ProspectiveIndex 数据模型

```cypher
CREATE NODE TABLE ProspectiveIndex (
    id              STRING PRIMARY KEY,
    space_id        STRING,
    source_node_id  STRING,
    prospective_query STRING,
    reasoning       STRING,
    entity_context  STRING,
    created_at      DATETIME
)
```

ChromaDB 集合：

```
Collection: "prospective_queries"

每条记录:
  id: prospective_index_id
  embedding: prospective_query 的向量嵌入
  metadata: {
    space_id: string,
    source_node_id: string,
    entity_context: string,
  }
```

### 2.4 前瞻性索引生成

```python
PROSPECTIVE_INDEX_PROMPT = """Given the following memory fact, generate 3-5 hypothetical future 
query scenarios where this fact would be relevant but the query would NOT directly mention 
the key concepts in the fact.

Memory: {fact_text}
Entities: {entities}
Context: {context}

For each scenario, provide:
1. prospective_query: A natural language query a user might ask
2. reasoning: Why this memory is relevant to the query (brief chain of thought)

Rules:
- Queries should be semantically distant from the original fact (different vocabulary)
- Focus on decision-making, recommendation, or planning scenarios
- Include at least one query about a related but different domain

Output JSON:
{{
    "prospective_queries": [
        {{"query": "...", "reasoning": "..."}},
        ...
    ]
}}"""

PROSPECTIVE_GENERATION_TRIGGERS = {
    "always": lambda node: node.memory_type in ("observation", "opinion", "constraint", "commitment"),
    "high_value": lambda node: node.confidence >= 0.8 and node.proof_count >= 2,
    "model_domain_filter": lambda node: node.model_domain in ("user", "world", "self"),
}

async def generate_prospective_indexes(
    node: CognitiveNode,
    llm_call_fn,
    max_scenarios: int = 5,
) -> list[ProspectiveIndex]:
    if not any(trigger(node) for trigger in PROSPECTIVE_GENERATION_TRIGGERS.values()):
        return []

    entities = node.entity_name or ""
    context = node.tags if node.tags else []

    prompt = PROSPECTIVE_INDEX_PROMPT.format(
        fact_text=node.text,
        entities=entities,
        context=context,
    )

    result = await llm_call_fn(prompt, response_format="json")
    scenarios = result.get("prospective_queries", [])[:max_scenarios]

    indexes = []
    for scenario in scenarios:
        idx = ProspectiveIndex(
            id=generate_uuid5(scenario["query"], node.id),
            space_id=node.space_id,
            source_node_id=node.id,
            prospective_query=scenario["query"],
            reasoning=scenario["reasoning"],
            entity_context=entities,
            created_at=datetime.utcnow(),
        )
        indexes.append(idx)

    return indexes
```

### 2.5 检索时前瞻性匹配

```python
PROSPECTIVE_BOOST_WEIGHT = 0.4
PROSPECTIVE_SIMILARITY_THRESHOLD = 0.5

async def search_prospective_indexes(
    query: str,
    space_id: str,
    top_k: int = 10,
) -> dict[str, float]:
    query_embedding = await embed(query)

    results = await chroma_query(
        collection="prospective_queries",
        query_embeddings=[query_embedding],
        where={"space_id": space_id},
        top_k=top_k * 3,
    )

    boosts = {}
    for result in results:
        if result.similarity < PROSPECTIVE_SIMILARITY_THRESHOLD:
            continue
        source_id = result.metadata["source_node_id"]
        boost = result.similarity * PROSPECTIVE_BOOST_WEIGHT
        if source_id not in boosts or boosts[source_id] < boost:
            boosts[source_id] = boost

    return boosts
```

### 2.6 与 recall 管线集成

在 recall 的评分阶段（步骤 5-6 之间）插入前瞻性索引匹配：

```
recall(query, space_id, ...)
  │
  ├─ 1-4. [不变] 类型过滤 → 置信度过滤 → 信念状态过滤 → 可见性过滤
  │
  ├─ 5. DispositionProfile 动态权重
  │
  ├─ 5.5 [新增] 前瞻性索引匹配
  │    └── search_prospective_indexes(query, space_id)
  │    └── 对匹配的 source_node_id 施加 prospective_boost
  │    └── rank_score *= (1.0 + prospective_boost)
  │
  ├─ 6. 时序邻近性评分
  │
  ├─ 7-10. [不变] 重排序 → 证据链展开 → Token 裁剪 → 返回
```

### 2.7 成本控制

| 维度         | 策略                                                           |
| ---------- | ------------------------------------------------------------ |
| 写入时 LLM 成本 | 仅对 observation/opinion/constraint/commitment 类型生成，每条 3-5 个场景 |
| 存储成本       | ProspectiveIndex 独立集合，不污染主记忆库                                |
| 检索时延迟      | 前瞻性匹配与 RRF 融合并行执行，不增加串行延迟                                    |
| 索引更新       | 碎片巩固为 observation 时触发前瞻性索引生成；mental\_model 刷新时重新生成           |

### 2.8 验收案例

**案例 1：隐性约束召回**

```
写入阶段:
  oe_remember("我对海鲜过敏", space_id="space.finance")
  → fragment 创建
  → 巩固为 observation: "用户对海鲜过敏"
  → 前瞻性索引生成:
    · "推荐什么晚餐？" → 需排除海鲜
    · "这家日料店合适吗？" → 不合适
    · "海边度假注意什么？" → 避开海鲜餐厅

检索阶段:
  oe_recall("推荐什么晚餐？", space_id="space.finance")
  → 向量检索: "推荐晚餐" 与 "海鲜过敏" 相似度 0.15 → 未命中
  → 前瞻性索引: "推荐什么晚餐？" 与 prospective_query 匹配，相似度 0.92
  → source_node_id 指向 observation "用户对海鲜过敏"
  → prospective_boost = 0.92 × 0.4 = 0.368
  → rank_score *= 1.368 → 排名从 #15 提升至 #1
  → 结果: "用户对海鲜过敏" 排名第一
```

**案例 2：跨域约束**

```
写入阶段:
  oe_remember("API credit_check 限速 100 次/分钟", space_id="space.finance",
              memory_type="constraint", model_domain="world")
  → 前瞻性索引:
    · "批量查征信可行吗？" → 需考虑限速
    · "为什么征信查询这么慢？" → 可能触发限速

检索阶段:
  oe_recall("批量查征信可行吗？", space_id="space.finance")
  → 向量检索: "批量查征信" 与 "API 限速" 相似度 0.25 → 未命中
  → 前瞻性索引: 匹配 "批量查征信可行吗？"，相似度 0.88
  → constraint "API credit_check 限速 100 次/分钟" 被召回
```

**案例 3：承诺追踪**

```
写入阶段:
  oe_remember("明天给用户报告", space_id="space.finance",
              memory_type="commitment", model_domain="task")
  → 前瞻性索引:
    · "今天有什么待办？" → 承诺未履行
    · "报告准备好了吗？" → 需检查承诺状态

检索阶段:
  oe_recall("今天有什么待办？", space_id="space.finance")
  → 前瞻性索引匹配 → commitment 被召回
```

***

## 优化三：信念修正形式化（AGM-lite）

### 3.1 问题分析

当前信念修正规则引擎的问题：

| 问题          | 当前实现                            | AGM 要求                                 |
| ----------- | ------------------------------- | -------------------------------------- |
| 无形式化保证      | 7 条规则 + eval 执行                 | K*2-K*6 公设 + Relevance/Core-Retainment |
| 规则冲突无验证     | detect\_rule\_conflicts 仅检测同优先级 | 需证明所有输入下结果一致                           |
| 无收缩操作       | 只有取代（supersede）和拒绝（reject）      | AGM: K\*A = (K - ¬A) + A               |
| 核心信念保护弱     | feedback\_weight > 0.9 保护       | Core-Retainment: 非矛盾直接原因必须保留           |
| 修正传播无最小改变保证 | BFS 传播，标记 pending\_review       | AGM: 最小改变原则                            |

### 3.2 设计：AGM-lite 信念修正框架

不追求完整 AGM（需要逻辑推理引擎），而是定义一组满足 AGM 公设子集的可配置规则，称为 **AGM-lite**。

```
┌─────────────────────────────────────────────────────────────────┐
│  AGM-lite 信念修正框架                                           │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │ 1. 矛盾检测      │  │ 2. 可放弃性排序  │  │ 3. 收缩操作    │  │
│  │ · 规则层检测     │  │ · discardability │  │ · 最小改变原则  │  │
│  │ · 搜索层检测     │  │   评分           │  │ · 核心信念保护  │  │
│  └────────┬────────┘  └────────┬────────┘  └───────┬────────┘  │
│           │                    │                    │            │
│           ▼                    ▼                    ▼            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 4. AGM 公设验证                                          │   │
│  │ · K*2 Success: 新信息必须被接受                           │   │
│  │ · K*3 Consistency: 修正后系统保持一致                      │   │
│  │ · K*5 Preservation: 不矛盾则旧信念全部保留                  │   │
│  │ · Relevance: 移除的信念必须与矛盾逻辑相关                    │   │
│  │ · Core-Retainment: 核心信念不可移除                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 5. 修正执行 + 传播                                        │   │
│  │ · belief_status 更新                                      │   │
│  │ · SUPERSEDES 边创建                                       │   │
│  │ · 下游影响分析 + 最小传播                                  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 可放弃性评分（Discardability Score）

参考 Kumiho 的四因子模型，定义可放弃性评分：

```python
@dataclass
class DiscardabilityScore:
    feedback_factor: float
    evidence_factor: float
    type_factor: float
    age_factor: float

    TYPE_DISCARDABILITY = {
        "fragment": 1.0,
        "self_experience": 0.9,
        "episode": 0.8,
        "observation": 0.6,
        "opinion": 0.5,
        "task_state": 0.4,
        "commitment": 0.3,
        "entity": 0.2,
        "rule": 0.15,
        "constraint": 0.1,
        "mental_model": 0.1,
    }

    @classmethod
    def compute(cls, node: CognitiveNode) -> float:
        feedback = 1.0 - node.feedback_weight
        evidence = 1.0 - min(node.proof_count / 10.0, 1.0)
        type_factor = cls.TYPE_DISCARDABILITY.get(node.memory_type, 0.5)
        age_days = (datetime.utcnow() - node.created_at).days if node.created_at else 0
        age = min(age_days / 365.0, 1.0)

        score = feedback * 0.3 + evidence * 0.3 + type_factor * 0.2 + age * 0.2
        return score
```

**可放弃性排序规则**：

- 可放弃性越高 → 越容易被收缩（移除）
- 可放弃性越低 → 越应该保留（核心信念）

### 3.4 收缩操作（Contraction）

AGM 修正操作 `K*A = (K - ¬A) + A` 的 OntologyEngine 实现：

```python
class AGMContraction:
    async def contract(self, space_id: str, new_belief: CognitiveNode,
                       contradictory_nodes: list[CognitiveNode]) -> ContractionResult:
        to_remove = []
        to_downgrade = []

        sorted_contradictory = sorted(
            contradictory_nodes,
            key=lambda n: DiscardabilityScore.compute(n),
            reverse=True,
        )

        for node in sorted_contradictory:
            if self._is_core_belief(node):
                to_downgrade.append(node)
                continue

            if self._is_minimal_removal(node, to_remove, contradictory_nodes):
                to_remove.append(node)
            else:
                to_downgrade.append(node)

        self._verify_agm_postulates(new_belief, to_remove, to_downgrade, contradictory_nodes)

        return ContractionResult(
            removed=to_remove,
            downgraded=to_downgrade,
            new_belief=new_belief,
        )

    def _is_core_belief(self, node: CognitiveNode) -> bool:
        if node.feedback_weight >= 0.9:
            return True
        if node.memory_type in ("rule", "constraint") and node.belief_status == "accepted":
            return True
        if node.proof_count >= 10 and node.confidence >= 0.95:
            return True
        return False

    def _is_minimal_removal(self, candidate: CognitiveNode,
                            already_removed: list,
                            all_contradictory: list) -> bool:
        if not already_removed:
            return True

        remaining = [n for n in all_contradictory
                     if n.id not in {r.id for r in already_removed} and n.id != candidate.id]
        if not remaining:
            return True

        return DiscardabilityScore.compute(candidate) > min(
            DiscardabilityScore.compute(n) for n in remaining
        )
```

### 3.5 AGM 公设验证

```python
class AGMPostulateVerifier:
    def verify(self, new_belief: CognitiveNode,
               removed: list[CognitiveNode],
               downgraded: list[CognitiveNode],
               contradictory: list[CognitiveNode]) -> AGMVerificationResult:
        violations = []

        if new_belief.belief_status not in ("accepted", "pending_review"):
            violations.append(AGMViolation(
                postulate="K*2_Success",
                description="New belief must be accepted or pending review",
                node_id=new_belief.id,
            ))

        for node in removed:
            if self._is_core_belief(node):
                violations.append(AGMViolation(
                    postulate="Core_Retainment",
                    description=f"Core belief {node.id} should not be removed",
                    node_id=node.id,
                ))

        for node in removed:
            if not self._is_relevant_to_contradiction(node, new_belief, contradictory):
                violations.append(AGMViolation(
                    postulate="Relevance",
                    description=f"Removed node {node.id} is not relevant to the contradiction",
                    node_id=node.id,
                ))

        non_contradictory = [n for n in contradictory if n not in removed and n not in downgraded]
        for node in non_contradictory:
            if not self._directly_contradicts(node, new_belief):
                violations.append(AGMViolation(
                    postulate="K*5_Preservation",
                    description=f"Non-contradictory node {node.id} should be preserved",
                    node_id=node.id,
                ))

        return AGMVerificationResult(
            passed=len(violations) == 0,
            violations=violations,
        )

    def _is_relevant_to_contradiction(self, node, new_belief, contradictory) -> bool:
        if node in contradictory:
            return True
        if node.entity_name and node.entity_name == new_belief.entity_name:
            return True
        if set(node.tags or []) & set(new_belief.tags or []):
            return True
        return False

    def _directly_contradicts(self, node, new_belief) -> bool:
        if node.entity_name != new_belief.entity_name:
            return False
        if node.memory_type != new_belief.memory_type:
            return False
        return True
```

### 3.6 与现有规则引擎的集成

AGM-lite 不替换现有规则引擎，而是作为**验证层**叠加在规则引擎之上：

```python
async def _apply_belief_revision_with_agm(
    self, node_id: str, contradiction: ContradictionReport,
    rules: list[BeliefRevisionRule] | None = None,
) -> dict[str, Any] | None:
    rule_result = await self._apply_belief_revision_rules(node_id, contradiction, rules)

    if rule_result is None:
        return None

    contradictory_nodes = await self._find_contradictory_nodes(node_id, contradiction)
    new_belief = await self.repository.get_cognitive_node(node_id)

    contraction = AGMContraction()
    contraction_result = await contraction.contract(
        space_id=new_belief.space_id,
        new_belief=new_belief,
        contradictory_nodes=contradictory_nodes,
    )

    verifier = AGMPostulateVerifier()
    verification = verifier.verify(
        new_belief=new_belief,
        removed=contraction_result.removed,
        downgraded=contraction_result.downgraded,
        contradictory=contradictory_nodes,
    )

    if not verification.passed:
        for violation in verification.violations:
            if violation.postulate in ("Core_Retainment", "Relevance"):
                await self._revert_rule_action(rule_result, violation.node_id)
                await self._escalate_to_manual_review(violation)

    return rule_result
```

### 3.7 一致性检查

在规则引擎初始化和规则变更时运行：

```python
class BeliefRevisionConsistencyChecker:
    def check(self, rules: list[BeliefRevisionRule]) -> ConsistencyReport:
        issues = []

        for i, r1 in enumerate(rules):
            for r2 in rules[i+1:]:
                if self._conditions_overlap(r1.condition, r2.condition):
                    if r1.priority == r2.priority and r1.action != r2.action:
                        issues.append(ConsistencyIssue(
                            type="priority_conflict",
                            rules=[r1.rule_id, r2.rule_id],
                            description=f"Same priority {r1.priority} but different actions",
                        ))

                    if r1.action.get("block_revision") and r2.action.get("supersede_old"):
                        issues.append(ConsistencyIssue(
                            type="action_contradiction",
                            rules=[r1.rule_id, r2.rule_id],
                            description="One rule blocks while another supersedes",
                        ))

        for rule in rules:
            if rule.track == "track_a" and rule.action.get("set_belief") == "rejected":
                issues.append(ConsistencyIssue(
                    type="track_violation",
                    rules=[rule.rule_id],
                    description="Track A (authoritative) should not auto-reject",
                ))

        return ConsistencyReport(issues=issues, is_consistent=len(issues) == 0)

    def _conditions_overlap(self, cond1: str, cond2: str) -> bool:
        vars1 = set(re.findall(r'\b\w+\b', cond1))
        vars2 = set(re.findall(r'\b\w+\b', cond2))
        return bool(vars1 & vars2 - {"and", "or", "not", "in", "is"})
```

### 3.8 验收案例

**案例 1：核心信念保护（Core-Retainment）**

```
场景：征信报告显示"华为风险等级=D"，用户更正为"华为风险等级=B"
  · 旧信念: entity(华为, risk_grade=D, feedback_weight=0.95, proof_count=12)
  · 新信息: observation(华为, risk_grade=B, source=user_correction)

AGM-lite 收缩:
  1. 可放弃性评分: feedback=0.05, evidence=0.0, type=0.2, age=0.5 → 0.115 (低)
  2. _is_core_belief: True (feedback_weight >= 0.9 AND proof_count >= 10)
  3. 不移除，而是 downgraded → belief_status=pending_review
  4. 新信息 accepted → belief_status=accepted
  5. AGM 验证: Core-Retainment 通过 ✓

对比当前规则引擎:
  · BR_R001 (用户更正, priority=100) → 自动取代
  · BR_R005 (反馈权重保护, priority=60) → 拒绝取代
  · 优先级 100 > 60 → 执行取代，忽略反馈保护
  · 违反 Core-Retainment ✗
```

**案例 2：最小改变原则（Relevance）**

```
场景：新观察"华为地址变更"与旧实体"华为"的地址属性矛盾
  · 矛盾节点: entity(华为, address=朝阳区), entity(华为, address=海淀区)
  · 关联节点: mental_model(华为风险摘要) 依赖 entity(华为)

AGM-lite 收缩:
  1. 可放弃性: entity(朝阳区)=0.2, entity(海淀区)=0.25
  2. 移除可放弃性更高的 entity(海淀区)
  3. mental_model 不在矛盾节点中 → 不移除（Relevance ✓）
  4. 但标记 mental_model 为 pending_review（传播）
  5. AGM 验证: Relevance 通过 ✓

对比当前规则引擎:
  · BR_R004 (时序更新) → supersede 旧地址
  · CorrectionPropagation → BFS 标记 mental_model 为 pending_review
  · 结果一致，但 AGM-lite 提供了形式化验证
```

**案例 3：一致性检查**

```
场景：新增规则 BR_R008 "低置信度自动拒绝" (confidence < 0.3 → set_belief=rejected)
  · 与 BR_R005 (feedback_weight > 0.9 → block_revision) 冲突:
    当 feedback_weight=0.95 且 confidence=0.2 时，两条规则同时匹配
  · ConsistencyChecker 检测到 action_contradiction
  · 建议: 将 BR_R008 的 track 设为 "track_b"，排除高 feedback 节点
```

***

## 验收标准与验收数据集

> **\[关键设计点]**：每个优化方向均需通过量化验收，验收数据集遵循 LoCoMo/BEAM 评估范式。

### 验收框架总览

```
┌─────────────────────────────────────────────────────────────────┐
│  验收框架                                                        │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ 单元测试      │  │ 集成评估      │  │ 对比基准              │  │
│  │ (pytest)     │  │ (CLIRunner)  │  │ (优化前 vs 优化后)    │  │
│  │ · 功能正确性  │  │ · 端到端轨迹  │  │ · 量化指标对比        │  │
│  │ · 边界条件    │  │ · 多场景覆盖  │  │ · A/B 测试           │  │
│  │ · 回归保护    │  │ · Nugget 评分 │  │ · 统计显著性          │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 通用验收原则

1. **Nugget-Based 评分**：参考 BEAM 基准，每个测试用例的答案分解为原子信息单元（nugget），独立评分 0/0.5/1.0
2. **对比基准**：所有优化必须与优化前基线对比，提供量化改进数据
3. **统计显著性**：关键指标需 3 次以上独立运行，报告均值和标准差
4. **回归保护**：优化不得降低现有 10 条 LoCoMo 评估轨迹（T1-T10）的通过率

***

### VA-1: Token 效率优化验收

#### VA-1.1 验收指标

| 指标 ID   | 指标名称      | 计算方式                                    | 验收阈值              | 当前基线        |
| ------- | --------- | --------------------------------------- | ----------------- | ----------- |
| VA-1-M1 | Token 利用率 | `实际返回 token / token_budget`             | ≥ 0.7             | \~0.3（大量浪费） |
| VA-1-M2 | Token 节省率 | `1 - (优化后 token / 优化前 token)`           | ≥ 0.5             | 0%（无压缩）     |
| VA-1-M3 | 信息完整度     | `nugget_hit_count / nugget_total_count` | ≥ 0.9             | 1.0（全返回）    |
| VA-1-M4 | 检索延迟 P95  | recall 端到端延迟                            | ≤ 优化前 × 1.2       | 基线待测        |
| VA-1-M5 | 压缩模式正确性   | minimal/standard/full 模式输出字段数           | 符合设计规格            | N/A         |
| VA-1-M6 | 过取倍率适配    | `internal_limit / target_results`       | 匹配 query\_type 预设 | 固定值         |

#### VA-1.2 验收数据集

**DS-1A: Token 预算感知数据集**

| 用例 ID    | 场景    | 记忆库规模 | token\_budget | query\_type | 期望结果                                  |
| -------- | ----- | ----- | ------------- | ----------- | ------------------------------------- |
| DS-1A-01 | 紧预算单跳 | 50 条  | 2000          | factual     | minimal 模式，≤ 40 条结果，核心信息完整            |
| DS-1A-02 | 中预算多跳 | 100 条 | 6000          | multi\_hop  | standard 模式，≤ 40 条结果，evidence\_ids 保留 |
| DS-1A-03 | 宽预算分析 | 200 条 | 16000         | analytical  | full 模式，完整字段 + 证据链                    |
| DS-1A-04 | 零预算回退 | 50 条  | None          | factual     | 默认 4000，standard 模式                   |
| DS-1A-05 | 极小预算  | 50 条  | 500           | factual     | minimal 模式，≤ 10 条结果，仅核心句              |

**DS-1B: 结构化压缩数据集**

| 用例 ID    | 场景              | 记忆类型                                             | 压缩模式     | 验证点                               |
| -------- | --------------- | ------------------------------------------------ | -------- | --------------------------------- |
| DS-1B-01 | 长文本 entity      | entity (500字)                                    | minimal  | 核心句 ≤ 100 字，id/type/confidence 保留 |
| DS-1B-02 | 带证据 observation | observation + 3 条 fragment                       | standard | evidence\_ids 保留，fragment 全文不展开   |
| DS-1B-03 | mental\_model   | mental\_model (1000字)                            | full     | 全文 + 证据链完整                        |
| DS-1B-04 | 混合类型结果          | 5 entity + 3 observation + 2 mental\_model       | auto     | 按 budget 自动选择模式                   |
| DS-1B-05 | 中文核心句提取         | "华为技术有限公司成立于1987年，总部位于深圳，是全球领先的ICT基础设施和智能终端提供商。" | minimal  | 核心句包含"华为"+"深圳"                    |

**DS-1C: 激进短路数据集**

| 用例 ID    | DispositionProfile                                | 查询       | 期望行为             | 验证点                       |
| -------- | ------------------------------------------------- | -------- | ---------------- | ------------------------- |
| DS-1C-01 | thoroughness=0.2, abstraction\_preference=0.8     | "华为风险概述" | opinion\_only 短路 | 只返回 mental\_model/opinion |
| DS-1C-02 | evidence\_demand=0.3, abstraction\_preference=0.6 | "华为风险等级" | entity\_first 短路 | entity 优先，无证据链            |
| DS-1C-03 | thoroughness=0.9                                  | "华为风险等级" | 正常漏斗             | 遍历 4 层，完整证据链              |
| DS-1C-04 | thoroughness=0.3                                  | "华为风险等级" | fast\_answer 短路  | 跳过异步验证                    |

**DS-1D: 加性融合打分数据集**

| 用例 ID    | 场景         | 语义分  | BM25 分 | 实体 boost | 期望 combined\_score | 验证点    |
| -------- | ---------- | ---- | ------ | -------- | ------------------ | ------ |
| DS-1D-01 | 纯语义        | 0.8  | 0      | 0        | 0.8                | 除数=1.0 |
| DS-1D-02 | 语义+BM25    | 0.7  | 0.6    | 0        | 0.65               | 除数=2.0 |
| DS-1D-03 | 三信号        | 0.7  | 0.6    | 0.3      | 0.64               | 除数=2.5 |
| DS-1D-04 | 语义低于阈值     | 0.05 | 0.9    | 0.5      | 排除                 | 语义前置门控 |
| DS-1D-05 | 实体 boost 高 | 0.3  | 0.2    | 0.5      | 0.4                | 除数=2.5 |

#### VA-1.3 单元测试清单

| 测试 ID   | 测试方法                                           | 覆盖点                    |
| ------- | ---------------------------------------------- | ---------------------- |
| UT-1-01 | `test_compute_internal_limit__factual`         | 过取倍率 = 4               |
| UT-1-02 | `test_compute_internal_limit__multi_hop`       | 过取倍率 = 6               |
| UT-1-03 | `test_result_compressor__minimal`              | 核心句提取 + 字段筛选           |
| UT-1-04 | `test_result_compressor__standard`             | text + evidence\_ids   |
| UT-1-05 | `test_result_compressor__full`                 | 全字段                    |
| UT-1-06 | `test_aggressive_short_circuit__opinion_only`  | thoroughness < 0.3 触发  |
| UT-1-07 | `test_aggressive_short_circuit__not_triggered` | thoroughness ≥ 0.5 不触发 |
| UT-1-08 | `test_score_and_rank_v2__semantic_gate`        | 语义低于阈值排除               |
| UT-1-09 | `test_score_and_rank_v2__adaptive_divisor`     | 自适应除数计算                |
| UT-1-10 | `test_format_result__field_selection`          | 核心字段 + metadata 嵌套     |
| UT-1-11 | `test_token_budget_trim__respects_budget`      | 总 token 不超预算           |
| UT-1-12 | `test_token_budget_trim__priority_order`       | 按 rank\_score 降序纳入     |

#### VA-1.4 集成评估轨迹

| 轨迹 ID   | 名称          | 步骤                                                          | 评分方式               |
| ------- | ----------- | ----------------------------------------------------------- | ------------------ |
| IT-1-01 | 紧预算检索       | 写入 50 条 → recall(budget=2000) → 验证 token 利用率 ≥ 0.7          | Nugget: 核心事实是否在结果中 |
| IT-1-02 | 压缩模式切换      | 写入混合类型 → recall(budget=4000) → recall(budget=12000) → 对比字段数 | Nugget: 信息完整度      |
| IT-1-03 | 激进短路对比      | 设置 Disposition → recall → 对比有无短路的 token 消耗                  | 量化: token 节省率      |
| IT-1-04 | 加性融合 vs RRF | 同一查询 → 两种融合 → 对比排序质量                                        | Nugget: 目标结果排名     |

***

### VA-2: 前瞻性索引验收

#### VA-2.1 验收指标

| 指标 ID   | 指标名称          | 计算方式                                        | 验收阈值    | 当前基线          |
| ------- | ------------- | ------------------------------------------- | ------- | ------------- |
| VA-2-M1 | 语义鸿沟召回率       | `cue-trigger 场景命中数 / cue-trigger 场景总数`      | ≥ 0.8   | \~0.2（向量检索失败） |
| VA-2-M2 | 前瞻性 boost 有效性 | `boost 后目标排名 ≤ 3 / boost 前排名 > 10`          | ≥ 0.7   | N/A           |
| VA-2-M3 | 索引生成覆盖率       | `生成前瞻性索引的记忆数 / 符合触发条件的记忆数`                  | ≥ 0.95  | 0（未实现）        |
| VA-2-M4 | 写入延迟增量        | `有前瞻性索引的 remember 延迟 - 无前瞻性索引的 remember 延迟` | ≤ 2s    | 0             |
| VA-2-M5 | 检索延迟增量        | `有前瞻性匹配的 recall 延迟 - 无前瞻性匹配的 recall 延迟`     | ≤ 100ms | 0             |
| VA-2-M6 | 存储增量比         | `prospective_queries 集合大小 / 主记忆集合大小`        | ≤ 5x    | 0             |

#### VA-2.2 验收数据集

**DS-2A: Cue-Trigger Semantic Disconnect 数据集**

> 参考 LoCoMo-Plus 基准设计，专门测试隐性约束的跨会话召回。

| 用例 ID    | 写入记忆（会话 1）        | 检索查询（会话 N）        | 语义距离    | 期望前瞻性场景            | 验证点            |
| -------- | ----------------- | ----------------- | ------- | ------------------ | -------------- |
| DS-2A-01 | "用户对海鲜过敏"         | "推荐什么晚餐？"         | 高（0.15） | "推荐晚餐→排除海鲜"        | 观察被召回          |
| DS-2A-02 | "用户偏好素食"          | "这家牛排店怎么样？"       | 高（0.12） | "牛排店→不适合素食"        | 观察被召回          |
| DS-2A-03 | "API 限速 100 次/分钟" | "批量查征信可行吗？"       | 中（0.25） | "批量查询→考虑限速"        | constraint 被召回 |
| DS-2A-04 | "明天给用户报告"         | "今天有什么待办？"        | 高（0.18） | "待办→承诺未履行"         | commitment 被召回 |
| DS-2A-05 | "用户是保守型投资者"       | "推荐高风险基金？"        | 中（0.30） | "高风险→不适合保守型"       | opinion 被召回    |
| DS-2A-06 | "华为风险等级 D 级"      | "能给华为放贷吗？"        | 高（0.20） | "放贷→需考虑风险等级"       | entity 被召回     |
| DS-2A-07 | "项目截止日期是周五"       | "今天能请假吗？"         | 高（0.15） | "请假→需考虑截止日期"       | commitment 被召回 |
| DS-2A-08 | "用户不喜欢加班"         | "周末团建安排？"         | 中（0.28） | "周末团建→可能加班"        | opinion 被召回    |
| DS-2A-09 | "数据库维护窗口凌晨2-4点"   | "现在能部署吗？"（当前凌晨3点） | 高（0.22） | "部署→需考虑维护窗口"       | constraint 被召回 |
| DS-2A-10 | "用户只使用 Python"    | "这个 Rust 库好用吗？"   | 中（0.35） | "Rust 库→用户不用 Rust" | opinion 被召回    |

**DS-2B: 前瞻性索引生成质量数据集**

| 用例 ID    | 输入记忆              | memory\_type | 期望场景数 | 验证点            |
| -------- | ----------------- | ------------ | ----- | -------------- |
| DS-2B-01 | "用户对海鲜过敏"         | observation  | 3-5   | 场景语义距离 > 原始事实  |
| DS-2B-02 | "API 限速 100 次/分钟" | constraint   | 3-5   | 至少 1 个跨域场景     |
| DS-2B-03 | "临时备注：明天开会"       | fragment     | 0     | fragment 不触发生成 |
| DS-2B-04 | "华为风险等级 D"        | entity       | 3-5   | 场景涉及决策/推荐      |
| DS-2B-05 | "用户偏好素食"          | opinion      | 3-5   | 场景涉及餐饮/社交      |

**DS-2C: 前瞻性索引与 RRF 融合交互数据集**

| 用例 ID    | 场景           | 向量检索结果 | 前瞻性匹配结果 | 期望最终排名    | 验证点            |
| -------- | ------------ | ------ | ------- | --------- | -------------- |
| DS-2C-01 | 向量命中 + 前瞻命中  | 排名 #1  | 排名 #1   | #1（双重确认）  | boost 不破坏已有高分  |
| DS-2C-02 | 向量未命中 + 前瞻命中 | 排名 #15 | 排名 #1   | #1（前瞻拯救）  | boost 提升排名     |
| DS-2C-03 | 向量命中 + 前瞻未命中 | 排名 #3  | 无       | #3（不受影响）  | 无前瞻匹配时不降权      |
| DS-2C-04 | 多条前瞻匹配同一记忆   | 排名 #8  | 3 条匹配   | #1（多场景确认） | 多 boost 叠加取最大值 |

#### VA-2.3 单元测试清单

| 测试 ID   | 测试方法                                                   | 覆盖点                              |
| ------- | ------------------------------------------------------ | -------------------------------- |
| UT-2-01 | `test_prospective_trigger__observation`                | observation 类型触发生成               |
| UT-2-02 | `test_prospective_trigger__fragment_skip`              | fragment 类型不触发                   |
| UT-2-03 | `test_prospective_trigger__high_value`                 | 高 confidence + 高 proof\_count 触发 |
| UT-2-04 | `test_generate_prospective_indexes__count`             | 生成 3-5 个场景                       |
| UT-2-05 | `test_generate_prospective_indexes__semantic_distance` | 场景与原始事实语义距离 > 阈值                 |
| UT-2-06 | `test_search_prospective_indexes__threshold`           | 相似度 < 0.5 排除                     |
| UT-2-07 | `test_search_prospective_indexes__boost_calc`          | boost = similarity × 0.4         |
| UT-2-08 | `test_prospective_boost__rank_improvement`             | rank\_score × (1 + boost) 提升排名   |
| UT-2-09 | `test_prospective_boost__no_match_no_penalty`          | 无匹配时不降权                          |
| UT-2-10 | `test_prospective_index__dedup_by_uuid5`               | 同一场景不重复创建                        |

#### VA-2.4 集成评估轨迹

| 轨迹 ID   | 名称            | 步骤                                    | 评分方式              |
| ------- | ------------- | ------------------------------------- | ----------------- |
| IT-2-01 | 语义鸿沟端到端       | 写入 10 条隐性约束 → 跨 5 轮对话 → recall 语义鸿沟查询 | Nugget: 10 个场景命中率 |
| IT-2-02 | 前瞻性 vs 无前瞻性对比 | 同一数据集 → 两种模式 recall → 对比召回率           | 量化: 召回率提升         |
| IT-2-03 | 写入延迟测量        | 100 次 remember → 平均延迟                 | 量化: 延迟增量 ≤ 2s     |
| IT-2-04 | 检索延迟测量        | 100 次 recall → P95 延迟                 | 量化: 延迟增量 ≤ 100ms  |
| IT-2-05 | 存储增量测量        | 100 条记忆 → prospective\_queries 集合大小   | 量化: 增量比 ≤ 5x      |

***

### VA-3: AGM-lite 信念修正验收

#### VA-3.1 验收指标

| 指标 ID   | 指标名称                  | 计算方式                             | 验收阈值   | 当前基线                |
| ------- | --------------------- | -------------------------------- | ------ | ------------------- |
| VA-3-M1 | Core-Retainment 通过率   | `核心信念未被移除的修正次数 / 涉及核心信念的修正总次数`   | 1.0    | \~0.8（BR\_R001 可覆盖） |
| VA-3-M2 | Relevance 通过率         | `移除信念与矛盾相关的修正次数 / 修正总次数`         | ≥ 0.95 | N/A                 |
| VA-3-M3 | K\*5 Preservation 通过率 | `不矛盾旧信念被保留的修正次数 / 涉及非矛盾信念的修正总次数` | ≥ 0.98 | N/A                 |
| VA-3-M4 | 可放弃性评分正确性             | `评分与手动计算一致的记忆数 / 测试记忆总数`         | 1.0    | N/A                 |
| VA-3-M5 | 一致性检查检出率              | `被一致性检查器检出的规则冲突 / 人工标注的规则冲突`     | ≥ 0.9  | N/A                 |
| VA-3-M6 | AGM 验证违规回退率           | `违规后成功回退的次数 / 违规总次数`             | 1.0    | 0（无验证层）             |

#### VA-3.2 验收数据集

**DS-3A: 信念修正场景数据集**

| 用例 ID    | 旧信念                                                                   | 新信息                                              | 冲突类型        | 期望 AGM-lite 行为                                     | 期望公设验证                             |
| -------- | --------------------------------------------------------------------- | ------------------------------------------------ | ----------- | -------------------------------------------------- | ---------------------------------- |
| DS-3A-01 | entity(华为, risk=D, feedback=0.95, proof=12)                           | observation(华为, risk=B, source=user\_correction) | 数值冲突 + 核心信念 | 旧信念 downgraded→pending\_review，新信息 accepted        | Core-Retainment ✓                  |
| DS-3A-02 | entity(华为, addr=朝阳)                                                   | entity(华为, addr=海淀)                              | 同属性冲突       | 可放弃性高的被移除，另一个 accepted                             | Relevance ✓                        |
| DS-3A-03 | rule(所有交易必须审核, feedback=0.98)                                         | observation(小额交易免审核, confidence=0.7)             | 规则 vs 观察    | 旧规则 downgraded→pending\_review，新观察 pending\_review | Core-Retainment ✓                  |
| DS-3A-04 | observation(华为营收50亿)                                                  | observation(华为营收65亿, source=财报)                  | 数值更新        | 旧观察 superseded，新观察 accepted                        | K\*5 ✓（非矛盾，时序更新）                   |
| DS-3A-05 | entity(华为, risk=D) + mental\_model(华为风险摘要)                            | observation(华为, risk=B)                          | 实体 + 下游模型   | entity downgraded，mental\_model 标记 pending\_review | Relevance ✓（mental\_model 不在矛盾节点中） |
| DS-3A-06 | constraint(API限速100次/分, belief=accepted)                              | constraint(API限速5000次/分, confidence=0.95)        | 同约束更新       | 旧约束 superseded，新约束 accepted                        | K*2 ✓ + K*5 ✓                      |
| DS-3A-07 | opinion(用户偏好A, feedback=0.3)                                          | opinion(用户偏好B, confidence=0.9)                   | 偏好变更        | 旧偏好移除（可放弃性高），新偏好 accepted                          | Relevance ✓                        |
| DS-3A-08 | entity(A, risk=D) + entity(B, risk=C)                                 | observation(A, risk=B)                           | 仅 A 相关      | entity(A) downgraded，entity(B) 不受影响                | K\*5 ✓（B 不矛盾）                      |
| DS-3A-09 | mental\_model(华为综合评估, proof=15)                                       | observation(华为, risk=B, confidence=0.6)          | 低置信度 vs 高证明 | mental\_model 保留，observation pending\_review       | Core-Retainment ✓                  |
| DS-3A-10 | entity(华为, risk=D, feedback=0.95) + entity(华为, risk=B, feedback=0.95) | observation(华为, risk=C, source=user\_correction) | 双核心信念冲突     | 两者都 downgraded→pending\_review，新信息 accepted        | Core-Retainment ✓（不移除）             |

**DS-3B: 可放弃性评分数据集**

| 用例 ID    | 记忆特征                                          | 期望可放弃性     | 验证点                  |
| -------- | --------------------------------------------- | ---------- | -------------------- |
| DS-3B-01 | fragment, feedback=0.1, proof=0, age=1天       | 高（\~0.87）  | 碎片 + 低反馈 + 无证据 = 易放弃 |
| DS-3B-02 | entity, feedback=0.95, proof=12, age=180天     | 低（\~0.115） | 实体 + 高反馈 + 多证据 = 难放弃 |
| DS-3B-03 | mental\_model, feedback=0.8, proof=8, age=90天 | 低（\~0.26）  | 心智模型 + 较高反馈 = 较难放弃   |
| DS-3B-04 | observation, feedback=0.5, proof=3, age=30天   | 中（\~0.50）  | 观察 + 中等 = 中等可放弃      |
| DS-3B-05 | rule, feedback=0.9, proof=5, age=365天         | 低（\~0.20）  | 规则 + 高反馈 = 难放弃       |
| DS-3B-06 | constraint, feedback=0.7, proof=2, age=7天     | 低（\~0.29）  | 约束类型因子低              |

**DS-3C: 一致性检查数据集**

| 用例 ID    | 规则集                             | 期望检出问题                                    | 验证点              |
| -------- | ------------------------------- | ----------------------------------------- | ---------------- |
| DS-3C-01 | BR\_R001 + BR\_R005             | action\_contradiction（block vs supersede） | 用户更正 vs 反馈保护冲突   |
| DS-3C-02 | 两条同优先级不同动作规则                    | priority\_conflict                        | 同优先级不可有不同动作      |
| DS-3C-03 | Track A 规则 set\_belief=rejected | track\_violation                          | 权威源不应自动拒绝        |
| DS-3C-04 | 无冲突的 7 条默认规则                    | 无问题                                       | 默认规则集应通过检查       |
| DS-3C-05 | BR\_R003 + 新增 BR\_R008（低置信度拒绝）  | action\_contradiction                     | 高置信度取代 vs 低置信度拒绝 |

**DS-3D: AGM 公设验证数据集**

| 用例 ID    | 修正场景        | 期望通过的公设                                    | 期望违反的公设           | 验证点  |
| -------- | ----------- | ------------------------------------------ | ----------------- | ---- |
| DS-3D-01 | 正常取代（非核心信念） | K*2, K*3, K\*5, Relevance, Core-Retainment | 无                 | 全部通过 |
| DS-3D-02 | 核心信念被移除     | K*2, K*5                                   | Core-Retainment   | 检出违规 |
| DS-3D-03 | 无关信念被移除     | K*2, K*3                                   | Relevance         | 检出违规 |
| DS-3D-04 | 非矛盾信念被移除    | K*2, K*3                                   | K\*5 Preservation | 检出违规 |
| DS-3D-05 | 新信息被拒绝      | 无                                          | K\*2 Success      | 检出违规 |

#### VA-3.3 单元测试清单

| 测试 ID   | 测试方法                                                   | 覆盖点                                                              |
| ------- | ------------------------------------------------------ | ---------------------------------------------------------------- |
| UT-3-01 | `test_discardability_score__fragment_low_feedback`     | 碎片 + 低反馈 = 高可放弃性                                                 |
| UT-3-02 | `test_discardability_score__entity_high_feedback`      | 实体 + 高反馈 = 低可放弃性                                                 |
| UT-3-03 | `test_discardability_score__type_factor_ordering`      | fragment > episode > observation > entity > rule > mental\_model |
| UT-3-04 | `test_is_core_belief__feedback_threshold`              | feedback\_weight ≥ 0.9 → 核心信念                                    |
| UT-3-05 | `test_is_core_belief__rule_constraint`                 | rule/constraint + accepted → 核心信念                                |
| UT-3-06 | `test_is_core_belief__high_proof_confidence`           | proof ≥ 10 + confidence ≥ 0.95 → 核心信念                            |
| UT-3-07 | `test_contraction__core_belief_downgrade`              | 核心信念降级而非移除                                                       |
| UT-3-08 | `test_contraction__minimal_removal`                    | 只移除可放弃性最高的                                                       |
| UT-3-09 | `test_contraction__empty_contradictory`                | 无矛盾节点 → 空结果                                                      |
| UT-3-10 | `test_agm_verify__k2_success`                          | 新信息必须被接受                                                         |
| UT-3-11 | `test_agm_verify__core_retainment_violation`           | 核心信念被移除 → 检出违规                                                   |
| UT-3-12 | `test_agm_verify__relevance_violation`                 | 无关信念被移除 → 检出违规                                                   |
| UT-3-13 | `test_agm_verify__k5_preservation_violation`           | 非矛盾信念被移除 → 检出违规                                                  |
| UT-3-14 | `test_consistency_checker__priority_conflict`          | 同优先级不同动作 → 检出                                                    |
| UT-3-15 | `test_consistency_checker__action_contradiction`       | block vs supersede → 检出                                          |
| UT-3-16 | `test_consistency_checker__track_violation`            | Track A auto-reject → 检出                                         |
| UT-3-17 | `test_belief_revision_with_agm__revert_on_violation`   | 违规时回退规则动作                                                        |
| UT-3-18 | `test_belief_revision_with_agm__escalate_on_violation` | 违规时升级人工审查                                                        |

#### VA-3.4 集成评估轨迹

| 轨迹 ID   | 名称         | 步骤                                   | 评分方式                           |
| ------- | ---------- | ------------------------------------ | ------------------------------ |
| IT-3-01 | 核心信念保护端到端  | 写入核心信念 → 矛盾信息 → reflect → 验证核心信念未被移除 | Nugget: 核心信念 status ≠ rejected |
| IT-3-02 | AGM 验证违规回退 | 写入 → 矛盾 → 触发规则 → AGM 验证失败 → 回退       | 量化: 回退成功率                      |
| IT-3-03 | 一致性检查端到端   | 加载默认规则 → 添加冲突规则 → 运行检查 → 验证检出        | Nugget: 冲突检出                   |
| IT-3-04 | 可放弃性排序验证   | 写入 10 条不同特征记忆 → 矛盾 → 验证移除顺序          | 量化: 排序正确率                      |
| IT-3-05 | 修正传播最小化    | 写入依赖链 → 矛盾 → 验证只传播到相关节点              | Nugget: 无关节点不受影响               |

***

### 验收数据集实施规范

#### 数据集格式

每个验收数据集以 Python 模块形式存储，遵循项目测试规范：

```
tests/
  benchmarks/
    optimization_sota/
      __init__.py
      ds_token_efficiency.py      # DS-1A, DS-1B, DS-1C, DS-1D
      ds_prospective_index.py     # DS-2A, DS-2B, DS-2C
      ds_agm_lite.py              # DS-3A, DS-3B, DS-3C, DS-3D
      conftest.py                 # 共享 fixture
  unit/
    engine/
      cognitive/
        test_token_efficiency.py  # UT-1-*
        test_prospective_index.py # UT-2-*
        test_agm_lite.py          # UT-3-*

examples/
  agent_memory/
    09_sota_optimization_eval/
      run_eval.py                 # 集成评估轨迹 IT-1-*, IT-2-*, IT-3-*
      results/                    # 评估结果 JSON
```

#### 评分标准

| 分数  | 含义   | 判定规则                         |
| --- | ---- | ---------------------------- |
| 1.0 | 完全通过 | 所有 nugget 命中，指标达到验收阈值        |
| 0.5 | 部分通过 | 核心功能正确但指标未达阈值，或部分 nugget 未命中 |
| 0.0 | 未通过  | 核心功能错误，或关键公设违反               |

#### 回归保护

优化实施后，必须重新运行现有 LoCoMo 评估（T1-T10），确保：

- 通过率不降低（当前 10/10）
- T1-T3 的 score 不降低（当前 0.5，优化后应 ≥ 0.5）

***

## 实施优先级

| 优化方向       | 优先级 | 工作量 | 依赖       | 预期收益                |
| ---------- | --- | --- | -------- | ------------------- |
| Token 效率优化 | P0  | 中   | 无        | Agent 上下文利用率提升 3-4x |
| 前瞻性索引      | P1  | 大   | LLM 调用能力 | 隐性约束召回率提升 40%+      |
| 信念修正形式化    | P1  | 中   | 现有规则引擎   | 修正逻辑一致性保证           |

## 与现有文档的关系

| 本文档章节         | 影响的现有文档                         | 修改类型                  |
| ------------- | ------------------------------- | --------------------- |
| 优化一 Layer 1-5 | memory-api.md §14               | 扩展检索管线                |
| 优化一 Layer 2   | memory-api.md §5                | 新增结果压缩                |
| 优化一 Layer 3   | memory-hierarchy.md §6          | 扩展短路策略                |
| 优化二           | memory-api.md §2 (oe\_remember) | 新增前瞻性索引生成             |
| 优化二           | memory-api.md §3 (oe\_recall)   | 新增前瞻性匹配步骤             |
| 优化二           | memory-hierarchy.md §3          | 新增 ProspectiveIndex 表 |
| 优化三           | memory-lifecycle.md §9          | 扩展信念修正规则引擎            |
| 优化三           | memory-lifecycle.md §10         | 扩展更正传播                |

## 参考文档

| 主题                                    | 文档位置                                                 |
| ------------------------------------- | ---------------------------------------------------- |
| mem0 Token-Efficient Memory Algorithm | `docs-dev/research/mem0-report/report.md`            |
| Hindsight 深度调研                        | `docs-dev/research/hindsight-deep-analysis.md`       |
| Kumiho AGM 信念修正                       | arXiv:2603.17244                                     |
| Agent 记忆设计总览                          | `docs/02-design/agent-memory/README.md`              |
| 记忆层次设计                                | `docs/02-design/agent-memory/memory-hierarchy.md`    |
| 记忆生命周期设计                              | `docs/02-design/agent-memory/memory-lifecycle.md`    |
| 认知操作 API 设计                           | `docs/02-design/agent-memory/memory-api.md`          |
| SOTA 审视报告                             | `discuss/2026-04-27-agent-memory-design-analysis.md` |

