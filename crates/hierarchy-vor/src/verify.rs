//! The fail-closed decision procedure (section 3.4's REQ-27), the Rust form of
//! `authorisation_record.verify_record_attestation` (lines 176 to 232). This
//! module is generic over [`crate::record::AttestedRecord`] and knows no
//! concrete record type, exactly as `crate::record` itself does not.
//!
//! **The four cases, mirrored exactly (REQ-27).** `verify_record_attestation`
//! has four branches: no authoriser or no attestation (refused); an authoriser
//! absent from the trusted set (refused); a digest that does not match
//! (refused); and only then, verified. [`verify_record`] below reproduces
//! these four branches in the same order, with [`RecordRefusal`] carrying
//! exactly the first three as its closed set of variants. There is no fifth
//! outcome and no warning path: the return type is `Result<(), RecordRefusal>`,
//! so the success side carries nothing to narrow or hollow.
//!
//! **Every digest comparison routes through `crate::record::constant_time_equals`
//! (REQ-4).** This module contains no `==` comparison of two attestation
//! strings anywhere; the one comparison in [`verify_record`] below calls the
//! crate's single comparison function.
//!
//! **REQ-18: no refusal reason here ever carries a secret.** Every
//! [`RecordRefusal`] reason names only the record type and, where relevant,
//! the authoriser id supplied on the record -- never a secret byte, and never
//! the raw digest bytes of a failed comparison (only the fact that it failed).

use crate::authoriser::TrustedAuthoriserSet;
use crate::record::{AttestedRecord, compute_record_attestation, constant_time_equals};

/// The three refusal reasons [`verify_record`] can return, mirroring
/// `verify_record_attestation`'s three refusal branches exactly (REQ-27).
/// Closed: no fourth refusal variant. The fourth, success, outcome is
/// `Ok(())`, never a variant of this enum.
#[derive(Debug)]
pub enum RecordRefusal {
    /// No authoriser, no attestation, or both absent from the record. An
    /// unattested record is not trusted; silence never earns trust.
    Unattested(String),
    /// The record names an authoriser that is not in the trusted set: an
    /// unknown or forged authoriser has no trusted secret to verify against.
    UnknownAuthoriser(String),
    /// The recomputed digest does not match the record's own attestation: the
    /// record was altered after attestation, or attested under the wrong key
    /// (the config-tamper case).
    DigestMismatch(String),
}

/// Verifies `record`'s provenance against `trusted`, fail closed on exactly
/// the four cases `verify_record_attestation` states (REQ-27). `authoriser`
/// and `attestation` are read from the record's own carried fields by the
/// caller (mirroring the Python's `getattr(record, "authoriser", None)` and
/// `getattr(record, "attestation", None)`), rather than this function reaching
/// into a concrete record type it does not know about.
///
/// Every digest comparison delegates to [`crate::record::constant_time_equals`]
/// (REQ-4); this function performs no raw `==` comparison of two attestation
/// strings.
pub(crate) fn verify_record<R: AttestedRecord>(
    record: &R,
    authoriser: Option<&str>,
    attestation: Option<&str>,
    trusted: &TrustedAuthoriserSet,
) -> Result<(), RecordRefusal> {
    let record_type = record.record_type();

    let (authoriser, attestation) = match (authoriser, attestation) {
        (Some(a), Some(d)) if !a.is_empty() && !d.is_empty() => (a, d),
        _ => {
            return Err(RecordRefusal::Unattested(format!(
                "{record_type} record carries no verifiable attestation (authoriser or \
                 digest absent); an unattested record is refused (fail closed, D103, \
                 extending D94 direction C)"
            )));
        }
    };

    let secret = match trusted.secret_for(authoriser) {
        Some(secret) => secret,
        None => {
            return Err(RecordRefusal::UnknownAuthoriser(format!(
                "{record_type} record names authoriser {authoriser:?}, which is not in \
                 the trusted authoriser set; an unknown or forged authoriser is refused \
                 (fail closed, D103, extending D94 direction C)"
            )));
        }
    };

    let expected = compute_record_attestation(record, secret);
    if !constant_time_equals(&expected, attestation) {
        return Err(RecordRefusal::DigestMismatch(format!(
            "{record_type} record attestation does not verify against authoriser \
             {authoriser:?}; the record was altered after attestation or attested under \
             the wrong key (config-tamper, refused fail closed, D103, extending D94 \
             direction C)"
        )));
    }

    Ok(())
}
