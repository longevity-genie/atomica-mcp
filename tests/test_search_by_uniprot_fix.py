#!/usr/bin/env python3
"""Test search_by_uniprot specifically for the relative paths fix."""

import pytest
from pathlib import Path
from atomica_mcp.server import AtomicaMCP, get_dataset_directory


@pytest.fixture
def mcp_server():
    """Create MCP server instance."""
    return AtomicaMCP()


@pytest.mark.skipif(
    not get_dataset_directory().exists(),
    reason="Dataset not available"
)
def test_search_by_uniprot_returns_relative_paths(mcp_server):
    """Test that search_by_uniprot returns relative paths, not absolute paths."""
    if not mcp_server.dataset_available or mcp_server.index is None:
        pytest.skip("Dataset or index not available")
    
    # Check if index has uniprot_ids column
    if "uniprot_ids" not in mcp_server.index.columns:
        pytest.skip("Index does not have UniProt IDs. Run 'dataset index --include-metadata' to rebuild.")
    
    # Test with P02649 (APOE protein)
    result = mcp_server.search_by_uniprot("P02649")
    
    # Basic structure checks
    assert isinstance(result, dict)
    assert "uniprot_id" in result
    assert result["uniprot_id"] == "P02649"
    assert "dataset_directory" in result
    assert "structures" in result
    assert "count" in result
    
    # Should have found structures
    assert result["count"] > 0
    assert len(result["structures"]) > 0
    
    # Check that dataset_directory is a valid path
    dataset_dir = Path(result["dataset_directory"])
    assert dataset_dir.exists()
    
    # Check that paths in structures are RELATIVE, not absolute
    for structure in result["structures"]:
        assert "pdb_id" in structure
        
        # Check interact_scores_path
        if "interact_scores_path" in structure and structure["interact_scores_path"]:
            path = structure["interact_scores_path"]
            assert not path.startswith("/"), f"interact_scores_path should be relative, got: {path}"
            assert not path.startswith("~"), f"interact_scores_path should not use home dir, got: {path}"
            
            # Verify the path is valid by constructing absolute path
            abs_path = dataset_dir / path
            assert abs_path.exists(), f"File should exist: {abs_path}"
        
        # Check critical_residues_path
        if "critical_residues_path" in structure and structure["critical_residues_path"]:
            path = structure["critical_residues_path"]
            assert not path.startswith("/"), f"critical_residues_path should be relative, got: {path}"
            assert not path.startswith("~"), f"critical_residues_path should not use home dir, got: {path}"
            
            # Verify the path is valid
            abs_path = dataset_dir / path
            assert abs_path.exists(), f"File should exist: {abs_path}"
        
        # Check pymol_path
        if "pymol_path" in structure and structure["pymol_path"]:
            path = structure["pymol_path"]
            assert not path.startswith("/"), f"pymol_path should be relative, got: {path}"
            assert not path.startswith("~"), f"pymol_path should not use home dir, got: {path}"
            
            # Verify the path is valid
            abs_path = dataset_dir / path
            assert abs_path.exists(), f"File should exist: {abs_path}"


@pytest.mark.skipif(
    not get_dataset_directory().exists(),
    reason="Dataset not available"
)
def test_search_by_uniprot_json_serializable(mcp_server):
    """Test that search_by_uniprot result is JSON serializable."""
    import json
    
    if not mcp_server.dataset_available or mcp_server.index is None:
        pytest.skip("Dataset or index not available")
    
    if "uniprot_ids" not in mcp_server.index.columns:
        pytest.skip("Index does not have UniProt IDs")
    
    result = mcp_server.search_by_uniprot("P02649")
    
    # Should be serializable to JSON
    json_str = json.dumps(result)
    assert len(json_str) > 0
    
    # Should be deserializable
    reconstructed = json.loads(json_str)
    assert reconstructed["uniprot_id"] == "P02649"
    assert reconstructed["count"] == result["count"]


@pytest.mark.skipif(
    not get_dataset_directory().exists(),
    reason="Dataset not available"
)
def test_search_by_gene_returns_relative_paths(mcp_server):
    """Test that search_by_gene also returns relative paths."""
    if not mcp_server.dataset_available or mcp_server.index is None:
        pytest.skip("Dataset or index not available")
    
    if "gene_symbols" not in mcp_server.index.columns:
        pytest.skip("Index does not have gene symbols")
    
    # Test with APOE gene
    result = mcp_server.search_by_gene("APOE")
    
    assert isinstance(result, dict)
    assert "structures" in result
    
    # If structures found, check paths are relative
    if result.get("count", 0) > 0:
        dataset_dir = Path(mcp_server.dataset_dir)
        
        for structure in result["structures"]:
            # Check paths are relative
            for path_key in ["interact_scores_path", "critical_residues_path", "pymol_path"]:
                if path_key in structure and structure[path_key]:
                    path = structure[path_key]
                    assert not path.startswith("/"), f"{path_key} should be relative, got: {path}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

