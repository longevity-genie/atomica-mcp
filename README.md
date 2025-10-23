# atomica-mcp

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **🏆 HackAging.ai Submission**  
> Longevity Genie Team submission to the **Sequence to Function Track** at [HackAging.ai](http://hackaging.ai/)
>
> **What we built:**
> - **This repository**: Model Context Protocol (MCP) server that works with Claude Desktop, Cursor, Windsurf, and other MCP hosts
> - **[Dataset](https://huggingface.co/datasets/longevity-genie/atomica_longevity_proteins)**: 94 analyzed longevity protein structures on Hugging Face
> - **[Custom ATOMICA fork](https://github.com/longevity-genie/ATOMICA)**: Polished the original model with improved usability, additional features, and longevity-focused applications
> - **[Analysis examples](analysis/)**: NRF2/KEAP1 structural analysis demo (showcased in presentation video) with figures showing disease mutations, glycation sites, and critical residues
> - **[Presentation](https://docs.google.com/presentation/d/1ZX44XQxWUYvo3pH9bJNdj5i4BN33pGkR9VNHJtyIKII/edit?usp=sharing)**: Overview slides and demo video

## The Problem

Aging research needs to evaluate thousands of protein-protein interactions. Every aging-related gene interacts with many others. Understanding these interactions helps us:
- See which aging pathways work together or against each other
- Transfer proteins from long-lived species without breaking their dependencies
- Get quick, AI-readable interaction predictions

Traditional computational methods are too slow for this scale.

## Our Solution

We built a system that combines computational analysis with AI assistants through Model Context Protocol servers.

**What's included:**

1. **MCP servers** (work with Claude Desktop, Cursor, Windsurf, etc.)
   - [synergy-age-MCP](https://github.com/longevity-genie/synergy-age-mcp) - aging gene interactions
   - [omnipath-mcp](https://github.com/longevity-genie/omnipath-mcp) - signaling pathways
   - biothings-mcp - gene annotations
   - **This server** - precomputed interaction scores, PyMOL scripts, critical residue predictions

2. **Enhanced ATOMICA model** ([repo](https://github.com/longevity-genie/ATOMICA))
   - Polished the original model with improved usability and additional features
   - Applied to longevity research use-case
   - Analyzed 94 structures across 5 longevity-related protein families

3. **Dataset and analysis examples** ([analysis/](analysis/) folder)
   - 94 structures: NRF2, KEAP1, SOX2, APOE, OCT4
   - Critical residue rankings using ATOMICA scoring
   - Validation against disease mutations (NRF2 IMDDHH syndrome)
   - Age-related modification sites (glycation)
   - Figures and structural annotations included

**Demo analysis results (NRF2, as shown in video):**
- Confirmed E82 in ETGE motif as the most critical residue for KEAP1 binding
- Found F468 maintains structure near age-affected glycation sites
- Showed R499 glycation has more functional impact than K462
- Identified potentially novel regulatory cysteines C406/C368 in KEAP1

**How it works:** Connect AI assistants (Claude, Cursor, etc.) to biological databases through MCP servers, then use computational predictions to guide questions and validate findings.

---

## About This Server

This is a Model Context Protocol (MCP) server providing access to the ATOMICA longevity proteins dataset and PDB structure analysis tools.

**ATOMICA** is a geometric deep learning model trained on 2M+ interaction complexes. It identifies critical residues in protein structures by analyzing atomic-scale interaction patterns.

**Dataset**: 94 structures across 5 longevity-related protein families (NRF2, KEAP1, SOX2, APOE, OCT4)  
**Repository**: [longevity-genie/atomica_longevity_proteins](https://huggingface.co/datasets/longevity-genie/atomica_longevity_proteins)

Each structure includes:
- Structure file (CIF format)
- ATOMICA interaction scores
- Critical residue rankings
- PyMOL visualization commands

## Quick Start

### Installation

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run the server
uvx atomica-mcp
```

### Configure with Your AI Assistant

Add to your MCP config file (Claude Desktop, Cursor, Windsurf, etc.):

**Cursor/Windsurf**: `~/.cursor/mcp.json` or `~/.windsurf/mcp.json`  
**Claude Desktop (macOS)**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Claude Desktop (Windows)**: `%APPDATA%\Claude\claude_desktop_config.json`

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

Restart your AI assistant. The dataset (~500MB) downloads automatically on first use.

### Example Queries

Once connected, try asking your AI assistant:
- "What structures are available for KEAP1?"
- "Show me critical residues in NRF2 ETGE motif"
- "Find APOE structures and their variants"
- "Get PyMOL commands for structure 2FLU"

## Available Tools

The server provides 8 MCP tools:

**Dataset queries:**
- `atomica_list_structures` - List all structures
- `atomica_get_structure` - Get details for a specific PDB
- `atomica_search_by_gene` - Search by gene symbol (e.g., "KEAP1")
- `atomica_search_by_uniprot` - Search by UniProt ID
- `atomica_search_by_organism` - Filter by organism

**Auxiliary tools:**
- `atomica_resolve_pdb` - Get metadata for any PDB ID
- `atomica_get_structures_for_uniprot` - Get all PDB structures for a UniProt ID
- `atomica_dataset_info` - Dataset statistics

For detailed tool documentation, see the [full documentation](#available-tools-detailed) below.

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

## Development

### Python Library Usage

```python
from atomica_mcp.server import AtomicaMCP
from atomica_mcp.mining.pdb_metadata import get_structures_for_uniprot

# Initialize server
mcp = AtomicaMCP()

# Query dataset
structures = mcp.list_structures(limit=10)
keap1 = mcp.search_by_gene("KEAP1")

# Get structures for UniProt
p53 = get_structures_for_uniprot("P04637")
```

### Testing

```bash
uv run pytest
```

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

## Related Projects

- [opengenes-mcp](https://github.com/longevity-genie/opengenes-mcp) - Aging and longevity genetics database
- [gget-mcp](https://github.com/longevity-genie/gget-mcp) - Genomics and sequence analysis toolkit
- [holy-bio-mcp](https://github.com/longevity-genie/holy-bio-mcp) - Unified bioinformatics framework

## License

MIT License - see LICENSE file for details

## Contributors

This project was developed by the Longevity Genie Team for the HackAging.ai hackathon:

**Anton Kulaga**
- ATOMICA fork development
- ATOMICA MCP server
- Presentation
- Hackathon submission

**Newton Winter**
- Demo analysis (NRF2/KEAP1)
- PDB structure processing
- ATOMICA fork DevOps
- HuggingFace dataset preparation

**Livia Zaharia**
- Video editing
- Presentation design

## Citation

If you use atomica-mcp in your research, please cite:

```bibtex
@software{atomica-mcp,
  title={atomica-mcp: MCP server for ATOMICA longevity proteins dataset},
  author={Kulaga, Anton and Winter, Newton and Zaharia, Livia},
  year={2025},
  url={https://github.com/longevity-genie/atomica-mcp},
  note={HackAging.ai Submission - Longevity Genie Team}
}
```
