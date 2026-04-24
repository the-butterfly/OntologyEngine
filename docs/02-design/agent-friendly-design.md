# Agent-Friendly Interface Design

> **status**: accepted
> **phase**: phase1-enhancement
> **source_of_truth**: 本文档
> **last_verified**: 2026-04-23
> **verified_against**: `ontology_engine/mcp/`, `ontology_engine/api/`, `ontology_engine/cli/`

---

## 目的

定义 OntologyEngine 面向 Agent 基础设施的接口设计规范，确保所有 API / MCP / CLI 工具对 Agent 友好：有明确的使用说明、错误信息清晰、关键动作允许模拟和关联影响分析、操作结果可验证、具备友好的版本回退、可以通过 CLI/MCP 完成端到端操作。

---

## 设计原则

### 1. 接口自描述

Agent 能仅凭接口定义理解如何调用，无需查阅外部文档。

**API 层**:
- 所有端点必须设置 FastAPI `summary` 和 `description` 参数
- 所有 Pydantic Model 字段必须设置 `Field(description=..., examples=...)`
- 禁止使用 `dict[str, Any]` 作为请求体，必须定义强类型 Model
- 所有端点必须设置 `response_model`

**MCP 层**:
- 每个工具 description 必须包含：用途说明、使用场景、前置条件、返回值概述
- 每个参数必须设置 `description` 和 `examples`
- enum 类型参数必须列出所有可选值及其含义
- 不可用的选项不得暴露

**CLI 层**:
- 每个命令必须有 `--help` 输出
- 每个参数必须有 `help` 文本，包含示例值
- 命令 docstring 应说明返回值结构

### 2. 错误可自修复

Agent 能根据错误信息自行修复，无需人工介入。

**统一错误响应格式**:

```json
{
    "success": false,
    "error": {
        "code": "SPACE_NOT_FOUND",
        "message": "Space 'space_xxx' not found",
        "suggestion": "Use GET /v1/spaces to list available spaces"
    },
    "data": null,
    "meta": {
        "request_id": "...",
        "timestamp": "..."
    }
}
```

**规则**:
- 错误响应必须返回正确的 HTTP 状态码（禁止 HTTP 200 + success=false）
- 错误码必须有注册表（见 `docs/02-design/api/error-codes.md`）
- 错误信息统一使用英文
- `suggestion` 字段提供修复建议，引导 Agent 下一步操作

**MCP 层错误格式**:

```json
{
    "success": false,
    "data": null,
    "error": {
        "code": "SPACE_NOT_FOUND",
        "message": "Space 'space_xxx' not found",
        "suggestion": "Use oe_list_spaces to find available spaces"
    }
}
```

### 3. 操作可预览

所有关键操作允许 Agent 先预览影响，再决定是否执行。

**dry-run 规则**:

| 操作类型 | dry-run 支持 | 查询参数 | 预览返回内容 |
|----------|:----------:|----------|-------------|
| DELETE | 必须 | `?dry_run=true` | 将被删除的资源清单 + 级联影响 |
| PUT/PATCH | 应该 | `?dry_run=true` | 变更 diff + 受影响的下游资源 |
| POST (写操作) | 应该 | `?dry_run=true` | 将创建的资源预览 |
| rollback | 必须 | `?dry_run=true` | 回退前后状态差异 |
| 规则执行 | 必须 | 参数 `dry_run=true` | 执行结果但不持久化 |

**Schema 变更影响分析**:

```
POST /v1/spaces/{space_id}/schema/impact-analysis
```

分析 Schema 变更对下游规则和实体的影响，返回受影响的规则列表和实体数量。

### 4. 结果可验证

操作返回足够信息供 Agent 验证成功。

**创建操作**:
- 返回完整资源状态（包括自动生成的 ID、创建时间、初始状态）
- 返回 `self` 链接（资源自身的 URL）

**删除操作**:
- 返回删除前快照
- 返回级联删除清单（关联资源列表）
- 返回受影响资源数量

**更新操作**:
- 返回更新后的完整资源状态
- 返回变更字段列表

**执行操作**:
- 返回执行 ID，可通过 GET 端点查询历史结果
- 返回执行时间戳和耗时

### 5. 端到端可达

Agent 可通过任一接口层完成完整的业务流程。

**核心业务流程**:

```
创建空间 → 加载 Schema → 导入实例 → 定义规则 → 激活空间 → 运行分析 → 查询结果
```

**三层接口能力对齐表**:

