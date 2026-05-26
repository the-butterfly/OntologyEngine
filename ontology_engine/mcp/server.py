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
from ontology_engine.mcp.tools.management import oe_create_entity, oe_define_rule, oe_activate_space, oe_update_relation
from ontology_engine.mcp.tools.versioning import oe_snapshot, oe_rollback
from ontology_engine.mcp.tools.memory import (
    oe_remember,
    oe_recall,
    oe_reflect,
    oe_approve_memory,
    oe_consolidate,
    oe_forget,
    oe_memory_stats,
    oe_get_reflection_status,
    oe_memory_types,
    oe_audit_trail,
    oe_correct_memory,
    oe_delete_memory,
    oe_list_my_memories,
    oe_record_commitment,
    oe_check_commitments,
)

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
            name="oe_update_relation",
            description=(
                "Update a relation's attributes in a semantic space. "
                "For cognitive nodes, uses MemoryAPI.correct_memory."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID"},
                    "relation_id": {"type": "string", "description": "Relation ID to update"},
                    "attributes": {"type": "object", "description": "Attributes to update"},
                    "reason": {"type": "string", "description": "Reason for update"},
                },
                "required": ["space_id", "relation_id"],
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
        Tool(
            name="oe_remember",
            description=(
                "Store information into the agent's memory. Automatically extracts "
                "entities, relations, and facts. Optionally triggers consolidation "
                "to form higher-level observations. Use this whenever you encounter "
                "important information worth retaining."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The content to remember. Text, facts, observations, or any information worth retaining.",
                    },
                    "space_id": {
                        "type": "string",
                        "description": "The space ID to store the memory in.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for categorization.",
                    },
                    "memory_type": {
                        "type": "string",
                        "description": "Memory type hint: fragment, observation, episode.",
                        "default": "fragment",
                    },
                    "auto_consolidate": {
                        "type": "boolean",
                        "description": "If true, trigger consolidation after storing.",
                        "default": False,
                    },
                    "visibility": {
                        "type": "string",
                        "description": "Visibility: private (only creator), shared (space members), public (all).",
                        "enum": ["private", "shared", "public"],
                        "default": "shared",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence score (0.0-1.0). Lower values indicate uncertain information.",
                        "default": 1.0,
                    },
                    "supersede_target": {
                        "type": "string",
                        "description": "Node ID to supersede. Creates a SUPERSEDES edge and transitions the target to superseded belief status.",
                    },
                    "supersede_reason": {
                        "type": "string",
                        "description": "Reason for superseding the target node.",
                    },
                },
                "required": ["content", "space_id"],
            },
        ),
        Tool(
            name="oe_recall",
            description=(
                "Recall information from the agent's memory. Automatically routes "
                "to the best retrieval strategy and prioritizes results by memory "
                "type. Returns relevant memories with evidence chains and confidence scores."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query to search for.",
                    },
                    "space_id": {
                        "type": "string",
                        "description": "The space ID to search in.",
                    },
                    "memory_type": {
                        "type": "string",
                        "description": "Optional type filter: mental_model, opinion, entity, observation, rule, episode, procedure, fragment.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results.",
                        "default": 10,
                    },
                    "include_evidence": {
                        "type": "boolean",
                        "description": "Whether to include evidence chains.",
                        "default": True,
                    },
                    "evidence_depth": {
                        "type": "integer",
                        "description": "Evidence chain expansion depth. 1=direct sources, 2=sources of sources.",
                        "default": 1,
                    },
                    "as_of": {
                        "type": "string",
                        "description": "Temporal query: return memories as they were at this ISO timestamp.",
                    },
                    "token_budget": {
                        "type": "integer",
                        "description": "Maximum tokens in response. Truncates results to fit budget.",
                    },
                    "disposition_override": {
                        "type": "string",
                        "description": "Disposition profile scene name (e.g., 'audit' for high evidence demand, 'quick' for fast answers). Overrides default weighting.",
                    },
                },
                "required": ["query", "space_id"],
            },
        ),
        Tool(
            name="oe_reflect",
            description=(
                "Reflect on existing memories to discover contradictions, "
                "generate new insights, or update mental models. Reflection "
                "automatically triggers consolidation and forgetting as needed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or topic to reflect on.",
                    },
                    "space_id": {
                        "type": "string",
                        "description": "The space ID to reflect on.",
                    },
                    "max_iterations": {
                        "type": "integer",
                        "description": "Maximum number of reflection iterations.",
                        "default": 10,
                    },
                    "focus_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional focus on specific memory types.",
                    },
                    "cascade_depth": {
                        "type": "integer",
                        "description": "Correction propagation cascade depth. Controls how far belief changes propagate through cognitive edges.",
                        "default": 3,
                    },
                },
                "required": ["query", "space_id"],
            },
        ),
        Tool(
            name="oe_approve_memory",
            description=(
                "Approve, reject, or modify a pending memory review. "
                "Part of the three-zone model for agent-human collaboration."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {
                        "type": "string",
                        "description": "Node ID to approve, reject, or modify.",
                    },
                    "action": {
                        "type": "string",
                        "description": "Action: approve, reject, or modify.",
                        "enum": ["approve", "reject", "modify"],
                        "default": "approve",
                    },
                    "modifier_id": {
                        "type": "string",
                        "description": "ID of the modifier (user/agent).",
                        "default": "user",
                    },
                    "comment": {
                        "type": "string",
                        "description": "Optional comment for the action.",
                    },
                },
                "required": ["node_id"],
            },
        ),
        Tool(
            name="oe_consolidate",
            description=(
                "Manually trigger memory consolidation. Converts fragment "
                "memories into persistent knowledge (observations/entities). "
                "Normally triggered automatically by oe_reflect."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID to consolidate."},
                },
                "required": ["space_id"],
            },
        ),
        Tool(
            name="oe_forget",
            description=(
                "Manually trigger memory forgetting. Applies Ebbinghaus decay "
                "and demotion/archival based on memory strength. "
                "Normally triggered automatically by oe_reflect."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID to apply forgetting."},
                    "days_elapsed": {
                        "type": "integer",
                        "description": "Days since last evaluation.",
                        "default": 1,
                    },
                },
                "required": ["space_id"],
            },
        ),
        Tool(
            name="oe_memory_stats",
            description=(
                "Get memory statistics for a space: total nodes, distribution "
                "by type and belief status, average feedback weight."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID."},
                },
                "required": ["space_id"],
            },
        ),
        Tool(
            name="oe_get_reflection_status",
            description=(
                "Check the status of an asynchronous reflection job. "
                "Returns progress, partial results, and final outputs "
                "when completed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "reflection_id": {"type": "string", "description": "Reflection job ID."},
                },
                "required": ["reflection_id"],
            },
        ),
        Tool(
            name="oe_memory_types",
            description=(
                "Get memory type distribution for a space. "
                "Shows counts and average feedback weight per memory type "
                "(entity, observation, fragment, mental_model, etc.)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID."},
                },
                "required": ["space_id"],
            },
        ),
        Tool(
            name="oe_audit_trail",
            description=(
                "Query the audit trail for a space. Returns superseded, "
                "rejected, and corrected nodes. Useful for understanding "
                "the history of memory corrections."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID."},
                    "limit": {
                        "type": "integer",
                        "description": "Maximum audit entries.",
                        "default": 50,
                    },
                },
                "required": ["space_id"],
            },
        ),
        Tool(
            name="oe_correct_memory",
            description=(
                "Correct a memory's content. Creates a new superseding version "
                "with a SUPERSEDES edge. The original node transitions to "
                "'superseded' belief status. Correction propagation is triggered."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "Node ID to correct."},
                    "corrected_text": {"type": "string", "description": "The corrected content text."},
                    "reason": {"type": "string", "description": "Reason for the correction.", "default": ""},
                    "user_id": {"type": "string", "description": "User performing the correction.", "default": "mcp_user"},
                },
                "required": ["node_id", "corrected_text"],
            },
        ),
        Tool(
            name="oe_delete_memory",
            description=(
                "Delete a memory node. Protected memories (feedback_weight > 0.8) "
                "cannot be deleted. Optionally cascade to connected edges."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_id": {"type": "string", "description": "Node ID to delete."},
                    "space_id": {"type": "string", "description": "Space ID."},
                    "cascade": {"type": "boolean", "description": "Also delete connected edges.", "default": False},
                    "user_id": {"type": "string", "description": "User performing the deletion.", "default": "mcp_user"},
                },
                "required": ["node_id", "space_id"],
            },
        ),
        Tool(
            name="oe_list_my_memories",
            description=(
                "List memories belonging to a specific user. "
                "Optionally filter by scope type and memory type."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID."},
                    "user_id": {"type": "string", "description": "User ID to list memories for."},
                    "scope_type": {"type": "string", "description": "Optional scope type filter."},
                    "memory_type": {"type": "string", "description": "Optional memory type filter."},
                    "limit": {"type": "integer", "description": "Maximum results.", "default": 50},
                },
                "required": ["space_id", "user_id"],
            },
        ),
        Tool(
            name="oe_record_commitment",
            description=(
                "Record a commitment as a commitment-type memory node. "
                "Commitments track promises, deadlines, and task obligations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Commitment content/description."},
                    "space_id": {"type": "string", "description": "Space ID."},
                    "deadline": {"type": "string", "description": "Deadline in ISO datetime format."},
                    "task_id": {"type": "string", "description": "Associated task ID."},
                    "created_by": {"type": "string", "description": "Creator user ID."},
                },
                "required": ["content", "space_id"],
            },
        ),
        Tool(
            name="oe_check_commitments",
            description=(
                "Check commitments in a space. Optionally filter by status "
                "or show only overdue commitments."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "space_id": {"type": "string", "description": "Space ID."},
                    "status": {"type": "string", "description": "Filter by status: pending, fulfilled, overdue."},
                    "overdue": {"type": "boolean", "description": "Show only overdue commitments.", "default": False},
                },
                "required": ["space_id"],
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
        "oe_update_relation": oe_update_relation,
        "oe_snapshot": oe_snapshot,
        "oe_rollback": oe_rollback,
        "oe_remember": oe_remember,
        "oe_recall": oe_recall,
        "oe_reflect": oe_reflect,
        "oe_approve_memory": oe_approve_memory,
        "oe_consolidate": oe_consolidate,
        "oe_forget": oe_forget,
        "oe_memory_stats": oe_memory_stats,
        "oe_get_reflection_status": oe_get_reflection_status,
        "oe_memory_types": oe_memory_types,
        "oe_audit_trail": oe_audit_trail,
        "oe_correct_memory": oe_correct_memory,
        "oe_delete_memory": oe_delete_memory,
        "oe_list_my_memories": oe_list_my_memories,
        "oe_record_commitment": oe_record_commitment,
        "oe_check_commitments": oe_check_commitments,
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
    from ontology_engine.storage.config import create_meta_store
    from ontology_engine.core.schema import SchemaLoader

    storage = create_meta_store()
    schema = None
    try:
        schema_loader = SchemaLoader()
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
