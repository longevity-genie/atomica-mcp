#!/usr/bin/env python3
"""ATOMICA MCP Server - Protein structure and ATOMICA analysis interface.

ATOMICA is a geometric deep learning model that learns atomic-scale representations
of intermolecular interactions across proteins, small molecules, ions, lipids, and nucleic acids.
Trained on 2M+ interaction complexes, it generates embeddings that capture physicochemical
features shared across molecular classes.

This server provides access to ATOMICA longevity protein structures with:
- Interaction scores: ATOMICA embeddings quantify interface similarity and predict binding partners
- Critical residues: Ranked residues that influence interactions (low scores = high impact)
- PyMOL commands: Visualization scripts to highlight interaction-critical regions
"""

import asyncio
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

import typer
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from eliot import start_action
from huggingface_hub import hf_hub_download
import polars as pl

from atomica_mcp.dataset import get_hf_filesystem, resolve_pdb_metadata
from atomica_mcp.mining.pdb_metadata import get_pdb_metadata, get_structures_for_uniprot

# Hugging Face repository configuration
HF_REPO_ID = "longevity-genie/atomica_longevity_proteins"
DEFAULT_DATASET_DIR = Path("data/input/atomica_longevity_proteins")
DEFAULT_INDEX_PATH = Path("data/output/atomica_index.parquet")

