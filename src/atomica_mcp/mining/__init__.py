"""
PDB mining module for retrieving comprehensive protein structure metadata.

This module provides high-quality functionality for mining PDB and AlphaFold
structure data, including UniProt mappings, gene symbols, and extensive metadata.
"""

from atomica_mcp.mining.pdb_metadata import (
    PDBMetadata,
    StructureInfo,
    ComplexInfo,
    get_pdb_metadata,
    get_structures_for_uniprot,
    get_uniprot_info,
    get_gene_symbol,
)

__all__ = [
    "PDBMetadata",
    "StructureInfo",
    "ComplexInfo",
    "get_pdb_metadata",
    "get_structures_for_uniprot",
    "get_uniprot_info",
    "get_gene_symbol",
]


