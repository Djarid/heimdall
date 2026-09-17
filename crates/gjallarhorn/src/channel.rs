// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! Channel separation (GJ-B-2). This module's one responsibility (section
//! 4.0): own the two separate structures and the single admission rule.
//! It decides which structure an event is admitted to; it never decides
//! which route the event takes, that is `routing.rs`'s own job.
//!
//! **The two structures share nothing (REQ-24).** [`ProtectedChannel`] and
//! [`TriageQueue`] are two distinct types with no shared backing store, no
//! common supertype, no trait implemented by both that exposes their
//! contents, no `From` or `TryFrom` in either direction, and no method
//! anywhere on either type that moves, copies or promotes an item from one
//! into the other. Burying an escalation in a triage flood must be
//! structurally impossible rather than merely unlikely, and the absence of
//! every one of those seams is how that holds.
//!
//! **Admission is one pure function of type and provenance alone
//! (REQ-25).** [`admission_for`] reads only the event type and the source
//! provenance. It never reads the severity, the correlation key, the audit
//! reference, the arrival ordinal or any content field. The four types
//! that admit to the protected channel are exactly
//! [`crate::types::EventType::PromotionRequestAboveThreshold`],
//! [`crate::types::EventType::AuditLogIntegrityFailure`],
//! [`crate::types::EventType::AttemptIntrospectionOrCanaryFire`] and
//! [`crate::types::EventType::ConstraintAxiomViolated`]. Additionally, and
//! independently of type, any event whose provenance carries
//! `provenance_protected` admits to the protected channel, even one of the
//! other four types that would otherwise triage. Everything else admits to
//! the triage queue.
//!
//! **The protected channel is append only, with no bound anywhere
//! (REQ-26).** [`ProtectedChannel`] admits and reads; no method on it
//! updates, shortens, reorders or takes anything away from an
//! already-admitted entry. An admitted escalation stays readable
//! regardless of how many items the triage queue subsequently holds, with
//! no upper limit and no capacity bound anywhere on the type.
//!
//! **The triage queue's ordering is age only, and this is stated as a
//! partial ordering rather than as the design document's own triage
//! priority (REQ-27, REQ-28, REQ-30).** [`TriageQueue::ordered`] sorts
//! solely by the caller-supplied arrival ordinal each event carries; it
//! reads no clock this crate reads and no arrival order into the structure
//! itself. The design document's own triage priority is built from four
//! terms: age, a reputation score, clean-run history and known-critical
//! membership. Three of those four, the reputation score, the clean-run
//! history and the known-critical membership, come from Muninn and the
//! world model, and neither exists in Rust, so none of the three is read
//! here: there is no reputation parameter, no reputation field, no
//! origin-class weighting, no clean-run-history input and no
//! known-critical-membership weighting anywhere in this module, and none
//! of the three is stood in for by a stub, a placeholder, a mock or a
//! default value. Only age is implemented. HLD risk R-5 is **therefore
//! untouched by this build and must not be read as closed**: this ordering
//! is one of the design document's four terms, not its triage priority as
//! a whole.
//!
//! **The two structures are separately sized (REQ-29).** Each is
//! separately constructible, separately readable and independently sized:
//! admitting to one never changes the other's length, in either
//! direction.

use crate::types::{EventType, GjallarhornEvent, SourceProvenance};

/// REQ-25: the outcome of [`admission_for`]'s single pure decision. Which
/// of the two structures an event belongs to, and nothing more; carries no
/// information about the route.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Admission {
    /// The event admits to [`ProtectedChannel`].
    Protected,
    /// The event admits to [`TriageQueue`].
    Triage,
}

