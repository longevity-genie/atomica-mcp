# Resolve Protein Names and Gene Symbols

This guide explains how to use the protein name resolution CLI to fetch protein names and gene symbols from UniProt IDs in your data.

## Overview

The `resolve` command provides two main functionalities:

1. **`resolve sample`** - Test the UniProt API with a small sample of IDs
2. **`resolve resolve`** - Batch process all UniProt IDs from PP_extended.parquet

This tool:
- Loads UniProt IDs from PP_extended.parquet  
- Fetches protein names and gene symbols from the UniProt REST API
- Optionally resolves Ensembl IDs from UniProt IDs using the ID mapping service
- Joins results back with original data
- Saves enriched data to a new Parquet file

## Quick Start

### Test with a Sample (Recommended First Step)

```bash
cd pdb-mcp

# Test protein names and gene symbols
uv run python -m pdb_mcp resolve sample -n 10

# Also test Ensembl ID resolution (optional, slower)
uv run python -m pdb_mcp resolve sample -n 3 --resolve-genes
```

Output:
```
📖 Loading data/output/PP_extended.parquet...
🧪 Testing with 10 sample IDs: ['Q9V2J8', 'P12345', ...]
✓ Batch 1/1: 10 IDs fetched

✅ Successfully fetched 10 proteins:
shape: (10, 3)
┌────────────────────────────────┬──────────────────┬──────────────────┐
│ Protein names                  ┆ Gene Names       ┆ Organism         │
│ ---                            ┆ ---              ┆ ---              │
│ str                            ┆ str              ┆ str              │
╞════════════════════════════════╪══════════════════╪══════════════════╡
│ Glycogen synthase              ┆ GSY1 GYS GYS1    ┆ Homo sapiens     │
│ ...                            ┆ ...              ┆ ...              │
└────────────────────────────────┴──────────────────┴──────────────────┘
```

### Resolve All UniProt IDs (50k+ IDs)

```bash
# Default: Protein names and gene symbols
uv run python -m pdb_mcp resolve resolve

# With Ensembl IDs (optional, takes longer due to API async jobs)
uv run python -m pdb_mcp resolve resolve --resolve-genes

# With sequential processing (safer)
uv run python -m pdb_mcp resolve resolve --no-parallel

# Custom output location
uv run python -m pdb_mcp resolve resolve \
    --output-file data/output/my_proteins.parquet
```

## Command Reference

### `resolve sample` - Test with Sample Data

Test the UniProt API and verify connectivity before processing all data.

```bash
uv run python -m pdb_mcp resolve sample [OPTIONS]
```

**Options:**

- `-i, --input-file PATH` - Input Parquet file (default: `data/output/PP_extended.parquet`)
- `-u, --uniprot-column TEXT` - Column name with UniProt IDs (default: `UniProtKB_AC`)
- `-n, --sample-size INTEGER` - Number of samples to fetch (default: 10)
- `--resolve-genes / --no-resolve-genes` - Also test Ensembl ID resolution (default: no)

**Examples:**

```bash
# Test protein names only
uv run python -m pdb_mcp resolve sample

# Test with 5 IDs
uv run python -m pdb_mcp resolve sample -n 5

# Test including Ensembl IDs
uv run python -m pdb_mcp resolve sample -n 5 --resolve-genes

# Test with custom input
uv run python -m pdb_mcp resolve sample -i data/output/my_data.parquet -n 20
```

### `resolve resolve` - Process All UniProt IDs

Batch fetch protein names and gene symbols for all UniProt IDs in your data.

```bash
uv run python -m pdb_mcp resolve resolve [OPTIONS]
```

**Options:**

- `-i, --input-file PATH` - Input Parquet file (default: `data/output/PP_extended.parquet`)
- `-o, --output-file PATH` - Output Parquet file (default: `data/output/protein_names.parquet`)
- `-u, --uniprot-column TEXT` - Column name with UniProt IDs (default: `UniProtKB_AC`)
- `--resolve-genes / --no-resolve-genes` - Resolve Ensembl IDs (default: no)
- `--parallel / --no-parallel` - Use parallel requests (default: parallel, faster)
- `-b, --batch-size INTEGER` - IDs per API request (default: 500)
- `-w, --max-workers INTEGER` - Parallel workers (default: 5)
- `--verbose / --no-verbose` - Show detailed output (default: verbose)

