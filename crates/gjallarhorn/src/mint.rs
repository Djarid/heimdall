// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The narrow minting surface (GJ-B-1). This module's one responsibility
//! (section 4.0): be the only door through which a [`crate::types::GjallarhornEvent`]
//! comes into existence, one function per [`crate::types::EventType`]
//! variant. No routing and no admission live here; those belong to
//! `routing.rs` and `channel.rs`.
//!
//! **The route is unforgeable from outside this crate (REQ-11, REQ-12).**
//! `EventType` appears on no public function's signature anywhere in this
//! crate: not as a parameter, and not inside any parameter's type. Each of
//! the eight functions below takes the source provenance, the severity,
//! the audit reference and the arrival ordinal, never the event type, and
//! stamps its own variant as a compile-time constant inside its own body.
//! Which route an event obtains is therefore fixed by which minting
//! function the caller called, and a caller cannot choose an arbitrary
//! type and route combination.
//!
//! **The refusal path is genuine, not a debug assertion (REQ-13).** Every
//! minting function refuses, with a typed [`MintRefusal`], when the source
//! provenance's raising component is empty, when its concrete origin
//! identifier is empty, or when the audit reference is empty. An event
//! with no attributable origin must never be constructed, because both the
//! correlation key ([`crate::aggregate::correlation_key_for`]) and the
//! channel admission rule ([`crate::channel::admission_for`]) read the
//! provenance, and a blank provenance would collapse unrelated events into
//! one incident.
//!
//! **The correlation key is derived, not supplied (REQ-31's anti-forgery
//! property).** No minting function below takes a correlation key as a
//! parameter. Each one derives it internally by calling
//! [`crate::aggregate::correlation_key_for`] over the provenance and the
//! function's own stamped type, so a caller can neither supply a forged
//! key to defeat correlation nor a colliding one to force a false
//! collapse. Putting the derivation inside the mint, rather than leaving it
//! to the caller, is what makes this property structural rather than a
//! matter of caller discipline.

use crate::aggregate::correlation_key_for;
use crate::types::{EventType, GjallarhornEvent, Severity, SourceProvenance};

/// REQ-13: a genuine runtime refusal path, closed set. Returned by every
/// one of the eight minting functions below when the source provenance's
/// raising component is empty, when its origin identifier is empty, or
/// when the audit reference is empty. No event is ever returned alongside
/// a refusal.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MintRefusal {
    /// The source provenance's raising component was empty.
    EmptyRaisingComponent,
    /// The source provenance's concrete origin identifier was empty.
    EmptyOriginId,
    /// The audit reference was empty.
    EmptyAuditRef,
}

/// The one validation and construction routine every minting function
/// below shares. Refuses per REQ-13's three checks, in that order; on
/// success derives the correlation key from the stamped type and the
/// provenance alone (REQ-31) and constructs the event through
/// [`GjallarhornEvent::new`], the single `pub(crate)` construction site
/// this crate exposes (REQ-11).
fn mint(
    event_type: EventType,
    source: SourceProvenance,
    severity: Severity,
    audit_ref: String,
    arrival_ordinal: u64,
) -> Result<GjallarhornEvent, MintRefusal> {
    if source.raising_component().is_empty() {
        return Err(MintRefusal::EmptyRaisingComponent);
    }
    if source.origin_id().is_empty() {
        return Err(MintRefusal::EmptyOriginId);
    }
    if audit_ref.is_empty() {
        return Err(MintRefusal::EmptyAuditRef);
    }
    let correlation_key = correlation_key_for(event_type, &source);
    Ok(GjallarhornEvent::new(
        event_type,
        source,
        severity,
        correlation_key,
        audit_ref,
        arrival_ordinal,
    ))
}

/// Mints an [`EventType::InstructionPatternAtBoundary`] event. Takes no
/// `EventType` parameter and no `Route` parameter (REQ-11, REQ-12): the
/// variant is stamped as a compile-time constant in this function's own
/// body.
pub fn mint_instruction_pattern_at_boundary(
    source: SourceProvenance,
    severity: Severity,
    audit_ref: String,
    arrival_ordinal: u64,
) -> Result<GjallarhornEvent, MintRefusal> {
    mint(
        EventType::InstructionPatternAtBoundary,
        source,
        severity,
        audit_ref,
        arrival_ordinal,
    )
}

