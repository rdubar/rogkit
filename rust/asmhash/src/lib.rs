//! Hand-written ARM64 assembly primitives for Apple Silicon, exposed as
//! safe Rust functions and benchmarked against equivalent library
//! implementations from `filehash`.
//!
//! Scope is deliberately narrow: only the parts of each algorithm that map
//! onto a dedicated hardware instruction (FEAT_CRC32, FEAT_SHA256) are in
//! assembly. Buffer chunking / padding stays in Rust — mechanism in asm,
//! policy in Rust.

mod crc32c;
mod sha256;

pub use crc32c::crc32c;
pub use sha256::sha256;
