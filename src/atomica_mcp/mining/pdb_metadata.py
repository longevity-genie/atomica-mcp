"""
PDB metadata mining with comprehensive type hints, logging, and retry logic.

This module provides functions to retrieve and resolve PDB metadata including:
- UniProt ID to gene symbol mapping
- PDB structures for UniProt IDs
- Comprehensive structure metadata (resolution, method, date, etc.)
- Complex information (protein-protein, protein-ligand, protein-nucleotide)
- Chain mappings and coverage information
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import requests
from eliot import start_action
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging

# Setup logger for tenacity
logger = logging.getLogger(__name__)


@dataclass
class ComplexInfo:
    """Information about molecular complexes in a PDB structure."""
    
    has_protein_complex: bool = False
    protein_complex_details: Optional[List[str]] = None
    has_nucleotide: bool = False
    nucleotide_details: Optional[List[str]] = None
    has_ligand: bool = False
    ligand_details: Optional[List[str]] = None
    is_fusion: bool = False
    

@dataclass
class StructureInfo:
    """Comprehensive information about a PDB or AlphaFold structure."""
    
    structure_id: str
    uniprot_id: str
    gene_symbol: Optional[str] = None
    deposition_date: Optional[str] = None
    experimental_method: Optional[str] = None
    resolution: Optional[float] = None
    r_free: Optional[float] = None
    pdb_redo_available: bool = False
    pdb_redo_rfree: Optional[float] = None
    chains: List[str] = field(default_factory=list)
    coverage: Dict[str, List[Tuple[int, int]]] = field(default_factory=dict)
    complex_info: Optional[ComplexInfo] = None
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = {
            "structure_id": self.structure_id,
            "uniprot_id": self.uniprot_id,
            "gene_symbol": self.gene_symbol,
            "deposition_date": self.deposition_date,
            "experimental_method": self.experimental_method,
            "resolution": self.resolution,
            "r_free": self.r_free,
            "pdb_redo_available": self.pdb_redo_available,
            "pdb_redo_rfree": self.pdb_redo_rfree,
            "chains": self.chains,
            "coverage": self.coverage,
            "warnings": self.warnings,
        }
        
        if self.complex_info:
            data["complex_info"] = {
                "has_protein_complex": self.complex_info.has_protein_complex,
                "protein_complex_details": self.complex_info.protein_complex_details,
                "has_nucleotide": self.complex_info.has_nucleotide,
                "nucleotide_details": self.complex_info.nucleotide_details,
                "has_ligand": self.complex_info.has_ligand,
                "ligand_details": self.complex_info.ligand_details,
                "is_fusion": self.complex_info.is_fusion,
            }
        
        return data


@dataclass
class PDBMetadata:
    """Complete PDB metadata for a structure."""
    
    pdb_id: str
    title: Optional[str] = None
    uniprot_ids: List[str] = field(default_factory=list)
    gene_symbols: List[str] = field(default_factory=list)
    organism: Optional[str] = None
    organism_tax_id: Optional[int] = None
    structures: List[StructureInfo] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pdb_id": self.pdb_id,
            "title": self.title,
            "uniprot_ids": self.uniprot_ids,
            "gene_symbols": self.gene_symbols,
            "organism": self.organism,
            "organism_tax_id": self.organism_tax_id,
            "structures": [s.to_dict() for s in self.structures],
        }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _make_request(url: str, timeout: int = 30) -> requests.Response:
    """Make HTTP request with retry logic."""
    with start_action(action_type="http_request", url=url) as action:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response


def _make_request_with_error_handling(url: str, timeout: int = 30) -> Optional[requests.Response]:
    """Make HTTP request that returns None on HTTP errors."""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        # Return None for HTTP errors (404, 400, etc.)
        return None


def get_gene_symbol(uniprot_id: str) -> Optional[str]:
    """
    Retrieve gene symbol for a UniProt ID.

    Args:
        uniprot_id: UniProt accession number

    Returns:
        Gene symbol or None if not found or invalid
    """
    with start_action(action_type="get_gene_symbol", uniprot_id=uniprot_id) as action:
        url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
        response = _make_request_with_error_handling(url)

        if response is None:
            # HTTP error occurred (invalid ID, not found, etc.)
            action.log(message_type="gene_symbol_invalid_id")
            return None

        data = response.json()

        if "genes" in data and len(data["genes"]) > 0:
            if "geneName" in data["genes"][0]:
                gene_symbol = data["genes"][0]["geneName"]["value"]
                action.log(message_type="gene_symbol_found", gene_symbol=gene_symbol)
                return gene_symbol

        action.log(message_type="gene_symbol_not_found")
        return None


def get_uniprot_info(uniprot_id: str) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive UniProt information.
    
    Args:
        uniprot_id: UniProt accession number
        
    Returns:
        Dictionary with UniProt information or None if not found
    """
    with start_action(action_type="get_uniprot_info", uniprot_id=uniprot_id) as action:
        url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
        response = _make_request(url)
        data = response.json()
        
        info: Dict[str, Any] = {
            "uniprot_id": uniprot_id,
            "protein_name": None,
            "gene_symbol": None,
            "organism": None,
            "tax_id": None,
            "sequence_length": None,
        }
        
        # Extract protein name
        if "proteinDescription" in data:
            if "recommendedName" in data["proteinDescription"]:
                info["protein_name"] = data["proteinDescription"]["recommendedName"]["fullName"]["value"]
        
        # Extract gene symbol
        if "genes" in data and len(data["genes"]) > 0:
            if "geneName" in data["genes"][0]:
                info["gene_symbol"] = data["genes"][0]["geneName"]["value"]
        
        # Extract organism
        if "organism" in data:
            info["organism"] = data["organism"]["scientificName"]
            if "taxonId" in data["organism"]:
                info["tax_id"] = data["organism"]["taxonId"]
        
        # Extract sequence length
        if "sequence" in data:
            info["sequence_length"] = data["sequence"]["length"]
        
        action.log(message_type="uniprot_info_retrieved", info=info)
        return info


