"""Execution MCP tools — oe_execute_rule and oe_simulate."""

import asyncio

from ontology_engine.mcp import mcp_response, get_service


async def oe_execute_rule(
    entity_id: str,
    view_id: str,
    dimension: str = "credit_assessment",
    explain_level: str = "brief",
    dry_run: bool = False,
) -> dict[str, object]:
    """Execute rule analysis on an entity.

    Runs the complete analysis pipeline (L2 categorization → L3 metric
    computation → L4 rule execution) for the specified entity and dimension.
    Set dry_run=true to preview results without persisting.

    Parameters:
        entity_id: Entity ID to analyze (e.g., "SUP_C1")
        view_id: View or space ID (e.g., "view_supply_chain_finance")
        dimension: Analysis dimension (e.g., "credit_assessment", "compliance_assessment")
        explain_level: Explanation detail level. Options: "full" (all steps), "detailed" (key steps), "brief" (summary only)
        dry_run: If true, preview results without persisting changes

    Returns:
        MCP unified format: {success, data, error}
        data contains: entity_id, dimension, decision, rule_results, computed_metrics
    """
    try:
        space_service = get_service("space")
        space = await space_service.get_space(view_id)
        if not space:
            return mcp_response(
                success=False,
                error={
                    "code": "SPACE_NOT_FOUND",
                    "message": f"Space '{view_id}' not found",
                    "suggestion": "Use oe_list_spaces to find available spaces",
                },
            )

        entity = next(
            (e for e in space.instances.entities if e.get("entity_id") == entity_id),
            None,
        )
        if not entity:
            return mcp_response(
                success=False,
                error={
                    "code": "ENTITY_NOT_FOUND",
                    "message": f"Entity '{entity_id}' not found in space '{view_id}'",
                    "suggestion": "Check entity_id or use a different view_id",
                },
            )

        analysis_service = get_service("analysis")

        if dry_run:
            result = await analysis_service.execute_dry_run(
                entity_id=entity_id,
                dimension=dimension,
                context={"overrides": {}},
            )
        else:
            result = await analysis_service.execute_analysis(
                entity_id=entity_id,
                dimension=dimension,
                context={"overrides": {}},
            )

        result_dict = _serialize_analysis_result(result, explain_level)
        result_dict["dry_run"] = dry_run

        return mcp_response(success=True, data=result_dict)
    except RuntimeError as e:
        return mcp_response(
            success=False,
            error={"code": "DEPS_NOT_INITIALIZED", "message": str(e)},
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "ANALYSIS_ERROR", "message": str(e)},
        )


async def oe_simulate(
    entity_id: str,
    view_id: str,
    dimension: str = "credit_assessment",
    overrides: dict | None = None,
) -> dict:
    """Simulate rule execution with hypothetical data overrides.

    Runs two analyses in parallel: baseline (current data) and simulated
    (with overrides applied). Returns both results for comparison.
    No data is persisted.

    Parameters:
        entity_id: Entity ID to simulate (e.g., "SUP_C1")
        view_id: View or space ID (e.g., "view_supply_chain_finance")
        dimension: Analysis dimension (e.g., "credit_assessment")
        overrides: Field overrides for simulation. Keys are field names,
                   values are hypothetical values.
                   Example: {"revenue": 5000000, "risk_level": "high"}

    Returns:
        MCP unified format: {success, data, error}
        data contains: baseline, simulated, overrides_applied
    """
    try:
        space_service = get_service("space")
        space = await space_service.get_space(view_id)
        if not space:
            return mcp_response(
                success=False,
                error={
                    "code": "SPACE_NOT_FOUND",
                    "message": f"Space '{view_id}' not found",
                    "suggestion": "Use oe_list_spaces to find available spaces",
                },
            )

        entity = next(
            (e for e in space.instances.entities if e.get("entity_id") == entity_id),
            None,
        )
        if not entity:
            return mcp_response(
                success=False,
                error={
                    "code": "ENTITY_NOT_FOUND",
                    "message": f"Entity '{entity_id}' not found in space '{view_id}'",
                    "suggestion": "Check entity_id or use a different view_id",
                },
            )

        analysis_service = get_service("analysis")

        baseline, simulated = await asyncio.gather(
            analysis_service.execute_dry_run(
                entity_id=entity_id,
                dimension=dimension,
                context={"overrides": {}},
            ),
            analysis_service.execute_dry_run(
                entity_id=entity_id,
                dimension=dimension,
                context={"overrides": overrides or {}},
            ),
        )

        return mcp_response(
            success=True,
            data={
                "baseline": _serialize_analysis_result(baseline, "brief"),
                "simulated": _serialize_analysis_result(simulated, "brief"),
                "overrides_applied": overrides or {},
            },
        )
    except RuntimeError as e:
        return mcp_response(
            success=False,
            error={"code": "DEPS_NOT_INITIALIZED", "message": str(e)},
        )
    except Exception as e:
        return mcp_response(
            success=False,
            error={"code": "SIMULATION_ERROR", "message": str(e)},
        )


def _serialize_analysis_result(result: object, explain_level: str) -> dict:
    """Serialize an AnalysisResponse to a plain dict."""
    if hasattr(result, "to_dict") and callable(result.to_dict):
        return result.to_dict()

    data = {}
    for attr in ("entity_id", "fact_object", "dimension", "decision",
                 "decision_reasoning", "computed_metrics", "category_tags"):
        val = getattr(result, attr, None)
        if val is not None:
            if hasattr(val, "to_dict") and callable(val.to_dict):
                data[attr] = val.to_dict()
            elif isinstance(val, list):
                data[attr] = [
                    item.to_dict() if hasattr(item, "to_dict") and callable(item.to_dict)
                    else str(item)
                    for item in val
                ]
            else:
                data[attr] = val

    if explain_level != "brief":
        rule_results = getattr(result, "rule_results", [])
        data["rule_results"] = [
            rr.to_dict() if hasattr(rr, "to_dict") and callable(rr.to_dict)
            else {"rule_id": getattr(rr, "rule_id", ""), "passed": getattr(rr, "passed", False)}
            for rr in rule_results
        ]

        alerts = getattr(result, "alerts", [])
        data["alerts"] = [
            a.to_dict() if hasattr(a, "to_dict") and callable(a.to_dict)
            else {"level": getattr(a, "level", "info"), "message": getattr(a, "message", "")}
            for a in alerts
        ]

    return data
