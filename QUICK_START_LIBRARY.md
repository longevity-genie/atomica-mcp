# PDB-MCP Quick Start (Library Usage)

This guide shows how to use pdb-mcp as a reusable Python library for protein structure and biological annotation work.

## Installation

```bash
# Clone the repository
git clone https://github.com/user/pdb-mcp.git
cd pdb-mcp

# Install in development mode
uv sync
uv pip install -e .

# Or install directly
uv pip install pdb-mcp
```

## Basic Example: Get Protein Information

```python
from pdb_mcp import (
    load_anage_data,
    fetch_pdb_metadata,
    get_chain_organism,
    get_chain_protein_name,
    get_chain_uniprot_ids,
)
from pathlib import Path

# Load AnAge database (organism classifications)
anage_data = load_anage_data(Path("data/input/anage/anage_data.txt"))

# Fetch PDB metadata (using RCSB API, no local files needed)
metadata = fetch_pdb_metadata("2uxq", use_tsv=False)

# Process each chain in the structure
if metadata["found"]:
    print(f"PDB ID: {metadata['pdb_id']}")
    
    for entity in metadata["entities"]:
        for chain_id in entity["chains"]:
            protein_name = get_chain_protein_name(metadata, chain_id)
            organism = get_chain_organism(metadata, chain_id, anage_data)
            uniprot_ids = get_chain_uniprot_ids(metadata, chain_id)
            
            print(f"\nChain {chain_id}:")
            print(f"  Protein: {protein_name}")
            print(f"  Organism: {organism['scientific_name']}")
            print(f"  Classification: {organism['classification']}")
            print(f"  UniProt IDs: {uniprot_ids}")
```

## Example: Batch Process PDB Structures

```python
from pdb_mcp import (
    load_anage_data,
    fetch_pdb_metadata,
    get_chain_organism,
    iter_jsonl_gz_lines,
    StreamingCSVWriter,
)
from pathlib import Path
from collections import defaultdict

# Setup
anage_data = load_anage_data(Path("anage_data.txt"))
pdb_ids = ["2uxq", "1mbn", "3hfm"]  # List of PDB IDs

# Write results to CSV
with StreamingCSVWriter(Path("results.csv")) as csv_writer:
    for pdb_id in pdb_ids:
        metadata = fetch_pdb_metadata(pdb_id, use_tsv=False)
        
        if not metadata["found"]:
            print(f"⚠ {pdb_id} not found")
            continue
        
        # Process each chain
        for entity in metadata["entities"]:
            for chain_id in entity["chains"]:
                organism = get_chain_organism(metadata, chain_id, anage_data)
                
                result = {
                    "pdb_id": pdb_id,
                    "chain_id": chain_id,
                    "organism": organism["scientific_name"],
                    "classification": organism["classification"],
                    "in_anage": organism["in_anage"],
                }
                csv_writer.add_result(result)

print("✓ Results written to results.csv")
```

## Example: Use Local PDB Annotations (Faster)

```python
from pdb_mcp import (
    load_anage_data,
    load_pdb_annotations,
    fetch_pdb_metadata,
    get_chain_organism,
)
from pathlib import Path

# Pre-load PDB annotations (requires download)
load_pdb_annotations(Path("data/input/pdb"))

# Load AnAge database
anage_data = load_anage_data(Path("data/input/anage/anage_data.txt"))

# Now fetch_pdb_metadata uses local TSV files (much faster!)
metadata = fetch_pdb_metadata("2uxq", use_tsv=True)

if metadata["found"]:
    print(f"Source: {metadata.get('source')}")  # "TSV" instead of "API"
    
    for entity in metadata["entities"]:
        for chain_id in entity["chains"]:
            organism = get_chain_organism(metadata, chain_id, anage_data)
            print(f"Chain {chain_id}: {organism['scientific_name']}")
```

## Example: Filter by Organism Type

```python
from pdb_mcp import (
    load_anage_data,
    fetch_pdb_metadata,
    get_chain_organism,
    classify_organism,
)
from pathlib import Path

anage_data = load_anage_data(Path("anage_data.txt"))

# Find only mammalian proteins
pdb_ids = ["2uxq", "1mbn", "3hfm", "1pdb"]

for pdb_id in pdb_ids:
    metadata = fetch_pdb_metadata(pdb_id, use_tsv=False)
    
    if not metadata["found"]:
        continue
    
    for entity in metadata["entities"]:
        for chain_id in entity["chains"]:
            organism = get_chain_organism(metadata, chain_id, anage_data)
            
            # Filter: only keep mammals
            if organism.get("classification") == "Mammalia":
                print(f"{pdb_id} chain {chain_id}: {organism['scientific_name']}")
```

## Example: Stream Large JSONL Files

