# RFC-022: LLM 反思混合模式 + 策略性遗忘

> **状态**: draft
> **创建日期**: 2026-05-07
> **作者**: agent-memory-session
> **评审截止**: 待定
> **关联设计**: [reflect-agent.md](../../docs/02-design/agent-memory/reflect-agent.md) · [memory-lifecycle.md](../../docs/02-design/agent-memory/memory-lifecycle.md)
> **验收基准**: examples/agent_memory/ 02_contradiction + 05_lifecycle + 08_qul

## 摘要

实现 ReflectAgent 的 LLM 调用循环（混合模式：LLM 可用时调用，不可用时降级为纯规则检测）；补齐策略性遗忘（superseded*0.5, rejected*0.2, 级联标记 stale）；修复遗忘因子计算偏差。

## 背景与动机

### 当前问题

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| G10 | 策略性遗忘完全未实现 | HIGH | 被否定的记忆仍按自然衰减速度消退 |
| G11 | LLM 驱动反思循环未实现 | HIGH | 无法发现语义层面的隐含矛盾 |
| G12 | DreamCycle Phase 5 偏离规范 | MED | 图谱补全仅做词重叠统计，不创建边 |
| G13 | confirmation 因子计算偏差 | MED | 设计用 exp(-0.05*days)，实现用 count/5 |
| G14 | 衰减率选择用 confidence 而非 strength | MED | 高置信度低强度记忆获得低遗忘率 |
| G15 | CorrectionPropagation 下游差异化处理缺失 | MED | mental_model 未标记 is_stale |

### 验收组影响

- 02_contradiction: T1 score=0.33（insights=0，LLM 反思缺失）
- 05_lifecycle: T7 策略性遗忘未验证
- 08_qul: T6-T7 遗忘因子影响不正确

## 设计方案

### D1: LLM 反思混合模式

```python
class ReflectAgent:
    async def reflect(self, query, space_id, disposition=None, llm_call=None):
        # Phase A: 规则矛盾检测 (always)
        rule_contradictions = await self._detect_rule_based_contradictions(
            query, space_id, disposition=disposition
        )

        # Phase B: LLM 反思循环 (if available)
        search_contradictions = []
        insights = []
        if llm_call is not None:
            try:
                result = await self._run_llm_reflection_loop(
                    query, space_id, disposition, llm_call
                )
                search_contradictions = result.contradictions
                insights = result.insights
            except Exception as e:
                logger.warning("LLM reflection failed, using rule-only results: %s", e)
        else:
            logger.info("No LLM available, using rule-based reflection only")

        # Phase C: 合并去重
        all_contradictions = self._merge_contradictions(
            rule_contradictions, search_contradictions
        )

        return ReflectResult(
            contradictions=all_contradictions,
            insights=insights,
            method="hybrid" if llm_call else "rule_only",
        )
```

**LLM 反思循环**:
- 工具集: search_by_type, recall, detect_contradictions, done
- 前 3 轮强制检索: mental_model → entity → observation
- 第 4+ 轮: LLM 自主决策
- 幻觉防护: 所有 evidence_ids 必须在 available_ids 中
- 上下文溢出保护: Token 计数 >= max_context_tokens 时强制 done

### D2: 策略性遗忘

```python
class ForgettingEngine:
    async def apply_strategic_forgetting(self, node_id: str, signal: str):
        """Apply strategic forgetting based on negation signals.

        Args:
            node_id: The node receiving the negation signal
            signal: "superseded" or "rejected"
        """
        node = await self._repo.get_node(node_id)
        if not node:
            return

        # 1. Strength骤降
        if signal == "superseded":
            decay_factor = 0.5
        elif signal == "rejected":
            decay_factor = 0.2
        else:
            return

        node.feedback_weight *= decay_factor

        # 2. valid_to提前 (rejected)
        if signal == "rejected" and node.valid_to is None:
            node.valid_to = datetime.now(timezone.utc).isoformat()

        # 3. 级联标记stale
        await self._mark_downstream_stale(node_id, signal)

        await self._repo.update_node(node)

    async def _mark_downstream_stale(self, node_id: str, signal: str):
        """Mark downstream nodes as stale via cognitive edges."""
        edges = await self._repo.query_cognitive_edges(
            from_id=node_id,
            edge_types=["SUMMARIZED_AS", "CONSOLIDATED_INTO", "COGNITIVE_RELATES_TO"],
        )
        for edge in edges:
            downstream = await self._repo.get_node(edge.to_id)
            if downstream and downstream.belief_status == "accepted":
                downstream.attributes = downstream.attributes or {}
                downstream.attributes["stale_reason"] = f"upstream_{signal}"
                downstream.attributes["stale_from"] = node_id
                await self._repo.update_node(downstream)
```

