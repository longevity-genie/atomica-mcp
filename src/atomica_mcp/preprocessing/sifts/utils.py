"""
SIFTS (Structure Integration with Function, Taxonomy and Sequences) utilities.

This module provides functions for working with SIFTS data from EBI:
- Loading PDB annotation TSV files (chain-to-UniProt, chain-to-taxonomy)
- Querying UniProt IDs for PDB chains
- Querying organism/taxonomy information for PDB chains

SIFTS Data Sources:
https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/
"""
from typing import Optional, List, Dict, Any
from pathlib import Path

import polars as pl


# Global dictionaries for local PDB annotations from SIFTS
PDB_UNIPROT_DATA: Optional[pl.DataFrame] = None
PDB_TAXONOMY_DATA: Optional[pl.DataFrame] = None
UNIPROT_PDB_DATA: Optional[pl.DataFrame] = None


def load_pdb_annotations(
    annotations_dir: Path,
    skip_taxonomy: bool = False,
    skip_uniprot: bool = False
) -> None:
    """
    Load PDB annotation TSV files from SIFTS into global dataframes for fast lookup.
    
    Args:
        annotations_dir: Path to the annotations/pdb directory containing TSV.GZ files
        skip_taxonomy: If True, skip loading taxonomy file
        skip_uniprot: If True, skip loading uniprot mapping file
    """
    global PDB_UNIPROT_DATA, PDB_TAXONOMY_DATA, UNIPROT_PDB_DATA
    
    # Load pdb_chain_uniprot.tsv.gz - Maps PDB chains to UniProt IDs
    uniprot_file = annotations_dir / "pdb_chain_uniprot.tsv.gz"
    if uniprot_file.exists() and not skip_uniprot:
        PDB_UNIPROT_DATA = pl.read_csv(
            uniprot_file,
            separator='\t',
            has_header=True,
            skip_rows=1,  # Skip comment header
            ignore_errors=True,
            quote_char=None,  # Disable quote character handling
            infer_schema_length=10000,
        )
        # Normalize PDB IDs to lowercase
        PDB_UNIPROT_DATA = PDB_UNIPROT_DATA.with_columns(
            pl.col("PDB").str.to_lowercase()
        )
    
    # Load pdb_chain_taxonomy.tsv.gz - Maps PDB chains to taxonomy information
    taxonomy_file = annotations_dir / "pdb_chain_taxonomy.tsv.gz"
    if taxonomy_file.exists() and not skip_taxonomy:
        PDB_TAXONOMY_DATA = pl.read_csv(
            taxonomy_file,
            separator='\t',
            has_header=True,
            skip_rows=1,  # Skip comment header
            ignore_errors=True,
            quote_char=None,  # Disable quote character handling
            infer_schema_length=10000,
        )
        # Normalize PDB IDs to lowercase
        PDB_TAXONOMY_DATA = PDB_TAXONOMY_DATA.with_columns(
            pl.col("PDB").str.to_lowercase()
        )


def get_uniprot_ids_from_tsv(pdb_id: str, chain_id: str, pdb_uniprot_data: Optional[pl.DataFrame] = None) -> List[str]:
    """
    Get UniProt IDs for a PDB chain from SIFTS TSV data.
    
    Args:
        pdb_id: PDB identifier (lowercase)
        chain_id: Chain identifier (e.g., 'A', 'B')
        pdb_uniprot_data: Optional PDB-UniProt mapping DataFrame. Uses global if not provided.
    
    Returns:
        List of UniProt IDs for the chain
    """
    data = pdb_uniprot_data if pdb_uniprot_data is not None else PDB_UNIPROT_DATA
    if data is None:
        return []
    
    # Filter for matching PDB ID and chain
    matches = data.filter(
        (pl.col("PDB") == pdb_id) & (pl.col("CHAIN") == chain_id)
    )
    
    if len(matches) == 0:
        return []
    
    # Extract SP_PRIMARY (UniProt ID) from all matches
    uniprot_ids = matches["SP_PRIMARY"].unique().to_list()
    return [uid for uid in uniprot_ids if uid]  # Filter out None/empty