/// REQ-25: a pure function of the event type and the source provenance
/// only. `Severity`, the correlation key, the audit reference and the
/// arrival ordinal are absent from this signature, and every content field
/// is absent too, so an admission can never be derived from
/// attacker-supplied content.
///
/// Returns [`Admission::Protected`] for
/// [`EventType::PromotionRequestAboveThreshold`],
/// [`EventType::AuditLogIntegrityFailure`],
/// [`EventType::AttemptIntrospectionOrCanaryFire`] and
/// [`EventType::ConstraintAxiomViolated`], matching the design document's
/// own list; and, independently of type, for any event whose provenance
/// carries `provenance_protected`, which is the design document's own
/// critical-source bullet. Every other type, when the provenance is not
/// itself protected, returns [`Admission::Triage`].
pub fn admission_for(event_type: EventType, source: &SourceProvenance) -> Admission {
    if source.provenance_protected() {
        return Admission::Protected;
    }
    match event_type {
        EventType::PromotionRequestAboveThreshold
        | EventType::AuditLogIntegrityFailure
        | EventType::AttemptIntrospectionOrCanaryFire
        | EventType::ConstraintAxiomViolated => Admission::Protected,
        EventType::InstructionPatternAtBoundary
        | EventType::TaintBoundaryBreachAttempt
        | EventType::AnomalySurfaced
        | EventType::ResourceLimitBreached => Admission::Triage,
    }
}

/// REQ-24, REQ-26: append only, unbounded, with no upper limit, no cap
/// and no reorder anywhere on this type. Carries no shared backing store
/// with [`TriageQueue`], no common trait exposing its contents, no `From`
/// or `TryFrom` in either direction, and no method anywhere that moves an
/// item into [`TriageQueue`].
#[derive(Debug, Default)]
pub struct ProtectedChannel {
    entries: Vec<GjallarhornEvent>,
}

impl ProtectedChannel {
    /// Builds an empty protected channel: no entries until the first
    /// admission.
    pub fn new() -> Self {
        ProtectedChannel {
            entries: Vec::new(),
        }
    }

    /// Admits one event. There is no admission rule enforced here: the
    /// caller (`raise.rs`) is the one that consults [`admission_for`]
    /// before calling this method. Appends only: no method on this type
    /// updates, shortens or reorders an already-admitted entry.
    pub fn admit(&mut self, event: GjallarhornEvent) {
        self.entries.push(event);
    }

    /// Every event this channel holds, in admission order. A read-only
    /// accessor: there is no mutable counterpart anywhere on this type.
    pub fn entries(&self) -> &[GjallarhornEvent] {
        &self.entries
    }

    /// How many events this channel holds.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Whether this channel holds no events.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}

/// REQ-24, REQ-27, REQ-28, REQ-30: ordering is age only, derived solely
/// from the caller-supplied arrival ordinal each event carries. No
/// reputation parameter, no reputation field, no origin-class weighting,
/// no clean-run-history input and no known-critical-membership weighting
/// anywhere on this type, and none of the four terms is stood in for by a
/// stub. Carries no shared backing store with [`ProtectedChannel`], no
/// common trait exposing its contents, no `From` or `TryFrom` in either
/// direction, and no method anywhere that moves an item into
/// [`ProtectedChannel`].
#[derive(Debug, Default)]
pub struct TriageQueue {
    entries: Vec<GjallarhornEvent>,
}

impl TriageQueue {
    /// Builds an empty triage queue: no entries until the first admission.
    pub fn new() -> Self {
        TriageQueue {
            entries: Vec::new(),
        }
    }

    /// Admits one event, in whatever order the caller admits it. This
    /// method itself imposes no ordering: [`TriageQueue::ordered`] is
    /// where the age-only ordering is applied, on read.
    pub fn admit(&mut self, event: GjallarhornEvent) {
        self.entries.push(event);
    }

    /// Every event this queue holds, oldest first by arrival ordinal
    /// (REQ-27). A stable sort: two events sharing an arrival ordinal keep
    /// their relative admission order, so a reviewer reading the queue
    /// twice sees the same sequence (EC-13). Monotonic in age: an item's
    /// position relative to an older item never worsens because newer
    /// items arrived, because the whole ordering is recomputed fresh from
    /// the ordinal alone on every call, never accumulated incrementally.
    pub fn ordered(&self) -> Vec<&GjallarhornEvent> {
        let mut ordered: Vec<&GjallarhornEvent> = self.entries.iter().collect();
        ordered.sort_by_key(|event| event.arrival_ordinal());
        ordered
    }

    /// How many events this queue holds.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Whether this queue holds no events.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }
}
