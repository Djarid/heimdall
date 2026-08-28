//! The one hardcoded cohort, its committed attestation constant and the
//! crate's single mandatory entry point (section 3.4, REQ-20 to REQ-27;
//! section 4.1's `cohort.rs` table). This is the module `crate::types` itself
//! defers to (its own doc comment: "`crate::cohort` (a later issue) owns the
//! actual `heimdall-dev` VALUES"): every content value the `heimdall-dev`
//! cohort carries is a compile-time constant declared below, and nowhere
//! else in this crate.
//!
//! **`load_verified_cohort` is the crate's only door (REQ-23).** There is no
//! other way for a caller, in this crate or outside it, to obtain a
//! [`VerifiedCohort`]: its constructor is `pub(crate)`
//! ([`VerifiedCohort::new`]), so the only value that can ever exist outside
//! this module is one this module itself built, after [`verify::verify_record`]
//! returned `Ok(())` against the loaded [`authoriser::TrustedAuthoriserSet`].
//! On any refusal the return is `Err(CohortRefusal)`, never a narrowed,
//! hollowed or otherwise degraded cohort: there is no fail-closed substitute
//! value to hand back, because hollowing `consequential_sinks` on the way out
//! is exactly the disarming direction REQ-23 forbids.
//!
//! **`trust_ceiling` stays opaque here too (REQ-21).** [`TRUST_CEILING`] is a
//! plain `&'static str`. Nothing in this module, or anywhere else in this
//! crate, ranks it, parses it, or compares it for ordering; the const-time
//! checks below only ever test it for a forbidden *character*, never for its
//! *position* on any scale.

use crate::authoriser::TrustedAuthoriserSet;
use crate::types::{CohortDefinition, CohortSurface};
use crate::verify::{RecordRefusal, verify_record};

/// The hardcoded cohort's own id (REQ-20). Equal to the `cohort_id` field of
/// every replayed vector whose `cohort_id` is the real cohort's (V-1 in
/// `vectors/cohort_vectors.json`).
pub const COHORT_ID: &str = "heimdall-dev";

/// The hardcoded cohort's permitted actions (REQ-20), exactly two: the
/// `action:<name>` convention (`action.py` lines 30 to 54) with a dotted
/// second segment (`spec.md` section 2.1 question two). Deliberately not
/// registered in `ontology/yggdrasil/spine/action.py`: see that section for
/// the three reasons this vocabulary stays out of Phase 1's loaded ontology.
pub const PERMITTED_ACTIONS: &[&str] = &["action:git.commit", "action:git.push"];

/// The hardcoded cohort's trust ceiling (REQ-20): the literal string
/// `"TAINTED"`, handled as an **opaque string** everywhere in this crate
/// (REQ-21). Never ranked, parsed, or compared for ordering; see this
/// module's own doc comment and the const-time check block below, which
/// checks it only for a forbidden *character*, never for a position on any
/// lattice.
pub const TRUST_CEILING: &str = "TAINTED";

/// The hardcoded cohort's consequential sinks (REQ-20), exactly two, the
/// `sink:<name>` convention (`harness.py` line 641). REQ-26: this set is
/// **not** routed into `consequentiality::evaluate` anywhere in this crate;
/// step three (a later issue) reads it from [`CohortSurface::consequential_sinks`]
/// for its own `action_critical` determination, and the gate's own sink
/// registry remains a separate, later input.
pub const CONSEQUENTIAL_SINKS: &[&str] = &["sink:git.commit", "sink:git.push"];

/// The authoriser id the hardcoded cohort's attestation names (REQ-20). This
/// is the id [`load_verified_cohort`]'s caller must have loaded a secret for,
/// in the [`TrustedAuthoriserSet`] it passes in.
pub const AUTHORISER_ID: &str = "heimdall-dev-authoriser";

