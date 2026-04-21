# Hindsight 记忆系统深度调研报告

> 来源：https://hindsight.vectorize.io/ | 代码：~/Projects/github/GraphRAGs/hindsight
> 调研日期：2026-04-20 | 基准：LongMemEval SOTA

---

## 一、项目概述与核心洞察

### 1.1 核心定位

**Hindsight** 是 Vectorize.io 开发的 Agent 记忆系统，其核心理念区别于传统 RAG 和知识图谱：

> "Hindsight is focused on making agents that learn, not just remember."

**关键数据**：
- LongMemEval 基准 SOTA 性能（2026年1月）
- Virginia Tech 和 The Washington Post 独立复现
- Fortune 500 企业生产使用

### 1.2 三大核心操作

| 操作 | 作用 | 触发方式 |
|------|------|----------|
| **Retain** | 存储记忆，提取事实/实体/关系 | 外部调用 |
| **Recall** | 4路并行检索记忆 | 外部调用 |
| **Reflect** | 主动反思，生成新洞察 | 外部调用 |

---

## 二、记忆类型层次架构（Memory Hierarchy）

### 2.1 四层记忆类型（优先级递减）

```
┌─────────────────────────────────────────────────────────────┐
│  Mental Model    │ 用户策划的摘要 │ 最高优先级 │ reflect使用 │
├─────────────────────────────────────────────────────────────┤
│  Observation     │ 自动归纳知识   │ 中优先级   │ 证据追踪   │
├─────────────────────────────────────────────────────────────┤
│  World Fact      │ 客观世界事实   │ 低优先级   │ retain提取 │
├─────────────────────────────────────────────────────────────┤
│  Experience Fact │ Agent自身经历   │ 低优先级   │ retain提取 │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 各层详细定义

#### Mental Model（精神模型）

**定义**：用户策划的高层摘要，用于常见查询模式。

**表结构**（mental_models 表）：
- `id`: UUID
- `bank_id`: 所属记忆银行
- `name`: 模型名称
- `query`: 触发查询
- `content`: 摘要内容
- `trigger`: 刷新触发器配置
- `last_refreshed_at`: 上次刷新时间
- `tags`: 标签（用于隔离）

**刷新机制**：
- `trigger.refresh_after_consolidation=true` 时，Consolidation 后自动触发
- `compute_mental_model_is_stale()` 判断是否需要刷新

#### Observation（观察）

**定义**：从原始事实自动归纳的持久知识，带证据追踪。

**存储结构**（memory_units 表，fact_type='observation'）：
```python
{
    "id": "uuid",
    "fact_type": "observation",
    "text": "Alice works at Google",
    "proof_count": 3,                    # 证据数量
    "source_memory_ids": ["uuid1", ...], # 来源记忆
    "history": [                         # 变更历史
        {
            "previous_text": "...",
            "changed_at": "2026-04-01T...",
        }
    ],
    "occurred_start": datetime,          # MIN(来源记忆)
    "occurred_end": datetime,             # MAX(来源记忆)
    "mentioned_at": datetime,             # MAX(来源记忆)
}
```

**与 Mental Model 的区别**：
| 维度 | Observation | Mental Model |
|------|------------|--------------|
| 来源 | 自动归纳 | 用户策划 |
| 刷新 | Consolidation 自动 | 手动/触发 |
| 粒度 | 单条知识 | 主题摘要 |

#### World Fact vs Experience Fact

**区分逻辑**（fact_extraction.py:1097-1106）：
```python
raw_fact_type = llm_fact.get("fact_type")
if raw_fact_type == "assistant":
    fact_type = "experience"  # Agent 第一人称经历
elif raw_fact_type == "world":
    fact_type = "world"      # 客观世界事实
else:
    fact_type = "experience" if raw_fact_kind == "assistant" else "world"
