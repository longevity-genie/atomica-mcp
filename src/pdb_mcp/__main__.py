#!/usr/bin/env python3
"""
PDB-MCP: Model Context Protocol server for PDB structure queries and protein resolution.

Provides MCP tools for:
- Querying PDB structures by ID, keyword, or organism
- Fetching protein metadata and organism information
- Resolving proteins from PDB chains using AnAge database
- Getting structural statistics and classifications
"""

import typer
from pdb_mcp.server import mcp, DEFAULT_HOST, DEFAULT_PORT


app = typer.Typer(help="PDB-MCP Server - Protein structure queries and resolution")


@app.command("run")
def cli_app(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Host to bind to"),
    port: int = typer.Option(DEFAULT_PORT, "--port", help="Port to bind to"),
    transport: str = typer.Option("streamable-http", "--transport", help="Transport type"),
) -> None:
    """Run the PDB MCP server with specified transport."""
    mcp.run(transport=transport, host=host, port=port)


@app.command("stdio")
def cli_app_stdio(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Run the MCP server with stdio transport."""
    mcp.run(transport="stdio")


@app.command("sse")
def cli_app_sse(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Host to bind to"),
    port: int = typer.Option(DEFAULT_PORT, "--port", help="Port to bind to"),
) -> None:
    """Run the MCP server with SSE transport."""
    mcp.run(transport="sse", host=host, port=port)


# Standalone CLI functions for direct script access
def cli_app_run() -> None:
    """Standalone function for pdb-mcp-run script."""
    mcp.run(transport="streamable-http", host=DEFAULT_HOST, port=DEFAULT_PORT)


def cli_app_stdio_standalone() -> None:
    """Standalone function for pdb-mcp-stdio script."""
    mcp.run(transport="stdio")


def cli_app_sse_standalone() -> None:
    """Standalone function for pdb-mcp-sse script."""
    mcp.run(transport="sse", host=DEFAULT_HOST, port=DEFAULT_PORT)


if __name__ == "__main__":
    import sys
    # Show help if no arguments provided
    if len(sys.argv) == 1:
        app(["--help"])
    else:
        app()
