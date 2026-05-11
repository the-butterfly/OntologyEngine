# RFC-020~025 代码审查修复决策记录

**日期**: 2026-05-10
**范围**: RFC-020 ~ RFC-025 全面代码审查后的修复

## 关键决策

### D1: apply_dynamic_weight 双重计算 Bug 修复

**问题**: `apply_dynamic_weight(rrf_score, memory_type, disposition)` 函数内部 `weight = BASE_TYPE_WEIGHTS.get(memory_type, 1.0)` 重新取了基础权重，而调用方传入的 `rrf_score` 已经是 `BASE_TYPE_WEIGHTS` 的值，导致双重计算（3.0 * 3.0 = 9.0 而非 3.0）。

**决策**: 将函数内部 `weight` 初始化为 `1.0`，由调用方负责传入正确的基础权重。函数只负责计算动态调整系数。

**影响文件**: models.py, kuzu_store.py (compute_dynamic_weights)

### D2: kuzu_store.py compute_dynamic_weights 统一为 7 维度

**问题**: kuzu_store.py 中存在独立的 3 维度 `compute_dynamic_weights` 实现（skepticism, empathy, risk_tolerance），与 models.py 的 7 维度 `apply_dynamic_weight` 冲突。

**决策**: 将 kuzu_store.py 的 `compute_dynamic_weights` 改为委托 models.py 的 `apply_dynamic_weight`，消除双版本。

### D3: _degrade() 降级链单路搜索

**问题**: `_degrade()` 每步都调用 `self._rrf.fuse(query_type="mixed")`，降级链形同虚设。

**决策**: 使用 `DEGRADATION_PATHS` 映射调用单路搜索方法（如 `_search_layer_r`, `_search_bm25_fts5` 等）。

### D4: _mark_downstream_stale 递归→BFS

**问题**: 递归实现无全局 visited 集合，有环图中会重复处理节点；MAX_CASCADE_NODES 语义错误。

**决策**: 改为 BFS 实现，添加全局 `visited` 集合，`len(visited) >= MAX_CASCADE_NODES` 时停止。

### D5: 硬删除条件修正

**问题**: 代码使用 `len(node.source_fragment_ids) == 0`，RFC 要求 `strength < 0.01 且 proof_count == 0`。

**决策**: 改为 `node.strength < 0.01 and node.proof_count == 0`。`proof_count` 包含间接证据（COG_SUPPORTED_BY 边计数），比 `source_fragment_ids`（仅直接来源）更准确。

### D6: CorrectionPropagation 差异化处理

**问题**: 所有下游统一 transition 到 pending_review，无差异化。

**决策**: 根据 memory_type 设置不同属性标记：
- mental_model → is_stale=True
- entity → needs_attribute_update=True
- observation → needs_reinduction=True
- rule → needs_revalidation=True
- commitment → needs_reassessment=True
- procedure → needs_reverification=True

### D7: QUL 接入 recall 主流程

**问题**: QUL 模块存在但完全未接入 recall 流程。

**决策**: 在 memory_api._recall() 中：
1. 优先使用 QUL 提取约束和推断 query_type
2. QUL 不可用时降级到 detect_query_type
3. rank_score 计算后调用 apply_constraint_boost 重排序

### D8: valid_from/valid_to 统一过滤

**问题**: 所有非 temporal 路径可能返回已过期节点。

**决策**: 在 rrf_fusion.py 的 fuse() 返回前添加 `_filter_validity()` 过滤。

### D9: OCC 原子更新

**问题**: update_node_with_occ 使用 read-then-write 两步操作，存在竞态条件。

**决策**: 在 kuzu_store.py 添加 `update_cognitive_node_with_occ` 方法，使用单条 Cypher `WHERE n.version = $expected_version SET n.version = n.version + 1` 原子执行。

### D10: abstraction_preference 降权目标修正

**问题**: 代码降权 entity/rule，RFC 设计降权 fragment。

**决策**: 对齐 RFC-023 D5，高抽象偏好时降权 fragment，提升 mental_model/opinion。添加 `> 0.7` 阈值条件。