# Configuration
DEFAULT_HOST = os.getenv("MCP_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("MCP_PORT", "3002"))
DEFAULT_TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http")
DEFAULT_TIMEOUT = int(os.getenv("MCP_TIMEOUT", "300"))  # Timeout for external API requests


def get_dataset_directory() -> Path:
    """
    Get the path to the ATOMICA dataset directory.
    
    Checks in this order:
    1. ATOMICA_DATASET_DIR environment variable
    2. Current working directory (data/input/atomica_longevity_proteins)
    3. Package parent directories
    4. Default path
    
    Returns path if it exists, otherwise returns default path
    (caller should handle downloading if needed).
    """
    # Check environment variable first
    env_path = os.getenv("ATOMICA_DATASET_DIR")
    if env_path:
        dataset_path = Path(env_path)
        if dataset_path.exists():
            return dataset_path
        # If env var is set but doesn't exist, still return it
        # (might be intentional for initialization)
        return dataset_path
    
    # Check in current working directory
    cwd_path = Path.cwd() / "data/input/atomica_longevity_proteins"
    if cwd_path.exists():
        return cwd_path
    
    # Check in package parent directories
    package_path = Path(__file__).parent.parent.parent / "data/input/atomica_longevity_proteins"
    if package_path.exists():
        return package_path
    
    # Return default path (may not exist yet)
    return DEFAULT_DATASET_DIR


def ensure_dataset_available(dataset_dir: Path) -> bool:
    """
    Check if dataset is available, download if not.
    
    Args:
        dataset_dir: Path to dataset directory
    
    Returns:
        True if dataset is available or was successfully downloaded
    """
    if dataset_dir.exists() and list(dataset_dir.glob("*.cif")):
        return True
    
    # Dataset not found, try to download
    with start_action(action_type="download_atomica_dataset", dataset_dir=str(dataset_dir)) as action:
        try:
            from atomica_mcp.dataset import download as download_dataset
            
            # Download dataset using the download function
            dataset_dir.mkdir(parents=True, exist_ok=True)
            
            # Use fsspec to download
            fs = get_hf_filesystem()
            repo_path = f"datasets/{HF_REPO_ID}"
            
            files = fs.ls(repo_path, detail=False)
            files = [f for f in files if not f.endswith('/')]
            
            if not files:
                action.log(message_type="no_files_found")
                return False
            
            # Download files
            downloaded = 0
            for remote_file in files:
                filename = Path(remote_file).name
                local_path = dataset_dir / filename
                
                if not local_path.exists():
                    remote_url = f"hf://{remote_file}"
                    fs.get(remote_url, str(local_path))
                    downloaded += 1
            
            action.log(message_type="download_complete", downloaded=downloaded, total=len(files))
            return True
        
        except Exception as e:
            action.log(message_type="download_failed", error=str(e))
            return False


def get_or_create_index(dataset_dir: Path, index_path: Path) -> Optional[pl.DataFrame]:
    """
    Get index DataFrame, create if it doesn't exist.
    
    Args:
        dataset_dir: Path to dataset directory
        index_path: Path to index file
    
    Returns:
        DataFrame with index data or None if creation fails
    """
    if index_path.exists():
        return pl.read_parquet(index_path)
    
    # Index doesn't exist, try to create it
    with start_action(action_type="create_index", dataset_dir=str(dataset_dir)) as action:
        try:
            # Find all CIF files
            cif_files = sorted(dataset_dir.glob("*.cif"))
            
            if not cif_files:
                action.log(message_type="no_cif_files")
                return None
            
            # Build records
            records = []
            for cif_file in cif_files:
                pdb_id = cif_file.stem
                
                record = {
                    "pdb_id": pdb_id.upper(),
                    "cif_path": str(cif_file.relative_to(dataset_dir.parent.parent)),
                    "metadata_path": str((dataset_dir / f"{pdb_id}_metadata.json").relative_to(dataset_dir.parent.parent)) if (dataset_dir / f"{pdb_id}_metadata.json").exists() else None,
                    "summary_path": str((dataset_dir / f"{pdb_id}_summary.json").relative_to(dataset_dir.parent.parent)) if (dataset_dir / f"{pdb_id}_summary.json").exists() else None,
                    "critical_residues_path": str((dataset_dir / f"{pdb_id}_critical_residues.tsv").relative_to(dataset_dir.parent.parent)) if (dataset_dir / f"{pdb_id}_critical_residues.tsv").exists() else None,
                    "interact_scores_path": str((dataset_dir / f"{pdb_id}_interact_scores.json").relative_to(dataset_dir.parent.parent)) if (dataset_dir / f"{pdb_id}_interact_scores.json").exists() else None,
                    "pymol_path": str((dataset_dir / f"{pdb_id}_pymol_commands.pml").relative_to(dataset_dir.parent.parent)) if (dataset_dir / f"{pdb_id}_pymol_commands.pml").exists() else None,
                }
                
                records.append(record)
            
            # Create DataFrame
            df = pl.DataFrame(records)
            
            # Save index
            index_path.parent.mkdir(parents=True, exist_ok=True)
            df.write_parquet(index_path)
            
            action.log(message_type="index_created", rows=len(df))
            return df
        
        except Exception as e:
            action.log(message_type="index_creation_failed", error=str(e))
            return None


class PDBInfo(BaseModel):
    """Information about a PDB structure."""
    pdb_id: str = Field(description="PDB identifier")
    title: Optional[str] = Field(description="Structure title")
    uniprot_ids: List[str] = Field(default_factory=list, description="UniProt IDs")
    gene_symbols: List[str] = Field(default_factory=list, description="Gene symbols")
    organism: Optional[str] = Field(description="Organism name")
    taxonomy_id: Optional[int] = Field(description="NCBI taxonomy ID")


class AtomicaStructure(BaseModel):
    """ATOMICA structure information."""
    pdb_id: str = Field(description="PDB identifier")
    cif_path: Optional[str] = Field(description="Path to CIF structure file")
    metadata_path: Optional[str] = Field(description="Path to metadata JSON")
    summary_path: Optional[str] = Field(description="Path to summary JSON")
    critical_residues_path: Optional[str] = Field(description="Path to critical residues TSV")
    interact_scores_path: Optional[str] = Field(description="Path to interaction scores JSON")
    pymol_path: Optional[str] = Field(description="Path to PyMOL commands")


class AtomicaMCP(FastMCP):
    """ATOMICA MCP Server with protein structure analysis tools."""
    
    def __init__(
        self,
        name: str = "ATOMICA MCP Server",
        dataset_dir: Optional[Path] = None,
        index_path: Optional[Path] = None,
        timeout: int = DEFAULT_TIMEOUT,
        **kwargs
    ):
        """
        Initialize the ATOMICA server.
        
        Args:
            name: Server name
            dataset_dir: Path to dataset directory (auto-detected if None)
            index_path: Path to index file (default: data/output/atomica_index.parquet)
            timeout: Timeout for external API requests in seconds (default: 30)
            **kwargs: Additional arguments for FastMCP
        """
        super().__init__(name=name, **kwargs)
        
        # Setup paths
        self.dataset_dir = dataset_dir or get_dataset_directory()
        self.index_path = index_path or DEFAULT_INDEX_PATH
        self.timeout = timeout
        
        # Ensure dataset is available (with timeout consideration)
        self.dataset_available = ensure_dataset_available(self.dataset_dir)
        
        # Load or create index
        if self.dataset_available:
            self.index = get_or_create_index(self.dataset_dir, self.index_path)
        else:
            self.index = None
        
        # Register tools and resources
        self._register_atomica_tools()
        self._register_atomica_resources()
    
    def _resolve_path(self, relative_path: Optional[str]) -> Optional[str]:
        """
        Resolve relative path from index to absolute path and verify existence.
        
        Args:
            relative_path: Relative path from index (e.g., '1u6d/1u6d.cif')
        
        Returns:
            Absolute path as string if file exists, None otherwise
        """
        if not relative_path:
            return None
        
        # Paths in index are relative to dataset_dir
        abs_path = self.dataset_dir / relative_path
        
        # Verify file exists
        if abs_path.exists():
            return str(abs_path.absolute())
        else:
            return None
    
    def _resolve_paths_in_dict(self, data: Dict[str, Any], path_keys: List[str]) -> Dict[str, Any]:
        """
        Resolve relative paths in dictionary to absolute paths.
        
        Args:
            data: Dictionary containing path values
            path_keys: List of keys that contain paths to resolve
        
        Returns:
            Dictionary with resolved paths
        """
        for key in path_keys:
            if key in data and data[key]:
                data[key] = self._resolve_path(data[key])
        return data
    
    def _register_atomica_tools(self):
        """Register ATOMICA-specific tools."""
        
        # Dataset query tools
        self.tool(
            name="atomica_list_structures",
            description="List all PDB structures in the ATOMICA longevity proteins dataset (NRF2/NFE2L2, KEAP1, SOX2, APOE, OCT4/POU5F1)"
        )(self.list_structures)
        
        self.tool(
            name="atomica_get_structure",
            description="Get info about PDB structure including file paths for interaction scores, critical residues TSV, and PyMOL visualization commands. Example: atomica_get_structure('4iqk')"
        )(self.get_structure)
        
        self.tool(
            name="atomica_get_structure_files",
            description="Get file paths and check availability for PDB structure files (CIF structure, metadata, critical residues TSV, interaction scores JSON, PyMOL commands PML)"
        )(self.get_structure_files)
        
        self.tool(
            name="atomica_search_by_gene",
            description="Search by gene symbol. Supports taxonomy ID or Latin name (e.g., '9606'/'Homo sapiens', 'Mus musculus'). Example: atomica_search_by_gene('KEAP1', 'Homo sapiens')"
        )(self.search_by_gene)
        
        self.tool(
            name="atomica_search_by_uniprot",
            description="Search for structures by UniProt ID(s). Direct lookup in index, fast. Example: atomica_search_by_uniprot('Q14145')"
        )(self.search_by_uniprot)
        
        self.tool(
            name="atomica_search_by_organism",
            description="Search by organism (best-effort, data often incomplete). Prefer search_by_gene with species for reliable results. Example: atomica_search_by_organism('Homo sapiens')"
        )(self.search_by_organism)
        
        # Auxiliary PDB tools
        self.tool(
            name="atomica_resolve_pdb",
            description="Resolve metadata for any PDB ID: UniProt IDs, gene symbols, organisms. Works beyond ATOMICA dataset. Example: atomica_resolve_pdb('1tup')"
        )(self.resolve_pdb)
        
        self.tool(
            name="atomica_get_structures_for_uniprot",
            description="Get all PDB structures for a UniProt ID with resolution, method, dates. Includes AlphaFold if available. Example: atomica_get_structures_for_uniprot('P04637')"
        )(self.get_structures_for_uniprot)
        
        # Dataset management tools
        self.tool(
            name="atomica_dataset_info",
            description="Get ATOMICA dataset statistics: structure counts, unique genes, organisms, repository info"
        )(self.dataset_info)
    
    def _register_atomica_resources(self):
        """Register ATOMICA-specific resources."""
        
        @self.resource("resource://atomica_dataset-info")
        def get_dataset_info_resource() -> str:
            """
            Get detailed information about the ATOMICA longevity proteins dataset.
            
            Returns:
                Formatted information about the dataset
            """
            return """ATOMICA Longevity Proteins Dataset

Description:
  Comprehensive structural analysis of key longevity-related proteins
  using the ATOMICA deep learning model for protein-protein interaction prediction.

Protein Families:
  • NRF2 (NFE2L2): 19 structures - Oxidative stress response
  • KEAP1: 47 structures - Oxidative stress response
  • SOX2: 8 structures - Pluripotency factor
  • APOE (E2/E3/E4): 9 structures - Lipid metabolism & Alzheimer's
  • OCT4 (POU5F1): 4 structures - Reprogramming factor

Total: ~94 high-resolution protein structures

Files per structure:
  • {pdb_id}.cif - Structure file (mmCIF format)
  • {pdb_id}_metadata.json - PDB metadata
  • {pdb_id}_interact_scores.json - ATOMICA interaction scores
  • {pdb_id}_summary.json - Processing statistics
  • {pdb_id}_critical_residues.tsv - Ranked critical residues
  • {pdb_id}_pymol_commands.pml - PyMOL visualization commands

Repository: longevity-genie/atomica_longevity_proteins
URL: https://huggingface.co/datasets/longevity-genie/atomica_longevity_proteins
"""
        
        @self.resource("resource://atomica_index-schema")
        def get_index_schema() -> str:
            """
            Get the schema of the ATOMICA dataset index.
            
            Returns:
                Description of index columns
            """
            return """ATOMICA Dataset Index Schema

Columns:
  • pdb_id: PDB identifier (uppercase)
  • cif_path: Path to structure file (mmCIF format)
  • metadata_path: Path to metadata JSON (PDB API data)
  • summary_path: Path to processing summary JSON
  • critical_residues_path: Path to critical residues TSV
  • interact_scores_path: Path to ATOMICA interaction scores JSON
  • pymol_path: Path to PyMOL visualization commands

Extended columns (if index was built with metadata):
  • metadata_found: Whether metadata was successfully resolved
  • title: Structure title
  • uniprot_ids: List of UniProt identifiers
  • organisms: List of organism names
  • taxonomy_ids: List of NCBI taxonomy IDs
  • gene_symbols: List of gene symbols
  • structures_json: JSON string with structure details
  • critical_residues_count: Number of critical residues identified
  • total_time_seconds: Processing time
  • gpu_memory_mb_max: Maximum GPU memory used

Query patterns:
  • Filter by gene: pl.col('gene_symbols').list.contains('KEAP1')
  • Check if complete: pl.col('metadata_path').is_not_null()
  • Get structures with residues: pl.col('critical_residues_count').is_not_null()
"""
    
    def list_structures(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """
        List PDB structures in ATOMICA dataset with pagination.
        
        Args:
            limit: Max structures to return
            offset: Structures to skip
        
        Returns:
            List of structures with availability flags
            
        Example:
            >>> list_structures(limit=10, offset=0)
            {
                "structures": [{"pdb_id": "1B68", "has_metadata": true, ...}],
                "total": 94,
                "limit": 10,
                "offset": 0
            }
        """
        with start_action(action_type="list_structures", limit=limit, offset=offset) as action:
            if not self.dataset_available or self.index is None:
                return {
                    "error": "ATOMICA dataset not available",
                    "structures": [],
                    "total": 0
                }
            
            # Get paginated results
            total = len(self.index)
            results = self.index[offset:offset+limit]
            
            structures = [
                {
                    "pdb_id": row["pdb_id"],
                    "has_metadata": row.get("metadata_path") is not None,
                    "has_critical_residues": row.get("critical_residues_path") is not None,
                    "has_interact_scores": row.get("interact_scores_path") is not None,
                }
                for row in results.iter_rows(named=True)
            ]
            
            action.log(message_type="structures_listed", count=len(structures), total=total)
            
            return {
                "structures": structures,
                "total": total,
                "limit": limit,
                "offset": offset
            }
    
    def get_structure(self, pdb_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific PDB structure.
        
        Args:
            pdb_id: PDB identifier (case-insensitive, e.g., '1u6d', '4iqk')
        
        Returns:
            Dictionary with structure info and ATOMICA file paths
            
        Example:
            >>> get_structure('1u6d')
            {
                "pdb_id": "1U6D",
                "title": "Crystal structure of the Kelch domain of human Keap1",
                "uniprot_ids": ["Q14145"],
                "gene_symbols": ["KEAP1"],
                "interact_scores_path": "1u6d/1u6d_interact_scores.json",
                "critical_residues_path": "1u6d/1u6d_critical_residues.tsv",
                "pymol_path": "1u6d/1u6d_pymol_commands.pml",
                "critical_residues_count": 156
            }
        """
        with start_action(action_type="get_structure", pdb_id=pdb_id) as action:
            if not self.dataset_available or self.index is None:
                return {
                    "error": "ATOMICA dataset not available",
                    "pdb_id": pdb_id.upper()
                }
            
            # Normalize PDB ID
            pdb_id = pdb_id.upper()
            
            # Find in index
            result = self.index.filter(pl.col("pdb_id") == pdb_id)
            
            if len(result) == 0:
                action.log(message_type="structure_not_found")
                return {
                    "error": f"Structure {pdb_id} not found in ATOMICA dataset",
                    "pdb_id": pdb_id
                }
            
            # Get row data
            row = result.row(0, named=True)
            
            # Build structure info with absolute paths
            path_keys = ["cif_path", "metadata_path", "summary_path", 
                        "critical_residues_path", "interact_scores_path", "pymol_path"]
            
            structure_info = {
                "pdb_id": row["pdb_id"],
            }
            
            # Resolve paths to absolute
            for key in path_keys:
                structure_info[key] = self._resolve_path(row.get(key))
            
            # Add extended metadata if available
            if "title" in row:
                structure_info["title"] = row.get("title")
            if "uniprot_ids" in row:
                structure_info["uniprot_ids"] = row.get("uniprot_ids")
            if "gene_symbols" in row:
                structure_info["gene_symbols"] = row.get("gene_symbols")
            if "organisms" in row:
                structure_info["organisms"] = row.get("organisms")
            if "taxonomy_ids" in row:
                structure_info["taxonomy_ids"] = row.get("taxonomy_ids")
            if "critical_residues_count" in row:
                structure_info["critical_residues_count"] = row.get("critical_residues_count")
            
            action.log(message_type="structure_found")
            return structure_info
    
    def get_structure_files(self, pdb_id: str) -> Dict[str, Any]:
        """
        Get file paths for a PDB structure.
        
        Args:
            pdb_id: PDB identifier
        
        Returns:
            Dictionary with file paths and availability
        """
        with start_action(action_type="get_structure_files", pdb_id=pdb_id) as action:
            if not self.dataset_available:
                return {
                    "error": "ATOMICA dataset not available",
                    "pdb_id": pdb_id.upper()
                }
            
            pdb_id_lower = pdb_id.lower()
            pdb_id_upper = pdb_id.upper()
            
            # Build file paths relative to dataset_dir
            rel_paths = {
                "cif": f"{pdb_id_lower}/{pdb_id_lower}.cif",
                "metadata": f"{pdb_id_lower}/{pdb_id_lower}_metadata.json",
                "summary": f"{pdb_id_lower}/{pdb_id_lower}_summary.json",
                "critical_residues": f"{pdb_id_lower}/{pdb_id_lower}_critical_residues.tsv",
                "interact_scores": f"{pdb_id_lower}/{pdb_id_lower}_interact_scores.json",
                "pymol": f"{pdb_id_lower}/{pdb_id_lower}_pymol_commands.pml",
            }
            
            # Resolve to absolute paths and check existence
            files = {}
            availability = {}
            
            for name, rel_path in rel_paths.items():
                abs_path = self._resolve_path(rel_path)
                files[name] = abs_path
                availability[name] = abs_path is not None
            
            action.log(message_type="files_checked", available=sum(availability.values()))
            
            return {
                "pdb_id": pdb_id_upper,
                "files": files,
                "availability": availability
            }
    
    def search_by_gene(self, gene_symbol: str, species: str = "9606") -> Dict[str, Any]:
        """
        Search for structures by gene symbol via UniProt ID resolution.
        
        Strategy:
        1. First try direct gene symbol match in index (fast)
        2. If no results, resolve gene→UniProt via API, then search by UniProt (robust)
        
        Args:
            gene_symbol: Gene symbol (e.g., 'KEAP1', 'APOE', 'NRF2')
            species: Species as taxonomy ID or Latin name (default: '9606' for human)
                     Examples: "9606", "Homo sapiens", "10090", "Mus musculus"
        
        Returns:
            Dictionary with matching structures including ATOMICA data paths
            
        Example:
            >>> search_by_gene('KEAP1')  # Human by default
            >>> search_by_gene('KEAP1', '9606')  # Human by taxonomy ID
            >>> search_by_gene('KEAP1', 'Homo sapiens')  # Human by Latin name
            >>> search_by_gene('Trp53', 'Mus musculus')  # Mouse p53
            
            Returns:
            {
                "gene_symbol": "KEAP1",
                "species": "9606",
                "resolution_method": "direct_gene_match",
                "structures": [
                    {
                        "pdb_id": "1U6D",
                        "uniprot_ids": ["Q14145"],
                        "gene_symbols": ["KEAP1"],
                        "interact_scores_path": "/abs/path/to/1u6d_interact_scores.json",
                        "critical_residues_path": "/abs/path/to/1u6d_critical_residues.tsv",
                        "pymol_path": "/abs/path/to/1u6d_pymol_commands.pml"
                    },
                    ...
                ],
                "count": 56
            }
        """
        with start_action(action_type="search_by_gene", gene_symbol=gene_symbol, species=species) as action:
            if not self.dataset_available or self.index is None:
                return {
                    "error": "ATOMICA dataset not available",
                    "gene_symbol": gene_symbol,
                    "structures": []
                }
            
            # Check if index has necessary columns
            if "uniprot_ids" not in self.index.columns:
                action.log(message_type="uniprot_column_missing")
                return {
                    "error": "Index does not have UniProt ID information. Run 'dataset index --include-metadata' to rebuild.",
                    "gene_symbol": gene_symbol,
                    "structures": []
                }
            
            # Strategy 1: Try direct gene symbol match in index (fast path)
            if "gene_symbols" in self.index.columns:
                gene_symbol_upper = gene_symbol.upper().strip()
                results = self.index.filter(
                    pl.col("gene_symbols").list.eval(
                        pl.element().str.to_uppercase() == gene_symbol_upper
                    ).list.any()
                )
                
                if len(results) > 0:
                    action.log(message_type="found_by_gene_symbol", count=len(results))
                    structures = [
                        {
                            "pdb_id": row["pdb_id"],
                            "title": row.get("title"),
                            "uniprot_ids": row.get("uniprot_ids", []),
                            "gene_symbols": row.get("gene_symbols", []),
                            "interact_scores_path": self._resolve_path(row.get("interact_scores_path")),
                            "critical_residues_path": self._resolve_path(row.get("critical_residues_path")),
                            "pymol_path": self._resolve_path(row.get("pymol_path")),
                        }
                        for row in results.iter_rows(named=True)
                    ]
                    
                    return {
                        "gene_symbol": gene_symbol,
                        "species": species,
                        "resolution_method": "direct_gene_match",
                        "structures": structures,
                        "count": len(structures)
                    }
            
            # Strategy 2: No direct match - resolve gene→UniProt via API, then search by UniProt
            action.log(message_type="fallback_to_uniprot_api")
            from atomica_mcp.mining.pdb_metadata import resolve_gene_to_uniprot
            
            uniprot_ids = resolve_gene_to_uniprot(gene_symbol, species=species)
            
            if not uniprot_ids:
                action.log(message_type="no_uniprot_found", gene_symbol=gene_symbol)
                return {
                    "gene_symbol": gene_symbol,
                    "species": species,
                    "resolution_method": "uniprot_api",
                    "resolved_uniprot_ids": [],
                    "structures": [],
                    "count": 0,
                    "message": f"No UniProt IDs found for gene symbol '{gene_symbol}' in species {species}"
                }
            
            action.log(message_type="uniprot_resolved", uniprot_ids=uniprot_ids)
            
            # Search by resolved UniProt IDs in index
            results = self.index.filter(
                pl.col("uniprot_ids").list.eval(
                    pl.element().is_in(uniprot_ids)
                ).list.any()
            )
            
            structures = [
                {
                    "pdb_id": row["pdb_id"],
                    "title": row.get("title"),
                    "uniprot_ids": row.get("uniprot_ids", []),
                    "gene_symbols": row.get("gene_symbols", []),
                    "interact_scores_path": self._resolve_path(row.get("interact_scores_path")),
                    "critical_residues_path": self._resolve_path(row.get("critical_residues_path")),
                    "pymol_path": self._resolve_path(row.get("pymol_path")),
                }
                for row in results.iter_rows(named=True)
            ]
            
            action.log(message_type="search_complete", count=len(structures))
            
            return {
                "gene_symbol": gene_symbol,
                "species": species,
                "resolution_method": "uniprot_api",
                "resolved_uniprot_ids": uniprot_ids,
                "structures": structures,
                "count": len(structures)
            }
    
    def search_by_uniprot(self, uniprot_id: str) -> Dict[str, Any]:
        """
        Search for structures by UniProt ID. Direct index lookup.
        
        Args:
            uniprot_id: UniProt accession (e.g., 'Q14145', 'P04637')
        
        Returns:
            Dictionary with matching structures including ATOMICA data paths
            
        Example:
            >>> search_by_uniprot('Q14145')  # KEAP1
            {
                "uniprot_id": "Q14145",
                "structures": [
                    {
                        "pdb_id": "1U6D",
                        "uniprot_ids": ["Q14145"],
                        "gene_symbols": ["KEAP1"],
                        "interact_scores_path": "...",
                        "critical_residues_path": "...",
                        "pymol_path": "..."
                    }
                ],
                "count": 47
            }
        """
        with start_action(action_type="search_by_uniprot", uniprot_id=uniprot_id) as action:
            if not self.dataset_available or self.index is None:
                return {
                    "error": "ATOMICA dataset not available",
                    "uniprot_id": uniprot_id,
                    "structures": []
                }
            
            # Check if index has uniprot_ids column
            if "uniprot_ids" not in self.index.columns:
                action.log(message_type="uniprot_column_missing")
                return {
                    "error": "Index does not have UniProt ID information. Run 'dataset index --include-metadata' to rebuild.",
                    "uniprot_id": uniprot_id,
                    "structures": []
                }
            
            # Filter by UniProt ID (uniprot_ids is list[str])
            results = self.index.filter(
                pl.col("uniprot_ids").list.contains(uniprot_id)
            )
            
            structures = [
                {
                    "pdb_id": row["pdb_id"],
                    "title": row.get("title"),
                    "uniprot_ids": row.get("uniprot_ids", []),
                    "gene_symbols": row.get("gene_symbols", []),
                    "interact_scores_path": self._resolve_path(row.get("interact_scores_path")),
                    "critical_residues_path": self._resolve_path(row.get("critical_residues_path")),
                    "pymol_path": self._resolve_path(row.get("pymol_path")),
                }
                for row in results.iter_rows(named=True)
            ]
            
            action.log(message_type="search_complete", count=len(structures))
            
            return {
                "uniprot_id": uniprot_id,
                "structures": structures,
                "count": len(structures)
            }
    
    def search_by_organism(self, organism: str) -> Dict[str, Any]:
        """
        Search for structures by organism name (best-effort).
        
        Note: Organism data in index is often incomplete. This search:
        - Tries substring match on organism names in index
        - Returns results even if organism field is empty for some structures
        - Consider using search_by_gene with species parameter for more reliable results
        
        Args:
            organism: Organism name or substring (e.g., 'Homo sapiens', 'human', 'sapiens')
        
        Returns:
            Dictionary with matching structures and warning if data is sparse
        """
        with start_action(action_type="search_by_organism", organism=organism) as action:
            if not self.dataset_available or self.index is None:
                return {
                    "error": "ATOMICA dataset not available",
                    "organism": organism,
                    "structures": []
                }
            
            # Check if index has organisms column
            if "organisms" not in self.index.columns:
                action.log(message_type="organism_column_missing")
                return {
                    "warning": "Index does not have organism information. Use search_by_gene with species parameter instead.",
                    "organism": organism,
                    "structures": [],
                    "suggestion": "Try: atomica_search_by_gene('KEAP1', 'Homo sapiens')"
                }
            
            # Count how many structures have organism data
            with_organisms = self.index.filter(pl.col("organisms").list.len() > 0).height
            total = len(self.index)
            
            # If no structures have organism data, return early with warning
            if with_organisms == 0:
                action.log(message_type="no_organism_data")
                return {
                    "organism": organism,
                    "structures": [],
                    "count": 0,
                    "index_coverage": {
                        "structures_with_organism_data": 0,
                        "total_structures": total,
                        "percentage": 0.0
                    },
                    "warning": (
                        "No organism data found in index. "
                        "Use search_by_gene with species parameter instead."
                    ),
                    "suggestion": "Try: atomica_search_by_gene('KEAP1', 'Homo sapiens')"
                }
            
            # Filter by organism (case-insensitive substring match)
            # Check for null values and empty lists
            organism_lower = organism.lower()
            try:
                results = self.index.filter(
                    pl.col("organisms").list.eval(
                        pl.element().is_not_null() & 
                        pl.element().str.to_lowercase().str.contains(organism_lower)
                    ).list.any()
                )
            except Exception as e:
                # Fallback: organisms column might have null values
                action.log(message_type="organism_search_error", error=str(e))
                return {
                    "organism": organism,
                    "structures": [],
                    "count": 0,
                    "warning": (
                        f"Organism search failed due to data format issues. "
                        f"Use search_by_gene with species parameter instead."
                    ),
                    "suggestion": "Try: atomica_search_by_gene('KEAP1', 'Homo sapiens')"
                }
            
            structures = [
                {
                    "pdb_id": row["pdb_id"],
                    "title": row.get("title"),
                    "organisms": row.get("organisms", []),
                    "gene_symbols": row.get("gene_symbols", []),
                    "uniprot_ids": row.get("uniprot_ids", []),
                }
                for row in results.iter_rows(named=True)
            ]
            
            action.log(message_type="search_complete", count=len(structures), 
                      with_organisms=with_organisms, total=total)
            
            result = {
                "organism": organism,
                "structures": structures,
                "count": len(structures),
                "index_coverage": {
                    "structures_with_organism_data": with_organisms,
                    "total_structures": total,
                    "percentage": round(100 * with_organisms / total, 1) if total > 0 else 0
                }
            }
            
            # Add warning if organism data is sparse
            if with_organisms < total * 0.5:
                result["warning"] = (
                    f"Organism data is sparse in index ({with_organisms}/{total} structures have organism info). "
                    "Consider using search_by_gene with species parameter for more reliable results."
                )
            
            return result
    
    def resolve_pdb(self, pdb_id: str) -> Dict[str, Any]:
        """
        Resolve metadata for any PDB ID (not restricted to ATOMICA dataset).
        
        Uses comprehensive PDB mining to get UniProt IDs, gene symbols, organisms, etc.
        
        Args:
            pdb_id: PDB identifier
        
        Returns:
            Dictionary with resolved metadata
        """
        with start_action(action_type="resolve_pdb", pdb_id=pdb_id) as action:
            metadata = resolve_pdb_metadata(pdb_id)
            action.log(message_type="pdb_resolved", found=metadata.get("found", False))
            return metadata
    
    def get_structures_for_uniprot(self, uniprot_id: str, include_alphafold: bool = True, max_structures: Optional[int] = None) -> Dict[str, Any]:
        """
        Get all available PDB structures for a UniProt ID.
        
        Args:
            uniprot_id: UniProt identifier (e.g., 'Q16236')
            include_alphafold: Whether to include AlphaFold structures
            max_structures: Maximum number of structures to return (None for all)
        
        Returns:
            Dictionary with structures and metadata
        """
        with start_action(action_type="get_structures_for_uniprot", uniprot_id=uniprot_id) as action:
            try:
                structures = get_structures_for_uniprot(uniprot_id, include_alphafold=include_alphafold)
                
                if not structures:
                    return {
                        "uniprot_id": uniprot_id,
                        "structures": [],
                        "count": 0,
                        "message": "No structures found"
                    }
                
                # Limit results if requested
                if max_structures is not None:
                    structures = structures[:max_structures]
                
                # Convert to dictionaries
                structure_dicts = [s.to_dict() for s in structures]
                
                action.log(message_type="structures_retrieved", count=len(structure_dicts))
                
                return {
                    "uniprot_id": uniprot_id,
                    "structures": structure_dicts,
                    "count": len(structure_dicts)
                }
            
            except Exception as e:
                action.log(message_type="retrieval_failed", error=str(e))
                return {
                    "error": str(e),
                    "uniprot_id": uniprot_id,
                    "structures": [],
                    "count": 0
                }
    
    def dataset_info(self) -> Dict[str, Any]:
        """
        Get information about the ATOMICA dataset status and statistics.
        
        Returns:
            Dictionary with dataset information
        """
        with start_action(action_type="dataset_info") as action:
            info = {
                "dataset_available": self.dataset_available,
                "dataset_directory": str(self.dataset_dir),
                "index_path": str(self.index_path),
                "repository": HF_REPO_ID,
                "repository_url": f"https://huggingface.co/datasets/{HF_REPO_ID}"
            }
            
            if self.dataset_available and self.index is not None:
                info["total_structures"] = len(self.index)
                
                # Count files
                info["structures_with_metadata"] = self.index.filter(
                    pl.col("metadata_path").is_not_null()
                ).height
                info["structures_with_critical_residues"] = self.index.filter(
                    pl.col("critical_residues_path").is_not_null()
                ).height
                info["structures_with_interact_scores"] = self.index.filter(
                    pl.col("interact_scores_path").is_not_null()
                ).height
                
                # Extended info if available
                if "gene_symbols" in self.index.columns:
                    all_genes = [
                        gene
                        for genes in self.index["gene_symbols"].to_list()
                        if genes
                        for gene in genes
                    ]
                    unique_genes = sorted(set(all_genes))
                    info["unique_genes"] = unique_genes
                    info["gene_count"] = len(unique_genes)
                
                if "organisms" in self.index.columns:
                    all_organisms = [
                        org
                        for orgs in self.index["organisms"].to_list()
                        if orgs
                        for org in orgs
                    ]
                    unique_organisms = sorted(set(all_organisms))
                    info["unique_organisms"] = unique_organisms
                    info["organism_count"] = len(unique_organisms)
            else:
                info["message"] = "Dataset not available. Download using: atomica-mcp dataset download"
            
            action.log(message_type="info_retrieved", available=self.dataset_available)
            return info


# Initialize the ATOMICA MCP server
mcp = AtomicaMCP()

# Create typer app
app = typer.Typer(help="ATOMICA MCP Server - Protein structure and ATOMICA analysis interface")


@app.command("run")
def cli_app(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Host to bind to"),
    port: int = typer.Option(DEFAULT_PORT, "--port", help="Port to bind to"),
    transport: str = typer.Option("streamable-http", "--transport", help="Transport type")
) -> None:
    """Run the MCP server with specified transport."""
    mcp.run(transport=transport, host=host, port=port)


@app.command("stdio")
def cli_app_stdio(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
) -> None:
    """Run the MCP server with stdio transport."""
    mcp.run(transport="stdio")


@app.command("sse")
def cli_app_sse(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Host to bind to"),
    port: int = typer.Option(DEFAULT_PORT, "--port", help="Port to bind to")
) -> None:
    """Run the MCP server with SSE transport."""
    mcp.run(transport="sse", host=host, port=port)


# Standalone CLI functions for direct script access
def cli_app_run() -> None:
    """Standalone function for atomica-mcp-run script."""
    mcp.run(transport="streamable-http", host=DEFAULT_HOST, port=DEFAULT_PORT)


def cli_app_stdio_standalone() -> None:
    """Standalone function for atomica-mcp-stdio script."""
    mcp.run(transport="stdio")


def cli_app_sse_standalone() -> None:
    """Standalone function for atomica-mcp-sse script."""
    mcp.run(transport="sse", host=DEFAULT_HOST, port=DEFAULT_PORT)


if __name__ == "__main__":
    app()

