#!/usr/bin/env python3
"""
Example: How to use atomica_search_by_uniprot results

This script demonstrates how to:
1. Search for structures by UniProt ID
2. Construct absolute paths from the relative paths in the response
3. Read and process the ATOMICA analysis files
"""

from pathlib import Path
from atomica_mcp.server import AtomicaMCP

def main():
    # Initialize the MCP server
    mcp = AtomicaMCP()
    
    # Search for P02649 (APOE protein)
    print("Searching for APOE protein (P02649)...")
    result = mcp.search_by_uniprot("P02649")
    
    print(f"Found {result['count']} structures")
    print(f"Dataset directory: {result['dataset_directory']}")
    print()
    
    # Get the dataset directory
    dataset_dir = Path(result['dataset_directory'])
    
    # Process each structure
    for structure in result['structures']:
        pdb_id = structure['pdb_id']
        print(f"Structure: {pdb_id}")
        print(f"  Title: {structure.get('title', 'N/A')}")
        print(f"  Genes: {', '.join(structure.get('gene_symbols', []))}")
        
        # Construct absolute paths
        interact_scores_file = dataset_dir / structure['interact_scores_path']
        critical_residues_file = dataset_dir / structure['critical_residues_path']
        pymol_file = dataset_dir / structure['pymol_path']
        
        # Verify files exist
        print(f"  Files:")
        print(f"    Interaction scores: {interact_scores_file} ({'✓' if interact_scores_file.exists() else '✗'})")
        print(f"    Critical residues: {critical_residues_file} ({'✓' if critical_residues_file.exists() else '✗'})")
        print(f"    PyMOL commands: {pymol_file} ({'✓' if pymol_file.exists() else '✗'})")
        
        # Example: Read critical residues
        if critical_residues_file.exists():
            with open(critical_residues_file, 'r') as f:
                lines = [line for line in f if line.strip() and not line.startswith('#')]
                print(f"    Critical residues count: {len(lines)}")
        
        print()

if __name__ == "__main__":
    main()

