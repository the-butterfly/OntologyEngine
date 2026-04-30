# 实体解析消歧

> **status**: draft | **phase**: rewrite | **source_of_truth**: 本文档 | **last_verified**: 2026-04-30

## 目的

定义 OntologyEngine 的实体解析消歧机制，确保同一现实实体在知识库中只存在一个 CognitiveNode，即使输入时使用了不同表述。

## 解决的问题

| # | 问题 | 示例 | 影响 |
|---|------|------|------|
| 1 | 同名变体 | "张三"/"张先生"/"Zhang San" | 创建重复实体 |
| 2 | 缩写与全称 | "华为"/"华为技术有限公司" | 知识碎片化 |
| 3 | 别名与曾用名 | "Facebook"/"Meta" | 时序关系断裂 |
| 4 | 跨文档共指 | 文档A"该公司"/文档B"华为" | 无法关联 |

---

## 消歧评分公式 [关键设计点]

```
score = name_similarity × 0.5
      + cooccurrence_overlap × 0.3
      + temporal_proximity × 0.2
```

### 阈值策略

| 分数范围 | 动作 | 说明 |
|----------|------|------|
| > 0.6 | 复用现有实体 | 高置信度匹配 |
| 0.3 - 0.6 | 待审 | 创建新实体 + 标记 pending_review |
| < 0.3 | 创建新实体 | 低置信度，视为不同实体 |

---

## 名称相似度计算

```python
def compute_name_similarity(text: str, candidate_name: str) -> float:
    t = text.lower().strip()
    c = candidate_name.lower().strip()

    if t == c:
        return 1.0

    edit_sim = SequenceMatcher(None, t, c).ratio()

    phonetic_sim = 0.0
    if pinyin(t) == pinyin(c):
        phonetic_sim = 0.8

    if len(t) > 1 and len(c) > 1:
        prefix_sim = 1.0 if c.startswith(t) or t.startswith(c) else 0.0
    else:
        prefix_sim = 0.0

    return max(edit_sim, phonetic_sim, prefix_sim)
```

| 方法 | 权重 | 适用场景 |
|------|------|---------|
| 编辑距离 | 基础 | 拼写变体、缩写 |
| 拼音相似 | 0.8 | 中文人名变体 |
| 前缀匹配 | 1.0 | 公司名缩写 |

---

## 共现重叠度

```python
async def compute_cooccurrence_overlap(
    entity_text: str,
    candidate_id: str,
    context: ResolutionContext,
) -> float:
    if not context.nearby_entity_ids:
        return 0.0

    co_entities = await get_cooccurrences(candidate_id)
    if not co_entities:
        return 0.0

    overlap = len(context.nearby_entity_ids & co_entities)
    return overlap / len(context.nearby_entity_ids)
```

### 共现追踪存储

```cypher
CREATE REL TABLE CO_OCCURS_WITH (
    FROM CognitiveNode,
    TO CognitiveNode,
    weight    DOUBLE DEFAULT 1.0,
    count     INT64 DEFAULT 1,
    last_seen DATETIME,
    space_id  STRING
)
```

### 共现更新

```python
async def update_cooccurrences(entity_ids: list[str], space_id: str):
    for i, eid_a in enumerate(entity_ids):
        for eid_b in entity_ids[i + 1:]:
            existing = await get_cooccurrence(eid_a, eid_b, space_id)
            if existing:
                await update_cypher("""
                    MATCH (a:CognitiveNode {id: $a})-[r:CO_OCCURS_WITH]-(b:CognitiveNode {id: $b})
                    SET r.count = r.count + 1,
                        r.weight = r.weight * 0.9 + 0.1,
                        r.last_seen = $now
                """, {"a": eid_a, "b": eid_b, "now": now_iso()})
            else:
                await create_cypher("""
                    MATCH (a:CognitiveNode {id: $a}), (b:CognitiveNode {id: $b})
                    CREATE (a)-[:CO_OCCURS_WITH {weight: 1.0, count: 1, last_seen: $now, space_id: $space_id}]->(b)
                """, {"a": eid_a, "b": eid_b, "now": now_iso(), "space_id": space_id})
```

---

## 时序邻近性

```python
def compute_temporal_proximity(
    context: ResolutionContext,
    candidate: CognitiveNode,
) -> float:
    if not context.event_date or not candidate.occurred_at:
        return 0.0

    days_diff = abs((context.event_date - candidate.occurred_at).days)
    if days_diff > 365:
        return 0.0

    return max(0.0, 1.0 - days_diff / 365)
```

---

## 双策略切换 [关键设计点]

```python
class EntityResolver:
    def __init__(self, storage, strategy: str = "auto"):
        self.storage = storage
        self.strategy = strategy

    async def resolve(
        self,
        space_id: str,
        entity_texts: list[str],
        context: ResolutionContext,
    ) -> list[ResolutionResult]:
        if self.strategy == "full" or (
            self.strategy == "auto"
            and await self._entity_count(space_id) < 10000
        ):
            return await self._resolve_full(space_id, entity_texts, context)
        else:
            return await self._resolve_trigram(space_id, entity_texts, context)
```

### Full 策略（小规模）

