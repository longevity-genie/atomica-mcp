#!/usr/bin/env python3
"""
PDB-MCP Server: Model Context Protocol server for PDB structure queries and protein resolution.

This server provides tools for:
- Querying PDB structures by ID, keyword, or organism
- Fetching protein metadata and organism information
- Resolving proteins from PDB chains using AnAge database
- Getting structural statistics and classifications
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

import typer
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from eliot import start_action

from pdb_mcp.pdb_utils import (
    load_anage_data,
    load_pdb_annotations,
    fetch_pdb_metadata,
    get_chain_protein_name,
    get_chain_organism,
    get_chain_uniprot_ids,
    classify_organism,
    get_project_data_dir,
)

# Configuration
DEFAULT_HOST = os.getenv("MCP_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("MCP_PORT", "3002"))
DEFAULT_TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http")


class PDBStructure(BaseModel):
    """Result from a PDB query."""
    pdb_id: str = Field(description="PDB identifier")
    found: bool = Field(description="Whether PDB was found")
    title: Optional[str] = Field(default=None, description="Structure title")
    resolution: Optional[List[float]] = Field(default=None, description="Resolution in Angstroms")
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="Polymer entities with chains and organisms")
    error: Optional[str] = Field(default=None, description="Error message if not found")


class OrganismClassification(BaseModel):
    """Classification of an organism."""
    scientific_name: str = Field(description="Scientific name")
    classification: str = Field(description="Organism classification")
    common_name: str = Field(description="Common name")
    max_longevity_yrs: Optional[float] = Field(default=None, description="Maximum longevity in years from AnAge")
    in_anage: bool = Field(description="Whether organism is in AnAge database")
    kingdom: str = Field(description="Kingdom classification")
    phylum: str = Field(description="Phylum classification")


class PDBMCPServer(FastMCP):
    """PDB MCP Server with tools for structure queries and protein resolution."""

    def __init__(
        self,
        name: str = "PDB MCP Server",
        prefix: str = "pdb_",
        anage_file: Optional[Path] = None,
        annotations_dir: Optional[Path] = None,
        **kwargs
    ):
        """Initialize the PDB MCP server."""
        super().__init__(name=name, **kwargs)
        
        self.prefix = prefix
        self.anage_data: Dict[str, Dict[str, Any]] = {}
        self.use_tsv = False
        
        # Load data files if available
        try:
            data_dir = get_project_data_dir()
            
            # Try loading AnAge data
            if anage_file is None:
                anage_file = data_dir / "input" / "anage" / "anage_data.txt"
            if anage_file and anage_file.exists():
                with start_action(action_type="load_anage_data", file=str(anage_file)):
                    self.anage_data = load_anage_data(anage_file)
            
            # Try loading PDB annotations
            if annotations_dir is None:
                annotations_dir = data_dir / "input" / "pdb"
            if annotations_dir and annotations_dir.exists():
                with start_action(action_type="load_pdb_annotations", dir=str(annotations_dir)):
                    load_pdb_annotations(annotations_dir)
                    self.use_tsv = True
        except Exception as e:
            with start_action(action_type="data_loading_warning", error=str(e)):
                pass
        
        # Register tools and resources
        self._register_pdb_tools()
        self._register_pdb_resources()
    
    def _register_pdb_tools(self) -> None:
        """Register PDB-specific tools."""
        self.tool(
            name=f"{self.prefix}fetch_structure",
            description="Fetch PDB structure metadata by PDB ID"
        )(self.fetch_structure)
        
        self.tool(
            name=f"{self.prefix}classify_organism",
            description="Classify an organism using AnAge database"
        )(self.classify_organism_tool)
        
        self.tool(
            name=f"{self.prefix}get_chain_info",
            description="Get detailed information about a specific chain in a PDB structure"
        )(self.get_chain_info)
        
        self.tool(
            name=f"{self.prefix}list_organisms_in_anage",
            description="Get a list of organisms available in the AnAge database"
        )(self.list_organisms_in_anage)
        
        self.tool(
            name=f"{self.prefix}get_available_data",
            description="Get information about available data sources (AnAge, PDB annotations)"
        )(self.get_available_data)

    def _register_pdb_resources(self) -> None:
        """Register PDB-specific resources."""
        
        @self.resource(f"resource://{self.prefix}anage-info")
        def get_anage_info() -> str:
            """
            Get information about the AnAge database.
            
            AnAge (Animal Ageing and Longevity) is a comprehensive database of 
            longevity and life history in animals. It includes:
            - Maximum longevity data
            - Taxonomic classification
            - Common names and scientific names
            - Life history traits
            
            Returns:
                Description of AnAge database and available data
            """
            with start_action(action_type="get_anage_info"):
                return """AnAge Database - Animal Ageing and Longevity

