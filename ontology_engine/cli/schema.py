"""Schema management CLI commands."""

from __future__ import annotations

from pathlib import Path

import typer

from ontology_engine.cli.client import APIClient, CLIError, format_output

app = typer.Typer(help="Schema management commands.")


@app.command()
def load(
    space_id: str = typer.Option(..., "--space-id", "-s", help="Space ID to load schema into"),
    file: Path = typer.Option(..., "--file", "-f", help="YAML schema file path"),
    format: str = typer.Option("json", "--format", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Load a YAML schema file into a semantic space."""
    import asyncio

    if not file.exists():
        typer.echo(format_output({"error": {"code": "FILE_NOT_FOUND", "message": f"File not found: {file}"}}, format))
        raise typer.Exit(code=1)

    content = file.read_text(encoding="utf-8")
    client = APIClient(base_url=base_url)
    try:
        result = asyncio.run(
            client.post(f"/spaces/{space_id}/schema/load-yaml", json_body={"yaml_content": content})
        )
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message, "suggestion": e.suggestion}}, format))
        raise typer.Exit(code=1)


@app.command()
def show(
    space_id: str = typer.Option(..., "--space-id", "-s", help="Space ID"),
    format: str = typer.Option("json", "--format", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Show schema overview for a semantic space."""
    import asyncio

    client = APIClient(base_url=base_url)
    try:
        result = asyncio.run(client.get(f"/spaces/{space_id}"))
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message}}, format))
        raise typer.Exit(code=1)


@app.command()
def validate(
    file: Path = typer.Argument(help="YAML schema file to validate"),
    format: str = typer.Option("json", "--format", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Validate a YAML schema file without loading it."""
    if not file.exists():
        typer.echo(format_output({"error": {"code": "FILE_NOT_FOUND", "message": f"File not found: {file}"}}, format))
        raise typer.Exit(code=1)

    try:
        from ontology_engine.core.schema import SchemaLoader
        loader = SchemaLoader()
        loader.load(str(file))
        typer.echo(format_output({"valid": True, "file": str(file)}, format))
    except Exception as e:
        typer.echo(format_output({"valid": False, "file": str(file), "error": str(e)}, format))
        raise typer.Exit(code=1)
