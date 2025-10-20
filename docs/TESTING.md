# Testing Guide for PDB-MCP

## Overview

The PDB-MCP project includes comprehensive test suites covering:
1. **Unit Tests** - Low-level utility functions and data loading
2. **Integration Tests** - End-to-end MCP server functionality with real data

All tests use real data sources (RCSB API, AnAge database) without mocking.

## Running Tests

### Run all tests
```bash
uv run pytest
```

### Run specific test file
```bash
# MCP Integration tests
uv run pytest tests/test_mcp_integration.py -v

# PDB Resolution tests
uv run pytest tests/test_pdb_resolution.py -v
```

### Run specific test class
```bash
uv run pytest tests/test_mcp_integration.py::TestPDBMCPFetchStructure -v
```

### Run specific test
```bash
uv run pytest tests/test_mcp_integration.py::TestPDBMCPFetchStructure::test_fetch_structure_human_protein -v
```

### Run with verbose output and short tracebacks
```bash
uv run pytest tests/test_mcp_integration.py -v --tb=short
```

## Test Structure

### Integration Tests (`test_mcp_integration.py`)

The integration test suite verifies all MCP server tools work correctly with real data:

#### Test Classes

1. **TestPDBMCPFetchStructure** (7 tests)
   - Tests the `fetch_structure` tool with real PDB IDs
   - Verifies structure metadata, resolution, titles, and entities
   - Tests with valid and invalid PDB IDs
   - Validates UniProt ID formats

2. **TestPDBMCPClassifyOrganism** (5 tests)
   - Tests organism classification against AnAge database
   - Verifies known species (Homo sapiens, Mus musculus, etc.)
   - Tests unknown species handling
   - Validates all return types

3. **TestPDBMCPGetChainInfo** (6 tests)
   - Tests chain information retrieval
   - Verifies organism classification within chain info
   - Tests multiple chains from same structure
   - Validates protein names and UniProt IDs

4. **TestPDBMCPListOrganisms** (4 tests)
   - Tests organism listing from AnAge database
   - Verifies list contains common species
   - Confirms output is sorted

5. **TestPDBMCPGetAvailableData** (5 tests)
   - Tests data availability information
   - Verifies AnAge database status
   - Checks PDB annotations availability
   - Validates server information

6. **TestPDBMCPResources** (2 tests)
   - Tests MCP resource functionality
   - Verifies schema information

7. **TestPDBMCPEndToEndWorkflows** (4 tests)
   - Complex multi-tool workflows
   - Fetches structures and classifies organisms
   - Tests chain info with organism verification
   - Tests multiple structures

8. **TestPDBMCPDataConsistency** (4 tests)
   - Verifies repeated calls return consistent data
   - Tests caching behavior
   - Validates data integrity

9. **TestPDBMCPErrorHandling** (3 tests)
   - Tests error handling for invalid inputs
   - Verifies graceful failures
   - Tests unknown organism handling

#### Key Fixtures

- **mcp_server**: Session-scoped PDBMCPServer instance with `use_tsv=False` to force RCSB API usage
- **test_pdb_ids**: Dictionary of known test PDB IDs with expected properties

### Unit Tests (`test_pdb_resolution.py`)

Covers lower-level functionality:
- AnAge data loading and queries
- Entry ID parsing
- PDB resolution via API
- Metadata structure validation
- Chain organism classification

## Running Integration Tests

The integration tests use **real data sources** and do **NOT mock methods**:

```bash
# Run all 40 integration tests
uv run pytest tests/test_mcp_integration.py -v

# Expected output: 40 passed in ~67 seconds
```

### Test Data Sources

- **RCSB PDB API**: Real structure queries via REST API
- **AnAge Database**: Real organism classification data
- **Test PDB IDs**: 
  - `2uxq` - PPAR-gamma (Human)
  - `1a3x` - HIV Protease
  - `1mbn` - Myoglobin (Horse)

## Continuous Integration

The test suite is designed to run in CI/CD pipelines with network access to:
- `https://data.rcsb.org/` - PDB data API
- RCSB API endpoints

## Test Statistics

- **Total Tests**: 61 (40 integration + 21 unit)
- **Pass Rate**: 100% (59 passed, 2 skipped)
- **Average Runtime**: ~81 seconds
- **No Mocking**: All tests use real data

## Troubleshooting

### Tests fail with "Connection refused"
- Ensure internet access to RCSB servers
- Check firewall/proxy settings

### Tests timeout
- May need to increase `timeout` parameter in fixtures
- Default timeout is 10 seconds

### AnAge data not found
- Tests will skip if AnAge data file not available
- Download: [AnAge Database](http://genomics.senescence.info/download.html)
- Place in: `data/input/anage/anage_data.txt`

## Best Practices

1. **Always use real data** - Integration tests should not mock external APIs
2. **Test error cases** - Include tests for invalid inputs and edge cases
3. **Use fixtures** - Create reusable test data with pytest fixtures
4. **Test end-to-end** - Combine multiple tools in workflow tests
5. **Verify consistency** - Test that repeated calls return consistent results

## Adding New Tests

To add integration tests for new tools:

1. Create a new test class in `test_mcp_integration.py`
2. Use the `mcp_server` fixture for server instance
3. Call real tools without mocking
4. Verify results match expected behavior
5. Include both success and error cases

Example:

```python
class TestNewToolName:
    """Tests for the new_tool tool."""
    
    def test_new_tool_success(self, mcp_server: PDBMCPServer) -> None:
        """Test successful execution with valid input."""
        result = mcp_server.new_tool("valid_input")
        
        assert result["success"] is True
        assert "expected_field" in result
    
    def test_new_tool_error(self, mcp_server: PDBMCPServer) -> None:
        """Test error handling with invalid input."""
        result = mcp_server.new_tool("invalid_input")
        
        assert result["success"] is False
        assert "error" in result
```
