"""
CLI for resolving protein names from PDB IDs in JSONL.GZ files using AnAge database.

This module orchestrates the protein resolution workflow by using the core utilities
from the pdb_utils module.
"""
from typing import Optional
from pathlib import Path
import sys
from collections import OrderedDict

import typer
from eliot import start_action, Logger
from pycomfort.logging import to_nice_file, to_nice_stdout

from atomica_mcp.preprocessing.pdb_utils import (
    load_anage_data,
    load_pdb_annotations,
    fetch_pdb_metadata,
    get_chain_protein_name,
    get_chain_organism,
    get_chain_uniprot_ids,
    iter_jsonl_gz_lines,
    matches_filter,
    get_last_processed_line,
    StreamingJSONLWriter,
    StreamingCSVWriter,
    StreamingJSONArrayWriter,
    parse_line_numbers,
    parse_entry_id,
    get_project_data_dir,
    ANAGE_DATA,
    PDB_UNIPROT_DATA,
    PDB_TAXONOMY_DATA,
)


app = typer.Typer(help="Resolve protein names from PDB IDs in JSONL.GZ files", add_completion=False)


@app.command()
def resolve(
    input_file: Path = typer.Option(..., help="Path to the .jsonl.gz file to process"),
    line_numbers: Optional[str] = typer.Option(None, help="Line numbers to process (e.g., '1,5,10' or '1-10' or '1-5,10,15-20'). If not provided, processes all lines."),
    anage_file: Optional[Path] = typer.Option(None, help="Path to the AnAge database TSV file. If not provided, uses data/input/anage/anage_data.txt"),
    output: Path = typer.Option(..., help="Base output path (will create output.csv and output.jsonl.gz in data/output/)"),
    skip_jsonl: bool = typer.Option(False, help="If True, skip writing JSONL output"),
    skip_csv: bool = typer.Option(False, help="If True, skip writing CSV output"),
    append: bool = typer.Option(False, help="If True, resume from the last processed line in output files"),
    log_to_file: bool = typer.Option(False, help="If True, log detailed output to files in ./logs directory (only errors shown in stdout)"),
    log_dir: Path = typer.Option(Path("logs"), help="Directory for log files (only used if --log-to-file is set)"),
    log_file_name: str = typer.Option("resolve_proteins", help="Base name for log files without extension (only used if --log-to-file is set). Creates {log_file_name}.json and {log_file_name}.log"),
    clean_destinations: bool = typer.Option(True, help="If True, clean previous log destinations to keep only the current one"),
    show_chains: bool = typer.Option(True, help="Show individual chain information"),
    filter_organism: Optional[str] = typer.Option(None, help="Filter by organism name (case-insensitive partial match)"),
    filter_classification: Optional[str] = typer.Option(None, help="Filter by AnAge classification (e.g., Mammalia, Aves, Actinopterygii)"),
    mammals_only: bool = typer.Option(False, help="Shorthand to filter only mammalian proteins (same as --filter-classification Mammalia)"),
    timeout: int = typer.Option(10, help="Request timeout in seconds for API calls"),
    retries: int = typer.Option(3, help="Number of retry attempts for failed API calls"),
    pdb_cache_size: int = typer.Option(20000, help="Max unique PDB IDs cached in-memory (LRU)"),
    csv_batch_size: int = typer.Option(500, help="CSV rows per write batch to limit memory"),
    use_tsv: bool = typer.Option(True, help="If True, use local TSV files for data. If False, use RCSB API."),
) -> None:
    """
    Resolve protein names from PDB IDs in JSONL.GZ entries using AnAge database.
    
    Extracts PDB IDs from entries, queries RCSB PDB for metadata,
    resolves protein names for each chain, and filters using AnAge database for organism classification.
    
    By default, writes both output.csv and output.jsonl.gz with consistent naming.
    Use --skip-jsonl or --skip-csv to disable one format.
    Supports resume/append mode: Use --append flag to resume from the last processed line.
    
    Data locations:
    - AnAge database: data/input/anage/anage_data.txt
    - PDB annotations: data/input/pdb/*.tsv.gz
    - Results: data/output/
    """
    # Resolve default paths
    data_dir = get_project_data_dir()
    
    if anage_file is None:
        anage_file = data_dir / "input" / "anage" / "anage_data.txt"
    
    # Ensure output goes to data/output/ for relative paths, or create parent dirs for absolute paths
    output_dir = data_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / output.name if output.parent == Path(".") else output
    
    # Ensure parent directory exists for output (handles both relative and absolute paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # Derive output file paths from base output path
    output_csv: Optional[Path] = None if skip_csv else output.parent / f"{output.stem}.csv"
    output_jsonl: Optional[Path] = None if skip_jsonl else output.parent / f"{output.stem}.jsonl.gz"
    output_file: Optional[Path] = None  # JSON array output disabled by default
    
    # Configure logging
    if log_to_file:
        log_dir.mkdir(exist_ok=True)
        json_log = log_dir / f"{log_file_name}.json"
        rendered_log = log_dir / f"{log_file_name}.log"
        to_nice_file(json_log, rendered_log)
        # Keep only the last added destination (file logging) if flag is set
        if clean_destinations and len(Logger._destinations._destinations) > 1:
            Logger._destinations._destinations = [Logger._destinations._destinations[-1]]
    else:
        to_nice_stdout()
        # Keep only the last added destination (stdout logging) if flag is set
        if clean_destinations and len(Logger._destinations._destinations) > 1:
            Logger._destinations._destinations = [Logger._destinations._destinations[-1]]
    
    with start_action(action_type="resolve_proteins", input_file=str(input_file)) as action:
        action.log(
            message_type="output_config",
            csv_enabled=output_csv is not None,
            csv_path=str(output_csv) if output_csv else None,
            jsonl_enabled=output_jsonl is not None,
            jsonl_path=str(output_jsonl) if output_jsonl else None
        )
        
        # Load AnAge database
        action.log(message_type="loading_anage", anage_file=str(anage_file))
        anage_data = load_anage_data(anage_file)
        action.log(message_type="anage_loaded", organism_count=len(anage_data))
        
        # Load PDB annotations if using TSV mode
        if use_tsv:
            annotations_dir = data_dir / "input" / "pdb"
            if annotations_dir.exists():
                action.log(message_type="loading_pdb_annotations", annotation_dir=str(annotations_dir))
                load_pdb_annotations(annotations_dir)
                action.log(message_type="pdb_annotations_loaded")
            else:
                action.log(message_type="annotation_dir_not_found", annotation_dir=str(annotations_dir))
                # Fallback to API mode
                use_tsv = False
                action.log(message_type="fallback_to_api_mode")
        
        # Handle mammals_only shorthand
        if mammals_only:
            filter_classification = "Mammalia"
            action.log(message_type="filter_set", filter_type="mammals_only")
        
        # Determine starting line for resume/append mode
        start_line = 0
        if append:
            if output_jsonl:
                start_line = get_last_processed_line(output_jsonl)
                action.log(message_type="resume_mode_info", source="jsonl", last_line=start_line)
            elif output_csv:
                # Note: CSV might have multiple rows per input line, so tracking via JSONL is preferred
                action.log(message_type="warning_csv_append", message="CSV tracking is approximate since multiple rows can map to one input line. Consider enabling JSONL for accurate resume tracking.")
                start_line = get_last_processed_line(output_csv)
            
            if start_line > 0:
                action.log(message_type="resume_mode_enabled", starting_from_line=start_line)
        
        # Parse line numbers
        line_nums = None
        if line_numbers:
            line_nums = parse_line_numbers(line_numbers)
        elif start_line > 0:
            # In append mode, create a filter to skip already-processed lines
            from pdb_mcp.pdb_utils import LineNumberFilter
            line_nums = LineNumberFilter([], {i for i in range(start_line + 1, 10**9)})  # Skip lines up to start_line
        
        action.log(message_type="filtering_config", 
                  anage_only=True,
                  filter_organism=filter_organism,
                  filter_classification=filter_classification,
                  append_mode=append,
                  resume_from_line=start_line)
        
        # Echo resume status to user
        if append and start_line > 0:
            typer.echo(f"📄 Resuming from line {start_line}", err=False)
        
        # Counters for summary
        total_processed = 0
        total_passed_filter = 0
        # LRU cache for PDB metadata to prevent unbounded growth
        processed_pdb_ids: "OrderedDict[str, dict]" = OrderedDict()
        
        # Open streaming writers if needed
        jsonl_writer = StreamingJSONLWriter(output_jsonl, append=append).__enter__() if output_jsonl else None
        csv_writer = StreamingCSVWriter(output_csv, batch_size=csv_batch_size, append=append).__enter__() if output_csv else None
        json_array_writer = StreamingJSONArrayWriter(output_file).__enter__() if output_file else None
        
        try:
            # Stream through entries one at a time (memory efficient)
            for entry_data in iter_jsonl_gz_lines(input_file, line_nums):
                line_num = entry_data["line_number"]
                entry = entry_data["entry"]
                entry_id = entry.get("id", "")
                
                # Skip if we've already processed this line in append mode
                if append and line_num <= start_line:
                    continue
                
                # Parse entry ID to extract PDB and chain info
                parsed = parse_entry_id(entry_id)
                pdb_id = parsed["pdb_id"]
                
                # Fetch PDB metadata using LRU cache
                metadata = processed_pdb_ids.get(pdb_id)
                if metadata is None:
                    metadata = fetch_pdb_metadata(pdb_id, timeout=timeout, retries=retries, use_tsv=use_tsv)
                    processed_pdb_ids[pdb_id] = metadata
                    # Enforce LRU size limit
                    if len(processed_pdb_ids) > max(1, pdb_cache_size):
                        processed_pdb_ids.popitem(last=False)
                else:
                    # Refresh LRU order
                    processed_pdb_ids.move_to_end(pdb_id)
                
                # Build result
                result = {
                    "line_number": line_num,
                    "entry_id": entry_id,
                    "pdb_id": pdb_id,
                    "chains": {
                        "chain1": parsed["chain1"],
                        "chain2": parsed["chain2"],
                    },
                    "metadata": metadata,
                }
                
                # Resolve protein names, organism info, and UniProt IDs for chains
                if show_chains and metadata.get("found"):
                    result["chain_proteins"] = {
                        "chain1": get_chain_protein_name(metadata, parsed["chain1"]),
                        "chain2": get_chain_protein_name(metadata, parsed["chain2"]),
                    }
                    result["chain_organisms"] = {
                        "chain1": get_chain_organism(metadata, parsed["chain1"], anage_data),
                        "chain2": get_chain_organism(metadata, parsed["chain2"], anage_data),
                    }
                    result["chain_uniprot_ids"] = {
                        "chain1": get_chain_uniprot_ids(metadata, parsed["chain1"]),
                        "chain2": get_chain_uniprot_ids(metadata, parsed["chain2"]),
                    }
                
                total_processed += 1
                
                # Report progress every 1000 lines
                if total_processed % 1000 == 0:
                    typer.echo(f"✓ Processed {total_processed} lines ({total_passed_filter} passed filter)")
                
                # Apply filters
                passes_filter = matches_filter(result, filter_organism, filter_classification)
                
                if passes_filter:
                    total_passed_filter += 1
                    
                    # Write to JSONL immediately (streaming)
                    if jsonl_writer:
                        jsonl_writer.write_entry(entry)
                    
                    # Add to CSV writer (batched streaming)
                    if csv_writer:
                        csv_writer.add_result(result)
                    
                    # Stream JSON output if requested (no memory accumulation)
                    if json_array_writer:
                        json_array_writer.write_item(result)
                    
                    # Log result
                    anage_organisms = []
                    if show_chains and "chain_proteins" in result:
                        chain1_org = result.get("chain_organisms", {}).get("chain1", {})
                        chain2_org = result.get("chain_organisms", {}).get("chain2", {})
                        
                        if chain1_org.get("in_anage", False):
                            anage_organisms.append(chain1_org.get('scientific_name', ''))
                        if parsed['chain2'] and chain2_org.get("in_anage", False):
                            anage_organisms.append(chain2_org.get('scientific_name', ''))
                    
                    with start_action(
                        action_type="anage_entry_resolved",
                        line_number=line_num,
                        entry_id=entry_id,
                        pdb_id=pdb_id,
                        found=metadata.get("found", False),
                        organisms=anage_organisms
                    ):
                        pass
        finally:
            # Close writers
            if jsonl_writer:
                jsonl_writer.__exit__(None, None, None)
            if csv_writer:
                csv_writer.__exit__(None, None, None)
            if json_array_writer:
                json_array_writer.__exit__(None, None, None)
        
        # Summary
        unique_pdbs = len(processed_pdb_ids)
        
        action.log(
            message_type="processing_summary",
            total_processed=total_processed,
            passed_filter=total_passed_filter,
            unique_pdb_structures=unique_pdbs,
            filtered_out=total_processed - total_passed_filter,
            append_mode=append,
            resumed_from_line=start_line if append else 0
        )
        
        # Check if we have filtered results
        if total_passed_filter == 0 and (output_jsonl or output_csv):
            with start_action(action_type="no_results_warning"):
                pass
        
        # Log JSONL output if it was written
        if output_jsonl and total_passed_filter > 0:
            with start_action(action_type="save_jsonl", output_file=str(output_jsonl)) as jsonl_action:
                jsonl_action.log(message_type="jsonl_saved", path=str(output_jsonl), count=total_passed_filter, append_mode=append)
        
        # Log CSV output if it was written
        if output_csv and total_passed_filter > 0:
            with start_action(action_type="save_csv", output_file=str(output_csv)) as csv_action:
                csv_action.log(message_type="csv_saved", path=str(output_csv), append_mode=append)
        
        # Log JSON array output if it was written
        if output_file and total_passed_filter > 0:
            with start_action(action_type="save_json_array", output_file=str(output_file)) as json_action:
                json_action.log(message_type="json_saved", path=str(output_file), count=total_passed_filter)


if __name__ == "__main__":
    # Show help if no arguments provided
    if len(sys.argv) == 1:
        app(["--help"])
    else:
        app()

