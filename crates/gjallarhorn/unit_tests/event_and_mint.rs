// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! `EventType`'s closed vocabulary, the narrow minting surface (GJ-B-1) and
//! the correlation key's derivation cases (REQ-7 to REQ-13, REQ-31; AC-7 to
//! AC-13, AC-31's derivation cases). Written from
//! `.opencode/plans/gjallarhorn-build-spec.md` alone, with no sight of the
//! implementation.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crate::types::{EventType, Route,
//! Severity, SourceProvenance, GjallarhornEvent}`, `crate::mint::{MintRefusal,
//! mint_instruction_pattern_at_boundary, mint_constraint_axiom_violated,
//! mint_taint_boundary_breach_attempt, mint_anomaly_surfaced,
//! mint_attempt_introspection_or_canary_fire, mint_resource_limit_breached,
//! mint_promotion_request_above_threshold, mint_audit_log_integrity_failure}`
//! and `crate::aggregate::correlation_key_for` all exist. That is expected
//! and correct at this stage: `crates/gjallarhorn/` does not exist yet.
//!
//! Wired into the crate by `lib.rs`'s
//! `#[cfg(test)] #[path = "../unit_tests/event_and_mint.rs"] mod event_and_mint;`
//! declaration (REQ-52), so this file is compiled as an in-crate module.

use crate::mint::{
    MintRefusal, mint_anomaly_surfaced, mint_attempt_introspection_or_canary_fire,
    mint_audit_log_integrity_failure, mint_constraint_axiom_violated,
    mint_instruction_pattern_at_boundary, mint_promotion_request_above_threshold,
    mint_resource_limit_breached, mint_taint_boundary_breach_attempt,
};
use crate::types::{EventType, Severity, SourceProvenance};

/// A well-formed, non-empty provenance fixture used across this file. The
/// minting functions must accept this and refuse only on the deliberately
/// broken variants each test builds from it.
fn valid_provenance() -> SourceProvenance {
    SourceProvenance::new(
        "test-raising-component".to_string(),
        "test-origin-id".to_string(),
        "test-origin-class".to_string(),
        false,
    )
}

fn provenance_with(
    raising_component: &str,
    origin_id: &str,
    origin_class: &str,
    protected: bool,
) -> SourceProvenance {
    SourceProvenance::new(
        raising_component.to_string(),
        origin_id.to_string(),
        origin_class.to_string(),
        protected,
    )
}

// ---------------------------------------------------------------------------------
// AC-7 (REQ-7): EventType has exactly eight variants, in the DD's own order,
// and no string-conversion route exists for it. The exhaustive match below
// compiles only if EventType has exactly these eight variants and no more.
// ---------------------------------------------------------------------------------

#[test]
fn ac7_event_type_has_exactly_eight_variants_in_dd_order() {
    fn ordinal(t: EventType) -> u8 {
        match t {
            EventType::InstructionPatternAtBoundary => 0,
            EventType::ConstraintAxiomViolated => 1,
            EventType::TaintBoundaryBreachAttempt => 2,
            EventType::AnomalySurfaced => 3,
            EventType::AttemptIntrospectionOrCanaryFire => 4,
            EventType::ResourceLimitBreached => 5,
            EventType::PromotionRequestAboveThreshold => 6,
            EventType::AuditLogIntegrityFailure => 7,
            // Deliberately NO wildcard arm: a ninth variant added later must
            // fail this match at compile time, which is itself part of the
            // proof this test pins (EC-4).
        }
    }
    let ordered = [
        EventType::InstructionPatternAtBoundary,
        EventType::ConstraintAxiomViolated,
        EventType::TaintBoundaryBreachAttempt,
        EventType::AnomalySurfaced,
        EventType::AttemptIntrospectionOrCanaryFire,
        EventType::ResourceLimitBreached,
        EventType::PromotionRequestAboveThreshold,
        EventType::AuditLogIntegrityFailure,
    ];
    for (i, t) in ordered.iter().enumerate() {
        assert_eq!(
            ordinal(*t),
            i as u8,
            "AC-7: EventType's declaration order must match the DD section 3.1 row order"
        );
    }
}