### D11: _remember() 接入 IngestionService 双层写入

**问题**: `_remember()` 直接使用 `self._repo.create_node()` 进行单层写入，未利用 IngestionService 的 fragment + cognitive node 双层写入能力。

**决策**: 当 `self._ingestion` 可用时，优先调用 `self._ingestion.ingest()` 进行双层写入（Layer-R fragment + Layer-S cognitive node + COG_SUPPORTED_BY 边），然后补充 IngestionService 不处理的字段（belief_status, confidence, visibility, valid_from/valid_to, model_domain 等）。IngestionService 不可用时回退到直接创建路径。

**影响文件**: memory_api.py

### D12: factory.py 注入 QUL

**问题**: MemoryAPI 构造函数接收 `qul` 参数，但 factory.py 未创建和注入 QueryUnderstandingLayer。

**决策**: 在 `create_memory_api()` 中创建 `QueryUnderstandingLayer(repository=repo, llm_call=llm_call_fn)` 并作为 `qul` 参数传入 MemoryAPI。

**影响文件**: factory.py

### D13: model_domain 自动映射

**问题**: `_remember()` 创建 CognitiveNode 时未设置 `model_domain` 字段。

**决策**: 添加 `_infer_model_domain(memory_type)` 方法，基于 memory_type 自动映射：
- entity/rule/constraint/observation/fragment → "world"
- mental_model/opinion/self_experience → "self"
- commitment/task_state/procedure/episode → "task"

**影响文件**: memory_api.py

### D14: RetrievalResult 写入 valid_from/valid_to 到 metadata

**问题**: rrf_fusion.py 的搜索方法构建 RetrievalResult 时未将节点的 valid_from/valid_to 写入 metadata，导致 `_filter_validity()` 方法形同虚设。

**决策**: 在 `_search_layer_r`, `_search_layer_s`, `_search_bm25`, `_search_temporal` 四个搜索方法中，构建 RetrievalResult 时添加 metadata 字典，包含 valid_from, valid_to, belief_status。

**影响文件**: rrf_fusion.py

### D15: compute_temporal_weight 替代硬编码公式

**问题**: `_recall()` 中使用硬编码公式 `0.7 + 0.3 * tp` 计算时间权重，未利用 DispositionProfile 的 recency_bias 维度。

**决策**: 导入并使用 `compute_temporal_weight(recency_bias)` 替代硬编码公式，recency_bias 从 profile 对象获取（默认 0.5）。

**影响文件**: memory_api.py

### D16: strategy_adjustment 参数透传

**问题**: StrategyAdjustment 数据类仅在 QUL 内部使用，未传递到 QueryRouter/RRF 层。

**决策**: 在 `RRFFusionEngine.fuse()` 和 `QueryRouter.route()` 中添加 `strategy_adjustment` 参数，透传到 fuse() 中应用 boost_weights 和 temporal_window_days 过滤。

**影响文件**: rrf_fusion.py, query_router.py

### D17: CorrectionPropagation 添加 signal 参数

**问题**: `propagate()` 方法无 signal 参数，调用方（correct_memory）使用 try/except TypeError 降级处理。

**决策**: 添加 `signal: str = ""` 参数到 propagate() 方法和 PropagationResult dataclass。移除调用方的 TypeError 回退。

**影响文件**: correction_propagation.py, memory_api.py

### D18: stale_reason 添加 upstream_ 前缀

**问题**: `_mark_downstream_stale` 设置 stale_reason 时直接使用 reason 原值，无法区分上游传播和本地标记。

**决策**: 改为 `f"upstream_{reason}"`，使 stale_reason 带有来源标识。

**影响文件**: lifecycle.py

### D19: approve_memory 提升 feedback_weight 到 1.0

**问题**: approve_memory 仅设置 confidence=1.0，未设置 feedback_weight，导致审批后的记忆仍可能被遗忘引擎衰减。

**决策**: 在 approve 分支添加 `node.feedback_weight = 1.0`，确保审批后的记忆受到反馈权重保护。

**影响文件**: memory_api.py

### D20: ConsolidationEngine 写入 consolidation_reasoning + COG_SUPPORTED_BY 边

