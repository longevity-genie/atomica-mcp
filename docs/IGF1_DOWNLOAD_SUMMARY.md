# IGF1 PDB Structures Download

## Summary

Successfully downloaded two key IGF1 PDB structures to `data/output/pdbs/`:

### 1. **Best IGF1 Model: 1TGR.pdb** (115 KB)
- **PDB ID:** 1TGR
- **Resolution:** 1.42 Ångströms (highest resolution)
- **Method:** X-ray crystallography
- **Content:** Mini-IGF-1 structure
- **Description:** Crystal structure of mini-IGF-1 with engineered mutations
- **Chains:** A, B (residues 1-52)

### 2. **IGF1 + Receptor Complex: 4XSS.pdb** (555 KB)
- **PDB ID:** 4XSS
- **Resolution:** 3.00 Ångströms
- **Method:** X-ray crystallography
- **Content:** IGF1 bound to a hybrid insulin/IGF1 receptor
- **Description:** Insulin-like growth factor I in complex with site 1 of a hybrid insulin receptor/type 1 insulin-like growth factor receptor
- **Chains:**
  - B: IGF1 (residues 49-118)
  - E: Insulin receptor (residues 28-377)
  - F: IGF1R alpha-CT peptide (residues 691-706)

## Usage

### Using the Python Module

```python
from pdb_mcp.download_igf1_pdbs import download_igf1_pdbs

# Download structures to default location (data/output/pdbs/)
files = download_igf1_pdbs()

# Or specify custom output directory
from pathlib import Path
files = download_igf1_pdbs(output_dir=Path("/path/to/output"))

print(files)
# Output:
# {
#     'best_igf1_model': PosixPath('/home/...../data/output/pdbs/1TGR.pdb'),
#     'igf1_receptor_complex': PosixPath('/home/...../data/output/pdbs/4XSS.pdb')
# }
```

### Using Command Line

```bash
# Download to default location
uv run python -m pdb_mcp.download_igf1_pdbs

# Download to custom location
uv run python -m pdb_mcp.download_igf1_pdbs
```

## Files Downloaded

```
data/output/pdbs/
├── 1TGR.pdb    (115 KB) - Best IGF1 model
└── 4XSS.pdb    (555 KB) - IGF1 + Receptor complex
```

## Structure Information

### 1TGR - Best for Visualization
- **Best for:** Structural analysis of IGF1 backbone
- **Resolution:** Highest among all IGF1 structures
- **Use case:** Understanding IGF1 fold and domain organization

### 4XSS - Best for Functional Analysis
- **Best for:** Understanding IGF1-receptor binding
- **Resolution:** Good resolution for complex structures
- **Use case:** Studying IGF1 activation of growth factor signaling
- **Key interactions:** IGF1-IR binding site, receptor conformation changes

## Related Structures

For reference, these other IGF1 complex structures are also available:

| PDB ID | Type | Resolution | Features |
|--------|------|-----------|----------|
| 7WRQ | IGF1/IGFBP3/ALS | 3.60 Å | Ternary complex with binding proteins |
| 5U8Q | IGF1/IGF1R | 3.27 Å | Full receptor complex |
| 1WQJ | IGF1/Integrin | 1.60 Å | Highest resolution integrin binding |
| 2DSP | IGF1/Integrin | 2.50 Å | Integrin binding site |

## References

- **1TGR:** Structural basis for IGF1 fold and domain organization
- **4XSS:** IGF1 signaling mechanism through receptor activation