/// The `heimdall-dev` cohort's committed attestation constant (REQ-20,
/// REQ-22): the keyed digest of the six fields above (`attestation` itself
/// excluded, exactly as [`crate::types::CohortDefinition::canonical_fields`]
/// excludes it), computed **out of band**, under the real secret, and pasted
/// in here. It is never computed at startup from the same bytes it checks
/// (REQ-22): [`load_verified_cohort`] recomputes a digest over this module's
/// hardcoded content plus whatever secret [`TrustedAuthoriserSet`] loaded,
/// and compares that against this constant, so a source edit to the
/// cohort's own content cannot re-attest itself.
///
/// **Provenance, stated plainly, not softened.** This value was produced by
/// `export_cohort_vectors.py`'s authoring mode (REQ-31) under a
/// development-time placeholder secret, not a real, separately-provisioned
/// production secret. It must be replaced once a real secret is provisioned.
/// Until that replacement happens, any deployment relying on this constant
/// is relying on a development-time value, and that fact must not be
/// smoothed over in any report that quotes this constant.
pub const COMMITTED_ATTESTATION: &str =
    "8002847c14111adc70e1d707e5cf38a68b05663cff9b5ecab5a0e296046b9214";

/// Returns `true` when `s` contains none of the three characters the
/// comma-join encoding treats specially (REQ-10): a comma, a newline, or an
/// `=`. `const fn` so every hardcoded field value below is checked for this
/// at **compile time** (see the `const _: () = ...;` block further down),
/// not merely at test time, following REQ-42 item 5's spirit -- the full
/// surface-check harness that scans arbitrary future edits is issue #33's
/// job; this is the mechanical check this module can carry on its own fixed
/// set of constants.
const fn field_is_clean(s: &str) -> bool {
    let bytes = s.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        let b = bytes[i];
        if b == b',' || b == b'\n' || b == b'=' {
            return false;
        }
        i += 1;
    }
    true
}

/// [`field_is_clean`], applied to every member of a `const` slice of field
/// values (for [`PERMITTED_ACTIONS`] and [`CONSEQUENTIAL_SINKS`]).
const fn all_fields_clean(values: &[&str]) -> bool {
    let mut i = 0;
    while i < values.len() {
        if !field_is_clean(values[i]) {
            return false;
        }
        i += 1;
    }
    true
}

// Compile-time assertions (REQ-10, REQ-42 item 5): a future edit that
// introduces a comma, a newline or an `=` into any hardcoded field value
// above fails the BUILD, not merely a later test run. These are expected to
// stay permanently true and inert, because the constants above are clean;
// they exist to catch drift the moment it is introduced, not because the
// current values are suspected of violating the rule.
const _: () = assert!(
    field_is_clean(COHORT_ID),
    "COHORT_ID contains a comma, newline or '=' (REQ-10)"
);
const _: () = assert!(
    field_is_clean(TRUST_CEILING),
    "TRUST_CEILING contains a comma, newline or '=' (REQ-10)"
);
const _: () = assert!(
    field_is_clean(AUTHORISER_ID),
    "AUTHORISER_ID contains a comma, newline or '=' (REQ-10)"
);
const _: () = assert!(
    all_fields_clean(PERMITTED_ACTIONS),
    "a PERMITTED_ACTIONS member contains a comma, newline or '=' (REQ-10)"
);
const _: () = assert!(
    all_fields_clean(CONSEQUENTIAL_SINKS),
    "a CONSEQUENTIAL_SINKS member contains a comma, newline or '=' (REQ-10)"
);

/// The closed set of ways [`load_verified_cohort`] can refuse (REQ-23,
/// REQ-27). [`CohortRefusal::Verification`] carries the four-case fail-closed
/// decision [`verify::verify_record`] returned (REQ-27; only three of the
/// four are reachable here, since the fourth is `Ok(())` and never becomes a
/// refusal at all). [`CohortRefusal::ContentIntegrity`] exists for REQ-10's
/// field-content rule: structurally required by section 4.1's `cohort.rs`
/// table, but never actually reachable through this module's own hardcoded
/// constants, because the `const _: () = assert!(...)` block above already
/// fails the build on the same condition long before this code could run. It
/// is retained as a runtime defence in depth and as the documented shape a
/// future, less-constant cohort source would need.
#[derive(Debug)]
pub enum CohortRefusal {
    /// The record's attestation did not verify (wraps
    /// [`verify::RecordRefusal`]'s own three refusal branches).
    Verification(RecordRefusal),
    /// A hardcoded field value contains a comma, a newline or an `=`
    /// (REQ-10). Never observed in practice against this module's own
    /// constants; see this enum's own doc comment.
    ContentIntegrity(String),
}

