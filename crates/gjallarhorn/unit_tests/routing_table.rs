// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The hardcoded, compile-time routing table (OR-9, REQ-14 to REQ-18; AC-14
//! to AC-18, all eight routes individually). Written from
//! `.opencode/plans/gjallarhorn-build-spec.md` alone, with no sight of the
//! implementation.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crate::routing::{GLOBAL_DEFAULT_ROUTE,
//! route_for}` and `crate::types::{EventType, Route, Severity,
//! SourceProvenance}` exist. That is expected and correct at this stage.
//!
//! Wired into the crate by `lib.rs`'s
//! `#[cfg(test)] #[path = "../unit_tests/routing_table.rs"] mod routing_table;`
//! declaration (REQ-52).
//!
//! **AC-14's and AC-16's source-scan and doc-comment obligations (no
//! wildcard arm in `route_for`'s match; no `std::fs`/`std::env`/
//! `read_to_string`/`static mut`/`OnceLock` anywhere in `routing.rs`; the
//! module doc comment's own stated reasoning) are mechanical, file-content
//! checks rather than runtime behaviour, and are asserted here by reading
//! `routing.rs`'s own source, on `crates/process-engine/unit_tests/sequence_shape.rs`'s
//! own `cleaned_source` convention.**

use crate::routing::{GLOBAL_DEFAULT_ROUTE, route_for};
use crate::types::{EventType, Route, Severity, SourceProvenance};

fn crate_src_dir() -> std::path::PathBuf {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src")
}

/// Reads and line-comment-strips `routing.rs`, on
/// `crates/process-engine/unit_tests/sequence_shape.rs`'s own
/// `cleaned_source` technique: block comments and string literals are not
/// stripped, since none of the probes below needs that fidelity.
fn cleaned_routing_source() -> String {
    let path = crate_src_dir().join("routing.rs");
    let src = std::fs::read_to_string(&path).unwrap_or_else(|e| {
        panic!(
            "expected crates/gjallarhorn/src/routing.rs to exist once this build lands \
             (this is the correct RED state before then): {e}"
        )
    });
    src.lines()
        .map(|line| match line.find("//") {
            Some(idx) => format!("{}{}", &line[..idx], " ".repeat(line.len() - idx)),
            None => line.to_string(),
        })
        .collect::<Vec<_>>()
        .join("\n")
}

// ---------------------------------------------------------------------------------
// AC-14 (REQ-14): route_for's match has exactly eight arms and no wildcard
// arm, and there is no configuration surface in routing.rs.
// ---------------------------------------------------------------------------------

#[test]
fn ac14_route_for_match_has_no_wildcard_arm_in_source() {
    let cleaned = cleaned_routing_source();
    // A conservative textual proxy for "no wildcard arm anywhere in this
    // file's match statements": no bare `_ =>` token sequence. This is
    // deliberately narrow (it would also catch a wildcard arm in some
    // other match in the same file, which is fine: routing.rs's only
    // exhaustive dispatch is route_for's own, per REQ-14).
    assert!(
        !cleaned.contains("_ =>") && !cleaned.contains("_=>"),
        "AC-14/REQ-14: routing.rs must contain no wildcard (`_`) match arm anywhere, so \
         a ninth EventType variant fails the build rather than folding into a catch-all"
    );
}

