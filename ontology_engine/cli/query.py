"""Query CLI commands."""

from __future__ import annotations

import typer

from ontology_engine.cli.client import APIClient, CLIError, format_output

app = typer.Typer(help="Knowledge retrieval and query commands.")


@app.command()
def search(
    query: str = typer.Argument(help="Search text, e.g. 'high risk suppliers'"),
    match_mode: str = typer.Option("hybrid", "--mode", "-m", help="Search mode: vector|keyword|hybrid|pattern"),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Maximum number of results"),
    format: str = typer.Option("json", "--format", "-f", help="Output format: json|table|yaml"),
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Search for entities and relations across semantic spaces."""
    import asyncio

    client = APIClient(base_url=base_url)
    body = {"query_text": query, "match_mode": match_mode, "top_k": top_k}
    try:
        result = asyncio.run(client.post("/query/search", json_body=body))
        typer.echo(format_output(result.get("data", result), format))
    except CLIError as e:
        typer.echo(format_output({"error": {"code": e.code, "message": e.message}}, format))
        raise typer.Exit(code=1)
