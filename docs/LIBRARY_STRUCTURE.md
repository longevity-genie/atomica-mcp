# PDB-MCP Library Structure

This document describes the refactored modular structure of pdb-mcp, which separates reusable core functionality from CLI wrappers.

## Architecture Overview

### Core Module: `pdb_utils.py`

The `pdb_utils.py` module contains all reusable, library-agnostic functionality for working with PDB structures and AnAge biological annotations. This is the foundation that can be published as a standalone library.

**Key Features:**
- Pure Python functions with type hints
- No CLI-specific code
- Dependency injection for AnAge data (allowing multiple instances)
- Efficient streaming I/O for large datasets
- Memory-efficient caching (LRU)

### CLI Wrapper: `resolve_proteins.py`

This module provides Typer CLI commands that orchestrate the core `pdb_utils` functionality for command-line usage.

**Responsibilities:**
- CLI argument parsing and validation
- Logging setup and configuration
- User-facing progress reporting
- Directory resolution and path management

### Entry Point: `__main__.py`

Aggregates CLI commands from different modules and provides a unified interface.

## Core Module API

### Data Loading Functions

#### `load_anage_data(anage_file: Path) -> Dict[str, Dict[str, Any]]`
Load AnAge database from TSV file and create a lookup dictionary.

```python
from pdb_mcp import load_anage_data
from pathlib import Path

anage_data = load_anage_data(Path("anage_data.txt"))
print(anage_data["homo sapiens"])  # Scientific names are lowercase keys
```

#### `load_pdb_annotations(annotations_dir: Path, skip_taxonomy: bool = False, skip_uniprot: bool = False) -> None`
Load PDB annotation TSV files (pdb_chain_uniprot.tsv.gz, pdb_chain_taxonomy.tsv.gz) into memory.

```python
from pdb_mcp import load_pdb_annotations
from pathlib import Path

# Loads into module-level globals: PDB_UNIPROT_DATA, PDB_TAXONOMY_DATA
load_pdb_annotations(Path("pdb_annotations"))
```

### PDB Metadata Functions

#### `fetch_pdb_metadata(pdb_id: str, timeout: int = 10, retries: int = 3, use_tsv: bool = True) -> Dict[str, Any]`
Fetch PDB metadata including chains, organisms, and protein descriptions.

```python
from pdb_mcp import fetch_pdb_metadata

# Using local TSV files (faster, requires pre-loaded data)
metadata = fetch_pdb_metadata("2uxq", use_tsv=True)

# Using RCSB REST API (slower, no pre-loaded data needed)
metadata = fetch_pdb_metadata("2uxq", use_tsv=False)

print(metadata)
# {
#     "pdb_id": "2uxq",
#     "found": True,
#     "source": "TSV",  # or "API"
#     "entities": [...]
# }
```

#### `parse_entry_id(entry_id: str) -> Dict[str, str]`
Parse entry ID to extract PDB ID and chain information.

```python
from pdb_mcp import parse_entry_id

result = parse_entry_id("2uxq_2_A_B")
# {"pdb_id": "2uxq", "chain1": "A", "chain2": "B"}
```

### Chain Information Functions

#### `get_chain_protein_name(metadata: Dict, chain_id: str) -> str`
Get protein name/description for a specific chain.

```python
from pdb_mcp import get_chain_protein_name, fetch_pdb_metadata

metadata = fetch_pdb_metadata("2uxq", use_tsv=True)
protein_name = get_chain_protein_name(metadata, "A")
```

#### `get_chain_organism(metadata: Dict, chain_id: str, anage_data: Optional[Dict] = None) -> Dict[str, Any]`
Get organism information for a chain, including AnAge classification data.

```python
from pdb_mcp import get_chain_organism, fetch_pdb_metadata, load_anage_data
from pathlib import Path

anage_data = load_anage_data(Path("anage_data.txt"))
metadata = fetch_pdb_metadata("2uxq", use_tsv=True)
organism = get_chain_organism(metadata, "A", anage_data)
# {
#     "scientific_name": "Homo sapiens",
#     "taxonomy_id": 9606,
#     "classification": "Mammalia",
#     "common_name": "Human",
#     "max_longevity_yrs": 122.5,
#     "kingdom": "Animalia",
#     "phylum": "Chordata",
#     "in_anage": True
# }
```

#### `get_chain_uniprot_ids(metadata: Dict, chain_id: str) -> List[str]`
Get UniProt IDs for a chain.

```python
from pdb_mcp import get_chain_uniprot_ids

uniprot_ids = get_chain_uniprot_ids(metadata, "A")
```

### Organism Classification

#### `classify_organism(scientific_name: str, anage_data: Optional[Dict] = None) -> Dict[str, Any]`
Classify organism based on AnAge database lookup.

```python
from pdb_mcp import classify_organism, load_anage_data
from pathlib import Path

anage_data = load_anage_data(Path("anage_data.txt"))
classification = classify_organism("Homo sapiens", anage_data)
# {
#     "classification": "Mammalia",
#     "common_name": "Human",
#     "max_longevity_yrs": 122.5,
#     "kingdom": "Animalia",
#     "phylum": "Chordata",
#     "in_anage": True
# }
```

### Filtering & Searching

#### `matches_filter(result: Dict, filter_organism: Optional[str], filter_classification: Optional[str]) -> bool`
Check if a result matches organism or classification filters.

```python
from pdb_mcp import matches_filter

# Filter organisms in AnAge that match "human" (case-insensitive)
passes = matches_filter(result, filter_organism="human", filter_classification=None)

# Filter only mammals
passes = matches_filter(result, filter_organism=None, filter_classification="Mammalia")
```

