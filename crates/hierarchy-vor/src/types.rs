//! The cohort's value shapes, no logic (section 4.1's own description of this
//! module). [`CohortDefinition`] carries the mandatory cohort's content, one
//! record type built on `crate::record`'s substrate; [`CohortSurface`] is the
//! borrowed, read-only projection a verified handle hands back (REQ-25).
//!
//! `crate::cohort` (a later issue) owns the actual `heimdall-dev` VALUES
//! (`COHORT_ID`, `PERMITTED_ACTIONS`, `TRUST_CEILING`, `CONSEQUENTIAL_SINKS`,
//! `AUTHORISER_ID`) and the committed attestation constant; this module only
//! defines the shapes those values are carried in.

use crate::record::{AttestedRecord, RECORD_TYPE_COHORT_DEFINITION};

/// The hardcoded cohort's record shape (REQ-20): exactly four content fields
/// (`cohort_id`, `permitted_actions`, `trust_ceiling`, `consequential_sinks`)
/// plus the attested pair (`authoriser`, `attestation`), mirroring Python's
/// `AgentContext` field for field and adding nothing. There is no
/// `permitted_targets` field, no protected-branch list and no fifth content
/// field of any kind.
///
/// `pub(crate)`, not `pub`: nothing outside this crate constructs a
/// `CohortDefinition` directly. A downstream caller (step three) reaches the
/// cohort only through `crate::cohort::load_verified_cohort`'s
/// `VerifiedCohort` and its read-only [`CohortSurface`] projection, never
/// through this struct.
pub(crate) struct CohortDefinition {
    pub(crate) cohort_id: String,
    pub(crate) permitted_actions: Vec<String>,
    pub(crate) trust_ceiling: String,
    pub(crate) consequential_sinks: Vec<String>,
    pub(crate) authoriser: Option<String>,
    pub(crate) attestation: Option<String>,
}

impl AttestedRecord for CohortDefinition {
    fn record_type(&self) -> &'static str {
        RECORD_TYPE_COHORT_DEFINITION
    }

    /// The attested content: `cohort_id`, `permitted_actions` (sorted),
    /// `trust_ceiling`, `consequential_sinks` (sorted) and `authoriser`.
    /// `attestation` is deliberately absent: it is the digest being computed
    /// or checked, not part of what it covers, exactly as
    /// `AgentContext.canonical_fields()` (Python) leaves it out.
    ///
    /// Both collection fields are sorted ascending before being joined with
    /// a single comma (REQ-9); an empty collection encodes as the empty
    /// string. Rust's `String` ordering over valid UTF-8 is Unicode
    /// code-point order, the same order Python's `sorted()` over `str`
    /// uses, so this produces byte-identical output to the Python substrate
    /// for every input, including non-ASCII members (pinned by vector, not
    /// merely asserted here).
    ///
    /// `authoriser` is encoded as the empty string when absent, exactly as
    /// `AgentContext.canonical_fields()` does with `self.authoriser or ""`.
    fn canonical_fields(&self) -> Vec<(&'static str, String)> {
        let mut permitted_actions = self.permitted_actions.clone();
        permitted_actions.sort();
        let mut consequential_sinks = self.consequential_sinks.clone();
        consequential_sinks.sort();

        vec![
            ("cohort_id", self.cohort_id.clone()),
            ("permitted_actions", permitted_actions.join(",")),
            ("trust_ceiling", self.trust_ceiling.clone()),
            ("consequential_sinks", consequential_sinks.join(",")),
            (
                "authoriser",
                self.authoriser.clone().unwrap_or_default(),
            ),
        ]
    }
}

/// A borrowed, read-only projection of a verified cohort's control surface
/// (REQ-25), immutable for its lifetime. No setter, no owned copy, no
/// interior mutability and no mutable borrow anywhere in this type: every
/// accessor below takes `&self` and returns either a borrowed slice, a
/// borrowed `&str`, or (for [`may_perform`](CohortSurface::may_perform)) a
/// plain `bool`.
///
/// Constructed only from within this crate ([`CohortSurface::new`] is
/// `pub(crate)`): `crate::cohort::VerifiedCohort::surface` (a later issue) is
/// the one place that builds one, from the verified cohort's own content, so
/// a caller can never hand-build a `CohortSurface` over unverified data.
pub struct CohortSurface<'a> {
    cohort_id: &'a str,
    permitted_actions: &'a [String],
    trust_ceiling: &'a str,
    consequential_sinks: &'a [String],
}

impl<'a> CohortSurface<'a> {
    /// Builds a projection borrowed from `record`. `pub(crate)`: see the
    /// type's own doc comment for why this must not be public.
    pub(crate) fn new(record: &'a CohortDefinition) -> Self {
        CohortSurface {
            cohort_id: &record.cohort_id,
            permitted_actions: &record.permitted_actions,
            trust_ceiling: &record.trust_ceiling,
            consequential_sinks: &record.consequential_sinks,
        }
    }

    /// The cohort's own id.
    pub fn cohort_id(&self) -> &str {
        self.cohort_id
    }

    /// The action names this cohort may perform.
    pub fn permitted_actions(&self) -> &[String] {
        self.permitted_actions
    }

    /// The cohort's trust ceiling, handled as an opaque string everywhere in
    /// this crate (REQ-21): never ranked, parsed or compared for ordering
    /// here.
    pub fn trust_ceiling(&self) -> &str {
        self.trust_ceiling
    }

    /// The sink names that are consequential for this cohort.
    pub fn consequential_sinks(&self) -> &[String] {
        self.consequential_sinks
    }

    /// Whether `action` is one of this cohort's own permitted actions.
    pub fn may_perform(&self, action: &str) -> bool {
        self.permitted_actions.iter().any(|a| a == action)
    }
}
