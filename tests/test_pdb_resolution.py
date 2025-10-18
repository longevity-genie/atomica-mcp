"""
Integration tests for PDB resolution with real data.

Tests use actual AnAge data and known PDB IDs to verify:
- TSV-based resolution (when annotations are available)
- API fallback (when TSV data is not available)
- Organism classification
- Chain information extraction
- UniProt ID resolution
"""
import pytest
from pathlib import Path
from pdb_mcp import (
    load_anage_data,
    load_pdb_annotations,
    fetch_pdb_metadata,
    get_chain_organism,
    parse_entry_id,
    classify_organism,
)


# Known test PDB IDs with expected organisms
TEST_PDBS = {
    "2uxq": {
        "title_contains": "Human",  # Should contain human-related info
        "organisms": ["Homo sapiens"],
    },
    "1mbn": {
        "title_contains": "Myoglobin",
        "organisms": ["Equus caballus"],  # Sperm whale myoglobin or horse
    },
}


@pytest.fixture(scope="session")
def anage_data():
    """Load AnAge database once per test session."""
    anage_file = Path(__file__).parent.parent / "data" / "input" / "anage" / "anage_data.txt"
    
    if not anage_file.exists():
        pytest.skip(f"AnAge data not found at {anage_file}")
    
    return load_anage_data(anage_file)


@pytest.fixture(scope="session")
def pdb_annotations_available():
    """Check if PDB annotations are available."""
    annotations_dir = Path(__file__).parent.parent / "data" / "input" / "pdb"
    return annotations_dir.exists() and len(list(annotations_dir.glob("*.tsv.gz"))) > 0


@pytest.fixture(scope="session")
def load_pdb_data(pdb_annotations_available):
    """Load PDB annotations if available."""
    if pdb_annotations_available:
        annotations_dir = Path(__file__).parent.parent / "data" / "input" / "pdb"
        load_pdb_annotations(annotations_dir)
        return True
    return False


class TestAnAgeData:
    """Tests for AnAge data loading and functionality."""
    
    def test_anage_data_loaded(self, anage_data):
        """Test that AnAge data loaded successfully."""
        assert len(anage_data) > 0, "AnAge data should not be empty"
        assert "homo sapiens" in anage_data, "Homo sapiens should be in AnAge"
    
    def test_anage_homo_sapiens(self, anage_data):
        """Test Homo sapiens entry in AnAge."""
        homo_sapiens = anage_data["homo sapiens"]
        
        assert homo_sapiens["scientific_name"] == "Homo sapiens"
        assert homo_sapiens["common_name"] == "Human"
        assert homo_sapiens["class"] == "Mammalia"
        assert homo_sapiens["kingdom"] == "Animalia"
    
    def test_anage_mouse(self, anage_data):
        """Test Mus musculus (mouse) entry in AnAge."""
        if "mus musculus" not in anage_data:
            pytest.skip("Mus musculus not in AnAge data")
        
        mouse = anage_data["mus musculus"]
        assert mouse["scientific_name"] == "Mus musculus"
        assert "mouse" in mouse["common_name"].lower()  # Could be "Mouse" or "House mouse"
        assert mouse["class"] == "Mammalia"
    
    def test_classify_organism_known(self, anage_data):
        """Test organism classification for known organism."""
        result = classify_organism("Homo sapiens", anage_data)
        
        assert result["in_anage"] is True
        assert result["classification"] == "Mammalia"
        assert result["common_name"] == "Human"
        assert result["max_longevity_yrs"] is not None
    
    def test_classify_organism_unknown(self, anage_data):
        """Test organism classification for unknown organism."""
        result = classify_organism("Unknown species xyz", anage_data)
        
        assert result["in_anage"] is False
        assert result["classification"] == "Unknown"


class TestEntryIDParsing:
    """Tests for entry ID parsing."""
    
    def test_parse_entry_id_full(self):
        """Test parsing entry ID with both chains."""
        result = parse_entry_id("2uxq_2_A_B")
        
        assert result["pdb_id"] == "2uxq"
        assert result["chain1"] == "A"
        assert result["chain2"] == "B"
    
    def test_parse_entry_id_single_chain(self):
        """Test parsing entry ID with single chain."""
        result = parse_entry_id("2uxq_1_A")
        
        assert result["pdb_id"] == "2uxq"
        assert result["chain1"] == "A"
        assert result["chain2"] == ""
    
    def test_parse_entry_id_lowercase(self):
        """Test that PDB ID is normalized to lowercase."""
        result = parse_entry_id("2UXQ_1_A")
        
        assert result["pdb_id"] == "2uxq"