```

**典型场景**：
- World Fact: "用户喜欢咖啡"、"Alice 在 Google 工作"
- Experience Fact: "用户问如何优化 API"、"Agent 帮用户修复了 bug"

---

## 三、TEMPR 四路并行检索机制

### 3.1 架构概览

```
Query: "去年夏天我和Alice在巴黎做了什么"

┌─────────────────────────────────────────────────────────────────┐
│                      Parallel Retrieval                          │
├──────────────┬──────────────┬──────────────┬──────────────────────┤
│  Semantic    │    BM25     │    Graph    │     Temporal         │
│  (向量相似度) │  (关键词)    │  (图扩展)   │     (时序约束)        │
├──────────────┴──────────────┴──────────────┴──────────────────────┤
│                   Reciprocal Rank Fusion                        │
│                   score(d) = Σ(1 / (k + rank(d)))              │
├─────────────────────────────────────────────────────────────────┤
│                    Cross-Encoder Reranking                      │
├─────────────────────────────────────────────────────────────────┤
│                     Token Limit Trimming                        │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Semantic 检索（向量相似度）

**实现**：`retrieval.py:retrieve_semantic_bm25_combined`

**关键设计**：
1. **Partial HNSW Index**：每个 fact_type 有独立索引
   ```sql
   CREATE INDEX idx_mu_emb_world ON memory_units 
   USING hnsw (embedding vector_cosine_ops)
   WHERE fact_type = 'world';
   ```

2. **5x Overfetch 补偿近似误差**：
   ```python
   hnsw_fetch = max(limit * 5, 100)  # retrieval.py:140
   ```

3. **ef_search=200**：连接初始化时全局设置，提高稀疏图召回率

4. **相似度阈值 0.3**：
   ```sql
   WHERE (1 - (embedding <=> $1::vector)) >= 0.3
   ```

### 3.3 BM25 检索（关键词精确匹配）

**三种模式**（config.text_search_extension）：
| 模式 | 实现 | Score 表达式 |
|------|------|-------------|
| `native` | PostgreSQL ts_rank_cd | `ts_rank_cd(search_vector, to_tsquery(...))` |
| `pg_textsearch` | pg_textsearch 扩展 | `-(text <@> to_bm25query(...))` |
| `vchord` | VectorChord bm25vector | `search_vector <&> to_bm25query(...)` |

**Query Tokenize**（retrieval.py:29-35）：
```python
def tokenize_query(query_text: str) -> list[str]:
    """Normalize query text and split into BM25 tokens."""
    return re.sub(r"[^\w\s]", " ", query_text.lower()).split()
```

### 3.4 Graph 检索（链接扩展）

**实现**：`link_expansion_retrieval.py`

**链路类型**：
- `temporal`：时序邻近
- `causes` / `caused_by`：因果关系
- `enables` / `prevents`：使能/阻止

**扩散激活算法**（retrieval.py:506）：
```python
propagated_temporal = parent_score * link_weight * causal_boost * 0.7
combined_temporal = max(neighbor_temporal_proximity, propagated_temporal)

# 因果增强
causal_boost = 2.0 if link_type in ("causes", "caused_by") else 1.5 if ... else 1.0
```

### 3.5 Temporal 检索（时序约束）

**两阶段 Entry Point 查询**（retrieval.py:313-352）：

**Phase 1 - date_ranked**：
```sql
WITH date_ranked AS MATERIALIZED (
    SELECT id, fact_type,
           ROW_NUMBER() OVER (PARTITION BY fact_type ORDER BY occurred_start DESC) AS rn
    FROM memory_units
    WHERE bank_id = $2
      AND occurred_start BETWEEN $4 AND $5  -- 时序窗口
)
```

**Phase 2 - sim_ranked**：
```sql
sim_ranked AS (
    SELECT mu.*, 1 - (mu.embedding <=> $1::vector) AS similarity
    FROM date_ranked dr
    JOIN memory_units mu ON mu.id = dr.id
    WHERE dr.rn <= 50
      AND similarity >= 0.1
)
SELECT ... WHERE sim_rn <= 10
```

