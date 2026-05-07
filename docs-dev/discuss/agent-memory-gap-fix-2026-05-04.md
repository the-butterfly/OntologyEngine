# Agent Memory GAP 修复 — 2026-05-04

## 背景

对 `docs/02-design/agent-memory/` 6 份设计文档与 `ontology_engine/engine/cognitive/` 14+ 源文件进行逐项比对，发现 5 个临界 GAP + 5 个遗留项。

## 第一轮修复：5 个临界 GAP

### GAP1: CognitiveNode 缺少 attributes 字段

**问题**: 设计要求 `attributes: MAP(STRING, STRING)` 存储类型特有字段（fact_type, opinion_type 等），但 CognitiveNode 模型没有此字段。

**修复**:
- `models.py`: CognitiveNode 添加 `attributes: dict[str, str]`
- `kuzu_store.py`: KuzuDB schema 添加 `attributes JSON` 列
- `kuzu_store.py`: upsert_cognitive_node / get_cognitive_node 支持 attributes
- `repository.py`: create_node / update_node 传递 attributes
- `memory_api.py`: 新增 `_extract_attributes()` 方法，按 memory_type 从 metadata 中提取允许的键

**设计决策**: attributes 仅存储白名单键（按 memory_type 过滤），不存储任意 metadata，防止字段膨胀。

### GAP2: recall TYPE_WEIGHTS 与 BASE_TYPE_WEIGHTS 不一致

**问题**: recall 用了简化版权重 `{mental_model:2.0, ...}`，与 rrf_types.py 的 `BASE_TYPE_WEIGHTS` `{mental_model:3.0, ...}` 不同步。

**修复**:
- `memory_api.py`: 删除内联 TYPE_WEIGHTS，改为 `from rrf_types import BASE_TYPE_WEIGHTS`
- recall 中 `BASE_TYPE_WEIGHTS.get(mt, 1.0)` 替代原硬编码

**设计决策**: 单一事实源，TYPE_WEIGHTS 只在 rrf_types.py 维护。

### GAP3: 信念修正规则引擎未实际执行

**问题**: 7 条 DEFAULT_BELIEF_REVISION_RULES 定义了但从未在 reflect 流程中调用，矛盾节点一律 `transition_belief("pending_review")`。

**修复**:
- `memory_api.py`: 新增 `_apply_belief_revision_rules()` 方法
- reflect 流程中矛盾节点先尝试规则匹配，无匹配才 fallback 到 pending_review
- 规则 eval 使用 `{"__builtins__": {}}` 安全沙箱
- 同状态转换跳过（`new_status != node.belief_status`）

**设计决策**: 规则优先级排序（priority DESC），首条匹配即执行，未匹配则 fallback。

### GAP4: 遗忘保护条件与设计不一致

**问题**: 设计要求 `feedback_weight >= 0.9 → 永不遗忘`，但实现只检查 `mental_model + accepted`。

**修复**:
- `lifecycle.py`: `_is_protected()` 新增 `feedback_weight >= 0.9` 检查，优先于类型检查

### GAP5: REST /stats /types /audit 绕过 MemoryAPI 单例

**问题**: 三个 GET 端点各自 `KuzuGraphStore(kuzu_path)` 新建连接，可能多连接冲突。

**修复**:
- `api/routes/memory.py`: 三个端点统一使用 `api = await _get_memory_api(); repo = api._repo`
- 删除 `from ontology_engine.api.dependencies import get_storage` 等冗余导入

## 第二轮修复：5 个遗留项

### 遗留1: DispositionProfile 持久化 → 已建表，GAP 分析有误

**重新验证**: DispositionProfileNode 表已在 KuzuGraphStore 中创建（L260-L275），upsert/get/compute_weights 方法完整。之前的 GAP 分析标注"未建表"是错误的。

**状态**: 关闭，无需修复。

### 遗留2: Cross-Encoder 重排序实现

