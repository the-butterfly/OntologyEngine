# 记忆生命周期设计

> **status**: draft | **phase**: phase2 | **source_of_truth**: `docs/01-overview/09-agent-memory.md` | **last_verified**: 2026-04-25

---

## 目的

定义 OntologyEngine Agent 记忆系统的三大认知操作——巩固（Consolidation）、遗忘（Forgetting）、反思（Reflection）的详细设计，以及实体消歧和记忆调度机制。

## 核心概念

在双层+类型标签架构下，记忆生命周期的核心是 **memory_type 的升级与降级**：

```
fragment → observation → entity → mental_model
   ↑           ↑           ↑          ↑
 原始碎片    自动归纳    Schema对齐   主题摘要

episode → procedure
   ↑         ↑
 经验事件   操作模式
```

- **巩固 = 类型升级**（fragment → observation → entity → mental_model）
- **遗忘 = 类型降级或衰减**（mental_model → entity → observation → archived → deleted）
- **反思 = 按类型权重递减检索 + 洞察生成 + 触发巩固和遗忘**

---

## 1. 巩固（Consolidation）

### 1.1 概念

将 fragment 类型记忆自动归纳为 observation 类型，或将 observation 升级为 entity 类型。

### 1.2 触发方式

| 触发方式 | 条件 | 优先级 |
|---------|------|--------|
| 阈值触发 | 未巩固碎片数 > `consolidation_threshold`（默认 50） | 高 |
| 定时触发 | 后台定期执行（默认每 6 小时） | 中 |
| 事件触发 | Ingestion 完成后，如果新增碎片 > 20 | 高 |
| Reflect 触发 | `oe_reflect` 内部自动触发 | 高 |
| 手动触发 | 高级用户调用 `oe_consolidate` | 低 |

### 1.3 ConsolidationJob 流程

```python
async def run_consolidation_job(memory_engine, space_id, request_context):
    unconsolidated = await fetch_unconsolidated_fragments(space_id, batch_size)

    tag_groups = group_by_tags(unconsolidated)

    for tag_key, fragments in tag_groups.items():
        existing_observations = await find_related_memory_units(
            space_id, memory_type="observation", tags=tag_key
        )

        result = await consolidate_batch_with_llm(
            llm_config, fragments, existing_observations
        )

        await execute_consolidation_actions(result, space_id)

    await trigger_mental_model_refreshes(space_id, consolidated_tags)
```

### 1.4 LLM 判断逻辑

```yaml
ConsolidationBatchResponse:
  creates: [CreateAction]         # 创建新 observation
  updates: [UpdateAction]         # 更新现有 observation
  deletes: [DeleteAction]         # 删除过时 observation
  upgrades: [UpgradeAction]       # observation 升级为 entity [NEW]
```

**Prompt 逻辑**：

```
Given fragments and existing observations:
- If fragments add new knowledge → CREATE new MemoryUnit(type=observation)
- If fragments refine existing observation → UPDATE
- If fragments contradict existing observation → DELETE old, CREATE new
- If fragments are redundant → SKIP (mark as consolidated)
- If observation matches Schema entity pattern → UPGRADE to entity type
```

### 1.5 标签隔离

不同标签的记忆绝不混合处理：

```
observation(tags=["domain:risk"]) ← fragment(tags=["domain:risk"])
observation(tags=["domain:supply"]) ← fragment(tags=["domain:supply"])
# 两者永远不会合并
```

### 1.6 自适应分批

```python
async def consolidate_with_auto_split(batch, llm_config, **kwargs):
    try:
        return await consolidate_batch(batch, llm_config, **kwargs)
    except OutputTooLongError:
        mid = len(batch) // 2
        await consolidate_with_auto_split(batch[:mid], llm_config, **kwargs)
        await consolidate_with_auto_split(batch[mid:], llm_config, **kwargs)
```

### 1.7 类型升级操作

```python
async def upgrade_memory_type(unit_id, new_type, additional_attrs=None):
    unit = await get_memory_unit(unit_id)
    old_type = unit.memory_type

    unit.memory_type = new_type
    unit.attributes.update(additional_attrs or {})
    unit.consolidated_at = datetime.utcnow()

    await update_memory_unit(unit)
    await create_type_edge(
        from_id=unit_id,
        edge_type=get_upgrade_edge(old_type, new_type)
    )
```

---

## 2. 遗忘（Forgetting）

### 2.1 概念

