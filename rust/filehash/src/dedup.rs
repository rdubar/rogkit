//! Duplicate file detection

use crate::HashResult;
use std::collections::HashMap;
use std::path::PathBuf;

/// Find duplicate files by hash
///
/// Demonstrates:
/// - Borrowing: Takes a borrowed slice of results
/// - Ownership: Returns owned HashMap
/// - Zero-copy: Groups files without copying paths unnecessarily
///
/// # Arguments
///
/// * `results` - Hash results to analyze (borrowed)
///
/// # Returns
///
/// HashMap of hash -> paths for files with duplicates (owned by caller)
pub fn find_duplicates(results: &[HashResult]) -> HashMap<String, Vec<PathBuf>> {
    // Build a map of hash -> paths
    // Demonstrates efficient grouping without unnecessary cloning
    let mut hash_map: HashMap<String, Vec<PathBuf>> = HashMap::new();

    for result in results {
        // Borrow the hash, clone only the PathBuf (which is cheap - just a pointer)
        hash_map
            .entry(result.hash.clone())
            .or_insert_with(Vec::new)
            .push(result.path.clone());
    }

    // Filter to only hashes with multiple files (duplicates)
    // Demonstrates iterator chains and functional programming
    hash_map
        .into_iter()
        .filter(|(_, paths)| paths.len() > 1)
        .collect()
}

/// Calculate total wasted space from duplicates
///
/// # Arguments
///
/// * `results` - Hash results to analyze (borrowed)
///
/// # Returns
///
/// Total bytes wasted by duplicate files
pub fn calculate_wasted_space(results: &[HashResult]) -> u64 {
    let duplicates = find_duplicates(results);

    let mut wasted = 0u64;
    for (hash, paths) in duplicates {
        // Find the file size (all duplicates have the same size)
        if let Some(original) = results.iter().find(|r| r.hash == hash) {
            // Wasted space = size * (count - 1)
            // Keep one copy, rest is wasted
            let duplicate_count = paths.len() as u64 - 1;
            wasted += original.size * duplicate_count;
        }
    }

    wasted
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn test_find_duplicates() {
        let results = vec![
            HashResult {
                path: PathBuf::from("/file1.txt"),
                hash: "abc123".to_string(),
                size: 100,
            },
            HashResult {
                path: PathBuf::from("/file2.txt"),
                hash: "abc123".to_string(),
                size: 100,
            },
            HashResult {
                path: PathBuf::from("/file3.txt"),
                hash: "def456".to_string(),
                size: 200,
            },
        ];

        let duplicates = find_duplicates(&results);
        assert_eq!(duplicates.len(), 1);
        assert_eq!(duplicates.get("abc123").unwrap().len(), 2);
    }

    #[test]
    fn test_calculate_wasted_space() {
        let results = vec![
            HashResult {
                path: PathBuf::from("/file1.txt"),
                hash: "abc123".to_string(),
                size: 100,
            },
            HashResult {
                path: PathBuf::from("/file2.txt"),
                hash: "abc123".to_string(),
                size: 100,
            },
            HashResult {
                path: PathBuf::from("/file3.txt"),
                hash: "abc123".to_string(),
                size: 100,
            },
        ];

        let wasted = calculate_wasted_space(&results);
        // 3 copies of 100 bytes = keep 1, waste 2*100 = 200
        assert_eq!(wasted, 200);
    }
}
