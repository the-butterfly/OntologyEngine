# Agent 基础设施友好性改进计划

> **status**: accepted
> **phase**: phase1-enhancement
> **source_of_truth**: 本文档
> **last_verified**: 2026-04-23
> **verified_against**: `ontology_engine/mcp/`, `ontology_engine/api/`, `ontology_engine/cli/`

---

## 背景

面向 Agent 基础设施定位，OntologyEngine 提供的三层接口（API / MCP / CLI）均未达到 Agent 友好标准：

| 层 | 综合评分 | 核心问题 |
|----|:--------:|----------|
| API (REST) | 4.3/10 | 错误返回 HTTP 200、路由混乱、CRUD 无 dry-run |
| MCP (Tool) | 1.3/10 | 架构违规（直接调 storage/API）、`:memory:` 空操作、工具描述简略 |
| CLI | 0/10 | 完全空白 |

六维度评估结果：

| 维度 | API | MCP | CLI |
|------|:---:|:---:|:---:|
| 使用说明明确性 | 3 | 2 | 0 |
| 错误信息清晰性 | 4 | 2 | 0 |
| 模拟与影响分析 | 5 | 1 | 0 |
| 操作结果可验证性 | 4 | 2 | 0 |
| 版本回退友好性 | 5 | 0 | 0 |
| 端到端操作能力 | 5 | 1 | 0 |

---

## 改进原则

### P1: 接口自描述原则

Agent 能仅凭接口定义理解如何调用，无需查阅外部文档。

- 所有端点/工具必须有 `summary` + `description`
- 所有参数必须有 `description` + `examples`
- 所有返回值必须有 `response_model` 或完整 Schema
- 禁止使用 `dict[str, Any]` 作为请求体

### P2: 错误可自修复原则

Agent 能根据错误信息自行修复，无需人工介入。

- 错误响应包含：`code`（结构化错误码）+ `message`（可读消息）+ `suggestion`（修复建议）
- 错误码有注册表，与 HTTP 状态码一一对应
- 错误信息统一英文

### P3: 操作可预览原则

所有关键操作允许 Agent 先预览影响，再决定是否执行。

- 所有 DELETE/PUT/PATCH 端点支持 `?dry_run=true`
- 回退操作支持预览模式
- Schema 变更支持影响分析

### P4: 结果可验证原则

操作返回足够信息供 Agent 验证成功。

- 创建操作返回完整资源状态 + `self` 链接
- 删除操作返回删除前快照 + 级联影响清单
- 写操作支持 read-after-write 验证

### P5: 端到端可达原则

Agent 可通过任一接口层完成完整的业务流程。

- MCP 工具集覆盖完整业务流程
- CLI 命令集覆盖完整业务流程
- 三层接口能力集对齐

### P6: 版本可回退原则

关键资源支持版本管理，回退操作有安全网。

- Space/规则/实体均支持版本快照
- 回退操作有预览模式
- 增量更新支持一键回退

---

## P0 — 紧急修复（架构违规 + 基本可用性）

### Task 1: 修复 MCP 架构违规

**问题**: MCP 工具直接调用 storage 层和 API 层，违反模块边界规则。

**修复方案**: 引入 MCP 依赖注入容器，所有 MCP 工具通过 service 层调用。

**涉及文件**:
- 修改: `ontology_engine/mcp/__init__.py` — 添加 `init_mcp_dependencies()` 和 service 获取函数
- 修改: `ontology_engine/mcp/tools/dataset.py` — 移除 `SQLiteStorage(db_path=":memory:")`，改用 `get_dataset_service()`
- 修改: `ontology_engine/mcp/tools/query.py` — 移除 `SQLiteStorage(db_path=":memory:")`，改用 `get_query_service()`
- 修改: `ontology_engine/mcp/tools/execution.py` — 移除 `from api.routes.consumption import _run_full_analysis`，改用 `get_analysis_service()`
- 修改: `ontology_engine/mcp/tools/space.py` — 移除直接操作 `SemanticSpaceStorage`，改用 `get_schema_service()`
- 修改: `ontology_engine/mcp/server.py` — 在 `main()` 中初始化依赖

**验收标准**:
- `grep -r "from ontology_engine.storage" ontology_engine/mcp/ --include="*.py"` 返回空
- `grep -r "from ontology_engine.api" ontology_engine/mcp/ --include="*.py"` 返回空
- `grep -r "from ontology_engine.core" ontology_engine/mcp/ --include="*.py"` 返回空
- MCP 工具可正常调用并返回有效数据

### Task 2: 修复 MCP Schema 不一致和不可用模式