**时序邻近性计算**（retrieval.py:397-401）：
```python
days_from_mid = abs((best_date - mid_date).total_seconds() / 86400)
temporal_proximity = 1.0 - min(days_from_mid / (total_days / 2), 1.0)
```

### 3.6 Reciprocal Rank Fusion（RRF）

**实现**：`fusion.py:10-77`

**公式**：
```python
def reciprocal_rank_fusion(result_lists: list[list[RetrievalResult]], k: int = 60):
    for source_idx, results in enumerate(result_lists):
        for rank, retrieval in enumerate(results, start=1):
            doc_id = retrieval.id
            rrf_scores[doc_id] += 1.0 / (k + rank)
```

**k=60 的选择**：平衡排名差异，k 越大，不同排名的贡献差异越小。

**RRF 结果结构**：
```python
@dataclass
class MergedCandidate:
    retrieval: RetrievalResult
    rrf_score: float
    rrf_rank: int
    source_ranks: dict[str, int]  # {"semantic_rank": 1, "bm25_rank": 3, ...}
```

---

## 四、实体解析与消歧机制

### 4.1 EntityResolver 架构

**实现**：`entity_resolver.py:61-67`

```python
class EntityResolver:
    def __init__(self, pool: asyncpg.Pool, entity_lookup: str = "full"):
        self.pool = pool
        self.entity_lookup = entity_lookup  # "full" or "trigram"
        self._pending_stats: dict[int, list[_EntityStat]] = {}
        self._pending_cooccurrences: dict[int, list[_CooccurrencePair]] = {}
```

**双策略切换**：
- `full`：加载所有 bank 实体到内存（O(N)，适合小规模）
- `trigram`：用 pg_trgm 索引仅获取相似候选（O(1)，适合大规模）

### 4.2 Full 策略

**流程**（entity_resolver.py:236-305）：
```python
async def _resolve_entities_batch_full(self, conn, bank_id, entities_data, unit_event_date):
    # 1. 加载所有 bank 实体
    all_entities = await conn.fetch(
        "SELECT canonical_name, id, metadata, last_seen, mention_count "
        "FROM entities WHERE bank_id = $1", bank_id
    )

    # 2. 加载所有共现关系
    all_cooccurrences = await conn.fetch(
        "SELECT entity_id_1, entity_id_2, cooccurrence_count "
        "FROM entity_cooccurrences WHERE ..."
    )

    # 3. 构建共现映射
    cooccurrence_map: dict[str, set[str]] = {...}

    # 4. 批量匹配
    for entity_text in entity_texts:
        matching = [e for e in all_entities if ...]
        all_candidates[entity_text] = matching
```

### 4.3 Trigram 策略

**实现**（entity_resolver.py:307-385）：

```python
await conn.execute("SET pg_trgm.similarity_threshold = 0.15")
rows = await conn.fetch(
    """
    SELECT DISTINCT ON (e.id)
        e.id, e.canonical_name, e.metadata, e.last_seen, e.mention_count,
        q.query_text
    FROM unnest($2::text[]) AS q(query_text)
    JOIN entities e ON (
        e.bank_id = $1
        AND LOWER(e.canonical_name) % LOWER(q.query_text)  -- trigram 相似
    )
    """, bank_id, entity_texts
)
```

**为什么 threshold=0.15**：
- 默认 0.3 太严格，可能漏掉 substring 关系
- 降低到 0.15 在保持索引性能的同时捕获更多匹配

### 4.4 消歧评分算法

**评分公式**（entity_resolver.py:422-450）：

```python
score = 0.0

# 1. 名称相似度 (权重 0.5)
name_similarity = SequenceMatcher(None, entity_text.lower(), canonical_name.lower()).ratio()
score += name_similarity * 0.5

# 2. 共现实体重叠 (权重 0.3)
if nearby_entity_set:
    co_entities = cooccurrence_map.get(candidate_id, set())
    overlap = len(nearby_entity_set & co_entities)
    co_entity_score = overlap / len(nearby_entity_set)
    score += co_entity_score * 0.3

# 3. 时序邻近性 (权重 0.2)
if last_seen and entity_event_date:
    days_diff = abs((event_date_utc - last_seen_utc).total_seconds() / 86400)
    if days_diff < 7:
        temporal_score = max(0, 1.0 - (days_diff / 7))
        score += temporal_score * 0.2
```

