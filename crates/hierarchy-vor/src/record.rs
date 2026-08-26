//! The shared attested-record substrate, re-expressed in Rust (D103's own
//! mechanism, `ontology/nornir/authorisation_record.py`).
//!
//! This module knows no concrete record type. It reads a record through
//! exactly two methods, [`AttestedRecord::record_type`] and
//! [`AttestedRecord::canonical_fields`], and depends on nothing else about
//! the record's shape, so the dependency points one way exactly as the
//! Python docstring (lines 12 to 15) requires: records depend on this module
//! to be attested and verified; this module depends on no record. It must
//! not name, import or match on `CohortDefinition` (REQ-7); `crate::types`
//! is not referenced anywhere below.
//!
//! Every item here is `pub(crate)`, never `pub`: REQ-13 forbids any public
//! function that takes secret bytes, and [`compute_record_attestation`] is
//! exactly such a function. Keeping the whole module `pub(crate)` means the
//! in-crate unit tests wired from `lib.rs` (REQ-38) can reach it directly by
//! path, while `tests/public_surface.rs`, compiled as an external crate, can
//! reach none of it, which is the intended shape (section 4.1).
//!
//! Byte-level fidelity with the Python substrate (REQ-8). [`RECORD_DOMAIN`]
//! is byte-identical to `_RECORD_DOMAIN`, and [`canonical_record_bytes`]
//! builds exactly the same layout `canonical_record_bytes` (Python, lines
//! 123 to 147) does: the domain separator, a single `0x00` byte, then a
//! newline-joined body whose first line is `record_type=<tag>` and whose
//! remaining lines are the record's own fields, in the order the record
//! returned them, encoded UTF-8. The record-type tag prefix means an
//! attestation computed for one record type cannot verify when presented as
//! another, in either direction (REQ-8's own cross-type requirement).
//!
//! The comma-join encoding [`AttestedRecord`] implementations are expected to
//! use for collection fields (REQ-9) is not injective (REQ-10): a member
//! containing a comma, a newline or an `=` produces canonical bytes another
//! field set could also produce. This is inherited from the Python substrate
//! verbatim and is deliberately not fixed here, because changing the
//! encoding would break every existing `AgentContext` attestation. This
//! module does not (and cannot, being record-agnostic) enforce the mechanical
//! check that the hardcoded cohort's own field values avoid these three
//! characters; that check belongs to the record type itself or to its own
//! tests (REQ-10's second half).

/// This crate's own record-type tag (REQ-40 parity): must equal the Python
/// constant `RECORD_TYPE_COHORT_DEFINITION`
/// (`ontology/nornir/authorisation_record.py`) exactly, character for
/// character, so a cohort attestation computed on either side of the
/// substrate verifies identically on the other.
pub(crate) const RECORD_TYPE_COHORT_DEFINITION: &str = "cohort_definition";

/// The substrate's own domain separator (REQ-8): byte-identical to Python's
/// `_RECORD_DOMAIN`. Distinct from `sink_attestation.compute_attestation`'s
/// own domain separator (its `b"\x00"` byte between content and key), so an
/// attestation computed under this substrate cannot verify as a
/// `SinkDeclaration` attestation, or vice versa, even under the same
/// authoriser and the same secret (REQ-12's cross-substrate separation).
pub(crate) const RECORD_DOMAIN: &[u8] = b"heimdall.authorisation_record.v1";

/// The Rust form of the Python substrate's two-method record interface
/// (REQ-7). Exactly two required methods, and nothing else: this trait must
/// never grow a third method or a default implementation that reaches into a
/// concrete record type, or the "this module knows no concrete record type"
/// property this file's own module doc states would stop being true.
pub(crate) trait AttestedRecord {
    /// The record-type tag prefixed into the record's canonical bytes
    /// (REQ-8). The Rust form of Python's `record_type() -> str`.
    fn record_type(&self) -> &'static str;

    /// The record's own attested content, as a fixed-order sequence of
    /// (name, value) pairs. The Rust form of Python's `canonical_fields() ->
    /// tuple[tuple[str, str], ...]`. A record implementing this trait is
    /// responsible for sorting any collection it encodes into a value string
    /// itself (REQ-9): this trait's contract does not require the caller to
    /// sort anything, only to read the pairs back in the order returned.
    fn canonical_fields(&self) -> Vec<(&'static str, String)>;
}

/// Deterministic encoding of a record's attested content, prefixed with its
/// record-type tag (REQ-8, REQ-9), byte-identical to Python's
/// `canonical_record_bytes`. Reads only `record.record_type()` and
/// `record.canonical_fields()`: this function need not know a record's
/// internal shape beyond that narrow interface, and it mutates nothing, only
/// reads.
pub(crate) fn canonical_record_bytes<R: AttestedRecord>(record: &R) -> Vec<u8> {
    let mut lines = Vec::with_capacity(1 + 4);
    lines.push(format!("record_type={}", record.record_type()));
    for (name, value) in record.canonical_fields() {
        lines.push(format!("{name}={value}"));
    }
    let body = lines.join("\n").into_bytes();

    let mut out = Vec::with_capacity(RECORD_DOMAIN.len() + 1 + body.len());
    out.extend_from_slice(RECORD_DOMAIN);
    out.push(0x00);
    out.extend_from_slice(&body);
    out
}

/// Computes the keyed digest for a record under a trusted secret
/// (REQ-11), byte-identical to Python's `compute_record_attestation`: the
/// lowercase hex SHA-256 of the canonical bytes, then a single `0x00` domain
/// separator byte, then the secret bytes.
///
/// `pub(crate)` only (REQ-13): this function takes secret bytes directly, so
/// it must never be reachable from outside the crate. The in-crate unit
/// tests use it to build attested fixtures; `crate::verify::verify_record`
/// (a later issue) recomputes it to check one.
pub(crate) fn compute_record_attestation<R: AttestedRecord>(record: &R, secret: &[u8]) -> String {
    let mut preimage = canonical_record_bytes(record);
    preimage.push(0x00); // domain separator between content and key
    preimage.extend_from_slice(secret);
    crate::sha256::digest_hex(&preimage)
}

/// The crate's only digest comparison (REQ-4): compares two hex digests
/// without an early exit on the first differing byte, so the comparison does
/// not leak how many leading characters matched via timing. Lengths are
/// compared first (a length mismatch cannot be an equal digest, and doing so
/// lets the accumulating loop below assume equal length); the accumulating
/// comparison itself never returns early once the lengths match, exactly as
/// Python's `_constant_time_equals` (`ontology/nornir/sink_attestation.py`,
/// lines 176 to 185) does.
pub(crate) fn constant_time_equals(a: &str, b: &str) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut result: u8 = 0;
    for (x, y) in a.bytes().zip(b.bytes()) {
        result |= x ^ y;
    }
    result == 0
}
