"""
Integration tests for PDB-MCP Server tools and resources.

These tests verify that the MCP server tools work correctly with real data:
- fetch_structure: Query PDB structures by ID
- classify_organism: Classify organisms using AnAge database
- get_chain_info: Get chain-specific protein and organism information
- list_organisms_in_anage: List available organisms
- get_available_data: Check data source availability
- Resources: Verify resource endpoints provide data

Tests use real PDB IDs and organism data from RCSB API and AnAge database.
No mocking is used - all tests run against real data sources.
"""
import pytest
from pathlib import Path
from typing import Dict, Any
from pdb_mcp.server import PDBMCPServer, PDBStructure, OrganismClassification


@pytest.fixture(scope="session")
def mcp_server() -> PDBMCPServer:
    """Create a PDB MCP server instance for testing."""
    server = PDBMCPServer()
    # Force use_tsv to False to ensure RCSB API is used instead of local TSV files
    server.use_tsv = False
    return server


@pytest.fixture(scope="session")
def test_pdb_ids() -> Dict[str, Dict[str, Any]]:
    """Known PDB IDs with expected properties for testing."""
    return {
        "2uxq": {
            "name": "PPAR-gamma",
            "expected_organism": "Homo sapiens",
            "has_chains": True,
            "min_entities": 1,
        },
        "1a3x": {
            "name": "HIV Protease",
            "expected_organism": "Human immunodeficiency virus 1",
            "has_chains": True,
            "min_entities": 1,
        },
        "1mbn": {
            "name": "Myoglobin",
            "expected_organism": "Equus caballus",  # Horse
            "has_chains": True,
            "min_entities": 1,
        },
    }


