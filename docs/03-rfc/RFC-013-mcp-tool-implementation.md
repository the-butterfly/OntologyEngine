# RFC-013: MCP 工具实现

> **状态**: draft
> **父 RFC**: [RFC-010](./RFC-010-phase2-roadmap.md)
> **关联文档**: `docs/07-agent-interface.md`
> **创建日期**: 2026-04-14
> **作者**: the-butterfly
> **评审截止**: 待定

## 动机

`docs/07-agent-interface.md` 已定义了完整的 MCP 工具集（`oe_create_space`、`oe_load_schema`、`oe_register_dataset`、`oe_execute_rule`、`oe_query`、`oe_trace_rule`、`oe_simulate`）。

**审视发现（2026-04-14）**: 该文档与 `ontology_engine/tools/` 实际实现代码的一致性**尚未核验**。本 RFC 的第一步是完成核验，然后按核验结论实现缺失工具。

## 第一步：工具一致性核验

### 核验清单

| 工具名 | 文档定义 | 实际代码 | 一致性 | 行动 |
|--------|----------|----------|--------|------|
| `oe_create_space` | `07-agent-interface.md` | `ontology_engine/tools/` | ? | 核验 |
| `oe_load_schema` | `07-agent-interface.md` | `ontology_engine/tools/` | ? | 核验 |
| `oe_register_dataset` | `07-agent-interface.md` | `ontology_engine/tools/` | ? | 核验 |
| `oe_execute_rule` | `07-agent-interface.md` | `ontology_engine/tools/` | ? | 核验 |
| `oe_query` | `07-agent-interface.md` | `ontology_engine/tools/` | ? | 核验 |
| `oe_trace_rule` | `07-agent-interface.md` | `ontology_engine/tools/` | ? | 核验 |
| `oe_simulate` | `07-agent-interface.md` | `ontology_engine/tools/` | ? | 核验 |

核验维度：
1. **工具名**: 文档定义 vs 实际文件名/函数名
2. **参数**: 参数名 / 类型 / 是否可选 / 默认值
3. **返回格式**: 文档描述 vs 实际返回 JSON 结构
4. **HTTP 映射**: 文档声称的 HTTP method + path 是否与实际 API routes 一致

### 核验后发现的问题记录到

```
docs/09-examples/TOOL_AUDIT.md  （新建，工具核验报告）
```

## 第二步：按需实现

核验完成后，按以下优先级实现缺失工具：

```
优先级 1（核心）:
  ├── oe_create_space     → 管理面 /v1/management/spaces POST
  ├── oe_load_schema      → 管理面 /v1/management/{spaceId}/schema PUT
  └── oe_execute_rule     → 消费面 /v1/consumption/views/{viewId}/execute POST

优先级 2（数据）:
  ├── oe_register_dataset → 管理面 /v1/management/{spaceId}/datasets POST
  └── oe_trigger_sync     → 管理面 /v1/management/{spaceId}/datasets/{datasetId}/sync POST

优先级 3（查询）:
  ├── oe_query            → 消费面 /v1/consumption/views/{viewId}/query POST
  ├── oe_trace_rule       → 消费面 /v1/consumption/views/{viewId}/trace GET
  └── oe_simulate         → 可视化 /v1/visualize/simulate POST
```

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
- [ ] 工具核验（第一步）→ 输出 `docs/09-examples/TOOL_AUDIT.md`
- [ ] MCP Server 入口（`ontology_engine/mcp/server.py`）
- [ ] Claude Desktop 集成配置（`claude_desktop_config.json` 模板）
- [ ] 全部 7 个工具的 MCP 层包装

### 不包含
- Phase 3 认证/授权模型
- 多租户隔离
- 流式输出（streaming）

## 相关文档

- **07-agent-interface.md** — [Agent 接口设计](../07-agent-interface.md)
- **审视报告** — [docs/09-examples/REVIEW_REPORT.md](../09-examples/REVIEW_REPORT.md)
- **API 设计规范** — [development/api-design.md](../development/api-design.md)
