# Upload to HuggingFace

This script uploads the atomica_longevity_proteins dataset to HuggingFace Hub, intelligently uploading only new or changed files.

## Features

- **Bulk Upload**: Uses HuggingFace's `upload_folder` API to create a single commit with all changes
- **Smart Sync**: Compares local files with remote files using SHA256 hashes
- **Skip Unchanged**: Only uploads files that are new or have changed
- **Staging Directory**: Creates a temporary directory with only files to upload
- **Logging**: Full eliot logging support for debugging and tracking

## Installation

The script is already configured in `pyproject.toml`. After running `uv sync`, the command will be available as:

```bash
upload-to-hf
```

## Authentication

You need a HuggingFace token with write access. You can either:

1. Set the `HF_TOKEN` environment variable:
```bash
export HF_TOKEN=your_token_here
```

2. Pass it as a command-line option:
```bash
upload-to-hf --token your_token_here
```

Get your token from: https://huggingface.co/settings/tokens

## Usage

### Basic Usage

Upload with default settings:
```bash
upload-to-hf
```

### Custom Settings

```bash
upload-to-hf \
  --local-dir data/input/atomica_longevity_proteins \
  --repo-id longevity-genie/atomica_longevity_proteins \
  --commit-message "Update protein structures with new ATOMICA analysis" \
  --log-file logs/hf_upload.log
```

### Dry Run

See what would be uploaded without actually uploading:
```bash
upload-to-hf --dry-run
```

## Command Options

- `--local-dir`: Local directory containing files to upload (default: `data/input/atomica_longevity_proteins`)
- `--repo-id`: HuggingFace dataset repository ID (default: `longevity-genie/atomica_longevity_proteins`)
- `--token`: HuggingFace API token (uses `HF_TOKEN` env var if not provided)
- `--log-file`: Path to log file for eliot logging (optional)
- `--commit-message`: Commit message for the upload (default: "Update dataset files")
- `--dry-run`: Don't actually upload, just show what would be uploaded

## How It Works

1. **Scan Local Files**: Lists all files in the local directory
2. **List Remote Files**: Gets list of files already in the HuggingFace repo
3. **Compare Hashes**: For existing files, downloads and compares SHA256 hashes
4. **Identify Changes**: Determines which files are new or changed
5. **Stage Files**: Creates temporary directory with only files to upload
6. **Bulk Upload**: Uploads all changed files in a single commit
7. **Cleanup**: Removes temporary staging directory

## Example Output

```
Found 5 files to upload:
  - 8ax8_critical_residues.tsv
  - 8ax8_interact_scores.json
  - 8ax8_metadata.json
  - 8ax8_summary.json
  - 8ax8.cif

Uploading to longevity-genie/atomica_longevity_proteins...
Upload complete!
Commit URL: https://huggingface.co/datasets/longevity-genie/atomica_longevity_proteins/commit/abc123...
```

## Logging

If you specify a log file with `--log-file`, detailed eliot logs will be written including:
- File hash calculations
- Remote file comparisons
- Staging operations
- Upload progress

## Notes

- The script uses SHA256 hashing to detect changes
- Unchanged files are skipped automatically
- All uploads are batched into a single commit to avoid commit spam
- The staging directory is automatically cleaned up after upload