def get_pdb_structures_from_uniprot(uniprot_id: str) -> List[str]:
    """
    Get list of PDB IDs associated with a UniProt ID.

    Args:
        uniprot_id: UniProt accession number

    Returns:
        List of PDB IDs or empty list if not found or invalid
    """
    with start_action(action_type="get_pdb_structures", uniprot_id=uniprot_id) as action:
        url = f"https://www.uniprot.org/uniprot/{uniprot_id}.txt"
        response = _make_request_with_error_handling(url)

        if response is None:
            # HTTP error occurred (invalid ID, not found, etc.)
            action.log(message_type="pdb_structures_invalid_id")
            return []

        pdb_ids = []
        for line in response.text.split("\n"):
            if line.startswith("DR   PDB;"):
                parts = [item.strip() for item in line.rstrip(".\n").split(";")]
                if len(parts) >= 2:
                    pdb_id = parts[1]
                    pdb_ids.append(pdb_id)

        action.log(message_type="pdb_structures_found", count=len(pdb_ids), pdb_ids=pdb_ids)
        return pdb_ids


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def resolve_gene_to_uniprot(gene_symbol: str, species: str = "9606") -> List[str]:
    """
    Resolve gene symbol to UniProt ID(s) using UniProt API.
    
    Args:
        gene_symbol: Gene symbol (e.g., 'TP53', 'KEAP1', 'NRF2')
        species: Species as taxonomy ID or Latin name
                 Examples: "9606", "Homo sapiens", "10090", "Mus musculus"
                 Default: "9606" (human)
    
    Returns:
        List of UniProt IDs matching the gene symbol
        
    Example:
        >>> resolve_gene_to_uniprot('TP53', '9606')
        ['P04637']
        >>> resolve_gene_to_uniprot('TP53', 'Homo sapiens')
        ['P04637']
        >>> resolve_gene_to_uniprot('Trp53', 'Mus musculus')
        ['P02340']
    """
    with start_action(action_type="resolve_gene_to_uniprot", gene_symbol=gene_symbol, species=species) as action:
        # Determine if species is taxonomy ID or Latin name
        species_query = f"organism_id:{species}" if species.isdigit() else f"organism_name:{species}"
        
        # UniProt API query for gene name in specific organism
        url = "https://rest.uniprot.org/uniprotkb/search"
        params = {
            "query": f"(gene:{gene_symbol}) AND ({species_query}) AND (reviewed:true)",
            "format": "json",
            "fields": "accession,gene_primary",
            "size": 10  # Get up to 10 results
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            uniprot_ids = []
            if "results" in data and len(data["results"]) > 0:
                for result in data["results"]:
                    uniprot_id = result.get("primaryAccession")
                    if uniprot_id:
                        uniprot_ids.append(uniprot_id)
            
            action.log(message_type="gene_resolved", uniprot_count=len(uniprot_ids), species_query=species_query)
            return uniprot_ids
            
        except requests.exceptions.RequestException as e:
            action.log(message_type="uniprot_api_error", error=str(e))
            # Try fallback with unreviewed entries
            try:
                params["query"] = f"(gene:{gene_symbol}) AND ({species_query})"
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                uniprot_ids = []
                if "results" in data and len(data["results"]) > 0:
                    for result in data["results"][:3]:  # Limit to 3 unreviewed
                        uniprot_id = result.get("primaryAccession")
                        if uniprot_id:
                            uniprot_ids.append(uniprot_id)
                
                action.log(message_type="gene_resolved_fallback", uniprot_count=len(uniprot_ids))
                return uniprot_ids
            except:
                action.log(message_type="uniprot_fallback_failed")
                return []


def get_alphafold_structure(uniprot_id: str) -> Optional[StructureInfo]:
    """
    Get AlphaFold structure information for a UniProt ID.

    Args:
        uniprot_id: UniProt accession number

    Returns:
        StructureInfo for AlphaFold model or None if not available or invalid
    """
    with start_action(action_type="get_alphafold_structure", uniprot_id=uniprot_id) as action:
        url = f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}"
        response = _make_request_with_error_handling(url)

        if response is None:
            # HTTP error occurred (invalid ID, not found, etc.)
            action.log(message_type="alphafold_invalid_id")
            return None

        data = response.json()

        if not data or len(data) == 0:
            action.log(message_type="alphafold_not_found")
            return None

        result = data[0]
        af_id = result["pdbUrl"].split("/")[-1].replace(".cif", "")

        structure_info = StructureInfo(
            structure_id=af_id,
            uniprot_id=uniprot_id,
            deposition_date=result.get("modelCreatedDate"),
            experimental_method="PREDICTED",
            chains=["A"],
        )

        action.log(message_type="alphafold_structure_found", alphafold_id=af_id)
        return structure_info


