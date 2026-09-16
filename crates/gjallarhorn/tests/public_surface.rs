// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! Public-surface sufficiency for `gjallarhorn` (REQ-10, REQ-11, REQ-22,
//! REQ-36, REQ-37, REQ-53; AC-10, AC-11, AC-22, AC-36, AC-37, AC-53), on
//! `crates/hierarchy-vor/tests/public_surface.rs`'s and
//! `crates/process-engine/unit_tests/sequence_shape.rs`'s own precedent for
//! this class of criterion. Written from
//! `.opencode/plans/gjallarhorn-build-spec.md` alone, with no sight of the
//! implementation.
//!
//! Compiled as an EXTERNAL crate importing `gjallarhorn`'s public surface
//! only, exactly as every sibling crate's own `tests/public_surface.rs`
//! does, and exactly as any future non-test caller (the one live raise
//! site inside `crates/process-engine/`, OR-5/OR-7) would. THIS FILE WILL
//! FAIL TO COMPILE until `gjallarhorn` declares its real modules and
//! re-exports its public surface from the crate root. That is the
//! expected RED state at this stage: `crates/gjallarhorn/` does not exist
//! yet.
//!
//! **Signatures assumed here**, per section 4.9 of the spec (the crate-root
//! re-exports): `gjallarhorn::{raise, GjallarhornEvent, EventType, Route,
//! Severity, SourceProvenance, EventRecorder, MinimalEventRecorder,
//! Delivery, InProcessDelivery, ProtectedChannel, TriageQueue, Incident,
//! MintRefusal, AggregateRefusal, RaiseRefusal, RaiseOutcome}`, plus the
//! eight `mint_*` functions and `admission_for`/`Admission` and
//! `route_for`/`GLOBAL_DEFAULT_ROUTE`.
//!
//! **On AC-10's, AC-11's and AC-53's "exact `rustc` output recorded rather
//! than paraphrased" requirement.** Per this repository's own established
//! convention for exactly this class of claim
//! (`crates/hierarchy-vor/tests/public_surface.rs`'s AC-24/AC-39 blocks,
//! `crates/himinbjorg/tests/public_surface.rs`'s AC-35 block,
//! `crates/process-engine/unit_tests/sequence_shape.rs`'s AC-13/AC-40
//! blocks, `crates/cognition-client/tests/public_surface.rs`'s AC-12
//! block), a snippet that must NOT compile cannot be asserted by a passing
//! automated test in this same crate without a `trybuild`-style
//! dev-dependency, which REQ-2's literally-empty-`[dependencies]` rule and
//! this repository's exact-pin discipline both argue against for a check
//! this narrow (and `[dev-dependencies]` are permitted by REQ-2 only when
//! a test genuinely needs one; a trybuild harness for compile-fail
//! snippets this repository already has a documented manual convention
//! for is not a genuine need). Every compile-boundary confirmation below is
//! therefore a documented, commented-out block: to confirm by hand once
//! the crate exists, uncomment ONE block at a time, run
//! `cargo build -p gjallarhorn --tests`, capture rustc's EXACT diagnostic
//! text, and record it verbatim (not paraphrased) in the pull request.
//! Leave every block commented in the committed file, otherwise this crate
//! never builds at all. This is the spec's own required evidencing method
//! for AC-10, AC-11 and AC-53, read literally: "the exact `rustc` output
//! recorded rather than paraphrased" describes a human-captured diagnostic
//! in the pull request, on this repository's own established precedent for
//! this exact recurring criterion shape, not a `#[should_panic]` test or a
//! new `trybuild` dependency.

// ---------------------------------------------------------------------------------
// AC-12/REQ-12 (positive control, exercised for real): the ONLY route to a
// GjallarhornEvent from this external crate is one of the eight minting
// functions. This is exercised without any private-surface access at all,
// which is itself part of the proof that the public surface is sufficient
// (REQ-53).
// ---------------------------------------------------------------------------------

