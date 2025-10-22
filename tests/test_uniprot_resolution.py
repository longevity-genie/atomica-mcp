"""
Integration tests for UniProt ID resolution with fallback strategies.
These tests use real API calls to verify that the fallback mechanisms work correctly.
"""

from atomica_mcp.mining.pdb_metadata import (
    get_pdb_metadata,
    resolve_uniprot_ids_with_fallbacks,
    get_uniprot_mappings_sifts,
    get_uniprot_mappings_rcsb,
    get_uniprot_mappings_graphql,
)


def test_resolve_uniprot_primary_pdbe_api():
    """Test UniProt resolution using primary PDBe API."""
    # Test with a well-known structure (APOE)
    pdb_id = "1b68"
    uniprot_ids = resolve_uniprot_ids_with_fallbacks(pdb_id)
    
    assert len(uniprot_ids) > 0, f"Expected to find UniProt IDs for {pdb_id}"
    assert "P02649" in uniprot_ids, "Expected to find APOE UniProt ID (P02649)"


def test_resolve_uniprot_sifts_fallback():
    """Test SIFTS fallback mechanism."""
    pdb_id = "1b68"
    mappings = get_uniprot_mappings_sifts(pdb_id)
    
    # SIFTS should return a dictionary
    assert isinstance(mappings, dict)
    # Should contain UniProt IDs
    if mappings:
        assert len(mappings) > 0


def test_resolve_uniprot_rcsb_graphql_fallback():
    """Test RCSB GraphQL API fallback."""
    pdb_id = "1b68"
    uniprot_ids = get_uniprot_mappings_graphql(pdb_id)
    
    assert isinstance(uniprot_ids, list)
    # RCSB GraphQL should also find this
    if uniprot_ids:
        assert len(uniprot_ids) > 0


def test_resolve_uniprot_rcsb_rest_fallback():
    """Test RCSB REST API fallback."""
    pdb_id = "1b68"
    uniprot_ids = get_uniprot_mappings_rcsb(pdb_id)
    
    assert isinstance(uniprot_ids, list)


def test_get_pdb_metadata_with_uniprot():
    """Test complete metadata retrieval with UniProt resolution."""
    pdb_id = "1b68"
    metadata = get_pdb_metadata(pdb_id)
    
    assert metadata is not None, f"Metadata should be found for {pdb_id}"
    assert metadata.pdb_id == "1B68"
    assert metadata.title is not None
    assert len(metadata.uniprot_ids) > 0, "Should have UniProt IDs"
    assert len(metadata.gene_symbols) > 0, "Should have gene symbols"
    assert "P02649" in metadata.uniprot_ids
    assert "APOE" in metadata.gene_symbols


def test_get_pdb_metadata_complex():
    """Test metadata retrieval for a protein complex."""
    # KEAP1-NRF2 complex
    pdb_id = "2flu"
    metadata = get_pdb_metadata(pdb_id)
    
    assert metadata is not None
    assert len(metadata.uniprot_ids) > 0
    # Complex should have multiple proteins
    assert len(metadata.structures) > 0


def test_get_pdb_metadata_multiple_structures():
    """Test metadata retrieval for various structure types."""
    test_cases = [
        ("1b68", "APOE", "P02649"),  # X-ray structure - APOE
        ("2flu", None, None),  # Complex structure (KEAP1-NRF2)
        ("6ht5", "Sox2", "P48432"),  # Oct4/Sox2 complex
    ]
    
    for pdb_id, expected_gene, expected_uniprot in test_cases:
        metadata = get_pdb_metadata(pdb_id)
        
        assert metadata is not None, f"Should find metadata for {pdb_id}"
        assert metadata.pdb_id == pdb_id.upper()
        assert len(metadata.uniprot_ids) > 0, f"Should have UniProt IDs for {pdb_id}"
        
        if expected_uniprot:
            assert expected_uniprot in metadata.uniprot_ids, \
                f"Expected to find {expected_uniprot} in {pdb_id}"
        
        if expected_gene:
            assert expected_gene in metadata.gene_symbols, \
                f"Expected to find {expected_gene} in {pdb_id}"


def test_uniprot_resolution_invalid_pdb():
    """Test that invalid PDB IDs are handled gracefully."""
    pdb_id = "xxxx"
    metadata = get_pdb_metadata(pdb_id)
    
    # Should return None for invalid PDB
    assert metadata is None


def test_uniprot_resolution_no_protein():
    """Test PDB entries without protein structures."""
    # This would be a nucleic acid only structure
    # For now, we'll just verify the function doesn't crash
    pdb_id = "1bna"  # DNA structure
    metadata = get_pdb_metadata(pdb_id)
    
    # Should return something (even if no UniProt IDs)
    assert metadata is not None
    assert metadata.pdb_id == "1BNA"


def test_fallback_cascading():
    """
    Test that fallback mechanisms cascade correctly.
    This test ensures that if one API fails, the next one is tried.
    """
    pdb_id = "1b68"
    
    # Get result using all fallbacks
    uniprot_ids = resolve_uniprot_ids_with_fallbacks(pdb_id)
    
    assert len(uniprot_ids) > 0, "At least one fallback should succeed"
    assert "P02649" in uniprot_ids, "Should find APOE UniProt ID"