#[test]
fn ac14_routing_module_has_no_configuration_surface() {
    let cleaned = cleaned_routing_source();
    for forbidden in ["std::fs", "std::env", "read_to_string", "static mut", "OnceLock"] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-14/REQ-14: routing.rs must contain no {forbidden:?}: no file read, no \
             environment read, no argument parse and no mutable global anywhere in this \
             module"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-15 (REQ-15): route_for returns exactly the DD's own eight-row table,
// asserted individually for all eight, with the two the DD's test plan
// names explicitly (audit-integrity to halt-system, instruction-pattern to
// log-only) each in their own named case.
// ---------------------------------------------------------------------------------

#[test]
fn ac15_instruction_pattern_at_boundary_routes_to_log_only() {
    assert_eq!(
        route_for(EventType::InstructionPatternAtBoundary),
        Route::LogOnly,
        "AC-15: InstructionPatternAtBoundary must route to LogOnly (DD section 3.1)"
    );
}

#[test]
fn ac15_constraint_axiom_violated_routes_to_human_notify() {
    assert_eq!(
        route_for(EventType::ConstraintAxiomViolated),
        Route::HumanNotify
    );
}

#[test]
fn ac15_taint_boundary_breach_attempt_routes_to_human_notify() {
    assert_eq!(
        route_for(EventType::TaintBoundaryBreachAttempt),
        Route::HumanNotify
    );
}

#[test]
fn ac15_anomaly_surfaced_routes_to_human_notify() {
    assert_eq!(route_for(EventType::AnomalySurfaced), Route::HumanNotify);
}

#[test]
fn ac15_resource_limit_breached_routes_to_human_notify() {
    assert_eq!(
        route_for(EventType::ResourceLimitBreached),
        Route::HumanNotify
    );
}

#[test]
fn ac15_promotion_request_above_threshold_routes_to_human_notify() {
    assert_eq!(
        route_for(EventType::PromotionRequestAboveThreshold),
        Route::HumanNotify
    );
}

#[test]
fn ac15_attempt_introspection_or_canary_fire_routes_to_halt_agent() {
    assert_eq!(
        route_for(EventType::AttemptIntrospectionOrCanaryFire),
        Route::HaltAgent
    );
}

#[test]
fn ac15_audit_log_integrity_failure_routes_to_halt_system() {
    assert_eq!(
        route_for(EventType::AuditLogIntegrityFailure),
        Route::HaltSystem,
        "AC-15: AuditLogIntegrityFailure must route to HaltSystem (DD section 3.1), the \
         DD's own explicitly-named highest-force case"
    );
}

// ---------------------------------------------------------------------------------
// AC-16 (REQ-16): the global default is HumanNotify, never LogOnly, and the
// module doc comment states the DD section 5 bullet one reasoning.
// ---------------------------------------------------------------------------------

#[test]
fn ac16_global_default_route_is_human_notify_not_log_only() {
    assert_eq!(
        GLOBAL_DEFAULT_ROUTE,
        Route::HumanNotify,
        "AC-16/REQ-16: the retained global default must be HumanNotify, never LogOnly, \
         because an absent event type must escalate rather than fall through to log-only"
    );
    assert_ne!(GLOBAL_DEFAULT_ROUTE, Route::LogOnly);
}

#[test]
fn ac16_routing_module_doc_comment_states_the_escalation_reasoning() {
    // Deliberately the RAW source, not cleaned_routing_source()'s
    // comment-stripped version: this test's whole job is to inspect doc
    // comment TEXT, which cleaned_routing_source() exists to strip away
    // for the wildcard/configuration-surface scans above.
    let src = std::fs::read_to_string(crate_src_dir().join("routing.rs")).unwrap_or_else(|e| {
        panic!("expected crates/gjallarhorn/src/routing.rs to exist: {e}")
    });
    let lower = src.to_lowercase();
    assert!(
        lower.contains("escalat"),
        "AC-16/REQ-16: routing.rs's module doc comment must state, in its own words, why \
         the default must escalate rather than fall through to log-only (DD section 5 \
         bullet one)"
    );
}

// ---------------------------------------------------------------------------------
// AC-17 (REQ-17): the module doc comment states the structural-
// unrepresentability property, that it is stronger than the DD's own
// fail-closed default, and that the constant is retained as defence in
// depth; the constant's value is asserted by a test (done above by AC-16).
// ---------------------------------------------------------------------------------

#[test]
fn ac17_routing_module_doc_comment_states_structural_unrepresentability_and_defence_in_depth() {
    let src = std::fs::read_to_string(crate_src_dir().join("routing.rs")).unwrap_or_else(|e| {
        panic!("expected crates/gjallarhorn/src/routing.rs to exist: {e}")
    });
    let lower = src.to_lowercase();
    assert!(
        lower.contains("unrepresentable"),
        "AC-17/REQ-17: routing.rs's module doc comment must state that an event type \
         absent from the routing table is structurally unrepresentable, because \
         EventType is closed and the dispatch is exhaustive"
    );
    assert!(
        lower.contains("defence in depth") || lower.contains("defense in depth"),
        "AC-17/REQ-17: routing.rs's module doc comment must state that the retained \
         default constant is kept as defence in depth"
    );
}

// ---------------------------------------------------------------------------------
// AC-18 (REQ-18): route_for is a total pure function of EventType alone.
// The same event type paired with differing severities and differing
// provenances (origin class and provenance_protected) must yield the
// identical route in all combinations, because route_for cannot see any of
// them (its signature takes only an EventType).
// ---------------------------------------------------------------------------------

#[test]
fn ac18_route_for_signature_takes_exactly_one_event_type_parameter_and_nothing_else() {
    // A function-pointer coercion: this compiles only if route_for's
    // signature is EXACTLY `fn(EventType) -> Route`, with no second
    // parameter for Severity, SourceProvenance, a correlation key, an
    // audit reference, an arrival ordinal, a ProtectedChannel, a
    // TriageQueue or an Incident. This is REQ-18's own structural proof:
    // if any of those were ever added to the signature, this line would
    // fail to compile.
    let _signature_is_exactly_one_event_type_in: fn(EventType) -> Route = route_for;
}

#[test]
fn ac18_route_for_is_invariant_under_differing_severity_and_provenance_it_cannot_see() {
    // route_for's signature is `fn route_for(event_type: EventType) -> Route`
    // (REQ-18): the fact that this test cannot pass a Severity or a
    // SourceProvenance to it at all is itself the proof. The four
    // combinations below are constructed only to demonstrate that VARYING
    // them (in values this test constructs but never passes to route_for)
    // has no observable effect, because there is no channel for them to
    // travel through.
    let _severity_a = Severity::Informational;
    let _severity_b = Severity::Critical;
    let _provenance_a = SourceProvenance::new(
        "raiser".to_string(),
        "origin".to_string(),
        "class-a".to_string(),
        false,
    );
    let _provenance_b = SourceProvenance::new(
        "raiser".to_string(),
        "origin".to_string(),
        "class-b".to_string(),
        true,
    );

    let route_1 = route_for(EventType::ConstraintAxiomViolated);
    let route_2 = route_for(EventType::ConstraintAxiomViolated);
    let route_3 = route_for(EventType::ConstraintAxiomViolated);
    let route_4 = route_for(EventType::ConstraintAxiomViolated);

    assert_eq!(route_1, route_2);
    assert_eq!(route_2, route_3);
    assert_eq!(route_3, route_4);
    assert_eq!(
        route_1,
        Route::HumanNotify,
        "AC-18: route_for's signature takes only an EventType, so severity and \
         provenance cannot reach it and the route for a fixed event type is always \
         identical"
    );
}
