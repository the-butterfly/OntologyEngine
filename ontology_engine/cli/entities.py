"""Entity management CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from ontology_engine.cli.client import APIClient, CLIError, format_output

app = typer.Typer(help="Entity and instance management commands.")


@app.command("list")
def list_entities(
    space_id: str = typer.Option(..., "--space-id", "-s", help="Space ID"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """List all entities in a semantic space."""
    import asyncio

    client = APIClient(base_url=base_url)
    try:
        result = asyncio.run(client.get(f"/spaces/{space_id}/instances/entities"))
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message}}, format))
        raise typer.Exit(code=1)


@app.command()
def add(
    space_id: str = typer.Option(..., "--space-id", "-s", help="Space ID"),
    entity_id: str = typer.Option(..., "--entity-id", "-e", help="Entity ID, e.g. 'SUP_C1'"),
    fact_object: str = typer.Option(..., "--fact-object", help="Fact object type, e.g. 'Supplier'"),
    attributes: Optional[str] = typer.Option(None, "--attributes", "-a", help="JSON attributes string"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Add a new entity to a semantic space."""
    import asyncio
    import json

    attrs = {}
    if attributes:
        try:
            attrs = json.loads(attributes)
        except json.JSONDecodeError:
            typer.echo(format_output({"error": {"code": "INVALID_JSON", "message": "attributes must be valid JSON"}}, format))
            raise typer.Exit(code=1)

    client = APIClient(base_url=base_url)
    body = {"entity_id": entity_id, "_fact_object": fact_object, **attrs}
    try:
        result = asyncio.run(
            client.post(f"/spaces/{space_id}/instances/entities", json_body=body)
        )
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message, "suggestion": e.suggestion}}, format))
        raise typer.Exit(code=1)


@app.command()
def import_yaml(
    space_id: str = typer.Option(..., "--space-id", "-s", help="Space ID"),
    file: Path = typer.Option(..., "--file", "-f", help="YAML entity file path"),
    format: str = typer.Option("json", "--format", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Import entities from a YAML file into a semantic space."""
    import asyncio

    if not file.exists():
        typer.echo(format_output({"error": {"code": "FILE_NOT_FOUND", "message": f"File not found: {file}"}}, format))
        raise typer.Exit(code=1)

    content = file.read_text(encoding="utf-8")
    client = APIClient(base_url=base_url)
    try:
        result = asyncio.run(
            client.post(f"/spaces/{space_id}/instances/load-yaml", json_body={"yaml_content": content})
        )
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message, "suggestion": e.suggestion}}, format))
        raise typer.Exit(code=1)
