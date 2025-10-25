#!/usr/bin/env python3
"""
Dataset management commands for atomica-mcp.
Download and manage atomica_longevity_proteins dataset from Hugging Face.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import json

import typer
from eliot import start_action, to_file
import fsspec
import polars as pl
from pycomfort.logging import to_nice_file

app = typer.Typer(
    help="Dataset management commands for ATOMICA longevity proteins",
    no_args_is_help=True
)


def setup_logging(log_file_name: str, log_to_file: bool = True) -> None:
    """
    Set up Eliot logging with file destinations.
    
    Args:
        log_file_name: Base name for log files (without extension)
        log_to_file: Whether to enable file logging
    """
    if log_to_file:
        # Get root directory (3 levels up from this file)
        root = Path(__file__).parent.parent.parent
        log_dir = root / "logs"
        log_dir.mkdir(exist_ok=True)
        
        json_log = log_dir / f"{log_file_name}.json"
        rendered_log = log_dir / f"{log_file_name}.log"
        
        # Register Eliot destinations
        to_file(open(str(json_log), "w"))
        to_nice_file(json_log, rendered_log)


def get_hf_filesystem() -> fsspec.AbstractFileSystem:
    """
    Get Hugging Face fsspec filesystem.
    
    Returns:
        Hugging Face filesystem instance
    """
    return fsspec.filesystem("hf", token=None)


@app.command()
def download(
    output_dir: Path = typer.Option(
        Path("data/input/atomica_longevity_proteins"),
        "--output-dir", "-o",
        help="Output directory for downloaded dataset"
    ),
    repo_id: str = typer.Option(
        "longevity-genie/atomica_longevity_proteins",
        "--repo-id", "-r",
        help="Hugging Face repository ID"
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Force re-download even if files exist"
    ),
    pattern: Optional[str] = typer.Option(
        None,
        "--pattern", "-p",
        help="Download only files matching pattern (glob, e.g., '*.cif' or '6ht5*')"
    )
) -> None:
    """
    Download atomica_longevity_proteins dataset from Hugging Face using fsspec.
    
    This downloads PDB structures, ATOMICA scores, metadata, and critical residues
    for longevity-related proteins including NRF2, KEAP1, SOX2, APOE, and OCT4.
    
    Examples:
        # Download full dataset
        dataset download
        
        # Download to data/inputs
        dataset download --output-dir data/inputs
        
        # Download only CIF structure files
        dataset download --pattern "*.cif"
        
        # Download only files for specific PDB (e.g., 6ht5)
        dataset download --pattern "6ht5*"
    """
    # Set up logging
    setup_logging("download_dataset")
    
    with start_action(action_type="download_dataset", repo=repo_id, output=str(output_dir)) as action:
        output_dir.mkdir(parents=True, exist_ok=True)
        
        typer.echo(f"📦 Downloading dataset: {repo_id}")
        typer.echo(f"📁 Output directory: {output_dir}")
        
        try:
            # Get fsspec filesystem
            typer.echo("🔌 Connecting to Hugging Face...")
            fs = get_hf_filesystem()
            
            # List files in the dataset using hf:// protocol
            typer.echo("🔍 Discovering dataset files...")
            repo_path = f"datasets/{repo_id}"
            
            try:
                files = fs.ls(repo_path, detail=False)
                # Filter out directories and metadata files
                files = [f for f in files if not f.endswith('/')]
                
                # Apply pattern filter if provided
                if pattern:
                    import fnmatch
                    files = [f for f in files if fnmatch.fnmatch(Path(f).name, pattern)]
                
                action.log(message_type="files_listed", count=len(files))
            
            except Exception as e:
                action.log(message_type="list_error", error=str(e))
                typer.echo(f"❌ Could not list files: {e}", err=True)
                raise typer.Exit(code=1)
            
            if not files:
                typer.echo("❌ No files found to download", err=True)
                raise typer.Exit(code=1)
            
            if pattern:
                typer.echo(f"🎯 Pattern '{pattern}' matched {len(files)} files")
            else:
                typer.echo(f"📥 Found {len(files)} files to download")
            
            downloaded = 0
            skipped = 0
            failed = 0
            
            for remote_file in files:
                # Extract filename from path
                filename = Path(remote_file).name
                local_path = output_dir / filename
                
                # Check if file exists and skip if not forcing
                if local_path.exists() and not force:
                    skipped += 1
                    continue
                
                try:
                    with start_action(action_type="download_file", file=filename) as dl_action:
                        # Download using fsspec with hf:// protocol
                        remote_url = f"hf://{remote_file}"
                        fs.get(remote_url, str(local_path))
                        
                        downloaded += 1
                        
                        if downloaded % 10 == 0:
                            typer.echo(f"✓ Downloaded {downloaded}/{len(files)} files...")
                        
                        dl_action.log(
                            message_type="download_complete",
                            size_bytes=local_path.stat().st_size if local_path.exists() else 0
                        )
                
                except Exception as e:
                    failed += 1
                    with start_action(action_type="download_failed", file=filename) as fail_action:
                        fail_action.log(message_type="error", error=str(e))
                    typer.echo(f"✗ Failed to download {filename}: {e}", err=True)
            
            # Summary
            typer.echo("\n" + "="*60)
            typer.echo("📊 Download Summary:")
            typer.echo(f"  ✓ Downloaded: {downloaded}")
            typer.echo(f"  ⊘ Skipped (already exist): {skipped}")
            typer.echo(f"  ✗ Failed: {failed}")
            typer.echo(f"  📁 Location: {output_dir.resolve()}")
            typer.echo("="*60)
            
            if failed > 0:
                typer.echo("\n⚠️  Some files failed to download. Check logs for details.", err=True)
                raise typer.Exit(code=1)
            
            if downloaded > 0:
                typer.echo("\n✅ Dataset download completed successfully!")
            elif skipped > 0:
                typer.echo("\n✅ All files already exist. Use --force to re-download.")
        
        except typer.Exit:
            raise
        except Exception as e:
            typer.echo(f"\n❌ Error downloading dataset: {e}", err=True)
            raise typer.Exit(code=1)


@app.command()
def list_files(
    repo_id: str = typer.Option(
        "longevity-genie/atomica_longevity_proteins",
        "--repo-id", "-r",
        help="Hugging Face repository ID"
    ),
    pattern: Optional[str] = typer.Option(
        None,
        "--pattern", "-p",
        help="Filter files by pattern (glob, e.g., '*.cif')"
    )
) -> None:
    """
    List all files in the dataset repository.
    """
    # Set up logging
    setup_logging("list_files")
    
    with start_action(action_type="list_files", repo=repo_id):
        typer.echo(f"📦 Repository: {repo_id}")
        typer.echo(f"🔍 Listing files...\n")
        
        try:
            fs = get_hf_filesystem()
            repo_path = f"datasets/{repo_id}"
            files = fs.ls(repo_path, detail=False)
            files = [f for f in files if not f.endswith('/')]
            
            # Apply pattern filter if provided
            if pattern:
                import fnmatch
                files = [f for f in files if fnmatch.fnmatch(Path(f).name, pattern)]
            
            # Remove repo prefix for display
            display_files = [Path(f).name for f in files]
            
            if pattern:
                typer.echo(f"🎯 Pattern '{pattern}' matched {len(display_files)} files\n")
            
            # Group files by extension
            from collections import defaultdict
            by_ext: dict[str, list[str]] = defaultdict(list)
            for f in display_files:
                ext = Path(f).suffix or "no_extension"
                by_ext[ext].append(f)
            
            # Display summary
            typer.echo("📊 File Summary:")
            for ext, file_list in sorted(by_ext.items()):
                typer.echo(f"  {ext:20s}: {len(file_list):4d} files")
            
            typer.echo(f"\n📄 Total: {len(display_files)} files")
            
            # Display first 20 files
            if display_files:
                typer.echo("\n📋 First 20 files:")
                for f in sorted(display_files)[:20]:
                    typer.echo(f"  • {f}")
                
                if len(display_files) > 20:
                    typer.echo(f"\n  ... and {len(display_files) - 20} more files")
        
        except Exception as e:
            typer.echo(f"\n❌ Error listing files: {e}", err=True)
            raise typer.Exit(code=1)


@app.command()
def reorganize(
    dataset_dir: Path = typer.Option(
        Path("data/input/atomica_longevity_proteins"),
        "--dataset-dir", "-d",
        help="Directory containing the ATOMICA longevity proteins dataset"
    ),
    index_file: Optional[Path] = typer.Option(
        None,
        "--index", "-i",
        help="Index parquet file to update (optional; if not provided, reorganizes based on file patterns)"
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be done without actually moving files"
    )
) -> None:
    """
    Reorganize dataset files into per-PDB folders and update paths to be relative.
    
    This command:
    1. Creates a folder for each PDB ID (e.g., 1b68/)
    2. Moves all related files into that folder (e.g., 1b68.cif, 1b68_metadata.json)
    3. Updates the index parquet to use paths relative to dataset root (if index is provided)
    
    If no index is provided, it will reorganize files based on their naming patterns.
    
    Examples:
        # Reorganize dataset with existing index
        dataset reorganize
        
        # Reorganize FOXO3 folder without index (based on file patterns)
        dataset reorganize --dataset-dir data/FOXO3
        
        # Dry run to see what would be done
        dataset reorganize --dry-run
        
        # Use custom paths with index
        dataset reorganize --dataset-dir data/atomica --index data/index.parquet
    """
    # Set up logging
    setup_logging("reorganize_dataset")
    
    with start_action(action_type="reorganize_dataset", dataset_dir=str(dataset_dir), index=str(index_file) if index_file else "none", dry_run=dry_run) as action:
        if not dataset_dir.exists():
            typer.echo(f"❌ Dataset directory not found: {dataset_dir}", err=True)
            raise typer.Exit(code=1)
        
        # Make paths absolute for processing
        dataset_dir = dataset_dir.resolve()
        
        typer.echo(f"📦 Reorganizing ATOMICA dataset: {dataset_dir}")
        
        if index_file:
            if not index_file.exists():
                typer.echo(f"❌ Index file not found: {index_file}", err=True)
                raise typer.Exit(code=1)
            index_file = index_file.resolve()
            typer.echo(f"📊 Index file: {index_file}")
        else:
            typer.echo(f"📊 No index provided - will reorganize based on file patterns")
        
        if dry_run:
            typer.echo("🔍 DRY RUN MODE - No files will be moved")
        
        # Determine PDB IDs to process
        pdb_ids: List[str] = []
        
        if index_file:
            # Load the index
            typer.echo("\n📖 Loading index...")
            df = pl.read_parquet(index_file)
            pdb_ids = df['pdb_id'].to_list()
            typer.echo(f"✓ Found {len(pdb_ids)} structures in index")
        else:
            # Scan directory for PDB files and extract PDB IDs from file patterns
            typer.echo("\n🔍 Scanning directory for PDB files...")
            
            # Look for files matching pattern: {pdb_id}.cif or {pdb_id}_*.json/tsv/pml
            all_files = list(dataset_dir.glob("*"))
            pdb_id_set = set()
            
            for file in all_files:
                if file.is_file():
                    # Extract PDB ID from filename (e.g., "1b68.cif" -> "1b68")
                    stem = file.stem
                    # Remove suffixes like _metadata, _summary, _critical_residues, _interact_scores, _pymol_commands
                    for suffix in ['_metadata', '_summary', '_critical_residues', '_interact_scores', '_pymol_commands']:
                        if stem.endswith(suffix):
                            stem = stem[:-len(suffix)]
                    # Only add if it looks like a PDB ID (typically 4 chars/digits)
                    if stem and len(stem) <= 4:
                        pdb_id_set.add(stem.upper())
            
            pdb_ids = sorted(list(pdb_id_set))
            
            if not pdb_ids:
                typer.echo("❌ No PDB files found in directory (expected files like: 1b68.cif, 1b68_metadata.json, etc.)", err=True)
                raise typer.Exit(code=1)
            
            typer.echo(f"✓ Found {len(pdb_ids)} PDB IDs based on file patterns")
        
        # Track statistics
        moved_files = 0
        created_folders = 0
        updated_paths = 0
        skipped_files = 0
        
        # Process each PDB ID
        typer.echo("\n🔧 Reorganizing files...")
        for i, pdb_id in enumerate(pdb_ids, 1):
            pdb_id_lower = pdb_id.lower()
            pdb_folder = dataset_dir / pdb_id_lower
            
            with start_action(action_type="reorganize_pdb", pdb_id=pdb_id) as pdb_action:
                # Create folder if it doesn't exist
                if not pdb_folder.exists():
                    if not dry_run:
                        pdb_folder.mkdir(parents=True, exist_ok=True)
                    created_folders += 1
                    typer.echo(f"  [{i}/{len(pdb_ids)}] {pdb_id}: Created folder")
                else:
                    typer.echo(f"  [{i}/{len(pdb_ids)}] {pdb_id}: Folder exists")
                
                # Find all files for this PDB
                file_patterns = [
                    f"{pdb_id_lower}.cif",
                    f"{pdb_id_lower}_metadata.json",
                    f"{pdb_id_lower}_summary.json",
                    f"{pdb_id_lower}_critical_residues.tsv",
                    f"{pdb_id_lower}_interact_scores.json",
                    f"{pdb_id_lower}_pymol_commands.pml"
                ]
                
                for pattern in file_patterns:
                    src_file = dataset_dir / pattern
                    dst_file = pdb_folder / pattern
                    
                    if src_file.exists() and src_file.parent == dataset_dir:
                        # File exists in root and needs to be moved
                        if not dry_run:
                            src_file.rename(dst_file)
                        moved_files += 1
                        pdb_action.log(message_type="file_moved", file=pattern)
                    elif dst_file.exists():
                        # File already in correct location
                        skipped_files += 1
                
        # Update the index with relative paths (only if index was provided)
        if index_file:
            typer.echo("\n📝 Updating index paths...")
            
            def make_relative_path(path_str: Optional[str]) -> Optional[str]:
                """Convert absolute or project-relative path to dataset-relative path."""
                if path_str is None:
                    return None
                path = Path(path_str)
                # If path is absolute or starts with data/input/atomica_longevity_proteins
                if path.is_absolute():
                    try:
                        rel = path.relative_to(dataset_dir)
                        return str(rel)
                    except ValueError:
                        return str(path)
                else:
                    # Remove data/input/atomica_longevity_proteins prefix if present
                    parts = path.parts
                    if "atomica_longevity_proteins" in parts:
                        idx = parts.index("atomica_longevity_proteins")
                        rel_parts = parts[idx + 1:]
                        if rel_parts:
                            return str(Path(*rel_parts))
                    return str(path)
            
            # Load index
            df = pl.read_parquet(index_file)
            
            # Update each path column
            path_columns = [
                'cif_path',
                'metadata_path',
                'summary_path',
                'critical_residues_path',
                'interact_scores_path',
                'pymol_path'
            ]
            
            # Only process columns that actually exist in the dataframe
            existing_path_columns = [col for col in path_columns if col in df.columns]
            
            # Update all path columns at once
            for col in existing_path_columns:
                # Create a new column with updated paths
                df = df.with_columns(
                    pl.when(pl.col(col).is_not_null())
                    .then(pl.col('pdb_id').str.to_lowercase() + "/" + pl.col(col).map_elements(lambda x: Path(x).name, return_dtype=pl.String))
                    .otherwise(None)
                    .alias(col)
                )
            
            updated_paths = len(existing_path_columns)
            
            # Save updated index
            if not dry_run:
                typer.echo(f"💾 Saving updated index to: {index_file}")
                df.write_parquet(index_file)
            else:
                typer.echo(f"💾 Would save updated index to: {index_file}")
            
            # Show sample of updated paths
            typer.echo("\n📋 Sample of updated paths:")
            sample_df = df.select(['pdb_id', 'cif_path', 'metadata_path']).head(3)
            typer.echo(sample_df)
        else:
            updated_paths = 0
        
        # Summary
        typer.echo("\n" + "="*60)
        typer.echo("📊 Reorganization Summary:")
        typer.echo(f"  📁 Folders created: {created_folders}")
        typer.echo(f"  📦 Files moved: {moved_files}")
        typer.echo(f"  ⊘ Files already in place: {skipped_files}")
        if index_file:
            typer.echo(f"  ✏️  Path columns updated: {updated_paths}")
        typer.echo(f"  📍 All paths now relative to: {dataset_dir.name}/")
        typer.echo("="*60)
        
        if dry_run:
            typer.echo("\n🔍 This was a DRY RUN. Run without --dry-run to apply changes.")
        else:
            typer.echo("\n✅ Dataset reorganization completed successfully!")
        
        action.log(
            message_type="reorganize_complete",
            folders_created=created_folders,
            files_moved=moved_files,
            paths_updated=updated_paths,
            index_provided=index_file is not None
        )


@app.command()
def info(
    repo_id: str = typer.Option(
        "longevity-genie/atomica_longevity_proteins",
        "--repo-id", "-r",
        help="Hugging Face repository ID"
    )
) -> None:
    """
    Show information about the dataset.
    """
    typer.echo(f"📦 Dataset: {repo_id}")
    typer.echo(f"🔗 URL: https://huggingface.co/datasets/{repo_id}")
    typer.echo("\n📄 Description:")
    typer.echo("  Comprehensive structural analysis of key longevity-related proteins")
    typer.echo("  using the ATOMICA deep learning model.")
    typer.echo("\n🧬 Protein Families:")
    typer.echo("  • NRF2 (NFE2L2): 19 structures - Oxidative stress response")
    typer.echo("  • KEAP1: 47 structures - Oxidative stress response")
    typer.echo("  • SOX2: 8 structures - Pluripotency factor")
    typer.echo("  • APOE (E2/E3/E4): 9 structures - Lipid metabolism & Alzheimer's")
    typer.echo("  • OCT4 (POU5F1): 4 structures - Reprogramming factor")
    typer.echo("\n📊 Total: 94 high-resolution protein structures")
    typer.echo("\n📁 Files per structure:")
    typer.echo("  • {pdb_id}.cif - Structure file (mmCIF format)")
    typer.echo("  • {pdb_id}_metadata.json - PDB metadata")
    typer.echo("  • {pdb_id}_interact_scores.json - ATOMICA interaction scores")
    typer.echo("  • {pdb_id}_summary.json - Processing statistics")
    typer.echo("  • {pdb_id}_critical_residues.tsv - Ranked critical residues")
    typer.echo("\n💡 Usage:")
    typer.echo("  # Download full dataset")
    typer.echo("  atomica-dataset download")
    typer.echo("\n  # Download to data/inputs")
    typer.echo("  atomica-dataset download --output-dir data/inputs")
    typer.echo("\n  # Download only structure files")
    typer.echo("  atomica-dataset download --pattern '*.cif'")
    typer.echo("\n  # List all available files")
    typer.echo("  atomica-dataset list-files")


def resolve_pdb_metadata(pdb_id: str) -> Dict[str, Any]:
    """
    Resolve protein metadata for a PDB ID using comprehensive PDB mining.
    
    Uses the mining module which queries PDBe API, UniProt API, and includes
    comprehensive metadata resolution with retry logic and error handling.
    
    Args:
        pdb_id: PDB identifier (e.g., '1b68')
    
    Returns:
        Dictionary with protein metadata including UniProt IDs, organisms, gene symbols,
        Ensembl IDs, structure information, and complex details
    """
    from atomica_mcp.mining.pdb_metadata import get_pdb_metadata
    
    with start_action(action_type="resolve_pdb_metadata", pdb_id=pdb_id) as action:
        # Use comprehensive mining function
        pdb_metadata = get_pdb_metadata(pdb_id)
        
        if pdb_metadata is None:
            action.log(message_type="pdb_metadata_not_found")
            return {
                "pdb_id": pdb_id,
                "found": False,
                "error": "PDB ID not found in database",
                "uniprot_ids": [],
                "organisms": [],
                "taxonomy_ids": [],
                "gene_symbols": [],
                "ensembl_ids": [],
                "title": None,
                "structures": []
            }
        
        # Extract key information from comprehensive metadata
        result = {
            "pdb_id": pdb_id.upper(),
            "found": True,
            "title": pdb_metadata.title,
            "uniprot_ids": pdb_metadata.uniprot_ids,
            "gene_symbols": pdb_metadata.gene_symbols,
            "organisms": [pdb_metadata.organism] if pdb_metadata.organism else [],
            "taxonomy_ids": [pdb_metadata.organism_tax_id] if pdb_metadata.organism_tax_id else [],
            "ensembl_ids": [],
            "structures": [s.to_dict() for s in pdb_metadata.structures]
        }
        
        action.log(
            message_type="pdb_metadata_resolved",
            uniprot_count=len(result["uniprot_ids"]),
            gene_count=len(result["gene_symbols"]),
            organism=result["organisms"][0] if result["organisms"] else None
        )
        
        return result


@app.command()
def index(
    dataset_dir: Path = typer.Option(
        Path("data/input/atomica_longevity_proteins"),
        "--dataset-dir", "-d",
        help="Directory containing the ATOMICA longevity proteins dataset"
    ),
    output_file: Path = typer.Option(
        Path("data/output/atomica_index.parquet"),
        "--output", "-o",
        help="Output file for the dataset index (parquet format)"
    ),
    save_to_dataset: bool = typer.Option(
        True,
        "--save-to-dataset/--no-save-to-dataset",
        help="Also save index to dataset directory as atomica_index.parquet"
    ),
    include_metadata: bool = typer.Option(
        False,
        "--include-metadata",
        help="Include full metadata dictionary in output (makes file larger)"
    )
) -> None:
    """
    Create an index of all PDB structures in the ATOMICA dataset with resolved metadata.
    
    Generates a comprehensive index DataFrame with:
    - PDB ID
    - Paths to all related files (CIF, metadata, summary, critical residues, etc.)
    - Resolved protein metadata (UniProt IDs, organisms, taxonomy IDs, gene symbols, Ensembl IDs, structures)
    - Counts and statistics from files
    
    The index is saved as a Parquet file for efficient querying and analysis.
    Boolean flags like "has_metadata" are not included as they can be computed from queries
    (e.g., pl.col("metadata_path").is_not_null()).
    
    Examples:
        # Create index with default settings
        dataset index
        
        # Create index with custom paths
        dataset index --dataset-dir data/atomica --output data/index.parquet
        
        # Include full metadata in the index
        dataset index --include-metadata
    """
    # Set up logging
    setup_logging("index_dataset")
    
    with start_action(action_type="index_dataset", dataset_dir=str(dataset_dir), output=str(output_file)) as action:
        if not dataset_dir.exists():
            typer.echo(f"❌ Dataset directory not found: {dataset_dir}", err=True)
            raise typer.Exit(code=1)
        
        typer.echo(f"📦 Indexing ATOMICA dataset: {dataset_dir}")
        typer.echo(f"📊 Building comprehensive index with metadata resolution...")
        
        # Find all PDB IDs by looking for .cif files (in subdirectories)
        cif_files = sorted(dataset_dir.glob("**/*.cif"))
        
        if not cif_files:
            typer.echo("❌ No CIF files found in dataset directory", err=True)
            raise typer.Exit(code=1)
        
        typer.echo(f"🔍 Found {len(cif_files)} structures")
        
        # Build index records
        records: List[Dict[str, Any]] = []
        
        # Step 1: Collect all PDB IDs and basic file info
        pdb_data = []
        for i, cif_file in enumerate(cif_files, 1):
            pdb_id = cif_file.stem
            pdb_dir = cif_file.parent
            
            # Define expected file paths (relative to parent directory)
            cif_path = cif_file
            metadata_path = pdb_dir / f"{pdb_id}_metadata.json"
            summary_path = pdb_dir / f"{pdb_id}_summary.json"
            critical_residues_path = pdb_dir / f"{pdb_id}_critical_residues.tsv"
            interact_scores_path = pdb_dir / f"{pdb_id}_interact_scores.json"
            pymol_path = pdb_dir / f"{pdb_id}_pymol_commands.pml"
            
            pdb_data.append({
                "pdb_id": pdb_id,
                "cif_path": cif_path,
                "metadata_path": metadata_path,
                "summary_path": summary_path,
                "critical_residues_path": critical_residues_path,
                "interact_scores_path": interact_scores_path,
                "pymol_path": pymol_path,
            })
        
        # Step 2: Resolve metadata for all PDB IDs (one by one but with progress tracking)
        typer.echo(f"\n🔬 Resolving metadata for {len(pdb_data)} structures...")
        
        for i, pdb_info in enumerate(pdb_data, 1):
            pdb_id = pdb_info["pdb_id"]
            
            with start_action(action_type="index_pdb", pdb_id=pdb_id) as pdb_action:
                # Read metadata JSON if it exists (for quick lookup)
                metadata_json: Optional[Dict[str, Any]] = None
                if pdb_info["metadata_path"].exists():
                    with start_action(action_type="read_metadata_json", path=str(pdb_info["metadata_path"])) as read_action:
                        try:
                            with open(pdb_info["metadata_path"], 'r') as f:
                                metadata_json = json.load(f)
                            read_action.log(message_type="metadata_json_loaded")
                        except Exception as e:
                            read_action.log(message_type="metadata_read_error", error=str(e))
                
                # Read summary JSON if it exists
                summary_json: Optional[Dict[str, Any]] = None
                if pdb_info["summary_path"].exists():
                    with start_action(action_type="read_summary_json", path=str(pdb_info["summary_path"])) as read_action:
                        try:
                            with open(pdb_info["summary_path"], 'r') as f:
                                summary_json = json.load(f)
                            read_action.log(message_type="summary_json_loaded")
                        except Exception as e:
                            read_action.log(message_type="summary_read_error", error=str(e))
                
                # Count critical residues if file exists
                critical_residues_count: Optional[int] = None
                if pdb_info["critical_residues_path"].exists():
                    with start_action(action_type="count_critical_residues", path=str(pdb_info["critical_residues_path"])) as count_action:
                        try:
                            with open(pdb_info["critical_residues_path"], 'r') as f:
                                # Count non-comment, non-empty lines
                                critical_residues_count = sum(1 for line in f if line.strip() and not line.startswith('#'))
                            count_action.log(message_type="residues_counted", count=critical_residues_count)
                        except Exception as e:
                            count_action.log(message_type="critical_residues_count_error", error=str(e))
                
                # Resolve protein metadata using comprehensive PDB mining
                typer.echo(f"  [{i}/{len(pdb_data)}] Resolving metadata for {pdb_id}...", nl=False)
                resolved_metadata = resolve_pdb_metadata(pdb_id)
                
                if resolved_metadata.get("found"):
                    uniprot_count = len(resolved_metadata.get('uniprot_ids', []))
                    gene_count = len(resolved_metadata.get('gene_symbols', []))
                    organism = resolved_metadata.get('organisms', [])[0] if resolved_metadata.get('organisms') else None
                    typer.echo(f" ✓ ({uniprot_count} UniProt, {gene_count} genes, {organism or 'no organism'})")
                else:
                    error_msg = resolved_metadata.get("error", "Unknown error")
                    typer.echo(f" ⚠ {error_msg}")
                
                # Build record (without boolean flags - can be computed via queries)
                record = {
                    "pdb_id": pdb_id.upper(),
                    # File paths (relative to dataset dir or None if not exist)
                    "cif_path": str(pdb_info["cif_path"].relative_to(dataset_dir)) if pdb_info["cif_path"].exists() else None,
                    "metadata_path": str(pdb_info["metadata_path"].relative_to(dataset_dir)) if pdb_info["metadata_path"].exists() else None,
                    "summary_path": str(pdb_info["summary_path"].relative_to(dataset_dir)) if pdb_info["summary_path"].exists() else None,
                    "critical_residues_path": str(pdb_info["critical_residues_path"].relative_to(dataset_dir)) if pdb_info["critical_residues_path"].exists() else None,
                    "interact_scores_path": str(pdb_info["interact_scores_path"].relative_to(dataset_dir)) if pdb_info["interact_scores_path"].exists() else None,
                    "pymol_path": str(pdb_info["pymol_path"].relative_to(dataset_dir)) if pdb_info["pymol_path"].exists() else None,
                    # Counts and stats
                    "critical_residues_count": critical_residues_count,
                    "total_time_seconds": summary_json.get("total_time_seconds") if summary_json else None,
                    "gpu_memory_mb_max": summary_json.get("gpu_memory_mb", {}).get("max") if summary_json else None,
                    # Resolved metadata from PDB mining
                    "metadata_found": resolved_metadata.get("found", False),
                    "title": resolved_metadata.get("title"),
                    "uniprot_ids": resolved_metadata.get("uniprot_ids", []),
                    "organisms": resolved_metadata.get("organisms", []),
                    "taxonomy_ids": resolved_metadata.get("taxonomy_ids", []),
                    "gene_symbols": resolved_metadata.get("gene_symbols", []),
                    "ensembl_ids": resolved_metadata.get("ensembl_ids", []),
                    # Convert structures to JSON string to avoid Parquet serialization issues
                    "structures_json": json.dumps(resolved_metadata.get("structures", [])) if resolved_metadata.get("structures") else None,
                }
                
                # Optionally include full metadata
                if include_metadata:
                    record["metadata_json"] = metadata_json
                    record["summary_json"] = summary_json
                
                records.append(record)
                
                pdb_action.log(
                    message_type="pdb_indexed",
                    metadata_found=resolved_metadata.get("found", False),
                    uniprot_count=len(resolved_metadata.get("uniprot_ids", [])),
                    organisms=resolved_metadata.get("organisms", [])
                )
        
        # Step 3: Batch-resolve Ensembl IDs and organisms for all UniProt IDs
        typer.echo("\n🧬 Batch-resolving Ensembl IDs and organisms for all UniProt IDs...")
        
        # Collect all unique UniProt IDs
        all_uniprot_ids = set()
        for record in records:
            all_uniprot_ids.update(record.get("uniprot_ids", []))
        
        if all_uniprot_ids:
            from atomica_mcp.mining.pdb_metadata import get_uniprot_info_batch
            
            typer.echo(f"  Found {len(all_uniprot_ids)} unique UniProt IDs to resolve")
            uniprot_info_map = get_uniprot_info_batch(list(all_uniprot_ids))
            
            # Update records with Ensembl IDs and organism info from UniProt
            for record in records:
                ensembl_ids_set = set()
                organisms_set = set()
                taxonomy_ids_set = set()
                
                for uniprot_id in record.get("uniprot_ids", []):
                    uniprot_info = uniprot_info_map.get(uniprot_id)
                    if uniprot_info:
                        # Add Ensembl IDs
                        if "ensembl_ids" in uniprot_info:
                            ensembl_ids_set.update(uniprot_info["ensembl_ids"])
                        
                        # Add organism info from UniProt (more reliable than PDB)
                        if uniprot_info.get("organism"):
                            organisms_set.add(uniprot_info["organism"])
                        if uniprot_info.get("tax_id"):
                            taxonomy_ids_set.add(uniprot_info["tax_id"])
                
                record["ensembl_ids"] = list(ensembl_ids_set)
                # Override organisms and taxonomy_ids with UniProt data
                if organisms_set:
                    record["organisms"] = list(organisms_set)
                if taxonomy_ids_set:
                    record["taxonomy_ids"] = list(taxonomy_ids_set)
            
            typer.echo(f"  ✓ Resolved Ensembl IDs for {len([r for r in records if r['ensembl_ids']])} structures")
            typer.echo(f"  ✓ Resolved organisms for {len([r for r in records if r['organisms']])} structures")
        
        # Create DataFrame
        typer.echo("\n📊 Creating index DataFrame...")
        df = pl.DataFrame(records)
        
        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to primary output location
        typer.echo(f"💾 Saving index to: {output_file}")
        df.write_parquet(output_file)
        
        # Also save to dataset directory if requested
        if save_to_dataset:
            dataset_index_path = dataset_dir / "atomica_index.parquet"
            typer.echo(f"💾 Saving index to dataset directory: {dataset_index_path}")
            df.write_parquet(dataset_index_path)
        
        # Print summary statistics
        typer.echo("\n" + "="*60)
        typer.echo("📊 Dataset Index Summary:")
        typer.echo(f"  Total structures: {len(df)}")
        
        # Count structures with complete datasets (all file paths not null)
        complete_count = df.filter(
            pl.col('metadata_path').is_not_null() & 
            pl.col('summary_path').is_not_null() & 
            pl.col('critical_residues_path').is_not_null()
        ).height
        typer.echo(f"  Complete datasets (all files): {complete_count}")
        typer.echo(f"  With metadata resolved: {df.filter(pl.col('metadata_found')).height}")
        
        # Count total UniProt IDs, genes, and Ensembl IDs
        total_uniprot = sum(len(ids) for ids in df['uniprot_ids'].to_list())
        total_genes = sum(len(genes) for genes in df['gene_symbols'].to_list())
        total_ensembl = sum(len(ids) for ids in df['ensembl_ids'].to_list())
        typer.echo(f"  Total UniProt IDs: {total_uniprot}")
        typer.echo(f"  Total gene symbols: {total_genes}")
        typer.echo(f"  Total Ensembl IDs: {total_ensembl}")
        
        # Show organism distribution
        all_organisms = [org for orgs in df['organisms'].to_list() for org in orgs if org]
        if all_organisms:
            from collections import Counter
            org_counts = Counter(all_organisms)
            typer.echo(f"  Unique organisms: {len(org_counts)}")
            typer.echo("\n  Top organisms:")
            for org, count in org_counts.most_common(5):
                typer.echo(f"    • {org}: {count} structures")
        
        typer.echo(f"\n  📁 Index saved: {output_file.resolve()}")
        if save_to_dataset:
            typer.echo(f"  📁 Also saved to: {(dataset_dir / 'atomica_index.parquet').resolve()}")
        typer.echo("="*60)
        
        typer.echo("\n✅ Dataset indexing completed successfully!")
        typer.echo("\n💡 Tip: Boolean flags like 'has_metadata' can be computed with queries:")
        typer.echo("   Example: df.filter(pl.col('metadata_path').is_not_null())")
        
        action.log(
            message_type="index_complete",
            total_structures=len(df),
            unique_organisms=len(set(org for orgs in df['organisms'].to_list() for org in orgs if org)),
            total_uniprot_ids=total_uniprot,
            total_gene_symbols=total_genes,
            total_ensembl_ids=total_ensembl
        )


@app.command()
def update(
    update_dir: Path = typer.Option(
        ...,
        "--update-dir", "-u",
        help="Directory containing new PDB structures to add to index"
    ),
    dataset_dir: Path = typer.Option(
        Path("data/input/atomica_longevity_proteins"),
        "--dataset-dir", "-d",
        help="Main dataset directory (for resolving relative paths)"
    ),
    index_file: Path = typer.Option(
        Path("data/output/atomica_index.parquet"),
        "--index", "-i",
        help="Existing index file to update"
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output file for updated index (defaults to same as --index)"
    ),
    save_to_dataset: bool = typer.Option(
        True,
        "--save-to-dataset/--no-save-to-dataset",
        help="Also save updated index to dataset directory as atomica_index.parquet"
    ),
    include_metadata: bool = typer.Option(
        False,
        "--include-metadata",
        help="Include full metadata dictionary in output (makes file larger)"
    ),
    force: bool = typer.Option(
        False,
        "--force", "-f",
        help="Re-process structures that already exist in the index"
    )
) -> None:
    """
    Update existing index with new PDB structures from an update folder.
    
    This command:
    1. Loads the existing index
    2. Scans update folder for new structures (same format as dataset)
    3. Resolves metadata only for new structures
    4. Merges with existing index
    5. Saves updated index
    
    The update folder should have the same structure as the dataset directory,
    with subdirectories for each PDB ID containing the structure files.
    
    Examples:
        # Update index with new structures
        dataset update --update-dir data/new_structures
        
        # Update specific index file
        dataset update --update-dir data/new_structures --index data/my_index.parquet
        
        # Force re-process existing structures
        dataset update --update-dir data/updates --force
        
        # Save to different output file
        dataset update --update-dir data/new --output data/updated_index.parquet
    """
    # Set up logging
    setup_logging("update_dataset")
    
    with start_action(
        action_type="update_dataset",
        update_dir=str(update_dir),
        dataset_dir=str(dataset_dir),
        index_file=str(index_file),
        force=force
    ) as action:
        # Validate paths
        if not update_dir.exists():
            typer.echo(f"❌ Update directory not found: {update_dir}", err=True)
            raise typer.Exit(code=1)
        
        if not index_file.exists():
            typer.echo(f"❌ Index file not found: {index_file}", err=True)
            typer.echo(f"💡 Tip: Use 'dataset index' to create an initial index first", err=True)
            raise typer.Exit(code=1)
        
        if output_file is None:
            output_file = index_file
        
        typer.echo(f"📦 Updating ATOMICA index")
        typer.echo(f"📂 Update directory: {update_dir}")
        typer.echo(f"📊 Existing index: {index_file}")
        typer.echo(f"💾 Output: {output_file}")
        
        # Load existing index
        typer.echo("\n📖 Loading existing index...")
        existing_df = pl.read_parquet(index_file)
        existing_pdb_ids = set(existing_df['pdb_id'].to_list())
        typer.echo(f"✓ Loaded {len(existing_df)} existing structures")
        
        # Find new structures in update directory
        typer.echo(f"\n🔍 Scanning for new structures in {update_dir}...")
        cif_files = sorted(update_dir.glob("**/*.cif"))
        
        if not cif_files:
            typer.echo("❌ No CIF files found in update directory", err=True)
            raise typer.Exit(code=1)
        
        typer.echo(f"✓ Found {len(cif_files)} structure files")
        
        # Filter to new structures (or all if force is True)
        new_pdb_data = []
        skipped_count = 0
        
        for cif_file in cif_files:
            pdb_id = cif_file.stem
            
            # Skip if already exists and not forcing update
            if pdb_id.upper() in existing_pdb_ids and not force:
                skipped_count += 1
                continue
            
            pdb_dir = cif_file.parent
            
            # Define expected file paths
            metadata_path = pdb_dir / f"{pdb_id}_metadata.json"
            summary_path = pdb_dir / f"{pdb_id}_summary.json"
            critical_residues_path = pdb_dir / f"{pdb_id}_critical_residues.tsv"
            interact_scores_path = pdb_dir / f"{pdb_id}_interact_scores.json"
            pymol_path = pdb_dir / f"{pdb_id}_pymol_commands.pml"
            
            new_pdb_data.append({
                "pdb_id": pdb_id,
                "cif_path": cif_file,
                "metadata_path": metadata_path,
                "summary_path": summary_path,
                "critical_residues_path": critical_residues_path,
                "interact_scores_path": interact_scores_path,
                "pymol_path": pymol_path,
            })
        
        if skipped_count > 0:
            typer.echo(f"⊘ Skipped {skipped_count} structures already in index (use --force to re-process)")
        
        if not new_pdb_data:
            typer.echo("✓ No new structures to add. Index is up to date!")
            return
        
        typer.echo(f"✓ Found {len(new_pdb_data)} new structures to process")
        
        # Process new structures (same logic as index command)
        typer.echo(f"\n🔬 Resolving metadata for {len(new_pdb_data)} new structures...")
        
        new_records: List[Dict[str, Any]] = []
        
        for i, pdb_info in enumerate(new_pdb_data, 1):
            pdb_id = pdb_info["pdb_id"]
            
            with start_action(action_type="process_new_pdb", pdb_id=pdb_id) as pdb_action:
                # Read metadata JSON if it exists
                metadata_json: Optional[Dict[str, Any]] = None
                if pdb_info["metadata_path"].exists():
                    with start_action(action_type="read_metadata_json", path=str(pdb_info["metadata_path"])):
                        try:
                            with open(pdb_info["metadata_path"], 'r') as f:
                                metadata_json = json.load(f)
                        except Exception as e:
                            typer.echo(f"  ⚠ Warning: Could not read metadata for {pdb_id}: {e}")
                
                # Read summary JSON if it exists
                summary_json: Optional[Dict[str, Any]] = None
                if pdb_info["summary_path"].exists():
                    with start_action(action_type="read_summary_json", path=str(pdb_info["summary_path"])):
                        try:
                            with open(pdb_info["summary_path"], 'r') as f:
                                summary_json = json.load(f)
                        except Exception as e:
                            typer.echo(f"  ⚠ Warning: Could not read summary for {pdb_id}: {e}")
                
                # Count critical residues if file exists
                critical_residues_count: Optional[int] = None
                if pdb_info["critical_residues_path"].exists():
                    try:
                        with open(pdb_info["critical_residues_path"], 'r') as f:
                            critical_residues_count = sum(1 for line in f if line.strip() and not line.startswith('#'))
                    except Exception as e:
                        typer.echo(f"  ⚠ Warning: Could not count residues for {pdb_id}: {e}")
                
                # Resolve protein metadata using comprehensive PDB mining
                typer.echo(f"  [{i}/{len(new_pdb_data)}] Resolving metadata for {pdb_id}...", nl=False)
                resolved_metadata = resolve_pdb_metadata(pdb_id)
                
                if resolved_metadata.get("found"):
                    uniprot_count = len(resolved_metadata.get('uniprot_ids', []))
                    gene_count = len(resolved_metadata.get('gene_symbols', []))
                    organism = resolved_metadata.get('organisms', [])[0] if resolved_metadata.get('organisms') else None
                    typer.echo(f" ✓ ({uniprot_count} UniProt, {gene_count} genes, {organism or 'no organism'})")
                else:
                    error_msg = resolved_metadata.get("error", "Unknown error")
                    typer.echo(f" ⚠ {error_msg}")
                
                # Compute relative paths to dataset_dir
                # This ensures paths are consistent with the main index
                try:
                    cif_rel_path = str(pdb_info["cif_path"].relative_to(dataset_dir)) if pdb_info["cif_path"].exists() else None
                except ValueError:
                    # If not relative to dataset_dir, try to construct path
                    cif_rel_path = f"{pdb_id}/{pdb_id}.cif" if pdb_info["cif_path"].exists() else None
                
                try:
                    metadata_rel_path = str(pdb_info["metadata_path"].relative_to(dataset_dir)) if pdb_info["metadata_path"].exists() else None
                except ValueError:
                    metadata_rel_path = f"{pdb_id}/{pdb_id}_metadata.json" if pdb_info["metadata_path"].exists() else None
                
                try:
                    summary_rel_path = str(pdb_info["summary_path"].relative_to(dataset_dir)) if pdb_info["summary_path"].exists() else None
                except ValueError:
                    summary_rel_path = f"{pdb_id}/{pdb_id}_summary.json" if pdb_info["summary_path"].exists() else None
                
                try:
                    critical_residues_rel_path = str(pdb_info["critical_residues_path"].relative_to(dataset_dir)) if pdb_info["critical_residues_path"].exists() else None
                except ValueError:
                    critical_residues_rel_path = f"{pdb_id}/{pdb_id}_critical_residues.tsv" if pdb_info["critical_residues_path"].exists() else None
                
                try:
                    interact_scores_rel_path = str(pdb_info["interact_scores_path"].relative_to(dataset_dir)) if pdb_info["interact_scores_path"].exists() else None
                except ValueError:
                    interact_scores_rel_path = f"{pdb_id}/{pdb_id}_interact_scores.json" if pdb_info["interact_scores_path"].exists() else None
                
                try:
                    pymol_rel_path = str(pdb_info["pymol_path"].relative_to(dataset_dir)) if pdb_info["pymol_path"].exists() else None
                except ValueError:
                    pymol_rel_path = f"{pdb_id}/{pdb_id}_pymol_commands.pml" if pdb_info["pymol_path"].exists() else None
                
                # Build record
                record = {
                    "pdb_id": pdb_id.upper(),
                    # File paths (relative to dataset dir)
                    "cif_path": cif_rel_path,
                    "metadata_path": metadata_rel_path,
                    "summary_path": summary_rel_path,
                    "critical_residues_path": critical_residues_rel_path,
                    "interact_scores_path": interact_scores_rel_path,
                    "pymol_path": pymol_rel_path,
                    # Counts and stats
                    "critical_residues_count": critical_residues_count,
                    "total_time_seconds": summary_json.get("total_time_seconds") if summary_json else None,
                    "gpu_memory_mb_max": summary_json.get("gpu_memory_mb", {}).get("max") if summary_json else None,
                    # Resolved metadata from PDB mining
                    "metadata_found": resolved_metadata.get("found", False),
                    "title": resolved_metadata.get("title"),
                    "uniprot_ids": resolved_metadata.get("uniprot_ids", []),
                    "organisms": resolved_metadata.get("organisms", []),
                    "taxonomy_ids": resolved_metadata.get("taxonomy_ids", []),
                    "gene_symbols": resolved_metadata.get("gene_symbols", []),
                    "ensembl_ids": resolved_metadata.get("ensembl_ids", []),
                    "structures_json": json.dumps(resolved_metadata.get("structures", [])) if resolved_metadata.get("structures") else None,
                }
                
                # Optionally include full metadata
                if include_metadata:
                    record["metadata_json"] = metadata_json
                    record["summary_json"] = summary_json
                
                new_records.append(record)
                
                pdb_action.log(
                    message_type="new_pdb_processed",
                    metadata_found=resolved_metadata.get("found", False),
                    uniprot_count=len(resolved_metadata.get("uniprot_ids", []))
                )
        
        # Batch-resolve Ensembl IDs for new structures
        typer.echo("\n🧬 Batch-resolving Ensembl IDs for new structures...")
        
        all_uniprot_ids = set()
        for record in new_records:
            all_uniprot_ids.update(record.get("uniprot_ids", []))
        
        if all_uniprot_ids:
            from atomica_mcp.mining.pdb_metadata import get_uniprot_info_batch
            
            typer.echo(f"  Found {len(all_uniprot_ids)} unique UniProt IDs to resolve")
            uniprot_info_map = get_uniprot_info_batch(list(all_uniprot_ids))
            
            # Update records with Ensembl IDs and organism info
            for record in new_records:
                ensembl_ids_set = set()
                organisms_set = set()
                taxonomy_ids_set = set()
                
                for uniprot_id in record.get("uniprot_ids", []):
                    uniprot_info = uniprot_info_map.get(uniprot_id)
                    if uniprot_info:
                        if "ensembl_ids" in uniprot_info:
                            ensembl_ids_set.update(uniprot_info["ensembl_ids"])
                        if uniprot_info.get("organism"):
                            organisms_set.add(uniprot_info["organism"])
                        if uniprot_info.get("tax_id"):
                            taxonomy_ids_set.add(uniprot_info["tax_id"])
                
                record["ensembl_ids"] = list(ensembl_ids_set)
                if organisms_set:
                    record["organisms"] = list(organisms_set)
                if taxonomy_ids_set:
                    record["taxonomy_ids"] = list(taxonomy_ids_set)
            
            typer.echo(f"  ✓ Resolved Ensembl IDs for {len([r for r in new_records if r['ensembl_ids']])} structures")
        
        # Create DataFrame for new records
        typer.echo("\n📊 Creating updated index...")
        new_df = pl.DataFrame(new_records)
        
        # Remove old entries if forcing update (to avoid duplicates)
        if force:
            new_pdb_ids_set = set(pdb_id.upper() for pdb_id in [info["pdb_id"] for info in new_pdb_data])
            existing_df = existing_df.filter(~pl.col('pdb_id').is_in(list(new_pdb_ids_set)))
            typer.echo(f"  Removed {len(new_pdb_ids_set)} existing entries for update")
        
        # Combine with existing index
        updated_df = pl.concat([existing_df, new_df], how="diagonal")
        
        # Sort by PDB ID for consistency
        updated_df = updated_df.sort("pdb_id")
        
        typer.echo(f"✓ Combined {len(existing_df)} existing + {len(new_df)} new = {len(updated_df)} total structures")
        
        # Ensure output directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Save updated index
        typer.echo(f"\n💾 Saving updated index to: {output_file}")
        updated_df.write_parquet(output_file)
        
        # Also save to dataset directory if requested
        if save_to_dataset:
            dataset_index_path = dataset_dir / "atomica_index.parquet"
            typer.echo(f"💾 Saving updated index to dataset directory: {dataset_index_path}")
            updated_df.write_parquet(dataset_index_path)
        
        # Print summary statistics
        typer.echo("\n" + "="*60)
        typer.echo("📊 Update Summary:")
        typer.echo(f"  Previous structures: {len(existing_df)}")
        typer.echo(f"  New structures added: {len(new_df)}")
        typer.echo(f"  Total structures: {len(updated_df)}")
        
        if skipped_count > 0:
            typer.echo(f"  Skipped (already exist): {skipped_count}")
        
        # Count newly added with metadata
        new_with_metadata = new_df.filter(pl.col('metadata_found')).height
        typer.echo(f"  New with metadata: {new_with_metadata}")
        
        # Count total UniProt IDs, genes, and Ensembl IDs in new structures
        total_new_uniprot = sum(len(ids) for ids in new_df['uniprot_ids'].to_list())
        total_new_genes = sum(len(genes) for genes in new_df['gene_symbols'].to_list())
        total_new_ensembl = sum(len(ids) for ids in new_df['ensembl_ids'].to_list())
        
        if total_new_uniprot > 0:
            typer.echo(f"  New UniProt IDs: {total_new_uniprot}")
        if total_new_genes > 0:
            typer.echo(f"  New gene symbols: {total_new_genes}")
        if total_new_ensembl > 0:
            typer.echo(f"  New Ensembl IDs: {total_new_ensembl}")
        
        typer.echo(f"\n  📁 Updated index saved: {output_file.resolve()}")
        if save_to_dataset:
            typer.echo(f"  📁 Also saved to: {(dataset_dir / 'atomica_index.parquet').resolve()}")
        typer.echo("="*60)
        
        typer.echo("\n✅ Index update completed successfully!")
        
        action.log(
            message_type="update_complete",
            previous_count=len(existing_df),
            new_count=len(new_df),
            total_count=len(updated_df),
            skipped_count=skipped_count
        )


if __name__ == "__main__":
    app()

