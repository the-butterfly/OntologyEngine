# MCP 工具核验报告

> **审查日期**: 2026-04-14
> **审查依据**: `docs/07-agent-interface.md` vs `ontology_engine/api/routes/` + `ontology_engine/`
> **核验方法**: 逐一对照文档定义的 MCP 工具与实际代码实现

---

## 一、总体结论

| 维度 | 结果 |
|------|------|
| MCP Server 实现 | ❌ **不存在** — `ontology_engine/mcp/` 目录从未创建 |
| MCP 工具实现 | ❌ **不存在** — `ontology_engine/tools/` 目录从未创建 |
| REST API 实现 | ✅ **部分存在** — 核心 API routes 已实现 |
| 文档定位 | `docs/07-agent-interface.md` 是 **Phase 2 目标设计**，不是当前实现 |

**核心发现**: `docs/07-agent-interface.md` 定义的 18 个 MCP 工具中：
- **0 个已实现为 MCP 工具**
- **约 14 个有等效 REST API endpoints**（可在 MCP Server 中包装）
- **约 4 个完全没有等效 API**（云端资产同步类）
- **`ontology_engine/mcp/server.py` 等文件从未创建**

---

## 二、MCP 工具 vs API 路由对照表

### 2.1 消费面工具

| MCP 工具名 | 文档参数 | 文档描述 | 对应 API Endpoint | API 实现状态 | MCP 包装计划 |
|-----------|----------|----------|-------------------|-------------|-------------|
| `oe_load_schema` | `schema_id`, `mode` | 加载 Schema | 无直接端点 | ❌ | `GET /v1/management/{space_id}/schema` 部分覆盖 |
| `oe_sync_assets` | `asset_types`, `strategy` | 云端资产同步 | 无 | ❌ **无等效 API** | Phase 3（云端依赖）|
| `oe_create_entity` | `concept`, `data` | 创建实体 | 无 | ❌ | `POST /v1/entities` 待实现 |
| `oe_execute_rule` | `entity_id`, `dimension`, `explain_level` | 执行规则 | `POST /v1/consumption/views/{view_id}/execute/analyze` | ✅ 已实现 | **P1** |
| `oe_query` | `query`, `match_mode`, `top_k` | 知识检索 | `POST /v1/query/vector` / `hybrid` / `graph` | ✅ 已实现 | **P1** |
| `oe_trace_rule` | `entity_id`, `trace_mode` | 规则追溯 | `GET /v1/query/trace/{entity_id}` | ✅ 已实现 | **P2** |

### 2.2 管理面工具

| MCP 工具名 | 文档参数 | 对应 API Endpoint | API 实现状态 | MCP 包装计划 |
|-----------|----------|-------------------|-------------|-------------|
| `oe_create_space` | `name`, `description`, `domain` | `POST /v1/management/spaces` | ✅ 已实现 | **P1** |
| `oe_activate_space` | `space_id` | `POST /v1/management/spaces/{space_id}/activate` | ✅ 已实现 | **P1** |
| `oe_archive_space` | `space_id` | `POST /v1/management/spaces/{space_id}/archive` | ✅ 已实现 | **P2** |
| `oe_create_schema` | `space_id`, `schema` | `PUT /v1/management/{space_id}/schema` | ✅ 已实现 | **P1** |
| `oe_update_schema` | `space_id`, `partial_schema` | 无 | ❌ **无等效 API** | 扩展现有 PUT |
| `oe_publish_schema` | `space_id`, `version` | 无快照端点 | ❌ **无等效 API** | 待设计 |
| `oe_define_rule` | `rule_definition` | `POST /v1/management/{space_id}/schema/L4/rules` | ✅ 已实现 | **P2** |
| `oe_attach_rule_logic` | `rule_id`, `rule_logic` | `POST /v1/management/{space_id}/schema/L4/rules/{rule_id}/logics` | ✅ 已实现 | **P2** |
| `oe_register_dataset` | `name`, `source_config` | `POST /v1/management/{space_id}/datasets` | ✅ 已实现 | **P1** |
| `oe_trigger_sync` | `dataset_id`, `mode` | `POST /v1/management/{space_id}/datasets/{dataset_id}/entities` | ✅ 已实现 | **P2** |
| `oe_get_sync_status` | `dataset_id` | `GET /v1/management/{space_id}/datasets/{dataset_id}` | ✅ 已实现 | **P2** |
| `oe_create_view` | `space_id`, `dimension` | `POST /v1/management/views` | ✅ 已实现 | **P2** |
| `oe_authorize_view` | `view_id`, `auth_config` | 无 | ❌ **无等效 API** | Phase 3 |
| `oe_snapshot` | `space_id`, `comment` | 无 | ❌ **无等效 API** | Phase 3 |
| `oe_rollback` | `space_id`, `version` | 无 | ❌ **无等效 API** | Phase 3 |
| `oe_simulate` | `entity_id`, `dimension`, `overrides` | `POST /v1/consumption/views/{view_id}/execute/simulate` | ✅ 已实现 | **P1** |

