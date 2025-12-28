//! File hashing implementation demonstrating ownership and parallelization

use anyhow::{Context, Result};
use memmap2::Mmap;
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::fs::File;
use std::path::{Path, PathBuf};
use indicatif::{ProgressBar, ProgressStyle};

/// Hash algorithms supported
#[derive(Debug, Clone, Copy)]
pub enum HashAlgorithm {
    /// BLAKE3 - fastest, modern, recommended
    Blake3,
    /// SHA-256 - widely compatible, standard
    Sha256,
    /// MD5 - legacy, not cryptographically secure
    Md5,
}

/// Result of hashing a file
///
/// Demonstrates Rust's ownership: this struct owns the PathBuf and String.
/// When dropped, memory is automatically freed - no garbage collector needed!
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HashResult {
    /// Path to the file (owned)
    pub path: PathBuf,
    /// Hex-encoded hash (owned)
    pub hash: String,
    /// File size in bytes
    pub size: u64,
}

/// Hash a single file
///
/// Demonstrates:
/// - Ownership: File handle is owned and automatically closed when function returns
/// - Borrowing: Path is borrowed (&Path) - no allocation
/// - Error handling: Result type for safe error propagation
///
/// # Arguments
///
/// * `path` - Path to file (borrowed, not copied)
/// * `algorithm` - Hash algorithm to use
///
/// # Returns
///
/// HashResult containing the hash and metadata (owned by caller)
pub fn hash_file(path: &Path, algorithm: HashAlgorithm) -> Result<HashResult> {
    // Open file - ownership transferred to this function
    let file = File::open(path)
        .with_context(|| format!("Failed to open file: {}", path.display()))?;

    // Get file size
    let metadata = file.metadata()
        .with_context(|| format!("Failed to get metadata: {}", path.display()))?;
    let size = metadata.len();

    // Memory-map the file for efficient zero-copy reading
    // The Mmap owns the mapping and will unmap when dropped - automatic cleanup
    let mmap = unsafe {
        Mmap::map(&file)
            .with_context(|| format!("Failed to mmap file: {}", path.display()))?
    };

    // Compute hash - borrowing the mmap data
    let hash = match algorithm {
        HashAlgorithm::Blake3 => {
            let hash = blake3::hash(&mmap);
            hash.to_hex().to_string()
        }
        HashAlgorithm::Sha256 => {
            use sha2::{Sha256, Digest};
            let mut hasher = Sha256::new();
            hasher.update(&mmap);
            format!("{:x}", hasher.finalize())
        }
        HashAlgorithm::Md5 => {
            let digest = md5::compute(&mmap);
            format!("{:x}", digest)
        }
    };

    // Return owned result - caller now owns this data
    Ok(HashResult {
        path: path.to_path_buf(),  // Convert borrowed &Path to owned PathBuf
        hash,
        size,
    })
    // File and Mmap are automatically closed/unmapped here - no manual cleanup needed
}

/// Hash multiple files in parallel
///
/// THIS IS WHERE RUST SHINES! Demonstrates fearless concurrency:
/// - Rayon automatically parallelizes the work across CPU cores
/// - Rust's type system guarantees no data races at compile time
/// - No locks, no mutexes needed - the compiler ensures thread safety
///
/// # Arguments
///
/// * `files` - Slice of file paths (borrowed)
/// * `algorithm` - Hash algorithm to use
/// * `show_progress` - Whether to show progress bar
///
/// # Returns
///
/// Vector of results (owned by caller)
pub fn hash_files_parallel(
    files: &[PathBuf],
    algorithm: HashAlgorithm,
    show_progress: bool,
) -> Result<Vec<HashResult>> {
    // Optional progress bar
    let progress = if show_progress {
        let pb = ProgressBar::new(files.len() as u64);
        pb.set_style(
            ProgressStyle::default_bar()
                .template("[{elapsed_precise}] {bar:40.cyan/blue} {pos}/{len} {msg}")
                .unwrap()
                .progress_chars("█▓▒░ "),
        );
        Some(pb)
    } else {
        None
    };

    // PARALLEL MAGIC HAPPENS HERE!
    //
    // .par_iter() creates a parallel iterator - work is automatically distributed
    // across all CPU cores. Each thread gets its own subset of files to process.
    //
    // Rust's ownership system ensures:
    // - No data races (each thread owns its file handle)
    // - No memory leaks (files are auto-closed in each thread)
    // - Thread safety is checked at compile time - no runtime overhead!
    let results: Vec<_> = files
        .par_iter()              // Create parallel iterator - spreads work across threads
        .map(|path| {            // Each thread runs this closure independently
            let result = hash_file(path, algorithm);  // Borrows path, owns result

            if let Some(ref pb) = progress {
                pb.inc(1);  // Thread-safe progress update
            }

            result
        })
        .collect::<Result<Vec<_>>>()?;  // Collect results, propagating any errors

    if let Some(pb) = progress {
        pb.finish_with_message("Done!");
    }

    Ok(results)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn test_hash_file_blake3() {
        let mut temp = NamedTempFile::new().unwrap();
        write!(temp, "Hello, Rust!").unwrap();

        let result = hash_file(temp.path(), HashAlgorithm::Blake3).unwrap();
        assert!(!result.hash.is_empty());
        assert_eq!(result.size, 12);
    }

    #[test]
    fn test_parallel_hashing() {
        // Create multiple temp files
        let mut temps = vec![];
        for i in 0..10 {
            let mut temp = NamedTempFile::new().unwrap();
            write!(temp, "File {}", i).unwrap();
            temps.push(temp);
        }

        let paths: Vec<_> = temps.iter().map(|t| t.path().to_path_buf()).collect();
        let results = hash_files_parallel(&paths, HashAlgorithm::Blake3, false).unwrap();

        assert_eq!(results.len(), 10);
    }
}
