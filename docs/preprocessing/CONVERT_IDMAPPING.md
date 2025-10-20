# Converting idmapping_selected.tab to Parquet

This guide explains how to convert UniProt's `idmapping_selected.tab` file to the efficient Parquet format using lazy evaluation for memory efficiency.

## Overview

The `convert_idmapping` module provides tools to convert large tab-separated UniProt ID mapping files to Parquet format. This conversion:

- **Reduces file size**: Parquet format is significantly more compressed than TSV
- **Improves performance**: Parquet enables columnar access and efficient querying
- **Uses lazy evaluation**: Memory-efficient processing using Polars' streaming capabilities
- **Preserves data**: Full fidelity conversion with schema detection

## Installation

The tool is part of the pdb-mcp package. Ensure dependencies are installed:

```bash
cd pdb-mcp
uv sync
```

## Quick Start

### Using the CLI

Convert using the command-line interface:

```bash
# Convert default location (data/input/uniprot/idmapping_selected.tab.gz)
uv run pdb-mcp convert convert \
    --input-file data/input/uniprot/idmapping_selected.tab.gz

# Specify custom output path
uv run pdb-mcp convert convert \
    --input-file data/input/uniprot/idmapping_selected.tab.gz \
    --output-file data/output/idmapping.parquet

# Without verbose output
uv run pdb-mcp convert convert \
    --input-file data/input/uniprot/idmapping_selected.tab.gz \
    --no-verbose

# With logging to file
uv run pdb-mcp convert convert \
    --input-file data/input/uniprot/idmapping_selected.tab.gz \
    --log-to-file
```

### Using Python Directly

```python
from pathlib import Path
from pdb_mcp.convert_idmapping import convert_idmapping_to_parquet

input_file = Path("data/input/uniprot/idmapping_selected.tab.gz")
output_file = Path("data/output/idmapping_selected.parquet")

# Convert with default settings
result = convert_idmapping_to_parquet(input_file, output_file)
print(f"Converted to: {result}")
```

### Using Jupyter Notebook

```python
from pathlib import Path
from pdb_mcp.convert_idmapping import convert_idmapping_to_parquet

input_file = Path("data/input/uniprot/idmapping_selected.tab.gz")
output_file = Path("data/output/idmapping_selected.parquet")

# Convert using lazy evaluation
result = convert_idmapping_to_parquet(input_file, output_file)

# Read back the parquet file lazily
import polars as pl
mapping = pl.scan_parquet(output_file)

# Access data without loading entire file
print(mapping.head().collect())
```

## Function Signature

```python
def convert_idmapping_to_parquet(
    input_path: Path,
    output_path: Path,
    separator: str = "\t",
    batch_size: Optional[int] = None,
    verbose: bool = True,
) -> Path:
    """
    Convert idmapping_selected.tab to Parquet format using lazy evaluation.
    
    This function reads the tab-separated file lazily, processes it efficiently,
    and writes it to Parquet format without loading the entire file into memory.
    
    Args:
        input_path: Path to the input tab file (compressed or uncompressed)
        output_path: Path where the output parquet file will be written
        separator: Column separator (default: tab)
        batch_size: Optional batch size for processing (only informational in lazy mode)
        verbose: If True, print progress information
        
    Returns:
        Path to the output parquet file
        
    Raises:
        FileNotFoundError: If input file does not exist
        IOError: If output cannot be written
    """
```

## Features

- **Lazy Evaluation**: Uses Polars' `scan_csv()` and `sink_parquet()` for memory-efficient streaming
- **Automatic Compression**: Handles both compressed (.gz) and uncompressed files
- **Schema Detection**: Automatically infers column types without loading full data
- **Error Handling**: Gracefully handles parsing errors with `ignore_errors=True`
- **Logging**: Integrates with Eliot logging for detailed processing information
- **Progress Information**: Optional verbose output showing conversion status

## Performance

The lazy evaluation approach is ideal for large files:

- **Memory Usage**: Constant regardless of file size (streams data)
- **Processing Speed**: Efficient column-by-column processing
- **Disk I/O**: Optimized by Polars' internal algorithms

## File Locations

Default paths (can be customized):

```
pdb-mcp/
├── data/
│   ├── input/
│   │   └── uniprot/
│   │       └── idmapping_selected.tab.gz  (input)
│   └── output/
│       └── idmapping_selected.parquet     (output)
```

## Using Converted Parquet Files

Once converted, read efficiently with Polars:

```python
import polars as pl

# Lazy read (no data loaded yet)
df_lazy = pl.scan_parquet("data/output/idmapping_selected.parquet")

# Access schema without loading
schema = df_lazy.collect_schema()

# Filter columns before loading (more efficient)
filtered = df_lazy.select(["UniProtKB-AC", "Gene_Name"]).collect()

# Aggregate operations are automatically optimized
result = df_lazy.group_by("Gene_Name").count().collect()
```

## Advanced Options

### Custom Separator

For files with different separators:

```python
convert_idmapping_to_parquet(
    input_path=Path("input.txt"),
    output_path=Path("output.parquet"),
    separator="|"  # Custom separator
)
```

### Disable Verbose Output

```python
convert_idmapping_to_parquet(
    input_path=input_file,
    output_path=output_file,
    verbose=False
)
```

### Using in Scripts with Logging

```python
from eliot import to_file
from pdb_mcp.convert_idmapping import convert_idmapping_to_parquet

# Enable file logging
log_file = open("conversion.log", "w")
to_file(log_file)

# Run conversion - all actions will be logged
result = convert_idmapping_to_parquet(
    input_path=Path("data/input/uniprot/idmapping_selected.tab.gz"),
    output_path=Path("data/output/idmapping_selected.parquet")
)
```

## Troubleshooting

### File Not Found

```
FileNotFoundError: Input file not found: /path/to/file
```

Ensure the input file exists and the path is correct:

```bash
ls -lh data/input/uniprot/idmapping_selected.tab.gz
```

### Disk Space Issues

The conversion requires enough disk space for both input and output:

```bash
# Check available space
df -h data/

# Estimate output size (Parquet is typically 30-50% of TSV size)
du -h data/input/uniprot/idmapping_selected.tab.gz
```

### Memory Issues

Even with lazy evaluation, ensure sufficient RAM for column processing. For systems with <4GB RAM, consider processing in smaller batches or upgrading the system.

## Performance Tips

1. **Pre-compress**: Ensure input is compressed (.gz) for faster I/O
2. **SSD Storage**: Use SSD for both input and output for best performance
3. **System RAM**: More RAM allows better caching and parallelization
4. **Network**: If on network storage, consider copying to local SSD first

## Integration with Other Tools

The conversion tool integrates seamlessly with other pdb-mcp components:

```python
from pdb_mcp.convert_idmapping import convert_idmapping_to_parquet
from pdb_mcp.resolve_proteins import resolve

# Convert and then use in protein resolution
convert_idmapping_to_parquet(
    input_path=Path("data/input/uniprot/idmapping_selected.tab.gz"),
    output_path=Path("data/output/idmapping_selected.parquet")
)

# Use the converted file in downstream analyses
```