**问题**: ConsolidationEngine 创建/更新节点时未写入 consolidation_reasoning 字段，且仅创建 CONSOLIDATED_INTO/SUMMARIZED_AS 边，缺少 COG_SUPPORTED_BY 边。

**决策**:
1. execute_create() 中添加 `consolidation_reasoning` 字段
2. execute_create() 中为每个 fragment 添加 COG_SUPPORTED_BY 边（Layer-R → Layer-S 支撑链接）
3. execute_update() 中设置 consolidation_reasoning

**影响文件**: consolidation_engine.py

### D21: apply_constraint_boost 后置过滤

**问题**: apply_constraint_boost 只做 boost 乘法和排序，未实现 StrategyAdjustment 中定义的 min_proof_count, min_belief_status, require_evidence 过滤。

**决策**: 在 boost 和排序后，遍历 strategy.adjustments 执行后置过滤：
- min_proof_count > 0: 过滤 proof_count 不达标的条目
- min_belief_status: 按信念状态等级过滤
- require_evidence: 过滤无证据的条目

**影响文件**: query_understanding_layer.py

### D22: update_node 使用 version 字段做 OCC

**问题**: update_node 的 OCC 版本检查使用 `len(history)` 而非 `version` 字段，与 update_node_with_occ 的实现不一致。

**决策**: 改为优先读取 `version` 字段，回退到 `len(history)`，确保 OCC 版本检查统一。

**影响文件**: repository.py

### D23: LLM 反思循环实现

**问题**: reflect_agent.py 的 `_run_reflection_loop` 中，LLM 可用时仍只使用规则检测，未实现 LLM tool-calling 反思。

**决策**: 添加 `_run_llm_reflection()` 方法，在规则检测后调用 LLM 进行深度分析：
1. 将搜索结果构建为上下文（最多 20 条，每条截断 200 字符）
2. 使用 JSON 格式 prompt 要求 LLM 返回 insights 和 contradictions
3. 验证 LLM 返回的 evidence_ids/node_ids 是否在 available_ids 集合中
4. 合并 LLM 结果到规则结果中
5. method 标记为 "hybrid"（LLM + 规则）或 "rule_only"（纯规则）

**影响文件**: reflect_agent.py

### D24: IngestionService memory_type 传递修复

**问题**: `_make_fragment_node()` 调用时未传递 `memory_type` 参数，导致 fragment 节点缺少 memory_type 字段。

**决策**: 在 ingest() 方法中调用 `_make_fragment_node()` 时显式传递 `memory_type="fragment"`。

**影响文件**: ingestion_service.py

### D25: _make_cognitive_node cognitive_layer 默认值修正

**问题**: `_make_cognitive_node()` 使用 `cognitive_layer="memory"` 作为默认值，但 "memory" 不是有效的 cognitive_layer 值。

**决策**: 改为 `cognitive_layer="semantic"` 作为默认值，使用 setdefault 模式允许调用方覆盖。

**影响文件**: ingestion_service.py

## 验收结果

**日期**: 2026-05-10
**验证方式**: 真实数据 + LLM 端点验证

| 修复项 | 验证结果 |
|--------|----------|
| P0-1 IngestionService 双层写入 | PASS |
| P0-2 QUL 注入 | PASS |
| P0-3 valid_from/valid_to metadata | PASS |
| P0-4 compute_temporal_weight | PASS |
| P0-5 strategy_adjustment 参数 | PASS |
| P0-6 model_domain 自动映射 | PASS |
| P1-1 signal 参数 | PASS |
| P1-2 upstream_ 前缀 | PASS |
| P1-3 feedback_weight=1.0 | PASS |
| P1-4 consolidation_reasoning | PASS |
| P1-5 后置过滤 | PASS |
| P1-6 version OCC | PASS |
| P1-7 LLM 反思循环 | PASS (method=hybrid, insights=2) |

**LLM 端点**: http://localhost:9528/v1, model=sensenova/sensenova-6.7-flash-lite
**质量门禁**: ruff check PASS, pytest 247/247 PASS

---

## 第二轮审查修复（2026-05-11）

