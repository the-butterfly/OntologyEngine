# RFC-023: 检索路径优化

> **状态**: draft
> **创建日期**: 2026-05-07
> **作者**: agent-memory-session
> **评审截止**: 待定
> **关联设计**: [query-routing.md](../../docs/02-design/query-engine/query-routing.md) · [rrf-fusion.md](../../docs/02-design/query-engine/rrf-fusion.md)
> **验收基准**: examples/agent_memory/ 04_locomo + 08_qul

## 摘要

实现 FTS5 双表 BM25 索引、修复 analytical 查询路由、实现降级链路径切换、后置排序+短路优化、DispositionProfile 7 维度完整实现、valid_from/valid_to 有效期过滤。

## 背景与动机

### 当前问题

| # | 问题 | 严重度 | 影响 |
|---|------|--------|------|
| G19 | FTS5 双表 BM25 索引缺失 | HIGH | BM25 退化为内存子串匹配，中文几乎无效 |
| G20 | Analytical 查询返回空列表 | HIGH | 分析型检索完全不可用 |
| G21 | 降级链路径切换未实现 | MED | 降级链每步都走 mixed RRF |
| G22 | valid_from/valid_to 有效期过滤缺失 | MED | 可能返回已过期记忆 |
| G23 | DispositionProfile 7 维度仅实现 2 维度 | MED | evidence_demand/recency_bias/risk_tolerance/empathy 未影响权重 |
| G24 | 短路后异步验证缺失 | MED | 短路结果可能包含未发现矛盾 |
| G26 | BASE_TYPE_WEIGHTS 值偏差 | LOW | fragment=0.5→1.0, mental_model=2.0→3.0 |
| G27 | recall 返回的 query_type 不正确 | LOW | 返回 "type_filter"/"semantic" 而非实际类型 |

### 验收组影响

- 04_locomo: T1-T3 全部低分（BM25 退化 + 向量索引缺失）
- 08_qul: T2-T3 约束驱动重排序未实现

## 设计方案

### D1: FTS5 双表 BM25 索引

```sql
-- 在 SQLite 中创建两张 FTS5 虚拟表
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fragment_fts
    USING fts5(content, space_id, tags, tokenize='unicode61');

CREATE VIRTUAL TABLE IF NOT EXISTS cognitive_node_fts
    USING fts5(content, space_id, memory_type, entity_name, tags,
               cognitive_layer, belief_status,
               tokenize='unicode61');

-- 同步触发器: CognitiveNode 写入时同步到 FTS5
-- (在 repository.create_node / update_node 中触发)
```

**BM25 搜索实现**:

```python
async def _search_bm25_fts5(self, query: str, space_id: str, top_k: int) -> list[RetrievalResult]:
    conn = self._get_sqlite_conn()
    # 1. 搜索 cognitive_node_fts (仅 belief_status=accepted)
    rows = conn.execute("""
        SELECT node_id, bm25(cognitive_node_fts) as score
        FROM cognitive_node_fts
        WHERE cognitive_node_fts MATCH ? AND space_id = ? AND belief_status = 'accepted'
        ORDER BY score
        LIMIT ?
    """, (query, space_id, top_k)).fetchall()

    # 2. 搜索 knowledge_fragment_fts
    frag_rows = conn.execute("""
        SELECT fragment_id, bm25(knowledge_fragment_fts) as score
        FROM knowledge_fragment_fts
        WHERE knowledge_fragment_fts MATCH ? AND space_id = ?
        ORDER BY score
        LIMIT ?
    """, (query, space_id, top_k)).fetchall()

    # 3. 合并结果
    ...
```

**jieba 分词选项**: 当 jieba 可用时，先分词再拼接为 FTS5 查询语法。

### D2: Analytical 查询路由修复

```python
# query_router.py
async def route(self, query, space_id, ...):
    query_type = self.detect_query_type(query)

    if query_type == "analytical":
        # 不再返回空列表，路由到 rrf_fusion 的 analytical 路径
        results = await self._rrf.fuse(
            query=query, space_id=space_id,
            query_type="analytical", ...
        )
        return results
    ...
```

### D3: 降级链路径切换

```python
# query_router.py _degrade()
DEGRADATION_PATHS = {
    "layer_r": lambda self, q, s, k: self._rrf._search_layer_r(q, s, k),
    "layer_s": lambda self, q, s, k: self._rrf._search_layer_s(q, s, k, memory_types=["entity", "mental_model"]),
    "bm25": lambda self, q, s, k: self._rrf._search_bm25(q, s, k),
    "bundle": lambda self, q, s, k: self._rrf._search_layer_s(q, s, k, memory_types=["entity"]),
    "temporal": lambda self, q, s, k: self._rrf._search_temporal(q, s, k),
}

async def _degrade(self, query, space_id, query_type, top_k):
    chain = DEGRADATION_CHAINS.get(query_type, ["layer_r", "bm25", "layer_s"])
    all_results = []
    for step_name in chain:
        search_fn = DEGRADATION_PATHS.get(step_name)
        if search_fn:
            results = await search_fn(self, query, space_id, top_k)
            all_results.extend(results)
            if len(all_results) >= MIN_RESULTS_THRESHOLD:
                break
    return all_results
```

### D4: 后置排序 + 短路优化

