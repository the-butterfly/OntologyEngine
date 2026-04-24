"""OntologyEngine MCP Server entry point."""

import asyncio
import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from ontology_engine.mcp import init_mcp_dependencies
from ontology_engine.mcp.tools.space import oe_create_space, oe_load_schema, oe_list_spaces
from ontology_engine.mcp.tools.dataset import oe_register_dataset, oe_trigger_sync
from ontology_engine.mcp.tools.execution import oe_execute_rule, oe_simulate
from ontology_engine.mcp.tools.query import oe_query
from ontology_engine.mcp.tools.management import oe_create_entity, oe_define_rule, oe_activate_space
from ontology_engine.mcp.tools.versioning import oe_snapshot, oe_rollback

logger = logging.getLogger(__name__)

server = Server("ontology-engine-mcp")


@server.list_tools()  # type: ignore[no-untyped-call,misc]
async def list_tools() -> list[Tool]:
    """Return all available MCP tools."""
    return [
        Tool(
            name="oe_create_space",
            description=(
                "Create a new semantic space in DRAFT status. "
                "After creation, load a schema via oe_load_schema and activate "
                "via oe_activate_space before running analysis. "
                "Returns the space_id needed for all subsequent operations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Space name, e.g. 'Supply Chain Finance'"},
                    "description": {"type": "string", "description": "Space description"},
                    "domain": {"type": "string", "description": "Business domain, e.g. 'finance', 'compliance'"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="oe_list_spaces",
            description=(
                "List all semantic spaces with their IDs, names, statuses, and entity counts. "
                "Use this to discover available spaces before calling other tools. "
                "Returns a list of space summaries."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="oe_load_schema",
            description=(
                "Load schema overview for a semantic space. Returns a summary of all "
                "four schema layers (L1-L4): fact object counts, categorization dimensions, "
                "analytical metrics, and rule definitions. Use this to understand the "
                "structure of a space before running analysis."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID, e.g. 'space_supply_chain_finance'"},
                },
                "required": ["space_id"],
            },
        ),
        Tool(
            name="oe_register_dataset",
            description=(
                "Register a dataset within a semantic space. After registration, "
                "use oe_trigger_sync to synchronize entities from the dataset into the space. "
                "Returns the dataset_id for subsequent sync operations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID to register the dataset under"},
                    "name": {"type": "string", "description": "Dataset name, e.g. 'Q1 Financial Data'"},
                    "source_type": {
                        "type": "string",
                        "description": "Data source type",
                        "enum": ["manual", "csv", "api", "database"],
                        "default": "manual",
                    },
                    "description": {"type": "string", "description": "Dataset description"},
                },
                "required": ["space_id", "name"],
            },
        ),
        Tool(
            name="oe_trigger_sync",
            description=(
                "Trigger entity synchronization from a dataset to a space. "
                "Synchronizes entities from the specified dataset into the semantic space. "
                "Use mode='incremental' for partial syncs or mode='full' for complete syncs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string", "description": "Dataset ID to sync from"},
                    "space_id": {"type": "string", "description": "Target space ID"},
                    "mode": {
                        "type": "string",
                        "description": "Sync mode: 'full' replaces all, 'incremental' adds only new",
                        "enum": ["full", "incremental"],
                        "default": "full",
                    },
                },
                "required": ["dataset_id", "space_id"],
            },
        ),
        Tool(
            name="oe_execute_rule",
            description=(
                "Execute rule analysis on an entity. Runs the complete analysis pipeline "
                "(L2 categorization, L3 metric computation, L4 rule execution) for the "
                "specified entity and dimension. Set dry_run=true to preview results "
                "without persisting changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entity ID to analyze, e.g. 'SUP_C1'"},
                    "view_id": {"type": "string", "description": "View or space ID, e.g. 'view_supply_chain_finance'"},
                    "dimension": {
                        "type": "string",
                        "description": "Analysis dimension, e.g. 'credit_assessment'",
                        "default": "credit_assessment",
                    },
                    "explain_level": {
                        "type": "string",
                        "description": "Explanation detail level",
                        "enum": ["full", "detailed", "brief"],
                        "default": "brief",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, preview results without persisting",
                        "default": False,
                    },
                },
                "required": ["entity_id", "view_id"],
            },
        ),
        Tool(
            name="oe_simulate",
            description=(
                "Simulate rule execution with hypothetical data overrides. "
                "Runs two analyses in parallel: baseline (current data) and simulated "
                "(with overrides applied). Returns both results for comparison. "
                "No data is persisted. Example overrides: {'revenue': 5000000}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Entity ID to simulate, e.g. 'SUP_C1'"},
                    "view_id": {"type": "string", "description": "View or space ID"},
                    "dimension": {
                        "type": "string",
                        "description": "Analysis dimension",
                        "default": "credit_assessment",
                    },
                    "overrides": {
                        "type": "object",
                        "description": "Field overrides for simulation, e.g. {'revenue': 5000000, 'risk_level': 'high'}",
                    },
                },
                "required": ["entity_id", "view_id"],
            },
        ),
        Tool(
            name="oe_query",
            description=(
                "Knowledge retrieval query across semantic spaces. "
                "Searches for entities and relations using the specified match mode. "
                "Use 'hybrid' for best results combining vector similarity and keyword matching."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search text, e.g. 'high risk suppliers'"},
                    "match_mode": {
                        "type": "string",
                        "description": "Search strategy",
                        "enum": ["vector", "keyword", "hybrid", "pattern"],
                        "default": "hybrid",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="oe_create_entity",
            description=(
                "Create a new entity in a semantic space. The entity must reference "
                "a valid fact_object type defined in the space's L1 schema layer. "
                "Returns the entity_id and fact_object for verification."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID"},
                    "entity_id": {"type": "string", "description": "Unique entity ID, e.g. 'SUP_C1'"},
                    "fact_object": {"type": "string", "description": "Fact object type from L1 schema, e.g. 'Supplier'"},
                    "attributes": {
                        "type": "object",
                        "description": "Optional entity attributes as key-value pairs, e.g. {'revenue': 5000000}",
                    },
                },
                "required": ["space_id", "entity_id", "fact_object"],
            },
        ),
        Tool(
            name="oe_define_rule",
            description=(
                "Define a new rule declaration in the space's L4 schema layer. "
                "After defining a rule, attach rule logic via the API. "
                "Rules are organized by analysis dimension (e.g., credit_assessment)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID"},
                    "rule_id": {"type": "string", "description": "Unique rule ID, e.g. 'rule_credit_score'"},
                    "name": {"type": "string", "description": "Human-readable rule name, e.g. 'Credit Score Check'"},
                    "dimension": {
                        "type": "string",
                        "description": "Analysis dimension",
                        "default": "credit_assessment",
                    },
                    "applies_to": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of fact_object types this rule applies to, e.g. ['Supplier']",
                    },
                    "description": {"type": "string", "description": "Rule description"},
                },
                "required": ["space_id", "rule_id", "name"],
            },
        ),
        Tool(
            name="oe_activate_space",
            description=(
                "Activate a semantic space, transitioning it from DRAFT to ACTIVE. "
                "An active space creates a consumption view for analysis and simulation. "
                "The space must have a schema loaded before activation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID to activate"},
                },
                "required": ["space_id"],
            },
        ),
        Tool(
            name="oe_snapshot",
            description=(
                "Create a versioned snapshot of a semantic space. "
                "Snapshots enable rollback to previous states. "
                "Use oe_rollback to restore a previous snapshot. "
                "Returns the version number and description."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID to snapshot"},
                    "description": {"type": "string", "description": "Snapshot description, e.g. 'Before rule change'"},
                },
                "required": ["space_id"],
            },
        ),
        Tool(
            name="oe_rollback",
            description=(
                "Rollback a semantic space to a previous version. "
                "Set dry_run=true to preview the rollback impact without applying changes. "
                "Use oe_snapshot to create version checkpoints before risky changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID to rollback"},
                    "target_version": {"type": "integer", "description": "Target version number to rollback to"},
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, preview rollback impact without applying",
                        "default": False,
                    },
                },
                "required": ["space_id", "target_version"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool call requests."""
    _TOOL_HANDLERS = {
        "oe_create_space": oe_create_space,
        "oe_list_spaces": oe_list_spaces,
        "oe_load_schema": oe_load_schema,
        "oe_register_dataset": oe_register_dataset,
        "oe_trigger_sync": oe_trigger_sync,
        "oe_execute_rule": oe_execute_rule,
        "oe_simulate": oe_simulate,
        "oe_query": oe_query,
        "oe_create_entity": oe_create_entity,
        "oe_define_rule": oe_define_rule,
        "oe_activate_space": oe_activate_space,
        "oe_snapshot": oe_snapshot,
        "oe_rollback": oe_rollback,
    }

    handler = _TOOL_HANDLERS.get(name)
    if handler:
        result = await handler(**arguments)
    else:
        result = {
            "success": False,
            "data": None,
            "error": {
                "code": "UNKNOWN_TOOL",
                "message": f"Unknown tool: {name}",
                "suggestion": f"Available tools: {list(_TOOL_HANDLERS.keys())}",
            },
        }

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


def _init_services() -> dict[str, object]:
    """Initialize services for MCP tools.

    Returns:
        Services dict for init_mcp_dependencies().
    """
    from ontology_engine.services import (
        SchemaService,
        EntityService,
        AnalysisService,
        QueryService,
        IngestionService,
        DatasetService,
        IncrementalUpdateService,
        RuleService,
        SpaceService,
    )
    from ontology_engine.services.visualization_service import VisualizationService
    from ontology_engine.services.dag_service import DAGService
    from ontology_engine.services.simulation_service import SimulationService
    from ontology_engine.core.schema import SchemaLoader
    from ontology_engine.storage.sqlite.store import SQLiteStorage

    storage = SQLiteStorage()
    schema_loader = SchemaLoader()
    schema = None
    try:
        schema = schema_loader.load("examples/supply_chain_finance/schema.yaml")
    except FileNotFoundError:
        pass

    services: dict[str, object] = {}
    services["schema"] = SchemaService(storage=storage)
    services["entity"] = EntityService(storage=storage, schema=schema)
    services["analysis"] = AnalysisService(storage=storage, schema=schema)
    services["query"] = QueryService(storage=storage, rule_executor=services["analysis"].rule_executor)
    services["ingestion"] = IngestionService(storage=storage, entity_service=services["entity"])
    services["visualization"] = VisualizationService(
        schema_service=services["schema"],
        analysis_service=services["analysis"],
        storage=storage,
        schema=schema,
    )
    services["dataset"] = DatasetService(storage=storage)
    services["incremental"] = IncrementalUpdateService(storage=storage)
    services["rule"] = RuleService(storage=storage)
    services["dag"] = DAGService(storage=storage, schema=schema)
    services["simulation"] = SimulationService()
    services["space"] = SpaceService()

    return services


async def main():
    """Run the MCP server over stdio."""
    try:
        services = _init_services()
        init_mcp_dependencies(services)
    except Exception as e:
        logger.error("Failed to initialize MCP dependencies: %s", e)
        raise

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
