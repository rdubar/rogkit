//! SHA-256 using the ARMv8 FEAT_SHA256 crypto-extension instructions.
//!
//! Only the 64-round compression function is in assembly — message padding
//! and 64-byte block chunking stay in Rust. Mechanism (the ISA-specific hot
//! loop) is separated from policy (framing), so the asm core stays small
//! and testable in isolation.

extern "C" {
    /// Runs one 64-byte block through the SHA-256 compression function,
    /// updating `state` (8 native-endian u32 words) in place.
    fn rk_sha256_compress(state: *mut u32, block: *const u8);
}

const H0: [u32; 8] = [
    0x6a09_e667,
    0xbb67_ae85,
    0x3c6e_f372,
    0xa54f_f53a,
    0x510e_527f,
    0x9b05_688c,
    0x1f83_d9ab,
    0x5be0_cd19,
];

/// Compute the SHA-256 digest of `data`.
pub fn sha256(data: &[u8]) -> [u8; 32] {
    let mut state = H0;

    let mut chunks = data.chunks_exact(64);
    for block in &mut chunks {
        unsafe { rk_sha256_compress(state.as_mut_ptr(), block.as_ptr()) };
    }

    // Standard SHA-256 padding: 0x80, zeros, then the 64-bit big-endian
    // message length. Needs a second block if the tail has no room left
    // for the 8-byte length after the 0x80 marker.
    let remainder = chunks.remainder();
    let pad_len = if remainder.len() < 56 { 64 } else { 128 };
    let mut pad = [0u8; 128];
    pad[..remainder.len()].copy_from_slice(remainder);
    pad[remainder.len()] = 0x80;
    let bit_len = (data.len() as u64) * 8;
    pad[pad_len - 8..pad_len].copy_from_slice(&bit_len.to_be_bytes());

    for block in pad[..pad_len].chunks_exact(64) {
        unsafe { rk_sha256_compress(state.as_mut_ptr(), block.as_ptr()) };
    }

    let mut out = [0u8; 32];
    for (i, word) in state.iter().enumerate() {
        out[i * 4..i * 4 + 4].copy_from_slice(&word.to_be_bytes());
    }
    out
}
