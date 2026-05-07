# Agent Memory GAP 修复 Round 4 — 2026-05-04

## 关键发现

### 🔴 关键 GAP 1: CorrectionPropagation 使用错误的边查询方法

**问题**: `_get_propagation_neighbors()` 调用 `repo._store.get_mutual_index_edges()` 查询互索引边（EXTRACTED_FROM/SUPPORTED_BY 等），但传播需要 SUMMARIZED_AS/CONSOLIDATED_INTO/COGNITIVE_RELATES_TO 认知边。**更正传播功能实质上是断路的。**

**修复**: 改用 `repo.query_cognitive_edges()` 双向查询（from_id + to_id），逐边类型遍历。

**决策**: 传播边类型 = `{SUMMARIZED_AS, CONSOLIDATED_INTO, COGNITIVE_RELATES_TO}`，与设计文档一致。

### 🔴 关键 GAP 2: KuzuDB 缺失 SUMMARIZED_AS/LEARNED_INTO/COGNITIVE_RELATES_TO 边表

**问题**: `consolidation_engine` 创建 SUMMARIZED_AS 和 LEARNED_INTO 边，`lifecycle.py` 创建 COGNITIVE_RELATES_TO 边，但这些边类型在 KuzuDB schema 中不存在，导致边创建失败。

**修复**: 在 KuzuDB schema 中添加三个新边表，表名统一为 UPPER_SNAKE_CASE（与 Cypher 关系类型一致）。

**决策**: 所有认知边表名使用 UPPER_SNAKE_CASE（如 `CONSOLIDATED_INTO` 而非 `ConsolidatedInto`），与 edge_type 字符串一致，避免映射错误。

### 🔴 关键 GAP 3: query_cognitive_edges 时间字段不匹配

**问题**: `query_cognitive_edges` 统一使用 `r.created_at` 返回时间字段，但 CONSOLIDATED_INTO 表使用 `consolidated_at`，SUPERSEDES 表使用 `superseded_at`。查询失败被 `except` 静默吞掉，导致 CONSOLIDATED_INTO 和 SUPERSEDES 边永远查不到。

**修复**: 添加 `edge_time_fields` 映射，根据边类型使用不同的时间字段。

### 🟡 GAP 4: CognitiveEdge 缺少 from_dict 方法

**问题**: `repository.query_cognitive_edges()` 调用 `CognitiveEdge.from_dict(d)`，但 CognitiveEdge 类没有 `from_dict` 类方法。

**修复**: 添加 `CognitiveEdge.from_dict()` 类方法。

### 🟡 GAP 5: 设计文档缺少检索逻辑时序图

**修复**: 在 memory-api.md 中添加：
- §14 Recall 检索逻辑时序图（10 步完整管线）
- §14.2 DispositionProfile 加载策略详解
- §15 Reflect 混合矛盾检测时序图
- §16 认知边类型完整清单（含时间字段映射）

### 🟡 GAP 6: 更正传播文档边类型描述错误

**修复**: memory-lifecycle.md §10 从 "基于 SUPERSEDES 边和 COGNITIVE_RELATES_TO 边" 修正为 "基于 SUMMARIZED_AS、CONSOLIDATED_INTO、COGNITIVE_RELATES_TO 边"。

## 端到端验证结果

12/12 测试全部通过（100%）：

| 测试 | 结果 |
|------|------|
| T1: Single-hop Recall | ✅ (0.60) |
| T2: Multi-hop Reasoning | ✅ (1.00) |
| T3: Temporal Reasoning | ✅ (1.00) |
| T4: Contradiction Detection | ✅ (1.00) |
| T5: Consolidation & Upgrade | ✅ (1.00) |
| T6: Supersede & Correction | ✅ (1.00) |
| T7: Forgetting Protection | ✅ (1.00) |
| T8: Attributes & Metadata | ✅ (1.00) |
| T9: DispositionProfile Dynamic Weight | ✅ (1.00) |
| T10: DreamCycle 5-Phase | ✅ (1.00) |
| T11: Correction Propagation | ✅ (1.00) [新增] |
| T12: Cognitive Edge Query | ✅ (1.00) [新增] |

## 修改文件清单

### 代码修改
- `ontology_engine/engine/cognitive/correction_propagation.py` — 修复边查询方法
- `ontology_engine/engine/cognitive/models.py` — 添加 CognitiveEdge.from_dict()
- `ontology_engine/storage/graph/kuzu_store.py` — 添加边表、补全 edge_table_map、修复时间字段查询

### 文档更新
- `docs/02-design/agent-memory/memory-api.md` — 添加检索时序图、混合矛盾检测、边类型清单
- `docs/02-design/agent-memory/memory-lifecycle.md` — 修正更正传播边类型
- `docs/02-design/agent-memory/reflect-agent.md` — 添加混合矛盾检测章节
- `docs/02-design/agent-memory/consolidation-engine.md` — 补充边类型选择逻辑

### 评估脚本
- `examples/case8_locomo_memory_eval/run_eval.py` — 添加 T11/T12 测试轨迹

## 待讨论决策点

1. **T1 Single-hop Recall 得分偏低 (0.60)**: 5 个查询中只有 3 个命中。原因可能是向量检索对短查询的召回不足，或 remember 时未充分提取实体属性。是否需要优化 embedding 策略？

2. **MCP Schema 参数覆盖**: 当前 MCP 工具只暴露 L1/L2 参数，L3 参数（evidence_depth, as_of, token_budget, disposition_override 等）只能通过 REST API 使用。是否需要在 MCP Schema 中逐步暴露更多 L3 参数？

3. **CO_OCCURS_WITH 和 COG_SUPPORTED_BY 的时间字段**: 这两个边表没有 created_at 字段，query_cognitive_edges 查询时返回 None。是否需要为这些边表添加 created_at 字段？
