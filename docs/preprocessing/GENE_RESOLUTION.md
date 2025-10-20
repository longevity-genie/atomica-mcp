# Gene Resolution Tool

## Overview

The gene resolution tool resolves **protein names**, **gene symbols**, and **Ensembl IDs** from UniProt IDs in batch using the UniProt APIs.

**Default input file:** `data/output/PP_graph_embeddings.parquet`

## What It Does

The tool resolves information in this order:

1. **🧬 Protein Names** - Fetches protein names from UniProt API
2. **🔤 Gene Symbols** - Maps UniProt IDs → Gene Names (actual gene symbols like "HLA-DPB1", "VPS36")
3. **🔗 Ensembl IDs** - Maps UniProt IDs → Ensembl IDs (fills gaps in input Ensembl IDs from input file)

## Important: No Fallback

**Gene symbols are NOT filled with Ensembl IDs as fallback.**
- If UniProt doesn't return a gene symbol → `primary_gene_name` is **NULL**
- Ensembl IDs stay separate in their own column
- This keeps data clean and unambiguous

## Usage

### Basic (recommended)
```bash
uv run python -m pdb_mcp resolve resolve
```
- Input: `data/output/PP_graph_embeddings.parquet` (default)
- Output: `data/output/protein_names.parquet` (default)
- Gene resolution: **ENABLED** by default
- Protein name resolution: **ENABLED** by default
- Sequence resolution: **DISABLED** by default

### With Ensembl IDs (Optional)
```bash
# All 50k IDs + Ensembl IDs: 10-20 minutes (async jobs)
uv run python -m pdb_mcp resolve resolve --resolve-genes
```

### Test Mode
```bash
# Test protein names/gene symbols
uv run python -m pdb_mcp resolve sample -n 10

# Test with Ensembl IDs too
uv run python -m pdb_mcp resolve sample -n 3 --resolve-genes
```

### Enable sequence resolution
```bash
uv run python -m pdb_mcp resolve resolve --resolve-sequences
```
Fetches amino acid sequences from UniProt for each protein.

### Custom input/output
```bash
uv run python -m pdb_mcp resolve resolve \
  --input-file data/output/PP_extended.parquet \
  --output-file data/output/PP_advanced.parquet
```

### Disable features
```bash
# Disable gene resolution
uv run python -m pdb_mcp resolve resolve --no-resolve-genes

# Disable everything except protein names
uv run python -m pdb_mcp resolve resolve --no-resolve-genes --no-resolve-sequences
```

### Test with sample
```bash
uv run python -m pdb_mcp resolve sample -n 20
```

## Output Columns (Added)

- **`uniprot_protein_names`**: Protein names from UniProt
- **`uniprot_gene_names`**: All gene name aliases from UniProt (space-separated)
- **`primary_gene_name`**: Primary gene symbol OR NULL if not resolved (no fallback!)
- **`uniprot_organism_name`**: Organism name from UniProt
- **`ensembl_id`**: Ensembl gene identifier (from input or API resolution)
- **`protein_sequence`**: Amino acid sequence (only if `--resolve-sequences` enabled)

## Example Results

| UniProtKB_AC | primary_gene_name | ensembl_id | uniprot_protein_names |
|---|---|---|---|
| P04440 | HLA-DPB1 | ENSG00000215048.13 | HLA class II... |
| Q86VN1 | VPS36 | ENSG00000136100.14 | Vacuolar... |
| P76216 | astB | null | Arylsulfatase... |
| P49842 | null | ENSG00000204344.16 | (null if not resolved) |

## Command Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--input-file` | `PP_graph_embeddings.parquet` | Input file path |
| `--output-file` | `protein_names.parquet` | Output file path |
| `--resolve-genes` | `true` | Resolve gene symbols and Ensembl IDs |
| `--resolve-sequences` | `false` | Fetch protein sequences (slower!) |
| `--parallel` | `true` | Use parallel API requests |
| `--batch-size` | `500` | IDs per API request |
| `--max-workers` | `5` | Parallel workers |
| `--verbose` | `true` | Detailed output |

## Why Optional Ensembl ID Resolution?

The Ensembl ID resolution is optional because:
- Uses UniProt's async ID mapping service
- Each batch creates a job that must be polled for completion
- Takes longer due to server-side processing
- May fail for some entries (optional field set to NULL)

**Recommendation:** Use the default (without `--resolve-genes`) unless you specifically need Ensembl IDs.

## Performance

| Configuration | Time | Network | Notes |
|---|---|---|---|
| **Protein names only** | 5-10 min | 100 requests | Fastest, recommended |
| **+ Gene symbols** | 5-10 min | 100 requests | Same as above |
| **+ Ensembl IDs** | 10-20 min | 100 + async mapping | Slower (async jobs) |
| **Sequential** | 15-20 min | 100 requests | More reliable |

**Network calculations:**
- 50,000 IDs ÷ 500 per request = 100 requests
- With 5 parallel workers: 100 ÷ 5 = 20 batches

- **9,001 UniProt IDs (no sequences)**: ~2-3 minutes
- **9,001 UniProt IDs (with sequences)**: ~10-15 minutes (slower due to sequence data)
- **Parallel requests**: Enabled by default (faster)

## Coverage

For typical PDB datasets:
- ~50-70% of entries get protein names from UniProt
- ~50-70% of entries get gene symbols from UniProt mapping
- ~68% of entries get Ensembl IDs from UniProt mapping or input file
- Remaining entries have NULL values (no fallback to Ensembl IDs)

