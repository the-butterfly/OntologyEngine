"""Space management CLI commands."""

from __future__ import annotations

from typing import Optional

import typer

from ontology_engine.cli.client import APIClient, CLIError, format_output

app = typer.Typer(help="Semantic space management commands.")


def _get_client(base_url: str) -> APIClient:
    return APIClient(base_url=base_url)


@app.command()
def create(
    name: str = typer.Option(..., "--name", "-n", help="Space name, e.g. 'Supply Chain Finance'"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Space description"),
    domain: Optional[str] = typer.Option(None, "--domain", help="Business domain, e.g. 'finance'"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Create a new semantic space in DRAFT status."""
    import asyncio

    client = _get_client(base_url)
    try:
        result = asyncio.run(
            client.post("/spaces", json_body={"name": name, "description": description, "domain": domain})
        )
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message, "suggestion": e.suggestion}}, format))
        raise typer.Exit(code=1)


@app.command("list")
def list_spaces(
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """List all semantic spaces."""
    import asyncio

    client = _get_client(base_url)
    try:
        result = asyncio.run(client.get("/spaces"))
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message}}, format))
        raise typer.Exit(code=1)


@app.command()
def get(
    space_id: str = typer.Argument(help="Space ID, e.g. 'space_supply_chain_finance'"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Get detailed information about a semantic space."""
    import asyncio

    client = _get_client(base_url)
    try:
        result = asyncio.run(client.get(f"/spaces/{space_id}"))
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message}}, format))
        raise typer.Exit(code=1)


@app.command()
def activate(
    space_id: str = typer.Argument(help="Space ID to activate"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Activate a semantic space (transitions from DRAFT to ACTIVE)."""
    import asyncio

    client = _get_client(base_url)
    try:
        result = asyncio.run(
            client.put(f"/spaces/{space_id}", json_body={"status": "ACTIVE"})
        )
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message, "suggestion": e.suggestion}}, format))
        raise typer.Exit(code=1)


@app.command()
def deactivate(
    space_id: str = typer.Argument(help="Space ID to deactivate"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Deactivate a semantic space (transitions to INACTIVE)."""
    import asyncio

    client = _get_client(base_url)
    try:
        result = asyncio.run(
            client.put(f"/spaces/{space_id}", json_body={"status": "INACTIVE"})
        )
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message}}, format))
        raise typer.Exit(code=1)


@app.command()
def delete(
    space_id: str = typer.Argument(help="Space ID to delete"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview what would be deleted without actually deleting"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Delete a semantic space and all its associated data."""
    import asyncio

    client = _get_client(base_url)
    try:
        result = asyncio.run(client.delete(f"/spaces/{space_id}", params={"dry_run": dry_run}))
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message, "suggestion": e.suggestion}}, format))
        raise typer.Exit(code=1)