def get_organism_from_tsv(pdb_id: str, chain_id: str, pdb_taxonomy_data: Optional[pl.DataFrame] = None, anage_data: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Get organism information for a PDB chain from SIFTS TSV data.
    Prioritizes correct scientific names over typos/variations.
    
    Args:
        pdb_id: PDB identifier (lowercase)
        chain_id: Chain identifier (e.g., 'A', 'B')
        pdb_taxonomy_data: Optional PDB taxonomy mapping DataFrame. Uses global if not provided.
        anage_data: Optional AnAge data dictionary for name validation.
    
    Returns:
        Dictionary with organism information (scientific_name, taxonomy_id)
    """
    from atomica_mcp.preprocessing.pdb_utils import ANAGE_DATA
    
    default_result = {
        "scientific_name": "Unknown",
        "taxonomy_id": None,
    }
    
    taxonomy_data = pdb_taxonomy_data if pdb_taxonomy_data is not None else PDB_TAXONOMY_DATA
    anage = anage_data if anage_data is not None else ANAGE_DATA
    
    if taxonomy_data is None:
        return default_result
    
    # Filter for matching PDB ID and chain
    matches = taxonomy_data.filter(
        (pl.col("PDB") == pdb_id) & (pl.col("CHAIN") == chain_id)
    )
    
    if len(matches) == 0:
        return default_result
    
    # Build reverse lookup from AnAge: common_name -> scientific_name
    common_name_to_scientific: Dict[str, str] = {}
    if anage:
        for scientific_lower, anage_entry in anage.items():
            common_name = anage_entry.get("common_name", "").lower().strip()
            if common_name:
                common_name_to_scientific[common_name] = anage_entry.get("scientific_name", "")
    
    # Common known scientific names that appear in AnAge (for exact matching)
    known_names = set(anage.keys()) if anage else set()  # All scientific names in AnAge (lowercase)
    
    # First pass: look for exact matches with known correct names from AnAge
    all_names = matches["SCIENTIFIC_NAME"].to_list()
    for name in all_names:
        name_stripped = name.strip() if name else ""
        name_lower = name_stripped.lower()
        
        if name_lower in known_names:
            tax_id_match = matches.filter(pl.col("SCIENTIFIC_NAME") == name_stripped).select("TAX_ID").item()
            return {
                "scientific_name": anage[name_lower].get("scientific_name", name_stripped),
                "taxonomy_id": tax_id_match,
            }
    
    # Second pass: try to match common names from AnAge
    for row in matches.iter_rows(named=True):
        scientific_name = row.get("SCIENTIFIC_NAME", "").strip()
        if not scientific_name or scientific_name.upper() == "UNKNOWN":
            continue
        
        scientific_lower = scientific_name.lower().strip('"')
        
        # Try direct match in AnAge
        if scientific_lower in known_names:
            tax_id_match = row.get("TAX_ID")
            return {
                "scientific_name": anage[scientific_lower].get("scientific_name", scientific_name),
                "taxonomy_id": tax_id_match,
            }
        
        # Try matching against AnAge common names
        if scientific_lower in common_name_to_scientific:
            canonical_name = common_name_to_scientific[scientific_lower]
            tax_id_match = row.get("TAX_ID")
            return {
                "scientific_name": canonical_name,
                "taxonomy_id": tax_id_match,
            }
    
    # Third pass: score and prioritize names by quality
    best_name = None
    best_score = -1
    best_tax_id = None
    
    for row in matches.iter_rows(named=True):
        scientific_name = row.get("SCIENTIFIC_NAME", "").strip()
        if not scientific_name or scientific_name.upper() == "UNKNOWN":
            continue
        
        # Score the name based on characteristics
        score = 0
        
        # Prefer names with exactly 2 words separated by space (typical scientific names)
        parts = scientific_name.split()
        if len(parts) == 2:
            score += 50
        elif len(parts) > 2:
            # Could be "Genus species subspecies" or "Homo sapiens (some note)"
            if '(' not in scientific_name:
                score += 30
            else:
                score += 10
        
        # Prefer names with lowercase first letter of species (e.g., "Homo sapiens" not "Homo Sapiens")
        if len(parts) >= 2 and parts[1] and parts[1][0].islower():
            score += 20
        
        # Prefer names that are not all uppercase (avoid "HUMAN")
        if scientific_name != scientific_name.upper():
            score += 15
        
        # Prefer names without extra characters in parentheses
        if '(' not in scientific_name:
            score += 5
        
        if score > best_score:
            best_score = score
            best_name = scientific_name
            best_tax_id = row.get("TAX_ID")
    
    if best_name:
        return {
            "scientific_name": best_name,
            "taxonomy_id": best_tax_id,
        }
    
    # Fallback to first valid name if scoring didn't work
    for row in matches.iter_rows(named=True):
        scientific_name = row.get("SCIENTIFIC_NAME", "").strip()
        if scientific_name and scientific_name.upper() != "UNKNOWN":
            return {
                "scientific_name": scientific_name,
                "taxonomy_id": row.get("TAX_ID"),
            }
    
    return default_result

