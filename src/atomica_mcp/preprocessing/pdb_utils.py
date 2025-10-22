"""
Core PDB and ANAGE utilities for protein resolution.

This module provides reusable functions for:
- Loading and querying AnAge database
- Fetching PDB metadata from local TSV files or RCSB API
- Classifying organisms based on AnAge database
- Working with streaming I/O for large files

Note: SIFTS-related functionality (loading PDB annotations, querying UniProt/taxonomy)
has been moved to the pdb_mcp.sifts subpackage.
"""
from typing import Optional, List, Dict, Any, Set, Tuple, Iterable
from pathlib import Path
import gzip
import json
from collections import OrderedDict

import polars as pl
import requests
import biotite.database.rcsb as rcsb
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from eliot import start_action

# Import SIFTS functionality from sifts subpackage
from atomica_mcp.preprocessing.sifts import (
    load_pdb_annotations,
    get_uniprot_ids_from_tsv,
    get_organism_from_tsv,
)
import atomica_mcp.preprocessing.sifts.utils as sifts_utils


# Global dictionary to store AnAge data
ANAGE_DATA: Dict[str, Dict[str, Any]] = {}


def load_anage_data(anage_file: Path) -> Dict[str, Dict[str, Any]]:
    """
    Load AnAge database from TSV file and create a lookup dictionary.
    
    Args:
        anage_file: Path to the AnAge data file (TSV format)
    
    Returns:
        Dictionary mapping lowercase scientific names to AnAge data
    """
    # Load with polars
    df = pl.read_csv(
        anage_file,
        separator='\t',
        has_header=True,
        ignore_errors=True
    )
    
    # Create scientific name column
    df = df.with_columns([
        (pl.col("Genus") + " " + pl.col("Species")).alias("scientific_name"),
        (pl.col("Genus") + " " + pl.col("Species")).str.to_lowercase().alias("scientific_name_lower")
    ])
    
    # Build dictionary
    anage_dict = {}
    for row in df.iter_rows(named=True):
        if row["Genus"] and row["Species"]:
            anage_dict[row["scientific_name_lower"]] = {
                "scientific_name": row["scientific_name"],
                "common_name": row["Common name"] or "",
                "max_longevity_yrs": row["Maximum longevity (yrs)"],
                "genus": row["Genus"],
                "species": row["Species"],
                "kingdom": row["Kingdom"] or "",
                "phylum": row["Phylum"] or "",
                "class": row["Class"] or "",
            }
    
    return anage_dict


# SIFTS functions (load_pdb_annotations, get_uniprot_ids_from_tsv, get_organism_from_tsv)
# are now imported from pdb_mcp.sifts package above


def parse_entry_id(entry_id: str) -> Dict[str, str]:
    """
    Parse entry ID to extract PDB ID and chain information.
    
    Format: PDB_ID_number_ChainA_ChainB
    Example: 2uxq_2_A_B -> {'pdb_id': '2uxq', 'chain1': 'A', 'chain2': 'B'}
    """
    parts = entry_id.split('_')
    if len(parts) >= 4:
        return {
            'pdb_id': parts[0].lower(),
            'chain1': parts[2],
            'chain2': parts[3]
        }
    elif len(parts) >= 3:
        return {
            'pdb_id': parts[0].lower(),
            'chain1': parts[2] if len(parts) > 2 else '',
            'chain2': ''
        }
    return {'pdb_id': parts[0].lower(), 'chain1': '', 'chain2': ''}


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
    retry=retry_if_exception_type((requests.exceptions.Timeout, requests.exceptions.ConnectionError)),
    reraise=True,
)
def _fetch_pdb_entry_info(pdb_id: str) -> Dict[str, Any]:
    """
    Fetch PDB entry information using biotite's RCSB API.
    
    Args:
        pdb_id: PDB identifier (e.g., '2uxq')
    
    Returns:
        Dictionary with entry information
    
    Raises:
        Exception: If biotite fetch fails after retries
    """
    # Use biotite to fetch entry info
    try:
        entry_info = rcsb.fetch(pdb_id, format="cif")
        # biotite returns structure, we need to extract metadata
        # For better metadata, use JSON format
        import urllib.request
        url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception:
        # Fallback if entry_info fails
        raise


