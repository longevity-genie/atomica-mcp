# ATOMICA Integration in pdb-mcp

This document describes the ported ATOMICA functionality integrated into pdb-mcp. This allows you to generate protein embeddings and compute interaction scores directly within the pdb-mcp ecosystem.

## Overview

Three main ATOMICA modules have been ported:

1. **embed_protein** - Download protein structures and generate ATOMICA embeddings
2. **get_embeddings** - Stream embeddings generation from ATOMICA models
3. **interact_score** - Compute interaction/criticality scores for proteins

## Installation

To use the ATOMICA functionality, install pdb-mcp with the `atomica` extra:

```bash
uv sync --extra atomica
```

Or, if ATOMICA is already installed:

```bash
uv sync
```

## Module Structure

The ported code is organized in `src/pdb_mcp/preprocessing/`:

```
src/pdb_mcp/preprocessing/
├── __init__.py
├── pdb_converter.py          # PDB to JSONL conversion utilities
├── atomica_embedder.py       # Core embedding and download functions
├── embed_protein.py          # CLI for embedding generation
├── interact_score.py         # CLI for interaction score computation
├── pdb_utils.py              # Existing protein utilities
├── resolve_protein_names.py  # Existing name resolution
└── resolve_proteins.py       # Existing protein resolution
```

## Key Adaptations

### 1. PDB Converter (`pdb_converter.py`)

The original ATOMICA `pdb_converter.py` required ATOMICA's full data pipeline. We created a simplified adapter that:

- Extracts basic structure information from PDB/CIF files
- Provides functions to save JSONL items
- Includes a `pdb_to_jsonl_item_basic()` function for basic structure extraction

**Note**: For full ATOMICA format with complete block/atom embeddings, you need ATOMICA's full data pipeline (`data.converter.pdb_to_list_blocks` + `data.dataset.blocks_to_data`).

### 2. Embedder (`atomica_embedder.py`)

Core functions for structure downloads and embedding generation:

```python
from pdb_mcp.preprocessing import (
    download_pdb_structure,           # Download from RCSB PDB
    download_alphafold_structure,     # Download from AlphaFold DB
    save_embeddings_parquet,          # Save embeddings to Parquet
    check_atomica_dependencies,       # Check if ATOMICA is available
    ensure_atomica_available,         # Raise error if not available
)
```

### 3. Embed Protein CLI (`embed_protein.py`)

CLI for generating embeddings from protein structures:

```bash
# Process PDB structure
embed-protein from-pdb-id 1ABC -o embeddings.parquet

# Process specific chains
embed-protein from-pdb-id 1ABC -o embeddings.parquet --chains A,B

# Download from AlphaFold if PDB not available
embed-protein from-pdb-id P12345 -o embeddings.parquet --alphafold-fallback

# Process local file
embed-protein from-file /path/to/protein.pdb -o embeddings.parquet
```

### 4. Interact Score CLI (`interact_score.py`)

CLI for computing interaction scores (residue criticality):

```bash
# Compute interaction scores
interact-profiler compute-interact-scores \
  --data-path protein.pdb \
  --output-path scores.jsonl \
  --model-ckpt model.pt

# With summary report
interact-profiler compute-interact-scores \
  --data-path protein.pdb \
  --output-path scores.jsonl \
  --model-ckpt model.pt \
  --summary-path summary.json
```

## Usage Examples

### Example 1: Generate Embeddings from PDB ID

```bash
embed-protein from-pdb-id 1TGR \
  --output /tmp/embeddings.parquet \
  --model-config /path/to/config.json \
  --model-weights /path/to/weights.pt \
  --device cuda
```

### Example 2: Generate Embeddings with AlphaFold Fallback

```bash
embed-protein from-pdb-id Q9Y5K6 \
  --output /tmp/embeddings.parquet \
  --alphafold-fallback \
  --alphafold-version 4 \
  --device cuda
```

### Example 3: Compute Interaction Scores

```bash
interact-profiler compute-interact-scores \
  --data-path 1TGR.pdb \
  --output-path /tmp/scores.jsonl \
  --model-ckpt /path/to/model.pt \
  --summary-path /tmp/summary.json
```

