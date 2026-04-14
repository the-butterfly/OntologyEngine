"""OntologyEngine MCP Server entry point."""

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from ontology_engine.mcp.tools.space import oe_create_space, oe_load_schema
from ontology_engine.mcp.tools.dataset import oe_register_dataset, oe_trigger_sync
from ontology_engine.mcp.tools.execution import oe_execute_rule, oe_simulate
from ontology_engine.mcp.tools.query import oe_query


server = Server("ontology-engine-mcp")


@server.list_tools()  # type: ignore[no-untyped-call,misc]
async def list_tools() -> list[Tool]:
    """Return all available MCP tools."""
    return [
        Tool(
            name="oe_create_space",
            description="创建语义空间（Semantic Space）",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "空间名称"},
                    "description": {"type": "string", "description": "空间描述"},
                    "domain": {"type": "string", "description": "业务领域"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="oe_load_schema",
            description="加载语义空间的 Schema 信息",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "空间 ID"},
                },
                "required": ["space_id"],
            },
        ),
        Tool(
            name="oe_register_dataset",
            description="注册数据集",
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "所属空间 ID"},
                    "name": {"type": "string", "description": "数据集名称"},
                    "source_config": {"type": "object", "description": "数据源配置"},
                },
                "required": ["space_id", "name"],
            },
        ),
        Tool(
            name="oe_trigger_sync",
            description="触发数据集实体同步",
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string", "description": "数据集 ID"},
                    "space_id": {"type": "string", "description": "空间 ID"},
                    "mode": {"type": "string", "description": "同步模式"},
                },
                "required": ["dataset_id", "space_id"],
            },
        ),
        Tool(
            name="oe_execute_rule",
            description="对实体执行规则分析",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体 ID"},
                    "view_id": {"type": "string", "description": "视图/空间 ID"},
                    "dimension": {"type": "string", "description": "分析维度"},
                    "explain_level": {"type": "string", "enum": ["full", "detailed", "brief"], "description": "解释级别"},
                },
                "required": ["entity_id", "view_id"],
            },
        ),
        Tool(
            name="oe_simulate",
            description="模拟规则执行（假设数据覆盖）",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "实体 ID"},
                    "view_id": {"type": "string", "description": "视图/空间 ID"},
                    "dimension": {"type": "string", "description": "分析维度"},
                    "overrides": {"type": "object", "description": "字段覆盖值"},
                },
                "required": ["entity_id", "view_id"],
            },
        ),
        Tool(
            name="oe_query",
            description="知识检索查询",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "查询文本"},
                    "match_mode": {"type": "string", "enum": ["vector", "keyword", "hybrid", "graph", "pattern"], "description": "匹配模式"},
                    "top_k": {"type": "integer", "description": "返回结果数量", "default": 10},
                },
                "required": ["query", "match_mode"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool call requests."""
    _TOOL_HANDLERS = {
        "oe_create_space": oe_create_space,
        "oe_load_schema": oe_load_schema,
        "oe_register_dataset": oe_register_dataset,
        "oe_trigger_sync": oe_trigger_sync,
        "oe_execute_rule": oe_execute_rule,
        "oe_simulate": oe_simulate,
        "oe_query": oe_query,
    }

    handler = _TOOL_HANDLERS.get(name)
    if handler:
        result = await handler(**arguments)
    else:
        result = {"success": False, "data": None, "error": f"Unknown tool: {name}"}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def main():
    """Run the MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
