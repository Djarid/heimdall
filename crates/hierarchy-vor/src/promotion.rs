// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The promotion-record substrate and its verification (section 3.4, REQ-17
//! to REQ-24; `.opencode/plans/rust-promotion-gate-spec.md` section 4.2's
//! `promotion.rs` illustrative signatures, section 4.3's canonical-field
//! schema).
//!
//! [`PromotionRecord`] is a **second** [`crate::record::AttestedRecord`] type
//! on the substrate `crate::record` already owns, alongside
//! [`crate::types::CohortDefinition`]. It carries exactly six content fields
//! plus the attested pair (`authoriser`, `attestation`): the assertion id
//! being promoted, a digest of that assertion's content, the trust level
//! being promoted to (`promoted_to`, carried as an **opaque string** -- never
//! ranked, parsed or ordered anywhere in this crate, exactly as
//! `crate::cohort::TRUST_CEILING` is not), and the validity-window bounds
//! (`valid_from`, `valid_until`). No fifth content field of any kind.
//!
//! **`RECORD_TYPE_PROMOTION` is byte-identical to
//! `ontology/nornir/authorisation_record.py`'s already-reserved
//! `RECORD_TYPE_PROMOTION` constant (REQ-18).** No new reservation is added to
//! that module, and no line of it changes: the tag is already reserved
//! there, this module just matches it. The record-type tag prefix
//! `crate::record::canonical_record_bytes` builds in means an attestation
//! computed for a [`PromotionRecord`] cannot verify when presented as a
//! `CohortDefinition`, and vice versa, even under the same authoriser and the
//! same secret (REQ-19).
//!
//! **[`load_verified_promotion`] is the crate's one new public door
//! (REQ-21).** It is the only way, in this crate or outside it, to obtain a
//! [`VerifiedPromotion`]: the witness's only constructor
//! ([`VerifiedPromotion::new`]) is `pub(crate)` and is called from exactly
//! one site, immediately after [`crate::verify::verify_record`] returns
//! `Ok(())`. On any refusal the return is `Err(PromotionRefusal)`, never a
//! degraded, narrowed or partially-verified promotion: there is no
//! fail-closed substitute value to hand back.
//!
//! **The validity window is checked against a caller-supplied instant, never
//! a wall-clock source this module reads itself (REQ-22).** `now` is a plain
//! `u64` parameter with no default and no `Option`; this module reads no
//! wall-clock source of any kind, and imports no clock-reading facility from
//! anywhere in its dependency graph. Boundaries are inclusive on both ends:
//! `now == valid_from` and `now == valid_until` both verify.
//!
//! **REQ-24: a genuine runtime refusal path, not a compile-time assertion.**
//! Unlike `crate::cohort`'s hardcoded, compile-time-constant field values
//! (checked by `const _: () = assert!(...)`), a promotion record's field
//! values are runtime data supplied by a caller, so every field value that
//! enters the record's canonical encoding is checked, at call time, for the
//! three characters the comma-join encoding treats specially (a comma, a
//! newline, or an `=`), **before** any attestation is computed or any
//! verification is attempted. A record carrying any of them is refused with
//! [`PromotionRefusal::ContentIntegrity`] rather than attested or verified.
//!
//! **Check ordering, stated explicitly so a reviewer can verify it directly
//! against the source below.** [`load_verified_promotion`] checks, in order:
//! (1) field content integrity (REQ-24); (2) the window is well-formed,
//! `valid_until >= valid_from` (else [`PromotionRefusal::MalformedWindow`]),
//! checked before any digest computation; (3) the four-case fail-closed
//! verification procedure of [`crate::verify::verify_record`], reused exactly
//! as it already exists, unwidened and unmodified; and only then (4) the
//! caller-supplied instant falls within the record's own attested validity
//! window (else [`PromotionRefusal::OutsideValidityWindow`]).
//!
//! **REQ-20: the secret boundary is not weakened.** This module names no
//! secret-carrying type in any public function signature and exposes no
//! secret, digest preimage, or [`crate::authoriser::TrustedAuthoriserSet`]'s
//! inner map from any public item. `trusted: &TrustedAuthoriserSet` is read
//! only through [`crate::verify::verify_record`], which already exists and is
//! reused unmodified.

use crate::authoriser::TrustedAuthoriserSet;
use crate::record::AttestedRecord;
use crate::verify::{RecordRefusal, verify_record};

/// This crate's own promotion record-type tag (REQ-18): must equal the Python
/// constant `RECORD_TYPE_PROMOTION` (`ontology/nornir/authorisation_record.py`)
/// exactly, character for character, so a promotion attestation computed on
/// either side of the substrate verifies identically on the other.
pub(crate) const RECORD_TYPE_PROMOTION: &str = "promotion_record";

