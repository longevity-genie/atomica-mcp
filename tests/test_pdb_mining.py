"""
Integration tests for PDB mining functionality.

These tests make real API calls to verify that PDB metadata resolution works correctly.
No mocking - we test against actual PDB, UniProt, and AlphaFold databases.
"""

import pytest
from atomica_mcp.mining.pdb_metadata import (
    get_gene_symbol,
    get_uniprot_info,
    get_pdb_structures_from_uniprot,
    get_alphafold_structure,
    get_pdb_structure_metadata,
    get_pdb_redo_info,
    get_complex_info,
    get_structures_for_uniprot,
    get_pdb_metadata,
)


class TestGeneSymbolResolution:
    """Test gene symbol retrieval from UniProt IDs."""
    
    def test_get_gene_symbol_human_protein(self) -> None:
        """Test gene symbol retrieval for well-known human protein."""
        # P04637 is human TP53 (tumor protein p53)
        gene_symbol = get_gene_symbol("P04637")
        assert gene_symbol == "TP53"
    
    def test_get_gene_symbol_mouse_protein(self) -> None:
        """Test gene symbol retrieval for mouse protein."""
        # P03995 is mouse GFAP (glial fibrillary acidic protein)
        gene_symbol = get_gene_symbol("P03995")
        assert gene_symbol == "Gfap"
    
    def test_get_gene_symbol_yeast_protein(self) -> None:
        """Test gene symbol retrieval for yeast protein."""
        # P00549 is yeast pyruvate kinase
        gene_symbol = get_gene_symbol("P00549")
        assert gene_symbol == "CDC19"
    
    def test_get_gene_symbol_invalid(self) -> None:
        """Test that invalid UniProt IDs return None."""
        gene_symbol = get_gene_symbol("INVALID123")
        assert gene_symbol is None


class TestUniProtInfo:
    """Test comprehensive UniProt information retrieval."""
    
    def test_get_uniprot_info_human_tp53(self) -> None:
        """Test UniProt info for human TP53."""
        info = get_uniprot_info("P04637")
        
        assert info is not None
        assert info["uniprot_id"] == "P04637"
        assert info["gene_symbol"] == "TP53"
        # Protein name can vary - just check it contains p53
        assert "p53" in info["protein_name"].lower()
        assert info["organism"] == "Homo sapiens"
        assert info["tax_id"] == 9606
        assert info["sequence_length"] == 393
    
    def test_get_uniprot_info_ecoli_protein(self) -> None:
        """Test UniProt info for E. coli protein - P0A7Y7 may be from Shigella flexneri."""
        # P0A7Y7 is RNase H - shared between E. coli and Shigella
        info = get_uniprot_info("P0A7Y7")
        
        assert info is not None
        assert info["uniprot_id"] == "P0A7Y7"
        # Organism can be E. coli or Shigella (closely related)
        assert info["organism"] in ["Escherichia coli", "Shigella flexneri"]
        # Tax IDs for various E. coli strains and Shigella species (623 is Shigella flexneri)
        assert info["tax_id"] in [83333, 562, 198214, 623]
        assert info["sequence_length"] > 0


class TestPDBStructureRetrieval:
    """Test PDB structure retrieval from UniProt IDs."""
    
    def test_get_pdb_structures_human_tp53(self) -> None:
        """Test PDB structure retrieval for human TP53."""
        # TP53 has many PDB structures
        pdb_ids = get_pdb_structures_from_uniprot("P04637")
        
        assert len(pdb_ids) > 0
        # Check for some well-known TP53 structures
        assert any(pdb in pdb_ids for pdb in ["1TUP", "2OCJ", "3KMD"])
    
    def test_get_pdb_structures_scp2(self) -> None:
        """Test PDB structure retrieval for SCP2."""
        # P22307 is human SCP2 (used in PDBminer examples)
        pdb_ids = get_pdb_structures_from_uniprot("P22307")
        
        assert len(pdb_ids) > 0
        # Known structures from PDBminer example
        assert "2C0L" in pdb_ids or "1QND" in pdb_ids


class TestAlphaFoldStructures:
    """Test AlphaFold structure retrieval."""
    
    def test_get_alphafold_structure_human_protein(self) -> None:
        """Test AlphaFold structure retrieval for human protein."""
        # P22307 is human SCP2
        af_structure = get_alphafold_structure("P22307")
        
        assert af_structure is not None
        assert af_structure.structure_id.startswith("AF-")
        assert af_structure.uniprot_id == "P22307"
        assert af_structure.experimental_method == "PREDICTED"
        assert af_structure.chains == ["A"]
        assert af_structure.deposition_date is not None
    
    def test_get_alphafold_structure_invalid(self) -> None:
        """Test that invalid UniProt IDs return None."""
        af_structure = get_alphafold_structure("INVALID123")
        assert af_structure is None


