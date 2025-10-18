# Download PDB Annotations

This guide explains how to download PDB annotation files from the EBI SIFTS database for use with the `resolve_proteins` module.

## Overview

The PDB annotation files are stored at the [EBI SIFTS FTP server](https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/). The `download_pdb_annotations` module provides a convenient way to download all necessary files using `fsspec`.

## Quick Start

### Using the CLI

The simplest way to download all annotation files:

```bash
cd pdb-mcp

# Download all files to data/input/pdb/
uv run python -m pdb_mcp download download

# Download to a custom location
uv run python -m pdb_mcp download download --output-dir /path/to/annotations

# Download without skipping existing files (re-download everything)
uv run python -m pdb_mcp download download --no-skip-existing
```

### Using as a Python Module

```python
from pathlib import Path
from pdb_mcp.download_pdb_annotations import download

download(
    output_dir=Path("data/input/pdb"),
    skip_existing=True,
    verbose=True
)
```

## Available Files

The following annotation files will be downloaded from [ftp://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/](https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/):

**Essential for resolve_proteins:**
- `pdb_chain_uniprot.tsv.gz` (5.5 MB) - PDB chain to UniProt mapping
- `pdb_chain_taxonomy.tsv.gz` (54 MB) - PDB chain taxonomy information

**Additional annotation files:**
- `pdb_chain_cath_uniprot.tsv.gz` (2.2 MB)
- `pdb_chain_ensembl.tsv.gz` (18 MB)
- `pdb_chain_enzyme.tsv.gz` (1.8 MB)
- `pdb_chain_go.tsv.gz` (73 MB)
- `pdb_chain_hmmer.tsv.gz` (4.0 MB)
- `pdb_chain_interpro.tsv.gz` (12 MB)
- `pdb_chain_pfam.tsv.gz` (4.9 MB)
- `pdb_chain_scop_uniprot.tsv.gz` (850 KB)
- `pdb_chain_scop2_uniprot.tsv.gz` (496 KB)
- `pdb_chain_scop2b_sf_uniprot.tsv.gz` (5.6 MB)
- `pdb_pfam_mapping.tsv.gz` (11 MB)
- `pdb_pubmed.tsv.gz` (1.0 MB)
- `uniprot_pdb.tsv.gz` (1.4 MB)
- `uniprot_segments_observed.tsv.gz` (9.4 MB)

**Total download size: ~200+ MB**

## Command-Line Options

```
Usage: python -m pdb_mcp download download [OPTIONS]

Options:
  --output-dir PATH              Output directory for downloaded files
                                 [default: data/input/pdb/]
  --skip-existing / --no-skip-existing
                                 Skip files that already exist
                                 [default: skip-existing]
  --verbose / --no-verbose       Enable verbose output
                                 [default: verbose]
  --help                         Show this message and exit
```

### Options Explained

- **`--output-dir`**: Where to save the downloaded files. If not specified, defaults to `data/input/pdb/` within the project.

- **`--skip-existing`** (default): Skips downloading files that already exist in the output directory. Useful for resuming interrupted downloads.

- **`--no-skip-existing`**: Downloads all files, overwriting any existing ones.

- **`--verbose`** (default): Shows download progress and status for each file.

- **`--no-verbose`**: Suppresses progress output (only shows summary).

## Examples

### Download all files to default location

```bash
uv run python -m pdb_mcp download download
```

Output:
```
⬇ Downloading: pdb_chain_uniprot.tsv.gz... ✓ (5.5 MB)
⬇ Downloading: pdb_chain_taxonomy.tsv.gz... ✓ (54.0 MB)
⬇ Downloading: pdb_chain_cath_uniprot.tsv.gz... ✓ (2.2 MB)
...

============================================================
✓ Downloaded: 16 files
📁 Output directory: /home/user/pdb-mcp/data/input/pdb
============================================================
```

### Resume incomplete download

```bash
# First attempt (interrupted)
uv run python -m pdb_mcp download download

# Resume - automatically skips existing files
uv run python -m pdb_mcp download download
```

### Download to custom location

```bash
mkdir -p /tmp/pdb_annotations
uv run python -m pdb_mcp download download --output-dir /tmp/pdb_annotations
```

### Force re-download all files

```bash
uv run python -m pdb_mcp download download --no-skip-existing
```

### Silent mode

```bash
uv run python -m pdb_mcp download download --no-verbose
```

## Integration with resolve_proteins

After downloading the annotation files, you can use them with the `resolve_proteins` module:

```bash
# The files are automatically found in data/input/pdb/
uv run python -m pdb_mcp resolve \
    --input-file data/input/your_data.jsonl.gz \
    --output results
```

The `resolve_proteins` module will automatically use the downloaded TSV files for faster, local lookups instead of querying the RCSB API.

## Logging

Download operations are logged using `eliot`. To save logs:

```bash
uv run python -m pdb_mcp download download --output-dir data/input/pdb
```

Logs will be available through the standard logging system. To enable file logging, the module uses the same logging infrastructure as `resolve_proteins`.

## Troubleshooting

### FTP Connection Errors

If you get FTP connection errors, check:
1. Internet connectivity
2. The EBI SIFTS server is online at [https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/](https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/)
3. Try again later if the server is temporarily unavailable

### File Size Issues

Downloaded files should match the sizes shown on the FTP server. If a download was interrupted:
1. Delete the partially downloaded file
2. Re-run the download command without `--skip-existing`

### Disk Space

Ensure you have enough disk space (at least 200+ MB) for all annotation files.

## Data Locations

Once downloaded, the annotation files are stored in:
```
pdb-mcp/data/input/pdb/
├── pdb_chain_uniprot.tsv.gz
├── pdb_chain_taxonomy.tsv.gz
└── ... (other annotation files)
```

These are used by the `resolve_proteins` module in TSV mode for fast organism classification and UniProt mapping.

## Alternative: Manual Download

If you prefer to download manually:

1. Visit [https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/](https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/)
2. Download the `.tsv.gz` files you need
3. Place them in `data/input/pdb/`

The minimum required files for `resolve_proteins` are:
- `pdb_chain_uniprot.tsv.gz`
- `pdb_chain_taxonomy.tsv.gz`

