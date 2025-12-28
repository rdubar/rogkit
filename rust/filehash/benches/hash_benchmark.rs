use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use filehash::{hash_file, HashAlgorithm};
use std::fs::File;
use std::io::Write;
use tempfile::TempDir;

fn create_test_files(count: usize, size: usize) -> (TempDir, Vec<std::path::PathBuf>) {
    let temp_dir = TempDir::new().unwrap();
    let mut paths = Vec::new();

    for i in 0..count {
        let path = temp_dir.path().join(format!("file_{}.bin", i));
        let mut file = File::create(&path).unwrap();

        // Write some data
        let data = vec![i as u8; size];
        file.write_all(&data).unwrap();

        paths.push(path);
    }

    (temp_dir, paths)
}

fn benchmark_hash_algorithms(c: &mut Criterion) {
    let (_temp, paths) = create_test_files(1, 1024 * 1024); // 1MB file
    let path = &paths[0];

    let mut group = c.benchmark_group("hash_algorithms");

    group.bench_with_input(
        BenchmarkId::new("blake3", "1MB"),
        path,
        |b, path| {
            b.iter(|| hash_file(black_box(path), HashAlgorithm::Blake3).unwrap())
        },
    );

    group.bench_with_input(
        BenchmarkId::new("sha256", "1MB"),
        path,
        |b, path| {
            b.iter(|| hash_file(black_box(path), HashAlgorithm::Sha256).unwrap())
        },
    );

    group.bench_with_input(
        BenchmarkId::new("md5", "1MB"),
        path,
        |b, path| {
            b.iter(|| hash_file(black_box(path), HashAlgorithm::Md5).unwrap())
        },
    );

    group.finish();
}

criterion_group!(benches, benchmark_hash_algorithms);
criterion_main!(benches);
