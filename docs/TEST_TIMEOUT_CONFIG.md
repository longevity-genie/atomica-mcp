# Test Timeout Configuration

## Overview

The ATOMICA MCP server tests are configured with timeouts to prevent tests from hanging indefinitely, especially when making external API calls or downloading datasets.

## Configuration

### pytest.ini

```ini
[pytest]
addopts = 
    --timeout=300          # Global timeout: 5 minutes
    --timeout-method=thread # Use thread-based timeout
timeout = 300              # Explicit timeout setting
```

### pyproject.toml

Added `pytest-timeout>=2.3.1` to dev dependencies:

```toml
[dependency-groups]
dev = [
    "pytest-timeout>=2.3.1",
    ...
]
```

## Timeout Levels

### 1. Global Timeout (300 seconds)
- Applied to all tests by default
- Set in `pytest.ini`
- Prevents any test from running longer than 5 minutes

### 2. Module-Level Timeout (300 seconds)
In `tests/test_mcp_server.py`:
```python
pytestmark = pytest.mark.timeout(300)
```

### 3. Individual Test Timeouts
Specific tests have custom timeouts based on expected duration:

- **`test_resolve_pdb`**: 60 seconds
  - Makes API calls to PDBe and UniProt
  - Usually completes in 5-10 seconds
  
- **`test_get_structures_for_uniprot`**: 120 seconds
  - Queries multiple APIs for structure lists
  - May take longer due to multiple requests

## Why Timeouts Are Important

### 1. External API Dependencies
- PDBe API: Can be slow or timeout
- UniProt API: May have rate limiting
- Hugging Face Hub: Dataset downloads can take time

### 2. Network Issues
- Tests can hang indefinitely if network is down
- Timeouts ensure tests fail fast rather than block CI/CD

### 3. Resource Constraints
- GitHub Actions and CI systems have time limits
- Helps identify performance regressions

## Overriding Timeouts

### Command Line
```bash
# Custom timeout (10 minutes)
uv run pytest --timeout=600

# Disable timeout for debugging
uv run pytest --timeout=0

# Timeout specific test suite
uv run pytest tests/test_mcp_server.py --timeout=120
```

### Environment Variable
```bash
export PYTEST_TIMEOUT=600
uv run pytest
```

### Per-Test Decorator
```python
@pytest.mark.timeout(60)
def test_fast_operation():
    pass

@pytest.mark.timeout(300)
def test_slow_operation():
    pass
```

## Debugging Timeouts

### If a test times out:

1. **Check network connectivity**
   ```bash
   curl https://www.ebi.ac.uk/pdbe/api/pdb/entry/summary/1tup
   ```

2. **Run with verbose output**
   ```bash
   uv run pytest -v -s tests/test_mcp_server.py::test_resolve_pdb
   ```

3. **Disable timeout temporarily**
   ```bash
   uv run pytest --timeout=0 tests/test_mcp_server.py::test_resolve_pdb
   ```

4. **Check logs**
   - Eliot logs in `logs/` directory
   - Pytest output with `-v` flag

5. **Mock external APIs** (if needed)
   - Use `pytest-mock` or `responses` library
   - Mock PDBe and UniProt API calls

## Best Practices

### 1. Set Reasonable Timeouts
- Fast unit tests: 5-10 seconds
- API integration tests: 30-60 seconds
- Dataset operations: 120-300 seconds

### 2. Use Markers
```python
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_large_dataset():
    pass
```

Then skip slow tests in CI:
```bash
pytest -m "not slow"
```

### 3. Fail Fast
- Short timeouts help identify issues quickly
- Better than waiting indefinitely

### 4. Document Expectations
```python
@pytest.mark.timeout(60)
def test_api_call(self):
    """
    Test API call to PDBe.
    
    Expected duration: 5-10 seconds
    Timeout: 60 seconds (with buffer for slow networks)
    """
    pass
```

## Timeout Method

We use `thread` method (not `signal`):
- Works on all platforms (Windows, Linux, macOS)
- Compatible with async code
- Safer for complex test scenarios

Set in `pytest.ini`:
```ini
--timeout-method=thread
```

## CI/CD Considerations

In GitHub Actions or other CI:
```yaml
- name: Run tests with timeout
  run: |
    pytest --timeout=300 --timeout-method=thread
  timeout-minutes: 10  # CI-level timeout
```

Always have a CI-level timeout higher than pytest timeout to allow for cleanup.

## Summary

✅ **Global timeout**: 300 seconds (5 minutes)  
✅ **Thread-based**: Works on all platforms  
✅ **Per-test overrides**: 60-120 seconds for specific tests  
✅ **Configurable**: Via CLI, env vars, or decorators  
✅ **Documented**: Clear timeout expectations in tests

This ensures tests don't hang and provides quick feedback during development and CI/CD.

