# 记忆生命周期设计

> **status**: draft | **phase**: phase2 | **source_of_truth**: `docs/01-overview/09-agent-memory.md` + `docs/01-overview/10-kb-process.md` | **last_verified**: 2026-04-30

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

## 8. 编译层（Compilation Layer）[新增]

> **[关键设计点]**：编译层是巩固的高级产物，将高频访问的实体信息预编译为 Entity Page / Topic Page，加速检索。

### 8.1 编译产物类型

| 产物 | 输入 | 输出 | Token 消耗 |
|------|------|------|-----------|
| Entity Page | 单个 entity + 关联 observation + 关系 | 结构化摘要 + 时间线 + 关键指标 | ~5000 |
| Topic Page | 多个 entity + mental_model | 主题综合观点 + 实体关联图 | ~3000 |

### 8.2 编译触发策略

| 策略 | 条件 | 说明 |
|------|------|------|
| 热点预编译 | access_count > 10/周 | 高频实体自动预编译 |
| 按需编译 | 首次查询 Entity Page 时 | 低频实体首次访问触发 |
| 事件触发 | entity 属性变更 | 标记 compiled_at < updated_at → stale |

### 8.3 编译产物一致性

```python
async def check_compilation_consistency(node_id):
    node = await get_cognitive_node(node_id)
    if node.compiled_at and node.compiled_at < node.updated_at:
        return CompilationStatus.STALE
    return CompilationStatus.CURRENT
```

### 8.4 编译防抖策略

```python
class CompilationDebouncer:
    def __init__(self, debounce_seconds=300):
        self.pending = {}
        self.debounce_seconds = debounce_seconds

    async def schedule_recompilation(self, node_id):
        if node_id in self.pending:
            self.pending[node_id].cancel()
        self.pending[node_id] = asyncio.create_task(
            self._debounced_compile(node_id)
        )

    async def _debounced_compile(self, node_id):
        await asyncio.sleep(self.debounce_seconds)
        await compile_entity_page(node_id)
        del self.pending[node_id]
```

### 8.5 成本感知编译

```python
async def compile_with_budget(space_id, daily_token_budget=5000000):
    candidates = await get_compilation_candidates(space_id)
    candidates.sort(key=lambda n: n.access_count, reverse=True)

    total_cost = 0
    for node in candidates:
        estimated_cost = estimate_compilation_cost(node)
        if total_cost + estimated_cost > daily_token_budget:
            break
        await compile_entity_page(node.id)
        total_cost += estimated_cost
```

---

## 9. 信念修正规则引擎 [新增]

> **[关键设计点]**：可配置的信念修正规则，支持优先级排序和冲突检测。

### 9.1 规则定义

```python
@dataclass
class BeliefRevisionRule:
    rule_id: str
    name: str
    condition: str
    action: str
    priority: int
    track: str  # "track_a" | "track_b" | "both"
    enabled: bool = True
```

### 9.2 默认规则集

| 优先级 | 规则 | 条件 | 动作 | 轨道 |
|--------|------|------|------|------|
| 100 | 用户明确更正 | source == "user_correction" | 自动取代 | both |
| 90 | 征信报告优先 | source_type == "credit_report" | 取代非征信来源 | track_a |
| 80 | 高置信度取代 | new.confidence > old.confidence × 1.5 | 自动取代 | track_b |
| 70 | 时序更新 | new.recorded_at > old.recorded_at | 自动 supersede | track_b |
| 60 | 反馈权重保护 | old.feedback_weight > 0.9 | 拒绝自动取代 | both |
| 50 | Schema 违反 | !schema_valid(new) | 拒绝写入 | both |
| 40 | 跨域矛盾 | new.domain != old.domain | 需人工确认 | track_a |

### 9.3 规则冲突检测

```python
def detect_rule_conflicts(rules):
    conflicts = []
    for i, r1 in enumerate(rules):
        for r2 in rules[i+1:]:
            if condition_overlap(r1.condition, r2.condition):
                if r1.action != r2.action and r1.priority == r2.priority:
                    conflicts.append(RuleConflict(r1, r2))
    return conflicts
```

---

## 10. 更正传播（CorrectionPropagation）[新增]

> **[关键设计点]**：更正自动传播到下游依赖，基于 SUPERSEDES 边和 COGNITIVE_RELATES_TO 边。

### 10.1 传播流程