基于记忆强度和价值的选择性衰减，不分 memory_type 统一执行。

### 2.2 记忆强度模型

```python
class MemoryStrength:
    access_count: int
    last_accessed_at: datetime
    proof_count: int
    feedback_weight: float

    @property
    def strength(self) -> float:
        days_since_access = (now - self.last_accessed_at).days
        recency = math.exp(-0.1 * days_since_access)
        evidence = min(self.proof_count / 10.0, 1.0)
        value = (recency * 0.3
                 + evidence * 0.3
                 + self.feedback_weight * 0.2
                 + self.access_frequency * 0.2)
        return value
```

### 2.3 Ebbinghaus 衰减

```python
def forgetting_rate(memory_value: float) -> float:
    if memory_value >= 0.8:
        return 0.1
    elif memory_value >= 0.5:
        return 0.4
    else:
        return 0.85

def decay_strength(current_strength: float, days_elapsed: int, value: float) -> float:
    lam = forgetting_rate(value)
    return current_strength * math.exp(-lam * days_elapsed)
```

### 2.4 遗忘策略

| 策略 | 触发条件 | 动作 |
|------|---------|------|
| 软衰减 | strength < 0.3 | 降低检索权重，不删除 |
| 类型降级 | strength < 0.2 | mental_model → entity → observation → archived |
| 归档 | strength < 0.1 | 移至归档存储，不参与常规检索 |
| 硬删除 | strength < 0.01 且 proof_count == 0 | 永久删除 |
| 保护 | feedback_weight >= 0.9 | 永不遗忘 |

### 2.5 与版本限制策略的协同

[temporal-modeling.md](../schema/temporal-modeling.md) 的版本限制策略（单实体最大 100 版本）是**容量管理**，遗忘机制是**认知合理性**。两者协同：

- 版本限制先执行（硬约束）
- 遗忘机制后执行（软衰减）
- 被版本限制淘汰的版本如果 strength > 0.3，先归档再删除

---

## 3. 反思（Reflection）

### 3.1 概念

Agent 主动审视已有知识，发现矛盾，生成新洞察，自动触发巩固和遗忘。

### 3.2 ReflectAgent 架构

```python
class ReflectAgent:
    def __init__(self, llm_config, memory_engine):
        self.llm = llm_config
        self.memory = memory_engine
        self.tools = [recall, expand, done]

    async def reflect(self, query, space_id, focus_types=None, max_iterations=10):
        messages = self._build_messages(query, space_id)

        type_priority = focus_types or [
            "mental_model", "entity", "observation", "fragment"
        ]

        for iteration, memory_type in enumerate(type_priority):
            if iteration >= max_iterations:
                break

            results = await self.memory.recall(
                query, space_id, memory_type=memory_type
            )
            messages.append(tool_result(memory_type, results))

        analysis = await self.llm.call(messages)

        actions = await self._execute_reflection_actions(
            analysis, space_id
        )

        return ReflectResult(
            insights=actions.insights,
            contradictions=actions.contradictions,
            consolidation=actions.consolidation,
            forgetting=actions.forgetting,
        )
```

### 3.3 反思输出与后续动作

| 输出类型 | 说明 | 后续动作 |
|---------|------|---------|
| 新洞察 | 从已有知识中发现的新结论 | 创建 MemoryUnit(type=observation) 或升级为 mental_model |
| 矛盾发现 | 发现已有知识间的矛盾 | 生成 contradiction_report |
| Mental Model 更新 | 更新高层摘要 | 标记 is_stale，触发刷新 |
| 程序性建议 | 基于经验提出的操作建议 | 创建 MemoryUnit(type=procedure) |
| 低价值记忆 | strength 过低的记忆 | 触发遗忘衰减 |
| 未巩固碎片 | 大量未归纳的碎片 | 触发巩固 |

---

## 4. 实体消歧

### 4.1 三级消歧策略

| 级别 | 方法 | 场景 | 精度 | 性能 |
|------|------|------|------|------|
| L1 | identity_fields + UUID5 | 结构化数据导入 | 确定性 | O(1) |
| L2 | trigram + 共现 + 时序 | 非结构化提取 | 高 | O(N) 或 O(1) |
| L3 | LLM 辅助判断 | 跨域对齐、高不确定性 | 中 | O(tokens) |

### 4.2 L2 模糊匹配