**触发时机**:
- `correct_memory()` 创建新节点后，对旧节点调用 `apply_strategic_forgetting(node_id, "superseded")`
- `approve/reject` 工作流中，对 rejected 节点调用 `apply_strategic_forgetting(node_id, "rejected")`

### D3: 遗忘因子修正

1. **confirmation 因子**: 新增 `last_confirmed_at` 字段到 CognitiveNode，使用 `exp(-0.05 * days_since_confirm)` 计算确认衰减
2. **衰减率选择**: 使用 `strength`（运行时计算值）而非 `confidence` 作为 memory_value
3. **硬删除条件**: 改为 `proof_count == 0` 而非 `source_fragment_ids 为空`

### D4: CorrectionPropagation 下游差异化

```python
async def propagate(self, node_id: str, ...):
    # ... BFS 传播 ...

    # 下游差异化处理
    for affected_id in visited:
        affected = await self._repo.get_node(affected_id)
        if not affected:
            continue

        if affected.memory_type == "mental_model":
            affected.attributes = affected.attributes or {}
            affected.attributes["is_stale"] = True
            affected.attributes["stale_reason"] = f"upstream_{signal}"

        if affected.memory_type == "entity":
            # 标记需要属性更新检查
            affected.attributes = affected.attributes or {}
            affected.attributes["needs_attribute_update"] = True

        if affected.memory_type == "observation":
            # 标记需要重新归纳
            affected.attributes = affected.attributes or {}
            affected.attributes["needs_reinduction"] = True

        await self._repo.update_node(affected)
```

### D5: DreamCycle Phase 5 修正

```python
# Phase 5: 图谱补全
async def _phase5_graph_completion(self, space_id: str):
    """LLM-driven graph completion for newly created nodes."""
    new_nodes = await self._repo.query_nodes(
        space_id=space_id,
        limit=50,
        # filter: created in last 24h
    )

    if not new_nodes:
        return []

    # 规则层: 词重叠候选 (Jaccard > 0.25)
    candidates = self._find_similar_pairs(new_nodes, threshold=0.25)

    # LLM 层: 验证并建议边类型 (if available)
    if self._llm_available:
        validated = await self._validate_edges_with_llm(candidates)
    else:
        validated = [(a, b, "COGNITIVE_RELATES_TO") for a, b in candidates]

    # 创建边
    created = []
    for from_id, to_id, edge_type in validated:
        try:
            await self._repo.create_cognitive_edge(
                from_id=from_id, to_id=to_id, edge_type=edge_type
            )
            created.append((from_id, to_id, edge_type))
        except Exception:
            pass

    return created
```

## 验收标准

### 02_contradiction 补充验收

| 轨迹 | 验收点 | 通过条件 |
|------|--------|---------|
| T1-EXT | LLM 反思降级验证 | LLM 不可用时仍返回规则矛盾，method="rule_only" |
| T2-EXT | LLM 反思循环验证 | LLM 可用时 insights > 0，method="hybrid" |
| T8-NEW | 幻觉防护验证 | 所有 insight.evidence_ids 在 available_ids 中 |

### 05_lifecycle 补充验收

| 轨迹 | 验收点 | 通过条件 |
|------|--------|---------|
| T7-EXT | 策略性遗忘 superseded | superseded 节点 strength *= 0.5 |
| T7-EXT2 | 策略性遗忘 rejected | rejected 节点 strength *= 0.2, valid_to 提前 |
| T7-EXT3 | 级联标记 stale | 下游 mental_model 的 is_stale=True |
| T9-NEW | 遗忘因子修正 | confirmation 使用 exp(-0.05*days)，衰减率使用 strength |

### 08_qul 补充验收

| 轨迹 | 验收点 | 通过条件 |
|------|--------|---------|
| T6-EXT | Ebbinghaus 衰减验证 | 高价值 rate=0.1, 中 value rate=0.4, 低 value rate=0.85 |
| T7-EXT | 策略性遗忘 E2E | correct → superseded → strength骤降 → 下游 stale |

## 实施计划

| 阶段 | 内容 | 依赖 |
|------|------|------|
| Phase 1 | 策略性遗忘实现 (D2) | 无 |
| Phase 2 | 遗忘因子修正 (D3) + CorrectionPropagation 差异化 (D4) | Phase 1 |
| Phase 3 | LLM 反思混合模式 (D1) | Phase 1 |
| Phase 4 | DreamCycle Phase 5 修正 (D5) | Phase 3 |

## 风险

1. LLM 反思循环的 Token 消耗可能较大，需设日预算限制
2. 策略性遗忘的级联标记可能影响大量节点，需设影响半径限制
3. last_confirmed_at 字段需数据库 Schema 迁移