/// The promotion record's shape (REQ-17): exactly six content fields
/// (`assertion_id`, `content_digest`, `promoted_to`, `valid_from`,
/// `valid_until`, `authoriser`) plus `attestation`, mirroring
/// `CohortDefinition`'s own shape and adding nothing. `pub(crate)`, not
/// `pub`: nothing outside this crate constructs a `PromotionRecord` directly.
/// A downstream caller obtains a promotion only through
/// [`load_verified_promotion`]'s [`VerifiedPromotion`] witness and its
/// read-only accessors, never through this struct.
#[derive(Debug)]
pub(crate) struct PromotionRecord {
    pub(crate) assertion_id: String,
    pub(crate) content_digest: String,
    /// The trust level being promoted to, carried as an **opaque string**
    /// (REQ-17). Never ranked, parsed, split or compared for ordering
    /// anywhere in this crate: the caller ranks it, not Vör.
    pub(crate) promoted_to: String,
    pub(crate) valid_from: u64,
    pub(crate) valid_until: u64,
    pub(crate) authoriser: Option<String>,
    pub(crate) attestation: Option<String>,
}

impl AttestedRecord for PromotionRecord {
    fn record_type(&self) -> &'static str {
        RECORD_TYPE_PROMOTION
    }

    /// The attested content, in the fixed order of spec section 4.3's table:
    /// `assertion_id`, `content_digest`, `promoted_to`, `valid_from`,
    /// `valid_until`, `authoriser`. `attestation` is deliberately absent: it
    /// is the digest being computed or checked, not part of what it covers,
    /// exactly as `CohortDefinition::canonical_fields` excludes it.
    ///
    /// `valid_from` and `valid_until` are encoded as plain decimal, no
    /// separators, so the window is attested and cannot be edited after
    /// attestation. `authoriser` is encoded as the empty string when absent,
    /// exactly as `CohortDefinition::canonical_fields` does with
    /// `self.authoriser or ""`.
    fn canonical_fields(&self) -> Vec<(&'static str, String)> {
        vec![
            ("assertion_id", self.assertion_id.clone()),
            ("content_digest", self.content_digest.clone()),
            ("promoted_to", self.promoted_to.clone()),
            ("valid_from", self.valid_from.to_string()),
            ("valid_until", self.valid_until.to_string()),
            ("authoriser", self.authoriser.clone().unwrap_or_default()),
        ]
    }
}

/// The closed set of ways [`load_verified_promotion`] can refuse (REQ-21).
#[derive(Debug)]
pub enum PromotionRefusal {
    /// The record's attestation did not verify (wraps
    /// [`crate::verify::RecordRefusal`]'s own three refusal branches).
    Verification(RecordRefusal),
    /// A field value contains a comma, a newline or an `=` (REQ-24). Checked
    /// **before** any attestation is computed or verification is attempted.
    /// A genuine runtime path, reachable and tested, because a promotion
    /// record's values are runtime data, not compile-time constants.
    ContentIntegrity(String),
    /// The caller-supplied instant of REQ-22 falls outside the record's own
    /// attested `[valid_from, valid_until]` window (inclusive on both
    /// boundaries).
    OutsideValidityWindow(String),
    /// `valid_until < valid_from`: a malformed window, checked before any
    /// digest computation.
    MalformedWindow(String),
}

/// A verified handle over a promotion record. Opaque (REQ-23): every field is
/// private, its only constructor ([`VerifiedPromotion::new`]) is
/// `pub(crate)` and is called from exactly one site (immediately below, in
/// [`load_verified_promotion`], right after [`verify_record`] returns
/// `Ok(())`), and it implements no public `From`, `TryFrom` or `Deref` to the
/// underlying [`PromotionRecord`]. It derives no `Clone`, `Copy` or
/// `Default`, and contains no interior mutability: its one field is a plain,
/// owned [`PromotionRecord`], and every method below takes `&self`, never
/// `&mut self`. The only value of this type any code outside this module can
/// ever hold is one [`load_verified_promotion`] built after a successful
/// verification.
///
/// See the derive note below for why `Debug` alone is added on top of this.
///
/// Derives `Debug` only (needed so `Result<VerifiedPromotion,
/// PromotionRefusal>` can be rendered by a caller's `{:?}` without a manual
/// impl; REQ-23 forbids `Clone`, `Copy`, `Default` and interior mutability,
/// not `Debug`). The derived `Debug` output prints the field names this
/// struct declares below, never a secret: `PromotionRecord` itself carries
/// no secret byte, only the attested content and the (non-secret)
/// authoriser id and attestation digest.
#[derive(Debug)]
pub struct VerifiedPromotion {
    record: PromotionRecord,
}