**范围**: RFC-020 ~ RFC-025 全面代码审查后的 HIGH 级 BUG 修复

### D26: rank_score 计算缺少 temporal_proximity 混合

**问题**: `_recall()` 中 rank_score 公式为 `score * type_weight * tw`，直接将 tw 作为乘法因子。RFC-023 D5 规定公式为 `score * type_weight * ((1 - tw) + tw * tp)`，tw 应为混合系数而非直接乘数。

**决策**: 修改为 `score * type_weight * ((1 - tw) + tw * tp)`，确保 tw 控制时间因素的影响力比例。

**影响文件**: memory_api.py

### D27: _qul_strategy 未传递到 route()

**问题**: `_recall()` 中 `_qul_strategy` 变量被计算后从未传递给 `self._router.route()`，导致 QUL 约束对检索路径权重和时间窗口的影响完全丢失。

**决策**: 在 `route()` 调用中添加 `strategy_adjustment=_qul_strategy` 参数。同时初始化 `_qul_strategy = None` 避免分支外的 NameError。

**影响文件**: memory_api.py

### D28: disposition 未传递到 route()

**问题**: `_recall()` 中 profile（DispositionProfile）的计算在 `route()` 调用之后，导致 route() 无法使用 disposition 进行动态权重调整和短路判定。

**决策**: 将 profile 计算逻辑提前到 route() 调用之前，并在 route() 中添加 `disposition=profile` 参数。

**影响文件**: memory_api.py

### D29: TRIGGER_BELIEFS 缺少 "rejected"

**问题**: `CorrectionPropagation` 的 `TRIGGER_BELIEFS = {"contradicted", "superseded"}` 缺少 "rejected"。当 `approve_memory(action="reject")` 触发策略性遗忘后，传播不会执行。

**决策**: 将 TRIGGER_BELIEFS 改为 `{"contradicted", "superseded", "rejected"}`。

**影响文件**: correction_propagation.py

### D30: _mark_downstream_stale 仅查 from_id 方向的边

**问题**: `_mark_downstream_stale` 只查询 `from_id=nid` 方向的边，对 COGNITIVE_RELATES_TO 双向边会遗漏反向连接的节点。CorrectionPropagation._get_propagation_neighbors() 已正确处理双向查询。

**决策**: 在正向边处理后，额外查询 `to_id=nid` 的反向边，对 COGNITIVE_RELATES_TO 类型的边执行相同的 stale 标记。

**影响文件**: lifecycle.py

### D31: _search_analytical 忽略 strategy_adjustment 和 _filter_validity

**问题**: `fuse()` 对 analytical 查询提前返回，跳过了 strategy_adjustment 应用和 _filter_validity 过滤。

**决策**: analytical 路径先执行搜索，再应用 strategy_adjustment boost_weights 和 _filter_validity，最后返回。

**影响文件**: rrf_fusion.py

### D32: _search_layer_s_broad/_search_bundle/_search_bm25_fts5(fragment) 缺少 metadata

**问题**: 这三个方法构建的 RetrievalResult 未设置 metadata（valid_from/valid_to/belief_status），导致 _filter_validity() 对这些路径的结果无效。

**决策**: 为所有三个方法的 RetrievalResult 添加 metadata 字典，包含 valid_from, valid_to, belief_status。

**影响文件**: rrf_fusion.py

### 第二轮验收结果

**日期**: 2026-05-11
**验证方式**: 真实数据 + LLM 端点验证

| 修复项 | 验证结果 |
|--------|----------|
| D26 rank_score 公式修正 | PASS |
| D27 _qul_strategy 传递 | PASS |
| D28 disposition 传递 | PASS |
| D29 TRIGGER_BELIEFS + rejected | PASS |
| D30 _mark_downstream_stale 双向 | PASS |
| D31 analytical 路径补全 | PASS |
| D32 metadata 补全 | PASS |

**E2E 验证**: 24/27 PASS（3 个非核心失败：recall content 格式、验证脚本参数名、dream 方法缺失）
**质量门禁**: ruff check PASS, pytest 247/247 PASS
**LLM 端点**: http://localhost:9528/v1, model=sensenova/sensenova-6.7-flash-lite

