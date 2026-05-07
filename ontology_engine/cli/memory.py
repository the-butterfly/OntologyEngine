"""Memory CLI commands."""

from __future__ import annotations

from typing import Any

import typer

from ontology_engine.cli.client import APIClient, format_output

app = typer.Typer(
    name="memory",
    help="Agent memory operations: remember, recall, reflect, approve, consolidate, forget, stats",
    no_args_is_help=True,
)


@app.command()
def remember(
    content: str = typer.Option(..., "--content", "-c", help="Content to remember"),
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    tags: str = typer.Option("", "--tags", "-t", help="Tags (comma-separated)"),
    memory_type: str = typer.Option("fragment", "--type", help="Memory type hint"),
    auto_consolidate: bool = typer.Option(False, "--auto-consolidate", help="Auto-consolidate after storage"),
    confidence: float = typer.Option(1.0, "--confidence", help="Confidence score (0.0-1.0)"),
    belief_status: str = typer.Option("accepted", "--belief", help="Belief status (accepted/pending_review)"),
    valid_from: str | None = typer.Option(None, "--valid-from", help="Valid from (ISO datetime)"),
    valid_to: str | None = typer.Option(None, "--valid-to", help="Valid to (ISO datetime)"),
    occurred_at: str | None = typer.Option(None, "--occurred-at", help="When the event occurred (ISO datetime)"),
    supersede_target: str | None = typer.Option(None, "--supersede", help="Node ID to supersede"),
    supersede_reason: str | None = typer.Option(None, "--supersede-reason", help="Reason for superseding"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Store information into the agent's memory."""
    import asyncio

    client = APIClient(base_url=base_url)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None

    payload: dict[str, Any] = {
        "content": content,
        "tags": tag_list,
        "memory_type": memory_type,
        "auto_consolidate": auto_consolidate,
        "confidence": confidence,
        "belief_status": belief_status,
    }
    if valid_from:
        payload["valid_from"] = valid_from
    if valid_to:
        payload["valid_to"] = valid_to
    if occurred_at:
        payload["occurred_at"] = occurred_at
    if supersede_target:
        payload["supersede_target"] = supersede_target
    if supersede_reason:
        payload["supersede_reason"] = supersede_reason

    result = asyncio.run(
        client.post(
            f"/spaces/{space}/memory/remember",
            payload,
        )
    )
    typer.echo(format_output(result))


@app.command()
def recall(
    query: str = typer.Option(..., "--query", "-q", help="Search query"),
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    memory_type: str | None = typer.Option(None, "--type", help="Memory type filter"),
    max_results: int = typer.Option(10, "--max", "-n", help="Max results"),
    as_of: str | None = typer.Option(None, "--as-of", help="Temporal filter (ISO datetime)"),
    belief_status_filter: str | None = typer.Option(None, "--belief-filter", help="Belief status filter"),
    min_confidence: float = typer.Option(0.5, "--min-confidence", help="Minimum confidence threshold"),
    cognitive_layer: str | None = typer.Option(None, "--layer", help="Cognitive layer filter"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Recall information from the agent's memory."""
    import asyncio

    client = APIClient(base_url=base_url)

    payload: dict[str, Any] = {
        "query": query,
        "memory_type": memory_type,
        "max_results": max_results,
        "min_confidence": min_confidence,
    }
    if as_of:
        payload["as_of"] = as_of
    if belief_status_filter:
        payload["belief_status_filter"] = belief_status_filter
    if cognitive_layer:
        payload["cognitive_layer"] = cognitive_layer

    result = asyncio.run(
        client.post(
            f"/spaces/{space}/memory/recall",
            payload,
        )
    )
    typer.echo(format_output(result))


@app.command()
def reflect(
    query: str = typer.Option(..., "--query", "-q", help="Reflection query"),
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    max_iterations: int = typer.Option(10, "--max-iter", help="Max iterations"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Reflect on memories to discover contradictions and insights."""
    import asyncio

    client = APIClient(base_url=base_url)

    result = asyncio.run(
        client.post(
            f"/spaces/{space}/memory/reflect",
            {
                "query": query,
                "max_iterations": max_iterations,
            },
        )
    )
    typer.echo(format_output(result))


@app.command()
def approve(
    node_id: str = typer.Option(..., "--node-id", "-n", help="Node ID to approve/reject"),
    action: str = typer.Option("approve", "--action", "-a", help="Action: approve, reject, modify"),
    comment: str = typer.Option("", "--comment", "-m", help="Approval comment"),
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Approve, reject, or modify a pending memory review."""
    import asyncio

    client = APIClient(base_url=base_url)

    result = asyncio.run(
        client.post(
            f"/spaces/{space}/memory/approve",
            {
                "node_id": node_id,
                "action": action,
                "comment": comment,
                "modifier_id": "cli_user",
            },
        )
    )
    typer.echo(format_output(result))


@app.command()
def consolidate(
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Manually trigger memory consolidation."""
    import asyncio

    client = APIClient(base_url=base_url)

    result = asyncio.run(
        client.post(
            f"/spaces/{space}/memory/consolidate",
            {},
        )
    )
    typer.echo(format_output(result))


@app.command()
def forget(
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    days: int = typer.Option(1, "--days", "-d", help="Days elapsed"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Manually trigger memory forgetting."""
    import asyncio

    client = APIClient(base_url=base_url)

    result = asyncio.run(
        client.post(
            f"/spaces/{space}/memory/forget",
            {"days_elapsed": days},
        )
    )
    typer.echo(format_output(result))


@app.command()
def stats(
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Get memory statistics for a space."""
    import asyncio

    client = APIClient(base_url=base_url)

    result = asyncio.run(
        client.get(
            f"/spaces/{space}/memory/stats",
        )
    )
    typer.echo(format_output(result))


@app.command()
def types(
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Get memory type distribution with strength per type."""
    import asyncio

    client = APIClient(base_url=base_url)

    result = asyncio.run(
        client.get(
            f"/spaces/{space}/memory/types",
        )
    )
    typer.echo(format_output(result))


@app.command()
def audit(
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max audit entries"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Query audit trail (superseded/rejected nodes)."""
    import asyncio

    client = APIClient(base_url=base_url)

    result = asyncio.run(
        client.get(
            f"/spaces/{space}/memory/audit?limit={limit}",
        )
    )
    typer.echo(format_output(result))


@app.command()
def correct(
    node_id: str = typer.Option(..., "--node-id", "-n", help="Node ID to correct"),
    corrected_text: str = typer.Option(..., "--text", "-t", help="Corrected text"),
    reason: str = typer.Option("", "--reason", "-r", help="Reason for correction"),
    user_id: str = typer.Option("cli_user", "--user", "-u", help="User performing correction"),
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Correct a memory's content, creating a new superseding version."""
    import asyncio

    client = APIClient(base_url=base_url)

    result = asyncio.run(
        client.patch(
            f"/spaces/{space}/memory/{node_id}/correct",
            {
                "corrected_text": corrected_text,
                "reason": reason,
                "user_id": user_id,
            },
        )
    )
    typer.echo(format_output(result))


@app.command()
def delete(
    node_id: str = typer.Option(..., "--node-id", "-n", help="Node ID to delete"),
    cascade: bool = typer.Option(False, "--cascade", help="Also delete connected edges"),
    user_id: str = typer.Option("cli_user", "--user", "-u", help="User performing deletion"),
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Delete a memory node."""
    import asyncio

    client = APIClient(base_url=base_url)

    result = asyncio.run(
        client.delete(
            f"/spaces/{space}/memory/{node_id}?cascade={cascade}&user_id={user_id}",
        )
    )
    typer.echo(format_output(result))


@app.command("list-my")
def list_my(
    user_id: str = typer.Option(..., "--user", "-u", help="User ID to list memories for"),
    scope_type: str | None = typer.Option(None, "--scope", help="Filter by scope type"),
    memory_type: str | None = typer.Option(None, "--type", help="Filter by memory type"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results"),
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """List memories belonging to a specific user."""
    import asyncio

    client = APIClient(base_url=base_url)

    params = [f"user_id={user_id}", f"limit={limit}"]
    if scope_type:
        params.append(f"scope_type={scope_type}")
    if memory_type:
        params.append(f"memory_type={memory_type}")

    result = asyncio.run(
        client.get(
            f"/spaces/{space}/memory/my?{'&'.join(params)}",
        )
    )
    typer.echo(format_output(result))


@app.command("record-commitment")
def record_commitment(
    content: str = typer.Option(..., "--content", "-c", help="Commitment content"),
    deadline: str | None = typer.Option(None, "--deadline", "-d", help="Deadline (ISO datetime)"),
    task_id: str | None = typer.Option(None, "--task-id", "-t", help="Associated task ID"),
    created_by: str | None = typer.Option(None, "--created-by", help="Creator user ID"),
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Record a commitment as a commitment-type memory."""
    import asyncio

    client = APIClient(base_url=base_url)

    payload: dict[str, Any] = {"content": content}
    if deadline:
        payload["deadline"] = deadline
    if task_id:
        payload["task_id"] = task_id
    if created_by:
        payload["created_by"] = created_by

    result = asyncio.run(
        client.post(
            f"/spaces/{space}/memory/commitments",
            payload,
        )
    )
    typer.echo(format_output(result))


@app.command("check-commitments")
def check_commitments(
    status: str | None = typer.Option(None, "--status", help="Filter by status (pending/fulfilled/overdue)"),
    overdue: bool = typer.Option(False, "--overdue", help="Show only overdue commitments"),
    space: str = typer.Option("default", "--space", "-s", help="Space ID"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Check commitments in a space."""
    import asyncio

    client = APIClient(base_url=base_url)

    params: list[str] = []
    if status:
        params.append(f"status={status}")
    if overdue:
        params.append("overdue=true")

    query = f"?{'&'.join(params)}" if params else ""
    result = asyncio.run(
        client.get(
            f"/spaces/{space}/memory/commitments{query}",
        )
    )
    typer.echo(format_output(result))
