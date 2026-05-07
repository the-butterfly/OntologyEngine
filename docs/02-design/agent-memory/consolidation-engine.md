# Consolidation 引擎

> **status**: under-review | **phase**: Phase 2 | **source_of_truth**: 本文档 | **last_verified**: 2026-05-03
>
> **实施状态**: 核心引擎已实现 (consolidation_engine.py)。Schema 对齐评分使用浓缩版结构检查（完整 EntityDeclaration-based 评分标记为 Phase 3）。tags 已通过 CognitiveNode.tags + Kuzu JSON 列完整接入隔离链路 (D-CON-4)。execute_create/update/delete 均写入 proof_count/confidence/tags/superseded_by。

## 目的

定义 OntologyEngine 的 Consolidation 引擎，将碎片记忆（fragment）自动归纳为持久知识（observation/entity/mental_model），维护证据链和变更历史。

## 解决的问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 碎片记忆无法自动归纳 | 知识停留在感知层，无法形成结构化认知 |
| 2 | 同主题碎片分散存储 | 重复信息无法合并，检索效率低 |
| 3 | 归纳过程缺乏证据追踪 | 无法验证知识的来源和可信度 |
| 4 | 不同标签空间的记忆混在一起处理 | 跨租户信息泄漏风险 |
| 5 | LLM 调用失败导致整批丢失 | 归纳鲁棒性不足 |
| 6 | 归纳产物与编译产物关系不清 | 巩固与编译的边界模糊 |

---

## 触发机制

| 触发方式 | 场景 | 优先级 |
|----------|------|--------|
| 写入后异步 | oe_remember 写入碎片后触发 | 高 |
| 定时批量 | 每日低峰期扫描未巩固碎片 | 中 |
| 手动触发 | 用户/Agent 显式请求巩固 | 低 |
| 反思触发 | ReflectAgent 检测到未巩固碎片 | 中 |

```python
async def maybe_trigger_consolidation(space_id: str, trigger: str = "write_async"):
    if trigger == "write_async":
        pending = await count_unconsolidated(space_id)
        if pending < CONSOLIDATION_THRESHOLD:
            return
    await enqueue_consolidation_job(space_id, trigger)
```

---

## 核心流程

```
┌───────────────────┐
│ 1. 获取未巩固碎片    │  consolidated_at IS NULL
└────────┬──────────┘
         ▼
┌───────────────────┐
│ 2. 按 tags 分组     │  不同 tags 不共享 LLM 调用
└────────┬──────────┘
         ▼
┌───────────────────┐
│ 3. LLM 批量判断     │  create / update / delete
└────────┬──────────┘
         ▼
┌───────────────────┐
│ 4. 执行动作          │  更新 CognitiveNode + 证据链
└────────┬──────────┘
         ▼
┌───────────────────┐
│ 5. 更新证据链        │  source_fragment_ids + history + proof_count
└────────┬──────────┘
         ▼
┌───────────────────┐
│ 6. 触发下游          │  mental_model 刷新 + 编译层更新
└───────────────────┘
```

---

## 三动作模型 [关键设计点]

### Create：创建新 Observation

```python
async def execute_create(action: CreateAction, space_id: str):
    node_id = generate_uuid5(action.text, action.tags)
    source_ids = [f.id for f in action.source_fragments]

    history_entry = json.dumps([{
        "change_reason": "consolidation",
        "changed_at": now_iso(),
        "changed_by": "consolidation_engine",
        "new_source_fragment_ids": source_ids,
    }])

    await create_cognitive_node(
        id=node_id,
        space_id=space_id,
        cognitive_layer="semantic",
        memory_type="observation",
        text=action.text,
        tags=action.tags,
        source_fragment_ids=source_ids,
        history=history_entry,
        proof_count=len(source_ids),
        confidence=action.confidence,
        consolidated_at=now_iso(),
    )

    for frag_id in source_ids:
        # Edge type varies by target memory_type:
        #   observation → CONSOLIDATED_INTO
        #   mental_model → SUMMARIZED_AS
        #   procedure → LEARNED_INTO
        edge_type = "CONSOLIDATED_INTO"
        if action.memory_type == "mental_model":
            edge_type = "SUMMARIZED_AS"
        elif action.memory_type == "procedure":
            edge_type = "LEARNED_INTO"
        await create_edge(edge_type, frag_id, node_id)
```

### Update：更新已有 Observation