/// Mints an [`EventType::ConstraintAxiomViolated`] event. Takes no
/// `EventType` parameter and no `Route` parameter (REQ-11, REQ-12): the
/// variant is stamped as a compile-time constant in this function's own
/// body.
pub fn mint_constraint_axiom_violated(
    source: SourceProvenance,
    severity: Severity,
    audit_ref: String,
    arrival_ordinal: u64,
) -> Result<GjallarhornEvent, MintRefusal> {
    mint(
        EventType::ConstraintAxiomViolated,
        source,
        severity,
        audit_ref,
        arrival_ordinal,
    )
}

/// Mints an [`EventType::TaintBoundaryBreachAttempt`] event. Takes no
/// `EventType` parameter and no `Route` parameter (REQ-11, REQ-12): the
/// variant is stamped as a compile-time constant in this function's own
/// body.
pub fn mint_taint_boundary_breach_attempt(
    source: SourceProvenance,
    severity: Severity,
    audit_ref: String,
    arrival_ordinal: u64,
) -> Result<GjallarhornEvent, MintRefusal> {
    mint(
        EventType::TaintBoundaryBreachAttempt,
        source,
        severity,
        audit_ref,
        arrival_ordinal,
    )
}

/// Mints an [`EventType::AnomalySurfaced`] event. Takes no `EventType`
/// parameter and no `Route` parameter (REQ-11, REQ-12): the variant is
/// stamped as a compile-time constant in this function's own body.
pub fn mint_anomaly_surfaced(
    source: SourceProvenance,
    severity: Severity,
    audit_ref: String,
    arrival_ordinal: u64,
) -> Result<GjallarhornEvent, MintRefusal> {
    mint(
        EventType::AnomalySurfaced,
        source,
        severity,
        audit_ref,
        arrival_ordinal,
    )
}

/// Mints an [`EventType::AttemptIntrospectionOrCanaryFire`] event. Takes no
/// `EventType` parameter and no `Route` parameter (REQ-11, REQ-12): the
/// variant is stamped as a compile-time constant in this function's own
/// body.
pub fn mint_attempt_introspection_or_canary_fire(
    source: SourceProvenance,
    severity: Severity,
    audit_ref: String,
    arrival_ordinal: u64,
) -> Result<GjallarhornEvent, MintRefusal> {
    mint(
        EventType::AttemptIntrospectionOrCanaryFire,
        source,
        severity,
        audit_ref,
        arrival_ordinal,
    )
}

/// Mints an [`EventType::ResourceLimitBreached`] event. Takes no
/// `EventType` parameter and no `Route` parameter (REQ-11, REQ-12): the
/// variant is stamped as a compile-time constant in this function's own
/// body.
pub fn mint_resource_limit_breached(
    source: SourceProvenance,
    severity: Severity,
    audit_ref: String,
    arrival_ordinal: u64,
) -> Result<GjallarhornEvent, MintRefusal> {
    mint(
        EventType::ResourceLimitBreached,
        source,
        severity,
        audit_ref,
        arrival_ordinal,
    )
}

/// Mints an [`EventType::PromotionRequestAboveThreshold`] event. Takes no
/// `EventType` parameter and no `Route` parameter (REQ-11, REQ-12): the
/// variant is stamped as a compile-time constant in this function's own
/// body.
pub fn mint_promotion_request_above_threshold(
    source: SourceProvenance,
    severity: Severity,
    audit_ref: String,
    arrival_ordinal: u64,
) -> Result<GjallarhornEvent, MintRefusal> {
    mint(
        EventType::PromotionRequestAboveThreshold,
        source,
        severity,
        audit_ref,
        arrival_ordinal,
    )
}

/// Mints an [`EventType::AuditLogIntegrityFailure`] event. Takes no
/// `EventType` parameter and no `Route` parameter (REQ-11, REQ-12): the
/// variant is stamped as a compile-time constant in this function's own
/// body.
pub fn mint_audit_log_integrity_failure(
    source: SourceProvenance,
    severity: Severity,
    audit_ref: String,
    arrival_ordinal: u64,
) -> Result<GjallarhornEvent, MintRefusal> {
    mint(
        EventType::AuditLogIntegrityFailure,
        source,
        severity,
        audit_ref,
        arrival_ordinal,
    )
}