def get_pdb_structure_metadata(pdb_id: str) -> Optional[Dict[str, Any]]:
    """
    Get comprehensive metadata for a PDB structure.

    Args:
        pdb_id: PDB identifier (4-letter code)

    Returns:
        Dictionary with structure metadata or None if not found or invalid
    """
    with start_action(action_type="get_pdb_structure_metadata", pdb_id=pdb_id) as action:
        # Get summary data from PDBe
        url = f"https://www.ebi.ac.uk/pdbe/api/pdb/entry/summary/{pdb_id}"
        response = _make_request_with_error_handling(url)

        if response is None:
            # HTTP error occurred (invalid ID, not found, etc.)
            action.log(message_type="pdb_metadata_invalid_id")
            return None

        data = response.json()

        if pdb_id.lower() not in data:
            action.log(message_type="pdb_metadata_not_found")
            return None
        
        entry_data = data[pdb_id.lower()][0]
        
        # Format deposition date
        dep_date = entry_data.get("deposition_date", "")
        if len(dep_date) == 8:
            dep_date = f"{dep_date[:4]}-{dep_date[4:6]}-{dep_date[6:]}"
        
        metadata: Dict[str, Any] = {
            "pdb_id": pdb_id.upper(),
            "deposition_date": dep_date,
            "experimental_method": entry_data.get("experimental_method", [""])[0].upper() if entry_data.get("experimental_method") else None,
            "resolution": None,
            "r_free": None,
        }
        
        # Get experimental data for resolution
        exp_method = metadata["experimental_method"]
        if exp_method and "NMR" not in exp_method:
            exp_url = f"https://www.ebi.ac.uk/pdbe/api/pdb/entry/experiment/{pdb_id}"
            exp_response = _make_request_with_error_handling(exp_url)

            if exp_response is not None:
                exp_data = exp_response.json()
                if pdb_id.lower() in exp_data:
                    exp_entry = exp_data[pdb_id.lower()][0]
                    metadata["resolution"] = exp_entry.get("resolution")
        
        action.log(message_type="pdb_metadata_retrieved", metadata=metadata)
        return metadata


