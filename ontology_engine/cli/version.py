"""Version management CLI commands."""

from __future__ import annotations

import typer

from ontology_engine.cli.client import APIClient, CLIError, format_output

app = typer.Typer(help="Version snapshot and rollback commands.")


@app.command("list")
def list_versions(
    space_id: str = typer.Option(..., "--space-id", "-s", help="Space ID"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """List all version snapshots for a semantic space."""
    import asyncio

    client = APIClient(base_url=base_url)
    try:
        result = asyncio.run(client.get(f"/spaces/{space_id}/versions"))
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message}}, format))
        raise typer.Exit(code=1)


@app.command()
def create(
    space_id: str = typer.Option(..., "--space-id", "-s", help="Space ID"),
    description: str = typer.Option("", "--description", "-d", help="Snapshot description"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Create a version snapshot of a semantic space."""
    import asyncio

    client = APIClient(base_url=base_url)
    try:
        result = asyncio.run(
            client.post(f"/spaces/{space_id}/versions", json_body={"description": description})
        )
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message, "suggestion": e.suggestion}}, format))
        raise typer.Exit(code=1)


@app.command()
def rollback(
    space_id: str = typer.Option(..., "--space-id", "-s", help="Space ID"),
    version: int = typer.Argument(help="Version number to rollback to"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview rollback diff without actually rolling back"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Rollback a semantic space to a specific version."""
    import asyncio

    client = APIClient(base_url=base_url)
    try:
        post_params = {"dry_run": "true"} if dry_run else None
        result = asyncio.run(
            client.post(
                f"/spaces/{space_id}/versions/{version}/rollback",
                json_body=None,
                params=post_params,
            )
        )
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message, "suggestion": e.suggestion}}, format))
        raise typer.Exit(code=1)
