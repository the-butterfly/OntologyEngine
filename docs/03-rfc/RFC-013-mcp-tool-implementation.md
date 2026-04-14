# RFC-013: MCP 工具实现

> **状态**: draft
> **父 RFC**: [RFC-010](./RFC-010-phase2-roadmap.md)
> **关联文档**: `docs/07-agent-interface.md`
> **创建日期**: 2026-04-14
> **作者**: the-butterfly
> **评审截止**: 待定

## 动机

`docs/07-agent-interface.md` 已定义了完整的 MCP 工具集（18 个）。RFC-013 是实现路线图，按优先级将 REST API 包装为 MCP 工具。

**审视发现（2026-04-14）**: `ontology_engine/mcp/` 目录从未创建（MCP Server 完全不存在）。`docs/09-examples/TOOL_AUDIT.md` 是逐一核验报告，定义 P1/P2/P3 优先级。本 RFC 执行该优先级计划。

## 工具实现顺序（以 TOOL_AUDIT 为准）

```
P1（消费面核心 — 立即可做）:
  ├── oe_execute_rule     → POST /v1/consumption/views/{view_id}/execute/analyze
  ├── oe_query            → POST /v1/query/vector | /hybrid | /graph
  ├── oe_simulate         → POST /v1/consumption/views/{view_id}/execute/simulate
  ├── oe_create_space     → POST /v1/management/spaces
  └── oe_register_dataset → POST /v1/management/{space_id}/datasets

P2（管理面扩展）:
  ├── oe_load_schema      → GET /v1/management/{space_id}/schema
  ├── oe_trace_rule       → GET /v1/query/trace/{entity_id}
  ├── oe_define_rule      → POST /v1/management/{space_id}/schema/L4/rules
  ├── oe_attach_rule_logic → POST /v1/management/{space_id}/schema/L4/rules/{rule_id}/logics
  ├── oe_trigger_sync     → POST /v1/management/{space_id}/datasets/{dataset_id}/entities
  ├── oe_get_sync_status  → GET /v1/management/{space_id}/datasets/{dataset_id}
  ├── oe_create_view      → POST /v1/management/views
  ├── oe_activate_space   → POST /v1/management/spaces/{space_id}/activate
  └── oe_archive_space    → POST /v1/management/spaces/{space_id}/archive

Phase 3（云端依赖 / 授权）:
  ├── oe_sync_assets      → 无离线等效（云端协议待设计）
  ├── oe_authorize_view   → 无等效 API
  ├── oe_snapshot         → 无等效 API
  └── oe_rollback         → 无等效 API
```

> **注**: TOOL_AUDIT.md 中包含完整的 18 个工具逐一对照表和参数差异分析。

## MCP Server 实现架构

```
ontology_engine/
└── mcp/
    ├── __init__.py
    ├── server.py          # MCP Server 入口
    ├── tools/             # 工具实现
    │   ├── space.py       # oe_create_space, oe_load_schema
    │   ├── dataset.py     # oe_register_dataset, oe_trigger_sync
    │   ├── execution.py   # oe_execute_rule, oe_trace_rule
    │   └── query.py       # oe_query, oe_simulate
    └── transports/
        └── stdio.py       # Claude Desktop / Cursor 通过 stdio 通信
```

## 工具签名设计原则

1. **参数命名**: 与 API request model 字段名一致（复用 Pydantic model）
2. **返回格式**: 统一 `{success: bool, data: {...}, error: str | null}` 三段式
3. **错误处理**: 工具级错误转换为 `error` 字段，不抛出异常
4. **认证**: Phase 2 简化为无认证（`API_KEY` 通过 header 注入，Claude Desktop MCP 支持）

## 实现范围

### 包含
- [✅ 已完成] 工具核验 → `docs/09-examples/TOOL_AUDIT.md`（18 个工具逐一对照）
- [ ] P1 核心 5 个工具（execute_rule / query / simulate / create_space / register_dataset）
- [ ] P2 管理面 8 个工具包装
- [ ] MCP Server 入口（`ontology_engine/mcp/server.py`）
- [ ] Claude Desktop 集成配置（`claude_desktop_config.json` 模板）

### 不包含
- Phase 3 云端资产同步（`oe_sync_assets`）
- Phase 3 授权/版本管理
- 流式输出（streaming）

## 相关文档

- **工具核验报告** — [docs/09-examples/TOOL_AUDIT.md](../09-examples/TOOL_AUDIT.md) — **P1/P2/P3 优先级以此为准**
- **审视报告** — [docs/09-examples/REVIEW_REPORT.md](../09-examples/REVIEW_REPORT.md)
- **Agent 接口设计** — [docs/07-agent-interface.md](../07-agent-interface.md) — 18 个工具定义
