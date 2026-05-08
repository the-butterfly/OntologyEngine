# RFC-020: 记忆生成路径优化

> **状态**: draft
> **创建日期**: 2026-05-07
> **作者**: agent-memory-session
> **评审截止**: 待定
> **关联设计**: [memory-api.md](../../docs/02-design/agent-memory/memory-api.md) · [consolidation-engine.md](../../docs/02-design/agent-memory/consolidation-engine.md) · [memory-lifecycle.md](../../docs/02-design/agent-memory/memory-lifecycle.md)
> **验收基准**: examples/agent_memory/ 01_ingestion + 03_consolidation

## 摘要

补齐 remember() 6 步编排链中的 IngestionService 和 ExtractionPipeline，实现 Layer-R/Layer-S 双层写入；修复 COG_SUPPORTED_BY 边缺失、CONTRADICTION_CANDIDATE 未处理、OCC version 字段不完整等问题。

## 背景与动机

### 当前问题

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| G1 | IngestionService + ExtractionPipeline 未实现，直接创建 CognitiveNode | HIGH | Layer-R/Layer-S 双层写入概念未实现，fragment 无独立向量索引 |
| G2 | CONTRADICTION_CANDIDATE 决策未处理，gate 返回后直接写入 | HIGH | 矛盾候选记忆未获高优先级 Consolidation |
| G3 | COG_SUPPORTED_BY 边未在引擎层创建 | HIGH | 双通道证据追踪缺一通道 |
| G4 | OCC version 字段未真正实现，用 extraction_hint 代替 | MED | 并发安全无保障 |
| G5 | L1 精确匹配（identity_fields + UUID5）缺失 | MED | 结构化数据导入无确定性匹配 |
| G6 | 推理轨迹 consolidation_reasoning 缺失 | MED | 巩固过程不可解释 |
| G8 | entity_resolver._store bug，应为 _repo | HIGH | 运行时必抛 AttributeError |
| G9 | proof_count Update 只 +1 而非 +len(new_sources) | MED | 证据计数失真 |

### 验收组影响

- 01_ingestion: T1 recall_hits=0（向量索引缺失），T3-T4 L1 精确匹配缺失
- 03_consolidation: T1 consolidated=0，T3 证据追踪不完整，T5-T6 编译摘要拼接

## 设计方案

### D1: IngestionService 双层写入

```
remember() 编排链（完整版）:
1. DeduplicationGate.check() → DUPLICATE / CONTRADICTION_CANDIDATE / DELAYED / ACCEPT
2. IngestionService.ingest() → 创建 KnowledgeFragment (Layer-R, memory_type=fragment)
3. ExtractionPipeline.extract() → 从碎片中提取 entities/relations
4. EntityResolver.resolve() → L1 identity_fields → L2 trigram → L3 LLM 消歧
5. 写入 CognitiveNode (Layer-S) + 创建 COG_SUPPORTED_BY 边
6. If auto_consolidate: ConsolidationEngine.consolidate()
```

**IngestionService**:
- 输入: content, space_id, tags, metadata
- 输出: KnowledgeFragment (Layer-R), fragment_id
- 行为: 创建 fragment 类型 CognitiveNode，写入 KuzuDB + ChromaDB 向量索引
- 向量索引: fragment 写入时同步 embedding 到 ChromaDB

**ExtractionPipeline**:
- 输入: KnowledgeFragment, schema_ref (可选)
- 输出: extracted_entities: list[ExtractedEntity], extracted_relations: list[ExtractedRelation]
- 行为: 
  - 无 schema_ref: 简单提取（content[:50] 作为 entity_text，取 tags 作为关系线索）
  - 有 schema_ref: Schema-guided 提取（按 EntityDeclaration.identity_fields 提取结构化实体）
- LLM 可选: 当 schema_ref 存在且 LLM 可用时，调用 LLM 做深度提取

### D2: CONTRADICTION_CANDIDATE 处理

```python
# memory_api.py _remember() 中增加:
if gate_decision == "CONTRADICTION_CANDIDATE":
    # 高优先级入队: 立即触发 Consolidation
    if auto_consolidate:
        await self._consolidation.consolidate(space_id, force=True)
    # 标记 belief_status 为 pending_review
    belief_status = "pending_review"
```