**问题**: 设计要求可选 Cross-Encoder 重排序（D-RRF-8），但完全未实现。

**修复**:
- `rrf_fusion.py`: 新增 `RerankerConfig` 配置类（enabled/strategy/model_path/top_k_for_rerank/top_k_after_rerank）
- `rrf_fusion.py`: `RRFFusionEngine.__init__` 新增 `reranker_config` 参数
- `rrf_fusion.py`: `fuse()` 方法末尾调用 `_rerank()`
- `rrf_fusion.py`: 新增 `_rerank()` / `_rerank_local_gguf()` / `_rerank_api()` 三方法
- 默认 `enabled=False, strategy="none"`，不影响现有行为
- local_gguf 策略：尝试 import llama_cpp，不存在则 warning 并 fallback
- api 策略：占位实现，返回候选原样

**设计决策**: 框架先行，模型运行时可选接入。默认关闭降低部署门槛（D-RRF-8）。

### 遗留3: 时序邻近性连续评分集成到 rank_score

**问题**: `_temporal_proximity_score()` 仅作排序 tie-breaker，未参与 rank_score 计算。设计要求连续评分影响最终排序。

**修复**:
- `memory_api.py`: 新增 `_compute_temporal_proximity()` 静态方法
- `memory_api.py`: rank_score 公式从 `score * type_weight` 改为 `score * type_weight * (0.7 + 0.3 * temporal_proximity)`
- recall 结果新增 `temporal_proximity` 字段

**设计决策**: 0.7/0.3 分配确保无时间戳的节点（tp=0.5）仍获得 85% 的基础分，时间敏感节点可获得最高 100% 加权。

### 遗留4: MCP oe_remember 补全 L2/L3 参数 + 修复 metadata 传递 bug

**问题**: MCP oe_remember 仅 6 参数，RememberRequest 有 18 字段。且 metadata 被接收但未传递给 api.remember()。

**修复**:
- `mcp/tools/memory.py`: oe_remember 新增 visibility/created_by/confidence/supersede_target/supersede_reason/schema_ref 6 个参数
- `mcp/tools/memory.py`: 修复 metadata 传递 bug（之前被接收但未传递）
- `mcp/tools/memory.py`: 修正 metadata 类型标注 `dict` → `dict[str, Any]`

**设计决策**: MCP 层暴露 L2 参数（visibility/confidence/schema_ref 等），L3 参数（valid_from/valid_to/occurred_at 等）通过 metadata 间接传递。

### 遗留5: 版本限制策略集成到遗忘流程

**问题**: `enforce_version_limit()` 函数已实现但从未被调用。

**修复**:
- `lifecycle.py`: `ForgettingEngine.apply_forgetting()` 末尾集成版本限制检查
- 遍历 space 内 entity 节点的 source_fragment_ids，对每个 entity_id 调用 enforce_version_limit
- 返回结果新增 `version_archived` 计数字段

## 端到端验证

新增 `tests/integration/test_e2e_knowledge_management.py`，9 个测试覆盖全部 10 个修复项：

| 测试 | 覆盖修复 |
|------|---------|
| test_gap1_attributes_field | GAP1: attributes 字段 |
| test_gap2_type_weights_unified | GAP2: TYPE_WEIGHTS 统一 |
| test_gap3_belief_revision_rules | GAP3: 信念修正规则 |
| test_gap4_forgetting_protection_feedback_weight | GAP4: 遗忘保护 |
| test_gap5_stats_uses_singleton_repo | GAP5: REST 单例 |
| test_end_to_end_knowledge_pipeline | 全流水线 |
| test_reranker_config_default_disabled | 遗留2: Cross-Encoder |
| test_temporal_proximity_in_rank_score | 遗留3: 时序评分 |
| test_version_limit_in_forgetting | 遗留5: 版本限制 |

**全量测试: 215 passed** (196 unit + 10 原有集成 + 9 新增)
