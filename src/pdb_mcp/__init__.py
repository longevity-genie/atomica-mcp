"""
PDB-MCP: Protein structure and annotation utilities for PDB and AnAge data.

This package provides utilities for working with PDB structures and AnAge biological annotations,
including protein name resolution, organism classification, and efficient data loading and streaming.
"""

from pdb_mcp.pdb_utils import (
    # Data loading functions
    load_anage_data,
    load_pdb_annotations,
    # PDB metadata functions
    fetch_pdb_metadata,
    parse_entry_id,
    # Chain information functions
    get_chain_protein_name,
    get_chain_organism,
    get_chain_uniprot_ids,
    get_uniprot_ids_from_tsv,
    get_organism_from_tsv,
    # Organism classification
    classify_organism,
    # Filtering and searching
    matches_filter,
    iter_jsonl_gz_lines,
    # File utilities
    get_last_processed_line,
    get_project_data_dir,
    # Streaming writers
    StreamingJSONLWriter,
    StreamingCSVWriter,
    StreamingJSONArrayWriter,
    # Utilities
    LineNumberFilter,
    parse_line_numbers,
)

__all__ = [
    # Data loading
    "load_anage_data",
    "load_pdb_annotations",
    # PDB metadata
    "fetch_pdb_metadata",
    "parse_entry_id",
    # Chain info
    "get_chain_protein_name",
    "get_chain_organism",
    "get_chain_uniprot_ids",
    "get_uniprot_ids_from_tsv",
    "get_organism_from_tsv",
    # Classification
    "classify_organism",
    # Filtering
    "matches_filter",
    "iter_jsonl_gz_lines",
    # Files
    "get_last_processed_line",
    "get_project_data_dir",
    # Streaming
    "StreamingJSONLWriter",
    "StreamingCSVWriter",
    "StreamingJSONArrayWriter",
    # Utilities
    "LineNumberFilter",
    "parse_line_numbers",
]
