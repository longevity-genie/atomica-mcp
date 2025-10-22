"""
SIFTS (Structure Integration with Function, Taxonomy and Sequences) package.

This package provides utilities for working with SIFTS data from EBI:
- Loading PDB annotation TSV files (chain-to-UniProt, chain-to-taxonomy)
- Downloading SIFTS data files
- Querying UniProt IDs for PDB chains
- Querying organism/taxonomy information for PDB chains

SIFTS Data Sources:
https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/
"""

from atomica_mcp.preprocessing.sifts.utils import (
    load_pdb_annotations,
    get_uniprot_ids_from_tsv,
    get_organism_from_tsv,
    PDB_UNIPROT_DATA,
    PDB_TAXONOMY_DATA,
    UNIPROT_PDB_DATA,
)

__all__ = [
    "load_pdb_annotations",
    "get_uniprot_ids_from_tsv",
    "get_organism_from_tsv",
    "PDB_UNIPROT_DATA",
    "PDB_TAXONOMY_DATA",
    "UNIPROT_PDB_DATA",
]



