# ATOMICA MCP - Quick Reference

## Installation

### For Claude Desktop (Recommended)

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "atomica": {
      "command": "uvx",
      "args": ["atomica-mcp"],
      "env": {}
    }
  }
}
```

**Location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

### Manual Installation

```bash
# Install with pip
pip install atomica-mcp

# Install with uv
uv pip install atomica-mcp

# Run server (stdio by default)
atomica-mcp
```

## Quick Test

```bash
# Test the command works (runs stdio by default)
uvx atomica-mcp

# Or test with help
uvx atomica-mcp --help
```

## Available Commands

- `atomica-mcp` - Run with stdio transport (default, for AI assistants)
- `atomica-stdio` - Run with stdio transport (same as above)
- `atomica-run` - Run with HTTP transport
- `atomica-sse` - Run with SSE transport
- `atomica-cli` - Full CLI with subcommands (stdio/run/sse)
- `dataset` - Manage ATOMICA dataset
- `pdb-mining` - PDB mining utilities

## Configuration Options

### With Custom Timeout (10 minutes)

```json
{
  "mcpServers": {
    "atomica": {
      "command": "uvx",
      "args": ["atomica-mcp"],
      "env": {
        "MCP_TIMEOUT": "600"
      }
    }
  }
}
```

### For Local Development

```json
{
  "mcpServers": {
    "atomica": {
      "command": "/path/to/atomica-mcp/.venv/bin/atomica-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

### HTTP Server

```bash
# Start server
atomica-run --host localhost --port 3002
```

```json
{
  "mcpServers": {
    "atomica": {
      "url": "http://localhost:3002/mcp",
      "transport": "streamable-http"
    }
  }
}
```

## Available Tools

1. `atomica_list_structures` - List all structures
2. `atomica_get_structure` - Get structure details
3. `atomica_get_structure_files` - Get file paths
4. `atomica_search_by_gene` - Search by gene (NFE2L2, KEAP1, SOX2, APOE, POU5F1)
5. `atomica_search_by_organism` - Search by organism
6. `atomica_resolve_pdb` - Resolve any PDB ID
7. `atomica_get_structures_for_uniprot` - Get structures for UniProt ID
8. `atomica_dataset_info` - Dataset statistics

## Example Queries for Claude

```
"What structures are available for KEAP1?"
"Tell me about structure 1b68"
"Get information about PDB 1tup"
"List all structures in the ATOMICA dataset"
"What proteins are studied in the ATOMICA dataset?"
```

## Troubleshooting

### Server not appearing in Claude Desktop

1. Check config file path is correct
2. Restart Claude Desktop completely
3. Test command: `uvx --from atomica-mcp atomica-stdio --help`
4. Check Claude Desktop logs for errors

### Timeout errors

Increase timeout in environment:
```json
"env": {
  "MCP_TIMEOUT": "600"
}
```

### Dataset not downloading

Dataset auto-downloads on first use. Manual download:
```bash
uv tool run atomica-mcp dataset download
```

## Links

- **GitHub**: https://github.com/longevity-genie/atomica-mcp
- **Dataset**: https://huggingface.co/datasets/longevity-genie/atomica_longevity_proteins
- **MCP Docs**: https://modelcontextprotocol.io/