// AC-7's second half (no FromStr/TryFrom<String>/From<&str>/from_str
// anywhere targeting EventType) is a source-scan property that belongs to
// the crate's own mechanical posture checks (`rust_gjallarhorn_harness.py`,
// out of scope for this Rust suite per the delegating prompt) and to
// `tests/public_surface.rs`'s compile-boundary confirmations for the
// public-surface half. This file asserts only the variant count and order,
// which is the part expressible as a passing Rust test.

// ---------------------------------------------------------------------------------
// AC-12 (REQ-12): eight public minting functions exist, each stamps its own
// variant and no other, and none takes an EventType or a Route parameter.
// ---------------------------------------------------------------------------------

#[test]
fn ac12_each_of_the_eight_minting_functions_stamps_its_own_variant_and_no_other() {
    let cases: Vec<(EventType, fn(SourceProvenance, Severity, String, u64) -> Result<crate::GjallarhornEvent, MintRefusal>)> = vec![
        (
            EventType::InstructionPatternAtBoundary,
            mint_instruction_pattern_at_boundary,
        ),
        (
            EventType::ConstraintAxiomViolated,
            mint_constraint_axiom_violated,
        ),
        (
            EventType::TaintBoundaryBreachAttempt,
            mint_taint_boundary_breach_attempt,
        ),
        (EventType::AnomalySurfaced, mint_anomaly_surfaced),
        (
            EventType::AttemptIntrospectionOrCanaryFire,
            mint_attempt_introspection_or_canary_fire,
        ),
        (
            EventType::ResourceLimitBreached,
            mint_resource_limit_breached,
        ),
        (
            EventType::PromotionRequestAboveThreshold,
            mint_promotion_request_above_threshold,
        ),
        (
            EventType::AuditLogIntegrityFailure,
            mint_audit_log_integrity_failure,
        ),
    ];
    assert_eq!(
        cases.len(),
        8,
        "AC-12: exactly eight minting functions must exist, one per EventType variant"
    );
    for (expected_type, mint_fn) in cases {
        let event = mint_fn(valid_provenance(), Severity::Elevated, "audit-ref-1".to_string(), 42)
            .unwrap_or_else(|e| {
                panic!(
                    "AC-12: minting {expected_type:?} with a valid provenance, severity, \
                     audit ref and ordinal must succeed; got Err({e:?})"
                )
            });
        assert_eq!(
            event.event_type(),
            expected_type,
            "AC-12: the minting function for {expected_type:?} must stamp exactly that \
             variant and no other"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-13 (REQ-13), EC-18: every minting function refuses on an empty raising
// component, an empty origin id, or an empty audit ref, with the matching
// MintRefusal variant, and never returns an event on any of the three.
// ---------------------------------------------------------------------------------

type MintFn = fn(SourceProvenance, Severity, String, u64) -> Result<crate::GjallarhornEvent, MintRefusal>;

fn all_eight_minting_functions() -> Vec<(&'static str, MintFn)> {
    vec![
        (
            "mint_instruction_pattern_at_boundary",
            mint_instruction_pattern_at_boundary,
        ),
        (
            "mint_constraint_axiom_violated",
            mint_constraint_axiom_violated,
        ),
        (
            "mint_taint_boundary_breach_attempt",
            mint_taint_boundary_breach_attempt,
        ),
        ("mint_anomaly_surfaced", mint_anomaly_surfaced),
        (
            "mint_attempt_introspection_or_canary_fire",
            mint_attempt_introspection_or_canary_fire,
        ),
        (
            "mint_resource_limit_breached",
            mint_resource_limit_breached,
        ),
        (
            "mint_promotion_request_above_threshold",
            mint_promotion_request_above_threshold,
        ),
        (
            "mint_audit_log_integrity_failure",
            mint_audit_log_integrity_failure,
        ),
    ]
}

#[test]
fn ac13_all_eight_functions_refuse_on_an_empty_raising_component() {
    for (name, mint_fn) in all_eight_minting_functions() {
        let source = provenance_with("", "origin-id", "origin-class", false);
        let outcome = mint_fn(source, Severity::Informational, "audit-ref".to_string(), 1);
        assert_eq!(
            outcome,
            Err(MintRefusal::EmptyRaisingComponent),
            "AC-13/EC-18: {name} must refuse Err(EmptyRaisingComponent) on an empty \
             raising component; got {outcome:?}"
        );
    }
}

#[test]
fn ac13_all_eight_functions_refuse_on_an_empty_origin_id() {
    for (name, mint_fn) in all_eight_minting_functions() {
        let source = provenance_with("raising-component", "", "origin-class", false);
        let outcome = mint_fn(source, Severity::Informational, "audit-ref".to_string(), 1);
        assert_eq!(
            outcome,
            Err(MintRefusal::EmptyOriginId),
            "AC-13/EC-18: {name} must refuse Err(EmptyOriginId) on an empty origin id; \
             got {outcome:?}"
        );
    }
}

#[test]
fn ac13_all_eight_functions_refuse_on_an_empty_audit_ref() {
    for (name, mint_fn) in all_eight_minting_functions() {
        let source = provenance_with("raising-component", "origin-id", "origin-class", false);
        let outcome = mint_fn(source, Severity::Informational, String::new(), 1);
        assert_eq!(
            outcome,
            Err(MintRefusal::EmptyAuditRef),
            "AC-13/EC-18: {name} must refuse Err(EmptyAuditRef) on an empty audit ref; \
             got {outcome:?}"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-8 (REQ-8): Route's force() is total, exhaustive, no wildcard, ascending
// 0,1,2,3, and Route has no Default impl (the no-Default half is a
// source-scan/compile-boundary concern left to tests/public_surface.rs and
// the mechanical posture harness; this test asserts the ordinal mapping).
// ---------------------------------------------------------------------------------

#[test]
fn ac8_route_force_is_ascending_zero_through_three() {
    assert_eq!(crate::types::Route::LogOnly.force(), 0);
    assert_eq!(crate::types::Route::HumanNotify.force(), 1);
    assert_eq!(crate::types::Route::HaltAgent.force(), 2);
    assert_eq!(crate::types::Route::HaltSystem.force(), 3);
}

// ---------------------------------------------------------------------------------
// AC-9 (REQ-9): Severity's ordinal() is strictly increasing in declaration
// order, and SourceProvenance's four accessors return exactly what was
// passed to `new`.
// ---------------------------------------------------------------------------------

#[test]
fn ac9_severity_ordinal_is_strictly_increasing_in_declaration_order() {
    let ordered = [
        Severity::Informational,
        Severity::Elevated,
        Severity::High,
        Severity::Critical,
    ];
    for i in 0..ordered.len() - 1 {
        assert!(
            ordered[i].ordinal() < ordered[i + 1].ordinal(),
            "AC-9: Severity::ordinal() must be strictly ascending across the declared \
             order; {:?} did not rank below {:?}",
            ordered[i],
            ordered[i + 1],
        );
    }
}

#[test]
fn ac9_source_provenance_accessors_return_exactly_what_was_passed_to_new() {
    let source = SourceProvenance::new(
        "raiser".to_string(),
        "origin-42".to_string(),
        "class-x".to_string(),
        true,
    );
    assert_eq!(source.raising_component(), "raiser");
    assert_eq!(source.origin_id(), "origin-42");
    assert_eq!(source.origin_class(), "class-x");
    assert!(source.provenance_protected());
}

// ---------------------------------------------------------------------------------
// AC-10 (REQ-10), the in-crate half: every accessor on GjallarhornEvent
// returns what the minting function was given (or, for the correlation
// key, what the derivation produces). The compile-boundary half (private
// fields, no mutator reachable, no Default/From/TryFrom/Deref) lives in
// tests/public_surface.rs, compiled as an external crate, per the spec's
// own file plan (section 8 file 17).
// ---------------------------------------------------------------------------------

#[test]
fn ac10_accessors_return_exactly_what_the_minting_function_was_given() {
    let source = provenance_with("himinbjorg-validation", "task-9001", "engine", false);
    let event = mint_constraint_axiom_violated(
        source.clone(),
        Severity::High,
        "audit-ref-77".to_string(),
        900,
    )
    .expect("a well-formed constraint-axiom-violated mint must succeed");

    assert_eq!(event.event_type(), EventType::ConstraintAxiomViolated);
    assert_eq!(event.source(), &source);
    assert_eq!(event.severity(), Severity::High);
    assert_eq!(event.audit_ref(), "audit-ref-77");
    assert_eq!(event.arrival_ordinal(), 900);
    // The correlation key is derived, not passed: it must equal what
    // correlation_key_for produces for the same (type, source) pair
    // (REQ-31, asserted fully in ac31 below).
    assert_eq!(
        event.correlation_key(),
        crate::aggregate::correlation_key_for(EventType::ConstraintAxiomViolated, &source)
    );
}

// ---------------------------------------------------------------------------------
// AC-31 (REQ-31), the anti-forgery criterion's derivation cases: identical
// inputs give identical keys; sharing raising_component+origin_id gives the
// same key regardless of severity/audit_ref/ordinal; differing origin id
// gives a different key; the derivation reads only EventType and
// SourceProvenance.
// ---------------------------------------------------------------------------------

#[test]
fn ac31_correlation_key_for_is_deterministic_over_identical_inputs() {
    let source = provenance_with("raiser", "origin-a", "class", false);
    let key1 = crate::aggregate::correlation_key_for(EventType::AnomalySurfaced, &source);
    let key2 = crate::aggregate::correlation_key_for(EventType::AnomalySurfaced, &source);
    assert_eq!(
        key1, key2,
        "AC-31: correlation_key_for must return identical keys for identical inputs on \
         every call"
    );
}

#[test]
fn ac31_events_sharing_source_term_collapse_regardless_of_severity_audit_ref_or_ordinal() {
    let source = provenance_with("shared-raiser", "shared-origin", "class-a", false);
    let event_a = mint_anomaly_surfaced(
        source.clone(),
        Severity::Informational,
        "audit-ref-a".to_string(),
        1,
    )
    .expect("mint must succeed");
    let event_b = mint_anomaly_surfaced(
        source,
        Severity::Critical,
        "audit-ref-b".to_string(),
        99999,
    )
    .expect("mint must succeed");

    assert_eq!(
        event_a.correlation_key(),
        event_b.correlation_key(),
        "AC-31: two events sharing the raising component and origin id must collapse to \
         the same correlation key even though severity, audit ref and arrival ordinal \
         all differ"
    );
}

#[test]
fn ac31_events_differing_in_origin_id_receive_different_keys() {
    let source_a = provenance_with("raiser", "origin-a", "class", false);
    let source_b = provenance_with("raiser", "origin-b", "class", false);
    let key_a = crate::aggregate::correlation_key_for(EventType::ResourceLimitBreached, &source_a);
    let key_b = crate::aggregate::correlation_key_for(EventType::ResourceLimitBreached, &source_b);
    assert_ne!(
        key_a, key_b,
        "AC-31: two events differing in origin identifier must receive different \
         correlation keys"
    );
}

#[test]
fn ac31_correlation_key_is_not_a_parameter_of_any_minting_function() {
    // Structural proof by construction: every minting function's signature
    // is (SourceProvenance, Severity, String, u64) -> Result<..>, with no
    // additional String parameter through which a caller could supply a
    // forged or colliding key. This is asserted by the very fact that
    // ac12's `MintFn` type alias above compiles against all eight
    // functions with exactly that arity: a ninth parameter accepting a
    // caller-supplied key would break that alias and fail this file to
    // compile, which is itself part of the proof.
    let _proof: MintFn = mint_anomaly_surfaced;
}

// ---------------------------------------------------------------------------------
// EC-2 / D103's limit two, named here rather than closed (no test asserts a
// backstop that does not exist): an in-crate module that honestly
// constructs an event with a wrong source produces a correctly-routed
// alert about the wrong thing. This file does not test a backstop for that
// because REQ-13's own module doc comment (record.rs) and this spec's
// section 12.3 both state plainly that none exists.
// ---------------------------------------------------------------------------------
