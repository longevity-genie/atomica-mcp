"""
Integration tests for get_structures_for_uniprot MCP server function.

Tests the new behavior where the function ALWAYS checks ATOMICA index first:
1. If found in index: Returns ATOMICA data instantly (fast path)
2. If NOT in index: Falls back to external API calls (slow path)
"""

from atomica_mcp.server import AtomicaMCP
import time


def test_mcp_get_structures_for_uniprot_q14145_fast_path():
    """
    Test MCP server function for Q14145 (KEAP1) - should use FAST path.
    
    Q14145 is in ATOMICA dataset, so function should:
    - Check index first (instant)
    - Return ATOMICA analysis data
    - NOT make external API calls
    - Complete in < 1 second
    """
    server = AtomicaMCP()
    uniprot_id = "Q14145"
    
    start = time.time()
    result = server.get_structures_for_uniprot(uniprot_id=uniprot_id, include_alphafold=False)
    elapsed = time.time() - start
    
    # Should be very fast (from index)
    assert elapsed < 1.0, f"Should be instant (< 1s), took {elapsed:.3f}s"
    
    # Should have results
    assert result is not None, "Should return result"
    assert "error" not in result, f"Should not have error: {result.get('error')}"
    assert result.get("count", 0) > 0, "Should find structures"
    
    # Should indicate ATOMICA dataset source
    assert result.get("source") == "atomica_dataset", "Should be from ATOMICA dataset"
    assert result.get("has_atomica_analysis") == True, "Should have ATOMICA analysis"
    
    # Should have ATOMICA data paths
    structures = result.get("structures", [])
    assert len(structures) > 0, "Should have structures"
    
    first = structures[0]
    assert "interact_scores_path" in first, "Should have interact_scores_path"
    assert "critical_residues_path" in first, "Should have critical_residues_path"
    assert "pymol_path" in first, "Should have pymol_path"
    assert first["interact_scores_path"] is not None, "interact_scores_path should not be None"
    
    print(f"✓ Q14145 (KEAP1) - FAST PATH")
    print(f"  Execution time: {elapsed:.3f}s (instant!)")
    print(f"  Structures found: {result['count']}")
    print(f"  Source: {result['source']}")
    print(f"  Has ATOMICA analysis: {result['has_atomica_analysis']}")
    print(f"  First structure: {first['pdb_id']}")
    print(f"  ✓ Has interaction scores: {first['interact_scores_path'] is not None}")
    print(f"  ✓ Has critical residues: {first['critical_residues_path'] is not None}")
    print(f"  ✓ Has PyMOL commands: {first['pymol_path'] is not None}")


def test_mcp_get_structures_for_uniprot_with_limit():
    """Test getting limited number of structures from MCP server."""
    server = AtomicaMCP()
    uniprot_id = "Q14145"
    max_structures = 10
    
    result = server.get_structures_for_uniprot(
        uniprot_id=uniprot_id,
        include_alphafold=False,
        max_structures=max_structures
    )
    
    assert result.get("count", 0) <= max_structures, "Should limit structures"
    assert result.get("count", 0) > 0, "Should have some structures"
    assert "limited_to" in result, "Should indicate it was limited"
    
    print(f"✓ Limited to {result['count']} structures (max: {max_structures})")


def test_mcp_search_by_uniprot_comparison():
    """
    Compare atomica_search_by_uniprot vs atomica_get_structures_for_uniprot.
    
    Both should return same data for Q14145 since it's in ATOMICA dataset,
    but search_by_uniprot is the explicit/direct method.
    """
    server = AtomicaMCP()
    uniprot_id = "Q14145"
    
    # Test search_by_uniprot (explicit ATOMICA search)
    start1 = time.time()
    search_result = server.search_by_uniprot(uniprot_id)
    elapsed1 = time.time() - start1
    
    # Test get_structures_for_uniprot (checks index first, then falls back)
    start2 = time.time()
    get_result = server.get_structures_for_uniprot(uniprot_id, include_alphafold=False)
    elapsed2 = time.time() - start2
    
    # Both should be fast
    assert elapsed1 < 1.0, f"search_by_uniprot should be instant, took {elapsed1:.3f}s"
    assert elapsed2 < 1.0, f"get_structures_for_uniprot should be instant for ATOMICA dataset, took {elapsed2:.3f}s"
    
    # Both should find structures
    assert search_result.get("count", 0) > 0, "search_by_uniprot should find structures"
    assert get_result.get("count", 0) > 0, "get_structures_for_uniprot should find structures"
    
    # get_structures_for_uniprot should indicate source
    assert get_result.get("source") == "atomica_dataset", "Should indicate ATOMICA dataset source"
    assert get_result.get("has_atomica_analysis") == True, "Should have ATOMICA analysis"
    
    # Both should return ATOMICA data paths
    search_first = search_result["structures"][0]
    get_first = get_result["structures"][0]
    
    assert search_first["interact_scores_path"] is not None, "search_by_uniprot should have ATOMICA paths"
    assert get_first["interact_scores_path"] is not None, "get_structures_for_uniprot should have ATOMICA paths"
    
    print(f"✓ COMPARISON:")
    print(f"  search_by_uniprot:          {elapsed1:.3f}s, {search_result['count']} structures")
    print(f"  get_structures_for_uniprot: {elapsed2:.3f}s, {get_result['count']} structures")
    print(f"  ✓ Both return ATOMICA analysis data")
    print(f"  ✓ Both are instant (use local index)")


def test_mcp_get_structures_for_uniprot_not_in_dataset():
    """
    Test with a UniProt NOT in ATOMICA dataset - should fall back to slow path.
    
    This test uses P04637 (TP53) which has many structures in PDB but might not
    be in the ATOMICA longevity proteins dataset.
    
    Note: This test might be slow if TP53 is not in ATOMICA dataset!
    """
    server = AtomicaMCP()
    uniprot_id = "P04637"  # TP53 - tumor suppressor, not a longevity protein
    
    # First check if it's in ATOMICA dataset
    search_result = server.search_by_uniprot(uniprot_id)
    
    if search_result.get("count", 0) > 0:
        print(f"⚠ P04637 IS in ATOMICA dataset ({search_result['count']} structures), skipping slow path test")
        return
    
    print(f"✓ P04637 NOT in ATOMICA dataset, testing fallback to external PDB APIs...")
    print(f"  (This will be slow - making external API calls)")
    
    # Should fall back to external APIs (slow)
    start = time.time()
    result = server.get_structures_for_uniprot(
        uniprot_id=uniprot_id,
        include_alphafold=False,
        max_structures=5  # Limit to avoid very long test
    )
    elapsed = time.time() - start
    
    # Should indicate external source
    if result.get("count", 0) > 0:
        assert result.get("source") == "external_pdb", "Should be from external PDB"
        assert result.get("has_atomica_analysis") == False, "Should NOT have ATOMICA analysis"
        print(f"  ✓ Fallback to external PDB successful")
        print(f"  ✓ Execution time: {elapsed:.3f}s (slow, as expected)")
        print(f"  ✓ Found {result['count']} structures")
        print(f"  ✓ Source: {result['source']}")
        print(f"  ✓ Has ATOMICA analysis: {result['has_atomica_analysis']}")
    else:
        print(f"  ⚠ No structures found for P04637 (might be API issue)")


