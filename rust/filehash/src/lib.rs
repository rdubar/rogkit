//! High-performance parallel file hasher and deduplicator
//!
//! This library demonstrates Rust's key features:
//! - **Ownership**: File handles are owned and automatically cleaned up
//! - **Borrowing**: Paths are borrowed, not copied, for zero-cost abstractions
//! - **Parallelization**: Files are hashed in parallel using Rayon with compile-time thread safety
//!
//! # Examples
//!
//! ```rust,no_run
//! use filehash::{hash_files, HashAlgorithm};
//! use std::path::Path;
//!
//! let paths = vec![Path::new(".")];
//! let results = hash_files(&paths, HashAlgorithm::Blake3, false, false).unwrap();
//! println!("Hashed {} files", results.len());
//! ```

mod hasher;
mod walker;
mod dedup;

pub use hasher::{HashAlgorithm, HashResult, hash_file};
pub use walker::walk_paths;
pub use dedup::find_duplicates;

use anyhow::Result;
use std::path::Path;

/// Output format for results
#[derive(Debug, Clone, Copy)]
pub enum OutputFormat {
    /// Human-readable output
    Human,
    /// JSON format
    Json,
    /// CSV format
    Csv,
}

/// Hash multiple files or directories in parallel
///
/// This function demonstrates:
/// - Borrowing: Paths are borrowed (&[impl AsRef<Path>])
/// - Parallelization: Uses Rayon for parallel processing
/// - Ownership: Results are collected and owned by caller
///
/// # Arguments
///
/// * `paths` - Slice of paths to hash (borrowed, not copied)
/// * `algorithm` - Hash algorithm to use
/// * `follow_links` - Whether to follow symbolic links
/// * `show_progress` - Whether to show a progress bar
///
/// # Returns
///
/// Vector of hash results, owned by the caller
pub fn hash_files(
    paths: &[impl AsRef<Path>],
    algorithm: HashAlgorithm,
    follow_links: bool,
    show_progress: bool,
) -> Result<Vec<HashResult>> {
    // Walk all paths to get file list (borrowing paths)
    let files = walk_paths(paths, follow_links)?;

    // Hash files in parallel (demonstrating fearless concurrency)
    let results = hasher::hash_files_parallel(&files, algorithm, show_progress)?;

    Ok(results)
}