#[test]
fn public_surface_obtains_a_gjallarhorn_event_only_through_a_minting_function() {
    let source = gjallarhorn::SourceProvenance::new(
        "public-surface-raiser".to_string(),
        "public-surface-origin".to_string(),
        "public-surface-class".to_string(),
        false,
    );
    let event = gjallarhorn::mint_anomaly_surfaced(
        source,
        gjallarhorn::Severity::Elevated,
        "audit-ref-public-surface".to_string(),
        1,
    )
    .expect("a well-formed mint through the public surface alone must succeed");

    assert_eq!(event.event_type(), gjallarhorn::EventType::AnomalySurfaced);
}

// ---------------------------------------------------------------------------------
// AC-10 (REQ-10): GjallarhornEvent's fields are all private. A direct field
// access from this external crate must fail to compile.
//
// To confirm by hand once the crate exists: uncomment the block below, run
// `cargo build -p gjallarhorn --tests`, capture rustc's exact diagnostic
// (expected E0616, "field `event_type` of struct `GjallarhornEvent` is
// private", or similar for any other named field), and record it verbatim
// in the pull request. Leave commented in the committed file.
//
// ```rust,ignore
// #[test]
// fn ac10_confirm_direct_field_access_does_not_compile() {
//     let source = gjallarhorn::SourceProvenance::new(
//         "raiser".to_string(),
//         "origin".to_string(),
//         "class".to_string(),
//         false,
//     );
//     let event = gjallarhorn::mint_anomaly_surfaced(
//         source,
//         gjallarhorn::Severity::Elevated,
//         "audit-ref".to_string(),
//         1,
//     )
//     .unwrap();
//     let _bad = event.event_type; // expected: E0616, field is private
// }
// ```
// ---------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------
// AC-11 (REQ-11), GJ-B-1's own criterion: no route from this external crate
// to a GjallarhornEvent with a CHOSEN EventType, by any route (struct
// literal, GjallarhornEvent::new, a From, a builder). Every attempt below
// must be a compile error.
//
// To confirm by hand once the crate exists: uncomment ONE block below at a
// time, run `cargo build -p gjallarhorn --tests`, capture rustc's exact
// diagnostic for that block, and record it verbatim in the pull request.
// Leave every block commented in the committed file.
//
// ```rust,ignore
// // (a) No public struct literal: GjallarhornEvent has no public field.
// // Expected: E0423 or E0616 (private field / cannot construct with a
// // struct literal).
// fn _ac11_confirm_no_struct_literal_construction() {
//     let _bad = gjallarhorn::GjallarhornEvent {
//         event_type: gjallarhorn::EventType::AnomalySurfaced,
//         // .. any other fields, if any were public
//     };
// }
//
// // (b) No public GjallarhornEvent::new: it is pub(crate) only (REQ-11).
// // Expected: E0603 ("function `new` is private") or E0599 (no function
// // named `new` found).
// fn _ac11_confirm_new_is_not_public() {
//     let source = gjallarhorn::SourceProvenance::new(
//         "raiser".to_string(),
//         "origin".to_string(),
//         "class".to_string(),
//         false,
//     );
//     let _bad = gjallarhorn::GjallarhornEvent::new(
//         gjallarhorn::EventType::AnomalySurfaced,
//         source,
//         gjallarhorn::Severity::Elevated,
//         "forged-key".to_string(),
//         "audit-ref".to_string(),
//         1,
//     ); // expected: E0603 or E0599
// }
//
// // (c) No public From/TryFrom/builder that takes an EventType. Expected:
// // E0277 (trait not implemented) or E0599 (no method/function found).
// fn _ac11_confirm_no_from_or_builder_taking_an_event_type() {
//     let _bad: gjallarhorn::GjallarhornEvent =
//         gjallarhorn::EventType::AnomalySurfaced.into(); // expected: E0277
// }
// ```
// ---------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------
// AC-11's mechanical scan half (EventType appears in no public input
// parameter position anywhere in the crate) is a source-scan concern for
// the mechanical posture harness (`rust_gjallarhorn_harness.py`, out of
// scope for this Rust suite per the delegating prompt), not expressible as
// a passing Rust test in this file. The positive half above (obtaining an
// event only through a minting function) and the compile-fail blocks above
// together evidence the behavioural half from this crate's own external
// public surface.
// ---------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------
// AC-22 (REQ-22): raise's recorder and delivery parameters are plain &mut
// impl, never Option. The positive half is exercised for real below; the
// compile-fail half (calling raise without a recorder does not compile) is
// a commented-out block, on the same convention as above.
// ---------------------------------------------------------------------------------