### 遗留问题（MEDIUM/LOW 优先级）

| 优先级 | 问题 | RFC |
|--------|------|-----|
| MEDIUM | ExtractionPipeline 提取结果被丢弃，未创建节点/边 | RFC-020 D1 |
| MEDIUM | _extract_with_rules 对中文内容无效 | RFC-020 G7 |
| MEDIUM | MemoryAPI 缺少 dream() 方法 | RFC-022 D5 |
| MEDIUM | apply_strategic_forgetting 不检查 _is_protected() | RFC-022 D2 |
| MEDIUM | 两套 strength 计算公式并存 | RFC-024 D5 |
| LOW | evidence_demand/empathy 缺少 > 0.7 阈值 | RFC-023 D5 |
| LOW | CorrectionPropagation 差异化标记缺 stale_reason/stale_from | RFC-022 D4 |
| LOW | correct_memory 新节点 version 硬编码为 1 | RFC-024 D1 |
| LOW | fragment_id 前缀 "frag:" vs RFC "mem:fragment:" | RFC-020 D1 |

---

## 第三轮修复：线程安全 + 遗留问题（2026-05-11）

**范围**: 深层并发风险修复 + MEDIUM/LOW 遗留问题

### D33: MemoryAPISingleton 线程安全

**问题**: `MemoryAPISingleton.get_or_create()` 无锁保护，多协程并发调用可能创建多个实例。

**决策**: 添加 `asyncio.Lock` 类变量 `_lock`，`get_or_create()` 和 `close()` 均在 `async with cls._lock` 内执行。对于多 worker 部署（gunicorn -w N），每个 worker 进程有独立的 Python 解释器和事件循环，Lock 只协调同一进程内的协程。跨进程的 KuzuDB 文件锁由 R2 的 `_execute_lock` 保护。

**影响文件**: factory.py

### D34: KuzuGraphStore 全局执行锁

**问题**: 所有 `self._conn.execute()` 调用无 asyncio.Lock 保护。Kuzu Python binding 不是线程安全的，并发 execute() 可能导致数据损坏或段错误。

**决策**:
1. 添加 `self._execute_lock: asyncio.Lock` 实例变量
2. 创建 `async def _execute(query, parameters)` 辅助方法，在锁内调用 `self._conn.execute()`
3. 将全部 82 处 `self._conn.execute()` 调用替换为 `await self._execute()`
4. 对于 read-modify-write 操作（update_cognitive_node_history, update_cognitive_node_belief），在方法层面使用 `async with self._execute_lock` 包裹整个读写序列

**影响文件**: kuzu_store.py

### D35: ReflectionJobStore 异步锁保护

**问题**: `_jobs` 字典无锁保护，并发读写可能导致数据不一致。

**决策**: 添加 `self._lock: asyncio.Lock`，所有方法（create_job, get_job, update_progress, set_partial_results, set_error）改为 `async` 并在 `async with self._lock` 内执行。同步调用点全部改为 `await`。

**影响文件**: memory_api.py, test_memory_api.py

### D36: read-modify-write 原子化

**问题**: `update_cognitive_node_history` 和 `update_cognitive_node_belief` 执行两步操作（先读后写），两步之间可能有其他协程插入导致丢失更新。

**决策**: 这两个方法不再通过 `await self._execute()` 调用，而是在方法层面直接获取 `_execute_lock`，在锁内执行读取和写入两步操作。这样整个 read-modify-write 序列是原子的。

**影响文件**: kuzu_store.py

### D37: ExtractionPipeline 提取结果创建节点/边

**问题**: `CognitiveIngestionService.ingest()` 调用 `self._pipeline.extract(content)` 获取实体和关系，但结果仅用于计数，未实际创建节点和边。

**决策**: 在 extract() 后遍历 entities（最多 10 个）调用 `_resolve_or_create_entity()` 创建或复用实体节点；遍历 relations（最多 5 个）创建 COGNITIVE_RELATES_TO 边。`_resolve_or_create_entity()` 先通过内容去重查询现有节点，不存在时创建新节点。

