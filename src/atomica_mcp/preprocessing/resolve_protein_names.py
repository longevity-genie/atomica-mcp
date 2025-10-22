import requests
import polars as pl
from pathlib import Path
from typing import List, Optional, Dict, Any
import time
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from eliot import start_action
import typer
from datetime import datetime

# Configure Polars to display all columns
pl.Config.set_tbl_cols(-1)  # Show all columns
pl.Config.set_tbl_width_chars(1000)  # Wider table display
pl.Config.set_fmt_str_lengths(100)  # Show more characters in strings

app = typer.Typer(help="Resolve protein names and gene symbols from UniProt IDs")

# UniProt API configuration
UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
UNIPROT_MAPPING_URL = "https://rest.uniprot.org/idmapping/run"
UNIPROT_MAPPING_STATUS_URL = "https://rest.uniprot.org/idmapping/status"
UNIPROT_RESULTS_URL = "https://rest.uniprot.org/idmapping/details"
BATCH_SIZE = 100  # IDs per request (reduced from 500 due to URL length limits in UniProt API)
REQUEST_TIMEOUT = 30
MAX_WORKERS = 5  # Parallel requests


def fetch_uniprot_batch(
    uniprot_ids: List[str],
    batch_size: int = BATCH_SIZE,
) -> pl.DataFrame:
    """
    Fetch protein names and gene symbols from UniProt for large batches.
    
    Args:
        uniprot_ids: List of UniProt accession IDs
        batch_size: Number of IDs per API request
    
    Returns:
        Polars DataFrame with protein information
    """
    all_results: List[pl.DataFrame] = []
    total_batches = (len(uniprot_ids) + batch_size - 1) // batch_size
    
    with start_action(
        action_type="uniprot_batch_fetch",
        total_ids=len(uniprot_ids),
        total_batches=total_batches,
    ) as action:
        for i in range(0, len(uniprot_ids), batch_size):
            batch = uniprot_ids[i : i + batch_size]
            batch_num = i // batch_size + 1
            
            try:
                # Build query: accession:Q9V2J8 OR accession:P12345 ...
                query = " OR ".join([f"accession:{uid}" for uid in batch])
                
                response = requests.get(
                    UNIPROT_SEARCH_URL,
                    params={
                        "query": query,
                        "format": "tsv",
                        "fields": "accession,protein_name,gene_names,organism_name,reviewed",
                    },
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                
                if response.text.strip():
                    df = pl.read_csv(
                        StringIO(response.text),
                        separator="\t",
                        schema_overrides={"Accession": pl.Utf8},
                    )
                    all_results.append(df)
                    typer.echo(
                        f"✓ Batch {batch_num}/{total_batches}: {len(batch)} IDs fetched",
                        err=False,
                    )
                else:
                    typer.echo(
                        f"⚠ Batch {batch_num}/{total_batches}: No results",
                        err=True,
                    )
            
            except Exception as e:
                typer.echo(
                    f"✗ Batch {batch_num}/{total_batches} failed: {e}",
                    err=True,
                )
                action.write_failure(batch_error=str(e), batch_num=batch_num)
    
    if all_results:
        return pl.concat(all_results)
    return pl.DataFrame()


def fetch_uniprot_parallel(
    uniprot_ids: List[str],
    batch_size: int = BATCH_SIZE,
    max_workers: int = MAX_WORKERS,
) -> pl.DataFrame:
    """
    Fetch protein information using parallel requests.
    
    Args:
        uniprot_ids: List of UniProt accession IDs
        batch_size: Number of IDs per API request
        max_workers: Number of parallel requests
    
    Returns:
        Polars DataFrame with protein information
    """
    
    def fetch_batch(batch: List[str]) -> pl.DataFrame:
        query = " OR ".join([f"accession:{uid}" for uid in batch])
        
        response = requests.get(
            UNIPROT_SEARCH_URL,
            params={
                "query": query,
                "format": "tsv",
                "fields": "accession,protein_name,gene_names,organism_name,reviewed",
            },
            timeout=REQUEST_TIMEOUT,
        )
        
        if response.status_code == 200 and response.text.strip():
            return pl.read_csv(StringIO(response.text), separator="\t")
        return pl.DataFrame()
    
    # Create batches
    batches = [
        uniprot_ids[i : i + batch_size]
        for i in range(0, len(uniprot_ids), batch_size)
    ]
    
    all_results: List[pl.DataFrame] = []
    
    with start_action(
        action_type="uniprot_parallel_fetch",
        total_batches=len(batches),
        max_workers=max_workers,
    ):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(fetch_batch, batch): i for i, batch in enumerate(batches)
            }
            
            for future in as_completed(futures):
                batch_num = futures[future]
                try:
                    result = future.result()
                    if len(result) > 0:
                        all_results.append(result)
                        typer.echo(
                            f"✓ Batch {batch_num + 1}/{len(batches)} completed",
                            err=False,
                        )
                except Exception as e:
                    typer.echo(
                        f"✗ Batch {batch_num + 1} failed: {e}",
                        err=True,
                    )
    
    return pl.concat(all_results) if all_results else pl.DataFrame()


