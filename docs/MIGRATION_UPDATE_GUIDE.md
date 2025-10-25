# ATOMICA Dataset Migration & Update Guide

This guide explains how to migrate legacy dataset structures (with files spread across multiple folders) into the standardized ATOMICA format, update your main dataset index, and sync with the HuggingFace repository.

## Overview

The ATOMICA longevity proteins dataset is hosted on HuggingFace at:
**https://huggingface.co/datasets/longevity-genie/atomica_longevity_proteins**

### Important Notes

⚠️ **The dataset is NOT a git submodule** - it's downloaded directly from HuggingFace using the `dataset download` command.

⚠️ **Always download the latest dataset first** before making updates to ensure you have the current version.

⚠️ **After migration, upload changes back to HuggingFace** using the `upload_to_hf.py` script to share your updates.

### Old Structure (Legacy)
Files were scattered across multiple locations with inconsistent organization:
```
downloads/pdbs/
├── 1b68.cif
├── 6ht5.cif
└── ...

downloads/pdbs/
├── 1b68.json (metadata)
├── 6ht5.json (metadata)
└── ...

output/
├── 1b68_critical_residues.tsv
├── 1b68_interact_scores.json
├── 1b68_pymol_commands.pml
├── 1b68_summary.json
├── 6ht5_critical_residues.tsv
├── 6ht5_interact_scores.json
├── 6ht5_pymol_commands.pml
├── 6ht5_summary.json
└── ...
```

### New Structure (Standardized)
Files are organized by PDB ID in a single directory:
```
data/input/atomica_longevity_proteins/
├── 1b68/
│   ├── 1b68.cif
│   ├── 1b68_metadata.json
│   ├── 1b68_critical_residues.tsv
│   ├── 1b68_interact_scores.json
│   ├── 1b68_pymol_commands.pml
│   └── 1b68_summary.json
├── 6ht5/
│   ├── 6ht5.cif
│   ├── 6ht5_metadata.json
│   ├── 6ht5_critical_residues.tsv
│   ├── 6ht5_interact_scores.json
│   ├── 6ht5_pymol_commands.pml
│   └── 6ht5_summary.json
└── atomica_index.parquet
```

## Complete Migration Workflow

### Prerequisites

1. **HuggingFace Token** (for uploading changes):
   ```bash
   # Set your HF token as environment variable
   export HF_TOKEN="your_huggingface_token_here"
   
   # Or add to .env file in project root
   echo "HF_TOKEN=your_huggingface_token_here" >> .env
   ```

2. **Python Environment** with required packages:
   ```bash
   pip install atomica-mcp  # or install from source
   ```

## Migration Steps

### Step 0: Download Current Dataset from HuggingFace

**⚠️ CRITICAL**: Always start by downloading the current dataset to ensure you have the latest version:

```bash
# Download the full dataset (default location: data/input/atomica_longevity_proteins)
python -m atomica_mcp.dataset download

# Or specify custom location
python -m atomica_mcp.dataset download --output-dir data/input/atomica_longevity_proteins
```

This ensures you're working with the current dataset and won't overwrite existing structures when updating.

### Step 1: Prepare Your New Dataset

Consolidate all files related to each PDB into a single staging directory.

**Option A: If files are in separate folders**

Create a staging directory and copy files:
```bash
# Create staging area
mkdir -p staging/atomica_staging

# Copy structure files
cp downloads/pdbs/*.cif staging/atomica_staging/

# Copy metadata files
cp downloads/pdbs/*.json staging/atomica_staging/

# Copy analysis files
cp output/*_critical_residues.tsv staging/atomica_staging/
cp output/*_interact_scores.json staging/atomica_staging/
cp output/*_pymol_commands.pml staging/atomica_staging/
cp output/*_summary.json staging/atomica_staging/
```

**Option B: If metadata files need renaming**

Ensure metadata files have the `_metadata.json` suffix:
```bash
cd staging/atomica_staging
for f in *.json; do
  # Skip if already has _metadata or other suffix
  if [[ ! "$f" =~ _(metadata|summary|interact_scores)\.json$ ]]; then
    pdb_id="${f%.json}"
    if [[ -f "$pdb_id.cif" ]]; then
      mv "$f" "${pdb_id}_metadata.json"
    fi
  fi
done
cd -
```

### Step 2: Preview Reorganization (Dry Run)

Before making actual changes, do a dry run to see what will happen:

```bash
# Dry run - shows what would be reorganized (no index needed!)
python -m atomica_mcp.dataset reorganize \
  --dataset-dir staging/atomica_staging \
  --dry-run
```

**Output example:**
```
📦 Reorganizing ATOMICA dataset: /path/to/staging/atomica_staging
📊 No index provided - will reorganize based on file patterns
🔍 DRY RUN MODE - No files will be moved

🔍 Scanning directory for PDB files...
✓ Found 47 PDB IDs based on file patterns

🔧 Reorganizing files...
  [1/47] 1B68: Created folder
  [2/47] 6HT5: Created folder
  ...

📊 Reorganization Summary:
  📁 Folders created: 47
  📦 Files moved: 282
  ⊘ Files already in place: 0
  📍 All paths now relative to: atomica_staging/

🔍 This was a DRY RUN. Run without --dry-run to apply changes.
```