**Examples:**

```bash
# Process all IDs with protein names and gene symbols
uv run python -m pdb_mcp resolve resolve

# Also resolve Ensembl IDs (optional)
uv run python -m pdb_mcp resolve resolve --resolve-genes

# Sequential processing
uv run python -m pdb_mcp resolve resolve --no-parallel

# Faster parallel with 10 workers
uv run python -m pdb_mcp resolve resolve --max-workers 10

# Custom output
uv run python -m pdb_mcp resolve resolve \
    --input-file data/output/PP_extended.parquet \
    --output-file data/output/proteins_enriched.parquet

# Silent mode
uv run python -m pdb_mcp resolve resolve --no-verbose
```

## Performance Characteristics

### For 50,000 UniProt IDs:

| Configuration | Time | Network | Output |
|---|---|---|---|
| **Protein names only** | 5-10 min | 100 requests | Fast |
| **+ Gene symbols** | 5-10 min | 100 requests | Same  
| **+ Ensembl IDs** | 10-20 min | 100 + async mapping | Slower (async jobs) |
| **Sequential** | 15-20 min | 100 requests | More reliable |

**Network calculations:**
- 50,000 IDs ÷ 500 per request = 100 requests
- With 5 parallel workers: 100 ÷ 5 = 20 batches

## Output Format

The output file contains your original data plus new columns:

**Always added:**

- `uniprot_protein_name` - Full protein name from UniProt
- `uniprot_gene_names` - Gene symbols and aliases (space-separated)
- `uniprot_organism_name` - Organism name from UniProt

**Optionally added (with `--resolve-genes`):**

- `ensembl_id` - Ensembl gene ID (if available and mapping succeeds)

**Example output:**

```
entry_id          | UniProtKB_AC | uniprot_protein_name | uniprot_gene_names | ensembl_id
7um4_1_A_B        | Q9V2J8       | Glycogen synthase    | GSY1 GYS GYS1      | ENSG00000140641
...
```

## Gene Symbol and Ensembl ID Resolution

### Default Behavior (Recommended)

The tool always fetches gene symbols directly from UniProt:

```bash
uv run python -m pdb_mcp resolve resolve
```

This adds the `uniprot_gene_names` column with gene symbols and aliases.

### Optional: Ensembl ID Mapping

To also resolve Ensembl IDs:

```bash
uv run python -m pdb_mcp resolve resolve --resolve-genes
```

**Note:** This takes longer because:
- Each UniProt→Ensembl mapping creates an async job on the UniProt server
- The tool polls for job completion (up to 60 seconds per job)
- If mapping fails, the entry will have NULL in `ensembl_id` column

**When to use:**
- ✅ You need Ensembl IDs for downstream analysis
- ✅ You have time for longer processing
- ❌ You only need gene symbols (use default instead)

## API Behavior

### UniProt Rate Limiting

The UniProt API has rate limits:
- ~1 request per second for sequential queries
- ~5 requests per second for parallel queries (with 5 workers)

The tool respects these limits automatically.

### Batch Processing Strategy

The tool uses efficient batch processing:

1. **Extracts unique UniProt IDs** from your data
2. **Groups IDs into batches** (default: 500 IDs per request)
3. **Builds OR queries** - `accession:Q9V2J8 OR accession:P12345 OR ...`
4. **Fetches via TSV format** - Faster parsing than JSON
5. **Combines results** into a single DataFrame
6. **Left joins** with original data (preserves unmatched entries)
7. **(Optional) Maps to Ensembl** - Async job per UniProt ID set

### Data Retrieved

For each UniProt ID, the API returns:

- **Accession** - UniProt ID
- **Protein names** - Full protein name
- **Gene Names** - Gene symbols and aliases
- **Organism** - Species name
- **Reviewed** - Whether entry is manually reviewed
- **Ensembl** - (optional) Ensembl gene ID

## Troubleshooting

### No UniProt IDs Found

```
✗ No UniProt IDs found in the specified column
```

**Solution:** Check that:
1. The input file exists
2. The column name is correct (case-sensitive)
3. The column contains valid UniProt IDs

```bash
# Inspect your data
uv run python3 -c "
import polars as pl
df = pl.read_parquet('data/output/PP_extended.parquet')
print('Columns:', df.columns)
print('Sample IDs:', df['UniProtKB_AC'].head())
"
```