```python
async def _resolve_full(
    self, space_id: str, entity_texts: list[str], context: ResolutionContext
) -> list[ResolutionResult]:
    all_entities = await self.storage.get_entities_by_space(space_id)
    results = []

    for text in entity_texts:
        best_score = 0.0
        best_candidate = None

        for entity in all_entities:
            score = self._compute_disambiguation_score(text, entity, context)
            if score > best_score:
                best_score = score
                best_candidate = entity

        results.append(ResolutionResult(
            entity_text=text,
            action="reuse" if best_score > 0.6 else "create",
            candidate_id=best_candidate.id if best_candidate else None,
            score=best_score,
        ))

    return results
```

### Trigram 策略（大规模）

```python
async def _resolve_trigram(
    self, space_id: str, entity_texts: list[str], context: ResolutionContext
) -> list[ResolutionResult]:
    results = []

    for text in entity_texts:
        trigrams = set(compute_trigrams(text))
        candidates = await self.storage.search_by_trigrams(
            space_id, trigrams, top_k=20
        )

        best_score = 0.0
        best_candidate = None

        for candidate in candidates:
            score = self._compute_disambiguation_score(text, candidate, context)
            if score > best_score:
                best_score = score
                best_candidate = candidate

        results.append(ResolutionResult(
            entity_text=text,
            action="reuse" if best_score > 0.6 else "create",
            candidate_id=best_candidate.id if best_candidate else None,
            score=best_score,
        ))

    return results

def compute_trigrams(text: str) -> list[str]:
    padded = f"  {text.lower()} "
    return [padded[i:i+3] for i in range(len(padded) - 2)]
```

---

## 与 CognitiveNode 集成

```python
async def resolve_and_create_or_reuse(
    entity_text: str,
    entity_type: str,
    space_id: str,
    context: ResolutionContext,
    schema_ref: str | None = None,
) -> str:
    result = await resolver.resolve(space_id, [entity_text], context)
    r = result[0]

    if r.action == "reuse":
        await increment_access_count(r.candidate_id)
        await update_cooccurrences(
            [r.candidate_id] + context.nearby_entity_ids, space_id
        )
        return r.candidate_id

    entity_id = generate_uuid5(entity_text, entity_type, space_id)
    await create_cognitive_node(
        id=entity_id,
        space_id=space_id,
        cognitive_layer="semantic",
        memory_type="entity",
        entity_name=entity_text,
        entity_type=entity_type,
        schema_ref=schema_ref,
        belief_status="accepted" if r.score < 0.3 else "pending_review",
    )
    await update_cooccurrences(
        [entity_id] + context.nearby_entity_ids, space_id
    )
    return entity_id
```

---

## 与 Schema L1 集成

```python
async def resolve_with_schema(
    entity_text: str,
    entity_type: str,
    space_id: str,
    context: ResolutionContext,
) -> str:
    schema = await get_entity_declaration(entity_type, space_id)

    if schema and schema.identity_fields:
        identity_values = context.extracted_attributes
        identity_key = tuple(
            identity_values.get(f) for f in schema.identity_fields
            if f in identity_values
        )

        if identity_key:
            existing = await find_by_identity_key(
                entity_type, identity_key, space_id
            )
            if existing:
                return existing.id

    return await resolve_and_create_or_reuse(
        entity_text, entity_type, space_id, context,
        schema_ref=schema.name if schema else None,
    )
```

**优先级**：Schema identity_fields 精确匹配 > 三维度消歧评分

---

## 并发安全

```python
async def resolve_batch(
    space_id: str,
    entities: list[EntityExtraction],
    context: ResolutionContext,
) -> dict[str, str]:
    task_key = f"resolve:{space_id}:{hash(frozenset(e.text for e in entities))}"

    async with task_lock(task_key):
        results = {}
        for entity in entities:
            entity_id = await resolve_and_create_or_reuse(
                entity.text, entity.type, space_id, context,
            )
            results[entity.text] = entity_id

        await refresh_cooccurrence_index(space_id)
        return results
```

---

## 批量解析

```python
async def resolve_ingestion_batch(
    space_id: str,
    extractions: list[ExtractionResult],
) -> dict[str, str]:
    all_entity_texts = []
    for ext in extractions:
        all_entity_texts.extend(e.text for e in ext.entities)

    context = ResolutionContext(
        nearby_entity_ids=set(),
        event_date=extractions[0].occurred_at if extractions else None,
    )

    resolver = EntityResolver(storage, strategy="auto")
    results = await resolver.resolve(space_id, all_entity_texts, context)

    entity_map = {}
    for r in results:
        entity_map[r.entity_text] = (
            r.candidate_id if r.action == "reuse"
            else await create_new_entity(r, space_id, context)
        )

    all_ids = list(entity_map.values())
    await update_cooccurrences(all_ids, space_id)

    return entity_map
```

---

## 设计决策

| # | 决策 | 理由 |
|---|------|------|
| D-ER-1 | 三维度评分 0.5/0.3/0.2 | Hindsight 验证有效，名称是主要判据 |
| D-ER-2 | 阈值 0.6/0.3 三段式 | 平衡精确性和召回率 |
| D-ER-3 | 双策略切换 10000 实体 | Full 策略 O(n) 扫描，超过 10000 性能下降 |
| D-ER-4 | CO_OCCURS_WITH 边存储共现 | 图数据库原生支持，可遍历可聚合 |
| D-ER-5 | Schema identity_fields 优先 | 结构化数据的精确匹配优于模糊消歧 |
| D-ER-6 | 乐观并发 + task-key 隔离 | KuzuDB 不支持行级锁，应用层保证 |
| D-ER-7 | 拼音相似度 0.8（非 1.0） | 同音不同字（如"李明"/"李铭"）需保留区分 |
