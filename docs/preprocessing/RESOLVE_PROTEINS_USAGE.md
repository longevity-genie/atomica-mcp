# Resolve Proteins Usage Guide

The `resolve_proteins` module has been ported from the ATOMICA project to `pdb-mcp`. This guide explains how to use it with the new project structure.

## Overview

The module resolves protein names from PDB IDs in JSONL.GZ files using the AnAge database for organism classification. It operates in two modes:

1. **TSV mode** (default): Uses local TSV files for PDB chain-to-UniProt mapping and taxonomy
2. **API mode**: Queries the RCSB PDB REST API for metadata

## Project Structure

```
pdb-mcp/
├── data/
│   ├── input/
│   │   ├── anage/
│   │   │   └── anage_data.txt          # AnAge database file
│   │   └── pdb/
│   │       ├── pdb_chain_uniprot.tsv.gz
│   │       ├── pdb_chain_taxonomy.tsv.gz
│   │       └── ... (other annotation files)
│   └── output/                           # Results written here
├── src/
│   └── pdb_mcp/
│       ├── resolve_proteins.py          # Main module
│       └── __main__.py                  # CLI entry point
└── pyproject.toml                       # Project dependencies
```

## Key Differences from ATOMICA

The main differences from the original ATOMICA implementation:

1. **Paths**: Data files are now in `data/input/` instead of `annotations/`
2. **Output**: Results go to `data/output/` instead of the current directory
3. **PDB Files**: PDB structures are NOT copied locally. They will be downloaded separately using fsspec with an appropriate command to `data/input/pdb/`

## Installation

```bash
cd pdb-mcp
uv sync
```

## Basic Usage

### Using Python Module

```python
from pdb_mcp.resolve_proteins import resolve

# Call the resolve command with parameters
resolve(
    input_file=Path("data/input/your_file.jsonl.gz"),
    output=Path("results"),
    anage_file=Path("data/input/anage/anage_data.txt")
)
```

### Using CLI

```bash
# Basic usage (requires --input-file and --output)
uv run python -m pdb_mcp.resolve_proteins \
    --input-file data/input/your_data.jsonl.gz \
    --output results

# With filtering for mammals only
uv run python -m pdb_mcp.resolve_proteins \
    --input-file data/input/your_data.jsonl.gz \
    --output results \
    --mammals-only

# With custom AnAge file
uv run python -m pdb_mcp.resolve_proteins \
    --input-file data/input/your_data.jsonl.gz \
    --output results \
    --anage-file path/to/custom_anage.txt

# Process specific line numbers
uv run python -m pdb_mcp.resolve_proteins \
    --input-file data/input/your_data.jsonl.gz \
    --output results \
    --line-numbers "1-100,200,300-400"

# Resume/append mode
uv run python -m pdb_mcp.resolve_proteins \
    --input-file data/input/your_data.jsonl.gz \
    --output results \
    --append

# Using API mode instead of TSV
uv run python -m pdb_mcp.resolve_proteins \
    --input-file data/input/your_data.jsonl.gz \
    --output results \
    --no-use-tsv
```

## Command-Line Options

```
Usage: python -m pdb_mcp.resolve_proteins [OPTIONS]

Options:
  --input-file PATH                    Path to .jsonl.gz file to process [required]
  --line-numbers TEXT                  Line numbers to process (e.g., '1,5,10' or '1-10')
  --anage-file PATH                    Path to AnAge database TSV file
  --output PATH                        Base output path [required]
  --skip-jsonl / --no-skip-jsonl      Skip writing JSONL output
  --skip-csv / --no-skip-csv          Skip writing CSV output
  --append / --no-append              Resume from last processed line
  --log-to-file / --no-log-to-file    Log to files in ./logs directory
  --log-dir PATH                       Directory for log files (default: logs)
  --log-file-name TEXT                Base name for log files (default: resolve_proteins)
  --clean-destinations / --no-clean-destinations  Clean log destinations
  --show-chains / --no-show-chains    Show individual chain information (default: True)
  --filter-organism TEXT               Filter by organism name (partial match)
  --filter-classification TEXT         Filter by AnAge classification (exact match)
  --mammals-only / --no-mammals-only  Filter to mammalian proteins only
  --timeout INTEGER                    Request timeout in seconds (default: 10)
  --retries INTEGER                    Retry attempts for failed API calls (default: 3)
  --pdb-cache-size INTEGER            Max unique PDB IDs in memory LRU cache (default: 20000)
  --csv-batch-size INTEGER            CSV rows per write batch (default: 500)
  --use-tsv / --no-use-tsv            Use local TSV files (default: True)
  --help                               Show this message and exit
```

## Data Paths

The module automatically resolves paths relative to the project structure:

- **AnAge file**: `data/input/anage/anage_data.txt` (if not specified)
- **PDB annotations**: `data/input/pdb/` (for TSV mode)
- **Output files**: `data/output/` (created automatically)

## Output Files

The module generates:

- `results.csv` - Tabular format with one row per chain
- `results.jsonl.gz` - Line-delimited JSON (compressed) with detailed information

Both files contain only entries that pass filtering criteria (organisms in AnAge database).

## Filtering

The module filters results by organisms in the AnAge database. Examples:

```bash
# Only mammals
--filter-classification Mammalia

# Only Homo sapiens
--filter-organism "Homo sapiens"

# Only birds
--filter-classification Aves
```

## Performance Tips

1. **Use TSV mode** (default) for better performance - requires PDB annotation files
2. **Adjust batch size**: Increase `--csv-batch-size` for faster writes (uses more memory)
3. **Use LRU cache**: `--pdb-cache-size` defaults to 20000 - adjust based on available memory
4. **Resume mode**: Use `--append` to resume interrupted processing without restarting

## Example Workflow

```bash
# 1. First run with progress logging
uv run python -m pdb_mcp.resolve_proteins \
    --input-file data/input/proteins.jsonl.gz \
    --output proteins_resolved \
    --log-to-file \
    --mammals-only

# 2. Results are in:
# - data/output/proteins_resolved.csv
# - data/output/proteins_resolved.jsonl.gz

# 3. If interrupted, resume with:
uv run python -m pdb_mcp.resolve_proteins \
    --input-file data/input/proteins.jsonl.gz \
    --output proteins_resolved \
    --append
```

## Logging

By default, logs are printed to stdout. Enable file logging:

```bash
uv run python -m pdb_mcp.resolve_proteins \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --log-to-file \
    --log-dir custom_logs \
    --log-file-name my_run
```

This creates:
- `custom_logs/my_run.json` - Machine-readable logs
- `custom_logs/my_run.log` - Human-readable logs

## PDB Files

Note: This module expects PDB structures to be downloaded separately using fsspec or another method to `data/input/pdb/` directory. The module uses only the annotation files (TSV) from that directory, not the actual PDB structure files.

For downloading PDB files, refer to the main project documentation.

