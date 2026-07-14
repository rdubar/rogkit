//! Cross-checks the ARM64 asm CRC-32C against an independent bitwise
//! software implementation, plus the well-known CRC-32C check value, so a
//! bug in either the asm or my memory of the check value can't hide.

/// Slow, obviously-correct bitwise CRC-32C (Castagnoli, reflected).
fn crc32c_reference(data: &[u8]) -> u32 {
    const POLY: u32 = 0x82f6_3b78; // reversed 0x1EDC6F41
    let mut crc: u32 = !0;
    for &byte in data {
        crc ^= byte as u32;
        for _ in 0..8 {
            crc = if crc & 1 != 0 {
                (crc >> 1) ^ POLY
            } else {
                crc >> 1
            };
        }
    }
    !crc
}

#[test]
fn empty_is_zero() {
    assert_eq!(asmhash::crc32c(b""), 0);
}

#[test]
fn known_check_value() {
    // The standard CRC-32C check value for the ASCII digits "123456789".
    assert_eq!(asmhash::crc32c(b"123456789"), 0xe306_9283);
}

#[test]
fn matches_software_reference_across_lengths_and_alignments() {
    // Cover every tail-handling path in the asm loop (qword/word/hword/byte)
    // and force both aligned and unaligned start offsets.
    let data: Vec<u8> = (0..4099u32)
        .map(|i| i.wrapping_mul(2654435761u32) as u8)
        .collect();
    for offset in 0..8 {
        for len in [
            0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 16, 17, 63, 64, 65, 4096, 4099 - 8,
        ] {
            let slice = &data[offset..offset + len.min(data.len() - offset)];
            assert_eq!(
                asmhash::crc32c(slice),
                crc32c_reference(slice),
                "mismatch at offset={offset} len={len}"
            );
        }
    }
}
