//! File system walking implementation

use anyhow::Result;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

/// Walk paths and collect all regular files
///
/// Demonstrates:
/// - Borrowing: Paths are borrowed, not copied
/// - Ownership: Returns owned PathBuf vector
/// - Iterator patterns: Functional programming style
///
/// # Arguments
///
/// * `paths` - Paths to walk (borrowed)
/// * `follow_links` - Whether to follow symbolic links
///
/// # Returns
///
/// Vector of file paths (owned by caller)
pub fn walk_paths(
    paths: &[impl AsRef<Path>],
    follow_links: bool,
) -> Result<Vec<PathBuf>> {
    let mut files = Vec::new();

    for path in paths {
        let path = path.as_ref();

        if path.is_file() {
            // Single file - just add it
            files.push(path.to_path_buf());
        } else if path.is_dir() {
            // Directory - walk it
            let walker = WalkDir::new(path)
                .follow_links(follow_links)
                .into_iter()
                .filter_map(|e| e.ok())  // Skip errors
                .filter(|e| e.file_type().is_file());  // Only files

            for entry in walker {
                files.push(entry.path().to_path_buf());
            }
        } else {
            anyhow::bail!("Path is neither file nor directory: {}", path.display());
        }
    }

    Ok(files)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    #[test]
    fn test_walk_single_file() {
        let temp = TempDir::new().unwrap();
        let file_path = temp.path().join("test.txt");
        fs::write(&file_path, "test").unwrap();

        let files = walk_paths(&[&file_path], false).unwrap();
        assert_eq!(files.len(), 1);
        assert_eq!(files[0], file_path);
    }

    #[test]
    fn test_walk_directory() {
        let temp = TempDir::new().unwrap();
        fs::write(temp.path().join("file1.txt"), "test1").unwrap();
        fs::write(temp.path().join("file2.txt"), "test2").unwrap();

        let files = walk_paths(&[temp.path()], false).unwrap();
        assert_eq!(files.len(), 2);
    }
}
