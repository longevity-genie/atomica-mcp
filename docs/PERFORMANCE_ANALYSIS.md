# Performance Analysis: get_structures_for_uniprot

## Issue Summary

The `get_structures_for_uniprot("Q14145")` call takes **~163 seconds (2:43 minutes)** to complete. This can appear frozen in Cursor/Claude Desktop with no progress feedback.

## Root Causes

### 1. **High Number of API Calls** ⚠️ MAIN ISSUE

For Q14145 (KEAP1), the function processes **105 PDB structures**. For each structure, it makes:

1. **get_pdb_structure_metadata()**: 1 API call to PDBe per structure
2. **get_pdb_redo_info()**: 1 API call to PDB-REDO per structure  
3. **get_complex_info()**: 1-2 API calls per structure

**Total**: ~315-420 API calls for 105 structures!

### 2. **Sequential Processing**

The code processes structures one-by-one in a for loop:

```python
for pdb_id in pdb_ids:  # 105 iterations
    metadata = get_pdb_structure_metadata(pdb_id)  # ~30 second timeout
    redo_available, redo_rfree = get_pdb_redo_info(pdb_id)  # ~30 second timeout
    complex_info = get_complex_info(pdb_id, uniprot_id)  # ~30-60 second timeout
```

Each structure takes ~1.5 seconds on average = 105 * 1.5s = **~157 seconds**

### 3. **Retry Logic with Exponential Backoff**

The code uses tenacity retry decorator:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
)
```

**Worst case per request**: 
- 1st attempt: fails immediately
- 2nd attempt: waits 2 seconds, then fails
- 3rd attempt: waits 4 seconds, then fails
- **Total**: ~6 seconds per failed request

If just 10% of requests fail and retry, that adds ~30+ seconds.

### 4. **No Progress Feedback**

The function doesn't emit progress updates, so users can't tell:
- How many structures are being processed
- What the current progress is
- Whether it's actually working or frozen

### 5. **HTTP Request Timeouts**

Each HTTP request has a 30-second timeout:

```python
def _make_request_with_error_handling(url: str, timeout: int = 30)
```

If APIs are slow or overloaded, requests can take close to 30 seconds each.

## What Can Go Wrong

### 1. ⏱️ **Timeout in Cursor** (Most Likely)

Your config has:
- Global `MCP_TIMEOUT`: 300000ms (5000 minutes) ✅ Good
- Global `MCP_TOOL_TIMEOUT`: 300000ms (5000 minutes) ✅ Good
- atomica-mcp `MCP_TIMEOUT`: 600s (10 minutes) ✅ Good

**But**: This timeout controls API requests inside the function, not the MCP tool timeout itself!

The actual MCP tool execution might have a default timeout in Cursor that's shorter than 163 seconds.

### 2. 🌐 **External API Failures**

If PDBe or PDB-REDO APIs are down/slow:
- Requests will retry 3 times with exponential backoff
- Each failed structure can take 30-90 seconds
- 105 structures * potential failures = very long execution time

### 3. 🔌 **Network Issues**

- DNS resolution failures
- Firewall blocking requests
- SSL certificate issues (we saw SSL errors in the 1zgk metadata)
- Rate limiting by external APIs

### 4. 🧊 **Cursor Freezing/Killing the Process**

Cursor might:
- Kill processes that run too long without feedback
- Assume the MCP server is frozen
- Have internal timeouts not configurable via JSON

### 5. 💾 **Memory Issues**

Processing 105 structures builds large data structures in memory:
- Each StructureInfo object with metadata
- JSON serialization of all data
- If memory is limited, swapping could slow things down

## Solutions & Workarounds

### Immediate Fixes

#### 1. **Add Progress Logging** (Recommended)

Modify `get_structures_for_uniprot` to log progress:

```python
for i, pdb_id in enumerate(pdb_ids, 1):
    action.log(message_type="processing_structure", 
               current=i, 
               total=len(pdb_ids), 
               pdb_id=pdb_id,
               progress_percent=round(i/len(pdb_ids)*100, 1))
    # ... rest of processing
```

#### 2. **Add Caching** (High Impact)

Cache API responses to avoid repeated calls:

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_pdb_structure_metadata_cached(pdb_id: str):
    return get_pdb_structure_metadata(pdb_id)
```

#### 3. **Parallel Processing** (High Impact)

Use concurrent.futures to process structures in parallel:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_structure(pdb_id, uniprot_id, gene_symbol):
    # All the processing for one structure
    ...

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(process_structure, pdb, uniprot_id, gene_symbol) 
               for pdb in pdb_ids]
    
    for future in as_completed(futures):
        structures.append(future.result())
```

This could reduce time from 163s to ~20-30s!

#### 4. **Limit Results by Default**

Add a reasonable default limit:

```python
def get_structures_for_uniprot(
    uniprot_id: str, 
    include_alphafold: bool = True,
    max_structures: int = 20  # Add default limit
) -> List[StructureInfo]:
    ...
    if max_structures:
        pdb_ids = pdb_ids[:max_structures]
```

#### 5. **Reduce Timeout Values**

Lower individual request timeouts from 30s to 10s:

```python
def _make_request_with_error_handling(url: str, timeout: int = 10)
```

### Long-term Solutions

1. **Build a Local Cache Database** (SQLite or Parquet)
   - Cache all PDB metadata locally
   - Update periodically
   - Instant lookups instead of API calls

2. **Implement Streaming Results**
   - Return structures as they're processed
   - Use async/await for better responsiveness

3. **Add Rate Limiting**
   - Respect API rate limits
   - Use backpressure to avoid overwhelming APIs

4. **Create Bulk Query API**
   - Allow querying multiple structures at once
   - Batch API calls where possible

## Testing Your Configuration

Your current config is good, but to verify it won't timeout:

```bash
# Test with timer
cd /home/antonkulaga/sources/atomica-mcp
time uv run pytest tests/test_get_structures_for_uniprot.py::test_get_structures_for_uniprot_q14145 -v

# Should complete in ~163 seconds
```

## Recommended Configuration Updates

Your config is already optimal for Cursor. The issue is in the implementation, not the config:

```json
{
  "mcpServers": {
    "atomica-mcp": {
      "command": "uvx",
      "args": ["atomica-mcp@latest"],
      "env": {
        "MCP_TRANSPORT": "stdio",
        "MCP_TIMEOUT": "600",
        "ATOMICA_DATASET_DIR": "/home/antonkulaga/sources/atomica-mcp/data/input/atomica_longevity_proteins"
      }
    }
  }
}
```

✅ **This config is correct** - The slowness is due to the function making 300+ sequential API calls.

## Priority Fixes (Ranked by Impact)

1. **Implement Parallel Processing** - Will reduce time by 80-90%
2. **Add Response Caching** - Will make subsequent calls instant
3. **Add Progress Logging** - Will prevent "frozen" appearance
4. **Add Default Limit (20 structures)** - Will make typical queries fast
5. **Reduce Individual Timeouts** - Will fail faster on problematic APIs

## Conclusion

The configuration is fine. The problem is the implementation makes hundreds of sequential API calls with no caching or parallelization. Even with your generous 600-second timeout, users will think it's frozen because there's no progress feedback.

**Best immediate fix**: Add a `max_structures` parameter with default=20 to limit results for typical queries.