#[test]
fn ac22_raise_is_callable_from_the_public_surface_with_plain_mut_references() {
    let source = gjallarhorn::SourceProvenance::new(
        "public-surface-raiser".to_string(),
        "public-surface-origin".to_string(),
        "public-surface-class".to_string(),
        false,
    );
    let event = gjallarhorn::mint_constraint_axiom_violated(
        source,
        gjallarhorn::Severity::High,
        "audit-ref-public-surface".to_string(),
        1,
    )
    .expect("a well-formed mint through the public surface alone must succeed");

    let mut recorder = gjallarhorn::MinimalEventRecorder::new();
    let mut protected = gjallarhorn::ProtectedChannel::new();
    let mut triage = gjallarhorn::TriageQueue::new();
    let mut delivery = gjallarhorn::InProcessDelivery::new();

    let outcome = gjallarhorn::raise(
        event,
        &mut recorder,
        &mut protected,
        &mut triage,
        &mut delivery,
    );
    assert!(
        outcome.is_ok(),
        "AC-22: raise called through the public surface alone, with an honest recorder \
         and honest delivery, must succeed; got {outcome:?}"
    );
}

// To confirm AC-22's compile-fail half by hand once the crate exists:
// uncomment the block below, run `cargo build -p gjallarhorn --tests`,
// capture rustc's exact diagnostic (expected E0061, incorrect number of
// function arguments, since there is no overload of raise omitting the
// recorder), and record it verbatim in the pull request. Leave commented
// in the committed file.
//
// ```rust,ignore
// fn _ac22_confirm_raise_cannot_be_called_without_a_recorder() {
//     let source = gjallarhorn::SourceProvenance::new(
//         "raiser".to_string(),
//         "origin".to_string(),
//         "class".to_string(),
//         false,
//     );
//     let event = gjallarhorn::mint_constraint_axiom_violated(
//         source,
//         gjallarhorn::Severity::High,
//         "audit-ref".to_string(),
//         1,
//     )
//     .unwrap();
//     let mut protected = gjallarhorn::ProtectedChannel::new();
//     let mut triage = gjallarhorn::TriageQueue::new();
//     let mut delivery = gjallarhorn::InProcessDelivery::new();
//     let _bad = gjallarhorn::raise(event, &mut protected, &mut triage, &mut delivery);
//     // expected: E0061, this function takes 5 arguments but 4 were supplied
// }
// ```

// ---------------------------------------------------------------------------------
// AC-36 (REQ-36): the Delivery trait declares exactly one method, and it
// is reachable and implementable from outside the crate.
// ---------------------------------------------------------------------------------

use gjallarhorn::Delivery as _;

struct ExternalProbeDelivery {
    delivered: Vec<(gjallarhorn::GjallarhornEvent, gjallarhorn::Route)>,
}

impl gjallarhorn::Delivery for ExternalProbeDelivery {
    fn deliver(
        &mut self,
        event: &gjallarhorn::GjallarhornEvent,
        route: gjallarhorn::Route,
    ) -> Result<(), String> {
        self.delivered.push((event.clone(), route));
        Ok(())
    }
}

#[test]
fn ac36_delivery_trait_is_implementable_from_outside_the_crate_with_exactly_one_method() {
    let source = gjallarhorn::SourceProvenance::new(
        "raiser".to_string(),
        "origin".to_string(),
        "class".to_string(),
        false,
    );
    let event = gjallarhorn::mint_anomaly_surfaced(
        source,
        gjallarhorn::Severity::Informational,
        "audit-ref".to_string(),
        1,
    )
    .expect("mint must succeed");

    let mut probe = ExternalProbeDelivery {
        delivered: Vec::new(),
    };
    probe
        .deliver(&event, gjallarhorn::Route::LogOnly)
        .expect("the probe implementation's own deliver must succeed");
    assert_eq!(probe.delivered.len(), 1);
}

// ---------------------------------------------------------------------------------
// AC-37 (REQ-37): InProcessDelivery retains three events delivered on three
// differing routes, in delivery order, and its own doc comment states
// plainly that no operator receives anything (the doc-comment half is a
// source-scan concern, asserted in the crate's own unit_tests instead;
// this file exercises the retaining behaviour from the public surface).
// ---------------------------------------------------------------------------------