**阈值 0.6**：超过则复用现有实体，否则创建新实体

### 4.5 并发安全设计

**Task-key 隔离**（entity_resolver.py:84-87）：
```python
def _task_key(self) -> int:
    """Return a unique key for the current asyncio task."""
    task = asyncio.current_task()
    return id(task) if task is not None else 0
```

**Post-txn 刷新模式**（entity_resolver.py:102-163）：
```python
async def flush_pending_stats(self) -> None:
    # 不在事务内更新，而是在事务提交后批量更新
    # 避免长事务锁竞争
    key = self._task_key()
    stats = self._pending_stats.pop(key, [])

    # 聚合统计
    agg: dict[str, _EntityStatAgg] = defaultdict(_EntityStatAgg)
    for s in stats:
        agg[s.entity_id].count += 1
        agg[s.entity_id].max_date = max(agg[s.entity_id].max_date, s.event_date)

    # 批量更新
    await conn.executemany(
        "UPDATE entities SET mention_count = mention_count + $2, ..."
    )
```

---

## 五、事实提取管道（Fact Extraction）

### 5.1 四种提取模式

**实现**：`fact_extraction.py`

| 模式 | 说明 | 使用场景 |
|------|------|----------|
| `concise` | 选择性提取，仅保留长期有价值信息 | **默认模式** |
| `verbose` | 极度详细提取，保留所有细节 | 复杂对话分析 |
| `verbatim` | 保留原文，仅提取元数据 | 精确原文检索 |
| `chunks` | 无 LLM，直接分块存储 | 高速批量摄入 |

### 5.2 多维事实模型

**核心模型**（fact_extraction.py:80-105）：
```python
class Fact(BaseModel):
    fact: str  # "what | when | where | who | why"
    fact_type: Literal["world", "experience"]

    occurred_start: str | None
    occurred_end: str | None
    where: str | None

    entities: list[Entity] | None
    causal_relations: list[CausalRelation] | None
```

**事实文本格式**：
```
what | when | where | who | why
  ↓     ↓     ↓     ↓     ↓
[核心事实] | [时间] | [地点] | [参与者] | [原因]
```

### 5.3 选择性提取原则

**CONCISE_GUIDELINES**（fact_extraction.py:528-548）：

**应该提取**：
- 个人info：名字、关系、角色、背景
- 偏好：喜欢/不喜欢、习惯、兴趣
- 重要事件：里程碑、决策、成就
- 计划/目标：未来意图、截止日期
- 专业知识：技能、知识、证书
- 重要上下文：项目、问题、约束
- 感官/情感细节：感受、感知

**不应提取**：
- 通用问候：无实质内容的寒暄
- 纯填充词：thanks, sounds good, ok
- 过程性话语：let me check, one moment
- 重复信息：已说过的内容

### 5.4 因果关系提取

**模型**（fact_extraction.py:106-142）：
```python
class CausalRelation(BaseModel):
    target_fact_index: int  # 指向同批次内更早的事实
    relation_type: Literal["caused_by"]
    strength: float  # 0.0-1.0，默认 1.0
```

**约束**：
- 仅能引用同批次内更早的事实（target_index < current_index）
- 每个事实最多 2 个因果关系
- 防止 LLM 幻觉无效索引

**示例**：
```
Input: "用户失业了，因此付不起房租，最终搬到了更小的公寓"

Fact 0: 用户失业
Fact 1: 用户付不起房租 (caused_by → Fact 0)
Fact 2: 用户搬到更小的公寓 (caused_by → Fact 1)
```

### 5.5 共指消解

