# Agent Memory 后端 API 不足问题记录

> **status**: draft | **phase**: Phase 2 | **last_verified**: 2026-05-06 | **verified_against**: localhost:8000 + examples/agent_memory/ANALYSIS.md + 前端代码审计

---

## 1. P0 阻塞问题 — 前端数据流中断

### 1.1 recall 返回空结果

**端点**: `POST /v1/spaces/{space_id}/memory/recall`

**现象**:
```bash
POST /recall {"query":"*","max_results":5}
→ {"results": [], "total": 0}
```

**影响**: 记忆图谱、记忆列表、待审区、所有页面数据为空。

**根因**: 向量索引默认 provider="bm25"，BM25 冷启动后 `_total_docs=0` 触发重建，但重建只索引前 5000 节点。中文子串匹配几乎无效。

**来源**: `examples/agent_memory/ANALYSIS.md §2.1`

### 1.2 confirmation_count 字段错误

**端点**: `GET /v1/spaces/{space_id}/memory/{node_id}`, `GET /v1/spaces/{space_id}/memory/{node_id}/evidence`

**现象**:
```bash
GET /{node_id} → {"error": {"code": "GET_NODE_ERROR", "message": "'confirmation_count'"}}
```

**影响**: MemoryDetailDrawer 不可用，证据链展开不可用。

**根因**: Kuzu 存储查询中引用了不存在的 `confirmation_count` 字段。

**来源**: 前端 API 探测 + `examples/agent_memory/ANALYSIS.md` 关键实现偏差 #4

---

## 2. P1 功能缺失 — 设计文档要求但未实现

### 2.1 缺少后端端点

| 端点 | 设计文档 | 用途 | 影响前端 |
|------|----------|------|----------|
| `GET /heatmap` | `.trae/documents/agent-memory-frontend-ui-design.md §4.1.1` | 记忆强度热力图数据 | MemoryOverviewPage 热力图 |
| `GET /dashboard` | `docs/02-design/agent-memory/memory-api.md` | 治理仪表盘聚合 | MemoryManagePage 治理面板 |
| `POST /validation/{case_id}` | 设计 §4.1.3 | 验证案例自动化执行 | MemoryOverviewPage 验证 Tab |
| `GET /validation/cases` | 设计 §4.1.3 | 验证案例列表 | MemoryOverviewPage 验证 Tab |
| `GET /disposition` | 设计 §4.4.1 | Disposition 配置读取 | MemoryConsumePage |
| `PUT /disposition` | 设计 §4.4.1 | Disposition 更新保存 | MemoryConsumePage |
| `GET /reflect-tasks` | 设计 §4.5.1 | Reflect 任务列表查询 | ReflectCenterPage |
| `GET /reflect/{reflection_id}` | 设计 §4.5.1 | Reflect 状态/结果轮询 | ReflectCenterPage |
| `PATCH /contradictions/{id}/resolve` | — | 矛盾人工裁决 | MemoryManagePage 矛盾看板 |

### 2.2 audit 返回字段不完整

**端点**: `GET /v1/spaces/{space_id}/memory/audit`

**当前返回**:
```json
{ "id": "...", "memory_type": "...", "content": "...", "belief_status": "...", "superseded_by": null, "updated_at": null }
```

**设计期望**:
- `agent_name` — Agent 标识
- `activity_type` — remember/recall/reflect/consolidate/forget/correct
- `timestamp` — 操作时间戳
- `operation` — 具体操作描述
- `result_summary` — 操作结果摘要

**影响**: Agent 活动流无法展示操作类型和延迟统计。

---

## 3. P2 设计偏差 — 已实现但与设计不符

### 3.1 Analytical 查询直接返回空

**文件**: `ontology_engine/engine/cognitive/rrf_fusion.py:128-129`

**偏差**: 分析型查询直接返回空列表，导致所有分析型 recall 无结果。

**来源**: `examples/agent_memory/ANALYSIS.md` 关键实现偏差 #2

### 3.2 QUL 只支持英文时间约束

**设计**: `docs/02-design/agent-memory/query-understanding-layer.md` 定义 8 种约束类型

**实现**: 只有一个孤立的 `extract_temporal_constraint` 函数，只匹配英文时间模式。

**来源**: `examples/agent_memory/ANALYSIS.md §2.6`

### 3.3 Layer-S 只查 entity 类型

**偏差**: Layer-S 查询只查 entity 类型，不查 observation/mental_model。

**来源**: `examples/agent_memory/ANALYSIS.md §2.4`

### 3.4 遗忘硬删除不处理连接边

**偏差**: 硬删除不处理连接边，导致 KuzuDB `"Node has connected edges"` 错误。

**来源**: `examples/agent_memory/ANALYSIS.md §2.4`

### 3.5 编译层 EntityPage 属性缺失

**偏差**: EntityPage 缺少 `related_observations`，TopicPage 缺少 `key_findings`/`open_questions`，导致 AttributeError。

**来源**: `examples/agent_memory/ANALYSIS.md` 关键实现偏差 #1

### 3.6 巩固 Update proof_count 只 +1

**设计**: 应 `+len(new_source_fragments)`

**实现**: 只 +1，导致证据计数失真。

**来源**: `examples/agent_memory/ANALYSIS.md` 关键实现偏差 #6

---

## 4. 前端兼容性处理总结

| 功能 | 当前状态 | 可用性 |
|------|----------|--------|
| 记忆统计卡片 | ✅ 基于 GET /stats | 可用 |
| 记忆图谱 (G6) | ⚠️ 依赖 recall 返回节点 | 需后端修复 |
| Agent 活动流 | ⚠️ audit 字段不全 | 部分可用 |
| 记忆详情抽屉 | ❌ confirmation_count 错误 | 不可用 |
| 证据链展开 | ❌ GET /evidence 报错 | 不可用 |
| 矛盾看板 | ✅ GET /contradictions | 可用，数据为空正常 |
| 矛盾裁决 | ❌ 无 PATCH /resolve | UI 按钮已实现，后端缺失 |
| 验证演示 | ❌ 无 /validation 端点 | UI 框架已实现，后端缺失 |
| 治理仪表盘 | ⚠️ 部分基于 /stats 模拟 | 可用但非真实聚合 |
| Disposition 预设 | ❌ 无 GET/PUT /disposition | UI 有滑块，无持久化 |
| 文档导入/上传 | ❌ 无上传端点 | UI 未实现，后端缺失 |

---

## 5. 建议后端修复优先级

| 优先级 | 问题 | 建议 |
|--------|------|------|
| P0 | recall 返回空 | 修复 BM25 降级策略，支持精确匹配 |
| P0 | confirmation_count | 移除 Kuzu 查询中不存在的字段引用 |
| P1 | 新增 /validation endpoints | 实现验证案例执行和诊断 API |
| P1 | audit 字段扩展 | 添加 agent_name, activity_type, operation |
| P2 | Analytical 查询短路 | 移除 `rrf_fusion.py:128-129` 的短路返回 |
| P2 | QUL 完整约束 | 实现 8 种约束类型，支持中文 |
| P2 | 编译层修复 | 补全 EntityPage/TopicPage 缺失属性 |
