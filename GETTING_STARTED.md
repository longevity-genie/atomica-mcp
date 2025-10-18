# Getting Started with PDB-MCP

PDB-MCP provides tools to download PDB annotation files and resolve protein names from PDB IDs using the AnAge database for organism classification.

## Quick Start

### 1. Installation

```bash
cd pdb-mcp
uv sync
```

### 2. Download PDB Annotation Files (Required)

Download all necessary annotation files from the EBI SIFTS database:

```bash
# Download to data/input/pdb/
uv run python -m pdb_mcp download download

# Shows download progress:
# ⬇ Downloading: pdb_chain_uniprot.tsv.gz... ✓ (5.5 MB)
# ⬇ Downloading: pdb_chain_taxonomy.tsv.gz... ✓ (54.0 MB)
# ... (16 files total, ~200 MB)
```

This step is **required** before using `resolve_proteins`. The files are stored in `data/input/pdb/` and used for fast local lookups.

### 3. Prepare Your Data

Place your JSONL.GZ input file in `data/input/`:

```bash
# Example with your data
cp your_proteins.jsonl.gz data/input/

# Check what you have
ls -lh data/input/
```

### 4. Resolve Protein Names

```bash
# Basic usage
uv run python -m pdb_mcp resolve \
    --input-file data/input/your_proteins.jsonl.gz \
    --output results

# With organism filtering (mammals only)
uv run python -m pdb_mcp resolve \
    --input-file data/input/your_proteins.jsonl.gz \
    --output results \
    --mammals-only

# Results are saved to:
# - data/output/results.csv
# - data/output/results.jsonl.gz
```

## Available Commands

### Main CLI

```bash
uv run python -m pdb_mcp --help
```

Shows two main commands:
- `download` - Download PDB annotations from EBI SIFTS
- `resolve` - Resolve protein names from PDB IDs

### Download Command

```bash
uv run python -m pdb_mcp download download [OPTIONS]
```

**Key options:**
- `--output-dir PATH` - Where to save files (default: `data/input/pdb/`)
- `--no-skip-existing` - Re-download all files
- `--no-verbose` - Suppress progress output

**Example: Resume interrupted download**
```bash
uv run python -m pdb_mcp download download
# Automatically skips already-downloaded files
```

### Resolve Command

```bash
uv run python -m pdb_mcp resolve [OPTIONS]
```

**Key options:**
- `--input-file PATH` - Input JSONL.GZ file (required)
- `--output PATH` - Output filename (required)
- `--mammals-only` - Filter to mammalian proteins only
- `--filter-organism TEXT` - Filter by organism name
- `--append` - Resume from last processed line
- `--log-to-file` - Save detailed logs

**Example: Process with filtering and logging**
```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output filtered_results \
    --filter-classification Mammalia \
    --log-to-file \
    --log-dir my_logs
```

## Workflow Example

### Complete workflow from start to finish:

```bash
# 1. Install dependencies
cd pdb-mcp
uv sync

# 2. Download annotation files (one-time setup)
uv run python -m pdb_mcp download download

# 3. Add your data
cp my_protein_data.jsonl.gz data/input/

# 4. Process with filtering
uv run python -m pdb_mcp resolve \
    --input-file data/input/my_protein_data.jsonl.gz \
    --output my_results \
    --mammals-only \
    --log-to-file

# 5. Check results
ls -lh data/output/my_results.*
head -20 data/output/my_results.csv
```

## Project Structure

```
pdb-mcp/
├── data/
│   ├── input/
│   │   ├── anage/
│   │   │   └── anage_data.txt              # AnAge database
│   │   ├── pdb/
│   │   │   ├── pdb_chain_uniprot.tsv.gz   # Downloaded annotation files
│   │   │   ├── pdb_chain_taxonomy.tsv.gz
│   │   │   └── ... (16 files total)
│   │   └── your_data.jsonl.gz              # Your input files
│   └── output/
│       └── results.csv & results.jsonl.gz  # Output results
├── src/pdb_mcp/
│   ├── resolve_proteins.py                 # Resolve protein names
│   ├── download_pdb_annotations.py         # Download annotations
│   └── __main__.py                         # CLI entry point
├── GETTING_STARTED.md                      # This file
├── DOWNLOAD_ANNOTATIONS.md                 # Download details
├── RESOLVE_PROTEINS_USAGE.md               # Resolve details
└── pyproject.toml                          # Project configuration
```

