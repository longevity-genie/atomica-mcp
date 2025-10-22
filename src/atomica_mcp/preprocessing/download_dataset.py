#!/usr/bin/env python3
"""
Download atomica_longevity_proteins dataset from Hugging Face using fsspec.
"""

from pathlib import Path
from typing import Optional
import json

import typer
from eliot import start_action, Message
import fsspec

app = typer.Typer(help="Download atomica_longevity_proteins dataset from Hugging Face")


def get_hf_filesystem() -> fsspec.AbstractFileSystem:
    """
    Get Hugging Face fsspec filesystem.
    
    Returns:
        Hugging Face filesystem instance
    """
    # Use the hf:// protocol with fsspec
    return fsspec.filesystem("hf", token=None)


def list_dataset_files(
    fs: fsspec.AbstractFileSystem,
    repo_id: str = "longevity-genie/atomica_longevity_proteins",
    pattern: Optional[str] = None
) -> list[str]:
    """
    List all files in the Hugging Face dataset repository.
    
    Args:
        fs: fsspec filesystem instance
        repo_id: Hugging Face repository ID
        pattern: Optional glob pattern to filter files
    
    Returns:
        List of file paths
    """
    with start_action(action_type="list_files", repo=repo_id):
        # List files in the dataset using hf:// protocol
        repo_path = f"datasets/{repo_id}"
        
        try:
            files = fs.ls(repo_path, detail=False)
            # Filter out directories and metadata files
            files = [f for f in files if not f.endswith('/')]
            
            # Apply pattern filter if provided
            if pattern:
                import fnmatch
                files = [f for f in files if fnmatch.fnmatch(Path(f).name, pattern)]
            
            Message.log(message_type="files_listed", count=len(files))
            return files
        
        except Exception as e:
            Message.log(message_type="list_error", error=str(e))
            # Fallback: construct expected file list based on known structure
            typer.echo("⚠️  Could not list files dynamically, using known structure", err=True)
            return construct_expected_files(repo_id, pattern)


def construct_expected_files(repo_id: str, pattern: Optional[str] = None) -> list[str]:
    """
    Construct list of expected files based on dataset documentation.
    
    Args:
        repo_id: Repository ID
        pattern: Optional glob pattern to filter files
    
    Returns:
        List of expected file paths
    """
    # All PDB IDs from the dataset documentation
    pdb_ids = [
        # NRF2 (19 structures)
        "1x36", "2flu", "2hlu", "2lz1", "3wn7", "4zge", "4zhw", "4zi7",
        "5cgj", "5daf", "5u6g", "6b0e", "6ll6", "7o1l", "7o1m", "7o1n",
        "7o2x", "8apc", "8apd", "8eqj",
        # KEAP1 (47 structures) 
        "1u6d", "1x2j", "1x2r", "2dyr", "2dyh", "4ifl", "4iqk", "4l7b",
        "4l7c", "4n1b", "4xma", "4xmb", "5fnu", "5fnv", "6b62", "6ff5",
        "6ffm", "6fmp", "6fmq", "6rog", "6sp1", "6sp4", "6t7z", "6tg8",
        "7exi", "7x4w", "7x4x",
        # SOX2 (8 structures)
        "1o4x", "2le4", "6wx8", "6wx7", "6wx9", "6t90", "6yov", "6t7b",
        # APOE (9 structures)
        "1le2", "1lpe", "1nfn", "2l7b", "1b68", "1le4", "8ax8", "1oef", "1ya9",
        # OCT4 (4 structures)
        "3l1p", "8g86", "8g87", "6ht5"
    ]
    
    # File extensions per structure
    extensions = [".cif", "_metadata.json", "_interact_scores.json", "_summary.json", "_critical_residues.tsv"]
    
    files = []
    for pdb_id in pdb_ids:
        for ext in extensions:
            filename = f"{pdb_id}{ext}"
            if pattern:
                import fnmatch
                if fnmatch.fnmatch(filename, pattern):
                    files.append(f"datasets/{repo_id}/{filename}")
            else:
                files.append(f"datasets/{repo_id}/{filename}")
    
    return files


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
        download-atomica-dataset download
        
        # Download to specific directory
        download-atomica-dataset download --output-dir /path/to/data
        
        # Download only CIF structure files
        download-atomica-dataset download --pattern "*.cif"
        
        # Download only files for specific PDB (e.g., 6ht5)
        download-atomica-dataset download --pattern "6ht5*"
    """
    with start_action(action_type="download_dataset", repo=repo_id, output=str(output_dir)):
        output_dir.mkdir(parents=True, exist_ok=True)
        
        typer.echo(f"📦 Downloading dataset: {repo_id}")
        typer.echo(f"📁 Output directory: {output_dir}")
        
        try:
            # Get fsspec filesystem
            typer.echo("🔌 Connecting to Hugging Face...")
            fs = get_hf_filesystem()
            
            # List files
            typer.echo("🔍 Discovering dataset files...")
            files = list_dataset_files(fs, repo_id, pattern)
            
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
                    with start_action(action_type="download_file", file=filename):
                        # Download using fsspec
                        # Use hf:// protocol
                        remote_url = f"hf://{remote_file}"
                        fs.get(remote_url, str(local_path))
                        
                        downloaded += 1
                        
                        if downloaded % 10 == 0:
                            typer.echo(f"✓ Downloaded {downloaded}/{len(files)} files...")
                        
                        Message.log(
                            message_type="download_complete",
                            file=filename,
                            size_bytes=local_path.stat().st_size if local_path.exists() else 0
                        )
                
                except Exception as e:
                    failed += 1
                    Message.log(
                        message_type="download_failed",
                        file=filename,
                        error=str(e)
                    )
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
    with start_action(action_type="list_files", repo=repo_id):
        typer.echo(f"📦 Repository: {repo_id}")
        typer.echo(f"🔍 Listing files...\n")
        
        try:
            fs = get_hf_filesystem()
            files = list_dataset_files(fs, repo_id, pattern)
            
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
    typer.echo("  download-atomica-dataset download")
    typer.echo("\n  # Download only structure files")
    typer.echo("  download-atomica-dataset download --pattern '*.cif'")
    typer.echo("\n  # List all available files")
    typer.echo("  download-atomica-dataset list-files")


if __name__ == "__main__":
    app()