def fetch_gene_symbols_batch(uniprot_ids: List[str]) -> pl.DataFrame:
    """
    Fetch Ensembl IDs from UniProt IDs using the ID Mapping service.
    Maps UniProt IDs to Ensembl IDs in batch.
    """
    if not uniprot_ids:
        return pl.DataFrame()
    
    try:
        with start_action(action_type="fetch_gene_symbols_batch") as action:
            typer.echo("  Submitting ID mapping request to UniProt...")
            
            # Submit mapping job
            response = requests.post(
                UNIPROT_MAPPING_URL,
                data={
                    "ids": " ".join(uniprot_ids),
                    "from": "UniProtKB_AC-ID",
                    "to": "Ensembl",
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            
            job_data = response.json()
            job_id = job_data.get("jobId")
            
            if not job_id:
                typer.echo("⚠ No job ID returned from UniProt")
                return pl.DataFrame()
            
            typer.echo(f"  Job ID: {job_id}")
            
            # Poll for results
            max_attempts = 60
            for attempt in range(max_attempts):
                status_response = requests.get(
                    f"{UNIPROT_MAPPING_STATUS_URL}/{job_id}",
                    timeout=REQUEST_TIMEOUT,
                )
                status_response.raise_for_status()
                status_data = status_response.json()
                
                if status_data.get("jobStatus") == "FINISHED":
                    typer.echo(f"  ✓ Mapping completed")
                    break
                
                if attempt % 10 == 0:
                    typer.echo(f"  Waiting for mapping... ({attempt}/{max_attempts})")
                time.sleep(1)
            
            # Fetch results - use stream endpoint
            download_url = f"https://rest.uniprot.org/idmapping/stream/{job_id}"
            
            typer.echo("  Downloading mapping results...")
            result_response = requests.get(
                download_url,
                params={"format": "tsv"},
                timeout=REQUEST_TIMEOUT,
            )
            result_response.raise_for_status()
            
            # Parse TSV results
            if result_response.text.strip():
                df = pl.read_csv(
                    StringIO(result_response.text),
                    separator="\t",
                )
                return df
            else:
                typer.echo("⚠ No mapping results returned")
                return pl.DataFrame()
    
    except Exception as e:
        typer.echo(f"✗ ID mapping failed: {e}", err=True)
        return pl.DataFrame()


def fetch_gene_names_batch(uniprot_ids: List[str]) -> pl.DataFrame:
    """
    Fetch gene names directly from UniProt IDs using ID mapping to Gene_Name database.
    This provides actual gene symbols instead of Ensembl IDs.
    """
    if not uniprot_ids:
        return pl.DataFrame()
    
    try:
        with start_action(action_type="fetch_gene_names_batch") as action:
            typer.echo("  Submitting gene name mapping request to UniProt...")
            
            # Submit mapping job to Gene_Name database
            response = requests.post(
                UNIPROT_MAPPING_URL,
                data={
                    "ids": " ".join(uniprot_ids),
                    "from": "UniProtKB_AC-ID",
                    "to": "Gene_Name",
                },
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            
            job_data = response.json()
            job_id = job_data.get("jobId")
            
            if not job_id:
                typer.echo("⚠ No job ID returned from UniProt")
                return pl.DataFrame()
            
            typer.echo(f"  Job ID: {job_id}")
            
            # Poll for results
            max_attempts = 60
            for attempt in range(max_attempts):
                status_response = requests.get(
                    f"{UNIPROT_MAPPING_STATUS_URL}/{job_id}",
                    timeout=REQUEST_TIMEOUT,
                )
                status_response.raise_for_status()
                status_data = status_response.json()
                
                if status_data.get("jobStatus") == "FINISHED":
                    typer.echo(f"  ✓ Gene name mapping completed")
                    break
                
                if attempt % 10 == 0:
                    typer.echo(f"  Waiting for gene name mapping... ({attempt}/{max_attempts})")
                time.sleep(1)
            
            # Fetch results
            download_url = f"https://rest.uniprot.org/idmapping/stream/{job_id}"
            
            typer.echo("  Downloading gene name results...")
            result_response = requests.get(
                download_url,
                params={"format": "tsv"},
                timeout=REQUEST_TIMEOUT,
            )
            result_response.raise_for_status()
            
            # Parse TSV results
            if result_response.text.strip():
                df = pl.read_csv(
                    StringIO(result_response.text),
                    separator="\t",
                )
                return df
            else:
                typer.echo("⚠ No gene name results returned")
                return pl.DataFrame()
    
    except Exception as e:
        typer.echo(f"✗ Gene name mapping failed: {e}", err=True)
        return pl.DataFrame()


def fetch_gene_info_from_ensembl(ensembl_ids: List[str]) -> pl.DataFrame:
    """
    Fetch gene names from Ensembl IDs using the REST API or local tools.
    This provides gene names for entries where UniProt didn't return them.
    """
    if not ensembl_ids:
        return pl.DataFrame()
    
    try:
        import requests
        
        # Use Ensembl REST API to get gene names
        results = []
        for ensembl_id in ensembl_ids[:100]:  # Limit to 100 per batch
            try:
                response = requests.get(
                    f"https://rest.ensembl.org/lookup/id/{ensembl_id}",
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    results.append({
                        "ensembl_id": ensembl_id,
                        "gene_name_from_ensembl": data.get("external_name")
                    })
            except Exception as e:
                continue
        
        if results:
            return pl.DataFrame(results)
    except Exception as e:
        pass
    
    return pl.DataFrame()


def extract_gene_name_from_ensembl_id(ensembl_id: str) -> Optional[str]:
    """
    Extract a simplified gene name/identifier from Ensembl ID.
    Ensembl IDs like 'ENSG00000064313.13' map to genes like ENSG00000064313.
    We can use this as a fallback when UniProt doesn't return gene names.
    """
    if not ensembl_id:
        return None
    try:
        # Take just the main part without version number
        # e.g., ENSG00000064313.13 -> ENSG00000064313
        return ensembl_id.split('.')[0]
    except:
        return None


@app.command()
def resolve(
    input_file: Path = typer.Option(
        Path("data/output/PP_graph_embeddings.parquet"),
        "--input-file",
        "-i",
        help="Path to PP_graph_embeddings.parquet",
    ),
    output_file: Path = typer.Option(
        Path("data/output/protein_names.parquet"),
        "--output-file",
        "-o",
        help="Path to save results",
    ),
    uniprot_column: str = typer.Option(
        "UniProtKB_AC",
        "--uniprot-column",
        "-u",
        help="Column name containing UniProt IDs",
    ),
    resolve_genes: bool = typer.Option(
        True,
        "--resolve-genes/--no-resolve-genes",
        help="Resolve gene symbols and Ensembl IDs (default: enabled)",
    ),
    parallel: bool = typer.Option(
        True,
        "--parallel/--no-parallel",
        help="Use parallel requests (faster but more network intensive)",
    ),
    batch_size: int = typer.Option(
        BATCH_SIZE,
        "--batch-size",
        "-b",
        help="IDs per API request",
    ),
    max_workers: int = typer.Option(
        MAX_WORKERS,
        "--max-workers",
        "-w",
        help="Number of parallel workers (if --parallel)",
    ),
    resolve_sequences: bool = typer.Option(
        False,
        "--resolve-sequences/--no-resolve-sequences",
        help="Also fetch protein sequences from UniProt (default: disabled, set to True to enable)",
    ),
    verbose: bool = typer.Option(
        True,
        "--verbose/--no-verbose",
        help="Enable verbose output",
    ),
) -> None:
    """
    Resolve protein names, gene symbols, and Ensembl IDs from UniProt IDs.
    
    This command:
    1. Loads UniProt IDs from input Parquet file (default: PP_graph_embeddings.parquet)
    2. Fetches protein names from UniProt API
    3. Resolves gene symbols from UniProt ID Mapping API (Gene_Name database)
    4. Resolves Ensembl gene IDs from UniProt ID Mapping API (fills gaps in input Ensembl IDs)
    5. Joins results back with original data
    6. Saves enriched data to output file
    
    Output includes:
    - uniprot_protein_names: Protein names from UniProt
    - uniprot_gene_names: All gene name aliases (space-separated)
    - primary_gene_name: Primary gene symbol (NULL if not resolved from UniProt or mapping databases)
    - ensembl_id: Ensembl gene identifier (from input or API resolution)
    - uniprot_organism_name: Organism name
    
    Note: Gene symbols are NOT filled with Ensembl IDs as fallback. 
    If UniProt doesn't return a gene symbol, primary_gene_name will be NULL.
    """
    
    typer.echo(f"🔄 Loading {input_file}...")
    
    if not input_file.exists():
        typer.echo(f"✗ Input file not found: {input_file}", err=True)
        raise typer.Exit(1)
    
    df = pl.read_parquet(input_file)
    typer.echo(f"✓ Loaded {df.height} rows, {df.width} columns")
    
    if uniprot_column not in df.columns:
        typer.echo(
            f"✗ Column '{uniprot_column}' not found. Available columns: {df.columns}",
            err=True,
        )
        raise typer.Exit(1)
    
    # Extract unique UniProt IDs
    uniprot_ids = (
        df.select(uniprot_column)
        .unique()
        .filter(pl.col(uniprot_column).is_not_null())
        .to_series()
        .to_list()
    )
    
    typer.echo(f"📊 Found {len(uniprot_ids)} unique UniProt IDs")
    
    if len(uniprot_ids) == 0:
        typer.echo("✗ No UniProt IDs found in the specified column", err=True)
        raise typer.Exit(1)
    
    # Fetch protein information
    typer.echo(
        f"🔍 Fetching protein information from UniProt API "
        f"({'parallel' if parallel else 'sequential'})..."
    )
    
    start_time = time.time()
    
    if parallel:
        result_df = fetch_uniprot_parallel(
            uniprot_ids, batch_size=batch_size, max_workers=max_workers
        )
    else:
        result_df = fetch_uniprot_batch(uniprot_ids, batch_size=batch_size)
    
    elapsed = time.time() - start_time
    typer.echo(f"✓ Fetched {len(result_df)} proteins in {elapsed:.1f}s")
    
    if len(result_df) == 0:
        typer.echo("✗ No results from UniProt API", err=True)
        raise typer.Exit(1)
    
    # Standardize column names for joining
    result_df = result_df.rename({"Entry": "UniProtKB_AC"})
    
    if verbose:
        typer.echo(f"\n📋 UniProt API response columns: {result_df.columns}")
        typer.echo(f"\n📊 Sample results:")
        typer.echo(str(result_df.head(5)))
    
    # Join with original data
    typer.echo(f"\n🔗 Joining with original data...")
    
    enriched_df = df.join(
        result_df.select(["UniProtKB_AC", "Protein names", "Gene Names", "Organism"]).unique(),
        on="UniProtKB_AC",
        how="left",
    )
    
    # Rename columns for clarity
    enriched_df = enriched_df.rename({
        "Protein names": "uniprot_protein_names",
        "Gene Names": "uniprot_gene_names",
        "Organism": "uniprot_organism_name",
    })
    
    # Keep all columns - don't drop protein names anymore!
    # uniprot_protein_names = protein name from UniProt API
    # UniProtKB_AC = UniProt accession ID for reference

    # Extract primary gene name only (first in space-separated list)
    enriched_df = enriched_df.with_columns([
        pl.col("uniprot_gene_names")
        .str.split(" ")
        .list.first()
        .alias("primary_gene_name")
    ])
    
    # Initialize ensembl_id column if it doesn't exist
    if "ensembl_id" not in enriched_df.columns:
        enriched_df = enriched_df.with_columns([
            pl.lit(None, dtype=pl.Utf8).alias("ensembl_id")
        ])
    
    # Optional gene symbol resolution
    if resolve_genes:
        typer.echo(f"\n🧬 Resolving gene symbols and Ensembl IDs from UniProt IDs...")
        
        # Get unique UniProt IDs for mapping
        uniprot_ids_for_mapping = enriched_df.filter(
            pl.col("UniProtKB_AC").is_not_null()
        ).select("UniProtKB_AC").unique().to_series().to_list()
        
        if uniprot_ids_for_mapping:
            typer.echo(f"📚 Mapping {len(uniprot_ids_for_mapping)} UniProt IDs...")
            
            # FIRST: Try to get gene names directly
            typer.echo(f"\n1️⃣  Resolving gene symbols (Gene_Name database)...")
            gene_names_df = fetch_gene_names_batch(uniprot_ids_for_mapping)
            
            if len(gene_names_df) > 0:
                typer.echo(f"✓ Retrieved gene symbols for {len(gene_names_df)} entries")
                
                # Rename and join
                gene_names_df = gene_names_df.rename({
                    "From": "UniProtKB_AC",
                    "To": "gene_symbol_from_api"
                })
                
                # Deduplicate: keep only first gene symbol per UniProt ID
                gene_names_df = gene_names_df.group_by("UniProtKB_AC").first()
                
                enriched_df = enriched_df.join(
                    gene_names_df.select(["UniProtKB_AC", "gene_symbol_from_api"]),
                    on="UniProtKB_AC",
                    how="left",
                )
                
                # Update primary_gene_name with API gene symbols
                enriched_df = enriched_df.with_columns([
                    pl.when(pl.col('gene_symbol_from_api').is_not_null())
                    .then(pl.col('gene_symbol_from_api'))
                    .otherwise(pl.col('primary_gene_name'))
                    .alias('primary_gene_name_updated')
                ])
                
                enriched_df = enriched_df.drop("primary_gene_name").rename({"primary_gene_name_updated": "primary_gene_name"})
                if "gene_symbol_from_api" in enriched_df.columns:
                    enriched_df = enriched_df.drop("gene_symbol_from_api")
                
                gene_symbol_count = enriched_df.filter(pl.col('primary_gene_name').is_not_null()).height
                typer.echo(f"  - Entries with gene symbols: {gene_symbol_count}")
            else:
                typer.echo("⚠ Gene name mapping returned no results")
            
            # SECOND: Get Ensembl IDs for remaining entries
            typer.echo(f"\n2️⃣  Resolving Ensembl IDs (Ensembl database)...")
            ensembl_df = fetch_gene_symbols_batch(uniprot_ids_for_mapping)
            
            if len(ensembl_df) > 0:
                typer.echo(f"✓ Retrieved Ensembl IDs for {len(ensembl_df)} entries")
                
                # Rename columns for consistency
                ensembl_df = ensembl_df.rename({
                    "From": "UniProtKB_AC",
                    "To": "ensembl_id_resolved"
                })
                
                # Deduplicate: keep only first Ensembl ID per UniProt ID  
                ensembl_df = ensembl_df.group_by("UniProtKB_AC").first()
                
                # Join with enriched_df
                enriched_df = enriched_df.join(
                    ensembl_df.select(["UniProtKB_AC", "ensembl_id_resolved"]).unique(),
                    on="UniProtKB_AC",
                    how="left",
                )
                
                # Update ensembl_id column - only if input doesn't already have it
                # (input Ensembl IDs are kept as-is, API-resolved ones fill gaps)
                enriched_df = enriched_df.with_columns([
                    pl.coalesce(pl.col("ensembl_id"), pl.col("ensembl_id_resolved")).alias("ensembl_id_new")
                ])
                
                enriched_df = enriched_df.drop("ensembl_id").rename({"ensembl_id_new": "ensembl_id"})
                
                if "ensembl_id_resolved" in enriched_df.columns:
                    enriched_df = enriched_df.drop("ensembl_id_resolved")
                
                typer.echo(f"  - Entries with Ensembl IDs: {enriched_df.filter(pl.col('ensembl_id').is_not_null()).height}")
            else:
                typer.echo("⚠ Ensembl ID mapping returned no results")
            
            # Summary of gene symbol resolution
            final_count = enriched_df.filter(pl.col('primary_gene_name').is_not_null()).height
            typer.echo(f"\n✓ Gene symbol resolution complete: {final_count} entries with gene symbols")
            typer.echo(f"  Note: Entries without resolved gene symbols have NULL values (no fallback)")
        else:
            typer.echo("⚠ No UniProt IDs found for mapping")
    
    typer.echo(f"✓ Enriched data: {enriched_df.height} rows, {enriched_df.width} columns")
    
    # Note: Some entries may have multiple mappings (e.g., multiple ensembl IDs)
    # This is expected behavior. We keep all rows from the original input.
    # If you want one row per unique ID, you can deduplicate later.

    # Save results
    output_file.parent.mkdir(parents=True, exist_ok=True)
    enriched_df.write_parquet(output_file)
    
    typer.echo(f"✅ Results saved to {output_file}")
    
    # Summary statistics
    typer.echo(f"\n📈 Summary:")
    typer.echo(f"  - Total proteins: {enriched_df.height}")
    
    # Protein names
    with_protein_names = enriched_df.filter(pl.col('uniprot_protein_names').is_not_null()).height
    typer.echo(f"  - With protein names from UniProt: {with_protein_names}")
    
    # Gene names
    typer.echo(
        f"  - With gene symbols: {enriched_df.filter(pl.col('primary_gene_name').is_not_null()).height}"
    )
    
    # Ensembl IDs
    if resolve_genes and "ensembl_id" in enriched_df.columns:
        typer.echo(
            f"  - With Ensembl IDs: {enriched_df.filter(pl.col('ensembl_id').is_not_null()).height}"
        )
    
    typer.echo(f"  - Output file: {output_file.absolute()}")
    
    with start_action(action_type="resolve_complete"):
        pass


@app.command()
def sample(
    input_file: Path = typer.Option(
        Path("data/output/PP_extended.parquet"),
        "--input-file",
        "-i",
        help="Path to PP_extended.parquet",
    ),
    uniprot_column: str = typer.Option(
        "UniProtKB_AC",
        "--uniprot-column",
        "-u",
        help="Column name containing UniProt IDs",
    ),
    sample_size: int = typer.Option(
        10,
        "--sample-size",
        "-n",
        help="Number of samples to fetch",
    ),
    resolve_genes: bool = typer.Option(
        True,
        "--resolve-genes/--no-resolve-genes",
        help="Also resolve Ensembl gene IDs (default: enabled)",
    ),
) -> None:
    """
    Test UniProt API with a small sample of IDs.
    """
    
    typer.echo(f"📖 Loading {input_file}...")
    
    if not input_file.exists():
        typer.echo(f"✗ Input file not found: {input_file}", err=True)
        raise typer.Exit(1)
    
    df = pl.read_parquet(input_file)
    
    # Get sample IDs
    sample_ids = (
        df.select(uniprot_column)
        .filter(pl.col(uniprot_column).is_not_null())
        .unique()
        .sample(min(sample_size, df.height))
        .to_series()
        .to_list()
    )
    
    typer.echo(f"🧪 Testing with {len(sample_ids)} sample IDs: {sample_ids}")
    
    # Fetch sample data
    result_df = fetch_uniprot_batch(sample_ids, batch_size=BATCH_SIZE)
    
    if len(result_df) > 0:
        typer.echo(f"\n✅ Successfully fetched {len(result_df)} proteins from UniProt")
        
        # Join with original data to show complete picture
        result_df = result_df.rename({"Entry": "UniProtKB_AC"})
        
        # Get sample rows from original data
        sample_df = df.filter(pl.col(uniprot_column).is_in(sample_ids))
        
        # Join
        enriched_sample = sample_df.join(
            result_df.select(["UniProtKB_AC", "Protein names", "Gene Names", "Organism"]),
            on="UniProtKB_AC",
            how="left",
        )
        
        # Rename and extract primary gene
        enriched_sample = enriched_sample.rename({
            "Gene Names": "uniprot_gene_names",
            "Organism": "uniprot_organism_name",
        })
        
        # Drop protein names (using UniProtKB_AC for resolution)
        if "Protein names" in enriched_sample.columns:
            enriched_sample = enriched_sample.drop("Protein names")
        
        # Extract primary gene name
        enriched_sample = enriched_sample.with_columns([
            pl.col("uniprot_gene_names")
            .str.split(" ")
            .list.first()
            .alias("primary_gene_name")
        ])
        
        typer.echo(f"\n📊 Sample with ALL columns ({enriched_sample.width} columns):")
        typer.echo(str(enriched_sample))
        
        # Optional gene resolution test
        if resolve_genes:
            typer.echo(f"\n🧬 Testing Ensembl ID resolution...")
            
            # Test with first 5 UniProt IDs (already renamed to UniProtKB_AC)
            test_ids = result_df.select("UniProtKB_AC").to_series().to_list()[:5]
            typer.echo(f"  Testing with UniProt IDs: {test_ids}")
            
            gene_result_df = fetch_gene_symbols_batch(test_ids)
            
            if len(gene_result_df) > 0:
                typer.echo(f"\n✅ Ensembl resolution successful:")
                typer.echo(str(gene_result_df))
            else:
                typer.echo("⚠ No Ensembl results (may need to wait longer or check UniProt API status)")
    else:
        typer.echo("✗ No results from UniProt API", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