#### `iter_jsonl_gz_lines(file_path: Path, line_numbers: Optional[Iterable[int]] = None) -> Iterable[Dict]`
Memory-efficient streaming of JSONL.GZ files.

```python
from pdb_mcp import iter_jsonl_gz_lines
from pathlib import Path

# Read all lines
for entry_data in iter_jsonl_gz_lines(Path("data.jsonl.gz")):
    line_num = entry_data["line_number"]
    entry = entry_data["entry"]
    process(entry)

# Read specific lines
for entry_data in iter_jsonl_gz_lines(Path("data.jsonl.gz"), line_numbers=[1, 5, 10]):
    process(entry_data["entry"])
```

### Streaming Writers

#### `StreamingJSONLWriter`
Context manager for streaming JSONL output with append support.

```python
from pdb_mcp import StreamingJSONLWriter
from pathlib import Path
import json

with StreamingJSONLWriter(Path("output.jsonl.gz"), append=False) as writer:
    for entry in entries:
        writer.write_entry(entry)
```

#### `StreamingCSVWriter`
Context manager for streaming CSV output with batched writes.

```python
from pdb_mcp import StreamingCSVWriter
from pathlib import Path

with StreamingCSVWriter(Path("output.csv"), batch_size=1000, append=False) as writer:
    for result in results:
        writer.add_result(result)
```

#### `StreamingJSONArrayWriter`
Context manager for streaming JSON array output.

```python
from pdb_mcp import StreamingJSONArrayWriter
from pathlib import Path

with StreamingJSONArrayWriter(Path("output.json")) as writer:
    for item in items:
        writer.write_item(item)
```

### Utilities

#### `LineNumberFilter`
Memory-efficient line number filter supporting ranges and single values.

```python
from pdb_mcp import LineNumberFilter

# Create filter for specific lines and ranges
filter = LineNumberFilter(ranges=[(1, 10), (100, 200)], singles={5, 15, 25})

# Check if line matches filter
if 105 in filter:
    print("Line 105 is in the filter")
```

#### `parse_line_numbers(line_numbers_str: str) -> LineNumberFilter`
Parse line numbers from string (e.g., "1-10,15,20-30").

```python
from pdb_mcp import parse_line_numbers

filter = parse_line_numbers("1-10,15,20-30")
for line_num in range(1, 100):
    if line_num in filter:
        process(line_num)
```

## Usage Examples

### Example 1: Simple Protein Resolution

```python
from pdb_mcp import (
    load_anage_data, fetch_pdb_metadata, get_chain_organism
)
from pathlib import Path

# Load data
anage_data = load_anage_data(Path("anage_data.txt"))

# Get PDB metadata
metadata = fetch_pdb_metadata("2uxq", use_tsv=False)

# Get organism info for each chain
if metadata["found"]:
    for entity in metadata["entities"]:
        for chain_id in entity["chains"]:
            organism = get_chain_organism(metadata, chain_id, anage_data)
            print(f"Chain {chain_id}: {organism['scientific_name']}")
```

### Example 2: Batch Processing with Streaming

```python
from pdb_mcp import (
    load_anage_data, load_pdb_annotations,
    iter_jsonl_gz_lines, fetch_pdb_metadata,
    get_chain_organism, StreamingCSVWriter
)
from pathlib import Path

# Load resources
anage_data = load_anage_data(Path("anage_data.txt"))
load_pdb_annotations(Path("pdb_annotations"))

# Stream processing
with StreamingCSVWriter(Path("results.csv")) as csv_writer:
    for entry_data in iter_jsonl_gz_lines(Path("data.jsonl.gz")):
        entry_id = entry_data["entry"]["id"]
        pdb_id = entry_id.split("_")[0]
        
        # Fetch metadata
        metadata = fetch_pdb_metadata(pdb_id, use_tsv=True)
        
        if metadata["found"]:
            for entity in metadata["entities"]:
                for chain_id in entity["chains"]:
                    organism = get_chain_organism(metadata, chain_id, anage_data)
                    
                    result = {
                        "entry_id": entry_id,
                        "pdb_id": pdb_id,
                        "chain_id": chain_id,
                        "organism": organism["scientific_name"],
                        "classification": organism["classification"],
                    }
                    csv_writer.add_result(result)
```

## Migration from Original Code

The refactoring maintains backward compatibility with the CLI while making the core functionality reusable:

**Before (Monolithic):**
- All code in `resolve_proteins.py`
- Global state (ANAGE_DATA, PDB_UNIPROT_DATA, etc.)
- Mixed CLI and business logic

**After (Modular):**
- Core utilities in `pdb_utils.py` (reusable library)
- CLI wrapper in `resolve_proteins.py` (uses pdb_utils)
- Clean separation of concerns
- Exportable public API via `__init__.py`

## Publishing as a Library

To publish pdb-mcp as a standalone library:

1. Create a separate repository or PyPI package
2. Move `pdb_utils.py` to the library core
3. Include supporting utilities (streaming, filtering, etc.)
4. Update `pyproject.toml` with appropriate metadata
5. Publish to PyPI: `uv publish`

The CLI tools can remain as optional extras:

```toml
[project.optional-dependencies]
cli = ["typer>=0.12.0", "fastmcp>=2.12.5"]
```

## Design Principles

1. **Separation of Concerns**: Core logic separate from CLI/UI code
2. **Type Hints**: Full type annotations for IDE support and documentation
3. **Dependency Injection**: Functions accept data parameters rather than relying solely on globals
4. **Memory Efficiency**: Streaming I/O, LRU caching, efficient data structures
5. **Composability**: Small, focused functions that can be composed for complex workflows
6. **Documentation**: Comprehensive docstrings for all public functions