class TestPDBResolutionWithFallback:
    """Integration tests for PDB resolution with TSV and API fallback."""
    
    @pytest.mark.parametrize("pdb_id", list(TEST_PDBS.keys()))
    def test_pdb_api_resolution(self, pdb_id):
        """Test PDB resolution using RCSB API (always available)."""
        metadata = fetch_pdb_metadata(pdb_id, use_tsv=False, timeout=10)
        
        assert metadata["found"] is True, f"PDB {pdb_id} should be found"
        assert metadata["pdb_id"] == pdb_id
        assert "entities" in metadata
        assert len(metadata["entities"]) > 0
    
    @pytest.mark.parametrize("pdb_id", list(TEST_PDBS.keys()))
    def test_pdb_metadata_structure(self, pdb_id):
        """Test that metadata has expected structure."""
        metadata = fetch_pdb_metadata(pdb_id, use_tsv=False)
        
        assert "found" in metadata
        assert "pdb_id" in metadata
        assert "entities" in metadata
        
        for entity in metadata["entities"]:
            assert "entity_id" in entity
            assert "chains" in entity
            assert "organism" in entity
            assert "uniprot_ids" in entity
    
    @pytest.mark.parametrize("pdb_id", list(TEST_PDBS.keys()))
    def test_pdb_organism_info(self, pdb_id, anage_data):
        """Test that organism information is extracted."""
        metadata = fetch_pdb_metadata(pdb_id, use_tsv=False)
        
        assert metadata["found"] is True
        
        for entity in metadata["entities"]:
            for chain_id in entity["chains"]:
                organism = get_chain_organism(metadata, chain_id, anage_data)
                
                assert "scientific_name" in organism
                assert organism["scientific_name"] != ""
                assert "taxonomy_id" in organism
                assert "in_anage" in organism
    
    def test_pdb_tsv_resolution_if_available(self, load_pdb_data, anage_data):
        """Test TSV-based resolution if annotations are available."""
        if not load_pdb_data:
            pytest.skip("PDB annotations not available")
        
        # Test with a known PDB
        pdb_id = "2uxq"
        metadata = fetch_pdb_metadata(pdb_id, use_tsv=True)
        
        # Should either find it in TSV or fall back
        if metadata["found"]:
            assert metadata["source"] == "TSV"
            assert len(metadata["entities"]) > 0
            
            # Verify organisms can be classified
            for entity in metadata["entities"]:
                for chain_id in entity["chains"]:
                    organism = get_chain_organism(metadata, chain_id, anage_data)
                    assert "scientific_name" in organism
    
    def test_pdb_fallback_chain(self, load_pdb_data, anage_data):
        """Test that TSV falls back to API if needed."""
        if not load_pdb_data:
            pytest.skip("PDB annotations not available, skipping fallback test")
        
        # This tests the fallback mechanism
        pdb_id = "2uxq"
        
        # Try TSV first
        tsv_metadata = fetch_pdb_metadata(pdb_id, use_tsv=True)
        
        # Try API
        api_metadata = fetch_pdb_metadata(pdb_id, use_tsv=False)
        
        # Both should find the PDB
        assert tsv_metadata["found"] is True
        assert api_metadata["found"] is True
        
        # PDB IDs should match
        assert tsv_metadata["pdb_id"] == api_metadata["pdb_id"]


class TestPDBWithAnAgeIntegration:
    """Full integration tests with AnAge data."""
    
    def test_human_protein_in_anage(self, anage_data):
        """Test resolving human proteins with AnAge classification."""
        # Fetch a known human protein
        metadata = fetch_pdb_metadata("2uxq", use_tsv=False)
        
        assert metadata["found"] is True
        
        # Check organism classification with AnAge
        for entity in metadata["entities"]:
            for chain_id in entity["chains"]:
                organism = get_chain_organism(metadata, chain_id, anage_data)
                
                # Should be recognized if human
                if organism["scientific_name"].lower() == "homo sapiens":
                    assert organism["in_anage"] is True
                    assert organism["classification"] == "Mammalia"
    
    def test_pdb_chain_organism_classification(self, anage_data):
        """Test that chain organisms are properly classified."""
        pdb_id = "2uxq"
        metadata = fetch_pdb_metadata(pdb_id, use_tsv=False)
        
        if not metadata["found"]:
            pytest.skip(f"Could not fetch {pdb_id}")
        
        # Get organisms for each chain
        organisms_found = []
        for entity in metadata["entities"]:
            for chain_id in entity["chains"]:
                organism = get_chain_organism(metadata, chain_id, anage_data)
                organisms_found.append(organism)
        
        assert len(organisms_found) > 0
        
        # At least one should have organism info
        non_unknown = [o for o in organisms_found if o["scientific_name"] != "Unknown"]
        assert len(non_unknown) > 0, "Should have at least one non-unknown organism"


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_invalid_pdb_id(self):
        """Test handling of invalid PDB ID."""
        metadata = fetch_pdb_metadata("XXXX", use_tsv=False)
        
        assert metadata["found"] is False
    
    def test_classify_empty_organism(self, anage_data):
        """Test classification of empty organism name."""
        result = classify_organism("", anage_data)
        
        assert result["in_anage"] is False
    
    def test_parse_malformed_entry_id(self):
        """Test parsing malformed entry ID."""
        result = parse_entry_id("malformed")
        
        assert "pdb_id" in result
        assert result["pdb_id"] == "malformed"
        assert result["chain1"] == ""