/// A verified handle over the `heimdall-dev` cohort. Opaque (REQ-24): its one
/// field is private, its only constructor ([`VerifiedCohort::new`]) is
/// `pub(crate)`, and it implements no public `From`, `TryFrom` or `Deref` to
/// the underlying [`CohortDefinition`]. It derives no `Clone`, `Copy` or
/// `Default`, and contains no interior mutability (no cell, no lock, no
/// atomic): its one field is a plain, owned [`CohortDefinition`], and every
/// method below takes `&self`, never `&mut self`. The only value of this
/// type any code outside this module can ever hold is one
/// [`load_verified_cohort`] built after a successful verification.
pub struct VerifiedCohort {
    definition: CohortDefinition,
}

impl VerifiedCohort {
    /// Builds a verified handle from an already-verified `definition`.
    /// `pub(crate)`, not `pub` (REQ-24): the only caller is
    /// [`load_verified_cohort`] below, immediately after
    /// [`verify::verify_record`] returns `Ok(())`. No code outside this
    /// crate, and no code inside it other than this module, can construct a
    /// `VerifiedCohort` for itself.
    pub(crate) fn new(definition: CohortDefinition) -> Self {
        VerifiedCohort { definition }
    }

    /// The handle's only read surface (REQ-25): a borrowed, read-only
    /// projection of the verified cohort's control surface, delegating
    /// entirely to [`crate::types::CohortSurface`]. No setter, no owned
    /// copy of the handle, and no mutable borrow anywhere on this path.
    pub fn surface(&self) -> CohortSurface<'_> {
        CohortSurface::new(&self.definition)
    }
}

/// The crate's single entry point (REQ-23): the only way a caller, in this
/// crate or outside it, obtains the `heimdall-dev` cohort. `trusted` is a
/// **plain reference**, never an `Option` and never defaulted, so there is no
/// unverified path through this function to design out later. Builds a
/// [`CohortDefinition`] from this module's own hardcoded constants (with
/// `authoriser` and `attestation` populated), verifies it against `trusted`
/// via [`verify::verify_record`], and returns either a [`VerifiedCohort`] or
/// a typed [`CohortRefusal`] -- never a degraded, narrowed or empty cohort on
/// the refusal side.
pub fn load_verified_cohort(
    trusted: &TrustedAuthoriserSet,
) -> Result<VerifiedCohort, CohortRefusal> {
    // Defence in depth for REQ-10 (see `CohortRefusal`'s own doc comment):
    // the `const _: () = assert!(...)` block above already makes this
    // unreachable for this module's own constants, by failing the build
    // itself on the same condition.
    let content_clean = field_is_clean(COHORT_ID)
        && field_is_clean(TRUST_CEILING)
        && field_is_clean(AUTHORISER_ID)
        && all_fields_clean(PERMITTED_ACTIONS)
        && all_fields_clean(CONSEQUENTIAL_SINKS);
    if !content_clean {
        return Err(CohortRefusal::ContentIntegrity(
            "a hardcoded cohort field value contains a comma, a newline or an '=' \
             character, which would make the comma-join encoding ambiguous (REQ-10); \
             refusing rather than attesting an ambiguous record"
                .to_string(),
        ));
    }

    let record = CohortDefinition {
        cohort_id: COHORT_ID.to_string(),
        permitted_actions: PERMITTED_ACTIONS.iter().map(|s| s.to_string()).collect(),
        trust_ceiling: TRUST_CEILING.to_string(),
        consequential_sinks: CONSEQUENTIAL_SINKS.iter().map(|s| s.to_string()).collect(),
        authoriser: Some(AUTHORISER_ID.to_string()),
        attestation: Some(COMMITTED_ATTESTATION.to_string()),
    };

    verify_record(
        &record,
        record.authoriser.as_deref(),
        record.attestation.as_deref(),
        trusted,
    )
    .map_err(CohortRefusal::Verification)?;

    Ok(VerifiedCohort::new(record))
}