The AnAge database contains comprehensive aging and longevity data for thousands of species:

FIELDS AVAILABLE:
- Scientific name (Genus Species)
- Common name
- Maximum longevity (years)
- Taxonomic classification (Kingdom, Phylum, Class, etc.)

USE CASES:
- Find organisms in your PDB structures that have known longevity data
- Classify organisms by taxonomic group
- Get maximum lifespan information for comparative longevity studies
- Filter structures by organism type (mammals, birds, reptiles, etc.)

ORGANISMS INCLUDED:
- Mammals, birds, reptiles, amphibians, fish
- Invertebrates (insects, crustaceans, mollusks, etc.)
- Plants, fungi, and microorganisms

ACCESS THROUGH:
- classify_organism tool: Look up any organism's classification
- list_organisms_in_anage tool: See all available organisms
- fetch_structure with organism filtering
"""
        
        @self.resource(f"resource://{self.prefix}pdb-annotations-info")
        def get_pdb_annotations_info() -> str:
            """
            Get information about available PDB annotation data.
            
            Returns:
                Description of PDB annotations and data sources
            """
            with start_action(action_type="get_pdb_annotations_info"):
                info = """PDB Annotations - Structure and Organism Data

AVAILABLE DATA SOURCES:
1. PDB Chain to UniProt Mapping
   - Maps each chain in PDB structures to UniProt protein identifiers
   - Provides protein functional information
   
2. PDB Chain to Taxonomy Mapping
   - Links PDB chains to organisms (scientific and common names)
   - Includes NCBI taxonomy IDs
   - Enables organism-based filtering

DATA AVAILABILITY:
"""
                if self.use_tsv:
                    info += "✓ PDB annotation TSV files are loaded and available\n"
                    info += "✓ Can efficiently query structure organisms and UniProt IDs\n"
                else:
                    info += "⚠ PDB annotation TSV files not found locally\n"
                    info += "✓ Can fetch data from RCSB REST API (slower, but always available)\n"
                
                info += """
TOOLS USING THIS DATA:
- fetch_structure: Returns organism and UniProt info for each chain
- get_chain_info: Detailed chain protein names, organisms, and UniProt IDs
"""
                return info
        
        @self.resource(f"resource://{self.prefix}schema-summary")
        def get_schema_summary() -> str:
            """
            Get a summary of available tools and data in this MCP server.
            
            Returns:
                Formatted summary of tools and their purposes
            """
            summary = f"""PDB-MCP Server Schema Summary

AVAILABLE TOOLS:

1. {self.prefix}fetch_structure(pdb_id: str) -> PDBStructure
   - Fetch metadata for a PDB structure
   - Returns: Structure title, resolution, chains, organisms, UniProt IDs
   - Data sources: RCSB API or local TSV files (faster if available)

2. {self.prefix}classify_organism(scientific_name: str) -> OrganismClassification
   - Classify an organism using AnAge database
   - Returns: Classification, common name, max longevity, kingdom, phylum
   - Useful for understanding which organisms have longevity data

3. {self.prefix}get_chain_info(pdb_id: str, chain_id: str) -> Dict
   - Get detailed information about a specific chain
   - Returns: Protein name, organism info, UniProt IDs
   - Requires: PDB ID and chain identifier (e.g., 'A', 'B')

4. {self.prefix}list_organisms_in_anage() -> List[str]
   - Get all organisms available in AnAge database
   - Useful for understanding which organisms have longevity data
   - Returns: List of scientific names

5. {self.prefix}get_available_data() -> Dict
   - Get information about available data sources
   - Returns: Status of AnAge and PDB annotations

DATA SOURCES:

AnAge Database:
- Animal Ageing and Longevity data
- Includes longevity, taxonomy, and life history
- Currently loaded organisms: {len(self.anage_data)}