**Prompt 指导**（fact_extraction.py:490-496）：
```
Link generic references to names when both appear:
- "my roommate" + "Emily" → use "Emily (user's roommate)"
- "the manager" + "Sarah" → use "Sarah (the manager)"
```

### 5.6 Chunk 处理策略

**分块逻辑**（fact_extraction.py:376-462）：

```python
def chunk_text(text: str, max_chars: int) -> list[str]:
    # 小文本直接返回
    if len(text) <= max_chars:
        return [text]

    # 尝试解析为对话 JSON
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return _chunk_conversation(parsed, max_chars)
    except:
        pass

    # 回退到句子级分块
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_chars,
        chunk_overlap=0,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]
    )
    return splitter.split_text(text)
```

**自动 Split 机制**（fact_extraction.py:1308-1427）：
```python
async def _extract_facts_with_auto_split(chunk, ...):
    try:
        return await _extract_facts_from_chunk(chunk, ...)
    except OutputTooLongError:
        # 自动折半重试
        mid_point = len(chunk) // 2
        first_half = chunk[:best_split]
        second_half = chunk[best_split:]
        # 递归处理两半
```

### 5.7 时序推理

**相对时间映射**（fact_extraction.py:29-65）：
```python
temporal_patterns = {
    r"\blast night\b": -1,
    r"\byesterday\b": -1,
    r"\btoday\b": 0,
    r"\btomorrow\b": 1,
    r"\blast week\b": -7,
    r"\bnext week\b": 7,
    r"\blast month\b": -30,
    r"\bnext month\b": 30,
}

for pattern, offset_days in temporal_patterns.items():
    if re.search(pattern, fact_lower):
        target_date = event_date + timedelta(days=offset_days)
        return target_date.isoformat()
```

---

## 六、Consolidation 机制

### 6.1 ConsolidationJob 流程

**主循环**（consolidation/consolidator.py:222-630）：

```python
async def run_consolidation_job(memory_engine, bank_id, request_context):
    # 1. 获取未归类的记忆
    memories = await conn.fetch("""
        SELECT * FROM memory_units
        WHERE bank_id = $1
          AND consolidated_at IS NULL
          AND fact_type IN ('experience', 'world')
        ORDER BY created_at ASC
        LIMIT $2
    """)

    # 2. 按标签分组
    tag_groups: dict[tuple[str, ...], list[dict]] = {}
    for m in memories:
        tag_key = tuple(sorted(m.get("tags") or []))
        tag_groups.setdefault(tag_key, []).append(m)

    # 3. 每组调用 LLM 判断 create/update/delete
    for llm_batch in llm_batches:
        result = await _consolidate_batch_with_llm(llm_config, memories, observations)
        await _execute_actions(result)

    # 4. 触发 Mental Model 刷新
    await _trigger_mental_model_refreshes(memory_engine, bank_id, consolidated_tags)
```

### 6.2 LLM 判断逻辑

**返回结构**（consolidation/consolidator.py:98-101）：
```python
class _ConsolidationBatchResponse(BaseModel):
    creates: list[_CreateAction] = []   # 创建新 Observation
    updates: list[_UpdateAction] = []   # 更新现有 Observation
    deletes: list[_DeleteAction] = []   # 删除过时 Observation
```

**Prompt 示例**（consolidation/prompts.py）：
```
Given facts about a user and existing observations:
- If facts add new knowledge → CREATE
- If facts refine/extend existing → UPDATE
- If facts contradict existing → DELETE old, CREATE new
```

### 6.3 标签隔离机制

**安全边界**：不同标签的记忆绝不混合处理

```python
# 错误示例：跨标签混合
Observation A(tags=["user:alice"]) ← 来源记忆1(tags=["user:alice"])
Observation B(tags=["project:alpha"]) ← 来源记忆2(tags=["project:alpha"])
# 两者永远不会合并，因为标签不同

# 正确示例：同标签内合并
Observation A(tags=["user:alice"]) ← 来源记忆1(tags=["user:alice"])
                              ← 来源记忆2(tags=["user:alice"])  # 同标签，可以合并
```

