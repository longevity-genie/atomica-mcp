"""
Command-line interface for PDB mining operations.

Provides CLI commands for:
- Retrieving metadata by PDB ID
- Finding structures for UniProt IDs  
- Batch processing multiple identifiers
"""

import json
import sys
from pathlib import Path
from typing import Optional, List
import typer
from eliot import to_file, start_action
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from atomica_mcp.mining.pdb_metadata import (
    get_pdb_metadata,
    get_structures_for_uniprot,
    get_gene_symbol,
    get_uniprot_info,
)

app = typer.Typer(
    name="pdb-mining",
    help="PDB structure metadata mining tools with comprehensive logging and retry logic.",
    add_completion=False,
)
console = Console()


def setup_logging(log_file: Optional[Path] = None) -> None:
    """Setup eliot logging to file."""
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        to_file(open(log_file, "w"))


@app.command(name="pdb")
def get_pdb(
    pdb_id: str = typer.Argument(..., help="PDB identifier (e.g., 2C0L)"),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output", help="Output JSON file path"
    ),
    log_file: Optional[Path] = typer.Option(
        None, "-l", "--log", help="Log file path for eliot logs"
    ),
    pretty: bool = typer.Option(
        True, "--pretty/--no-pretty", help="Pretty print JSON output"
    ),
) -> None:
    """
    Get comprehensive metadata for a PDB structure by its ID.
    
    Retrieves:
    - UniProt IDs and gene symbols
    - Experimental method and resolution
    - Complex information (protein-protein, ligands, nucleotides)
    - PDB-REDO availability
    - Organism information
    
    Example:
        pdb-mining pdb 2C0L -o 2c0l_metadata.json
    """
    setup_logging(log_file)
    
    with start_action(action_type="cli_get_pdb", pdb_id=pdb_id):
        with console.status(f"[bold green]Fetching metadata for PDB {pdb_id}..."):
            metadata = get_pdb_metadata(pdb_id)
        
        if not metadata:
            console.print(f"[red]Error:[/red] Could not retrieve metadata for PDB {pdb_id}")
            raise typer.Exit(1)
        
        # Convert to dict for output
        result = metadata.to_dict()
        
        # Output to file or stdout
        if output:
            with open(output, "w") as f:
                json.dump(result, f, indent=2 if pretty else None)
            console.print(f"[green]✓[/green] Metadata saved to {output}")
        else:
            if pretty:
                rprint(json.dumps(result, indent=2))
            else:
                print(json.dumps(result))
        
        # Display summary table
        table = Table(title=f"PDB {pdb_id} Summary")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Title", metadata.title or "N/A")
        table.add_row("UniProt IDs", ", ".join(metadata.uniprot_ids) if metadata.uniprot_ids else "N/A")
        table.add_row("Gene Symbols", ", ".join(metadata.gene_symbols) if metadata.gene_symbols else "N/A")
        table.add_row("Organism", metadata.organism or "N/A")
        table.add_row("Structures", str(len(metadata.structures)))
        
        console.print(table)


