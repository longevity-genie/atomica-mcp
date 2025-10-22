#!/usr/bin/env python3
"""Test the ATOMICA MCP server functionality."""

import pytest
from pathlib import Path
import json

from atomica_mcp.server import AtomicaMCP, get_dataset_directory, ensure_dataset_available


# Set default timeout for all tests in this module
pytestmark = pytest.mark.timeout(300)


class TestAtomicaMCP:
    """Test ATOMICA MCP server functionality."""
    
    @pytest.fixture
    def mcp_server(self):
        """Create MCP server instance."""
        return AtomicaMCP()
    
    def test_dataset_directory(self):
        """Test dataset directory resolution."""
        dataset_dir = get_dataset_directory()
        assert isinstance(dataset_dir, Path)
    
    def test_server_initialization(self, mcp_server):
        """Test server initializes correctly."""
        assert mcp_server is not None
        assert hasattr(mcp_server, 'dataset_dir')
        assert hasattr(mcp_server, 'index_path')
    
    def test_dataset_info(self, mcp_server):
        """Test dataset info retrieval."""
        info = mcp_server.dataset_info()
        
        assert isinstance(info, dict)
        assert "dataset_available" in info
        assert "dataset_directory" in info
        assert "repository" in info
        assert info["repository"] == "longevity-genie/atomica_longevity_proteins"
    
    @pytest.mark.skipif(
        not get_dataset_directory().exists(),
        reason="Dataset not available"
    )
    def test_list_structures(self, mcp_server):
        """Test listing structures."""
        if not mcp_server.dataset_available:
            pytest.skip("Dataset not available")
        
        result = mcp_server.list_structures(limit=10)
        
        assert isinstance(result, dict)
        assert "structures" in result
        assert "total" in result
        assert isinstance(result["structures"], list)
    
    @pytest.mark.skipif(
        not get_dataset_directory().exists(),
        reason="Dataset not available"
    )
    def test_get_structure_files(self, mcp_server):
        """Test getting structure file paths."""
        if not mcp_server.dataset_available:
            pytest.skip("Dataset not available")
        
        # Test with a known PDB ID from ATOMICA dataset
        result = mcp_server.get_structure_files("1b68")
        
        assert isinstance(result, dict)
        assert result["pdb_id"] == "1B68"
        assert "files" in result
        assert "availability" in result
    
    @pytest.mark.timeout(60)
    def test_resolve_pdb(self, mcp_server):
        """Test PDB resolution (any PDB, not just ATOMICA)."""
        # Test with TP53 structure
        result = mcp_server.resolve_pdb("1tup")
        
        assert isinstance(result, dict)
        assert "pdb_id" in result
        assert result["pdb_id"] == "1TUP"
        
        # Should have found metadata
        if result.get("found"):
            assert "uniprot_ids" in result
            assert "gene_symbols" in result
    
    @pytest.mark.timeout(120)
    @pytest.mark.slow
    @pytest.mark.skipif(
        True,  # Skip by default due to slow/unreliable external API
        reason="Requires external API access to PDB REDO which may be slow or unavailable"
    )
    def test_get_structures_for_uniprot(self, mcp_server):
        """Test getting structures for UniProt ID."""
        # Test with TP53 UniProt ID
        result = mcp_server.get_structures_for_uniprot("P04637", max_structures=5)
        
        assert isinstance(result, dict)
        assert "uniprot_id" in result
        assert result["uniprot_id"] == "P04637"
        assert "structures" in result
        assert "count" in result
        
        # TP53 should have structures
        if result["count"] > 0:
            assert isinstance(result["structures"], list)
            assert len(result["structures"]) > 0


class TestAtomicaDataset:
    """Test dataset-specific functionality."""
    
    @pytest.mark.timeout(120)
    @pytest.mark.slow
    @pytest.mark.skipif(
        True,  # Skip by default due to slow/unreliable external API
        reason="Requires external API access which may be slow or unavailable"
    )
    @pytest.mark.skipif(
        not get_dataset_directory().exists(),
        reason="Dataset not available"
    )
    def test_search_by_gene(self):
        """Test searching by gene symbol."""
        mcp = AtomicaMCP()
        
        if not mcp.dataset_available or mcp.index is None:
            pytest.skip("Dataset or index not available")
        
        # Check if index has gene_symbols column
        if "gene_symbols" not in mcp.index.columns:
            pytest.skip("Index does not have gene symbols. Run 'dataset index' to rebuild.")
        
        # Test searching for KEAP1
        result = mcp.search_by_gene("KEAP1")
        
        assert isinstance(result, dict)
        assert result["gene_symbol"] == "KEAP1"
        assert "structures" in result
        assert "count" in result
    
    @pytest.mark.timeout(120)
    @pytest.mark.slow
    @pytest.mark.skipif(
        True,  # Skip by default due to slow/unreliable external API
        reason="Requires external API access which may be slow or unavailable"
    )
    @pytest.mark.skipif(
        not get_dataset_directory().exists(),
        reason="Dataset not available"
    )
    def test_search_by_organism(self):
        """Test searching by organism."""
        mcp = AtomicaMCP()
        
        if not mcp.dataset_available or mcp.index is None:
            pytest.skip("Dataset or index not available")
        
        # Check if index has organisms column
        if "organisms" not in mcp.index.columns:
            pytest.skip("Index does not have organisms. Run 'dataset index' to rebuild.")
        
        # Test searching for human structures
        result = mcp.search_by_organism("human")
        
        assert isinstance(result, dict)
        assert result["organism"] == "human"
        assert "structures" in result
        assert "count" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