**observation_scopes 模式**（consolidation/consolidator.py:396-415）：
```python
if _obs_parsed == "per_tag":
    # 每标签独立 observation
    obs_tags_list = [[tag] for tag in memory_tags]
elif _obs_parsed == "all_combinations":
    # 所有标签组合
    obs_tags_list = [list(combo) for r in range(1, len(tags)+1) for combo in combinations(tags, r)]
elif _obs_parsed == "combined" or _obs_parsed is None:
    # 合并为一个 observation
    obs_tags_list = None
```

### 6.4 时序聚合规则

**聚合公式**（consolidation/consolidator.py:125-147）：
```python
def _aggregate_source_fields(source_mems, tags):
    return _SourceAggregation(
        event_date=_min_date(m.get("event_date") for m in source_mems),
        occurred_start=_min_date(m.get("occurred_start") for m in source_mems),
        occurred_end=_max_date(m.get("occurred_end") for m in source_mems),
        mentioned_at=_max_date(m.get("mentioned_at") for m in source_mems),
        tags=tags or source_mems[0].get("tags", [])
    )
```

**语义**：
- `occurred_start = MIN`：最早发生时间
- `occurred_end = MAX`：最晚结束时间
- `mentioned_at = MAX`：最近提及时间

### 6.5 History 追踪

**History 条目结构**（consolidation/consolidator.py:966-974）：
```python
history_entry = {
    "previous_text": "Alice works at Google",
    "previous_tags": ["company:google"],
    "previous_occurred_start": datetime(2025, 1, 1),
    "previous_occurred_end": datetime(2025, 1, 1),
    "previous_mentioned_at": datetime(2026, 3, 1),
    "changed_at": datetime(2026, 4, 1).isoformat(),
    "new_source_memory_ids": ["uuid3", "uuid4"]
}
```

### 6.6 自适应分批

**折半重试机制**（consolidation/consolidator.py:476-483）：
```python
if sub_llm_failed and len(sub_batch) > 1:
    # 折半重试
    mid = len(sub_batch) // 2
    pending[0:0] = [sub_batch[:mid], sub_batch[mid:]]
elif sub_llm_failed:
    # 单条仍失败，标记为永久失败
    failed_ids.append(sub_batch[0]["id"])
```

### 6.7 证据链追踪

**Source Memory 过滤**（consolidation/consolidator.py:45-70）：
```python
async def _filter_live_source_memories(conn, bank_id, source_memory_ids):
    """返回仍然存在的 source memory id（处理并发删除）"""
    rows = await conn.fetch(
        """
        SELECT id FROM memory_units
        WHERE id = ANY($1::uuid[]) AND bank_id = $2
        FOR SHARE  -- 防止并发删除导致孤儿
        """, source_memory_ids, bank_id
    )
    live = {row["id"] for row in rows}
    return [mid for mid in source_memory_ids if mid in live]
```

---

## 七、Reflect Agent 机制

### 7.1 Agent 架构

**实现**：`reflect/agent.py:304-969`

```python
async def run_reflect_agent(
    llm_config, bank_id, query, bank_profile,
    search_mental_models_fn, search_observations_fn,
    recall_fn, expand_fn,
    max_iterations=10
):
    # 工具列表
    tools = get_reflect_tools(
        include_mental_models=True,
        include_observations=True,
        include_recall=True
    )

    for iteration in range(max_iterations):
        if is_last_iteration:
            # 强制返回最终回答
            return await _force_final_response(query, context_history)

        # 强制按顺序检索
        if iteration < len(forced_sequence):
            tool_choice = forced_sequence[iteration]
        else:
            tool_choice = "auto"

        result = await llm_config.call_with_tools(messages, tools, tool_choice)
```

### 7.2 分层工具调用