def _fetch_pdb_entry_info_with_retries(pdb_id: str, timeout: int = 10, retries: int = 3) -> Dict[str, Any]:
    """
    Fetch PDB entry information with configurable retry logic.

    Args:
        pdb_id: PDB identifier (e.g., '2uxq')
        timeout: Request timeout in seconds
        retries: Number of retry attempts

    Returns:
        Dictionary with entry information

    Raises:
        Exception: If fetch fails after all retries
    """
    import time
    import requests.exceptions

    for attempt in range(retries + 1):
        try:
            # Use biotite to fetch entry info
            entry_info = rcsb.fetch(pdb_id, format="cif")
            # biotite returns structure, we need to extract metadata
            # For better metadata, use JSON format
            import urllib.request
            url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return json.loads(response.read().decode())
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt == retries:
                # Last attempt failed
                raise e
            # Wait before retrying (exponential backoff)
            wait_time = 0.5 * (2 ** attempt)
            time.sleep(min(wait_time, 10))
        except Exception as e:
            # For other exceptions, retry once more but don't wait
            if attempt == retries:
                raise e
            # Brief wait for non-network errors
            time.sleep(0.1)


def fetch_pdb_metadata(pdb_id: str, timeout: int = 10, retries: int = 3, use_tsv: bool = True, pdb_uniprot_data: Optional[pl.DataFrame] = None, pdb_taxonomy_data: Optional[pl.DataFrame] = None) -> Dict[str, Any]:
    """
    Fetch PDB metadata including resolution, title, chains, and organism information.

    Uses biotite's RCSB API for reliable metadata fetching with retry logic.

    Args:
        pdb_id: PDB identifier (e.g., '2uxq')
        timeout: Request timeout in seconds (passed to urllib)
        retries: Number of retry attempts for API calls
        use_tsv: If True, use local TSV files for organism/UniProt data. If False, use RCSB API.
        pdb_uniprot_data: Optional pre-loaded PDB-UniProt mapping. Uses global if not provided.
        pdb_taxonomy_data: Optional pre-loaded PDB taxonomy data. Uses global if not provided.

    Returns:
        Dictionary with PDB metadata including:
        - pdb_id: PDB identifier
        - found: Whether PDB was found
        - source: "TSV" or "API"
        - resolution: PDB resolution (from RCSB)
        - title: Structure title
        - entities: List of polymer entities with chains, organism, UniProt IDs
        - error: Error message if not found
    """
    try:
        if use_tsv:
            # Use local TSV files for organism/UniProt data
            pdb_id_lower = pdb_id.lower()
            
            uniprot_data = pdb_uniprot_data if pdb_uniprot_data is not None else sifts_utils.PDB_UNIPROT_DATA
            taxonomy_data = pdb_taxonomy_data if pdb_taxonomy_data is not None else sifts_utils.PDB_TAXONOMY_DATA
            
            if uniprot_data is None:
                # TSV data not loaded, fall back to API
                with start_action(action_type="tsv_fallback_to_api", pdb_id=pdb_id, reason="TSV data not loaded"):
                    pass
                return fetch_pdb_metadata(pdb_id, timeout=timeout, retries=retries, use_tsv=False)
            
            # Get all chains for this PDB ID
            pdb_matches = uniprot_data.filter(pl.col("PDB") == pdb_id_lower)
            if len(pdb_matches) == 0:
                # PDB not found in SIFTS, fall back to API
                with start_action(action_type="tsv_fallback_to_api", pdb_id=pdb_id, reason="PDB ID not found in SIFTS"):
                    pass
                return fetch_pdb_metadata(pdb_id, timeout=timeout, retries=retries, use_tsv=False)
            
            # Get unique chains
            chains = pdb_matches["CHAIN"].unique().to_list()
            
            # Build entity with organism and UniProt info per chain
            entities = []
            for chain_id in chains:
                chain_matches = pdb_matches.filter(pl.col("CHAIN") == chain_id)
                uniprot_ids_list = chain_matches["SP_PRIMARY"].unique().to_list()
                uniprot_ids_list = [uid for uid in uniprot_ids_list if uid]
                
                organism_info = get_organism_from_tsv(pdb_id_lower, chain_id, taxonomy_data)
                
                entity_info = {
                    "entity_id": f"chain_{chain_id}",
                    "description": "N/A (from TSV)",
                    "chains": [chain_id],
                    "type": "polymer",
                    "organism": organism_info,
                    "uniprot_ids": uniprot_ids_list,
                }
                entities.append(entity_info)
            
            metadata = {
                "pdb_id": pdb_id,
                "found": True,
                "source": "TSV",
                "entities": entities,
            }
            return metadata
        
        else:
            # Use biotite RCSB API for complete metadata
            metadata = {
                "pdb_id": pdb_id,
                "found": True,
                "source": "API",
            }
            
            try:
                # Fetch entry metadata using biotite's search API (no retries needed, biotite handles it)
                query = rcsb.BasicQuery(pdb_id)
                results = rcsb.search(query)
                
                if not results:
                    return {"pdb_id": pdb_id, "found": False, "error": "PDB ID not found"}
                
                # Fetch detailed entry information via REST API with configurable retries
                entry_data = _fetch_pdb_entry_info_with_retries(pdb_id, timeout=timeout, retries=retries)
                
                # Extract metadata
                metadata["title"] = entry_data.get("struct", {}).get("title", "")
                metadata["description"] = entry_data.get("struct", {}).get("pdbx_descriptor", "")
                
                # Get resolution (this is key - biotite has this)
                if "rcsb_entry_info" in entry_data:
                    metadata["resolution"] = entry_data["rcsb_entry_info"].get("resolution_combined", [])
                    metadata["experimental_method"] = entry_data["rcsb_entry_info"].get("experimental_method", "")
                
                # Get polymer entity IDs
                polymer_entity_ids = entry_data.get("rcsb_entry_container_identifiers", {}).get("polymer_entity_ids", [])
                
                # Fetch each polymer entity with retries
                metadata["entities"] = []
                for entity_id in polymer_entity_ids:
                    try:
                        entity_url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{entity_id}"
                        import urllib.request
                        with urllib.request.urlopen(entity_url, timeout=timeout) as response:
                            entity = json.loads(response.read().decode())
                        
                        chains_str = entity.get("entity_poly", {}).get("pdbx_strand_id", "")
                        chains = [c.strip() for c in chains_str.split(",")] if chains_str else []
                        
                        # Extract organism information
                        organism_info = {}
                        if "entity_src_gen" in entity and entity["entity_src_gen"]:
                            src = entity["entity_src_gen"][0]
                            organism_info = {
                                "scientific_name": src.get("pdbx_gene_src_scientific_name", "Unknown"),
                                "taxonomy_id": src.get("pdbx_gene_src_ncbi_taxonomy_id", None),
                            }
                        elif "entity_src_nat" in entity and entity["entity_src_nat"]:
                            src = entity["entity_src_nat"][0]
                            organism_info = {
                                "scientific_name": src.get("pdbx_organism_scientific", "Unknown"),
                                "taxonomy_id": src.get("pdbx_ncbi_taxonomy_id", None),
                            }
                        elif "rcsb_entity_source_organism" in entity and entity["rcsb_entity_source_organism"]:
                            src = entity["rcsb_entity_source_organism"][0]
                            organism_info = {
                                "scientific_name": src.get("ncbi_scientific_name", "Unknown"),
                                "taxonomy_id": src.get("ncbi_taxonomy_id", None),
                            }
                        else:
                            organism_info = {
                                "scientific_name": "Unknown",
                                "taxonomy_id": None,
                            }
                        
                        uniprot_ids = entity.get("rcsb_polymer_entity_container_identifiers", {}).get("uniprot_ids", [])
                        
                        entity_info = {
                            "entity_id": entity_id,
                            "description": entity.get("rcsb_polymer_entity", {}).get("pdbx_description", ""),
                            "chains": chains,
                            "type": entity.get("entity_poly", {}).get("type", ""),
                            "organism": organism_info,
                            "uniprot_ids": uniprot_ids,
                        }
                        metadata["entities"].append(entity_info)
                    except Exception:
                        # Silently skip entity errors
                        pass
                        
            except requests.exceptions.Timeout as e:
                return {"pdb_id": pdb_id, "found": False, "error": f"Timeout after {timeout}s: {str(e)}"}
            except requests.exceptions.ConnectionError as e:
                return {"pdb_id": pdb_id, "found": False, "error": f"Connection error: {str(e)}"}
            except requests.exceptions.RequestException as e:
                return {"pdb_id": pdb_id, "found": False, "error": f"Request error: {str(e)}"}
            except Exception as e:
                with start_action(action_type="fetch_error", pdb_id=pdb_id, error=str(e)):
                    pass
                return {"pdb_id": pdb_id, "found": False, "error": str(e)}
            
            return metadata
            
    except requests.exceptions.Timeout as e:
        with start_action(action_type="fetch_timeout", pdb_id=pdb_id, error=str(e)):
            pass
        return {"pdb_id": pdb_id, "found": False, "error": f"Timeout after {timeout}s: {str(e)}"}
    except requests.exceptions.ConnectionError as e:
        with start_action(action_type="connection_error", pdb_id=pdb_id, error=str(e)):
            pass
        return {"pdb_id": pdb_id, "found": False, "error": f"Connection error: {str(e)}"}
    except Exception as e:
        with start_action(action_type="fetch_error", pdb_id=pdb_id, error=str(e)):
            pass
        return {"pdb_id": pdb_id, "found": False, "error": str(e)}