### Step 3: Execute Reorganization

Once you've verified the dry run output, execute the actual reorganization:

```bash
# Reorganize files into per-PDB folders (no index needed!)
python -m atomica_mcp.dataset reorganize \
  --dataset-dir staging/atomica_staging
```

**Result:**
```
✅ Dataset reorganization completed successfully!
```

Now your staging directory will have the new structure:
```
staging/atomica_staging/
├── 1b68/
│   ├── 1b68.cif
│   ├── 1b68_metadata.json
│   ├── 1b68_critical_residues.tsv
│   ├── 1b68_interact_scores.json
│   ├── 1b68_pymol_commands.pml
│   └── 1b68_summary.json
├── 6ht5/
│   └── ... (similar structure)
└── ...
```

### Step 4: Update Main Dataset Index

Now update your main ATOMICA dataset with the newly reorganized structures:

```bash
# Update the main index with new structures from staging
python -m atomica_mcp.dataset update \
  --update-dir staging/atomica_staging \
  --dataset-dir data/input/atomica_longevity_proteins \
  --index data/output/atomica_index.parquet
```

**Parameters explained:**
- `--update-dir`: Staging folder with reorganized structures (source)
- `--dataset-dir`: Main dataset directory (destination/reference for relative paths)
- `--index`: Main index file to update

**Output example:**
```
📦 Updating ATOMICA index
📂 Update directory: staging/atomica_staging
📊 Existing index: data/output/atomica_index.parquet
💾 Output: data/output/atomica_index.parquet

📖 Loading existing index...
✓ Loaded 94 existing structures

🔍 Scanning for new structures in staging/atomica_staging...
✓ Found 47 structure files
✓ Found 47 new structures to process

🔬 Resolving metadata for 47 new structures...
  [1/47] Resolving metadata for 1B68... ✓ (1 UniProt, 1 genes, Homo sapiens)
  [2/47] Resolving metadata for 6HT5... ✓ (1 UniProt, 1 genes, Homo sapiens)
  ...

🧬 Batch-resolving Ensembl IDs for new structures...
  Found 47 unique UniProt IDs to resolve
  ✓ Resolved Ensembl IDs for 47 structures

📊 Creating updated index...
✓ Combined 94 existing + 47 new = 141 total structures

💾 Saving updated index to: data/output/atomica_index.parquet
💾 Saving updated index to dataset directory: data/input/atomica_longevity_proteins/atomica_index.parquet

========================================================
📊 Update Summary:
  Previous structures: 94
  New structures added: 47
  Total structures: 141
  New with metadata: 47
  New UniProt IDs: 47
  New gene symbols: 47
  New Ensembl IDs: 47

  📁 Updated index saved: /path/to/data/output/atomica_index.parquet
  📁 Also saved to: /path/to/data/input/atomica_longevity_proteins/atomica_index.parquet
========================================================

✅ Index update completed successfully!
```

### Step 5: Copy to Dataset Directory

Copy the reorganized structures to the main dataset directory:

```bash
# Copy reorganized structures to main dataset
cp -r staging/atomica_staging/*/ data/input/atomica_longevity_proteins/

# Verify
ls -la data/input/atomica_longevity_proteins/ | head -20
```

### Step 6: Upload to HuggingFace (CRITICAL!)

**⚠️ IMPORTANT**: After updating the dataset locally, you MUST upload changes to HuggingFace to share with the team.

```bash
# Upload updated dataset to HuggingFace
python -m atomica_mcp.upload_to_hf upload \
  --local-dir data/input/atomica_longevity_proteins \
  --repo-id longevity-genie/atomica_longevity_proteins \
  --commit-message "Add FOXO3/HSF1/NRF2 structures from new analysis"
```

**Upload features:**
- ✅ **Intelligent sync** - Only uploads new or changed files
- ✅ **Hash-based comparison** - Compares local vs remote file hashes
- ✅ **Bulk upload** - Single commit for all changes
- ✅ **Dry run support** - Preview what will be uploaded

**Preview before uploading:**
```bash
# Dry run to see what would be uploaded
python -m atomica_mcp.upload_to_hf upload \
  --local-dir data/input/atomica_longevity_proteins \
  --dry-run
```

**Output example:**
```
Found 47 files to upload:
  - 1b68/1b68.cif
  - 1b68/1b68_metadata.json
  - 1b68/1b68_critical_residues.tsv
  ...
  - atomica_index.parquet

Uploading to longevity-genie/atomica_longevity_proteins...
Upload complete!
Commit URL: https://huggingface.co/datasets/longevity-genie/atomica_longevity_proteins/commit/abc123
```

