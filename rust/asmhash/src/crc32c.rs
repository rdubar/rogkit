//! CRC-32C (Castagnoli) using the ARMv8 FEAT_CRC32 instructions.

extern "C" {
    fn rk_crc32c_update(crc: u32, buf: *const u8, len: usize) -> u32;
}

/// Compute the CRC-32C (Castagnoli) checksum of `data`.
///
/// Matches the standard CRC-32C convention (init `!0`, final XOR `!0`) used
/// by iSCSI, ext4, Btrfs, etc. — the well-known check value for `"123456789"`
/// is `0xe3069283`.
pub fn crc32c(data: &[u8]) -> u32 {
    let updated = unsafe { rk_crc32c_update(!0u32, data.as_ptr(), data.len()) };
    !updated
}
