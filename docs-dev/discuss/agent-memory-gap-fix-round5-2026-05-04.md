# Agent Memory GAP 修复 Round 5 — 2026-05-04

## 关键发现与修复

### 🔴 关键 GAP 1: 向量检索完全未接入 recall 路径

**根因**: `RRFFusionEngine` 创建时 `vector_search_fn=None`，Layer-R 退化为全量节点返回。BM25 同样为 None，退化为子串匹配。ChromaDB 的 7 个 Collection 面向旧 EntityInstance 模型，CognitiveNode 内容未写入向量存储。

**修复**: 创建 `CognitiveVectorIndex` 类，提供四级降级策略：
1. OpenAI-compatible API (LMStudio/vLLM/OpenAI) — 通过 httpx 异步调用
2. sentence-transformers 本地模型 — 通过 SentenceTransformer.encode()
3. BM25 TF-IDF 评分 — 零依赖降级
4. 子串匹配 — RRF fallback

**配置体系**: 支持 config.yaml + 环境变量 + 构造器参数三级配置。新增 `embedding` 配置节，与现有 `llm` 配置节并列。

**内容增强**: 写入时将 content 丰富为 `[memory_type] tags | content`，帮助 embedding 模型捕获类型语义和标签上下文。

### 🔴 关键 GAP 2: 更正传播方向语义错误

**问题**: 之前的双向遍历导致 fragment 会因 observation 的信念变化而改变，这是不合理的——fragment 是原始数据，不应因上层归纳的信念变化而改变。

**修复**: 区分有向边和双向边的传播方向：
- `CONSOLIDATED_INTO` (fragment → observation): 仅正向传播
- `SUMMARIZED_AS` (observation → mental_model): 仅正向传播
- `COGNITIVE_RELATES_TO`: 双向传播

### 🟡 GAP 3: approve_memory 绕过信念状态机

**问题**: 直接设置 `node.belief_status` 而非使用 `transition_belief()`，且缺少 `pending_review` 前置状态检查。

**修复**:
1. 添加 `pending_review` 前置检查，非 pending_review 状态抛出 `INVALID_BELIEF_TRANSITION` 错误
2. 使用 `transition_belief()` 进行状态转换，确保合法性验证

### 🟡 GAP 4: DreamCycle Phase 2 TTL 过期节点不实际清理

**问题**: TTL 过期节点只被收集到 `expired` 列表返回，但 `apply_forgetting` 不处理这些节点（它只基于 strength 做决策）。

**修复**: TTL 过期且 belief_status 为 accepted 的节点，先 transition 到 `superseded`，再调用 `apply_forgetting`。

### 🟡 GAP 5: CO_OCCURS_WITH/COG_SUPPORTED_BY 缺少 created_at

**问题**: 这两个边表没有 `created_at` 字段，`query_cognitive_edges` 查询时因字段不存在而静默失败。

**修复**: 为两个边表添加 `created_at STRING` 字段。设计原则：**所有边必须有生效时间（created_at），但允许某些静态内容资产没有失效时间**。

### 🟢 GAP 6: MCP Schema 参数覆盖不足

**修复**: 从使用视角分析收益，新增以下高收益参数到 MCP Schema：

| 工具 | 新增参数 | 收益 |
|------|---------|------|
| oe_remember | visibility, confidence, supersede_target, supersede_reason | 隐私控制、质量标注、知识更新核心 |
| oe_recall | evidence_depth, as_of, token_budget, disposition_override | 深度证据链、时间旅行、上下文控制、场景化检索 |
| oe_reflect | cascade_depth | 更正传播深度控制 |

## 修改文件清单

### 新增文件
- `ontology_engine/engine/cognitive/cognitive_vector_index.py` — 向量索引（四级降级）

### 代码修改
- `ontology_engine/engine/cognitive/factory.py` — 注入向量索引到 RRF
- `ontology_engine/engine/cognitive/memory_api.py` — 添加 vector_index 参数、remember 自动索引、approve_memory 状态机修复、disposition_override 支持字符串
- `ontology_engine/engine/cognitive/correction_propagation.py` — 传播方向语义修复
- `ontology_engine/engine/cognitive/lifecycle.py` — TTL 过期节点实际清理
- `ontology_engine/storage/graph/kuzu_store.py` — 边表添加 created_at
- `ontology_engine/mcp/server.py` — MCP Schema 参数暴露
- `ontology_engine/mcp/tools/memory.py` — oe_recall 添加 disposition_override

### 配置文件
- `config.yaml.example` — 新增 embedding 配置节

### 文档更新
- `docs/02-design/agent-memory/memory-api.md` — RRF 四路融合与向量索引、Embedding 配置体系
- `docs/02-design/agent-memory/memory-lifecycle.md` — 更正传播方向语义

### 评估脚本
- `examples/case8_locomo_memory_eval/run_eval.py` — 使用 LMStudio 本地端点

## 待讨论决策点

1. **向量索引持久化**: 当前 `CognitiveVectorIndex` 使用 `LocalVectorStore`（纯内存），重启后向量索引丢失，需要重新计算。是否需要持久化到 ChromaDB？

2. **embedding 维度不匹配**: 如果用户切换 embedding 模型（如从 384d 切换到 2560d），已有向量全部失效。是否需要版本化向量存储？

3. **TTL 过期策略**: 当前 TTL 过期节点被 transition 到 `superseded`，但这可能过于激进。是否应该先 transition 到 `pending_review`，等待人工确认后再 `superseded`？