def get_pdb_redo_info(pdb_id: str) -> Tuple[bool, Optional[float]]:
    """
    Check if PDB structure is available in PDB-REDO and get its R-free value.

    Args:
        pdb_id: PDB identifier

    Returns:
        Tuple of (available, r_free_value)
    """
    with start_action(action_type="get_pdb_redo_info", pdb_id=pdb_id) as action:
        url = f"https://pdb-redo.eu/db/{pdb_id}/data.json"
        response = _make_request_with_error_handling(url)

        if response is None:
            # HTTP error occurred (404, 500, etc.)
            action.log(message_type="pdb_redo_not_found")
            return (False, None)

        data = response.json()
        r_free = data.get("properties", {}).get("RFFIN")
        action.log(message_type="pdb_redo_found", r_free=r_free)
        return (True, r_free)


def get_complex_info(pdb_id: str, uniprot_id: str) -> Optional[ComplexInfo]:
    """
    Get information about complexes in a PDB structure.
    
    Args:
        pdb_id: PDB identifier
        uniprot_id: UniProt ID to check for
        
    Returns:
        ComplexInfo object or None if not available
    """
    with start_action(action_type="get_complex_info", pdb_id=pdb_id, uniprot_id=uniprot_id) as action:
        complex_info = ComplexInfo()
        
        # Get UniProt segments mapping
        url = f"https://www.ebi.ac.uk/pdbe/api/mappings/uniprot_segments/{pdb_id}"
        response = _make_request(url)
        data = response.json()
        
        if pdb_id.lower() not in data:
            return None
        
        segment_data = data[pdb_id.lower()]
        uniprot_entries = segment_data.get("UniProt", {})
        
        # Check for protein complexes/fusions
        if len(uniprot_entries) > 1:
            complex_info.has_protein_complex = True
            complex_details = []
            
            chains_per_uniprot: Dict[str, List[str]] = {}
            for up_id, up_data in uniprot_entries.items():
                chains = []
                for mapping in up_data.get("mappings", []):
                    chain_id = mapping.get("chain_id")
                    if chain_id:
                        chains.append(chain_id)
                chains_per_uniprot[up_id] = list(set(chains))
            
            # Check if it's a fusion product
            all_chains = []
            for chains in chains_per_uniprot.values():
                all_chains.extend(chains)
            
            if len(set(all_chains)) == len(all_chains):
                complex_info.is_fusion = False
            else:
                complex_info.is_fusion = True
            
            for up_id, chains in chains_per_uniprot.items():
                detail = f"{up_id}: chains {','.join(chains)}"
                complex_details.append(detail)
            
            complex_info.protein_complex_details = complex_details
        
        # Get molecule information for ligands and nucleotides
        mol_url = f"https://www.ebi.ac.uk/pdbe/api/pdb/entry/molecules/{pdb_id}"
        mol_response = _make_request(mol_url)
        mol_data = mol_response.json()
        
        if pdb_id.lower() in mol_data:
            molecules = mol_data[pdb_id.lower()]
            
            nucleotide_info = []
            ligand_info = []
            
            for molecule in molecules:
                mol_type = molecule.get("molecule_type", "")
                mol_name = molecule.get("molecule_name", [""])[0]
                mol_chains = molecule.get("in_chains", [])
                
                if "nucleotide" in mol_type.lower():
                    complex_info.has_nucleotide = True
                    nucleotide_info.append(f"{mol_name}: chains {','.join(mol_chains)}")
                elif mol_type != "polypeptide(L)" and mol_type != "water":
                    complex_info.has_ligand = True
                    ligand_info.append(f"{mol_name}: chains {','.join(mol_chains)}")
            
            if nucleotide_info:
                complex_info.nucleotide_details = nucleotide_info
            if ligand_info:
                complex_info.ligand_details = ligand_info
        
        action.log(
            message_type="complex_info_retrieved",
            has_protein_complex=complex_info.has_protein_complex,
            has_nucleotide=complex_info.has_nucleotide,
            has_ligand=complex_info.has_ligand,
            is_fusion=complex_info.is_fusion,
        )
        
        return complex_info


