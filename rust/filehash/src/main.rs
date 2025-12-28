use anyhow::Result;
use clap::{Parser, ValueEnum};
use colored::Colorize;
use std::path::PathBuf;

use filehash::{hash_files, find_duplicates, HashAlgorithm, OutputFormat};

/// High-performance parallel file hasher and deduplicator
///
/// Demonstrates Rust's ownership, borrowing, and concurrency features
/// by efficiently hashing files in parallel and finding duplicates.
#[derive(Parser, Debug)]
#[command(name = "filehash")]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Paths to hash (files or directories)
    #[arg(required = true)]
    paths: Vec<PathBuf>,

    /// Hash algorithm to use
    #[arg(short, long, value_enum, default_value = "blake3")]
    algorithm: HashAlgorithmArg,

    /// Find and report duplicate files
    #[arg(short, long)]
    duplicates: bool,

    /// Follow symbolic links
    #[arg(short = 'L', long)]
    follow_links: bool,

    /// Output format
    #[arg(short, long, value_enum, default_value = "human")]
    format: OutputFormatArg,

    /// Output file (defaults to stdout)
    #[arg(short, long)]
    output: Option<PathBuf>,

    /// Show progress bar
    #[arg(short, long)]
    progress: bool,

    /// Number of threads (defaults to number of CPUs)
    #[arg(short = 'j', long)]
    threads: Option<usize>,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum HashAlgorithmArg {
    /// BLAKE3 (fastest, recommended)
    Blake3,
    /// SHA-256 (widely compatible)
    Sha256,
    /// MD5 (legacy, not secure)
    Md5,
}

impl From<HashAlgorithmArg> for HashAlgorithm {
    fn from(arg: HashAlgorithmArg) -> Self {
        match arg {
            HashAlgorithmArg::Blake3 => HashAlgorithm::Blake3,
            HashAlgorithmArg::Sha256 => HashAlgorithm::Sha256,
            HashAlgorithmArg::Md5 => HashAlgorithm::Md5,
        }
    }
}

#[derive(Debug, Clone, Copy, ValueEnum)]
enum OutputFormatArg {
    /// Human-readable table format
    Human,
    /// JSON output
    Json,
    /// CSV output
    Csv,
}

impl From<OutputFormatArg> for OutputFormat {
    fn from(arg: OutputFormatArg) -> Self {
        match arg {
            OutputFormatArg::Human => OutputFormat::Human,
            OutputFormatArg::Json => OutputFormat::Json,
            OutputFormatArg::Csv => OutputFormat::Csv,
        }
    }
}

fn main() -> Result<()> {
    let args = Args::parse();

    // Set number of threads if specified
    if let Some(threads) = args.threads {
        rayon::ThreadPoolBuilder::new()
            .num_threads(threads)
            .build_global()
            .expect("Failed to set thread pool size");
    }

    // Print header
    if matches!(args.format, OutputFormatArg::Human) {
        println!(
            "{} {} using {}",
            "filehash".bright_cyan().bold(),
            env!("CARGO_PKG_VERSION"),
            format!("{:?}", args.algorithm).bright_yellow()
        );
        println!();
    }

    // Hash files
    let results = hash_files(
        &args.paths,
        args.algorithm.into(),
        args.follow_links,
        args.progress,
    )?;

    // Find duplicates if requested
    if args.duplicates {
        let duplicates = find_duplicates(&results);

        if matches!(args.format, OutputFormatArg::Human) {
            if duplicates.is_empty() {
                println!("{}", "No duplicates found!".bright_green());
            } else {
                println!(
                    "{} {} groups of duplicates:",
                    "Found".bright_red().bold(),
                    duplicates.len()
                );
                println!();

                for (hash, paths) in duplicates {
                    println!("{} {}", "Hash:".bright_cyan(), hash);
                    println!("{} {} files", "Files:".bright_cyan(), paths.len());
                    for path in paths {
                        println!("  • {}", path.display());
                    }
                    println!();
                }
            }
        }
    } else {
        // Output results
        let output_format: OutputFormat = args.format.into();
        if let Some(output_path) = args.output {
            // TODO: Write to file
            println!("Writing to {:?} in format {:?}", output_path, output_format);
        } else {
            // Write to stdout
            if matches!(args.format, OutputFormatArg::Human) {
                println!("{} {} files", "Hashed".bright_green().bold(), results.len());
                println!();
                for result in results.iter().take(10) {
                    println!("{} {}", result.hash.bright_yellow(), result.path.display());
                }
                if results.len() > 10 {
                    println!("... and {} more", results.len() - 10);
                }
            }
        }
    }

    Ok(())
}