def normalize_organism_name(name: str) -> str:
    """
    Normalize organism name by fixing common typos and variants.
    
    Args:
        name: Organism name (scientific or common)
    
    Returns:
        Normalized name
    """
    name_lower = name.lower().strip()
    
    # Common typos and synonyms in PDB data
    typo_map = {
        # Human
        "home sapiens": "homo sapiens",
        "homo sapien": "homo sapiens",
        # Mouse
        "balb/c mouse": "mus musculus",
        "c57bl/6 mouse": "mus musculus",
        "c57bl/6j mouse": "mus musculus",
        "swiss mouse": "mus musculus",
        # Rat
        "buffalo rat": "rattus norvegicus",
        "wistar rat": "rattus norvegicus",
        "sprague-dawley rat": "rattus norvegicus",
        # Cattle
        "bos bovis": "bos taurus",
        # Fruit fly
        "drosophila melangaster": "drosophila melanogaster",
        # Yeast
        "baker's yeast": "saccharomyces cerevisiae",
        "bakers yeast": "saccharomyces cerevisiae",
        # Bacteria (E. coli is in AnAge as a model organism)
        "bacillus coli": "escherichia coli",
        # Other bacteria (not in AnAge, but correct for consistency)
        "micrococcus aureus": "staphylococcus aureus",
        "bacillus mesentericus": "bacillus subtilis",
        "bacillus tuberculosis": "mycobacterium tuberculosis",
        "bacillus pestis": "yersinia pestis",
        "bacillus aeruginosus": "pseudomonas aeruginosa",
        "ampylobacter jejuni": "campylobacter jejuni",
    }
    
    if name_lower in typo_map:
        return typo_map[name_lower]
    
    # Handle strain/subspecies variants - extract genus + species (first two words)
    # Examples: "Escherichia coli K-12" → "Escherichia coli"
    #          "Anabaena sp. DCC D0672" → "Anabaena sp."
    parts = name_lower.split()
    if len(parts) > 2:
        # Check if third word looks like a strain/subspecies marker
        third_word = parts[2]
        # Common strain markers
        if any(marker in third_word for marker in ['atcc', 'dsm', 'strain', 'var.', 'subsp.', 'k-', 'h37rv', 'kt2440', 'pa01', 'dcc', 'v583']):
            return f"{parts[0]} {parts[1]}"
        # If third word is all uppercase or starts with uppercase (likely strain ID)
        if third_word.isupper() or (len(third_word) > 0 and third_word[0].isupper()):
            return f"{parts[0]} {parts[1]}"
        # If third word is numeric (e.g., "168", "27634")
        if third_word.isdigit():
            return f"{parts[0]} {parts[1]}"
    
    return name_lower