```python
async def execute_update(action: UpdateAction, space_id: str):
    existing = await get_cognitive_node(action.target_id)
    source_ids = list(set(
        (existing.source_fragment_ids or []) +
        [f.id for f in action.new_source_fragments]
    ))

    history_entry = {
        "previous_text": existing.text,
        "previous_tags": existing.tags,
        "previous_belief_status": existing.belief_status,
        "changed_at": now_iso(),
        "change_reason": "consolidation",
        "changed_by": "consolidation_engine",
        "new_source_fragment_ids": [f.id for f in action.new_source_fragments],
    }

    updated_history = append_to_json_array(existing.history, history_entry)

    await update_cognitive_node(
        id=action.target_id,
        text=action.updated_text,
        tags=action.updated_tags,
        source_fragment_ids=source_ids,
        history=updated_history,
        proof_count=existing.proof_count + len(action.new_source_fragments),
        confidence=max(existing.confidence, action.confidence),
        updated_at=now_iso(),
    )
```

### Delete：删除过时 Observation

```python
async def execute_delete(action: DeleteAction, space_id: str):
    existing = await get_cognitive_node(action.target_id)

    history_entry = {
        "previous_text": existing.text,
        "previous_belief_status": existing.belief_status,
        "changed_at": now_iso(),
        "change_reason": "consolidation",
        "changed_by": "consolidation_engine",
    }

    await update_cognitive_node(
        id=action.target_id,
        belief_status="superseded",
        history=append_to_json_array(existing.history, history_entry),
        superseded_by=action.replacement_id,
        updated_at=now_iso(),
    )
```

---

## 证据链更新 [关键设计点]

### 双通道证据追踪

| 通道 | 存储 | 查询场景 |
|------|------|---------|
| source_fragment_ids 数组 | CognitiveNode 强类型字段 | 快速溯源：给定节点 → 获取所有碎片 |
| COG_SUPPORTED_BY 边 | KuzuDB 边表 | 图遍历：给定碎片 → 找到所有支撑的节点 |
| CONSOLIDATED_INTO 边 | KuzuDB 边表 | 反向追踪：给定碎片 → 被归纳到哪个节点 |

### history 追加规则

```
每次变更（consolidation/correction/manual）均追加一条 history 条目
history 条目格式：
{
  "previous_text": "...",
  "previous_tags": ["..."],
  "previous_belief_status": "...",
  "changed_at": "2026-04-30T10:00:00Z",
  "change_reason": "consolidation | correction | manual",
  "changed_by": "agent_001 | user_001 | consolidation_engine",
  "new_source_fragment_ids": ["frag_001", "frag_002"]
}

history 条目上限：20 条（超出时压缩最早的条目，保留 first + last 19）
```

---

## Tags 隔离 [关键设计点]

```python
def group_by_tags(fragments: list[Fragment]) -> dict[tuple[str, ...], list[Fragment]]:
    tag_groups: dict[tuple[str, ...], list[Fragment]] = {}
    for f in fragments:
        tag_key = tuple(sorted(f.tags or []))
        tag_groups.setdefault(tag_key, []).append(f)
    return tag_groups

async def run_consolidation_job(space_id: str, batch_size: int = 50):
    unconsolidated = await fetch_unconsolidated_fragments(space_id, batch_size)
    tag_groups = group_by_tags(unconsolidated)

    for tag_key, fragments in tag_groups.items():
        existing = await find_related_observations(space_id, tags=tag_key)
        result = await consolidate_batch_with_llm(fragments, existing)
        await execute_consolidation_actions(result, space_id)
```

**隔离保证**：不同 tag_key 的碎片绝不共享同一次 LLM 调用。

---

## 自适应分批

```python
async def consolidate_batch_with_llm(
    fragments, existing, max_retries=3
):
    batch = fragments
    for attempt in range(max_retries):
        try:
            return await llm_consolidate(batch, existing)
        except LLMError:
            if len(batch) <= 1:
                raise
            mid = len(batch) // 2
            left = await consolidate_batch_with_llm(batch[:mid], existing, max_retries - 1)
            right = await consolidate_batch_with_llm(batch[mid:], existing, max_retries - 1)
            return merge_results(left, right)
```

---

## 并发安全

