// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! Gjallarhorn's vocabulary (section 4.0's own description of this module's
//! one responsibility): the closed event-type enum, the closed route enum,
//! severity, provenance and the opaque event. No decision, no routing, no
//! admission lives here; those belong to `routing.rs` and `channel.rs`.

/// REQ-7: a closed public enum with exactly eight variants, one for each of
/// the design document's section 3.1 trigger-type rows, in that table's own
/// order. No ninth variant. No `FromStr`, no `TryFrom<String>`, no
/// `From<&str>` and no `as_str`-to-`from_str` round trip anywhere in the
/// crate, so an unrecognised event-type string is structurally
/// unrepresentable rather than merely refused.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum EventType {
    InstructionPatternAtBoundary,
    ConstraintAxiomViolated,
    TaintBoundaryBreachAttempt,
    AnomalySurfaced,
    AttemptIntrospectionOrCanaryFire,
    ResourceLimitBreached,
    PromotionRequestAboveThreshold,
    AuditLogIntegrityFailure,
}

/// REQ-8: a closed public enum with exactly four variants, ordered by force,
/// ascending. No `Default` impl.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Route {
    LogOnly,
    HumanNotify,
    HaltAgent,
    HaltSystem,
}

impl Route {
    /// This route's force, ascending from zero: `LogOnly` is 0, `HumanNotify`
    /// is 1, `HaltAgent` is 2, `HaltSystem` is 3. Total and exhaustive over
    /// all four variants, no wildcard arm, so a fifth route added later fails
    /// the build rather than silently defaulting to a force.
    pub fn force(self) -> u8 {
        match self {
            Route::LogOnly => 0,
            Route::HumanNotify => 1,
            Route::HaltAgent => 2,
            Route::HaltSystem => 3,
        }
    }
}

/// REQ-9: a closed public enum with a total pure ordinal accessor, no
/// wildcard arm and no `Default`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Severity {
    Informational,
    Elevated,
    High,
    Critical,
}

impl Severity {
    /// This severity's position in the declared order, ascending from zero.
    /// Total and exhaustive over all four variants, no wildcard arm, so a
    /// fifth severity added later fails the build rather than silently
    /// defaulting to an ordinal.
    pub fn ordinal(self) -> u8 {
        match self {
            Severity::Informational => 0,
            Severity::Elevated => 1,
            Severity::High => 2,
            Severity::Critical => 3,
        }
    }
}

/// REQ-9: the attacker-uncontrolled admission and correlation input. Carries
/// the raising component, the concrete origin identifier and the origin
/// class, all as owned `String`s, plus `provenance_protected`, which the
/// crate READS and never derives from content (REQ-25).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SourceProvenance {
    raising_component: String,
    origin_id: String,
    origin_class: String,
    provenance_protected: bool,
}

impl SourceProvenance {
    /// Builds a provenance from its four owned parts. Carries no validation
    /// of its own: the eight minting functions in `mint.rs` are the ones
    /// that refuse an empty raising component, origin id or audit reference
    /// (REQ-13), because refusal there is what keeps a blank provenance from
    /// ever reaching a `GjallarhornEvent`.
    pub fn new(
        raising_component: String,
        origin_id: String,
        origin_class: String,
        provenance_protected: bool,
    ) -> Self {
        SourceProvenance {
            raising_component,
            origin_id,
            origin_class,
            provenance_protected,
        }
    }

    /// The component that raised this event.
    pub fn raising_component(&self) -> &str {
        &self.raising_component
    }

    /// The concrete origin identifier: which instance, task or run this
    /// event traces back to.
    pub fn origin_id(&self) -> &str {
        &self.origin_id
    }

    /// The origin's class: what kind of thing raised this event.
    pub fn origin_class(&self) -> &str {
        &self.origin_class
    }

    /// Whether this provenance is itself a critical source, read directly
    /// rather than derived from any content field (REQ-25).
    pub fn provenance_protected(&self) -> bool {
        self.provenance_protected
    }
}

/// REQ-10: every field private, accessors only, no mutator. No `Default`, no
/// `From`, no `TryFrom`, no `Deref`, no public field.
///
/// `Clone` IS derived, deliberately: an event is data to be aggregated, not a
/// witness of a verification, so unlike `hierarchy_vor::VerifiedPromotion`
/// there is nothing unforgeable being protected by withholding `Clone`. What
/// IS protected is the type field, and REQ-11 protects it by keeping
/// `EventType` off every public input position, so a clone of an event
/// cannot have its type changed either.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GjallarhornEvent {
    event_type: EventType,
    source: SourceProvenance,
    severity: Severity,
    correlation_key: String,
    audit_ref: String,
    arrival_ordinal: u64,
}

impl GjallarhornEvent {
    /// This event's stamped type.
    pub fn event_type(&self) -> EventType {
        self.event_type
    }

    /// This event's source provenance.
    pub fn source(&self) -> &SourceProvenance {
        &self.source
    }

    /// This event's severity.
    pub fn severity(&self) -> Severity {
        self.severity
    }

    /// This event's correlation key, derived deterministically from typed
    /// fields alone (REQ-31), not a caller-supplied value.
    pub fn correlation_key(&self) -> &str {
        &self.correlation_key
    }

    /// A reference into the audit trail this event's minting was recorded
    /// against.
    pub fn audit_ref(&self) -> &str {
        &self.audit_ref
    }

    /// The caller-supplied arrival ordinal used for age-only triage ordering
    /// (REQ-27). Never a clock the crate reads (REQ-6).
    pub fn arrival_ordinal(&self) -> u64 {
        self.arrival_ordinal
    }

    /// REQ-11: `pub(crate)` only, the single construction site the eight
    /// minting functions of `mint.rs` call. Nothing outside this crate can
    /// name it, so nothing outside this crate can choose an event type.
    pub(crate) fn new(
        event_type: EventType,
        source: SourceProvenance,
        severity: Severity,
        correlation_key: String,
        audit_ref: String,
        arrival_ordinal: u64,
    ) -> Self {
        GjallarhornEvent {
            event_type,
            source,
            severity,
            correlation_key,
            audit_ref,
            arrival_ordinal,
        }
    }
}
