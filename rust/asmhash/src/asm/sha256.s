// sha256.s — SHA-256 block compression using the ARMv8 FEAT_SHA256 crypto
// extension instructions (sha256h/sha256h2/sha256su0/sha256su1) available
// on all Apple Silicon.
//
// Only the compression function is here; message padding and 64-byte block
// chunking live in Rust (sha256.rs) — this is deliberately just the part
// that maps onto dedicated hardware instructions Clang won't emit without
// explicit intrinsics.
//
// Message-schedule words W0..W15 are held in four rotating registers
// (v5,v6,v7,v8), each holding 4 consecutive words. For round-quad q>=4,
// SHA256SU0 primes the register that held W[q-4] (right after its raw
// value is consumed) with a partial result, and SHA256SU1 completes it one
// quad later into W[q] using the two windows that haven't been overwritten
// yet — so the same four registers cycle through the full W0..W63 schedule
// without ever needing more than a 4-deep window in flight.
//
//   void rk_sha256_compress(uint32_t state[8], const uint8_t block[64]);
//
// state is 8 native-endian u32 words (A..H), updated in place. block is
// one 64-byte message block.

    .arch armv8-a+crypto
    .text
    .global _rk_sha256_compress
    .align 4

// x0 = state, x1 = block
_rk_sha256_compress:
    // v8 is the only callee-saved register we touch (AAPCS64: low 64 bits
    // of v8-v15 must be preserved) — save/restore it around the function.
    str     d8, [sp, #-16]!

    ld1     {v0.4s, v1.4s}, [x0]      // v0 = ABCD, v1 = EFGH (kept pristine)
    mov     v2.16b, v0.16b            // v2 = ABCD working
    mov     v3.16b, v1.16b            // v3 = EFGH working

    ld1     {v5.4s, v6.4s, v7.4s, v8.4s}, [x1]   // W0-3, W4-7, W8-11, W12-15
    rev32   v5.16b, v5.16b                        // message bytes are
    rev32   v6.16b, v6.16b                        // big-endian; block
    rev32   v7.16b, v7.16b                        // memory is little-endian
    rev32   v8.16b, v8.16b

    adrp    x2, Lsha256_k@PAGE
    add     x2, x2, Lsha256_k@PAGEOFF

    // Round-quads 0-3: raw message words, no schedule expansion yet.
    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v5.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su0 v5.4s, v6.4s

    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v6.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su0 v6.4s, v7.4s
    sha256su1 v5.4s, v7.4s, v8.4s

    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v7.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su0 v7.4s, v8.4s
    sha256su1 v6.4s, v8.4s, v5.4s

    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v8.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su0 v8.4s, v5.4s
    sha256su1 v7.4s, v5.4s, v6.4s

    // Round-quads 4-11: full schedule expansion (prime + complete each).
    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v5.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su0 v5.4s, v6.4s
    sha256su1 v8.4s, v6.4s, v7.4s

    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v6.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su0 v6.4s, v7.4s
    sha256su1 v5.4s, v7.4s, v8.4s

    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v7.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su0 v7.4s, v8.4s
    sha256su1 v6.4s, v8.4s, v5.4s

    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v8.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su0 v8.4s, v5.4s
    sha256su1 v7.4s, v5.4s, v6.4s

    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v5.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su0 v5.4s, v6.4s
    sha256su1 v8.4s, v6.4s, v7.4s

    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v6.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su0 v6.4s, v7.4s
    sha256su1 v5.4s, v7.4s, v8.4s

    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v7.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su0 v7.4s, v8.4s
    sha256su1 v6.4s, v8.4s, v5.4s

    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v8.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su0 v8.4s, v5.4s
    sha256su1 v7.4s, v5.4s, v6.4s

    // Round-quad 12: last completion needed (W60-63), no more priming.
    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v5.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s
    sha256su1 v8.4s, v6.4s, v7.4s

    // Round-quads 13-15: schedule is fully expanded, plain rounds only.
    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v6.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s

    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v7.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s

    ld1     {v17.4s}, [x2], #16
    add     v16.4s, v8.4s, v17.4s
    mov     v4.16b, v2.16b
    sha256h  q2, q3, v16.4s
    sha256h2 q3, q4, v16.4s

    // Davies-Meyer feed-forward: new state = old state + round output.
    add     v0.4s, v0.4s, v2.4s
    add     v1.4s, v1.4s, v3.4s
    st1     {v0.4s, v1.4s}, [x0]

    ldr     d8, [sp], #16
    ret

    .align  4
Lsha256_k:
    .word   0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5
    .word   0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5
    .word   0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3
    .word   0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174
    .word   0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc
    .word   0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da
    .word   0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7
    .word   0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967
    .word   0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13
    .word   0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85
    .word   0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3
    .word   0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070
    .word   0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5
    .word   0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3
    .word   0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208
    .word   0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
