# Download ATOMICA Longevity Proteins Dataset

This document describes how to download the ATOMICA longevity proteins dataset from Hugging Face using the `download_dataset.py` script.

## Overview

The script downloads the `atomica_longevity_proteins` dataset from Hugging Face, which contains comprehensive structural analysis of key longevity-related proteins using the ATOMICA deep learning model.

## Dataset Contents

- **94 high-resolution protein structures** across 5 protein families:
  - NRF2 (NFE2L2): 19 structures - Oxidative stress response
  - KEAP1: 47 structures - Oxidative stress response  
  - SOX2: 8 structures - Pluripotency factor
  - APOE (E2/E3/E4): 9 structures - Lipid metabolism & Alzheimer's
  - OCT4 (POU5F1): 4 structures - Reprogramming factor

- **Files per structure:**
  - `{pdb_id}.cif` - Structure file (mmCIF format)
  - `{pdb_id}_metadata.json` - PDB metadata
  - `{pdb_id}_interact_scores.json` - ATOMICA interaction scores
  - `{pdb_id}_summary.json` - Processing statistics
  - `{pdb_id}_critical_residues.tsv` - Ranked critical residues

## Installation

The CLI command is automatically installed when you install the `atomica-mcp` package:

```bash
uv sync
```

## Usage

### Show Dataset Information

```bash
uv run python -m atomica_mcp.preprocessing.download_dataset info
```

Or if installed as CLI (after `uv sync`):

```bash
download-atomica-dataset info
```

### List Available Files

```bash
# List all files
uv run python -m atomica_mcp.preprocessing.download_dataset list-files

# List only CIF files
uv run python -m atomica_mcp.preprocessing.download_dataset list-files --pattern "*.cif"

# List files for a specific PDB
uv run python -m atomica_mcp.preprocessing.download_dataset list-files --pattern "6ht5*"
```

### Download Dataset

```bash
# Download full dataset to default location (data/input/atomica_longevity_proteins)
uv run python -m atomica_mcp.preprocessing.download_dataset download

# Download to custom directory
uv run python -m atomica_mcp.preprocessing.download_dataset download --output-dir /path/to/data

# Download only structure files
uv run python -m atomica_mcp.preprocessing.download_dataset download --pattern "*.cif"

# Download only files for specific PDB ID
uv run python -m atomica_mcp.preprocessing.download_dataset download --pattern "6ht5*"

# Force re-download even if files exist
uv run python -m atomica_mcp.preprocessing.download_dataset download --force

# Download with specific repo
uv run python -m atomica_mcp.preprocessing.download_dataset download --repo-id longevity-genie/atomica_longevity_proteins
```

## Command Reference

### `info` Command

Shows information about the dataset including description, protein families, and usage examples.

**Options:**
- `--repo-id, -r`: Hugging Face repository ID (default: `longevity-genie/atomica_longevity_proteins`)

### `list-files` Command

Lists all files available in the dataset repository.

**Options:**
- `--repo-id, -r`: Hugging Face repository ID (default: `longevity-genie/atomica_longevity_proteins`)
- `--pattern, -p`: Filter files by glob pattern (e.g., `*.cif`, `6ht5*`)

### `download` Command

Downloads the dataset files using fsspec.

**Options:**
- `--output-dir, -o`: Output directory (default: `data/input/atomica_longevity_proteins`)
- `--repo-id, -r`: Hugging Face repository ID (default: `longevity-genie/atomica_longevity_proteins`)
- `--force, -f`: Force re-download even if files exist
- `--pattern, -p`: Download only files matching glob pattern (e.g., `*.cif`, `6ht5*`)

## Examples

### Download Only Structure Files

```bash
uv run python -m atomica_mcp.preprocessing.download_dataset download --pattern "*.cif"
```

### Download All Files for NRF2 Structures

NRF2 PDB IDs: 1x36, 2flu, 2hlu, 2lz1, 3wn7, 4zge, 4zhw, 4zi7, 5cgj, 5daf, 5u6g, 6b0e, 6ll6, 7o1l, 7o1m, 7o1n, 7o2x, 8apc, 8apd, 8eqj

```bash
# Download one at a time
uv run python -m atomica_mcp.preprocessing.download_dataset download --pattern "1x36*"
```

### Download Metadata Only

```bash
uv run python -m atomica_mcp.preprocessing.download_dataset download --pattern "*_metadata.json"
```

### Download ATOMICA Scores Only

```bash
uv run python -m atomica_mcp.preprocessing.download_dataset download --pattern "*_interact_scores.json"
```

## Technical Details

### Using fsspec

The script uses `fsspec` with the `hf://` protocol to download files from Hugging Face:

```python
import fsspec

# Get Hugging Face filesystem
fs = fsspec.filesystem("hf", token=None)

# Download a file
fs.get("hf://datasets/longevity-genie/atomica_longevity_proteins/6ht5.cif", "local_path.cif")
```

### Logging

The script uses `eliot` for structured logging. Logs include:
- File discovery events
- Download progress
- Success/failure status
- File sizes

## Troubleshooting

### Files Not Found

If dynamic file listing fails, the script falls back to a pre-defined list of expected files based on the dataset documentation.

### Permission Errors

Make sure the output directory is writable:

```bash
mkdir -p data/input/atomica_longevity_proteins
chmod 755 data/input/atomica_longevity_proteins
```

### Network Issues

The script uses fsspec which supports retries. If downloads fail, try:
1. Check your internet connection
2. Use `--force` to retry failed downloads
3. Download specific files with `--pattern`

## Dataset URL

https://huggingface.co/datasets/longevity-genie/atomica_longevity_proteins

