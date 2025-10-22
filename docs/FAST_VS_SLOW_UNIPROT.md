# Function Comparison: Fast vs Slow UniProt Queries

## The Problem

There are **TWO different functions** for querying by UniProt ID with very different performance characteristics:

### 1. `atomica_search_by_uniprot` (FAST ⚡)
**Purpose**: Search ATOMICA dataset only  
**Speed**: < 1 second (Polars filter on local index)  
**Data**: Only structures in ATOMICA dataset (94 structures)  
**Returns**: ATOMICA-specific data (scores, critical residues, PyMOL commands)

```python
# Implementation
results = self.index.filter(
    pl.col("uniprot_ids").list.contains(uniprot_id)
)
```

**Returns for Q14145**:
- ~47 KEAP1 structures from ATOMICA dataset
- Includes paths to:
  - `interact_scores_path` ✅
  - `critical_residues_path` ✅
  - `pymol_path` ✅

### 2. `atomica_get_structures_for_uniprot` (SLOW 🐌)
**Purpose**: Get ALL PDB structures for a UniProt (from PDB API)  
**Speed**: 163 seconds for Q14145 (105 structures × ~1.5s each)  
**Data**: All PDB structures, not just ATOMICA dataset  
**Returns**: General PDB metadata (resolution, method, date), NO ATOMICA scores

```python
# Implementation
structures = get_structures_for_uniprot(uniprot_id, include_alphafold=True)
# Makes 300+ sequential API calls to PDBe, PDB-REDO, etc.
```

**Returns for Q14145**:
- 105 KEAP1 structures from entire PDB
- Includes:
  - Resolution, method, deposition date ✅
  - Complex information ✅
  - NO ATOMICA scores ❌
  - NO critical residues ❌
  - NO PyMOL commands ❌

## The Issue

When a user asks: **"I want the atomica scores of Q14145"**

The AI might call the WRONG function:
- ❌ Calls `atomica_get_structures_for_uniprot` → Takes 163s, returns NO ATOMICA scores
- ✅ Should call `atomica_search_by_uniprot` → Takes <1s, returns ATOMICA scores

## Solution

### Fix the Function Descriptions

Make it clearer which function to use:

#### Current Description (Confusing):
```python
self.tool(
    name="atomica_search_by_uniprot",
    description="Search for structures by UniProt ID(s). Direct lookup in index, fast. Example: atomica_search_by_uniprot('Q14145')"
)

self.tool(
    name="atomica_get_structures_for_uniprot",
    description="Get all PDB structures for a UniProt ID with resolution, method, dates. Includes AlphaFold if available. Example: atomica_get_structures_for_uniprot('P04637')"
)
```

#### Better Description:
```python
self.tool(
    name="atomica_search_by_uniprot",
    description="Search ATOMICA dataset by UniProt ID. Returns structures WITH ATOMICA scores, critical residues, and PyMOL commands. FAST (instant). Use this for ATOMICA analysis. Example: atomica_search_by_uniprot('Q14145')"
)

self.tool(
    name="atomica_get_structures_for_uniprot",
    description="Get ALL PDB structures for a UniProt ID from entire PDB (not just ATOMICA dataset). Returns resolution, method, dates, complex info, but NO ATOMICA scores. SLOW (may take minutes for proteins with many structures). Use only when you need comprehensive PDB coverage beyond ATOMICA dataset. Example: atomica_get_structures_for_uniprot('P04637')"
)
```

### Add Warning in Slow Function

Add a check that warns if the UniProt is in the dataset:

```python
def get_structures_for_uniprot(self, uniprot_id: str, include_alphafold: bool = True, max_structures: Optional[int] = None) -> Dict[str, Any]:
    """..."""
    with start_action(action_type="get_structures_for_uniprot", uniprot_id=uniprot_id) as action:
        # Check if UniProt is in ATOMICA dataset
        if self.dataset_available and self.index is not None:
            if "uniprot_ids" in self.index.columns:
                dataset_results = self.index.filter(
                    pl.col("uniprot_ids").list.contains(uniprot_id)
                )
                if len(dataset_results) > 0:
                    action.log(
                        message_type="uniprot_in_dataset_warning",
                        uniprot_id=uniprot_id,
                        dataset_count=len(dataset_results),
                        warning="This UniProt is in ATOMICA dataset. Consider using atomica_search_by_uniprot for faster results with ATOMICA scores."
                    )
        
        try:
            structures = get_structures_for_uniprot(uniprot_id, include_alphafold=include_alphafold)
            # ... rest of implementation
```

### Add max_structures Default

Limit the slow function by default:

```python
def get_structures_for_uniprot(
    self, 
    uniprot_id: str, 
    include_alphafold: bool = True, 
    max_structures: Optional[int] = 20  # ADD DEFAULT LIMIT
) -> Dict[str, Any]:
```

## Performance Comparison

| Operation | `search_by_uniprot` | `get_structures_for_uniprot` |
|-----------|---------------------|------------------------------|
| **Q14145 (KEAP1)** | <1s | 163s |
| **P04637 (TP53)** | <1s (if in dataset) | ~300-600s (many structures) |
| **Invalid ID** | <1s (empty result) | 30-60s (timeout) |
| **Returns ATOMICA scores** | ✅ Yes | ❌ No |
| **Returns critical residues** | ✅ Yes | ❌ No |
| **Returns PyMOL commands** | ✅ Yes | ❌ No |
| **Requires internet** | ❌ No (local) | ✅ Yes (API calls) |
| **Can fail due to network** | ❌ No | ✅ Yes |

## Test Both Functions

Let's verify the fast path works:

```bash
# Test the FAST function (should be instant)
uv run python -c "
from atomica_mcp.server import ATOMICAServer
import time

server = ATOMICAServer()
start = time.time()
result = server.search_by_uniprot('Q14145')
elapsed = time.time() - start

print(f'Fast function took: {elapsed:.3f}s')
print(f'Found {result.get(\"count\", 0)} structures')
print(f'Has ATOMICA paths: {\"interact_scores_path\" in str(result)}')
"
```

Expected output:
```
Fast function took: 0.015s
Found 47 structures
Has ATOMICA paths: True
```

## Recommendation

1. **Update tool descriptions** to make it crystal clear which function does what
2. **Add default limit** of 20 to `get_structures_for_uniprot`
3. **Add warning** when calling the slow function for a UniProt that's in the dataset
4. **Document** the difference prominently in README

## For Your Use Case

When asking for **"ATOMICA scores of Q14145"**, Cursor should call:
- ✅ `atomica_search_by_uniprot("Q14145")` → Instant, includes ATOMICA scores
- ❌ NOT `atomica_get_structures_for_uniprot("Q14145")` → 163s, NO ATOMICA scores

The confusion comes from poor function naming/descriptions making it unclear to the AI which function to use.