def get_structures_for_uniprot(uniprot_id: str, include_alphafold: bool = True) -> List[StructureInfo]:
    """
    Get all structures (PDB + AlphaFold) for a UniProt ID with comprehensive metadata.
    
    Args:
        uniprot_id: UniProt accession number
        include_alphafold: Whether to include AlphaFold structures
        
    Returns:
        List of StructureInfo objects with comprehensive metadata
    """
    with start_action(action_type="get_structures_for_uniprot", uniprot_id=uniprot_id) as action:
        structures = []
        
        # Get gene symbol
        gene_symbol = get_gene_symbol(uniprot_id)
        
        # Get PDB structures
        pdb_ids = get_pdb_structures_from_uniprot(uniprot_id)
        
        for pdb_id in pdb_ids:
            # Get basic metadata
            metadata = get_pdb_structure_metadata(pdb_id)
            if not metadata:
                continue
            
            # Get PDB-REDO info
            redo_available, redo_rfree = get_pdb_redo_info(pdb_id)
            
            # Get complex information
            complex_info = get_complex_info(pdb_id, uniprot_id)
            
            structure_info = StructureInfo(
                structure_id=pdb_id.upper(),
                uniprot_id=uniprot_id,
                gene_symbol=gene_symbol,
                deposition_date=metadata.get("deposition_date"),
                experimental_method=metadata.get("experimental_method"),
                resolution=metadata.get("resolution"),
                r_free=metadata.get("r_free"),
                pdb_redo_available=redo_available,
                pdb_redo_rfree=redo_rfree,
                complex_info=complex_info,
            )
            
            structures.append(structure_info)
        
        # Add AlphaFold structure if requested
        if include_alphafold:
            af_structure = get_alphafold_structure(uniprot_id)
            if af_structure:
                af_structure.gene_symbol = gene_symbol
                structures.append(af_structure)
        
        # Sort structures by experimental method priority and resolution
        method_priority = {
            "X-RAY DIFFRACTION": 1,
            "ELECTRON MICROSCOPY": 2,
            "ELECTRON CRYSTALLOGRAPHY": 3,
            "SOLUTION NMR": 4,
            "SOLID-STATE NMR": 5,
            "PREDICTED": 6,
        }
        
        structures.sort(
            key=lambda s: (
                method_priority.get(s.experimental_method or "PREDICTED", 999),
                s.resolution if s.resolution is not None else float("inf"),
            )
        )
        
        action.log(
            message_type="structures_retrieved",
            uniprot_id=uniprot_id,
            count=len(structures),
        )
        
        return structures


def get_uniprot_mappings_sifts(pdb_id: str) -> Dict[str, Any]:
    """
    Get UniProt mappings using SIFTS (Structure Integration with Function, Taxonomy and Sequence).
    This is a fallback method when the PDBe API fails.
    
    Args:
        pdb_id: PDB identifier
        
    Returns:
        Dictionary with UniProt mappings or empty dict if not found
    """
    with start_action(action_type="get_uniprot_mappings_sifts", pdb_id=pdb_id) as action:
        # SIFTS REST API
        url = f"https://www.ebi.ac.uk/pdbe/api/mappings/best_structures/{pdb_id}"
        response = _make_request_with_error_handling(url)
        
        if response is None:
            action.log(message_type="sifts_api_failed")
            return {}
        
        data = response.json()
        
        # Extract UniProt IDs from SIFTS response
        uniprot_mappings = {}
        if pdb_id.lower() in data:
            for uniprot_id, mapping_info in data[pdb_id.lower()].items():
                uniprot_mappings[uniprot_id] = mapping_info
        
        action.log(message_type="sifts_mappings_retrieved", count=len(uniprot_mappings))
        return uniprot_mappings


def get_uniprot_mappings_rcsb(pdb_id: str) -> List[str]:
    """
    Get UniProt IDs using RCSB PDB REST API.
    This is another fallback method.
    
    Args:
        pdb_id: PDB identifier
        
    Returns:
        List of UniProt IDs
    """
    with start_action(action_type="get_uniprot_mappings_rcsb", pdb_id=pdb_id) as action:
        # RCSB PDB Data API
        url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id.upper()}"
        response = _make_request_with_error_handling(url)
        
        if response is None:
            action.log(message_type="rcsb_api_failed")
            return []
        
        data = response.json()
        uniprot_ids = []
        
        # Try to get polymer entities
        polymer_url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id.upper()}"
        polymer_response = _make_request_with_error_handling(polymer_url)
        
        if polymer_response is not None:
            polymer_data = polymer_response.json()
            # Extract UniProt accessions from reference sequence identifiers
            if "rcsb_polymer_entity_container_identifiers" in polymer_data:
                identifiers = polymer_data["rcsb_polymer_entity_container_identifiers"]
                if "uniprot_ids" in identifiers:
                    uniprot_ids.extend(identifiers["uniprot_ids"])
        
        action.log(message_type="rcsb_mappings_retrieved", count=len(uniprot_ids))
        return uniprot_ids


