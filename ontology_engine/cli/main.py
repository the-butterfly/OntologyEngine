"""OntologyEngine CLI — Agent-friendly command-line interface."""

from __future__ import annotations

import typer

from ontology_engine.cli import space, schema, entities, analyze, query, version

app = typer.Typer(
    name="ontology-cli",
    help="OntologyEngine CLI — Agent-friendly command-line interface for semantic space management.",
    no_args_is_help=True,
)

app.add_typer(space.app, name="space", help="Semantic space management (create, list, get, activate, deactivate, delete)")
app.add_typer(schema.app, name="schema", help="Schema management (load, show, validate)")
app.add_typer(entities.app, name="entities", help="Entity management (list, add, import)")
app.add_typer(analyze.app, name="analyze", help="Analysis and simulation (run, simulate)")
app.add_typer(query.app, name="query", help="Knowledge retrieval (search)")
app.add_typer(version.app, name="version", help="Version management (list, create, rollback)")


@app.command()
def health(
    base_url: str = typer.Option("http://localhost:8000/v1", "--api-url", help="API base URL"),
):
    """Check if the OntologyEngine API server is running."""
    import asyncio
    from ontology_engine.cli.client import APIClient, CLIError, format_output

    client = APIClient(base_url=base_url)
    try:
        result = asyncio.run(client.get("/spaces"))
        typer.echo(format_output({"status": "healthy", "spaces_count": len(result.get("data", {}).get("spaces", []))}))
    except CLIError:
        typer.echo(format_output({"status": "unhealthy", "message": "Cannot connect to API server"}))
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(format_output({"status": "unhealthy", "message": str(e)}))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
