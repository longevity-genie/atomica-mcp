"""
Download PDB annotation files from EBI SIFTS database.

Downloads all TSV.GZ files from the EBI SIFTS server:
https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/

These files are used by the resolve_proteins module for organism classification
and UniProt mapping.
"""
import sys
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse
import urllib.request
import urllib.error
from html.parser import HTMLParser

import typer
from eliot import start_action, Logger
from pycomfort.logging import to_nice_stdout

app = typer.Typer(help="Download PDB annotation files from EBI SIFTS database", invoke_without_command=True)

# EBI SIFTS HTTPS base URL (preferred)
EBI_SIFTS_HTTPS_URL = "https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/"
# EBI SIFTS FTP base URL (fallback)
EBI_SIFTS_FTP_URL = "ftp://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/"


class LinkExtractor(HTMLParser):
    """Extract links from HTML."""
    def __init__(self):
        super().__init__()
        self.links: List[str] = []
    
    def handle_starttag(self, tag: str, attrs: List) -> None:
        if tag == 'a':
            for attr, value in attrs:
                if attr == 'href' and value.endswith('.tsv.gz'):
                    self.links.append(value)


def get_output_dir() -> Path:
    """Get the output directory for PDB annotations."""
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent  # src/pdb_mcp/sifts/download.py -> project root
    output_dir = project_root / "data" / "input" / "pdb"
    
    if not output_dir.exists():
        # Fallback to current directory
        output_dir = Path.cwd() / "data" / "input" / "pdb"
    
    return output_dir


def download_https(url: str, local_path: Path, action) -> bool:
    """Download a file via HTTPS. Returns True if successful."""
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            with open(local_path, 'wb') as f:
                f.write(response.read())
        return True
    except Exception as e:
        action.log(message_type="https_download_failed", url=url, error=str(e))
        return False


def list_files_https(url: str, action) -> Optional[List[str]]:
    """List .tsv.gz files from HTTPS directory listing."""
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            html = response.read().decode('utf-8')
        
        parser = LinkExtractor()
        parser.feed(html)
        return parser.links
    except Exception as e:
        action.log(message_type="https_listing_failed", url=url, error=str(e))
        return None


@app.callback(invoke_without_command=True)
def download(
    ctx: typer.Context,
    output_dir: Optional[Path] = typer.Option(
        None,
        help="Output directory for downloaded files. If not provided, uses data/input/pdb/"
    ),
    skip_existing: bool = typer.Option(
        True,
        help="If True, skip files that already exist"
    ),
    verbose: bool = typer.Option(
        True,
        help="Enable verbose output"
    ),
) -> None:
    """
    Download all PDB annotation files from EBI SIFTS database.
    
    This downloads all .tsv.gz files from:
    https://ftp.ebi.ac.uk/pub/databases/msd/sifts/flatfiles/tsv/
    
    These files are used for PDB chain-to-UniProt mapping and organism classification.
    """
    # Skip if a subcommand is invoked
    if ctx.invoked_subcommand is not None:
        return
    
    # Setup logging
    to_nice_stdout()
    
    # Resolve output directory
    if output_dir is None:
        output_dir = get_output_dir()
    else:
        output_dir = Path(output_dir)
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with start_action(action_type="download_pdb_annotations", output_dir=str(output_dir)) as action:
        action.log(
            message_type="download_config",
            https_url=EBI_SIFTS_HTTPS_URL,
            output_dir=str(output_dir),
            skip_existing=skip_existing
        )
        
        try:
            # Try HTTPS first (more reliable)
            action.log(message_type="connecting_to_server", method="HTTPS", url=EBI_SIFTS_HTTPS_URL)
            typer.echo("🌐 Connecting to EBI SIFTS server (HTTPS)...")
            
            tsv_files = list_files_https(EBI_SIFTS_HTTPS_URL, action)
            
            if tsv_files is None or len(tsv_files) == 0:
                typer.echo("❌ No .tsv.gz files found on remote server", err=True)
                return
            
            action.log(
                message_type="files_found",
                count=len(tsv_files),
                files=tsv_files
            )
            
            # Download files
            downloaded = 0
            skipped = 0
            failed = 0
            
            for filename in tsv_files:
                local_path = output_dir / filename
                
                # Check if file exists and skip_existing is True
                if skip_existing and local_path.exists():
                    typer.echo(f"⊘ Skipping (exists): {filename}")
                    skipped += 1
                    continue
                
                try:
                    if verbose:
                        typer.echo(f"⬇ Downloading: {filename}...", nl=False)
                    
                    url = EBI_SIFTS_HTTPS_URL + filename
                    
                    with start_action(
                        action_type="downloading_file",
                        filename=filename,
                        url=url,
                        local_path=str(local_path)
                    ):
                        if download_https(url, local_path, action):
                            # Verify file size
                            file_size = local_path.stat().st_size
                            size_mb = file_size / (1024 * 1024)
                            
                            if verbose:
                                typer.echo(f" ✓ ({size_mb:.1f} MB)")
                            
                            downloaded += 1
                        else:
                            raise Exception("HTTPS download failed")
                    
                except Exception as e:
                    if verbose:
                        typer.echo(f" ❌ Error", err=True)
                    
                    action.log(
                        message_type="download_error",
                        filename=filename,
                        error=str(e)
                    )
                    failed += 1
            
            # Summary
            action.log(
                message_type="download_summary",
                downloaded=downloaded,
                skipped=skipped,
                failed=failed,
                total=len(tsv_files)
            )
            
            typer.echo("\n" + "="*60)
            typer.echo(f"✓ Downloaded: {downloaded} files")
            if skipped > 0:
                typer.echo(f"⊘ Skipped: {skipped} files (already exist)")
            if failed > 0:
                typer.echo(f"❌ Failed: {failed} files", err=True)
            typer.echo(f"📁 Output directory: {output_dir}")
            typer.echo("="*60)
            
            if failed > 0:
                sys.exit(1)
        
        except Exception as e:
            action.log(
                message_type="download_failed",
                error=str(e)
            )
            typer.echo(f"❌ Download failed: {str(e)}", err=True)
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        app(["--help"])
    else:
        app()