impl VerifiedPromotion {
    /// Builds a verified handle from an already-verified `record`.
    /// `pub(crate)`, not `pub` (REQ-23): the only caller is
    /// [`load_verified_promotion`] below, immediately after
    /// [`verify_record`] returns `Ok(())`. No code outside this crate, and
    /// no code inside it other than this module, can construct a
    /// `VerifiedPromotion` for itself.
    pub(crate) fn new(record: PromotionRecord) -> Self {
        VerifiedPromotion { record }
    }

    /// The exact assertion id this promotion binds.
    pub fn assertion_id(&self) -> &str {
        &self.record.assertion_id
    }

    /// The exact content digest this promotion binds.
    pub fn content_digest(&self) -> &str {
        &self.record.content_digest
    }

    /// The trust level this promotion promotes to, as the opaque string it
    /// was attested with (REQ-17): never ranked, parsed or ordered here. A
    /// caller wanting rank comparison (`crates/boundary-gjoll/`) reads this
    /// string and ranks it on its own side.
    pub fn promoted_to(&self) -> &str {
        &self.record.promoted_to
    }
}

/// Returns `true` when `s` contains none of the three characters the
/// comma-join encoding treats specially (REQ-24): a comma, a newline, or an
/// `=`. A plain runtime `fn`, not a `const fn` (unlike `crate::cohort`'s
/// equivalent): a promotion record's field values are runtime data, so this
/// check must be a genuine runtime refusal path, reachable and tested, not a
/// compile-time assertion over a fixed set of hardcoded constants.
fn field_is_clean(s: &str) -> bool {
    !s.contains(',') && !s.contains('\n') && !s.contains('=')
}

/// The crate's one new public entry point for promotion verification
/// (REQ-21). `trusted` is a **plain reference**, never an `Option` and never
/// defaulted; `now` is a **plain, caller-supplied instant** (REQ-22), never a
/// clock this function reads itself. Verifies through the existing
/// [`verify_record`] four-case fail-closed procedure, reused exactly as it
/// stands, and returns either an opaque [`VerifiedPromotion`] or a typed
/// [`PromotionRefusal`] -- never a degraded, narrowed or partially-verified
/// promotion.
///
/// Check ordering (see this module's own doc comment for the full
/// rationale): field content integrity first (REQ-24); then the window's own
/// well-formedness, before any digest computation; then verification; then
/// the validity window against `now`, boundaries inclusive on both ends.
#[allow(clippy::too_many_arguments)]
pub fn load_verified_promotion(
    assertion_id: &str,
    content_digest: &str,
    promoted_to: &str,
    valid_from: u64,
    valid_until: u64,
    authoriser: &str,
    attestation: &str,
    trusted: &TrustedAuthoriserSet,
    now: u64,
) -> Result<VerifiedPromotion, PromotionRefusal> {
    // REQ-24: a genuine runtime check over every field value that enters the
    // canonical encoding, before any attestation is computed or any
    // verification is attempted.
    let content_clean = field_is_clean(assertion_id)
        && field_is_clean(content_digest)
        && field_is_clean(promoted_to)
        && field_is_clean(authoriser);
    if !content_clean {
        return Err(PromotionRefusal::ContentIntegrity(
            "a promotion record field value contains a comma, a newline or an '=' \
             character, which would make the comma-join encoding ambiguous (REQ-24); \
             refusing rather than attesting or verifying an ambiguous record"
                .to_string(),
        ));
    }

    // REQ-22: the window's own well-formedness, checked before any digest
    // computation, so a malformed window wins over a wrong-secret digest
    // mismatch too.
    if valid_until < valid_from {
        return Err(PromotionRefusal::MalformedWindow(format!(
            "valid_until ({valid_until}) is less than valid_from ({valid_from}); a \
             malformed validity window is refused before any digest computation"
        )));
    }

    let record = PromotionRecord {
        assertion_id: assertion_id.to_string(),
        content_digest: content_digest.to_string(),
        promoted_to: promoted_to.to_string(),
        valid_from,
        valid_until,
        authoriser: Some(authoriser.to_string()),
        attestation: Some(attestation.to_string()),
    };

    verify_record(
        &record,
        record.authoriser.as_deref(),
        record.attestation.as_deref(),
        trusted,
    )
    .map_err(PromotionRefusal::Verification)?;

    // REQ-22: the caller-supplied instant, checked against the record's own
    // attested window, boundaries inclusive on both ends.
    if now < record.valid_from || now > record.valid_until {
        return Err(PromotionRefusal::OutsideValidityWindow(format!(
            "now ({now}) falls outside the inclusive validity window [{}, {}]",
            record.valid_from, record.valid_until
        )));
    }

    Ok(VerifiedPromotion::new(record))
}
