//! Verifies the ARM64 crypto-extension SHA-256 core against NIST test
//! vectors and against the `sha2` crate (already used by `filehash`) across
//! every block-boundary edge case, so a transcription error in the hand
//! written asm can't hide.

use sha2::{Digest, Sha256};

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

#[test]
fn nist_empty_string() {
    assert_eq!(
        hex(&asmhash::sha256(b"")),
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    );
}

#[test]
fn nist_abc() {
    assert_eq!(
        hex(&asmhash::sha256(b"abc")),
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    );
}

#[test]
fn nist_two_block_message() {
    // FIPS 180-4 example: 448-bit message, exercises the "two padding
    // blocks" path in a different way than the empty-tail case below.
    let msg = b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
    assert_eq!(
        hex(&asmhash::sha256(msg)),
        "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"
    );
}

#[test]
fn matches_sha2_crate_at_every_block_boundary() {
    // 0, 55, 56, 63, 64, 65 exercise every padding edge case (single vs.
    // double pad block); the rest cover multi-block messages generally.
    for len in [
        0usize, 1, 2, 3, 55, 56, 57, 63, 64, 65, 119, 120, 121, 127, 128, 129, 1000, 100_000,
    ] {
        let data: Vec<u8> = (0..len).map(|i| (i as u32).wrapping_mul(2654435761) as u8).collect();

        let mut hasher = Sha256::new();
        hasher.update(&data);
        let expected = hasher.finalize();

        assert_eq!(
            asmhash::sha256(&data).as_slice(),
            expected.as_slice(),
            "mismatch at len={len}"
        );
    }
}
