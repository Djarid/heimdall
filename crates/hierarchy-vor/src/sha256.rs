//! Pure SHA-256 (FIPS 180-4), hand-written inside this crate.
//!
//! Why hand-written rather than a dependency: the workspace's dependency
//! posture (REQ-1) requires `[dependencies]` to stay empty, and the Rust
//! standard library carries no SHA-256. Adding a runtime dependency to the
//! hierarchy plane's attestation path for a fixed, 90-line, publicly
//! specified algorithm would be a trust-boundary decision needing its own
//! `DECISIONS.md` row (`.opencode/plans/vor-minimal-cohort-spec.md` section
//! 2.3).
//!
//! The honest caveat, stated here rather than smoothed over: this is a
//! hand-written hash implementation on an authorisation path. It is checked
//! against the published FIPS 180-4 / NIST known-answer vectors and against
//! every golden vector this crate replays (REQ-35), so "is this
//! implementation correct" is answerable by test rather than by trust. It is
//! **not** side-channel hardened: SHA-256 over a fixed-length record with a
//! fixed-length key has no secret-dependent control flow to leak, so there is
//! nothing here for a timing side channel to expose. The one timing-sensitive
//! operation on this authorisation path, comparing two hex digests, is
//! re-expressed separately as a constant-time comparison in `record.rs`
//! (REQ-4); this module never compares digests itself. If a future step
//! needs HMAC proper, a real KDF or asymmetric signatures, the dependency
//! question is reopened, with its own decision row.
//!
//! The only public item is [`digest_hex`] (REQ-3): pure, total, no global
//! mutable state, no panic on any input reachable through its signature, and
//! no allocation beyond the returned `String`.

/// SHA-256 initial hash value (FIPS 180-4 section 5.3.3).
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

/// SHA-256 round constants (FIPS 180-4 section 4.2.2): the first 32 bits of
/// the fractional parts of the cube roots of the first 64 primes.
const K: [u32; 64] = [
    0x428a_2f98,
    0x7137_4491,
    0xb5c0_fbcf,
    0xe9b5_dba5,
    0x3956_c25b,
    0x59f1_11f1,
    0x923f_82a4,
    0xab1c_5ed5,
    0xd807_aa98,
    0x1283_5b01,
    0x2431_85be,
    0x550c_7dc3,
    0x72be_5d74,
    0x80de_b1fe,
    0x9bdc_06a7,
    0xc19b_f174,
    0xe49b_69c1,
    0xefbe_4786,
    0x0fc1_9dc6,
    0x240c_a1cc,
    0x2de9_2c6f,
    0x4a74_84aa,
    0x5cb0_a9dc,
    0x76f9_88da,
    0x983e_5152,
    0xa831_c66d,
    0xb003_27c8,
    0xbf59_7fc7,
    0xc6e0_0bf3,
    0xd5a7_9147,
    0x06ca_6351,
    0x1429_2967,
    0x27b7_0a85,
    0x2e1b_2138,
    0x4d2c_6dfc,
    0x5338_0d13,
    0x650a_7354,
    0x766a_0abb,
    0x81c2_c92e,
    0x9272_2c85,
    0xa2bf_e8a1,
    0xa81a_664b,
    0xc24b_8b70,
    0xc76c_51a3,
    0xd192_e819,
    0xd699_0624,
    0xf40e_3585,
    0x106a_a070,
    0x19a4_c116,
    0x1e37_6c08,
    0x2748_774c,
    0x34b0_bcb5,
    0x391c_0cb3,
    0x4ed8_aa4a,
    0x5b9c_ca4f,
    0x682e_6ff3,
    0x748f_82ee,
    0x78a5_636f,
    0x84c8_7814,
    0x8cc7_0208,
    0x90be_fffa,
    0xa450_6ceb,
    0xbef9_a3f7,
    0xc671_78f2,
];