```
更正写入（新 CognitiveNode supersede 旧 CognitiveNode）
  ↓
1. 查找旧节点的所有下游依赖
   ├── SUMMARIZED_AS → mental_model
   ├── COGNITIVE_RELATES_TO → 关联实体
   └── CONSOLIDATED_INTO → 上层 observation
  ↓
2. 对每个下游依赖：
   ├── mental_model → 标记 is_stale, compiled_at < updated_at
   ├── 关联实体 → 检查是否需要更新属性
   └── 上层 observation → 触发重新归纳
  ↓
3. 级联深度限制（默认 max_depth=3）
  ↓
4. 级联更新防风暴
   ├── 单次更正影响节点 > 100 → 需人工审批
   └── 批量更正分批执行
```

### 10.2 级联更新防风暴

```python
class CascadeController:
    MAX_CASCADE_NODES = 100
    MAX_CASCADE_DEPTH = 3

    async def propagate_correction(self, old_node_id, new_node_id):
        impact = await calculate_impact_radius(old_node_id, self.MAX_CASCADE_DEPTH)

        if len(impact.affected_nodes) > self.MAX_CASCADE_NODES:
            await request_manual_approval(
                f"Correction affects {len(impact.affected_nodes)} nodes, "
                f"exceeds threshold {self.MAX_CASCADE_NODES}"
            )
            return

        await execute_cascade_update(impact, new_node_id)
```

---

## 11. 梦境循环（Dream Cycle）[新增]

> **[关键设计点]**：周期性全局维护任务，采用采样策略而非全量扫描，控制资源消耗。

### 11.1 五阶段设计

| Phase | 任务 | 采样策略 | 资源估算 |
|-------|------|---------|---------|
| 1 矛盾检测 | 扫描 Compiled Page 检测矛盾 | 最近7天变更的 Page | ~10% 全量 |
| 2 过期检查 | 检查 valid_to 已过的记忆 | valid_to < now 的记忆 | 精确集合 |
| 3 孤立清理 | 清理无入边的 CognitiveNode | access_count < 5 的节点 | ~20% 全量 |
| 4 自链接增强 | 为相关记忆创建 COGNITIVE_RELATES_TO | 新创建的 Page | 增量 |
| 5 图谱补全 | LLM 建议新链接关系 | 新创建的 Page | 增量 |

### 11.2 执行策略

```python
async def run_dream_cycle(space_id, config):
    phase1_results = await detect_contradictions(
        space_id,
        filter={"updated_at": {"$gt": now - timedelta(days=7)}}
    )

    phase2_results = await check_expired(space_id)

    phase3_results = await clean_orphans(
        space_id,
        filter={"access_count": {"$lt": 5}}
    )

    phase4_results = await enhance_self_links(
        space_id,
        filter={"created_at": {"$gt": now - timedelta(days=1)}}
    )

    phase5_results = await complete_graph(
        space_id,
        filter={"created_at": {"$gt": now - timedelta(days=1)}}
    )

    return DreamCycleResult(
        contradictions=phase1_results,
        expired=phase2_results,
        orphans_cleaned=phase3_results,
        links_enhanced=phase4_results,
        graph_completed=phase5_results,
    )
```

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Agent 记忆概念 | `docs/01-overview/09-agent-memory.md` |
| Agent 记忆设计总览 | `docs/02-design/agent-memory/README.md` |
| 记忆层次设计 | `docs/02-design/agent-memory/memory-hierarchy.md` |
| 认知操作 API 设计 | `docs/02-design/agent-memory/memory-api.md` |
| Consolidation 引擎设计 | `docs/02-design/agent-memory/consolidation-engine.md` |
| Reflect Agent 设计 | `docs/02-design/agent-memory/reflect-agent.md` |
| 实体解析消歧设计 | `docs/02-design/services/entity-resolver.md` |
| 时序建模 | `docs/02-design/schema/temporal-modeling.md` |
| 查询引擎设计 | `docs/02-design/query-engine/README.md` |
| 知识库流程主文档 | `docs/01-overview/10-kb-process.md` |
| 审查辩论文档 | `discuss/2026-04-30-kb-memory-design-adversarial-review.md` |

> **[关键设计点]** 巩固的详细实现（三动作模型、证据链更新、自适应分批、并发安全）见 [consolidation-engine.md](./consolidation-engine.md)。本文档定义巩固的概念和触发机制，consolidation-engine.md 定义工程实现细节。

> **[关键设计点]** Reflect Agent 的详细实现（工具定义、迭代循环、幻觉防护、上下文溢出保护）见 [reflect-agent.md](./reflect-agent.md)。本文档定义反思的概念和输出类型，reflect-agent.md 定义 Agent 架构和工程实现。

> **[关键设计点]** 实体消歧的详细实现（三维度评分、双策略切换、共现追踪）见 [entity-resolver.md](../services/entity-resolver.md)。本文档定义消歧的概念和三级策略，entity-resolver.md 定义评分算法和工程实现。