### D3: COG_SUPPORTED_BY 边创建

在以下位置创建 COG_SUPPORTED_BY 边:
1. `_remember()`: CognitiveNode 创建后，为 source_fragment_ids 中的每个 fragment 创建 COG_SUPPORTED_BY 边
2. `ConsolidationEngine.execute_create()`: 新 observation 的 source_fragment_ids → COG_SUPPORTED_BY
3. `ConsolidationEngine.execute_update()`: 新增 source_fragment_ids → COG_SUPPORTED_BY

### D4: OCC version 字段

- CognitiveNode 新增 `version: int = 1` 字段
- `update_node()` 传递 `expected_version` 参数
- ConsolidationEngine 在 `_fetch_unconsolidated_fragments` 时记录 version，在 `execute_update` 时校验

### D5: L1 精确匹配

```python
# EntityResolver 新增:
async def _resolve_l1_exact(self, entity_text: str, identity_fields: dict | None = None) -> ResolveResult | None:
    if identity_fields:
        key = uuid.uuid5(UUID_NAMESPACE, json.dumps(identity_fields, sort_keys=True))
        existing = await self._repo.get_node(str(key))
        if existing:
            return ResolveResult(node_id=existing.id, score=1.0, strategy="l1_exact")
    # fallback: content 精确匹配
    nodes = await self._repo.query_nodes(entity_name=entity_text, limit=1)
    if nodes:
        return ResolveResult(node_id=nodes[0].id, score=1.0, strategy="l1_exact")
    return None
```

### D6: Bug 修复

1. `entity_resolver.py L374`: `self._store` → `self._repo`
2. `consolidation_engine.py L320`: `getattr(existing, "proof_count", 0) + 1` → `existing.proof_count + len(new_source_ids)`
3. `memory_api.py L1281`: `space_id=space_id` → `space_id=old_node.space_id`

## 验收标准

### 01_ingestion 补充验收

| 轨迹 | 验收点 | 通过条件 |
|------|--------|---------|
| T1-EXT | Layer-R 写入验证 | remember 后 fragment 节点存在于 KuzuDB，向量索引有对应 embedding |
| T2-EXT | CONTRADICTION_CANDIDATE 处理 | gate 返回 CONTRADICTION_CANDIDATE 时，记忆 belief_status=pending_review 且触发 Consolidation |
| T3-EXT | L1 identity_fields 匹配 | 相同 identity_fields 的两次 remember 复用同一 node_id |
| T9-NEW | COG_SUPPORTED_BY 边验证 | remember 后 CognitiveNode 有 COG_SUPPORTED_BY 边指向 source fragment |

### 03_consolidation 补充验收

| 轨迹 | 验收点 | 通过条件 |
|------|--------|---------|
| T1-EXT | 三动作独立验证 | Create: 新 observation 产生; Update: proof_count += len(new_sources); Delete: 旧节点 superseded |
| T3-EXT | 双通道证据追踪 | source_fragment_ids 非空 + COG_SUPPORTED_BY 边存在 + CONSOLIDATED_INTO 边存在 |
| T7-EXT | 推理轨迹验证 | 巩固后 CognitiveNode.consolidation_reasoning 非空 |
| T9-NEW | OCC 并发安全 | 两个并发 Consolidation 请求，后者因 version 不匹配而失败 |

## 实施计划

| 阶段 | 内容 | 依赖 |
|------|------|------|
| Phase 1 | Bug 修复 (G8, G9, memory_api space_id) | 无 |
| Phase 2 | COG_SUPPORTED_BY 边创建 (G3) | Phase 1 |
| Phase 3 | CONTRADICTION_CANDIDATE 处理 (G2) | Phase 1 |
| Phase 4 | IngestionService + ExtractionPipeline (G1) | Phase 2 |
| Phase 5 | OCC version 字段 (G4) + L1 精确匹配 (G5) + 推理轨迹 (G6) | Phase 4 |

## 风险

1. IngestionService 双层写入增加 remember 延迟（需同步写两个存储）
2. ExtractionPipeline 的 LLM 提取可能超时（需设超时和降级策略）
3. OCC version 字段需数据库 Schema 迁移