```python
# query_router.py route()
async def route(self, query, space_id, ...):
    # 1. 全量 RRF 融合 (保持当前架构)
    all_results = await self._rrf.fuse(query, space_id, query_type, ...)

    # 2. 短路判定
    if self._can_short_circuit(all_results, disposition):
        high_layer_results = [r for r in all_results if r.cognitive_layer in ("opinion", "semantic")]
        if high_layer_results and high_layer_results[0].get("confidence", 0) >= 0.7:
            # 短路返回高层结果
            return high_layer_results[:top_k]

    # 3. 正常返回全部结果 (按认知层优先级排序)
    return all_results[:top_k]

def _can_short_circuit(self, results, disposition) -> bool:
    if disposition and disposition.evidence_demand > 0.8:
        return False  # 高证据需求禁止短路
    if disposition and disposition.abstraction_preference > 0.7:
        return True   # 高抽象偏好允许短路
    return True  # 默认允许
```

### D5: DispositionProfile 7 维度完整实现

```python
# models.py apply_dynamic_weight()
def apply_dynamic_weight(rrf_score: float, memory_type: str, disposition: DispositionProfile) -> float:
    weight = BASE_TYPE_WEIGHTS.get(memory_type, 1.0)

    # abstraction_preference: 高值提升 mental_model/opinion，降低 fragment
    if disposition.abstraction_preference > 0.7:
        if memory_type in ("mental_model", "opinion"):
            weight *= 1.0 + (disposition.abstraction_preference - 0.5)
        elif memory_type == "fragment":
            weight *= 0.5 + (1.0 - disposition.abstraction_preference)

    # thoroughness: 高值提升 fragment/observation (全面检索)
    if disposition.thoroughness > 0.7:
        if memory_type in ("fragment", "observation"):
            weight *= 1.0 + (disposition.thoroughness - 0.5) * 0.5

    # evidence_demand: 高值提升 entity/rule (有证据支撑的类型)
    if disposition.evidence_demand > 0.7:
        if memory_type in ("entity", "rule"):
            weight *= 1.0 + (disposition.evidence_demand - 0.5) * 0.3
        elif memory_type == "fragment":
            weight *= 0.7  # 碎片证据不足，降权

    # recency_bias: 高值提升近期记忆 (通过 temporal_proximity 间接实现)
    # 在 recall 结果排序时叠加 recency_bias 影响

    # risk_tolerance: 低值提升高 belief_status 节点
    if disposition.risk_tolerance < 0.3:
        if memory_type in ("mental_model", "opinion"):
            weight *= 0.8  # 保守时降低主观判断权重

    # skepticism: 高值降低 mental_model 权重，提升 entity
    if disposition.skepticism > 0.7:
        if memory_type == "mental_model":
            weight *= 0.7
        elif memory_type == "entity":
            weight *= 1.2

    return rrf_score * weight
```

### D6: valid_from/valid_to 有效期过滤

```python
# rrf_fusion.py _search_temporal()
async def _search_temporal(self, query, space_id, top_k, ...):
    nodes = await self._repo.query_nodes(space_id=space_id, limit=200)

    now = datetime.now(timezone.utc)
    valid_nodes = []
    for n in nodes:
        # 有效期过滤
        if n.valid_from and n.valid_from > now.isoformat():
            continue  # 尚未生效
        if n.valid_to and n.valid_to < now.isoformat():
            continue  # 已过期
        valid_nodes.append(n)

    # 时序邻近性评分
    ...
```

### D7: BASE_TYPE_WEIGHTS 修正

```python
BASE_TYPE_WEIGHTS = {
    "mental_model": 2.0,    # 3.0 → 2.0
    "opinion": 1.3,         # 2.5 → 1.3
    "commitment": 1.4,      # 1.9 → 1.4
    "entity": 2.0,          # 保持
    "rule": 2.0,            # 保持
    "constraint": 1.6,      # 1.8 → 1.6
    "observation": 1.5,     # 保持
    "procedure": 1.8,       # 保持
    "task_state": 1.3,      # 1.6 → 1.3
    "episode": 1.2,         # 保持
    "self_experience": 1.1, # 保持
    "fragment": 0.5,        # 1.0 → 0.5
}
```

## 验收标准

### 04_locomo 补充验收

| 轨迹 | 验收点 | 通过条件 |
|------|--------|---------|
| T1-EXT | BM25 中文检索验证 | "深圳" 查询命中含 "深圳" 的节点 |
| T2-EXT | 多跳推理验证 | "cloud" + "k8s" 查询返回关联实体 |
| T3-EXT | 时序推理验证 | 返回 valid_to 为空或 > now 的最新策略 |
| T4-EXT | Analytical 查询验证 | analytical 查询返回非空结果 |
| T9-NEW | 降级链路径切换验证 | Layer-R 失败时自动切换到 BM25 |
| T10-NEW | 短路优化验证 | opinion 层高置信结果时，不返回 perception 层 |

### 08_qul 补充验收

| 轨迹 | 验收点 | 通过条件 |
|------|--------|---------|
| T2-EXT | Disposition 7 维影响验证 | 不同 disposition profile 产生不同排序 |
| T9-NEW | evidence_demand 过滤验证 | evidence_demand=0.9 时 fragment 权重降低 |

## 实施计划

| 阶段 | 内容 | 依赖 |
|------|------|------|
| Phase 1 | Analytical 查询修复 (D2) + BASE_TYPE_WEIGHTS 修正 (D7) | 无 |
| Phase 2 | FTS5 双表 BM25 索引 (D1) | Phase 1 |
| Phase 3 | 降级链路径切换 (D3) + 短路优化 (D4) | Phase 2 |
| Phase 4 | DispositionProfile 7 维度 (D5) + valid_from/valid_to (D6) | Phase 3 |

## 风险

1. FTS5 索引需要额外的 SQLite 数据库和同步机制，增加存储复杂度
2. BASE_TYPE_WEIGHTS 修正可能影响现有测试的预期结果
3. 短路优化可能导致某些场景下遗漏重要低层证据