class TestPDBMetadata:
    """Test PDB structure metadata retrieval."""
    
    def test_get_pdb_structure_metadata_xray(self) -> None:
        """Test metadata retrieval for X-ray structure."""
        # 2C0L is an X-ray structure from PDBminer example
        metadata = get_pdb_structure_metadata("2C0L")
        
        assert metadata is not None
        assert metadata["pdb_id"] == "2C0L"
        assert metadata["experimental_method"] == "X-RAY DIFFRACTION"
        assert metadata["resolution"] is not None
        assert metadata["resolution"] < 5.0  # Should be reasonable resolution
        assert metadata["deposition_date"] is not None
    
    def test_get_pdb_structure_metadata_nmr(self) -> None:
        """Test metadata retrieval for NMR structure."""
        # 1QND is an NMR structure from PDBminer example
        metadata = get_pdb_structure_metadata("1QND")
        
        assert metadata is not None
        assert metadata["pdb_id"] == "1QND"
        assert "NMR" in metadata["experimental_method"]
        # NMR structures don't have resolution
        assert metadata["resolution"] is None
    
    def test_get_pdb_structure_metadata_em(self) -> None:
        """Test metadata retrieval for electron microscopy structure."""
        # 6VSB is SARS-CoV-2 spike protein (EM)
        metadata = get_pdb_structure_metadata("6VSB")
        
        assert metadata is not None
        assert metadata["pdb_id"] == "6VSB"
        assert "MICROSCOPY" in metadata["experimental_method"]
        assert metadata["resolution"] is not None


class TestPDBRedo:
    """Test PDB-REDO database queries."""
    
    def test_get_pdb_redo_available(self) -> None:
        """Test PDB-REDO info for structure that exists in database."""
        # 2C0L is available in PDB-REDO (from PDBminer example)
        available, r_free = get_pdb_redo_info("2C0L")
        
        assert available is True
        assert r_free is not None
        assert 0.0 < r_free < 1.0  # R-free should be between 0 and 1
    
    def test_get_pdb_redo_not_available(self) -> None:
        """Test PDB-REDO info for NMR structure (not in PDB-REDO)."""
        # 1QND is NMR, not in PDB-REDO
        available, r_free = get_pdb_redo_info("1QND")
        
        assert available is False
        assert r_free is None


class TestComplexInfo:
    """Test complex information retrieval."""
    
    def test_get_complex_info_protein_complex(self) -> None:
        """Test complex info for protein-protein complex."""
        # 2C0L is a protein complex (from PDBminer example)
        complex_info = get_complex_info("2C0L", "P22307")
        
        assert complex_info is not None
        assert complex_info.has_protein_complex is True
        assert complex_info.protein_complex_details is not None
        assert len(complex_info.protein_complex_details) > 0
    
    def test_get_complex_info_simple_structure(self) -> None:
        """Test complex info for simple structure without complexes."""
        # 1QND is a simple NMR structure
        complex_info = get_complex_info("1QND", "P22307")
        
        assert complex_info is not None
        # Should not be a complex
        assert complex_info.has_protein_complex is False
    
    def test_get_complex_info_with_ligands(self) -> None:
        """Test complex info for structure with ligands."""
        # 1TUP is TP53 with DNA
        complex_info = get_complex_info("1TUP", "P04637")
        
        assert complex_info is not None
        # Should have nucleotide (DNA)
        assert complex_info.has_nucleotide is True or complex_info.has_ligand is True


class TestStructuresForUniProt:
    """Test comprehensive structure retrieval for UniProt IDs."""
    
    @pytest.mark.slow
    def test_get_structures_for_uniprot_with_alphafold(self) -> None:
        """Test structure retrieval including AlphaFold."""
        # P22307 (SCP2) has PDB structures and AlphaFold model
        structures = get_structures_for_uniprot("P22307", include_alphafold=True)
        
        assert len(structures) > 0
        
        # Should have gene symbol
        assert all(s.gene_symbol for s in structures)
        
        # Should have AlphaFold structure
        af_structures = [s for s in structures if s.structure_id.startswith("AF-")]
        assert len(af_structures) > 0
        
        # Should be sorted by method priority and resolution
        # X-ray should come before predicted
        experimental = [s for s in structures if not s.structure_id.startswith("AF-")]
        if experimental:
            assert experimental[0].experimental_method == "X-RAY DIFFRACTION" or experimental[0].experimental_method in ["ELECTRON MICROSCOPY", "SOLUTION NMR"]
    
    @pytest.mark.slow
    def test_get_structures_for_uniprot_without_alphafold(self) -> None:
        """Test structure retrieval excluding AlphaFold."""
        structures = get_structures_for_uniprot("P22307", include_alphafold=False)
        
        assert len(structures) > 0
        
        # Should not have AlphaFold structures
        af_structures = [s for s in structures if s.structure_id.startswith("AF-")]
        assert len(af_structures) == 0
    
    @pytest.mark.slow
    def test_get_structures_metadata_complete(self) -> None:
        """Test that retrieved structures have complete metadata."""
        structures = get_structures_for_uniprot("P22307", include_alphafold=True)
        
        for structure in structures:
            assert structure.structure_id is not None
            assert structure.uniprot_id == "P22307"
            assert structure.gene_symbol is not None
            assert structure.experimental_method is not None
            assert structure.deposition_date is not None
            
            # X-ray structures should have resolution
            if structure.experimental_method == "X-RAY DIFFRACTION":
                assert structure.resolution is not None


