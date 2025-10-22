#!/usr/bin/env python3
"""
Upload atomica_longevity_proteins dataset to HuggingFace Hub.
Only uploads new or changed files using bulk upload to avoid per-file commits.
"""

from pathlib import Path
from typing import Optional
import hashlib
from huggingface_hub import HfApi, hf_hub_download, list_repo_files
from huggingface_hub.utils import HfHubHTTPError
import typer
from eliot import start_action, Message, to_file
import tempfile
import shutil
from dotenv import load_dotenv

app = typer.Typer()


def calculate_file_hash(file_path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def get_remote_file_hash(repo_id: str, file_path: str, repo_type: str = "dataset") -> Optional[str]:
    """
    Download a remote file and calculate its hash.
    Returns None if file doesn't exist remotely.
    """
    with start_action(action_type="get_remote_file_hash", file_path=file_path):
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                
            downloaded_path = hf_hub_download(
                repo_id=repo_id,
                filename=file_path,
                repo_type=repo_type,
                local_dir=tmp_path.parent,
                local_dir_use_symlinks=False
            )
            file_hash = calculate_file_hash(Path(downloaded_path))
            
            # Cleanup
            if tmp_path.exists():
                tmp_path.unlink()
            
            Message.log(message_type="remote_file_hash", file_path=file_path, hash=file_hash)
            return file_hash
        except HfHubHTTPError as e:
            if e.response.status_code == 404:
                Message.log(message_type="remote_file_not_found", file_path=file_path)
                return None
            raise


def collect_files_to_upload(
    local_dir: Path,
    repo_id: str,
    repo_type: str = "dataset"
) -> list[Path]:
    """
    Compare local files with remote files and return list of files to upload.
    Only includes new or changed files.
    """
    with start_action(action_type="collect_files_to_upload", local_dir=str(local_dir)):
        files_to_upload: list[Path] = []
        
        # Get all local files
        local_files = [f for f in local_dir.rglob("*") if f.is_file()]
        Message.log(message_type="local_files_count", count=len(local_files))
        
        # Try to get list of remote files
        try:
            remote_files = set(list_repo_files(repo_id=repo_id, repo_type=repo_type))
            Message.log(message_type="remote_files_count", count=len(remote_files))
        except Exception as e:
            Message.log(message_type="remote_files_list_error", error=str(e))
            remote_files = set()
        
        for local_file in local_files:
            relative_path = local_file.relative_to(local_dir)
            relative_path_str = str(relative_path).replace("\\", "/")
            
            local_hash = calculate_file_hash(local_file)
            
            # Check if file exists remotely
            if relative_path_str in remote_files:
                # File exists, check if changed
                remote_hash = get_remote_file_hash(repo_id, relative_path_str, repo_type)
                
                if remote_hash is None or remote_hash != local_hash:
                    Message.log(
                        message_type="file_changed",
                        file=relative_path_str,
                        local_hash=local_hash,
                        remote_hash=remote_hash
                    )
                    files_to_upload.append(local_file)
                else:
                    Message.log(
                        message_type="file_unchanged",
                        file=relative_path_str
                    )
            else:
                # New file
                Message.log(
                    message_type="file_new",
                    file=relative_path_str,
                    hash=local_hash
                )
                files_to_upload.append(local_file)
        
        Message.log(message_type="files_to_upload_count", count=len(files_to_upload))
        return files_to_upload


def create_staging_directory(local_dir: Path, files_to_upload: list[Path]) -> Path:
    """
    Create a temporary staging directory with only the files to upload.
    This allows us to use upload_folder with only changed files.
    """
    with start_action(action_type="create_staging_directory"):
        staging_dir = Path(tempfile.mkdtemp(prefix="atomica_hf_upload_"))
        Message.log(message_type="staging_dir_created", path=str(staging_dir))
        
        for file_path in files_to_upload:
            relative_path = file_path.relative_to(local_dir)
            target_path = staging_dir / relative_path
            
            # Create parent directories
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file to staging
            shutil.copy2(file_path, target_path)
            Message.log(message_type="file_staged", file=str(relative_path))
        
        return staging_dir


@app.command()
def upload(
    local_dir: Path = typer.Option(
        Path("data/input/atomica_longevity_proteins"),
        help="Local directory containing files to upload"
    ),
    repo_id: str = typer.Option(
        "longevity-genie/atomica_longevity_proteins",
        help="HuggingFace dataset repository ID"
    ),
    token: Optional[str] = typer.Option(
        None,
        help="HuggingFace API token (uses HF_TOKEN env var if not provided)"
    ),
    log_file: Optional[Path] = typer.Option(
        None,
        help="Path to log file (optional)"
    ),
    commit_message: str = typer.Option(
        "Update dataset files",
        help="Commit message for the upload"
    ),
    dry_run: bool = typer.Option(
        False,
        help="Don't actually upload, just show what would be uploaded"
    )
) -> None:
    """
    Upload atomica_longevity_proteins dataset to HuggingFace Hub.
    Only uploads new or changed files using bulk upload.
    """
    # Load environment variables from .env file
    load_dotenv()
    
    if log_file:
        to_file(open(log_file, "w"))
    
    with start_action(
        action_type="upload_to_huggingface",
        repo_id=repo_id,
        local_dir=str(local_dir),
        dry_run=dry_run
    ):
        # Validate local directory exists
        if not local_dir.exists():
            typer.echo(f"Error: Local directory does not exist: {local_dir}", err=True)
            raise typer.Exit(code=1)
        
        # Initialize HF API
        api = HfApi(token=token)
        Message.log(message_type="hf_api_initialized")
        
        # Collect files to upload
        files_to_upload = collect_files_to_upload(local_dir, repo_id, repo_type="dataset")
        
        if not files_to_upload:
            typer.echo("No files to upload. All files are up to date.")
            Message.log(message_type="no_files_to_upload")
            return
        
        typer.echo(f"Found {len(files_to_upload)} files to upload:")
        for file_path in files_to_upload:
            relative_path = file_path.relative_to(local_dir)
            typer.echo(f"  - {relative_path}")
        
        if dry_run:
            typer.echo("\nDry run mode - no files were uploaded.")
            Message.log(message_type="dry_run_complete")
            return
        
        # Create staging directory with only files to upload
        staging_dir = create_staging_directory(local_dir, files_to_upload)
        
        try:
            # Upload folder using bulk upload
            typer.echo(f"\nUploading to {repo_id}...")
            
            upload_result = api.upload_folder(
                folder_path=str(staging_dir),
                repo_id=repo_id,
                repo_type="dataset",
                commit_message=commit_message,
                token=token
            )
            
            Message.log(
                message_type="upload_complete",
                commit_url=upload_result
            )
            typer.echo(f"Upload complete!")
            typer.echo(f"Commit URL: {upload_result}")
            
        finally:
            # Cleanup staging directory
            if staging_dir.exists():
                shutil.rmtree(staging_dir)
                Message.log(message_type="staging_dir_cleaned", path=str(staging_dir))


if __name__ == "__main__":
    app()