This will generate:
- `scores.jsonl` - Interaction scores for each residue
- `summary.json` - Processing statistics
- `1TGR_critical_residues.tsv` - TSV report of critical residues
- `1TGR_pymol_commands.pml` - PyMOL visualization commands

## ATOMICA Dependencies

The following dependencies are required for full ATOMICA functionality:

```python
# From pyproject.toml [project.optional-dependencies] section
torch>=2.1.1
e3nn>=0.5.1
scipy>=1.13.1
rdkit>=2023.9.5
openbabel-wheel>=3.1.1.20
biopython>=1.84
atom3d>=0.2.6
orjson>=3.9.0
```

These are installed with `uv sync --extra atomica`.

## Runtime Checks

All modules include runtime checks for ATOMICA availability:

```python
from pdb_mcp.preprocessing.atomica_embedder import ensure_atomica_available

# This will raise RuntimeError if ATOMICA is not available
ensure_atomica_available()
```

## ATOMICA Model Checkpoints

The CLI commands expect ATOMICA model checkpoints to be available:

- Default interface model: `downloads/ATOMICA_checkpoints/prot_interface/atomica_interface_v3.{json,pt}`
- Pretrain model: `downloads/ATOMICA_checkpoints/pretrain/pretrain_model_{config,weights}.pt`

These can be specified via `--model-config` and `--model-weights` options.

## Integration with Existing pdb-mcp Functions

The ported code integrates seamlessly with existing pdb-mcp functionality:

```python
from pdb_mcp.preprocessing import extract_pdb_structure_data
import biotite.database.rcsb as rcsb

# Download with existing pdb-mcp tools
pdb_file = rcsb.fetch("1TGR", "cif", target_path="/tmp/1TGR.cif")

# Extract structure data
structure_data = extract_pdb_structure_data(pdb_file, chains=["A"])

# Use with ATOMICA embedders
from pdb_mcp.preprocessing.atomica_embedder import save_embeddings_parquet
save_embeddings_parquet(embeddings, Path("/tmp/embeddings.parquet"))
```

## Eliot Logging

All functions use Eliot for comprehensive logging:

```bash
# Enable Eliot logging to file
embed-protein from-file protein.pdb \
  --output embeddings.parquet \
  --log-file /tmp/embedding_log.json
```

## Performance Notes

- **GPU Memory**: Model inference uses GPU. Adjust batch size if you encounter OOM errors.
- **Streaming**: Embeddings are streamed to disk using Polars for memory efficiency.
- **Caching**: Downloaded structures are cached in the temp directory (clean up between runs).

## Troubleshooting

### "ATOMICA dependencies not found"

Install ATOMICA dependencies:
```bash
uv sync --extra atomica
```

Or manually ensure ATOMICA is in your Python path.

### "Cannot import from data.dataset"

Ensure ATOMICA is properly installed or add ATOMICA root to PYTHONPATH:
```bash
export PYTHONPATH=/path/to/ATOMICA:$PYTHONPATH
```

### "Model not found"

Provide explicit paths to model config and weights:
```bash
embed-protein from-file protein.pdb \
  --output embeddings.parquet \
  --model-config /path/to/config.json \
  --model-weights /path/to/weights.pt
```

## Related Files

- Original ATOMICA: `/home/antonkulaga/sources/ATOMICA/`
- pdb-mcp preprocessing: `/home/antonkulaga/sources/pdb-mcp/src/pdb_mcp/preprocessing/`
- Documentation: `/home/antonkulaga/sources/pdb-mcp/docs/ATOMICA_INTEGRATION.md`

## Future Work

Potential improvements for future versions:

1. **Batch Processing**: Add batch mode for processing multiple proteins
2. **Caching**: Cache downloaded structures to avoid re-downloading
3. **Streaming Output**: Further optimize memory usage for very large datasets
4. **Integration Tests**: Add integration tests with real ATOMICA models
5. **Documentation**: Add more examples and troubleshooting guides