PDB Annotations:
- Chain to UniProt protein mappings
- Chain to organism (taxonomy) mappings
- Status: {'Available (TSV)' if self.use_tsv else 'Not loaded (will use RCSB API)'}
"""
            return summary
    
    def fetch_structure(self, pdb_id: str) -> PDBStructure:
        """
        Fetch PDB structure metadata by PDB ID.
        
        Args:
            pdb_id: PDB identifier (e.g., '2uxq', '1a3x')
            
        Returns:
            PDBStructure with metadata, organisms, and UniProt information
        """
        with start_action(action_type="fetch_structure", pdb_id=pdb_id):
            metadata = fetch_pdb_metadata(pdb_id, use_tsv=self.use_tsv)
            
            return PDBStructure(
                pdb_id=pdb_id,
                found=metadata.get("found", False),
                title=metadata.get("title"),
                resolution=metadata.get("resolution"),
                entities=metadata.get("entities", []),
                error=metadata.get("error")
            )
    
    def classify_organism_tool(self, scientific_name: str) -> OrganismClassification:
        """
        Classify an organism using the AnAge database.
        
        Args:
            scientific_name: Scientific name of organism (e.g., 'Homo sapiens', 'Mus musculus')
            
        Returns:
            OrganismClassification with AnAge data
        """
        with start_action(action_type="classify_organism", scientific_name=scientific_name):
            result = classify_organism(scientific_name, self.anage_data)
            
            return OrganismClassification(
                scientific_name=scientific_name,
                classification=result.get("classification", "Unknown"),
                common_name=result.get("common_name", ""),
                max_longevity_yrs=result.get("max_longevity_yrs"),
                in_anage=result.get("in_anage", False),
                kingdom=result.get("kingdom", ""),
                phylum=result.get("phylum", "")
            )
    
    def get_chain_info(self, pdb_id: str, chain_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific chain in a PDB structure.
        
        Args:
            pdb_id: PDB identifier
            chain_id: Chain identifier (e.g., 'A', 'B')
            
        Returns:
            Dictionary with chain information: protein name, organism, UniProt IDs
        """
        with start_action(action_type="get_chain_info", pdb_id=pdb_id, chain_id=chain_id):
            metadata = fetch_pdb_metadata(pdb_id, use_tsv=self.use_tsv)
            
            if not metadata.get("found"):
                return {
                    "pdb_id": pdb_id,
                    "chain_id": chain_id,
                    "found": False,
                    "error": metadata.get("error", "PDB not found")
                }
            
            protein_name = get_chain_protein_name(metadata, chain_id)
            organism_info = get_chain_organism(metadata, chain_id, self.anage_data)
            uniprot_ids = get_chain_uniprot_ids(metadata, chain_id)
            
            return {
                "pdb_id": pdb_id,
                "chain_id": chain_id,
                "found": True,
                "protein_name": protein_name,
                "organism": organism_info,
                "uniprot_ids": uniprot_ids
            }
    
    def list_organisms_in_anage(self) -> List[str]:
        """
        Get list of all organisms in the AnAge database.
        
        Returns:
            List of scientific names in AnAge
        """
        with start_action(action_type="list_organisms_in_anage"):
            organisms = [
                anage_entry.get("scientific_name", "")
                for anage_entry in self.anage_data.values()
            ]
            return sorted([org for org in organisms if org])
    
    def get_available_data(self) -> Dict[str, Any]:
        """
        Get information about available data sources.
        
        Returns:
            Dictionary with data availability status
        """
        with start_action(action_type="get_available_data"):
            return {
                "anage_database": {
                    "loaded": len(self.anage_data) > 0,
                    "organism_count": len(self.anage_data),
                    "description": "Animal Ageing and Longevity database with longevity and taxonomy data"
                },
                "pdb_annotations": {
                    "available": self.use_tsv,
                    "type": "Local TSV files" if self.use_tsv else "RCSB API (will be used for queries)",
                    "description": "PDB chain to organism and UniProt protein mappings"
                },
                "server_info": {
                    "name": "PDB-MCP Server",
                    "version": "0.1.0",
                    "description": "Model Context Protocol server for PDB structure queries and protein resolution"
                }
            }


# Initialize the PDB MCP server
mcp = PDBMCPServer()

# Create typer app
app = typer.Typer(help="PDB-MCP Server - Protein structure queries and resolution")


@app.command("run")
def cli_app(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Host to bind to"),
    port: int = typer.Option(DEFAULT_PORT, "--port", help="Port to bind to"),
    transport: str = typer.Option("streamable-http", "--transport", help="Transport type"),
) -> None:
    """Run the MCP server with specified transport."""
    mcp.run(transport=transport, host=host, port=port)


@app.command("stdio")
def cli_app_stdio(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Run the MCP server with stdio transport."""
    mcp.run(transport="stdio")


@app.command("sse")
def cli_app_sse(
    host: str = typer.Option(DEFAULT_HOST, "--host", help="Host to bind to"),
    port: int = typer.Option(DEFAULT_PORT, "--port", help="Port to bind to"),
) -> None:
    """Run the MCP server with SSE transport."""
    mcp.run(transport="sse", host=host, port=port)


# Standalone CLI functions for direct script access
def cli_app_run() -> None:
    """Standalone function for pdb-mcp-run script."""
    mcp.run(transport="streamable-http", host=DEFAULT_HOST, port=DEFAULT_PORT)


def cli_app_stdio() -> None:
    """Standalone function for pdb-mcp-stdio script."""
    mcp.run(transport="stdio")


def cli_app_sse() -> None:
    """Standalone function for pdb-mcp-sse script."""
    mcp.run(transport="sse", host=DEFAULT_HOST, port=DEFAULT_PORT)


if __name__ == "__main__":
    app()