### Step 7: Verify Upload

Verify that the structures were properly added:

```bash
# View the dataset on HuggingFace
open https://huggingface.co/datasets/longevity-genie/atomica_longevity_proteins

# Or load and inspect the updated index
python << 'EOF'
import polars as pl

# Load the updated index
df = pl.read_parquet("data/output/atomica_index.parquet")

print(f"Total structures: {len(df)}")
print(f"\nTotal UniProt IDs: {sum(len(ids) for ids in df['uniprot_ids'].to_list())}")
print(f"Total gene symbols: {sum(len(genes) for genes in df['gene_symbols'].to_list())}")
print(f"Total Ensembl IDs: {sum(len(ids) for ids in df['ensembl_ids'].to_list())}")

# Show organism distribution
from collections import Counter
all_organisms = [org for orgs in df['organisms'].to_list() for org in orgs if org]
org_counts = Counter(all_organisms)
print(f"\nOrganism distribution:")
for org, count in org_counts.most_common(5):
    print(f"  {org}: {count} structures")

# Show sample of new entries
print("\nSample of updated dataset:")
print(df.select(['pdb_id', 'uniprot_ids', 'gene_symbols', 'organisms']).head(5))
EOF
```

## Troubleshooting

### Issue: "No PDB files found in directory"

**Cause:** Files aren't named with the expected pattern

**Solution:** Check file names match pattern:
```bash
ls -la staging/atomica_staging/ | head -20
```

Files should look like:
- `1b68.cif`
- `1b68_metadata.json`
- `1b68_critical_residues.tsv`

If not, rename them:
```bash
# Example: rename metadata.json to proper format
mv metadata.json 1b68_metadata.json
```

### Issue: "Index file not found"

**Cause:** Specified index path doesn't exist

**Solution:** Create or specify correct path:
```bash
# Check if index exists
ls -la data/output/atomica_index.parquet

# If not, create initial index first
dataset index \
  --dataset-dir data/input/atomica_longevity_proteins \
  --output data/output/atomica_index.parquet
```

### Issue: Metadata resolution fails

**Cause:** Network issues or invalid PDB IDs

**Solution:** Check individual structures:
```bash
# The update command will log failures
# Look for warnings in the output about specific PDB IDs
# These can be manually resolved later
```

## Quick Reference

### Download Current Dataset from HuggingFace
```bash
python -m atomica_mcp.dataset download
```

### Just Reorganize a Folder (No Index Needed)
```bash
python -m atomica_mcp.dataset reorganize --dataset-dir data/my_folder
```

### Reorganize + Update Main Index
```bash
python -m atomica_mcp.dataset reorganize --dataset-dir staging/new_data
python -m atomica_mcp.dataset update \
  --update-dir staging/new_data \
  --dataset-dir data/input/atomica_longevity_proteins \
  --index data/output/atomica_index.parquet
```

### Upload Changes to HuggingFace
```bash
# Preview what will be uploaded
python -m atomica_mcp.upload_to_hf upload \
  --local-dir data/input/atomica_longevity_proteins \
  --dry-run

# Actually upload
python -m atomica_mcp.upload_to_hf upload \
  --local-dir data/input/atomica_longevity_proteins \
  --commit-message "Add new structures from analysis"
```

### Force Re-process Existing Structures
```bash
python -m atomica_mcp.dataset update \
  --update-dir staging/data \
  --dataset-dir data/input/atomica_longevity_proteins \
  --index data/output/atomica_index.parquet \
  --force
```

## Complete Workflow Summary

For someone migrating FOXO3/HSF1/NRF2 data:

```bash
# 1. Download current dataset
python -m atomica_mcp.dataset download

# 2. Reorganize your new data
python -m atomica_mcp.dataset reorganize --dataset-dir analysis/FOXO3

# 3. Update main index
python -m atomica_mcp.dataset update \
  --update-dir analysis/FOXO3 \
  --dataset-dir data/input/atomica_longevity_proteins \
  --index data/output/atomica_index.parquet

# 4. Copy files to main dataset
cp -r analysis/FOXO3/*/ data/input/atomica_longevity_proteins/

# 5. Upload to HuggingFace
python -m atomica_mcp.upload_to_hf upload \
  --local-dir data/input/atomica_longevity_proteins \
  --commit-message "Add FOXO3 structures from new analysis"
```

## Benefits of New Structure

✅ **Organized** - Files grouped by PDB ID  
✅ **Scalable** - Easy to add new structures  
✅ **Indexed** - Parquet index for fast queries  
✅ **Portable** - Relative paths work anywhere  
✅ **Discoverable** - Metadata embedded in index  
✅ **Consistent** - Standardized file organization  

## Next Steps

After successful migration:
1. Backup old data: `tar -czf backup_old_data.tar.gz downloads/ output/`
2. Remove staging directory: `rm -rf staging/`
3. Verify index: Use the verification script from Step 5
4. Document any manual fixes needed
