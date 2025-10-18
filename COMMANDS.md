# PDB-MCP Commands Reference

Quick reference for all available commands.

## Main CLI

```bash
uv run python -m pdb_mcp --help
```

## Download Commands

### Download all PDB annotations from EBI SIFTS

```bash
uv run python -m pdb_mcp download download
```

Downloads all 16 TSV.GZ files (~200 MB) to `data/input/pdb/`

**Options:**
```bash
# Download to custom location
uv run python -m pdb_mcp download download --output-dir /path/to/pdb

# Force re-download (skip nothing)
uv run python -m pdb_mcp download download --no-skip-existing

# Quiet mode (skip progress output)
uv run python -m pdb_mcp download download --no-verbose

# Show help
uv run python -m pdb_mcp download download --help
```

## Resolve Commands

### Basic protein resolution

```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results
```

Creates:
- `data/output/results.csv` (tabular data)
- `data/output/results.jsonl.gz` (detailed JSON)

### With filtering

**Mammals only:**
```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --mammals-only
```

**Specific organism:**
```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --filter-organism "Homo sapiens"
```

**Specific classification:**
```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --filter-classification Mammalia
```

### Large file processing

**Process specific lines:**
```bash
# First 1000 lines
uv run python -m pdb_mcp resolve \
    --input-file data/input/large.jsonl.gz \
    --output batch_1 \
    --line-numbers "1-1000"

# Specific lines
uv run python -m pdb_mcp resolve \
    --input-file data/input/large.jsonl.gz \
    --output selected \
    --line-numbers "100,500,1000-2000"
```

**Resume interrupted processing:**
```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --append
```

### Output options

**Skip JSON output (CSV only):**
```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --skip-jsonl
```

**Skip CSV output (JSON only):**
```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --skip-csv
```

### Logging

**Log to files:**
```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --log-to-file
```

Creates:
- `logs/resolve_proteins.json` (machine-readable logs)
- `logs/resolve_proteins.log` (human-readable logs)

**Custom log location and name:**
```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --log-to-file \
    --log-dir my_logs \
    --log-file-name my_run
```

Creates:
- `my_logs/my_run.json`
- `my_logs/my_run.log`

### Performance tuning

**Reduce memory usage (for large files):**
```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --pdb-cache-size 5000 \
    --csv-batch-size 100
```

**Adjust API timeouts (if using API mode):**
```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --timeout 30 \
    --retries 5
```

### API mode (instead of TSV)

```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --no-use-tsv
```

Note: Slower than TSV mode but doesn't require pre-downloaded annotations.

### Show all options

```bash
uv run python -m pdb_mcp resolve --help
```

## Common Workflows

### 1. First-time setup

```bash
# Install dependencies
cd pdb-mcp
uv sync

# Download annotations (one-time)
uv run python -m pdb_mcp download download

# Verify download
ls -lh data/input/pdb/ | head
```

### 2. Process with filtering

```bash
# Mammals only
uv run python -m pdb_mcp resolve \
    --input-file data/input/my_proteins.jsonl.gz \
    --output mammals_only \
    --mammals-only

# Check results
wc -l data/output/mammals_only.csv
head -5 data/output/mammals_only.csv
```

### 3. Large file batch processing

```bash
# Get line count
zcat data/input/huge.jsonl.gz | wc -l

# Process in 10k line batches
for i in {0..90..10}; do
  start=$((i * 1000 + 1))
  end=$(((i+10) * 1000))
  echo "Processing lines $start-$end"
  uv run python -m pdb_mcp resolve \
    --input-file data/input/huge.jsonl.gz \
    --output batch_$i \
    --line-numbers "$start-$end"
done
```

### 4. Debugging with logs

```bash
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --log-to-file \
    --log-dir debug_logs \
    --log-file-name my_test

# Check logs
tail -100 debug_logs/my_test.log
```

### 5. Resume interrupted job

```bash
# First run (gets interrupted)
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results

# Resume from where it stopped
uv run python -m pdb_mcp resolve \
    --input-file data/input/proteins.jsonl.gz \
    --output results \
    --append
```

## All Options Reference

### resolve command

```
--input-file PATH              Input JSONL.GZ file (required)
--output PATH                  Output filename (required)
--line-numbers TEXT            Process specific lines (e.g., "1-1000" or "1,5,10")
--anage-file PATH              AnAge database file (default: data/input/anage/anage_data.txt)
--skip-jsonl                   Skip JSONL output
--skip-csv                     Skip CSV output
--append                       Resume from last line
--log-to-file                  Log to files
--log-dir PATH                 Log directory (default: logs)
--log-file-name TEXT           Log file base name (default: resolve_proteins)
--clean-destinations           Clean previous destinations
--show-chains                  Show chain information (default: true)
--filter-organism TEXT         Filter by organism name
--filter-classification TEXT   Filter by classification (e.g., Mammalia)
--mammals-only                 Shorthand for Mammalia filter
--timeout INTEGER              API timeout in seconds (default: 10)
--retries INTEGER              Retry attempts (default: 3)
--pdb-cache-size INTEGER       PDB metadata cache size (default: 20000)
--csv-batch-size INTEGER       CSV rows per batch (default: 500)
--use-tsv / --no-use-tsv       Use TSV files vs API (default: true)
--help                         Show help
```

### download download command

```
--output-dir PATH              Output directory (default: data/input/pdb/)
--skip-existing                Skip existing files (default: true)
--verbose                      Show progress (default: true)
--help                         Show help
```

## Need Help?

- See `GETTING_STARTED.md` for comprehensive guide
- See `DOWNLOAD_ANNOTATIONS.md` for download details
- See `RESOLVE_PROTEINS_USAGE.md` for resolve details
- Run `--help` on any command