```python
async def fetch_unconsolidated_fragments(space_id: str, batch_size: int):
    cypher = """
        MATCH (kf:KnowledgeFragmentNode {space_id: $space_id})
        WHERE kf.consolidated_at IS NULL
          AND kf.version = $expected_version
        RETURN kf
        LIMIT $batch_size
    """
    fragments = await execute_cypher(cypher, {
        "space_id": space_id,
        "batch_size": batch_size,
    })

    await mark_as_consolidating([f.id for f in fragments])

    return fragments

async def mark_as_consolidating(fragment_ids: list[str]):
    cypher = """
        MATCH (kf:KnowledgeFragmentNode)
        WHERE kf.id IN $ids
        SET kf.version = kf.version + 1
    """
    await execute_cypher(cypher, {"ids": fragment_ids})
```

**策略**：乐观并发控制（version 字段），非 Hindsight 的 FOR SHARE 悲观锁。

---

## Mental Model 自动刷新

```python
async def trigger_mental_model_refresh(space_id: str, consolidated_tags: list[str]):
    cypher = """
        MATCH (n:CognitiveNode {space_id: $space_id, memory_type: 'mental_model'})
        WHERE ANY(tag IN n.tags WHERE tag IN $tags)
          AND n.attributes['is_stale'] = 'false'
        SET n.attributes['is_stale'] = 'true'
        RETURN n
    """
    stale_models = await execute_cypher(cypher, {
        "space_id": space_id,
        "tags": consolidated_tags,
    })

    for model in stale_models:
        await enqueue_refresh_job(model.id, space_id)
```

---

## Schema 对齐评分

```python
def compute_schema_alignment_score(observation: CognitiveNode, schema: EntityDeclaration) -> float:
    score = 0.0

    identity_match = set(observation.attributes.keys()) & set(schema.identity_fields)
    score += len(identity_match) / max(len(schema.identity_fields), 1) * 0.4

    attr_match = set(observation.attributes.keys()) & set(a.name for a in schema.attributes)
    score += len(attr_match) / max(len(schema.attributes), 1) * 0.3

    if observation.entity_type == schema.name:
        score += 0.3

    return score

SCHEMA_ALIGNMENT_THRESHOLD = 0.7

async def maybe_upgrade_to_entity(observation: CognitiveNode, space_id: str):
    schemas = await get_entity_declarations(space_id)
    for schema in schemas:
        score = compute_schema_alignment_score(observation, schema)
        if score >= SCHEMA_ALIGNMENT_THRESHOLD:
            await upgrade_memory_type(observation.id, "entity", schema_ref=schema.name)
            return
```

---

## 编译层与巩固层的关系 [关键设计点]

| 维度 | 巩固层 (Consolidation) | 编译层 (Compilation) |
|------|----------------------|---------------------|
| 输入 | KnowledgeFragment | CognitiveNode (entity/observation) |
| 输出 | CognitiveNode (observation/entity) | Entity Page / Topic Page |
| 触发 | 碎片积累 | Schema 对齐 + 编译阈值 |
| 目的 | 碎片→结构化知识 | 结构化知识→消费视图 |
| 关系 | 编译的前置条件 | 巩固的下游消费者 |

```
碎片 → [巩固] → observation/entity → [编译] → Entity Page / Topic Page
```

---

## 错误处理

| 错误类型 | 处理策略 |
|----------|---------|
| LLM 调用超时 | 折半重试，最多 3 次 |
| LLM 返回格式错误 | 丢弃该批次，记录日志，不重试 |
| 节点写入冲突 | 乐观并发重试（version 不匹配→重新获取→重试） |
| 碎片已被其他任务巩固 | 跳过该碎片（consolidated_at 非空） |
| Mental Model 刷新失败 | 保留 is_stale=true 标记，下次梦境循环重试 |

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-CON-1 | 乐观并发控制替代 FOR SHARE | KuzuDB 不支持行级锁，version 字段实现等价语义 |
| D-CON-2 | source_fragment_ids 作为强类型字段 | 高频溯源查询需要，避免遍历 CONSOLIDATED_INTO 边 |
| D-CON-3 | history 内联存储而非 SUPERSEDES 边遍历 | 高频历史查询性能需求，SUPERSEDES 边遍历成本高 |
| D-CON4 | Tags 严格分组隔离 | 防止跨租户信息泄漏，与 Hindsight 一致 |
| D-CON-5 | 自适应分批折半重试 | LLM 上下文窗口限制，折半降低 token 消耗 |
| D-CON-6 | 巩固与编译分离 | 职责不同：巩固是碎片→知识，编译是知识→视图 |
| D-CON-7 | Schema 对齐评分 0.7 阈值 | 平衡精确性和召回率，低于 0.7 的 observation 不应升级为 entity |