@app.command(name="uniprot")
def get_uniprot(
    uniprot_id: str = typer.Argument(..., help="UniProt accession (e.g., P22307)"),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output", help="Output JSON file path"
    ),
    log_file: Optional[Path] = typer.Option(
        None, "-l", "--log", help="Log file path for eliot logs"
    ),
    no_alphafold: bool = typer.Option(
        False, "--no-alphafold", help="Exclude AlphaFold structures"
    ),
    pretty: bool = typer.Option(
        True, "--pretty/--no-pretty", help="Pretty print JSON output"
    ),
) -> None:
    """
    Get all structures for a UniProt ID with comprehensive metadata.
    
    Retrieves:
    - All PDB structures
    - AlphaFold model (unless --no-alphafold)
    - Experimental methods and resolutions
    - Complex information
    - Gene symbols
    
    Results are sorted by experimental method priority and resolution.
    
    Example:
        pdb-mining uniprot P22307 -o p22307_structures.json
    """
    setup_logging(log_file)
    
    with start_action(action_type="cli_get_uniprot", uniprot_id=uniprot_id):
        with console.status(f"[bold green]Fetching structures for UniProt {uniprot_id}..."):
            structures = get_structures_for_uniprot(
                uniprot_id, 
                include_alphafold=not no_alphafold
            )
        
        if not structures:
            console.print(f"[red]Error:[/red] No structures found for UniProt {uniprot_id}")
            raise typer.Exit(1)
        
        # Convert to dict for output
        result = {
            "uniprot_id": uniprot_id,
            "structure_count": len(structures),
            "structures": [s.to_dict() for s in structures],
        }
        
        # Output to file or stdout
        if output:
            with open(output, "w") as f:
                json.dump(result, f, indent=2 if pretty else None)
            console.print(f"[green]✓[/green] Structures saved to {output}")
        else:
            if pretty:
                rprint(json.dumps(result, indent=2))
            else:
                print(json.dumps(result))
        
        # Display summary table
        table = Table(title=f"UniProt {uniprot_id} Structures")
        table.add_column("Rank", style="cyan")
        table.add_column("Structure ID", style="yellow")
        table.add_column("Method", style="white")
        table.add_column("Resolution", style="white")
        table.add_column("Complex", style="magenta")
        
        for i, structure in enumerate(structures[:10], 1):  # Show top 10
            resolution = f"{structure.resolution:.2f}" if structure.resolution else "N/A"
            complex_str = ""
            if structure.complex_info:
                parts = []
                if structure.complex_info.has_protein_complex:
                    parts.append("Protein")
                if structure.complex_info.has_nucleotide:
                    parts.append("Nucleotide")
                if structure.complex_info.has_ligand:
                    parts.append("Ligand")
                complex_str = ", ".join(parts) if parts else "None"
            else:
                complex_str = "N/A"
            
            table.add_row(
                str(i),
                structure.structure_id,
                structure.experimental_method or "N/A",
                resolution,
                complex_str,
            )
        
        if len(structures) > 10:
            console.print(f"\n[dim]Showing top 10 of {len(structures)} structures[/dim]")
        
        console.print(table)


@app.command(name="gene")
def get_gene(
    uniprot_id: str = typer.Argument(..., help="UniProt accession (e.g., P22307)"),
    log_file: Optional[Path] = typer.Option(
        None, "-l", "--log", help="Log file path for eliot logs"
    ),
) -> None:
    """
    Get gene symbol for a UniProt ID.
    
    Example:
        pdb-mining gene P22307
    """
    setup_logging(log_file)
    
    with start_action(action_type="cli_get_gene", uniprot_id=uniprot_id):
        gene_symbol = get_gene_symbol(uniprot_id)
        
        if gene_symbol:
            console.print(f"[green]✓[/green] {uniprot_id} → {gene_symbol}")
        else:
            console.print(f"[red]✗[/red] No gene symbol found for {uniprot_id}")
            raise typer.Exit(1)


