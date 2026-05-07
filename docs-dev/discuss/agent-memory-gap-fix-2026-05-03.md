# Session: Agent Memory 深度 GAP 分析 & 修复

**Date**: 2026-05-03

## Round 2 - 架构级 Tags 缺口修复

### 发现

对照 consolidation-engine.md 逐行对比，发现 CognitiveNode 数据模型缺少 `tags` 字段，
导致整个 consolidation tags 隔离链路断裂：

1. **CognitiveNode 无 tags 字段** → `remember()` 接收 tags 但无法写入
2. **Fragment 构造不携带 tags** → `group_by_tags()` 所有碎片归入空组
3. **execute_create 不写入 tags/proof_count/confidence**
4. **execute_update 不更新 proof_count/confidence/tags**
5. **execute_delete 不设置 node.superseded_by + 手动 history 截断**
6. **Kuzu SELECT 查询不包含 tags 列** → KeyError
7. **trigger_mental_model_refreshes tags 过滤无法工作**（现已修复）

### 修复

| # | 文件 | 修复内容 |
|---|------|----------|
| A1 | models.py | 添加 `tags: list[str]` 到 CognitiveNode |
| A2 | kuzu_store.py | 添加 `tags JSON` 到 CognitiveNode 表 schema + upsert/SET + 2个SELECT + 2个 node_to_dict |
| B1 | memory_api.py | `_remember()` 传入 `tags=req.tags or []` |
| B2 | repository.py | `create_node` + `update_node` 补全 tags/schema_ref/superseded_by/proof_count/valid_from/valid_to/recorded_at |
| C1 | consolidation_engine.py | Fragment 构造传入 tags |
| C2 | consolidation_engine.py | execute_create 写入 tags/proof_count/confidence |
| C3 | consolidation_engine.py | execute_update 更新 proof_count/confidence/updated_tags |
| C4 | consolidation_engine.py | execute_delete 设置 superseded_by + 统一使用 append_history_entry |

### 验证

- 960 tests passed (950 unit + 10 e2e)
- D-CON-4 Tags 隔离链路端到端通过

## 分析范围

对照 `docs/02-design/agent-memory/` (6 份设计文档) 的 44 个设计点，逐项比对
`ontology_engine/engine/cognitive/` + `api/routes/` + `mcp/tools/` + `cli/` 的 14+ 源文件。

验证工具：端到端测试 (`tests/integration/test_e2e_agent_memory.py`) 覆盖金融合规 Agent 完整场景。

## 关键发现

### 🔴 临界缺陷（已修复）

1. **REST API _get_memory_api() 崩溃**
   - KuzuGraphStore 构造函数不接受参数，MemoryAPI 缺少 6 个必需依赖
   - 所有 7 个 REST 端点不可用

2. **MCP _get_memory_api() 崩溃**
   - 相同问题，10 个 MCP 工具不可用

3. **Schema 对齐评分 tags 分支死代码**
   - `CognitiveNode` 无 `tags` 字段，0.1 分永远丢失

4. **maybe_upgrade_to_entity 条件重复**
   - 两个 if 分支条件完全相同，第二个语义错误

### ✅ 维度状态

| 维度 | 设计点 | 状态 |
|------|--------|------|
| 抽取构建 | 10/10 | 通过（含双通道提取、更正传播、Schema-guided） |
| 消费检索 | 12/12 | 通过（含 RRF 融合、Temporal Proximity、冷启动降级） |
| 知识治理 | 12/12 | 通过（含 DreamCycle、Consolidation OCC、编译调度器） |
| 接口层 | 10/10 | 通过（含 /types /audit 端点、MCP tools、CLI 命令） |

## 架构决策

1. **引入 MemoryAPIFactory** — 统一 MemoryAPI 初始化入口，避免 API/MCP 层重复 40+ 行依赖注入代码
2. **应用级单例 MemoryAPISingleton** — 所有 REST/MCP 端点共享同一套 MemoryAPI + Kuzu 连接
3. **Schema 对齐评分替换 tags 检查** — 改用 `content > 50 chars +0.1` 替代无法访问的 tags 字段
4. **maybe_upgrade_to_entity 修复** — fragment 高对齐 + 内容丰富 → observation；observation 多证据 → entity

## 验证

- 960 tests passed (950 unit + 10 e2e)
- E2E 覆盖: 合规文档导入 → 碎片抽取 → 双通道 Schema 提取 → 更正传播 → 检索（含审计） → Reflect → 审批 → DreamCycle → 编译 → MentalModel 刷新

## Round 3 - API 参数流失修复 + REST endpoint 统一化

### 发现

4路并行 Agent 语义对比后发现，前两轮修复集中在引擎层，REST API 层仍有参数流失：

1. **REST /remember 不传递 metadata/schema_ref/supersede_target** → metadata 参数在 REST 入口被丢弃
2. **REST /recall 不传递 evidence_depth/belief_status_filter/audit_trail** → 证据链、信念过滤、审计功能在 REST 不可用
3. **REST /consolidate + /forget 仍使用旧版直接 KuzuGraphStore 构造** → 绕过 MemoryAPI singleton，多连接冲突
4. **API routes docstring 说 7 endpoint 但实际 9**

### 修复

| # | 修复 |
|---|------|
| 1 | /remember 补传 metadata, created_by, confidence, schema_ref, supersede_target, supersede_reason |
| 2 | /recall 补传 evidence_depth, belief_status_filter, audit_trail |
| 3 | /consolidate → api._consolidation.run_consolidation_job() |
| 4 | /forget → api._forgetting.apply_forgetting() |
| 5 | 更新 docstring → 9 endpoints, 修复 Body import |

### 验证

- 960 tests passed (950 unit + 10 e2e)
- REST API 全部 9 端点参数已对齐 MemoryAPI 签名