| 业务能力 | API 端点 | MCP 工具 | CLI 命令 |
|----------|----------|----------|----------|
| 创建空间 | `POST /v1/spaces` | `oe_create_space` | `ontology-cli space create` |
| 列出空间 | `GET /v1/spaces` | `oe_list_spaces` | `ontology-cli space list` |
| 加载 Schema | `POST /v1/spaces/{id}/schema/load-yaml` | `oe_load_schema` | `ontology-cli schema load` |
| 导入实例 | `POST /v1/spaces/{id}/instances/load-yaml` | `oe_import_instances` | `ontology-cli entities import` |
| 创建实体 | `POST /v1/spaces/{id}/instances/entities` | `oe_create_entity` | `ontology-cli entities add` |
| 定义规则 | `POST /v1/spaces/{id}/schema/L4/rules/definitions` | `oe_define_rule` | `ontology-cli rules add` |
| 激活空间 | `POST /v1/spaces/{id}/activate` | `oe_activate_space` | `ontology-cli space activate` |
| 执行分析 | `POST /v1/views/{id}/execute/analyze` | `oe_execute_rule` | `ontology-cli analyze run` |
| 模拟执行 | `POST /v1/views/{id}/execute/simulate` | `oe_simulate` | `ontology-cli analyze simulate` |
| 知识检索 | `POST /v1/query/search` | `oe_query` | `ontology-cli query search` |
| 版本快照 | `POST /v1/spaces/{id}/versions` | `oe_snapshot` | `ontology-cli version create` |
| 版本回退 | `POST /v1/spaces/{id}/versions/{v}/rollback` | `oe_rollback` | `ontology-cli version rollback` |

### 6. 版本可回退

关键资源支持版本管理，回退操作有安全网。

**版本管理范围**:

| 资源 | 版本管理 | 快照粒度 | 回退粒度 |
|------|:--------:|----------|----------|
| Space | ✓ | Space 级完整快照 | Space 级回退 |
| 规则定义 | ✓ (P2) | 规则级增量快照 | 规则级回退 |
| 实体 | ✓ (P2) | 实体级增量快照 | 实体级回退 |
| 增量批次 | ✓ | 批次级 | 一键回退 |

**回退安全网**:
- 回退前自动创建当前版本快照
- 回退操作支持 `?dry_run=true` 预览
- 回退后返回前后差异摘要

---

## MCP 工具设计规范

### 工具注册规范

每个 MCP 工具必须包含：

1. **name**: `oe_{verb}_{noun}` 格式，如 `oe_create_space`
2. **description**: 至少 3 句话——用途、前置条件、返回值概述
3. **inputSchema**: 完整的 JSON Schema，包含 `description`、`examples`、`enum`

### 工具依赖注入

MCP 工具必须通过 service 层调用，禁止直接依赖 storage / engine / core / api 层。

```
MCP tools → services → engine/storage
```

依赖注入通过 `ontology_engine/mcp/__init__.py` 中的 `init_mcp_dependencies()` 实现：

```python
# mcp/__init__.py
_services: dict[str, Any] | None = None

def init_mcp_dependencies(services: dict[str, Any]) -> None:
    global _services
    _services = services

def get_service(name: str) -> Any:
    if _services is None:
        raise RuntimeError("MCP dependencies not initialized")
    return _services[name]
```

### 工具返回格式

```python
def mcp_response(
    success: bool,
    data: Any = None,
    error: str | dict | None = None,
) -> dict[str, Any]:
    return {
        "success": success,
        "data": data,
        "error": error,  # string 或 {"code": "...", "message": "...", "suggestion": "..."}
    }
```

---

## API 错误码注册表

见 `docs/02-design/api/error-codes.md` [待创建]。

核心错误码：

| 错误码 | HTTP 状态码 | 含义 | 修复建议 |
|--------|:----------:|------|----------|
| SPACE_NOT_FOUND | 404 | 空间不存在 | Use GET /v1/spaces to list available spaces |
| SPACE_CONFLICT | 409 | 空间名称冲突 | Use a different name or delete the existing space |
| ENTITY_NOT_FOUND | 404 | 实体不存在 | Use GET /v1/spaces/{id}/instances/entities to list entities |
| SCHEMA_NOT_LOADED | 422 | Schema 未加载 | Load schema first via POST /v1/spaces/{id}/schema/load-yaml |
| VALIDATION_ERROR | 422 | 请求验证失败 | Check request body format against the API schema |
| STORAGE_ERROR | 500 | 存储层错误 | Retry the operation or check storage configuration |
| ANALYSIS_ERROR | 500 | 分析执行失败 | Check entity data and rule definitions |

---

## CLI 设计规范

### 框架选择

使用 `typer`（基于 type hints，对 Agent 生成命令调用更友好）。

### 命令结构

```
ontology-cli
  ├── space    {create|list|get|activate|deactivate|archive|delete}
  ├── schema   {load|show|validate}
  ├── entities {list|add|import}
  ├── rules    {list|add|hot-update|dependency-graph}
  ├── analyze  {run|simulate}
  ├── query    {search|graph|trace}
  ├── version  {list|create|rollback}
  └── report   {generate}
```

### 输出格式

所有命令支持 `--format json|table|yaml`，默认 `json`（Agent 是主要消费者）。

### Dry-run 支持

所有写操作命令支持 `--dry-run` 参数。

---

## 参考文档

| 主题 | 文档位置 |
|------|----------|
| 旧版 Agent 接口设计 | `docs-baseline/07-agent-interface.md` |
| MCP 工具 RFC | `docs-dev/03-rfc/RFC-013-mcp-tool-implementation.md` |
| API 设计 | `docs/02-design/api/README.md` |
| 改进计划 | `docs/plans/2026-04-23-agent-friendly-infrastructure.md` |