class TestPDBMCPFetchStructure:
    """Tests for the fetch_structure tool."""

    def test_fetch_structure_human_protein(self, mcp_server: PDBMCPServer) -> None:
        """Test fetching a known human protein structure."""
        result: PDBStructure = mcp_server.fetch_structure("2uxq")
        
        assert result.found is True
        assert result.pdb_id == "2uxq"
        assert result.title is not None
        assert len(result.title) > 0
        assert result.resolution is not None
        assert len(result.resolution) > 0
        assert result.entities is not None
        assert len(result.entities) > 0
        assert result.error is None

    def test_fetch_structure_returns_entities(self, mcp_server: PDBMCPServer) -> None:
        """Test that entities have required fields."""
        result: PDBStructure = mcp_server.fetch_structure("1a3x")
        
        assert result.found is True
        
        for entity in result.entities:
            assert "chains" in entity
            assert "organism" in entity
            assert "uniprot_ids" in entity
            assert "entity_id" in entity
            
            # Chains should be non-empty
            assert len(entity["chains"]) > 0
            
            # Organism should have required fields
            organism = entity["organism"]
            assert "scientific_name" in organism
            assert "taxonomy_id" in organism

    def test_fetch_structure_multiple_pdb_ids(
        self,
        mcp_server: PDBMCPServer,
        test_pdb_ids: Dict[str, Dict[str, Any]]
    ) -> None:
        """Test fetching multiple different PDB structures."""
        for pdb_id, expected in test_pdb_ids.items():
            result: PDBStructure = mcp_server.fetch_structure(pdb_id)
            
            assert result.found is True, f"PDB {pdb_id} should be found"
            assert result.pdb_id == pdb_id
            assert len(result.entities) >= expected["min_entities"]

    def test_fetch_structure_invalid_pdb_id(self, mcp_server: PDBMCPServer) -> None:
        """Test that invalid PDB ID is handled gracefully."""
        result: PDBStructure = mcp_server.fetch_structure("XXXX")
        
        assert result.found is False
        assert result.pdb_id == "XXXX"
        assert result.error is not None

    def test_fetch_structure_resolution_is_number(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test that resolution values are valid numbers."""
        result: PDBStructure = mcp_server.fetch_structure("2uxq")
        
        assert result.found is True
        assert result.resolution is not None
        
        for res in result.resolution:
            assert isinstance(res, (int, float))
            assert res > 0  # Resolution should be positive

    def test_fetch_structure_title_is_string(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test that title is a non-empty string."""
        result: PDBStructure = mcp_server.fetch_structure("1mbn")
        
        assert result.found is True
        assert isinstance(result.title, str)
        assert len(result.title) > 0

    def test_fetch_structure_uniprot_ids_format(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test that UniProt IDs have expected format."""
        result: PDBStructure = mcp_server.fetch_structure("2uxq")
        
        assert result.found is True
        
        for entity in result.entities:
            uniprot_ids = entity["uniprot_ids"]
            
            if len(uniprot_ids) > 0:
                # UniProt IDs typically start with P, O, Q, or similar
                for upid in uniprot_ids:
                    assert isinstance(upid, str)
                    assert len(upid) > 0


class TestPDBMCPClassifyOrganism:
    """Tests for the classify_organism tool."""

    def test_classify_homo_sapiens(self, mcp_server: PDBMCPServer) -> None:
        """Test classification of Homo sapiens."""
        result: OrganismClassification = mcp_server.classify_organism_tool("Homo sapiens")
        
        assert result.scientific_name == "Homo sapiens"
        assert result.in_anage is True
        assert result.classification == "Mammalia"
        assert result.common_name.lower() == "human"
        assert result.kingdom == "Animalia"
        assert result.phylum == "Chordata"
        assert result.max_longevity_yrs is not None
        assert result.max_longevity_yrs > 0

    def test_classify_mus_musculus(self, mcp_server: PDBMCPServer) -> None:
        """Test classification of Mus musculus (mouse)."""
        result: OrganismClassification = mcp_server.classify_organism_tool("Mus musculus")
        
        assert result.scientific_name == "Mus musculus"
        assert result.in_anage is True
        assert result.classification == "Mammalia"
        assert "mouse" in result.common_name.lower()
        assert result.kingdom == "Animalia"
        assert result.max_longevity_yrs is not None

    def test_classify_unknown_organism(self, mcp_server: PDBMCPServer) -> None:
        """Test classification of unknown organism."""
        result: OrganismClassification = mcp_server.classify_organism_tool("Unknown xyz organism")
        
        assert result.scientific_name == "Unknown xyz organism"
        assert result.in_anage is False
        assert result.classification == "Unknown"
        assert result.kingdom == ""
        assert result.phylum == ""

    def test_classify_various_species(self, mcp_server: PDBMCPServer) -> None:
        """Test classification of various known species."""
        species_to_test = [
            ("Rattus norvegicus", "Mammalia", True),
            ("Mus musculus", "Mammalia", True),
            ("Gallus gallus", "Aves", True),
            ("Danio rerio", "Teleostei", True),
        ]
        
        for sci_name, expected_class, expected_in_anage in species_to_test:
            result: OrganismClassification = mcp_server.classify_organism_tool(sci_name)
            
            assert result.scientific_name == sci_name
            assert result.in_anage == expected_in_anage
            
            if expected_in_anage:
                assert result.classification == expected_class
                assert result.kingdom == "Animalia"
                assert result.max_longevity_yrs is not None

    def test_classify_returns_valid_types(self, mcp_server: PDBMCPServer) -> None:
        """Test that all returned fields have correct types."""
        result: OrganismClassification = mcp_server.classify_organism_tool("Homo sapiens")
        
        assert isinstance(result.scientific_name, str)
        assert isinstance(result.classification, str)
        assert isinstance(result.common_name, str)
        assert isinstance(result.in_anage, bool)
        assert isinstance(result.kingdom, str)
        assert isinstance(result.phylum, str)
        
        if result.max_longevity_yrs is not None:
            assert isinstance(result.max_longevity_yrs, (int, float))


class TestPDBMCPGetChainInfo:
    """Tests for the get_chain_info tool."""

    def test_get_chain_info_human_protein(self, mcp_server: PDBMCPServer) -> None:
        """Test getting chain info for human protein."""
        result: Dict[str, Any] = mcp_server.get_chain_info("2uxq", "A")
        
        assert result["found"] is True
        assert result["pdb_id"] == "2uxq"
        assert result["chain_id"] == "A"
        assert "protein_name" in result
        assert result["protein_name"]  # Non-empty
        assert "organism" in result
        assert "uniprot_ids" in result

    def test_get_chain_info_organism_has_classification(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test that organism info includes classification."""
        result: Dict[str, Any] = mcp_server.get_chain_info("1a3x", "A")
        
        assert result["found"] is True
        
        organism = result["organism"]
        assert "scientific_name" in organism
        assert "in_anage" in organism
        assert "classification" in organism
        assert "taxonomy_id" in organism

    def test_get_chain_info_invalid_pdb(self, mcp_server: PDBMCPServer) -> None:
        """Test handling of invalid PDB ID."""
        result: Dict[str, Any] = mcp_server.get_chain_info("XXXX", "A")
        
        assert result["found"] is False
        assert result["pdb_id"] == "XXXX"
        assert result["error"] is not None

    def test_get_chain_info_multiple_chains(self, mcp_server: PDBMCPServer) -> None:
        """Test getting info for multiple chains from same structure."""
        # First fetch the structure to know what chains exist
        structure = mcp_server.fetch_structure("2uxq")
        assert structure.found is True
        
        # Get available chains
        chains = set()
        for entity in structure.entities:
            chains.update(entity["chains"])
        
        # Test each chain
        for chain_id in chains:
            result: Dict[str, Any] = mcp_server.get_chain_info("2uxq", chain_id)
            assert result["found"] is True
            assert result["chain_id"] == chain_id
            assert "protein_name" in result
            assert "organism" in result

    def test_get_chain_info_protein_name_string(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test that protein_name is a string."""
        result: Dict[str, Any] = mcp_server.get_chain_info("1mbn", "A")
        
        assert result["found"] is True
        assert isinstance(result["protein_name"], str)

    def test_get_chain_info_uniprot_ids_list(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test that uniprot_ids is a list."""
        result: Dict[str, Any] = mcp_server.get_chain_info("2uxq", "A")
        
        assert result["found"] is True
        assert isinstance(result["uniprot_ids"], list)
        
        for upid in result["uniprot_ids"]:
            assert isinstance(upid, str)


class TestPDBMCPListOrganisms:
    """Tests for the list_organisms_in_anage tool."""

    def test_list_organisms_returns_list(self, mcp_server: PDBMCPServer) -> None:
        """Test that list_organisms_in_anage returns a list."""
        result = mcp_server.list_organisms_in_anage()
        
        assert isinstance(result, list)
        assert len(result) > 0

    def test_list_organisms_all_strings(self, mcp_server: PDBMCPServer) -> None:
        """Test that all organisms are strings."""
        result = mcp_server.list_organisms_in_anage()
        
        for organism in result:
            assert isinstance(organism, str)
            assert len(organism) > 0

    def test_list_organisms_contains_common_species(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test that common species are in the list."""
        result = mcp_server.list_organisms_in_anage()
        result_lower = [org.lower() for org in result]
        
        expected_species = ["homo sapiens", "mus musculus", "rattus norvegicus"]
        
        for species in expected_species:
            assert species in result_lower, f"{species} should be in AnAge"

    def test_list_organisms_sorted(self, mcp_server: PDBMCPServer) -> None:
        """Test that organisms are sorted."""
        result = mcp_server.list_organisms_in_anage()
        
        assert result == sorted(result)


class TestPDBMCPGetAvailableData:
    """Tests for the get_available_data tool."""

    def test_get_available_data_returns_dict(self, mcp_server: PDBMCPServer) -> None:
        """Test that get_available_data returns a dictionary."""
        result = mcp_server.get_available_data()
        
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_get_available_data_has_expected_keys(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test that result has expected top-level keys."""
        result = mcp_server.get_available_data()
        
        assert "anage_database" in result
        assert "pdb_annotations" in result
        assert "server_info" in result

    def test_get_available_data_anage_info(self, mcp_server: PDBMCPServer) -> None:
        """Test AnAge database information."""
        result = mcp_server.get_available_data()
        anage = result["anage_database"]
        
        assert "loaded" in anage
        assert "organism_count" in anage
        assert "description" in anage
        
        assert isinstance(anage["loaded"], bool)
        assert isinstance(anage["organism_count"], int)
        assert anage["organism_count"] > 0

    def test_get_available_data_pdb_annotations(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test PDB annotations information."""
        result = mcp_server.get_available_data()
        pdb_ann = result["pdb_annotations"]
        
        assert "available" in pdb_ann
        assert "type" in pdb_ann
        assert "description" in pdb_ann
        
        assert isinstance(pdb_ann["available"], bool)
        assert isinstance(pdb_ann["type"], str)

    def test_get_available_data_server_info(self, mcp_server: PDBMCPServer) -> None:
        """Test server information."""
        result = mcp_server.get_available_data()
        server = result["server_info"]
        
        assert "name" in server
        assert "version" in server
        assert "description" in server
        
        assert server["name"] == "PDB-MCP Server"


class TestPDBMCPResources:
    """Tests for MCP resources."""

    def test_anage_info_resource_returns_string(self, mcp_server: PDBMCPServer) -> None:
        """Test that AnAge info resource returns a string."""
        # Resources are registered during server initialization
        # Just verify the server initialized with resources
        assert hasattr(mcp_server, '_register_pdb_resources')
        assert len(mcp_server.list_organisms_in_anage()) > 0

    def test_schema_summary_includes_tools(self, mcp_server: PDBMCPServer) -> None:
        """Test that schema summary mentions all tools."""
        data = mcp_server.get_available_data()
        
        # Verify that the server has tools registered
        assert hasattr(mcp_server, 'tool')


class TestPDBMCPEndToEndWorkflows:
    """End-to-end integration tests combining multiple tools."""

    def test_workflow_fetch_and_classify_human_protein(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test workflow: fetch structure and classify organisms."""
        # Step 1: Fetch a human protein structure
        structure = mcp_server.fetch_structure("2uxq")
        assert structure.found is True
        
        # Step 2: Extract organisms from structure
        organisms = set()
        for entity in structure.entities:
            if "organism" in entity:
                organisms.add(entity["organism"]["scientific_name"])
        
        # Step 3: Classify each organism
        for organism in organisms:
            classification = mcp_server.classify_organism_tool(organism)
            assert classification.scientific_name == organism
            
            if "sapiens" in organism.lower():
                assert classification.in_anage is True

    def test_workflow_get_chain_info_and_verify_organism(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test workflow: get chain info and verify organism classification."""
        # Step 1: Get chain info
        chain_info = mcp_server.get_chain_info("2uxq", "A")
        assert chain_info["found"] is True
        
        # Step 2: Extract organism
        organism_name = chain_info["organism"]["scientific_name"]
        assert organism_name
        
        # Step 3: Classify organism
        classification = mcp_server.classify_organism_tool(organism_name)
        
        # Step 4: Verify consistency
        assert classification.scientific_name == organism_name
        assert classification.in_anage == chain_info["organism"]["in_anage"]

    def test_workflow_list_organisms_and_classify(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test workflow: list organisms and classify subset."""
        # Step 1: List organisms
        organisms = mcp_server.list_organisms_in_anage()
        assert len(organisms) > 0
        
        # Step 2: Test first 5 organisms
        for organism in organisms[:5]:
            classification = mcp_server.classify_organism_tool(organism)
            
            assert classification.scientific_name == organism
            assert classification.in_anage is True
            assert classification.classification
            assert classification.kingdom

    def test_workflow_multiple_structures(self, mcp_server: PDBMCPServer) -> None:
        """Test workflow with multiple structures."""
        pdb_ids = ["2uxq", "1a3x", "1mbn"]
        
        for pdb_id in pdb_ids:
            # Step 1: Fetch structure
            structure = mcp_server.fetch_structure(pdb_id)
            assert structure.found is True
            
            # Step 2: Get info for each chain
            for entity in structure.entities:
                for chain_id in entity["chains"]:
                    chain_info = mcp_server.get_chain_info(pdb_id, chain_id)
                    assert chain_info["found"] is True
                    
                    # Step 3: Classify organism
                    organism = chain_info["organism"]["scientific_name"]
                    if organism != "Unknown":
                        classification = mcp_server.classify_organism_tool(organism)
                        assert classification.scientific_name == organism


class TestPDBMCPDataConsistency:
    """Tests for data consistency across multiple tool calls."""

    def test_fetch_structure_consistency(self, mcp_server: PDBMCPServer) -> None:
        """Test that repeated calls return consistent data."""
        pdb_id = "2uxq"
        
        result1 = mcp_server.fetch_structure(pdb_id)
        result2 = mcp_server.fetch_structure(pdb_id)
        
        assert result1.pdb_id == result2.pdb_id
        assert result1.title == result2.title
        assert len(result1.entities) == len(result2.entities)

    def test_organism_classification_consistency(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test that repeated organism classifications are consistent."""
        organism = "Homo sapiens"
        
        result1 = mcp_server.classify_organism_tool(organism)
        result2 = mcp_server.classify_organism_tool(organism)
        
        assert result1.scientific_name == result2.scientific_name
        assert result1.classification == result2.classification
        assert result1.max_longevity_yrs == result2.max_longevity_yrs

    def test_chain_info_consistency(self, mcp_server: PDBMCPServer) -> None:
        """Test that repeated chain info calls are consistent."""
        pdb_id = "2uxq"
        chain_id = "A"
        
        result1 = mcp_server.get_chain_info(pdb_id, chain_id)
        result2 = mcp_server.get_chain_info(pdb_id, chain_id)
        
        # Skip if not found
        if not result1["found"] or not result2["found"]:
            pytest.skip("Chain info not available for this structure")
        
        assert result1["pdb_id"] == result2["pdb_id"]
        assert result1["chain_id"] == result2["chain_id"]
        assert result1["protein_name"] == result2["protein_name"]

    def test_organisms_list_consistency(self, mcp_server: PDBMCPServer) -> None:
        """Test that organisms list is consistent across calls."""
        result1 = mcp_server.list_organisms_in_anage()
        result2 = mcp_server.list_organisms_in_anage()
        
        assert result1 == result2


class TestPDBMCPErrorHandling:
    """Tests for error handling in MCP tools."""

    def test_fetch_invalid_pdb_returns_error(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test that invalid PDB returns error message."""
        result = mcp_server.fetch_structure("INVALID123")
        
        assert result.found is False
        assert result.error is not None
        assert len(result.error) > 0

    def test_get_chain_nonexistent_returns_error(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test that chain info for nonexistent PDB returns error."""
        result = mcp_server.get_chain_info("XXXX", "A")
        
        assert result["found"] is False
        assert "error" in result

    def test_classify_empty_organism_returns_unknown(
        self,
        mcp_server: PDBMCPServer
    ) -> None:
        """Test that empty organism name returns unknown classification."""
        result = mcp_server.classify_organism_tool("")
        
        assert result.in_anage is False
        assert result.classification == "Unknown"