def classify_organism(scientific_name: str, anage_data: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Classify organism based on AnAge database lookup.
    Handles typos, common names, and strain variants through normalization.
    
    Args:
        scientific_name: Scientific name of organism
        anage_data: Optional AnAge data dictionary. If None, uses global ANAGE_DATA.
    
    Returns:
        Dictionary with classification, common name, and max longevity from AnAge database.
        If not found in AnAge, returns "Unknown" classification.
    """
    if anage_data is None:
        anage_data = ANAGE_DATA
    
    # Normalize the name to fix typos and variants
    normalized_name = normalize_organism_name(scientific_name)
    
    # Check if organism is in AnAge database (exact match after normalization)
    if normalized_name in anage_data:
        anage_entry = anage_data[normalized_name]
        return {
            "classification": anage_entry.get("class", "Unknown"),
            "common_name": anage_entry.get("common_name", ""),
            "max_longevity_yrs": anage_entry.get("max_longevity_yrs"),
            "kingdom": anage_entry.get("kingdom", ""),
            "phylum": anage_entry.get("phylum", ""),
            "in_anage": True
        }
    
    # Try genus + species only (first two words) if not already tried
    parts = normalized_name.split()
    if len(parts) >= 2:
        genus_species = f"{parts[0]} {parts[1]}"
        if genus_species != normalized_name and genus_species in anage_data:
            anage_entry = anage_data[genus_species]
            return {
                "classification": anage_entry.get("class", "Unknown"),
                "common_name": anage_entry.get("common_name", ""),
                "max_longevity_yrs": anage_entry.get("max_longevity_yrs"),
                "kingdom": anage_entry.get("kingdom", ""),
                "phylum": anage_entry.get("phylum", ""),
                "in_anage": True
            }
    
    # Not found in AnAge database
    return {
        "classification": "Unknown",
        "common_name": "",
        "max_longevity_yrs": None,
        "kingdom": "",
        "phylum": "",
        "in_anage": False
    }


def get_chain_protein_name(metadata: Dict[str, Any], chain_id: str) -> str:
    """
    Get protein name for a specific chain from PDB metadata.
    
    Args:
        metadata: PDB metadata dictionary
        chain_id: Chain identifier (e.g., 'A', 'B')
    
    Returns:
        Protein name/description for the chain
    """
    if not metadata.get("found") or "entities" not in metadata:
        return "Unknown"
    
    for entity in metadata["entities"]:
        if chain_id in entity.get("chains", []):
            return entity.get("description", "Unknown")
    
    return "Unknown"


def get_chain_organism(metadata: Dict[str, Any], chain_id: str, anage_data: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Get organism information for a specific chain from PDB metadata.
    
    Args:
        metadata: PDB metadata dictionary
        chain_id: Chain identifier (e.g., 'A', 'B')
        anage_data: Optional AnAge data dictionary. If None, uses global ANAGE_DATA.
    
    Returns:
        Dictionary with organism information including classification and AnAge data
    """
    default_result = {
        "scientific_name": "Unknown",
        "taxonomy_id": None,
        "classification": "Unknown",
        "common_name": "",
        "max_longevity_yrs": None,
        "kingdom": "",
        "phylum": "",
        "in_anage": False
    }
    
    if not metadata.get("found") or "entities" not in metadata:
        return default_result
    
    for entity in metadata["entities"]:
        if chain_id in entity.get("chains", []):
            organism_info = entity.get("organism", {})
            scientific_name = organism_info.get("scientific_name", "Unknown")
            taxonomy_id = organism_info.get("taxonomy_id", None)
            
            # Get AnAge classification and data
            anage_info = classify_organism(scientific_name, anage_data)
            
            return {
                "scientific_name": scientific_name,
                "taxonomy_id": taxonomy_id,
                **anage_info
            }
    
    return default_result


def get_chain_uniprot_ids(metadata: Dict[str, Any], chain_id: str) -> List[str]:
    """
    Get UniProt IDs for a specific chain from PDB metadata.
    
    Args:
        metadata: PDB metadata dictionary
        chain_id: Chain identifier (e.g., 'A', 'B')
    
    Returns:
        List of UniProt IDs for the chain
    """
    if not metadata.get("found") or "entities" not in metadata:
        return []
    
    for entity in metadata["entities"]:
        if chain_id in entity.get("chains", []):
            return entity.get("uniprot_ids", [])
    
    return []


def iter_jsonl_gz_lines(file_path: Path, line_numbers: Optional[Iterable[int]] = None) -> Iterable[Dict[str, Any]]:
    """
    Iterate over lines from a gzipped JSONL file (memory efficient streaming).
    
    Args:
        file_path: Path to the .jsonl.gz file
        line_numbers: Optional set of line numbers to read (1-indexed). If None, reads all lines.
    
    Yields:
        Dictionaries with line_number and entry data
    """
    with gzip.open(file_path, 'rt', encoding='utf-8') as f:
        for line_num, line in enumerate(f, start=1):
            # Skip lines not in the filter (if provided)
            if line_numbers is not None and line_num not in line_numbers:
                continue
                
            try:
                entry = json.loads(line)
                yield {"line_number": line_num, "entry": entry}
            except json.JSONDecodeError as e:
                with start_action(action_type="json_decode_error", line_number=line_num, error=str(e)):
                    pass


def matches_filter(result: Dict[str, Any], filter_organism: Optional[str], filter_classification: Optional[str]) -> bool:
    """
    Check if a result matches the organism or classification filter.
    Only organisms in AnAge database are considered.
    
    Args:
        result: Result dictionary with chain_organisms information
        filter_organism: Organism name to filter (case-insensitive partial match)
        filter_classification: Classification to filter (exact match based on AnAge class)
    
    Returns:
        True if result matches filter criteria (must be in AnAge database)
    """
    chain_organisms = result.get("chain_organisms", {})
    
    for chain_key in ["chain1", "chain2"]:
        org_info = chain_organisms.get(chain_key, {})
        
        # Must be in AnAge database
        if not org_info.get("in_anage", False):
            continue
        
        # If no specific filters, accept any organism in AnAge
        if not filter_organism and not filter_classification:
            return True
        
        # Check organism filter (partial match, case-insensitive)
        if filter_organism:
            scientific_name = org_info.get("scientific_name", "").lower()
            common_name = org_info.get("common_name", "").lower()
            if filter_organism.lower() in scientific_name or filter_organism.lower() in common_name:
                return True
        
        # Check classification filter (exact match)
        if filter_classification:
            classification = org_info.get("classification", "")
            if classification.lower() == filter_classification.lower():
                return True
    
    return False


def get_last_processed_line(output_file: Path) -> int:
    """
    Extract the last processed line number from an output file.
    
    Args:
        output_file: Path to the output file (JSONL or CSV)
    
    Returns:
        Last processed line number (0-indexed from the file), or 0 if file doesn't exist or is empty
    """
    if not output_file.exists():
        return 0
    
    try:
        if output_file.suffix == '.gz':
            with gzip.open(output_file, 'rt', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            with open(output_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        
        if not lines:
            return 0
        
        # Try to parse the last line as JSON to extract line_number
        last_line = lines[-1].strip()
        if not last_line:
            # If last line is empty, try second to last
            if len(lines) > 1:
                last_line = lines[-2].strip()
            else:
                return 0
        
        try:
            entry = json.loads(last_line)
            last_line_num = entry.get("line_number", 0)
            return last_line_num
        except json.JSONDecodeError:
            # If we can't parse as JSON, return 0
            return 0
    except Exception:
        return 0


class StreamingJSONLWriter:
    """Context manager for streaming JSONL output (memory efficient). Supports append mode."""
    
    def __init__(self, output_path: Path, append: bool = False) -> None:
        self.output_path = output_path
        self.file_handle = None
        self.count = 0
        self.append = append
    
    def __enter__(self) -> "StreamingJSONLWriter":
        mode = 'at' if (self.append and self.output_path.exists()) else 'wt'
        if self.output_path.suffix == '.gz':
            self.file_handle = gzip.open(self.output_path, mode, encoding='utf-8')
        else:
            self.file_handle = open(self.output_path, mode, encoding='utf-8')
        return self
    
    def write_entry(self, entry: Dict[str, Any]) -> None:
        """Write a single entry to the JSONL file."""
        json.dump(entry, self.file_handle)
        self.file_handle.write('\n')
        self.file_handle.flush()  # Flush immediately to disk
        self.count += 1
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.file_handle:
            self.file_handle.close()


class StreamingCSVWriter:
    """Context manager for streaming CSV output (memory efficient). Supports append mode."""
    
    def __init__(self, output_path: Path, batch_size: int = 1000, append: bool = False) -> None:
        self.output_path = output_path
        self.rows: List[Dict[str, Any]] = []
        self.batch_size = max(1, batch_size)  # Write in batches to balance memory and I/O
        self.append = append
        self.is_first_batch = not (append and output_path.exists())
    
    def __enter__(self) -> "StreamingCSVWriter":
        return self
    
    def add_result(self, result: Dict[str, Any]) -> None:
        """Add a result and write batch if needed."""
        entry_id = result["entry_id"]
        pdb_id = result["pdb_id"]
        
        # Add chain1 only if in AnAge
        chain1_org = result.get("chain_organisms", {}).get("chain1", {})
        if chain1_org.get("in_anage", False):
            chain1_protein = result.get("chain_proteins", {}).get("chain1", "Unknown")
            chain1_uniprot = result.get("chain_uniprot_ids", {}).get("chain1", [])
            self.rows.append({
                "entry_id": entry_id,
                "pdb_id": pdb_id,
                "chain_id": result["chains"]["chain1"],
                "protein_name": chain1_protein,
                "organism": chain1_org.get("scientific_name", ""),
                "common_name": chain1_org.get("common_name", ""),
                "taxonomy_id": chain1_org.get("taxonomy_id", ""),
                "classification": chain1_org.get("classification", ""),
                "max_longevity_yrs": chain1_org.get("max_longevity_yrs"),
                "kingdom": chain1_org.get("kingdom", ""),
                "phylum": chain1_org.get("phylum", ""),
                "uniprot_ids": ";".join(chain1_uniprot) if chain1_uniprot else ""
            })
        
        # Add chain2 only if exists and in AnAge
        if result["chains"]["chain2"]:
            chain2_org = result.get("chain_organisms", {}).get("chain2", {})
            if chain2_org.get("in_anage", False):
                chain2_protein = result.get("chain_proteins", {}).get("chain2", "Unknown")
                chain2_uniprot = result.get("chain_uniprot_ids", {}).get("chain2", [])
                self.rows.append({
                    "entry_id": entry_id,
                    "pdb_id": pdb_id,
                    "chain_id": result["chains"]["chain2"],
                    "protein_name": chain2_protein,
                    "organism": chain2_org.get("scientific_name", ""),
                    "common_name": chain2_org.get("common_name", ""),
                    "taxonomy_id": chain2_org.get("taxonomy_id", ""),
                    "classification": chain2_org.get("classification", ""),
                    "max_longevity_yrs": chain2_org.get("max_longevity_yrs"),
                    "kingdom": chain2_org.get("kingdom", ""),
                    "phylum": chain2_org.get("phylum", ""),
                    "uniprot_ids": ";".join(chain2_uniprot) if chain2_uniprot else ""
                })
        
        # Write batch if we've accumulated enough rows
        if len(self.rows) >= self.batch_size:
            self._write_batch()
    
    def _write_batch(self) -> None:
        """Write accumulated rows to CSV and flush to disk."""
        if not self.rows:
            return
        
        df = pl.DataFrame(self.rows)
        
        # Write with or without header depending on whether this is the first batch
        if self.is_first_batch:
            df.write_csv(self.output_path)
            self.is_first_batch = False
        else:
            # Append without header
            with open(self.output_path, 'a') as f:
                df.write_csv(f, include_header=False)
                f.flush()  # Flush the file to disk
        
        # Clear the batch
        self.rows = []
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # Write any remaining rows
        self._write_batch()


class StreamingJSONArrayWriter:
    """Context manager to stream a JSON array to disk without loading everything in memory."""
    
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.file_handle = None
        self._first_item_written = False
    
    def __enter__(self) -> "StreamingJSONArrayWriter":
        self.file_handle = open(self.output_path, 'w', encoding='utf-8')
        # Start JSON array
        self.file_handle.write('[')
        return self
    
    def write_item(self, item: Dict[str, Any]) -> None:
        """Write a single item to the JSON array."""
        if self._first_item_written:
            self.file_handle.write(',')
        json.dump(item, self.file_handle)
        self._first_item_written = True
        self.file_handle.flush()  # Flush immediately to disk
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.file_handle:
            # Close JSON array
            self.file_handle.write(']')
            self.file_handle.close()


class LineNumberFilter:
    """Memory-efficient line number filter supporting ranges and single values.
    Implements __contains__ for quick membership checks without storing huge sets.
    """
    def __init__(self, ranges: List[Tuple[int, int]], singles: Set[int]) -> None:
        self.ranges = ranges  # list of (start, end) inclusive
        self.singles = singles
    
    def __contains__(self, line_number: int) -> bool:  # type: ignore[override]
        if line_number in self.singles:
            return True
        # linear scan over few ranges; users typically specify few ranges
        for start, end in self.ranges:
            if start <= line_number <= end:
                return True
        return False


def parse_line_numbers(line_numbers_str: str) -> LineNumberFilter:
    """
    Parse line numbers from string to a memory-efficient filter.
    Supports single numbers ("5"), ranges ("1-10"), lists ("1,5,10"), and mixed ("1-5,10,15-20").
    """
    ranges: List[Tuple[int, int]] = []
    singles: Set[int] = set()
    
    parts = line_numbers_str.split(',')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            start_s, end_s = part.split('-')
            start, end = int(start_s), int(end_s)
            if start > end:
                start, end = end, start
            ranges.append((start, end))
        else:
            singles.add(int(part))
    return LineNumberFilter(ranges, singles)


def get_project_data_dir() -> Path:
    """Get the project data directory, adjusting for different contexts."""
    # When run as a script or module
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent  # src/pdb_mcp/pdb_utils.py -> project root
    data_dir = project_root / "data"
    
    if not data_dir.exists():
        # Fallback to current directory
        data_dir = Path.cwd() / "data"
    
    return data_dir
