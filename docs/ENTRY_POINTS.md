# Entry Points Configuration - Final

## ✅ Complete Entry Points Setup

### Primary Entry Points

| Command | Purpose | Default Behavior |
|---------|---------|------------------|
| `atomica-mcp` | **Main MCP server** | Runs stdio transport by default (no subcommand needed) |
| `atomica-stdio` | Stdio transport | Same as `atomica-mcp` |
| `atomica-run` | HTTP transport | Runs HTTP server on port 3002 |
| `atomica-sse` | SSE transport | Runs SSE server on port 3002 |
| `atomica-cli` | Full CLI interface | Requires subcommands (stdio/run/sse) |

### Utility Commands

| Command | Purpose |
|---------|---------|
| `dataset` | Manage ATOMICA dataset (download, index, etc.) |
| `pdb-mining` | PDB mining utilities |
| `upload-to-hf` | Upload dataset to Hugging Face |

## Configuration in pyproject.toml

```toml
[project.scripts]
atomica-mcp = "atomica_mcp.__main__:cli_app_stdio_standalone"    # Default: stdio
atomica-stdio = "atomica_mcp.__main__:cli_app_stdio_standalone"  # Explicit stdio
atomica-sse = "atomica_mcp.__main__:cli_app_sse_standalone"      # SSE server
atomica-run = "atomica_mcp.__main__:cli_app_run"                 # HTTP server
atomica-cli = "atomica_mcp.__main__:app"                         # Full CLI with subcommands
dataset = "atomica_mcp.dataset:app"
pdb-mining = "atomica_mcp.mining.cli:main"
upload-to-hf = "atomica_mcp.upload_to_hf:app"
```

## MCP Client Configuration

### Simplest Configuration (Recommended)

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

This works because:
1. `uvx atomica-mcp` installs the package from PyPI
2. `atomica-mcp` command runs stdio by default (no subcommand needed)
3. Clean and simple - just the package name!

### Alternative Configurations

**Using atomica-stdio explicitly:**
```json
{
  "mcpServers": {
    "atomica": {
      "command": "uvx",
      "args": ["--from", "atomica-mcp", "atomica-stdio"],
      "env": {}
    }
  }
}
```

**Locally installed:**
```json
{
  "mcpServers": {
    "atomica": {
      "command": "atomica-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

## Command Line Usage

### Default Behavior (stdio)
```bash
# All of these do the same thing
atomica-mcp
atomica-stdio
uvx atomica-mcp
```

### Other Transports
```bash
# HTTP server
atomica-run --host localhost --port 3002
uvx --from atomica-mcp atomica-run

# SSE server
atomica-sse --host localhost --port 3002
uvx --from atomica-mcp atomica-sse
```

### Using CLI Interface
```bash
# If you need subcommands
atomica-cli stdio
atomica-cli run --host localhost --port 3002
atomica-cli sse --host localhost --port 3002
```

## Why This Design?

### ✅ Advantages

1. **Simple Default**: `uvx atomica-mcp` just works for MCP use case
2. **No Confusion**: Default command runs stdio (what 99% of users need)
3. **Explicit Options**: Other transports have dedicated commands
4. **CLI Available**: `atomica-cli` for users who want subcommands
5. **Clean Config**: Minimal JSON configuration for Claude Desktop

### 📋 Design Decisions

- **`atomica-mcp` = stdio by default**: MCP servers almost always use stdio with AI assistants
- **Dedicated commands for other transports**: Clear and obvious (`atomica-run`, `atomica-sse`)
- **`atomica-cli` for subcommands**: Power users who prefer CLI-style can still use it
- **No `--from` needed with uvx**: Package name matches command name for simplicity

## Testing

```bash
# Test default command
uvx atomica-mcp --help

# Test other commands
uvx --from atomica-mcp atomica-stdio --help
uvx --from atomica-mcp atomica-run --help
uvx --from atomica-mcp atomica-sse --help
uvx --from atomica-mcp atomica-cli --help
```

## Comparison with opengenes-mcp

Both packages now follow the same pattern:
```bash
uvx atomica-mcp   # runs stdio
uvx opengenes-mcp # runs stdio
```

Clean, consistent, and user-friendly! 🎉

