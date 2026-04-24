"""Analysis and simulation CLI commands."""

from __future__ import annotations

from typing import Optional

import typer

from ontology_engine.cli.client import APIClient, CLIError, format_output

app = typer.Typer(help="Analysis and simulation commands.")


@app.command()
def run(
    space_id: str = typer.Option(..., "--space-id", "-s", help="Space or View ID"),
    entity_id: str = typer.Option(..., "--entity-id", "-e", help="Entity ID to analyze, e.g. 'SUP_C1'"),
    dimension: str = typer.Option("credit_assessment", "--dimension", "-d", help="Analysis dimension"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview results without persisting"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Execute rule analysis on an entity."""
    import asyncio

    client = APIClient(base_url=base_url)
    body = {
        "entity_id": entity_id,
        "dimension": dimension,
        "include_trace": True,
        "dry_run": dry_run,
    }
    try:
        result = asyncio.run(
            client.post(f"/spaces/{space_id}/execute/analyze", json_body=body)
        )
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message, "suggestion": e.suggestion}}, format))
        raise typer.Exit(code=1)


@app.command()
def simulate(
    space_id: str = typer.Option(..., "--space-id", "-s", help="Space or View ID"),
    entity_id: str = typer.Option(..., "--entity-id", "-e", help="Entity ID to simulate"),
    dimension: str = typer.Option("credit_assessment", "--dimension", "-d", help="Analysis dimension"),
    overrides: Optional[str] = typer.Option(None, "--overrides", "-o", help="JSON overrides, e.g. '{\"revenue\": 5000000}'"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Simulate rule execution with hypothetical data overrides."""
    import asyncio
    import json

    overrides_dict = {}
    if overrides:
        try:
            overrides_dict = json.loads(overrides)
        except json.JSONDecodeError:
            typer.echo(format_output({"error": {"code": "INVALID_JSON", "message": "overrides must be valid JSON"}}, format))
            raise typer.Exit(code=1)

    client = APIClient(base_url=base_url)
    body = {
        "entity_id": entity_id,
        "dimension": dimension,
        "overrides": overrides_dict,
    }
    try:
        result = asyncio.run(
            client.post(f"/spaces/{space_id}/execute/simulate", json_body=body)
        )
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message, "suggestion": e.suggestion}}, format))
        raise typer.Exit(code=1)