### Connection Errors

```
✗ Batch 1 failed: [Errno -2] Name or service not known
```

**Solutions:**
1. Check internet connectivity
2. Verify UniProt API is online: https://rest.uniprot.org/uniprotkb/search
3. Try again later (temporary server issues)
4. Use `--no-parallel` to reduce load

### Ensembl Resolution Slow or Timeout

```
Waiting for mapping... (30/60)
```

**Solutions:**
1. Omit `--resolve-genes` (default works fine without Ensembl)
2. Use smaller `--batch-size`
3. Reduce `--max-workers` to 1 (sequential only)
4. Check UniProt API status

## Integration with Your Workflow

### Example: Basic Usage

```bash
# 1. Test with sample
uv run python -m pdb_mcp resolve sample -n 20

# 2. Process all data
uv run python -m pdb_mcp resolve resolve \
    --output-file data/output/PP_proteins.parquet

# 3. Load and inspect results
uv run python3 << 'EOF'
import polars as pl

result = pl.read_parquet('data/output/PP_proteins.parquet')
print(f"Total rows: {result.height}")
print(f"Rows with protein names: {result.filter(pl.col('uniprot_protein_name').is_not_null()).height}")
print(f"Rows with gene names: {result.filter(pl.col('uniprot_gene_names').is_not_null()).height}")
print("\nSample:")
print(result.select([
    'entry_id', 'UniProtKB_AC', 
    'uniprot_protein_name', 'uniprot_gene_names'
]).head())
EOF
```

### Example: Using Results in Python

```python
import polars as pl

# Load enriched data
df = pl.read_parquet('data/output/PP_proteins.parquet')

# Filter for entries with gene symbols
with_genes = df.filter(pl.col('uniprot_gene_names').is_not_null())

# Extract gene symbols
def parse_gene_names(gene_str: str) -> list:
    """Parse space-separated gene names into list."""
    if gene_str is None:
        return []
    return gene_str.split()

genes_df = with_genes.with_columns(
    pl.col('uniprot_gene_names')
    .map_elements(parse_gene_names, return_dtype=pl.List(pl.Utf8))
    .alias('gene_symbols')
)

# Export for downstream analysis
genes_df.select([
    'entry_id', 'UniProtKB_AC', 
    'uniprot_protein_name', 'gene_symbols'
]).write_csv('data/output/protein_genes.csv')
```

## Logging

The tool uses `eliot` for structured logging. Logs are automatically tracked for each action.

## API Documentation

For more information:

- [UniProt REST API](https://www.uniprot.org/help/uniprotkb-api)
- [API Field Reference](https://www.uniprot.org/help/return_fields)
- [Query Syntax](https://www.uniprot.org/help/query-fields)
- [ID Mapping Service](https://www.uniprot.org/id-mapping)

## Advanced Usage

### Custom Data Source

If you have UniProt IDs in a different file:

```python
from pdb_mcp.resolve_protein_names import fetch_uniprot_batch
import polars as pl

# Load your UniProt IDs
uniprot_ids = ["Q9V2J8", "P12345", "Q67890"]

# Fetch protein information
result_df = fetch_uniprot_batch(uniprot_ids)

# Save results
result_df.write_parquet("my_proteins.parquet")
```

### Programmatic Usage

```python
from pathlib import Path
from pdb_mcp.resolve_protein_names import fetch_uniprot_parallel

# Your data
uniprot_ids = ["Q9V2J8", "P12345"] * 25000  # 50k IDs

# Fetch with parallel processing
result = fetch_uniprot_parallel(
    uniprot_ids,
    batch_size=500,
    max_workers=5
)

# Process results
enriched = result.with_columns([
    pl.col("Gene Names").str.split(" ").alias("gene_symbols")
])

enriched.write_parquet("enriched_proteins.parquet")
```

## Performance Tips

1. **First run:** Use `--sample` to verify connectivity and data format
2. **Large datasets:** Use `--parallel --max-workers 5` (default)
3. **Gene symbols only:** Omit `--resolve-genes` (faster)
4. **Low bandwidth:** Use `--no-parallel` and `--batch-size 200`
5. **Reliable:** Use `--no-parallel` (safest for unstable connections)
