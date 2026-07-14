fn main() {
    let target = std::env::var("TARGET").unwrap_or_default();
    if !target.starts_with("aarch64") {
        panic!(
            "asmhash only supports aarch64 (ARM64) targets — it uses hand-written \
             Apple Silicon assembly (FEAT_CRC32 / FEAT_SHA256). Target was: {target}"
        );
    }

    cc::Build::new()
        .file("src/asm/crc32c.s")
        .file("src/asm/sha256.s")
        .compile("asmhash_native");

    println!("cargo:rerun-if-changed=src/asm/crc32c.s");
    println!("cargo:rerun-if-changed=src/asm/sha256.s");
}