def get_uniprot_mappings_graphql(pdb_id: str) -> List[str]:
    """
    Get UniProt IDs using RCSB PDB GraphQL API.
    This is yet another fallback method with more comprehensive data.
    
    Args:
        pdb_id: PDB identifier
        
    Returns:
        List of UniProt IDs
    """
    with start_action(action_type="get_uniprot_mappings_graphql", pdb_id=pdb_id) as action:
        url = "https://data.rcsb.org/graphql"
        
        query = """
        query ($pdb_id: String!) {
          entry(entry_id: $pdb_id) {
            polymer_entities {
              rcsb_polymer_entity_container_identifiers {
                reference_sequence_identifiers {
                  database_accession
                  database_name
                }
              }
            }
          }
        }
        """
        
        try:
            response = requests.post(
                url,
                json={"query": query, "variables": {"pdb_id": pdb_id.upper()}},
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            uniprot_ids = []
            
            if "data" in data and data["data"] and "entry" in data["data"]:
                entry = data["data"]["entry"]
                if entry and "polymer_entities" in entry:
                    for entity in entry["polymer_entities"]:
                        if "rcsb_polymer_entity_container_identifiers" in entity:
                            identifiers = entity["rcsb_polymer_entity_container_identifiers"]
                            if "reference_sequence_identifiers" in identifiers:
                                for ref in identifiers["reference_sequence_identifiers"]:
                                    if ref.get("database_name") == "UniProt":
                                        acc = ref.get("database_accession")
                                        if acc:
                                            uniprot_ids.append(acc)
            
            action.log(message_type="graphql_mappings_retrieved", count=len(uniprot_ids))
            return uniprot_ids
        
        except Exception as e:
            action.log(message_type="graphql_api_failed", error=str(e))
            return []


def resolve_uniprot_ids_with_fallbacks(pdb_id: str) -> List[str]:
    """
    Resolve UniProt IDs with multiple fallback strategies.
    
    Tries in order:
    1. PDBe UniProt mapping API (primary)
    2. SIFTS API (fallback 1)
    3. RCSB GraphQL API (fallback 2)
    4. RCSB REST API (fallback 3)
    
    Args:
        pdb_id: PDB identifier
        
    Returns:
        List of UniProt IDs (empty if none found)
    """
    with start_action(action_type="resolve_uniprot_ids_with_fallbacks", pdb_id=pdb_id) as action:
        uniprot_ids = []
        
        # Strategy 1: PDBe UniProt mapping API (primary)
        mapping_url = f"https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/{pdb_id}"
        mapping_response = _make_request_with_error_handling(mapping_url)
        
        if mapping_response is not None:
            mapping_data = mapping_response.json()
            # FIX: Use lowercase key to match API response
            if pdb_id.lower() in mapping_data:
                uniprot_mappings = mapping_data[pdb_id.lower()].get("UniProt", {})
                uniprot_ids = list(uniprot_mappings.keys())
                action.log(message_type="pdbe_api_success", count=len(uniprot_ids))
        
        # Strategy 2: SIFTS API (fallback 1)
        if not uniprot_ids:
            action.log(message_type="trying_sifts_fallback")
            sifts_mappings = get_uniprot_mappings_sifts(pdb_id)
            if sifts_mappings:
                uniprot_ids = list(sifts_mappings.keys())
                action.log(message_type="sifts_fallback_success", count=len(uniprot_ids))
        
        # Strategy 3: RCSB GraphQL API (fallback 2)
        if not uniprot_ids:
            action.log(message_type="trying_rcsb_graphql_fallback")
            uniprot_ids = get_uniprot_mappings_graphql(pdb_id)
            if uniprot_ids:
                action.log(message_type="rcsb_graphql_fallback_success", count=len(uniprot_ids))
        
        # Strategy 4: RCSB REST API (fallback 3)
        if not uniprot_ids:
            action.log(message_type="trying_rcsb_rest_fallback")
            uniprot_ids = get_uniprot_mappings_rcsb(pdb_id)
            if uniprot_ids:
                action.log(message_type="rcsb_rest_fallback_success", count=len(uniprot_ids))
        
        # Remove duplicates and sort
        uniprot_ids = sorted(list(set(uniprot_ids)))
        
        action.log(
            message_type="uniprot_resolution_complete",
            total_ids=len(uniprot_ids),
            ids=uniprot_ids
        )
        
        return uniprot_ids


def get_pdb_metadata(pdb_id: str) -> Optional[PDBMetadata]:
    """
    Get comprehensive metadata for a PDB structure by its ID.

    This is the main function for resolving metadata by PDB ID.
    Uses multiple fallback strategies to ensure maximum success rate
    in resolving UniProt IDs.

    Args:
        pdb_id: PDB identifier (4-letter code)

    Returns:
        PDBMetadata object with complete information or None if not found or invalid
    """
    with start_action(action_type="get_pdb_metadata", pdb_id=pdb_id) as action:
        # Get structure summary
        url = f"https://www.ebi.ac.uk/pdbe/api/pdb/entry/summary/{pdb_id}"
        response = _make_request_with_error_handling(url)

        if response is None:
            # HTTP error occurred (invalid ID, not found, etc.)
            action.log(message_type="pdb_invalid_id", pdb_id=pdb_id)
            return None

        data = response.json()

        if pdb_id.lower() not in data:
            action.log(message_type="pdb_not_found", pdb_id=pdb_id)
            return None
            
        entry_data = data[pdb_id.lower()][0]
            
        metadata = PDBMetadata(pdb_id=pdb_id.upper())
            
        # Get title
        metadata.title = entry_data.get("title")
            
        # Get organism info
        if entry_data.get("number_of_entities", {}).get("protein", 0) > 0:
            entity_url = f"https://www.ebi.ac.uk/pdbe/api/pdb/entry/entities/{pdb_id}"
            entity_response = _make_request_with_error_handling(entity_url)

            if entity_response is not None:
                entity_data = entity_response.json()
                if pdb_id.lower() in entity_data:
                    for entity in entity_data[pdb_id.lower()]:
                        if entity.get("molecule_type", []) == ["polypeptide(L)"]:
                            if "source" in entity and len(entity["source"]) > 0:
                                source = entity["source"][0]
                                metadata.organism = source.get("organism_scientific_name")
                                metadata.organism_tax_id = source.get("tax_id")
                            break

        # Get UniProt mappings using comprehensive fallback strategy
        metadata.uniprot_ids = resolve_uniprot_ids_with_fallbacks(pdb_id)
        
        # Get gene symbols for each UniProt ID
        for uniprot_id in metadata.uniprot_ids:
            gene_symbol = get_gene_symbol(uniprot_id)
            if gene_symbol:
                metadata.gene_symbols.append(gene_symbol)
        
        # Get structure information
        structure_metadata = get_pdb_structure_metadata(pdb_id)
        if structure_metadata:
            redo_available, redo_rfree = get_pdb_redo_info(pdb_id)
            
            if metadata.uniprot_ids:
                # Create a structure for each UniProt ID
                for uniprot_id in metadata.uniprot_ids:
                    complex_info = get_complex_info(pdb_id, uniprot_id)
                    
                    structure_info = StructureInfo(
                        structure_id=pdb_id.upper(),
                        uniprot_id=uniprot_id,
                        gene_symbol=get_gene_symbol(uniprot_id),
                        deposition_date=structure_metadata.get("deposition_date"),
                        experimental_method=structure_metadata.get("experimental_method"),
                        resolution=structure_metadata.get("resolution"),
                        r_free=structure_metadata.get("r_free"),
                        pdb_redo_available=redo_available,
                        pdb_redo_rfree=redo_rfree,
                        complex_info=complex_info,
                    )
                    
                    metadata.structures.append(structure_info)
            else:
                # No UniProt mappings, but still create basic structure info
                structure_info = StructureInfo(
                    structure_id=pdb_id.upper(),
                    uniprot_id=None,
                    gene_symbol=None,
                    deposition_date=structure_metadata.get("deposition_date"),
                    experimental_method=structure_metadata.get("experimental_method"),
                    resolution=structure_metadata.get("resolution"),
                    r_free=structure_metadata.get("r_free"),
                    pdb_redo_available=redo_available,
                    pdb_redo_rfree=redo_rfree,
                    complex_info=None,
                )
                
                metadata.structures.append(structure_info)
        
        action.log(
            message_type="pdb_metadata_complete",
            uniprot_count=len(metadata.uniprot_ids),
            gene_count=len(metadata.gene_symbols),
        )
        
        return metadata

