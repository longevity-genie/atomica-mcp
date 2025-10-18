# pdb-mcp

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

MCP (Model Context Protocol) server for PDB structure queries and protein resolution using the AnAge database.

This server implements the Model Context Protocol (MCP) for PDB (Protein Data Bank), providing a standardized interface for querying protein structures and resolving proteins using longevity data from the AnAge database. MCP enables AI assistants and agents to access PDB structures and organism aging information through structured interfaces.

## Features

- **PDB Structure Queries**: Fetch metadata for any PDB structure by ID (resolution, title, chains, organisms)
- **Organism Classification**: Classify organisms using the AnAge database to get longevity and taxonomy information
- **Chain Information**: Get detailed protein names, organism info, and UniProt IDs for specific PDB chains
- **AnAge Integration**: Access comprehensive animal aging and longevity data for thousands of species
- **Efficient Data Loading**: Optional local TSV files for fast queries (PDB chain-to-organism and chain-to-UniProt mappings)
- **RCSB API Fallback**: Automatically uses RCSB REST API if local data unavailable

## Available Tools

### 1. `pdb_fetch_structure(pdb_id: str)`
Fetch metadata for a PDB structure by ID.

**Returns:**
- Structure title and resolution
- List of polymer entities with chains
- Organism information for each chain
- UniProt protein IDs for each chain

**Example:**
```
pdb_fetch_structure("2uxq")
```

### 2. `pdb_classify_organism(scientific_name: str)`
Classify an organism using the AnAge database.

**Returns:**
- Organism classification (mammals, birds, reptiles, etc.)
- Common name
- Maximum longevity in years
- Kingdom and phylum information
- Whether organism is in AnAge database

**Example:**
```
pdb_classify_organism("Homo sapiens")
pdb_classify_organism("Mus musculus")
```

### 3. `pdb_get_chain_info(pdb_id: str, chain_id: str)`
Get detailed information about a specific chain in a PDB structure.

**Returns:**
- Protein name/description
- Organism information with AnAge data
- UniProt IDs

**Example:**
```
pdb_get_chain_info("2uxq", "A")
pdb_get_chain_info("1a3x", "B")
```

### 4. `pdb_list_organisms_in_anage()`
Get all organisms available in the AnAge database.

**Returns:**
- List of all scientific names in AnAge database

**Use for:**
- Understanding which organisms have longevity data
- Planning comparative studies

### 5. `pdb_get_available_data()`
Get information about available data sources.

**Returns:**
- AnAge database status and organism count
- PDB annotations availability
- Server information

## Available Resources

### 1. `resource://pdb_anage-info`
Comprehensive information about the AnAge database including available fields, use cases, and organisms included.

### 2. `resource://pdb_pdb-annotations-info`
Information about available PDB annotation data sources and their status.

### 3. `resource://pdb_schema-summary`
Summary of available tools, data sources, and schema information.

## Installation

### Quick Start with uvx

The easiest way to run the server:

```bash
# Install uv first if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run the server directly
uvx pdb-mcp stdio
```

### Installing from PyPI

```bash
pip install pdb-mcp
# or with uv
uv pip install pdb-mcp
```

### Installing from Source

```bash
# Clone the repository
git clone https://github.com/longevity-genie/pdb-mcp.git
cd pdb-mcp

# Install with uv
uv sync

# Or with pip
pip install -e .
```

## Running the Server

### Using stdio transport (recommended for AI assistants)

```bash
pdb-mcp stdio
```

### Using HTTP transport

```bash
pdb-mcp run --host localhost --port 3002
```

### Using SSE transport

```bash
pdb-mcp sse --host localhost --port 3002
```

## Configuration

Environment variables:
- `MCP_HOST`: Server host (default: 0.0.0.0)
- `MCP_PORT`: Server port (default: 3002)
- `MCP_TRANSPORT`: Transport type (default: streamable-http)

## Data Sources

### AnAge Database
The AnAge (Animal Ageing and Longevity) database contains:
- **Maximum longevity data** for thousands of species
- **Taxonomic classifications** (Kingdom, Phylum, Class, etc.)
- **Common names** for organisms
- **Life history traits**

Data location: `data/input/anage/anage_data.txt`

### PDB Annotations (Optional)
For faster queries, the server can use local PDB annotation TSV files:
- **pdb_chain_uniprot.tsv.gz**: Maps PDB chains to UniProt proteins
- **pdb_chain_taxonomy.tsv.gz**: Maps PDB chains to organisms

Data location: `data/input/pdb/`

If these files are not present, the server will use the RCSB REST API (slower but always available).

## Usage Examples

### Basic PDB Structure Query