## Understanding the Data Flow

### Download Annotations
```
EBI SIFTS FTP Server
        ↓ (fsspec)
    data/input/pdb/
```

### Process Proteins
```
data/input/your_data.jsonl.gz
        ↓
    resolve_proteins module
        ↓ (uses annotations from data/input/pdb/)
    data/output/results.csv
    data/output/results.jsonl.gz
```

## Output Formats

### CSV Output (`results.csv`)
Tab-separated values with headers:
- `entry_id` - Original entry ID
- `pdb_id` - PDB structure ID
- `chain_id` - Chain identifier
- `protein_name` - Protein description
- `organism` - Scientific name
- `common_name` - Common organism name
- `classification` - AnAge classification (Mammalia, Aves, etc.)
- `max_longevity_yrs` - Maximum lifespan in years
- ... and more fields

### JSONL.GZ Output (`results.jsonl.gz`)
Compressed line-delimited JSON with complete metadata:
- Original entry data
- PDB metadata
- Chain-specific information
- Organism classification
- UniProt IDs
- All detailed fields

## Common Use Cases

### 1. Filter proteins by animal class

```bash
# Only birds
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output bird_proteins \
    --filter-classification Aves

# Only fish
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output fish_proteins \
    --filter-classification Actinopterygii
```

### 2. Filter proteins from specific organism

```bash
# Only human proteins
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output human_proteins \
    --filter-organism "Homo sapiens"

# Only mouse proteins
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output mouse_proteins \
    --filter-organism "Mus musculus"
```

### 3. Process large files in batches

```bash
# First 1000 lines
uv run python -m pdb_mcp resolve \
    --input-file data/input/huge_file.jsonl.gz \
    --output batch_1 \
    --line-numbers "1-1000"

# Next batch
uv run python -m pdb_mcp resolve \
    --input-file data/input/huge_file.jsonl.gz \
    --output batch_2 \
    --line-numbers "1001-2000"
```

### 4. Skip CSV output, only need JSONL

```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --skip-csv
```

## Troubleshooting

### "No such file or directory: data/input/pdb"

This means you haven't downloaded the annotation files yet. Run:
```bash
uv run python -m pdb_mcp download download
```

### "PDB ID not found in TSV"

The annotation files don't contain information for that PDB ID. This can happen if:
1. The PDB ID doesn't exist
2. The annotation files are outdated
3. The file is corrupted

Try re-downloading:
```bash
uv run python -m pdb_mcp download download --no-skip-existing
```

### "No results written" or empty output

This usually means:
1. No proteins matched your filter criteria (e.g., no mammals in your data)
2. The input file format is incorrect
3. Line numbers were specified but don't exist

Check your filters and try without filtering to see if you get any results.

### Out of memory

If you run out of memory processing large files:
1. Reduce `--pdb-cache-size` (default: 20000)
2. Reduce `--csv-batch-size` (default: 500)
3. Process in smaller batches using `--line-numbers`

## Next Steps

- Read [DOWNLOAD_ANNOTATIONS.md](DOWNLOAD_ANNOTATIONS.md) for detailed download documentation
- Read [RESOLVE_PROTEINS_USAGE.md](RESOLVE_PROTEINS_USAGE.md) for detailed resolve documentation
- Check the logs directory for processing details
- Explore the output CSV and JSONL files

## Support

For issues or questions:
1. Check the relevant markdown file for your command
2. Run with `--log-to-file` to get detailed logs
3. Verify your input data format
4. Ensure annotation files are downloaded with `uv run python -m pdb_mcp download download`

## Acknowledgments

This project uses:
- **PDB Data**: From the [PDB](https://www.rcsb.org/)
- **Annotations**: From [EBI SIFTS](https://www.ebi.ac.uk/pdbe/docs/sifts/)
- **AnAge Database**: From the [AnAge database](https://genomics.senescence.info/genes/)
- **Libraries**: Polars, Typer, Eliot, fsspec, Biotite
