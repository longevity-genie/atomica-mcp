# Flexible API: Reducing Global State

## Overview

All core functions in `pdb_utils` now accept **optional parameters** for data sources, falling back to globals only if not provided. This design gives you maximum flexibility while maintaining backward compatibility.

## Design Philosophy

```
┌─────────────────────────────────────────────────────┐
│ Your Code                                           │
├─────────────────────────────────────────────────────┤
│ Pass custom data? ──→ Use your data                 │
│        ↓NO                                          │
│ Use global defaults (if pre-loaded)                 │
│        ↓NO                                          │
│ Return error or fetch from API                      │
└─────────────────────────────────────────────────────┘
```

**Benefits:**
- ✅ No required global state
- ✅ Complete control over data sources
- ✅ Easy to test (pass mock data)
- ✅ Thread-safe (no shared globals)
- ✅ Works with multiple AnAge datasets
- ✅ 100% backward compatible

## Functions with Flexible Parameters

### 1. `get_organism_from_tsv()`

**Signature:**
```python
def get_organism_from_tsv(
    pdb_id: str,
    chain_id: str,
    pdb_taxonomy_data: Optional[pl.DataFrame] = None,  # ← NEW!
    anage_data: Optional[Dict[str, Dict[str, Any]]] = None  # ← NEW!
) -> Dict[str, Any]:
```

**Usage:**

Option A: Use globals (pre-loaded with `load_pdb_annotations()`)
```python
from pdb_mcp import load_pdb_annotations, get_organism_from_tsv
from pathlib import Path

load_pdb_annotations(Path("pdb_annotations"))

# Uses globals automatically
organism = get_organism_from_tsv("2uxq", "A")
```

Option B: Pass custom data
```python
import polars as pl
from pdb_mcp import get_organism_from_tsv

# Load your own data
my_taxonomy = pl.read_csv("custom_taxonomy.tsv.gz", separator="\t")
my_anage = {...}

# Use your data, not globals
organism = get_organism_from_tsv("2uxq", "A", my_taxonomy, my_anage)
```

Option C: Mix and match
```python
from pdb_mcp import get_organism_from_tsv, load_anage_data
from pathlib import Path

# Use global taxonomy (pre-loaded), custom AnAge
custom_anage = load_anage_data(Path("custom_anage.txt"))
organism = get_organism_from_tsv("2uxq", "A", anage_data=custom_anage)
```

### 2. `get_uniprot_ids_from_tsv()`

**Signature:**
```python
def get_uniprot_ids_from_tsv(
    pdb_id: str,
    chain_id: str,
    pdb_uniprot_data: Optional[pl.DataFrame] = None  # ← NEW!
) -> List[str]:
```

**Usage:**

```python
from pdb_mcp import get_uniprot_ids_from_tsv, load_pdb_annotations

# Option A: Use globals
load_pdb_annotations(Path("pdb_annotations"))
ids = get_uniprot_ids_from_tsv("2uxq", "A")

# Option B: Pass custom data
import polars as pl
custom_uniprot = pl.read_csv("my_uniprot_map.tsv.gz", separator="\t")
ids = get_uniprot_ids_from_tsv("2uxq", "A", custom_uniprot)
```

### 3. `fetch_pdb_metadata()`

**Signature:**
```python
def fetch_pdb_metadata(
    pdb_id: str,
    timeout: int = 10,
    retries: int = 3,
    use_tsv: bool = True,
    pdb_uniprot_data: Optional[pl.DataFrame] = None,  # ← NEW!
    pdb_taxonomy_data: Optional[pl.DataFrame] = None   # ← NEW!
) -> Dict[str, Any]:
```

**Usage:**

```python
from pdb_mcp import fetch_pdb_metadata, load_pdb_annotations
from pathlib import Path

# Option A: Globals (fastest)
load_pdb_annotations(Path("pdb_annotations"))
metadata = fetch_pdb_metadata("2uxq", use_tsv=True)

# Option B: Custom data
import polars as pl
my_uniprot = pl.read_csv(...)
my_taxonomy = pl.read_csv(...)

metadata = fetch_pdb_metadata(
    "2uxq",
    use_tsv=True,
    pdb_uniprot_data=my_uniprot,
    pdb_taxonomy_data=my_taxonomy
)

# Option C: API fallback (no TSV data needed)
metadata = fetch_pdb_metadata("2uxq", use_tsv=False)
```

## Real-World Examples

### Example 1: Testing Without Globals

```python
import polars as pl
from pdb_mcp import get_organism_from_tsv

# Create minimal test data (no globals needed!)
test_taxonomy = pl.DataFrame({
    "PDB": ["2uxq"],
    "CHAIN": ["A"],
    "SCIENTIFIC_NAME": ["Homo sapiens"],
    "TAX_ID": [9606],
})

test_anage = {
    "homo sapiens": {
        "scientific_name": "Homo sapiens",
        "common_name": "Human",
        "class": "Mammalia",
    }
}

# Test function
organism = get_organism_from_tsv("2uxq", "A", test_taxonomy, test_anage)
assert organism["scientific_name"] == "Homo sapiens"
print("✓ Test passed!")
```