---

## 三、核心差距分析

### 3.1 MCP Server 未实现

**现状**: `docs/07-agent-interface.md` 定义了完整的 `OntologyEngineMCPServer` 类，但 `ontology_engine/mcp/server.py` 从未创建。

**RFC-013 规划**:
```python
# RFC-013 目标结构
ontology_engine/
└── mcp/
    ├── __init__.py
    ├── server.py          # MCP Server 入口（待实现）
    ├── tools/             # 工具包装（待实现）
    │   ├── space.py       # oe_create_space 等
    │   ├── dataset.py     # oe_register_dataset 等
    │   ├── execution.py   # oe_execute_rule 等
    │   └── query.py       # oe_query 等
    └── transports/
        └── stdio.py       # Claude Desktop 通信
```

### 3.2 API 覆盖但参数不完全匹配

部分 MCP 工具的参数与 API request model 不一致：

| MCP 工具 | 文档参数 | API Request Model | 差异 |
|---------|----------|-------------------|------|
| `oe_execute_rule` | `explain_level: enum(full/detailed/brief)` | `ExplainLevel = Literal["none", "basic", "full"]` | 枚举值不同 |
| `oe_query` | `match_mode: enum(hybrid/vector/graph)` | `MatchMode = Literal["vector", "keyword", "hybrid", "graph", "pattern"]` | MCP 少 `keyword/pattern` |
| `oe_simulate` | `dimension`, `overrides` | `categorization: str | None`, `input_overrides: dict` | 字段名不同 |

### 3.3 完全无等效 API（Phase 3+）

- `oe_sync_assets` — 云端资产同步，无离线等效
- `oe_authorize_view` — 授权配置，未实现
- `oe_snapshot` / `oe_rollback` — 版本管理，未实现

---

## 四、修复计划

### P1（立即可做）

| 工具 | 行动 |
|------|------|
| `oe_create_space` | 创建 MCP Server，`management.py` route → MCP tool |
| `oe_execute_rule` | 创建 MCP Server，`consumption.py` route → MCP tool |
| `oe_query` | `query.py` routes → MCP tool |
| `oe_register_dataset` | `datasets.py` route → MCP tool |
| `oe_simulate` | `consumption.py` route → MCP tool |

### P2（需 API 扩展）

| 工具 | 行动 |
|------|------|
| `oe_define_rule` | API 已支持，包装为 MCP |
| `oe_attach_rule_logic` | API 已支持，包装为 MCP |
| `oe_trace_rule` | `query.py` trace → MCP tool |
| `oe_load_schema` | 扩展 `management.py` GET schema 端点 |

### Phase 3（云端依赖）

| 工具 | 行动 |
|------|------|
| `oe_sync_assets` | 设计云端同步协议后实现 |
| `oe_authorize_view` | 设计授权模型后实现 |
| `oe_snapshot` / `oe_rollback` | 实现版本管理后包装 |

---

## 五、STATUS.md 更新建议

将 `docs/STATUS.md` 热点质量问题的 "MCP 工具一致性" 项更新为：
- **实际状态**: MCP Server 完全未实现（`ontology_engine/mcp/` 不存在）
- **已确认**: 文档 `docs/07-agent-interface.md` 是 Phase 2 目标设计
- **行动**: 按 RFC-013 P1 优先级实现 5 个核心工具的 MCP 包装
- **参考**: [`docs/03-rfc/RFC-013-mcp-tool-implementation.md`](../03-rfc/RFC-013-mcp-tool-implementation.md)
