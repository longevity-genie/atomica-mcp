# atomica-mcp

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP (Model Context Protocol) server for ATOMICA longevity proteins dataset and PDB structure analysis.

## What is ATOMICA?

**ATOMICA** is a geometric deep learning model that learns atomic-scale representations of intermolecular interactions across proteins, small molecules, ions, lipids, and nucleic acids. Trained on 2M+ interaction complexes, it generates embeddings that capture physicochemical features shared across molecular classes.

### Why ATOMICA Embeddings Are Useful

- **Interaction Scoring**: ATOMICA embeddings quantify interface similarity and predict binding partners based on learned physicochemical patterns
- **Critical Residues**: Identifies residues that most influence interactions (low ATOMICA scores = high impact on binding)
- **Cross-Modal Transfer**: Knowledge learned from protein-protein interactions helps predict protein-ligand binding
- **Visualization**: PyMOL commands highlight interaction-critical regions for structural analysis

### This MCP Server Provides

This server provides access to the ATOMICA longevity proteins dataset from Hugging Face, which contains comprehensive structural analysis of key aging-related proteins using the ATOMICA deep learning model. The server also provides auxiliary functions for resolving arbitrary PDB structures and UniProt IDs.

## Features

- **ATOMICA Dataset Access**: Query the curated dataset of 94 longevity-related protein structures
- **Automatic Dataset Management**: Downloads dataset from Hugging Face on first use
- **Comprehensive Metadata**: Access PDB metadata, ATOMICA interaction scores, critical residues, and PyMOL scripts
- **Gene-Based Queries**: Search structures by gene symbols (NFE2L2, KEAP1, SOX2, APOE, OCT4)
- **Organism Queries**: Filter structures by organism
- **PDB Resolution**: Resolve metadata for any PDB ID (not just ATOMICA dataset)
- **UniProt Integration**: Get all PDB structures for any UniProt ID
- **Efficient Indexing**: Polars-based indexing for fast queries

## ATOMICA Dataset

The dataset contains structural analysis of key longevity-related proteins:

### Protein Families
- **NRF2 (NFE2L2)**: ~12 structures - Oxidative stress response
- **KEAP1**: 56 structures - Oxidative stress response  
- **SOX2**: ~8 structures - Pluripotency factor
- **APOE (E2/E3/E4)**: 9 structures - Lipid metabolism & Alzheimer's
- **OCT4 (POU5F1)**: ~4 structures - Reprogramming factor

**Total**: 83 high-resolution protein structures with ATOMICA analysis

### Files per Structure
- `{pdb_id}.cif` - Structure file (mmCIF format)
- `{pdb_id}_metadata.json` - PDB metadata
- `{pdb_id}_interact_scores.json` - ATOMICA interaction scores
- `{pdb_id}_summary.json` - Processing statistics
- `{pdb_id}_critical_residues.tsv` - Ranked critical residues
- `{pdb_id}_pymol_commands.pml` - PyMOL visualization commands