/// Processes exactly one 64-byte (512-bit) block, folding it into `state`
/// (FIPS 180-4 section 6.2.2).
fn process_block(state: &mut [u32; 8], block: &[u8; 64]) {
    let mut w = [0u32; 64];
    for i in 0..16 {
        w[i] = u32::from_be_bytes([
            block[i * 4],
            block[i * 4 + 1],
            block[i * 4 + 2],
            block[i * 4 + 3],
        ]);
    }
    for i in 16..64 {
        let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
        let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16]
            .wrapping_add(s0)
            .wrapping_add(w[i - 7])
            .wrapping_add(s1);
    }

    let mut a = state[0];
    let mut b = state[1];
    let mut c = state[2];
    let mut d = state[3];
    let mut e = state[4];
    let mut f = state[5];
    let mut g = state[6];
    let mut h = state[7];

    for i in 0..64 {
        let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
        let ch = (e & f) ^ ((!e) & g);
        let temp1 = h
            .wrapping_add(s1)
            .wrapping_add(ch)
            .wrapping_add(K[i])
            .wrapping_add(w[i]);
        let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
        let maj = (a & b) ^ (a & c) ^ (b & c);
        let temp2 = s0.wrapping_add(maj);

        h = g;
        g = f;
        f = e;
        e = d.wrapping_add(temp1);
        d = c;
        c = b;
        b = a;
        a = temp2.wrapping_add(temp1);
    }

    state[0] = state[0].wrapping_add(a);
    state[1] = state[1].wrapping_add(b);
    state[2] = state[2].wrapping_add(c);
    state[3] = state[3].wrapping_add(d);
    state[4] = state[4].wrapping_add(e);
    state[5] = state[5].wrapping_add(f);
    state[6] = state[6].wrapping_add(g);
    state[7] = state[7].wrapping_add(h);
}

/// Computes the SHA-256 digest of `input` and returns it as 64 lowercase hex
/// characters (REQ-3). The only public item in this module.
///
/// Pure and total: every input, including the empty slice, produces a
/// result. No global mutable state is read or written. The only heap
/// allocation is the returned `String`; the full-block loop reads directly
/// from `input` and the final, padded block (at most two 64-byte blocks) is
/// built on a fixed-size stack buffer rather than a heap-allocated copy of
/// the whole padded message.
pub fn digest_hex(input: &[u8]) -> String {
    let mut state = H0;

    let full_blocks = input.len() / 64;
    for i in 0..full_blocks {
        let start = i * 64;
        // A 64-byte slice always converts to a `&[u8; 64]` array reference;
        // the `unwrap` here can never fail because `start..start + 64` is in
        // bounds by construction of `full_blocks`.
        let block: &[u8; 64] = input[start..start + 64].try_into().unwrap();
        process_block(&mut state, block);
    }

    // The tail: FIPS 180-4's padding is a single 0x80 byte, zero bytes, and
    // an 8-byte big-endian bit length, appended after the unprocessed
    // remainder of the message. That remainder is at most 63 bytes, so the
    // padded tail never needs more than two 64-byte blocks: built here on a
    // fixed-size stack buffer, never on a heap-allocated copy of `input`.
    let remainder = &input[full_blocks * 64..];
    let rem_len = remainder.len();
    let bit_len = (input.len() as u64).wrapping_mul(8);

    let mut buf = [0u8; 128];
    buf[..rem_len].copy_from_slice(remainder);
    buf[rem_len] = 0x80;
    let total_len = if rem_len < 56 { 64 } else { 128 };
    buf[total_len - 8..total_len].copy_from_slice(&bit_len.to_be_bytes());

    for chunk_start in (0..total_len).step_by(64) {
        let block: &[u8; 64] = buf[chunk_start..chunk_start + 64].try_into().unwrap();
        process_block(&mut state, block);
    }

    let mut out = String::with_capacity(64);
    for word in state {
        // `core::fmt::Write` writes directly into `out`'s existing buffer
        // (pre-sized above to exactly 64 bytes), so this does not allocate a
        // separate temporary string the way `format!` followed by
        // `push_str` would.
        use core::fmt::Write as _;
        write!(out, "{word:08x}").expect("writing to a String never fails");
    }
    out
}