```python
from pdb_mcp import (
    iter_jsonl_gz_lines,
    load_anage_data,
    load_pdb_annotations,
    fetch_pdb_metadata,
    get_chain_organism,
    StreamingCSVWriter,
    parse_entry_id,
)
from pathlib import Path

# Setup
anage_data = load_anage_data(Path("anage_data.txt"))
load_pdb_annotations(Path("pdb_annotations"))

# Stream process large file (memory efficient)
with StreamingCSVWriter(Path("large_output.csv"), batch_size=500) as csv_writer:
    for entry_data in iter_jsonl_gz_lines(Path("large_pdb_file.jsonl.gz")):
        line_num = entry_data["line_number"]
        entry = entry_data["entry"]
        
        # Parse entry ID
        parsed = parse_entry_id(entry["id"])
        pdb_id = parsed["pdb_id"]
        
        # Fetch metadata
        metadata = fetch_pdb_metadata(pdb_id, use_tsv=True)
        
        if metadata["found"]:
            for chain_id in [parsed["chain1"], parsed["chain2"]]:
                if not chain_id:
                    continue
                
                organism = get_chain_organism(metadata, chain_id, anage_data)
                
                result = {
                    "line_number": line_num,
                    "pdb_id": pdb_id,
                    "chain_id": chain_id,
                    "organism": organism["scientific_name"],
                    "in_anage": organism["in_anage"],
                }
                csv_writer.add_result(result)
        
        # Progress indicator
        if line_num % 1000 == 0:
            print(f"✓ Processed {line_num} lines")

print("✓ Done!")
```

## Common Patterns

### Pattern 1: Check if Organism is in AnAge

```python
from pdb_mcp import classify_organism, load_anage_data
from pathlib import Path

anage_data = load_anage_data(Path("anage_data.txt"))

organism_info = classify_organism("Homo sapiens", anage_data)
if organism_info["in_anage"]:
    print(f"Classification: {organism_info['classification']}")
    print(f"Max longevity: {organism_info['max_longevity_yrs']} years")
else:
    print("Not in AnAge database")
```

### Pattern 2: Process Specific Lines

```python
from pdb_mcp import iter_jsonl_gz_lines, parse_line_numbers
from pathlib import Path

# Process only lines 1-100 and line 500
line_filter = parse_line_numbers("1-100,500")

for entry_data in iter_jsonl_gz_lines(Path("data.jsonl.gz"), line_numbers=line_filter):
    process(entry_data["entry"])
```

### Pattern 3: Resume Processing

```python
from pdb_mcp import (
    get_last_processed_line,
    iter_jsonl_gz_lines,
    StreamingCSVWriter,
)
from pathlib import Path

output_file = Path("results.csv")

# Find where we left off
last_line = get_last_processed_line(output_file)

if last_line > 0:
    print(f"Resuming from line {last_line}")

# Continue processing
with StreamingCSVWriter(output_file, append=True) as csv_writer:
    for entry_data in iter_jsonl_gz_lines(Path("data.jsonl.gz")):
        if entry_data["line_number"] <= last_line:
            continue
        
        # Process entry
        csv_writer.add_result(result)
```

## API Reference

See `LIBRARY_STRUCTURE.md` for comprehensive API documentation and examples.

## Available Data

### AnAge Database
- **Location**: `data/input/anage/anage_data.txt`
- **Content**: Organism classification (Kingdom, Phylum, Class) and longevity data
- **Download**: Included in repository

### PDB Annotations
- **Location**: `data/input/pdb/*.tsv.gz`
- **Files**:
  - `pdb_chain_uniprot.tsv.gz`: PDB chains to UniProt IDs
  - `pdb_chain_taxonomy.tsv.gz`: PDB chains to taxonomy information
- **Download**: Run `python -m pdb_mcp download` or use `download_pdb_annotations.py`

## Performance Tips

1. **Use local TSV files** when processing many structures (`use_tsv=True`)
2. **Pre-load annotations** with `load_pdb_annotations()` before bulk processing
3. **Use streaming writers** for large output files to minimize memory usage
4. **Batch CSV writes** with larger `batch_size` for faster writing
5. **Cache metadata** if you need to access the same PDB ID multiple times

## Troubleshooting

### "TSV data not loaded" error
```python
# Make sure to load annotations before using use_tsv=True
from pdb_mcp import load_pdb_annotations
from pathlib import Path

load_pdb_annotations(Path("data/input/pdb"))
```

### "AnAge file not found" error
```python
# Use absolute paths when possible
from pathlib import Path
from pdb_mcp import load_anage_data

anage_file = Path("/full/path/to/anage_data.txt")
anage_data = load_anage_data(anage_file)
```

### Slow performance with API mode
```python
# Switch to TSV mode (faster)
# But requires: load_pdb_annotations(Path("pdb_annotations"))
metadata = fetch_pdb_metadata("2uxq", use_tsv=True)
```

## Next Steps

- Read `LIBRARY_STRUCTURE.md` for full API documentation
- Check `RESOLVE_PROTEINS_USAGE.md` for CLI usage
- View example scripts in the repository
- Run tests: `uv run pytest`