```
User: "Tell me about the 2uxq protein structure"

Tool Call:
pdb_fetch_structure("2uxq")

Response:
{
  "pdb_id": "2uxq",
  "found": true,
  "title": "COMPLEX OF PEROXISOME PROLIFERATOR-ACTIVATED RECEPTOR GAMMA WITH ROSIGLITAZONE",
  "resolution": [2.1],
  "entities": [
    {
      "chains": ["A"],
      "organism": {
        "scientific_name": "Homo sapiens",
        "taxonomy_id": 9606
      },
      "uniprot_ids": ["P37231"]
    }
  ]
}
```

### Organism Classification

```
User: "Is Homo sapiens in the AnAge database and what is its maximum longevity?"

Tool Call:
pdb_classify_organism("Homo sapiens")

Response:
{
  "scientific_name": "Homo sapiens",
  "classification": "Mammalia",
  "common_name": "Human",
  "max_longevity_yrs": 122.45,
  "in_anage": true,
  "kingdom": "Animalia",
  "phylum": "Chordata"
}
```

### Chain Information

```
User: "What protein is in chain A of structure 2uxq?"

Tool Call:
pdb_get_chain_info("2uxq", "A")

Response:
{
  "pdb_id": "2uxq",
  "chain_id": "A",
  "found": true,
  "protein_name": "Peroxisome proliferator-activated receptor gamma",
  "organism": {
    "scientific_name": "Homo sapiens",
    "classification": "Mammalia",
    "common_name": "Human",
    "max_longevity_yrs": 122.45,
    "in_anage": true
  },
  "uniprot_ids": ["P37231"]
}
```

## Library Usage

You can also use pdb-mcp as a Python library for your own scripts:

```python
from pdb_mcp.pdb_utils import (
    load_anage_data,
    fetch_pdb_metadata,
    classify_organism,
    get_chain_info
)
from pathlib import Path

# Load AnAge data
anage_data = load_anage_data(Path("data/input/anage/anage_data.txt"))

# Fetch PDB structure
metadata = fetch_pdb_metadata("2uxq")
print(metadata["title"])

# Classify organism
organism = classify_organism("Homo sapiens", anage_data)
print(f"Max longevity: {organism['max_longevity_yrs']} years")

# Get chain information
chain_info = get_chain_info(metadata, "A")
print(f"Protein: {chain_info['protein_name']}")
```

## Architecture

### PDBMCPServer Class

The main MCP server class that inherits from `FastMCP`:
- Loads AnAge data on initialization
- Registers tools and resources
- Provides methods for PDB queries and organism classification

### pdb_utils Module

Core utility functions:
- `fetch_pdb_metadata()`: Fetch structure metadata from RCSB API or local TSV
- `classify_organism()`: Look up organism in AnAge database
- `get_chain_protein_name()`: Extract protein name for a chain
- `get_chain_organism()`: Get organism info and AnAge classification for a chain
- `get_chain_uniprot_ids()`: Get UniProt IDs for a chain
- `load_anage_data()`: Load AnAge database from TSV file
- `load_pdb_annotations()`: Load PDB annotations from TSV.GZ files

## Requirements

- Python 3.10+
- biotite >= 1.2.0 (PDB structure access)
- fastmcp >= 2.12.5 (MCP framework)
- eliot >= 1.17.5 (Logging)
- polars >= 1.34.0 (Data processing)
- requests >= 2.31.0 (HTTP requests)
- tenacity >= 9.1.2 (Retry logic)
- typer >= 0.16.0 (CLI)

## Testing

Run tests:
```bash
uv run pytest
```

Run specific test:
```bash
uv run pytest tests/test_pdb_resolution.py -v
```

## About MCP (Model Context Protocol)

MCP is a protocol that bridges AI systems and specialized domain knowledge:

- **Structured Access**: Direct connection to authoritative protein structure data and aging research
- **Natural Language Queries**: Query PDB through AI assistants without SQL or complex APIs
- **Type Safety**: Strong typing through Pydantic models
- **AI Integration**: Seamless integration with AI assistants and coding tools

Learn more at [deeplearning.ai MCP course](https://www.deeplearning.ai/short-courses/mcp-build-rich-context-ai-apps-with-anthropic/).

## Related Projects

- **[opengenes-mcp](https://github.com/longevity-genie/opengenes-mcp)** - Aging and longevity genetics database queries
- **[gget-mcp](https://github.com/longevity-genie/gget-mcp)** - Genomics and sequence analysis toolkit
- **[holy-bio-mcp](https://github.com/longevity-genie/holy-bio-mcp)** - Unified framework for bioinformatics research

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

## Citation

If you use pdb-mcp in your research, please cite:

```bibtex
@software{pdb-mcp,
  title={pdb-mcp: MCP server for PDB structure queries and protein resolution},
  author={Kulaga, Anton and contributors},
  year={2025},
  url={https://github.com/longevity-genie/pdb-mcp}
}
```
