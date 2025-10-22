#!/usr/bin/env python3
"""Main entry point for ATOMICA MCP server."""

from atomica_mcp.server import app, cli_app_stdio_standalone, cli_app_sse_standalone, cli_app_run

if __name__ == "__main__":
    app()