```python
class EntityResolver:
    def __init__(self, storage, strategy="auto"):
        self.storage = storage
        self.strategy = strategy  # "full" | "trigram" | "auto"

    async def resolve(self, space_id, entity_texts, context):
        if self.strategy == "full" or (
            self.strategy == "auto" and await self._entity_count(space_id) < 10000
        ):
            return await self._resolve_full(space_id, entity_texts, context)
        else:
            return await self._resolve_trigram(space_id, entity_texts, context)
```

### 4.3 消歧评分

```python
def disambiguation_score(entity_text, candidate, context):
    name_sim = SequenceMatcher(
        None, entity_text.lower(), candidate.name.lower()
    ).ratio()
    score = name_sim * 0.5

    if context.nearby_entities:
        co_entities = get_cooccurrences(candidate.id)
        overlap = len(context.nearby_entities & co_entities)
        co_score = overlap / len(context.nearby_entities)
        score += co_score * 0.3

    if candidate.last_seen and context.event_date:
        days_diff = abs((context.event_date - candidate.last_seen).days)
        if days_diff < 7:
            temporal_score = max(0, 1.0 - days_diff / 7)
            score += temporal_score * 0.2

    return score
```

### 4.4 合并策略

```python
async def merge_entities(primary_id, secondary_id, space_id):
    primary = await get_entity(primary_id)
    secondary = await get_entity(secondary_id)
    merged_attrs = {**secondary.attributes, **primary.attributes}

    await redirect_edges(secondary_id, primary_id)
    await redirect_mutual_index_edges(secondary_id, primary_id)
    await update_vector_index(primary_id, merged_attrs)
    await mark_as_merged(secondary_id, primary_id)
    await record_merge_history(primary_id, secondary_id)
```

---

## 5. 时序邻近性评分

### 5.1 当前问题

当前时序检索是布尔过滤（valid_from <= as_of AND valid_to > as_of），无法区分"刚好在窗口内"和"完美匹配查询时间点"。

### 5.2 连续评分函数

```python
def temporal_proximity(query_time, entity_time, window_days):
    if query_time is None or entity_time is None:
        return 0.5

    half_window = window_days / 2
    days_from_mid = abs((query_time - entity_time).total_seconds() / 86400)

    proximity = 1.0 - min(days_from_mid / half_window, 1.0)
    return proximity
```

### 5.3 集成到检索

```python
temporal_score = temporal_proximity(query_time, entity.occurred_at, window_days=365)
final_score = rrf_score * type_weight + temporal_boost * temporal_score
```

---

## 6. Cross-Encoder 重排序

### 6.1 位置

在 RRF 融合 + 类型权重之后，增加可选的 Cross-Encoder 重排序。

```
TEMPR 检索 → RRF 融合 → 类型权重 → [Cross-Encoder 重排序] → 返回
```

### 6.2 配置

```yaml
memory:
  reranker:
    enabled: false
    strategy: "local_gguf"      # local_gguf | api | none
    model_path: "models/qwen3-reranker-0.6b.gguf"
    top_k_for_rerank: 20
    top_k_after_rerank: 10
```

---

## 7. 记忆调度

### 7.1 热度分级

```python
class MemoryHeat:
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"

    @staticmethod
    def classify(memory) -> str:
        if memory.feedback_weight >= 0.8 and days_since(memory.last_accessed_at) < 7:
            return MemoryHeat.HOT
        elif memory.feedback_weight >= 0.5 or days_since(memory.last_accessed_at) < 30:
            return MemoryHeat.WARM
        else:
            return MemoryHeat.COLD
```

### 7.2 上下文窗口感知

```python
class ContextAwareRetriever:
    def __init__(self, token_budget=8000):
        self.token_budget = token_budget

    async def recall_with_budget(self, query, space_id):
        results = await query_service.recall(query, space_id)

        total_tokens = 0
        budgeted_results = []
        for result in results:
            tokens = estimate_tokens(result)
            if total_tokens + tokens > self.token_budget:
                break
            budgeted_results.append(result)
            total_tokens += tokens

        return budgeted_results, total_tokens
```

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Agent 记忆概念 | `docs/01-overview/09-agent-memory.md` |
| Agent 记忆设计总览 | `docs/02-design/agent-memory/README.md` |
| 记忆层次设计 | `docs/02-design/agent-memory/memory-hierarchy.md` |
| 认知操作 API 设计 | `docs/02-design/agent-memory/memory-api.md` |
| 时序建模 | `docs/02-design/schema/temporal-modeling.md` |
| 查询引擎设计 | `docs/02-design/query-engine/README.md` |