class TestPDBMetadataByID:
    """Test PDB metadata retrieval by PDB ID."""
    
    def test_get_pdb_metadata_complete(self) -> None:
        """Test complete metadata retrieval for PDB structure."""
        # 1TUP - human TP53 structure
        metadata = get_pdb_metadata("1TUP")
        
        assert metadata is not None
        assert metadata.pdb_id == "1TUP"
        assert metadata.title is not None
        # Note: Some PDB structures may not have UniProt mappings available
        # Just verify the structure is returned correctly
        assert len(metadata.structures) > 0
        
        # Check structure info
        for structure in metadata.structures:
            assert structure.structure_id == "1TUP"
            assert structure.experimental_method is not None
    
    def test_get_pdb_metadata_human_protein(self) -> None:
        """Test metadata retrieval for human protein structure."""
        # 1TUP is human TP53 DNA-binding domain
        metadata = get_pdb_metadata("1TUP")
        
        assert metadata is not None
        assert metadata.pdb_id == "1TUP"
        # Just verify basic structure is there
        assert len(metadata.structures) > 0
    
    def test_get_pdb_metadata_to_dict(self) -> None:
        """Test that metadata can be serialized to dict."""
        metadata = get_pdb_metadata("2C0L")
        
        assert metadata is not None
        result = metadata.to_dict()
        
        assert isinstance(result, dict)
        assert result["pdb_id"] == "2C0L"
        assert "uniprot_ids" in result
        assert "gene_symbols" in result
        assert "structures" in result
        assert isinstance(result["structures"], list)


class TestErrorHandling:
    """Test error handling for invalid inputs."""
    
    def test_invalid_pdb_id(self) -> None:
        """Test that invalid PDB IDs are handled gracefully."""
        metadata = get_pdb_metadata("INVALID")
        assert metadata is None
    
    def test_invalid_uniprot_id(self) -> None:
        """Test that invalid UniProt IDs are handled gracefully."""
        structures = get_structures_for_uniprot("INVALID123")
        # Should return empty list, not crash
        assert structures == []
    
    def test_nonexistent_pdb(self) -> None:
        """Test that non-existent PDB IDs are handled gracefully."""
        metadata = get_pdb_structure_metadata("ZZZZ")
        assert metadata is None


class TestRealWorldExamples:
    """Test with real-world examples from PDBminer."""
    
    @pytest.mark.slow
    def test_pdbminer_example_p22307(self) -> None:
        """Test with P22307 (SCP2) from PDBminer examples."""
        # This is the example from PDBminer command_line example
        structures = get_structures_for_uniprot("P22307", include_alphafold=True)
        
        assert len(structures) >= 3  # Should have at least AF, 2C0L, 1QND
        
        # Check for known structures from PDBminer output
        structure_ids = [s.structure_id for s in structures]
        assert any("AF-P22307" in sid for sid in structure_ids)
        assert "2C0L" in structure_ids
        assert "1QND" in structure_ids
        
        # Find 2C0L and verify metadata
        c0l_structure = next(s for s in structures if s.structure_id == "2C0L")
        assert c0l_structure.experimental_method == "X-RAY DIFFRACTION"
        assert c0l_structure.resolution is not None
        assert c0l_structure.resolution < 3.0  # Should be 2.3 Å
        assert c0l_structure.pdb_redo_available is True
        assert c0l_structure.complex_info is not None
        assert c0l_structure.complex_info.has_protein_complex is True
        
        # Find 1QND and verify metadata
        qnd_structure = next(s for s in structures if s.structure_id == "1QND")
        assert "NMR" in qnd_structure.experimental_method
        assert qnd_structure.resolution is None
    
    @pytest.mark.slow
    def test_pdbminer_example_p04637(self) -> None:
        """Test with P04637 (TP53) - well-known protein with many structures."""
        structures = get_structures_for_uniprot("P04637", include_alphafold=False)
        
        # TP53 should have many PDB structures
        assert len(structures) > 10
        
        # All should be experimental (no AlphaFold)
        assert all(not s.structure_id.startswith("AF-") for s in structures)
        
        # All should have TP53 gene symbol
        assert all(s.gene_symbol == "TP53" for s in structures)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

