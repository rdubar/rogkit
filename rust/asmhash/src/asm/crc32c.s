// crc32c.s — ARM64 CRC-32C (Castagnoli) update using the FEAT_CRC32
// hardware instructions available on all Apple Silicon.
//
// Clang will not emit crc32cx/crc32cw/crc32ch/crc32cb from plain C or Rust
// source without explicit intrinsics — this is hand-written to use them
// directly, processing 8 bytes/instruction on the bulk of the buffer.
//
//   uint32_t rk_crc32c_update(uint32_t crc, const uint8_t *buf, size_t len);
//
// Takes the running CRC state (caller handles the initial ~0 / final ~0
// convention) and returns the updated state. Does not itself invert the
// value, so it composes across chunks.

    .arch armv8-a+crc
    .text
    .global _rk_crc32c_update
    .align 4

// x0 = crc (state, in w0), x1 = buf, x2 = len
_rk_crc32c_update:
.Lqword:
    cmp     x2, #8
    b.lt    .Lword
    ldr     x3, [x1], #8
    crc32cx w0, w0, x3
    sub     x2, x2, #8
    b       .Lqword

.Lword:
    cmp     x2, #4
    b.lt    .Lhword
    ldr     w3, [x1], #4
    crc32cw w0, w0, w3
    sub     x2, x2, #4

.Lhword:
    cmp     x2, #2
    b.lt    .Lbyte
    ldrh    w3, [x1], #2
    crc32ch w0, w0, w3
    sub     x2, x2, #2

.Lbyte:
    cbz     x2, .Ldone
    ldrb    w3, [x1]
    crc32cb w0, w0, w3

.Ldone:
    ret