**影响文件**: ingestion_service.py

### D38: MemoryAPI.dream() 方法

**问题**: RFC-022 D5 要求 MemoryAPI 暴露 `dream()` 方法，但代码中缺失。

**决策**: 添加 `async def dream(space_id)` 方法，调用 `self._dream.run(space_id)` 并返回 5 阶段结果摘要（contradictions, expired, orphans_cleaned, links_enhanced, graph_completed）。

**影响文件**: memory_api.py

### D39: apply_strategic_forgetting 保护检查

**问题**: `apply_strategic_forgetting()` 未检查 `_is_protected()`，导致受保护的记忆（feedback_weight >= 0.8 或 belief_status in {"accepted", "confirmed"}）仍可能被遗忘引擎衰减。

**决策**: 在方法开头添加 `if self._is_protected(node): return`，跳过受保护节点的衰减。

**影响文件**: lifecycle.py

### D40: 统一 strength 计算公式

**问题**: `MemoryAPI._compute_strength()` 和 `lifecycle.compute_memory_strength()` 使用不同的公式，可能导致同一节点在不同上下文中得到不同的 strength 值。

**决策**: `_compute_strength()` 改为委托 `compute_memory_strength()` 计算核心值，同时保留 breakdown 字典用于诊断。breakdown 中的各维度值仍独立计算用于展示。

**影响文件**: memory_api.py

### D41: evidence_demand/empathy 阈值条件

**问题**: `apply_dynamic_weight()` 中 evidence_demand 和 empathy 的调整无条件生效，RFC-023 D5 要求 `> 0.7` 时才触发。

**决策**: 添加 `if val > 0.7:` 条件判断，evidence_demand > 0.7 时才对 entity/rule 提权、fragment 降权；empathy > 0.7 时才对 observation/self_experience 提权。

**影响文件**: models.py

### D42: CorrectionPropagation stale_reason/stale_from

**问题**: 差异化标记仅设置类型特定属性（is_stale, needs_attribute_update 等），缺少 stale_reason 和 stale_from 字段，无法追踪标记来源。

**决策**: 在差异化标记后添加 `target.attributes["stale_reason"] = f"upstream_{source.belief_status}"` 和 `target.attributes["stale_from"] = source_node_id`。

**影响文件**: correction_propagation.py

### D43: correct_memory 新节点 version 递增

**问题**: `correct_memory()` 创建新节点时 `version=1`，应继承旧节点的 version 并递增。

**决策**: 改为 `version=old_node.version + 1`，确保版本链连续。

**影响文件**: memory_api.py

### 第三轮验收结果

**日期**: 2026-05-11
**验证方式**: ruff check + pytest

| 修复项 | 验证结果 |
|--------|----------|
| D33 MemoryAPISingleton 线程安全 | PASS |
| D34 KuzuGraphStore 执行锁 | PASS (82 处替换) |
| D35 ReflectionJobStore 异步锁 | PASS |
| D36 read-modify-write 原子化 | PASS |
| D37 ExtractionPipeline 节点创建 | PASS |
| D38 dream() 方法 | PASS |
| D39 遗忘保护检查 | PASS |
| D40 strength 公式统一 | PASS |
| D41 evidence_demand/empathy 阈值 | PASS |
| D42 stale_reason/stale_from | PASS |
| D43 correct_memory version 递增 | PASS |

**质量门禁**: ruff check PASS, pytest 1001/1001 PASS

### 残留风险

| 风险 | 说明 | 缓解措施 |
|------|------|----------|
| 多 worker 部署 | gunicorn -w N 每个 worker 独立打开同一 KuzuDB 文件 | R2 的 _execute_lock 保护单进程内并发；跨进程需 KuzuDB 文件锁或改用 read-only 模式 |
| fragment_id 前缀不一致 | 代码用 "frag:"，RFC 规定 "mem:fragment:" | 低优先级，不影响功能，后续统一 |
| _fragment_cache 无锁 | kuzu_store.py 的 _fragment_cache 字典在并发写入时可能丢失条目 | 缓存丢失仅导致重复查询，不影响数据正确性 |