### Example 2: Working with Multiple AnAge Datasets

```python
from pdb_mcp import (
    load_anage_data,
    fetch_pdb_metadata,
    get_chain_organism
)
from pathlib import Path

# Load two different AnAge versions
anage_v1 = load_anage_data(Path("anage_v1.txt"))
anage_v2 = load_anage_data(Path("anage_v2.txt"))

# Compare same structure with different annotations
metadata = fetch_pdb_metadata("2uxq", use_tsv=False)

print("With AnAge v1:")
org1 = get_chain_organism(metadata, "A", anage_v1)
print(f"  {org1['scientific_name']} ({org1['classification']})")

print("With AnAge v2:")
org2 = get_chain_organism(metadata, "A", anage_v2)
print(f"  {org2['scientific_name']} ({org2['classification']})")
```

### Example 3: Stream Processing with Custom Data

```python
from pdb_mcp import (
    iter_jsonl_gz_lines,
    fetch_pdb_metadata,
    get_chain_organism,
    StreamingCSVWriter,
)
import polars as pl

# Load custom PDB annotations once (not into globals)
my_uniprot = pl.read_csv("my_uniprot.tsv.gz", separator="\t")
my_taxonomy = pl.read_csv("my_taxonomy.tsv.gz", separator="\t")
my_anage = {...}  # Custom AnAge data

# Stream process large file with YOUR data
with StreamingCSVWriter("results.csv") as writer:
    for entry_data in iter_jsonl_gz_lines("data.jsonl.gz"):
        pdb_id = entry_data["entry"]["id"].split("_")[0]
        
        # Pass YOUR data, not globals
        metadata = fetch_pdb_metadata(
            pdb_id,
            use_tsv=True,
            pdb_uniprot_data=my_uniprot,
            pdb_taxonomy_data=my_taxonomy
        )
        
        if metadata["found"]:
            for entity in metadata["entities"]:
                for chain_id in entity["chains"]:
                    # Use YOUR AnAge data
                    organism = get_chain_organism(
                        metadata,
                        chain_id,
                        my_anage
                    )
                    writer.add_result({
                        "pdb_id": pdb_id,
                        "chain": chain_id,
                        "organism": organism["scientific_name"],
                    })
```

### Example 4: Microservice with Isolated Data

```python
from pdb_mcp import fetch_pdb_metadata, get_chain_organism
import polars as pl

class ProteinResolver:
    """Microservice-friendly resolver - no shared globals!"""
    
    def __init__(self, uniprot_file: str, taxonomy_file: str, anage_data: dict):
        """Initialize with isolated data (thread-safe!)"""
        self.uniprot_data = pl.read_csv(uniprot_file, separator="\t")
        self.taxonomy_data = pl.read_csv(taxonomy_file, separator="\t")
        self.anage_data = anage_data
    
    def resolve_structure(self, pdb_id: str) -> dict:
        """Resolve protein structure using isolated data"""
        metadata = fetch_pdb_metadata(
            pdb_id,
            use_tsv=True,
            pdb_uniprot_data=self.uniprot_data,
            pdb_taxonomy_data=self.taxonomy_data
        )
        
        results = []
        if metadata["found"]:
            for entity in metadata["entities"]:
                for chain_id in entity["chains"]:
                    organism = get_chain_organism(
                        metadata,
                        chain_id,
                        self.anage_data
                    )
                    results.append({
                        "chain": chain_id,
                        "organism": organism["scientific_name"],
                        "classification": organism["classification"],
                    })
        
        return {"pdb_id": pdb_id, "chains": results}

# Usage - each instance has isolated data
resolver1 = ProteinResolver("uniprot1.tsv.gz", "tax1.tsv.gz", anage1)
resolver2 = ProteinResolver("uniprot2.tsv.gz", "tax2.tsv.gz", anage2)

# Thread-safe, no global state conflicts
result1 = resolver1.resolve_structure("2uxq")
result2 = resolver2.resolve_structure("2uxq")
```

## When to Use Each Approach

| Approach | When to Use | Example |
|----------|------------|---------|
| **No parameters** | Simple scripts, CLI usage | `get_organism_from_tsv("2uxq", "A")` |
| **Pass data** | Testing, multiple datasets | `get_organism_from_tsv("2uxq", "A", my_data)` |
| **Mix** | Partial overrides | `get_organism_from_tsv("2uxq", "A", anage_data=custom_anage)` |

## API Backward Compatibility

All changes are **100% backward compatible**:

```python
# Old code still works (uses globals)
from pdb_mcp import load_pdb_annotations, get_organism_from_tsv

load_pdb_annotations(Path("annotations"))
org = get_organism_from_tsv("2uxq", "A")  # Uses globals automatically
```

The optional parameters are completely optional with sensible defaults.

## Summary

This flexible API design:
- ✅ Eliminates global state dependencies
- ✅ Makes code testable and composable
- ✅ Supports multiple data sources
- ✅ Thread-safe for microservices
- ✅ Maintains backward compatibility
- ✅ Scales from scripts to production systems