**问题**:
- `oe_register_dataset` 的 inputSchema 定义 `source_config`（object），函数签名是 `source_type`（str）
- `oe_query` 暴露不可用的 `graph` 模式
- `oe_trigger_sync` 的 `mode` 缺少 enum 定义

**涉及文件**:
- 修改: `ontology_engine/mcp/server.py` — 修正 inputSchema

**验收标准**:
- `oe_register_dataset` 的 inputSchema 与函数签名一致
- `oe_query` 的 match_mode enum 不包含 `graph`
- `oe_trigger_sync` 的 mode 有 enum 定义 `["full", "incremental"]`

### Task 3: 统一 API 错误处理

**问题**: `error_response()` 返回 HTTP 200 + `success=false`，Agent 无法通过 HTTP 状态码判断成功/失败。

**修复方案**: 为 `error_response()` 添加 HTTP 状态码参数，在路由层使用 `JSONResponse` 返回正确状态码。

**涉及文件**:
- 修改: `ontology_engine/api/dto/responses.py` — `error_response()` 增加 `status_code` 参数，返回 `JSONResponse`
- 修改: 所有路由文件 — 将 `return error_response(...)` 改为 `raise` 或使用 `JSONResponse`

**验收标准**:
- 错误响应返回正确的 HTTP 状态码（404/409/422/500 等）
- 成功响应仍返回 HTTP 200
- 响应体格式不变

---

## P1 — 短期改进（Agent 自主操作能力）

### Task 4: 丰富 MCP 工具描述

**涉及文件**:
- 修改: `ontology_engine/mcp/server.py` — 为所有工具添加完整 description + 参数 examples

**每个工具的 description 应包含**:
1. 用途说明
2. 使用场景
3. 前置条件
4. 返回值概述

### Task 5: 丰富 API 端点文档

**涉及文件**:
- 修改: 所有路由文件 — 为端点添加 `summary` 和 `description`
- 修改: `ontology_engine/api/dto/requests.py` — 为所有 Pydantic Model 字段添加 `Field(description=...)`

### Task 6: 建立错误码注册表

**涉及文件**:
- 新增: `docs/02-design/api/error-codes.md` — 错误码注册表
- 修改: `ontology_engine/services/dto/errors.py` — 扩展 `ServiceError` 添加 `suggestion` 字段
- 修改: `ontology_engine/mcp/__init__.py` — `mcp_response()` 的 error 支持结构化错误

### Task 7: 为 DELETE 端点添加 dry-run 支持

**涉及文件**:
- 修改: `ontology_engine/api/routes/semantic_spaces.py` — DELETE space 添加 `?dry_run=true`
- 修改: `ontology_engine/api/routes/management.py` — DELETE space 添加 `?dry_run=true`

### Task 8: 为 rollback 添加预览模式

**涉及文件**:
- 修改: `ontology_engine/api/routes/semantic_spaces.py` — rollback 添加 `?dry_run=true`

### Task 9: 添加 oe_list_spaces 工具

**涉及文件**:
- 修改: `ontology_engine/mcp/tools/space.py` — 添加 `oe_list_spaces`
- 修改: `ontology_engine/mcp/server.py` — 注册新工具

---

## P2 — 中期改进（Agent 高级能力）

### Task 10: 实现 P2 MCP 工具

- `oe_define_rule`: 定义规则声明
- `oe_attach_rule_logic`: 添加规则逻辑
- `oe_create_entity`: 创建实体
- `oe_activate_space`: 激活空间

### Task 11: CLI 骨架搭建

- 使用 typer 框架
- 实现 space/schema/entities 命令组
- 支持 `--format json` 输出
- 支持 `--dry-run` 参数

### Task 12: 为规则/实体添加独立版本管理

### Task 13: 添加 Schema 变更影响分析端点

### Task 14: 添加 ETag / 乐观并发控制

---

## 执行顺序

```
P0-Task1 (MCP 架构修复) ──▶ P0-Task2 (Schema 修复) ──▶ P0-Task3 (API 错误处理)
                                                              │
P1-Task4 (MCP 描述) ◄────────────────────────────────────────┘
P1-Task5 (API 文档)
P1-Task6 (错误码注册表)
P1-Task7 (DELETE dry-run)
P1-Task8 (rollback 预览)
P1-Task9 (oe_list_spaces)
         │
         ▼
P2-Task10~14
```

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| Agent 接口设计 | `docs-baseline/07-agent-interface.md` |
| MCP 工具 RFC | `docs-dev/03-rfc/RFC-013-mcp-tool-implementation.md` |
| API 设计 | `docs/02-design/api/README.md` |
| 服务层设计 | `docs/02-design/services/README.md` |
| Agent 友好性设计 | `docs/02-design/agent-friendly-design.md` |