**强制检索序列**（reflect/agent.py:552-563）：
```python
forced_sequence = []
if has_mental_models:
    forced_sequence.append("search_mental_models")  # 第 1 次迭代
if include_observations:
    forced_sequence.append("search_observations")     # 第 2 次迭代
if include_recall:
    forced_sequence.append("recall")                 # 第 3 次迭代

if iteration < len(forced_sequence):
    tool_choice = {"type": "function", "function": {"name": forced_sequence[iteration]}}
else:
    tool_choice = "auto"  # 之后允许 LLM 自主选择
```

**可用工具**：
| 工具 | 功能 | 返回 |
|------|------|------|
| `search_mental_models` | 搜索高层摘要 | mental_models |
| `search_observations` | 搜索归纳知识 | observations |
| `recall` | 搜索原始事实 | memories |
| `expand` | 扩展记忆邻域 | expanded memories |
| `done` | 完成推理 | final answer |

### 7.3 Disposition 系统

**Bank 配置**（reflect/prompts.py）：
```python
# Disposition 特质
bank_profile = {
    "name": "Alice's AI Assistant",
    "mission": "Help Alice manage her work and personal life",
    "disposition": {
        "skepticism": 3,    # 1-5 量表
        "empathy": 4,
        "literalism": 2
    }
}
```

**影响方式**：Disposition 注入到 system prompt，影响 LLM 的推理风格和回答倾向。

### 7.4 Directives 指令系统

**硬规则注入**（reflect/agent.py:356-357）：
```python
directive_rules = _extract_directive_rules(directives)
tools = get_reflect_tools(directive_rules=directive_rules, ...)
```

**Prompt 影响**：
```
You must NEVER violate these rules:
- Never share user passwords
- Never reveal internal system details
- Always confirm destructive actions
```

### 7.5 上下文溢出保护

**Token 预算检查**（reflect/agent.py:490-544）：
```python
estimated_tokens = _count_messages_tokens(messages)
if estimated_tokens >= max_context_tokens:
    # 强制进入最终回答
    return await _force_final_response(query, context_history)
```

### 7.6 幻觉防护

**可用 ID 追踪**（reflect/agent.py:389-392）：
```python
available_memory_ids: set[str] = set()
available_mental_model_ids: set[str] = set()
available_observation_ids: set[str] = set()

# 工具返回结果时更新
if normalized_tool_name == "search_observations":
    for obs in output["observations"]:
        available_observation_ids.add(obs["id"])

# done() 时验证
used_memory_ids = [mid for mid in args.get("memory_ids", [])
                    if mid in available_memory_ids]
```

---

## 八、对 Agent 知识引擎的启发与建议

### 8.1 记忆层次设计

**当前差距**：
- OntologyEngine 目前主要是三元组存储 + 概念层
- 缺少自动归纳层（Observation）

**建议设计**：

```
Layer 1: Raw Triple（事实层）
  - subject, predicate, object
  - 快速写入，高精度

Layer 2: Observation（归纳层）[NEW]
  - proof_count: 证据数量
  - source_triple_ids: 来源三元组
  - history: 变更历史
  - 自动从 Triple 归纳

Layer 3: Mental Model（高层摘要）[NEW]
  - 用户策划/主动反思生成
  - 用于常见查询模式
```

### 8.2 TEMPR 检索实现

**当前差距**：
- 主要依赖向量相似度
- 缺少 BM25、时序、图遍历

**建议实现**：

```python
class TEMPRRetrieval:
    async def retrieve(self, query, bank_id, fact_types):
        # 1. 并行四路检索
        semantic_task = self.semantic_search(query, bank_id, fact_types)
        bm25_task = self.bm25_search(query, bank_id, fact_types)
        graph_task = self.graph_search(query, bank_id, fact_types)
        temporal_task = self.temporal_search(query, bank_id, fact_types)

        semantic, bm25, graph, temporal = await asyncio.gather(
            semantic_task, bm25_task, graph_task, temporal_task
        )

        # 2. RRF 合并
        merged = reciprocal_rank_fusion([semantic, bm25, graph, temporal], k=60)

        # 3. Cross-encoder 重排
        reranked = await self.cross_encoder.rerank(query, merged[:20])

        return reranked
```