#[test]
fn ac37_in_process_delivery_retains_three_events_on_three_routes_in_delivery_order() {
    let mut delivery = gjallarhorn::InProcessDelivery::new();
    let source = gjallarhorn::SourceProvenance::new(
        "raiser".to_string(),
        "origin".to_string(),
        "class".to_string(),
        false,
    );

    let event_a = gjallarhorn::mint_instruction_pattern_at_boundary(
        source.clone(),
        gjallarhorn::Severity::Informational,
        "audit-ref-a".to_string(),
        1,
    )
    .expect("mint must succeed");
    let event_b = gjallarhorn::mint_attempt_introspection_or_canary_fire(
        source.clone(),
        gjallarhorn::Severity::Critical,
        "audit-ref-b".to_string(),
        2,
    )
    .expect("mint must succeed");
    let event_c = gjallarhorn::mint_audit_log_integrity_failure(
        source,
        gjallarhorn::Severity::Critical,
        "audit-ref-c".to_string(),
        3,
    )
    .expect("mint must succeed");

    delivery
        .deliver(&event_a, gjallarhorn::Route::LogOnly)
        .expect("deliver must succeed");
    delivery
        .deliver(&event_b, gjallarhorn::Route::HaltAgent)
        .expect("deliver must succeed");
    delivery
        .deliver(&event_c, gjallarhorn::Route::HaltSystem)
        .expect("deliver must succeed");

    let delivered = delivery.delivered();
    assert_eq!(delivered.len(), 3, "AC-37: all three deliveries must be retained");
    assert_eq!(delivered[0], (event_a, gjallarhorn::Route::LogOnly));
    assert_eq!(delivered[1], (event_b, gjallarhorn::Route::HaltAgent));
    assert_eq!(delivered[2], (event_c, gjallarhorn::Route::HaltSystem));
}

// ---------------------------------------------------------------------------------
// AC-53 (REQ-53): tests/public_surface.rs obtains a GjallarhornEvent only
// through one of the eight minting functions, and cannot construct one
// directly, set its event type, or reach any private field. The positive
// half is exercised throughout this file already (every event above was
// obtained through a mint_* function); the compile-fail half is the same
// set of commented-out blocks AC-10 and AC-11 already document, restated
// here for completeness per the spec's own file-plan mapping (section 8
// file 17 lists AC-53 against this same file).
//
// To confirm by hand once the crate exists: uncomment ONE block below at a
// time, run `cargo build -p gjallarhorn --tests`, capture rustc's exact
// diagnostic, and record it verbatim in the pull request. Leave every
// block commented in the committed file.
//
// ```rust,ignore
// // (a) Direct struct literal. Expected: E0423 or E0616.
// fn _ac53_confirm_no_direct_struct_literal() {
//     let _bad = gjallarhorn::GjallarhornEvent {
//         event_type: gjallarhorn::EventType::AnomalySurfaced,
//     };
// }
//
// // (b) A call to GjallarhornEvent::new. Expected: E0603 or E0599.
// fn _ac53_confirm_new_is_unreachable() {
//     let source = gjallarhorn::SourceProvenance::new(
//         "raiser".to_string(),
//         "origin".to_string(),
//         "class".to_string(),
//         false,
//     );
//     let _bad = gjallarhorn::GjallarhornEvent::new(
//         gjallarhorn::EventType::AnomalySurfaced,
//         source,
//         gjallarhorn::Severity::Elevated,
//         "forged-key".to_string(),
//         "audit-ref".to_string(),
//         1,
//     );
// }
//
// // (c) A private-field read. Expected: E0616.
// fn _ac53_confirm_private_field_read() {
//     let source = gjallarhorn::SourceProvenance::new(
//         "raiser".to_string(),
//         "origin".to_string(),
//         "class".to_string(),
//         false,
//     );
//     let event = gjallarhorn::mint_anomaly_surfaced(
//         source,
//         gjallarhorn::Severity::Elevated,
//         "audit-ref".to_string(),
//         1,
//     )
//     .unwrap();
//     let _bad = event.correlation_key; // field, not the accessor method; expected E0616
// }
// ```
// ---------------------------------------------------------------------------------