**Repository**: [longevity-genie/atomica_longevity_proteins](https://huggingface.co/datasets/longevity-genie/atomica_longevity_proteins)

## Available Tools

### Dataset Query Tools

#### 1. `atomica_list_structures(limit: int = 100, offset: int = 0)`
List all PDB structures in the ATOMICA dataset.

**Returns:**
- List of structures with basic information
- Total count and pagination info

**Example:**
```python
atomica_list_structures(limit=10)
```

#### 2. `atomica_get_structure(pdb_id: str)`
Get detailed information about a specific PDB structure from the ATOMICA dataset.

**Returns:**
- File paths (CIF, metadata, critical residues, etc.)
- Extended metadata if available (title, UniProt IDs, gene symbols, organisms)

**Example:**
```python
atomica_get_structure("1b68")
```

#### 3. `atomica_get_structure_files(pdb_id: str)`
Get file paths and availability for a PDB structure.

**Returns:**
- Dictionary of file paths
- Availability status for each file type

**Example:**
```python
atomica_get_structure_files("1b68")
```

#### 4. `atomica_search_by_gene(gene_symbol: str, species: str = "9606")`
Search ATOMICA dataset for structures by gene symbol.

**Two-stage search strategy:**
1. **Fast path**: Direct gene symbol match in index (if gene symbols are populated)
2. **Robust path**: If no match, resolves gene→UniProt via API, then searches by UniProt ID

**Species parameter**: Supports both taxonomy IDs and Latin names
- Taxonomy ID: `"9606"`, `"10090"`, etc.
- Latin name: `"Homo sapiens"`, `"Mus musculus"`, etc.
- Default: `"9606"` (human)

This approach handles gene aliases automatically (e.g., "NRF2" resolves to "NFE2L2") and works for any gene, not just those in the dataset index.

**Example:**
```python
atomica_search_by_gene("KEAP1")  # Human by default - 56 structures
atomica_search_by_gene("KEAP1", "Homo sapiens")  # Human by Latin name
atomica_search_by_gene("NFE2L2")  # NRF2 gene - 19 structures
atomica_search_by_gene("APOE", "9606")  # APOE gene - 9 structures
```

#### 5. `atomica_search_by_uniprot(uniprot_id: str)`
Search ATOMICA dataset for structures by UniProt ID. Direct index lookup - fastest method.

**Returns structures with ATOMICA analysis files:**
- Interaction scores JSON
- Critical residues TSV
- PyMOL visualization commands

**Example:**
```python
atomica_search_by_uniprot("Q14145")  # KEAP1 - 56 structures
atomica_search_by_uniprot("P02649")  # APOE - 8 structures
atomica_search_by_uniprot("Q16236")  # NFE2L2 (NRF2) - 19 structures
```

#### 6. `atomica_search_by_organism(organism: str)`
Search ATOMICA dataset for structures by organism (best-effort).

**⚠️ Note**: Organism data in the index is often incomplete or missing. This tool:
- Performs substring matching on organism names
- Returns coverage statistics showing data completeness
- May miss structures where organism info is not populated

**Recommendation**: For more reliable species-specific searches, use `atomica_search_by_gene` with the `species` parameter.

**Example:**
```python
atomica_search_by_organism("Homo sapiens")
atomica_search_by_organism("human")

# Better approach for species-specific search:
atomica_search_by_gene("KEAP1", "Homo sapiens")
```

### Auxiliary PDB Tools

#### 6. `atomica_resolve_pdb(pdb_id: str)`
Resolve metadata for any PDB ID (not restricted to ATOMICA dataset).

**Returns:**
- UniProt IDs
- Gene symbols
- Organism information
- Taxonomy IDs
- Structure details

**Example:**
```python
atomica_resolve_pdb("1tup")  # TP53 structure
```

#### 7. `atomica_get_structures_for_uniprot(uniprot_id: str, max_structures: int = 100)`
Get all available PDB structures for a given UniProt ID.

**Returns:**
- List of structures with metadata
- Resolution, experimental method, dates
- Complex information (protein-protein, ligands, nucleotides)

**Example:**
```python
atomica_get_structures_for_uniprot("P04637")  # TP53 UniProt ID
```

#### 8. `atomica_dataset_info()`
Get information about the ATOMICA dataset status and statistics.

**Returns:**
- Dataset availability
- Structure counts
- Unique genes and organisms
- Repository information

## Available Resources

### 1. `resource://atomica_dataset-info`
Detailed information about the ATOMICA longevity proteins dataset.

### 2. `resource://atomica_index-schema`
Schema of the dataset index with query patterns.

## Installation

### Quick Start with uvx

```bash
# Install uv first if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run the server (stdio transport)
uvx atomica-mcp
```

### Installing from Source

```bash
# Clone the repository
git clone https://github.com/longevity-genie/atomica-mcp.git
cd atomica-mcp

# Install with uv
uv sync

# Or with pip
pip install -e .
```

## Running the Server

The server uses stdio transport by default for AI assistants like Claude Desktop and Cursor.

```bash
# Run with uvx (no installation needed)
uvx atomica-mcp@latest

# Or run locally installed version
atomica-mcp
```

## Configuration

### Environment Variables (Optional)

- `ATOMICA_DATASET_DIR`: Custom path to dataset (auto-detected if not set)
- `MCP_TIMEOUT`: Timeout for API requests in seconds (default: 300, recommended: 600)

**Example:**
```bash
export MCP_TIMEOUT=600
atomica-mcp
```

For all environment variables, see [Advanced Configuration](#advanced-configuration).

### MCP Client Configuration

#### Quick Setup for Claude Desktop / Cursor

Add to your MCP configuration file:

**Claude Desktop macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Claude Desktop Windows**: `%APPDATA%\Claude\claude_desktop_config.json`  
**Cursor**: `~/.cursor/mcp.json`

```json
{
  "mcpServers": {
    "atomica-mcp": {
      "command": "uvx",
      "args": ["atomica-mcp@latest"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "MCP_TIMEOUT": "600"
      }
    }
  }
}
```

That's it! The dataset will download automatically on first use (~500MB).

**Optional**: If you've already downloaded the dataset locally, you can specify the path:
```json
"env": {
  "MCP_TRANSPORT": "stdio",
  "MCP_TIMEOUT": "600",
  "ATOMICA_DATASET_DIR": "/path/to/your/atomica_longevity_proteins"
}
```

### Testing Your Configuration

After adding the config, restart Claude Desktop/Cursor and test:

**Try asking**: "List structures in the ATOMICA dataset" or "What structures are available for KEAP1?"

If it doesn't work:
- Verify the command works in terminal: `uvx atomica-mcp@latest --help`
- Check logs in Claude Desktop/Cursor for errors
- Ensure the config JSON is valid

## Dataset Management CLI

The package includes a CLI for managing the ATOMICA dataset:

### Download Dataset

```bash
# Download full dataset
dataset download

# Download to custom directory
dataset download --output-dir data/inputs

# Download only CIF structure files
dataset download --pattern "*.cif"

# Download only files for specific PDB (e.g., 6ht5)
dataset download --pattern "6ht5*"

# Force re-download even if files exist
dataset download --force
```

### List Available Files

```bash
# List all files in the dataset
dataset list-files

# Filter by pattern
dataset list-files --pattern "*.cif"
```

### Create/Update Index

```bash
# Create index with basic file paths
dataset index

# Create index with full metadata resolution
dataset index --include-metadata

# Custom paths
dataset index --dataset-dir data/atomica --output data/index.parquet
```

### Reorganize Dataset

```bash
# Reorganize files into per-PDB folders
dataset reorganize

# Dry run to see what would be done
dataset reorganize --dry-run
```

### Dataset Information

```bash
# Show dataset information
dataset info
```

## Usage Examples

### Query ATOMICA Dataset

```
User: "What structures are available for KEAP1?"

Tool Call:
atomica_search_by_gene("KEAP1")

Response:
{
  "gene_symbol": "KEAP1",
  "resolution_method": "direct_gene_match",
  "structures": [
    {
      "pdb_id": "1U6D",
      "title": "Crystal structure of the Kelch domain of human Keap1",
      "uniprot_ids": ["Q14145"],
      "gene_symbols": ["KEAP1"],
      "interact_scores_path": "1u6d/1u6d_interact_scores.json",
      "critical_residues_path": "1u6d/1u6d_critical_residues.tsv",
      "pymol_path": "1u6d/1u6d_pymol_commands.pml"
    },
    ...
  ],
  "count": 56
}
```

### Search by UniProt ID

```
User: "Find structures for UniProt Q14145"

Tool Call:
atomica_search_by_uniprot("Q14145")

Response:
{
  "uniprot_id": "Q14145",
  "structures": [
    {
      "pdb_id": "1U6D",
      "title": "Crystal structure of the Kelch domain of human Keap1",
      "uniprot_ids": ["Q14145"],
      "gene_symbols": ["KEAP1"],
      "interact_scores_path": "1u6d/1u6d_interact_scores.json",
      "critical_residues_path": "1u6d/1u6d_critical_residues.tsv",
      "pymol_path": "1u6d/1u6d_pymol_commands.pml"
    },
    ...
  ],
  "count": 56
}
```

### Get Structure Details

```
User: "Tell me about structure 1u6d"

Tool Call:
atomica_get_structure("1u6d")

Response:
{
  "pdb_id": "1U6D",
  "cif_path": "1u6d/1u6d.cif",
  "metadata_path": "1u6d/1u6d_metadata.json",
  "critical_residues_path": "1u6d/1u6d_critical_residues.tsv",
  "interact_scores_path": "1u6d/1u6d_interact_scores.json",
  "pymol_path": "1u6d/1u6d_pymol_commands.pml",
  "title": "Crystal structure of the Kelch domain of human Keap1",
  "uniprot_ids": ["Q14145"],
  "gene_symbols": ["KEAP1"],
  "critical_residues_count": 156
}
```

### Resolve Arbitrary PDB

```
User: "What proteins are in PDB 1tup?"

Tool Call:
atomica_resolve_pdb("1tup")

Response:
{
  "pdb_id": "1TUP",
  "found": true,
  "title": "Tumor protein p53 DNA-binding domain",
  "uniprot_ids": ["P04637"],
  "gene_symbols": ["TP53"],
  "organisms": ["Homo sapiens"],
  "taxonomy_ids": [9606],
  "structures": [...]
}
```

### Get Structures for UniProt ID

```
User: "What PDB structures are available for TP53 (P04637)?"

Tool Call:
atomica_get_structures_for_uniprot("P04637", max_structures=5)

Response:
{
  "uniprot_id": "P04637",
  "structures": [
    {
      "structure_id": "1TUP",
      "uniprot_id": "P04637",
      "gene_symbol": "TP53",
      "resolution": 2.2,
      "experimental_method": "X-ray diffraction",
      "deposition_date": "1994-06-09"
    },
    ...
  ],
  "count": 5
}
```

## Library Usage

You can also use atomica-mcp as a Python library:

```python
from atomica_mcp.server import AtomicaMCP
from atomica_mcp.dataset import resolve_pdb_metadata
from atomica_mcp.mining.pdb_metadata import get_structures_for_uniprot

# Initialize server
mcp = AtomicaMCP()

# Query ATOMICA dataset
structures = mcp.list_structures(limit=10)
keap1_structures = mcp.search_by_gene("KEAP1")

# Resolve arbitrary PDB
tp53_metadata = resolve_pdb_metadata("1tup")

# Get structures for UniProt
p53_structures = get_structures_for_uniprot("P04637")
```

## Architecture

### Server Components

- **AtomicaMCP**: Main MCP server class inheriting from FastMCP
- **Dataset Management**: Automatic download and indexing of ATOMICA dataset
- **PDB Mining**: Comprehensive metadata resolution using PDBe and UniProt APIs
- **Efficient Queries**: Polars-based indexing for fast searches

### Key Modules

- `server.py`: MCP server implementation
- `dataset.py`: Dataset download and management CLI
- `mining/pdb_metadata.py`: PDB metadata mining with retry logic
- `upload_to_hf.py`: Dataset upload utilities

## Requirements

- Python 3.11+
- biotite >= 1.5.0
- eliot >= 1.17.5
- fastmcp >= 2.12.5
- fsspec >= 2025.9.0
- huggingface-hub >= 0.35.3
- polars >= 1.34.0
- pycomfort >= 0.0.18
- requests >= 2.32.5
- tenacity >= 9.1.2
- typer >= 0.20.0

## Testing

Run tests:
```bash
uv run pytest
```

Run specific test:
```bash
uv run pytest tests/test_mcp_server.py -v
uv run pytest tests/test_pdb_mining.py -v
```

### Test Timeouts

Tests are configured with timeouts to prevent hanging:
- **Default timeout**: 300 seconds (5 minutes) for all tests
- **Individual tests**: Some tests have specific timeouts (e.g., 60s for PDB resolution, 120s for UniProt queries)

The timeout is configured via `pytest-timeout` and set in `pytest.ini`. You can override it:

```bash
# Run with custom timeout
uv run pytest --timeout=600

# Disable timeout for debugging
uv run pytest --timeout=0
```

If tests timeout, it usually means:
1. Network issues connecting to external APIs (PDBe, UniProt)
2. Dataset download is taking too long
3. Server initialization is hanging

You can increase the timeout in `pytest.ini` or via environment variable:

```bash
export PYTEST_TIMEOUT=600
uv run pytest
```

## About MCP (Model Context Protocol)

The Model Context Protocol (MCP) is an open protocol that standardizes how applications provide context to Large Language Models (LLMs). Think of MCP servers as "tools" or "plugins" that AI assistants can use to access specialized data and functionality.

### Why MCP?

Traditional AI assistants are limited to their training data and can't access:
- ⛔ Real-time data from specialized databases
- ⛔ Domain-specific tools and APIs
- ⛔ Your organization's internal resources

**MCP solves this** by providing a standardized way for AI assistants to:
- ✅ Query specialized databases (like ATOMICA longevity proteins)
- ✅ Access domain-specific tools (PDB structure resolution, UniProt queries)
- ✅ Retrieve structured, accurate data on demand

### How It Works

```
AI Assistant (Claude, etc.)  ←→  MCP Server (atomica-mcp)  ←→  Data Sources
                                                                  ├─ ATOMICA Dataset
                                                                  ├─ PDB API
                                                                  └─ UniProt API
```

1. **User asks question**: "What structures are available for KEAP1?"
2. **AI decides to use tool**: Calls `atomica_search_by_gene("KEAP1")`
3. **MCP server executes**: Queries local dataset or external APIs
4. **Results returned**: Structured data sent back to AI
5. **AI synthesizes answer**: Natural language response with accurate data

### Key Benefits

- **Structured Access**: Direct connection to curated longevity protein structures
- **Natural Language Queries**: Ask questions naturally, AI handles the technical details
- **Type Safety**: Strong typing ensures data integrity
- **Up-to-Date**: Query real-time data from PDB and UniProt APIs
- **Extensible**: Easily add more tools and data sources

### MCP Server Features

This ATOMICA MCP server provides:
- **8 Tools** for querying protein structures and metadata
- **2 Resources** for documentation and schema information
- **Automatic dataset management** - downloads data on first use
- **Fast queries** with Polars-based indexing
- **Robust error handling** with structured logging

### Configuration

See the [Configuration](#configuration) section above for detailed setup instructions for Claude Desktop and other MCP clients.

### Example Conversations

**Querying Longevity Proteins:**
```
You: "Show me all structures for the oxidative stress response protein KEAP1"

Claude: [Uses atomica_search_by_gene("KEAP1")]
"I found 47 KEAP1 structures in the ATOMICA dataset. Here are some notable ones:
- 1U6D: Kelch domain of Keap1
- 4IQK: KEAP1 in complex with NRF2
..."
```

**Cross-Protein Analysis:**
```
You: "What's the relationship between KEAP1 and NRF2 structures?"

Claude: [Uses atomica_search_by_gene() for both proteins]
"KEAP1 and NRF2 form a critical oxidative stress response complex. 
The ATOMICA dataset contains:
- 47 KEAP1 structures
- 19 NRF2 structures
- Several complex structures showing their interaction..."
```

**Arbitrary PDB Queries:**
```
You: "Get me information about PDB structure 1TUP"

Claude: [Uses atomica_resolve_pdb("1tup")]
"1TUP is the tumor suppressor protein p53 DNA-binding domain from 
Homo sapiens. UniProt ID: P04637, Gene: TP53..."
```

### Learn More

- **MCP Specification**: [modelcontextprotocol.io](https://modelcontextprotocol.io/)
- **MCP Course**: [deeplearning.ai MCP course](https://www.deeplearning.ai/short-courses/mcp-build-rich-context-ai-apps-with-anthropic/)
- **FastMCP Framework**: [github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp)

## Related Projects

- **[opengenes-mcp](https://github.com/longevity-genie/opengenes-mcp)** - Aging and longevity genetics database queries
- **[gget-mcp](https://github.com/longevity-genie/gget-mcp)** - Genomics and sequence analysis toolkit
- **[holy-bio-mcp](https://github.com/longevity-genie/holy-bio-mcp)** - Unified framework for bioinformatics research

## Advanced Configuration

### Multiple MCP Servers

You can use ATOMICA alongside other MCP servers:
```json
{
  "mcpServers": {
    "atomica-mcp": {
      "command": "uvx",
      "args": ["atomica-mcp@latest"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "MCP_TIMEOUT": "600"
      }
    },
    "opengenes-mcp": {
      "command": "uvx",
      "args": ["opengenes-mcp@latest"],
      "env": {
        "MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

### Using Local Installation

If you've installed the package locally (not via uvx):
```json
{
  "mcpServers": {
    "atomica-mcp": {
      "command": "atomica-mcp",
      "args": [],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "MCP_TIMEOUT": "600"
      }
    }
  }
}
```

### HTTP Server Mode

For running as an HTTP server (not recommended for Cursor/Claude Desktop):
```bash
# Start HTTP server
atomica-mcp --transport streamable-http --port 3002

# Or set via environment
export MCP_TRANSPORT=streamable-http
export MCP_PORT=3002
atomica-mcp
```

### All Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT` | `streamable-http` | Transport mode: `stdio` (for Cursor/Claude) or `streamable-http` |
| `MCP_TIMEOUT` | `300` | Timeout in seconds for external API calls |
| `MCP_HOST` | `0.0.0.0` | Host for HTTP mode (not used in stdio) |
| `MCP_PORT` | `3002` | Port for HTTP mode (not used in stdio) |
| `ATOMICA_DATASET_DIR` | auto-detect | Custom path to dataset directory |

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

## Citation

If you use atomica-mcp in your research, please cite:

```bibtex
@software{atomica-mcp,
  title={atomica-mcp: MCP server for ATOMICA longevity proteins dataset},
  author={Kulaga, Anton and contributors},
  year={2025},
  url={https://github.com/longevity-genie/atomica-mcp}
}
```