@app.command(name="info")
def get_info(
    uniprot_id: str = typer.Argument(..., help="UniProt accession (e.g., P22307)"),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output", help="Output JSON file path"
    ),
    log_file: Optional[Path] = typer.Option(
        None, "-l", "--log", help="Log file path for eliot logs"
    ),
    pretty: bool = typer.Option(
        True, "--pretty/--no-pretty", help="Pretty print JSON output"
    ),
) -> None:
    """
    Get comprehensive UniProt information.
    
    Retrieves:
    - Protein name
    - Gene symbol
    - Organism
    - Taxonomy ID
    - Sequence length
    
    Example:
        pdb-mining info P22307
    """
    setup_logging(log_file)
    
    with start_action(action_type="cli_get_info", uniprot_id=uniprot_id):
        with console.status(f"[bold green]Fetching info for UniProt {uniprot_id}..."):
            info = get_uniprot_info(uniprot_id)
        
        if not info:
            console.print(f"[red]Error:[/red] Could not retrieve info for UniProt {uniprot_id}")
            raise typer.Exit(1)
        
        # Output to file or stdout
        if output:
            with open(output, "w") as f:
                json.dump(info, f, indent=2 if pretty else None)
            console.print(f"[green]✓[/green] Info saved to {output}")
        else:
            if pretty:
                rprint(json.dumps(info, indent=2))
            else:
                print(json.dumps(info))
        
        # Display summary table
        table = Table(title=f"UniProt {uniprot_id} Information")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        for key, value in info.items():
            if value is not None:
                table.add_row(key.replace("_", " ").title(), str(value))
        
        console.print(table)


@app.command(name="batch")
def batch_process(
    input_file: Path = typer.Argument(..., help="Input file with IDs (one per line)"),
    output_dir: Path = typer.Option(
        Path("output"), "-o", "--output-dir", help="Output directory for results"
    ),
    log_file: Optional[Path] = typer.Option(
        None, "-l", "--log", help="Log file path for eliot logs"
    ),
    id_type: str = typer.Option(
        "uniprot", "-t", "--type", help="ID type: 'pdb' or 'uniprot'"
    ),
    no_alphafold: bool = typer.Option(
        False, "--no-alphafold", help="Exclude AlphaFold structures (uniprot only)"
    ),
) -> None:
    """
    Batch process multiple IDs from a file.
    
    Input file should contain one ID per line.
    Results are saved as individual JSON files in the output directory.
    
    Example:
        pdb-mining batch ids.txt -o results/ -t uniprot
    """
    setup_logging(log_file)
    
    with start_action(action_type="cli_batch_process", input_file=str(input_file)):
        # Read input file
        if not input_file.exists():
            console.print(f"[red]Error:[/red] Input file {input_file} not found")
            raise typer.Exit(1)
        
        with open(input_file) as f:
            ids = [line.strip() for line in f if line.strip()]
        
        if not ids:
            console.print("[red]Error:[/red] No IDs found in input file")
            raise typer.Exit(1)
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Process each ID
        console.print(f"Processing {len(ids)} {id_type} IDs...")
        
        success_count = 0
        error_count = 0
        
        with typer.progressbar(ids, label="Processing") as progress:
            for id_value in progress:
                try:
                    if id_type.lower() == "pdb":
                        metadata = get_pdb_metadata(id_value)
                        if metadata:
                            output_file = output_dir / f"{id_value}_metadata.json"
                            with open(output_file, "w") as f:
                                json.dump(metadata.to_dict(), f, indent=2)
                            success_count += 1
                        else:
                            error_count += 1
                    
                    elif id_type.lower() == "uniprot":
                        structures = get_structures_for_uniprot(
                            id_value,
                            include_alphafold=not no_alphafold
                        )
                        if structures:
                            result = {
                                "uniprot_id": id_value,
                                "structure_count": len(structures),
                                "structures": [s.to_dict() for s in structures],
                            }
                            output_file = output_dir / f"{id_value}_structures.json"
                            with open(output_file, "w") as f:
                                json.dump(result, f, indent=2)
                            success_count += 1
                        else:
                            error_count += 1
                    else:
                        console.print(f"[red]Error:[/red] Invalid ID type: {id_type}")
                        raise typer.Exit(1)
                
                except Exception as e:
                    console.print(f"[red]Error processing {id_value}:[/red] {e}")
                    error_count += 1
        
        # Summary
        console.print("\n[bold]Batch Processing Summary:[/bold]")
        console.print(f"  [green]✓[/green] Successful: {success_count}")
        console.print(f"  [red]✗[/red] Failed: {error_count}")
        console.print(f"  Results saved to: {output_dir}")


def main() -> None:
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()


