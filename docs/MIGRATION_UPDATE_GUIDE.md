# ATOMICA Dataset Migration & Update Guide

This guide explains how to migrate legacy dataset structures (with files spread across multiple folders) into the standardized ATOMICA format and update your main dataset index.

## Overview

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
│   ├── 1b68.json (or 1b68_metadata.json)
│   ├── 1b68_critical_residues.tsv
│   ├── 1b68_interact_scores.json
│   ├── 1b68_pymol_commands.pml
│   └── 1b68_summary.json
├── 6ht5/
│   ├── 6ht5.cif
│   ├── 6ht5.json
│   ├── 6ht5_critical_residues.tsv
│   ├── 6ht5_interact_scores.json
│   ├── 6ht5_pymol_commands.pml
│   └── 6ht5_summary.json
└── atomica_index.parquet
```

## Migration Steps

### Step 1: Prepare Your Old Dataset

First, consolidate all files related to each PDB into a single staging directory.

**Option A: If files are in separate folders**

Create a staging directory and copy files:
```bash
# Create staging area
mkdir -p staging/atomica_staging

# Copy structure files
cp downloads/pdbs/*.cif staging/atomica_staging/

# Copy metadata files (rename .json to _metadata.json if needed)
cp downloads/pdbs/*.json staging/atomica_staging/

# Copy analysis files
cp output/*_critical_residues.tsv staging/atomica_staging/
cp output/*_interact_scores.json staging/atomica_staging/
cp output/*_pymol_commands.pml staging/atomica_staging/
cp output/*_summary.json staging/atomica_staging/
```

**Option B: If metadata files are named differently**

Rename them to match the expected pattern:
```bash
cd staging/atomica_staging
for f in *.json; do
  # Skip if already has _metadata suffix
  if [[ ! "$f" =~ _metadata\.json$ ]]; then
    pdb_id="${f%.json}"
    mv "$f" "${pdb_id}_metadata.json"
  fi
done
```

### Step 2: Preview Reorganization (Dry Run)

Before making actual changes, do a dry run to see what will happen:

```bash
# Dry run - shows what would be reorganized
dataset reorganize \
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
# Reorganize files into per-PDB folders
dataset reorganize \
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
dataset update \
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

### Step 5 (Optional): Verify Update

Verify that the structures were properly added:

```bash
# Load and inspect the updated index
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

### Step 6 (Optional): Copy to Dataset Directory

If you want to also copy the reorganized files to the main dataset directory:

```bash
# Copy reorganized structures to main dataset
cp -r staging/atomica_staging/*/ data/input/atomica_longevity_proteins/

# Verify
ls -la data/input/atomica_longevity_proteins/ | head -20
```

## Complete Migration Script

Here's a complete bash script that performs the entire migration:

```bash
#!/bin/bash
set -e

# Configuration
OLD_CIF_DIR="downloads/pdbs"
OLD_METADATA_DIR="downloads/pdbs"
OLD_ANALYSIS_DIR="output"
STAGING_DIR="staging/atomica_staging"
MAIN_DATASET_DIR="data/input/atomica_longevity_proteins"
INDEX_FILE="data/output/atomica_index.parquet"

echo "🚀 Starting ATOMICA dataset migration..."

# Step 1: Create staging directory
echo "📁 Creating staging directory..."
mkdir -p "$STAGING_DIR"

# Step 2: Copy files
echo "📦 Copying files to staging directory..."
cp "$OLD_CIF_DIR"/*.cif "$STAGING_DIR/" 2>/dev/null || echo "⚠️  No CIF files found"
cp "$OLD_METADATA_DIR"/*.json "$STAGING_DIR/" 2>/dev/null || echo "⚠️  No metadata files found"
cp "$OLD_ANALYSIS_DIR"/*_critical_residues.tsv "$STAGING_DIR/" 2>/dev/null || echo "⚠️  No critical residues files found"
cp "$OLD_ANALYSIS_DIR"/*_interact_scores.json "$STAGING_DIR/" 2>/dev/null || echo "⚠️  No interact scores files found"
cp "$OLD_ANALYSIS_DIR"/*_pymol_commands.pml "$STAGING_DIR/" 2>/dev/null || echo "⚠️  No PyMOL commands files found"
cp "$OLD_ANALYSIS_DIR"/*_summary.json "$STAGING_DIR/" 2>/dev/null || echo "⚠️  No summary files found"

# Step 3: Rename metadata files if needed
echo "🔧 Normalizing metadata file names..."
cd "$STAGING_DIR"
for f in *.json; do
  if [[ ! "$f" =~ _metadata\.json$ ]]; then
    pdb_id="${f%.json}"
    if [[ -f "$pdb_id.cif" ]]; then
      # This is a metadata file for a CIF
      mv "$f" "${pdb_id}_metadata.json" 2>/dev/null || true
    fi
  fi
done
cd - > /dev/null

# Step 4: Dry run
echo "🔍 Running dry run to preview changes..."
dataset reorganize \
  --dataset-dir "$STAGING_DIR" \
  --dry-run

read -p "👉 Continue with reorganization? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "❌ Migration cancelled"
  exit 1
fi

# Step 5: Reorganize
echo "🔄 Reorganizing files..."
dataset reorganize \
  --dataset-dir "$STAGING_DIR"

# Step 6: Update index
echo "🔄 Updating main dataset index..."
dataset update \
  --update-dir "$STAGING_DIR" \
  --dataset-dir "$MAIN_DATASET_DIR" \
  --index "$INDEX_FILE"

# Step 7: Optional copy to main dataset
read -p "👉 Copy reorganized structures to main dataset? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo "📋 Copying to main dataset directory..."
  cp -r "$STAGING_DIR"/*/ "$MAIN_DATASET_DIR/"
  echo "✅ Files copied"
fi

echo ""
echo "✅ Migration completed successfully!"
echo "📊 Summary:"
echo "   Staging directory: $STAGING_DIR"
echo "   Main dataset: $MAIN_DATASET_DIR"
echo "   Index file: $INDEX_FILE"
```

Save as `scripts/migrate_dataset.sh` and run:
```bash
chmod +x scripts/migrate_dataset.sh
./scripts/migrate_dataset.sh
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

### Just Reorganize a Folder (No Index Update)
```bash
dataset reorganize --dataset-dir data/my_folder
```

### Reorganize + Update Main Index
```bash
dataset reorganize --dataset-dir staging/new_data
dataset update \
  --update-dir staging/new_data \
  --dataset-dir data/input/atomica_longevity_proteins \
  --index data/output/atomica_index.parquet
```

### Force Re-process Existing Structures
```bash
dataset update \
  --update-dir staging/data \
  --dataset-dir data/input/atomica_longevity_proteins \
  --index data/output/atomica_index.parquet \
  --force
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