### 8.3 实体消歧机制

**建议实现**：

```python
class EntityResolver:
    async def resolve(self, bank_id, entity_texts, context):
        scores = {}
        for entity_text in entity_texts:
            candidates = await self._get_candidates(bank_id, entity_text)
            best_score = 0
            best_id = None

            for candidate in candidates:
                score = (
                    self._name_similarity(entity_text, candidate.name) * 0.5 +
                    self._cooccurrence_overlap(entity_text, candidate, context) * 0.3 +
                    self._temporal_proximity(entity_text, candidate) * 0.2
                )
                if score > best_score and score > 0.6:
                    best_score = score
                    best_id = candidate.id

            if best_id:
                scores[entity_text] = best_id
            else:
                # 创建新实体
                scores[entity_text] = await self._create_entity(bank_id, entity_text)

        return scores
```

### 8.4 Consolidation 机制

**建议实现**：

```python
class ConsolidationEngine:
    async def run(self, bank_id):
        # 1. 获取未归类三元组
        unconsolidated = await self.db.fetch_unconsolidated(bank_id)

        # 2. 按标签分组
        groups = self._group_by_tags(unconsolidated)

        # 3. 每组调用 LLM
        for group in groups:
            facts = [t.to_fact_text() for t in group]
            observations = await self._find_related_observations(facts)

            result = await self.llm.consolidate(facts, observations)

            # 4. 执行 create/update/delete
            await self._execute_actions(result)

        # 5. 触发 Mental Model 刷新
        await self._trigger_refresh(bank_id)
```

### 8.5 Reflect 能力

**建议实现**：

```python
class ReflectAgent:
    def __init__(self, llm, memory_engine):
        self.llm = llm
        self.memory = memory_engine
        self.tools = [
            search_mental_models,
            search_observations,
            recall,
            expand,
            done
        ]

    async def reflect(self, query, bank_id, context=None):
        messages = [system_prompt, user_prompt(query)]

        for i in range(10):
            response = await self.llm.call_with_tools(messages, self.tools)

            if not response.tool_calls:
                return response.content

            for tool_call in response.tool_calls:
                result = await self._execute_tool(tool_call)
                messages.append(tool_result(tool_call, result))

        return self._force_final_response(messages)
```

---

## 九、总结对比

| 维度 | Hindsight | OntologyEngine (当前) | 建议优先级 |
|------|-----------|----------------------|----------|
| 记忆层次 | 4层 (Mental/Obs/Wld/Exp) | 2层 (Triple/Concept) | **高** - 增加 Observation 层 |
| 检索策略 | TEMPR 4路并行 | 向量 + 图遍历 | **高** - 增加 BM25/时序 |
| 实体消歧 | trigram+共现+时序 | 无 | **中** - 增加实体解析 |
| 归纳机制 | LLM Consolidation | 无 | **高** - 增加自动 Observation |
| 反思机制 | Agentic Tool Calling | 无 | **中** - 增加 Reflect |
| 证据追踪 | proof_count + history | 无 | **高** - 增加来源追踪 |

---

## 十、核心参考代码路径

| 模块 | 代码路径 |
|------|---------|
| Memory Engine | `hindsight-api-slim/hindsight_api/engine/memory_engine.py` |
| Retrieval | `hindsight-api-slim/hindsight_api/engine/search/retrieval.py` |
| Fusion (RRF) | `hindsight-api-slim/hindsight_api/engine/search/fusion.py` |
| Entity Resolver | `hindsight-api-slim/hindsight_api/engine/entity_resolver.py` |
| Fact Extraction | `hindsight-api-slim/hindsight_api/engine/retain/fact_extraction.py` |
| Consolidation | `hindsight-api-slim/hindsight_api/engine/consolidation/consolidator.py` |
| Reflect Agent | `hindsight-api-slim/hindsight_api/engine/reflect/agent.py` |
