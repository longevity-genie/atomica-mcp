"""
Tests for organism name normalization and AnAge matching.

This test suite verifies that common typos, synonyms, and variants
in PDB organism names are correctly normalized and matched to AnAge entries.
"""
import pytest
from pathlib import Path
from pdb_mcp.pdb_utils import (
    load_anage_data,
    normalize_organism_name,
    classify_organism,
    get_project_data_dir,
)


@pytest.fixture(scope="module")
def anage_data():
    """Load AnAge data once for all tests."""
    data_dir = get_project_data_dir()
    anage_file = data_dir / "input" / "anage" / "anage_data.txt"
    return load_anage_data(anage_file)


class TestOrganismNormalization:
    """Test organism name normalization."""
    
    def test_typo_corrections(self):
        """Test that common typos are corrected."""
        assert normalize_organism_name("Home sapiens") == "homo sapiens"
        assert normalize_organism_name("Homo sapien") == "homo sapiens"
        assert normalize_organism_name("Drosophila melangaster") == "drosophila melanogaster"
    
    def test_common_name_to_scientific(self):
        """Test that common names are converted to scientific names."""
        assert normalize_organism_name("Balb/c mouse") == "mus musculus"
        assert normalize_organism_name("Buffalo rat") == "rattus norvegicus"
        assert normalize_organism_name("Baker's yeast") == "saccharomyces cerevisiae"
        assert normalize_organism_name("C57BL/6 mouse") == "mus musculus"
        assert normalize_organism_name("Wistar rat") == "rattus norvegicus"
    
    def test_historical_name_corrections(self):
        """Test that outdated scientific names are corrected."""
        assert normalize_organism_name("Bacillus coli") == "escherichia coli"
        assert normalize_organism_name("Bos bovis") == "bos taurus"
        assert normalize_organism_name("Micrococcus aureus") == "staphylococcus aureus"
        assert normalize_organism_name("Bacillus pestis") == "yersinia pestis"
    
    def test_strain_removal(self):
        """Test that strain identifiers are removed."""
        assert normalize_organism_name("Escherichia coli K-12") == "escherichia coli"
        assert normalize_organism_name("Bacillus subtilis 168") == "bacillus subtilis"
        assert normalize_organism_name("Thermus thermophilus ATCC 27634") == "thermus thermophilus"
        assert normalize_organism_name("Pseudomonas aeruginosa PA01") == "pseudomonas aeruginosa"
    
    def test_case_insensitive(self):
        """Test that normalization is case-insensitive."""
        assert normalize_organism_name("HOMO SAPIENS") == "homo sapiens"
        assert normalize_organism_name("Homo Sapiens") == "homo sapiens"
        assert normalize_organism_name("homo sapiens") == "homo sapiens"


class TestAnAgeClassification:
    """Test organism classification using AnAge database."""
    
    def test_human_variants(self, anage_data):
        """Test that human variants are correctly classified."""
        result = classify_organism("Home sapiens", anage_data)
        assert result["in_anage"] is True
        assert result["common_name"] == "Human"
        assert result["classification"] == "Mammalia"
    
    def test_mouse_strains(self, anage_data):
        """Test that mouse strains are correctly classified."""
        for variant in ["Balb/c mouse", "C57BL/6 mouse", "Swiss mouse"]:
            result = classify_organism(variant, anage_data)
            assert result["in_anage"] is True, f"Failed for {variant}"
            assert result["common_name"] == "House mouse"
            assert result["classification"] == "Mammalia"
    
    def test_rat_strains(self, anage_data):
        """Test that rat strains are correctly classified."""
        for variant in ["Buffalo rat", "Wistar rat", "Sprague-Dawley rat"]:
            result = classify_organism(variant, anage_data)
            assert result["in_anage"] is True, f"Failed for {variant}"
            assert result["common_name"] == "Norway rat"
            assert result["classification"] == "Mammalia"
    
    def test_model_organisms(self, anage_data):
        """Test common model organisms."""
        test_cases = [
            ("Drosophila melanogaster", "Fruit fly", "Insecta"),
            ("Drosophila melangaster", "Fruit fly", "Insecta"),  # typo version
            ("Caenorhabditis elegans", "Roundworm", "Chromadorea"),
            ("Saccharomyces cerevisiae", "Baker's yeast", "Saccharomycetes"),
            ("Baker's yeast", "Baker's yeast", "Saccharomycetes"),
            ("Escherichia coli", "Escherichia coli", "Gammaproteobacteria"),
            ("Bacillus coli", "Escherichia coli", "Gammaproteobacteria"),  # historical name
        ]
        
        for scientific_name, expected_common, expected_class in test_cases:
            result = classify_organism(scientific_name, anage_data)
            assert result["in_anage"] is True, f"Failed for {scientific_name}"
            assert result["common_name"] == expected_common
            assert result["classification"] == expected_class
    
    def test_strain_variants(self, anage_data):
        """Test that strain variants are matched to base species."""
        result = classify_organism("Escherichia coli K-12", anage_data)
        assert result["in_anage"] is True
        assert result["common_name"] == "Escherichia coli"
    
    def test_non_anage_organisms(self, anage_data):
        """Test that organisms not in AnAge are correctly identified."""
        non_anage = [
            "Arabidopsis thaliana",  # Plant
            "Mycobacterium tuberculosis",  # Bacterium not in AnAge
            "Pseudomonas aeruginosa",  # Bacterium not in AnAge
        ]
        
        for organism in non_anage:
            result = classify_organism(organism, anage_data)
            assert result["in_anage"] is False
            assert result["classification"] == "Unknown"


class TestPerformance:
    """Test the performance improvement."""
    
    def test_coverage_statistics(self, anage_data):
        """Verify that normalization significantly improves matching."""
        # Common organisms from PDB that previously failed to match
        previously_failed = [
            "Home sapiens",
            "Balb/c mouse",
            "Buffalo rat",
            "Drosophila melangaster",
            "Baker's yeast",
            "Bacillus coli",
            "Escherichia coli K-12",
            "Bos bovis",
        ]
        
        # All should now match
        matched = 0
        for organism in previously_failed:
            result = classify_organism(organism, anage_data)
            if result["in_anage"]:
                matched += 1
        
        # All should be matched now
        assert matched == len(previously_failed), \
            f"Only {matched}/{len(previously_failed)} organisms matched"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

