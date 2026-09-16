// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The event recorder, write-before-route, and `raise`'s fail-closed
//! sequencing (OR-8, REQ-19 to REQ-23, REQ-38; AC-19 to AC-23, AC-38).
//! Written from `.opencode/plans/gjallarhorn-build-spec.md` alone, with no
//! sight of the implementation.
//!
//! **AC-21 is this spec's own headline case** ("the single most important
//! test in the suite for OR-8") **and is its own named test function below,
//! `ac21_a_recorder_that_always_fails_prevents_routing_admission_and_delivery`,
//! not folded into any other case.**
//!
//! THIS FILE WILL FAIL TO COMPILE until `crate::record::{EventRecorder,
//! MinimalEventRecorder}`, `crate::delivery::{Delivery, InProcessDelivery}`,
//! `crate::channel::{ProtectedChannel, TriageQueue}` and
//! `crate::raise::{raise, RaiseOutcome, RaiseRefusal}` all exist. That is
//! expected and correct at this stage.
//!
//! Wired into the crate by `lib.rs`'s
//! `#[cfg(test)] #[path = "../unit_tests/raise_failclosed.rs"] mod raise_failclosed;`
//! declaration (REQ-52).

use crate::channel::{ProtectedChannel, TriageQueue};
use crate::delivery::{Delivery, InProcessDelivery};
use crate::mint::mint_constraint_axiom_violated;
use crate::raise::{RaiseRefusal, raise};
use crate::record::{EventRecorder, MinimalEventRecorder};
use crate::types::{GjallarhornEvent, Severity, SourceProvenance};

fn valid_provenance() -> SourceProvenance {
    SourceProvenance::new(
        "himinbjorg-validation".to_string(),
        "task-fixture-1".to_string(),
        "engine".to_string(),
        false,
    )
}

fn valid_event() -> GjallarhornEvent {
    mint_constraint_axiom_violated(
        valid_provenance(),
        Severity::High,
        "audit-ref-fixture".to_string(),
        7,
    )
    .expect("a well-formed fixture mint must succeed")
}

/// A recorder whose write ALWAYS fails, retaining nothing. The positive
/// control against which AC-21's four downstream effects are checked.
struct AlwaysFailingRecorder;

impl EventRecorder for AlwaysFailingRecorder {
    fn record_event(&mut self, _event: &GjallarhornEvent) -> Result<(), String> {
        Err("fixture: this recorder always fails, by design".to_string())
    }
}

/// A delivery implementation whose `deliver` ALWAYS fails. Used by AC-38.
struct AlwaysFailingDelivery;

impl Delivery for AlwaysFailingDelivery {
    fn deliver(
        &mut self,
        _event: &GjallarhornEvent,
        _route: crate::types::Route,
    ) -> Result<(), String> {
        Err("fixture: this delivery always fails, by design".to_string())
    }
}

// ---------------------------------------------------------------------------------
// AC-19 (REQ-19): EventRecorder declares exactly one method, and it is
// Gjallarhorn's own trait rather than a reuse of himinbjorg::DecisionRecorder.
// ---------------------------------------------------------------------------------

#[test]
fn ac19_event_recorder_trait_declares_exactly_one_method_signature() {
    // A generic function bound only by EventRecorder's one method,
    // record_event(&mut self, &GjallarhornEvent) -> Result<(), String>.
    // This compiles only if that method exists with that exact signature;
    // it does not prove no OTHER method exists (that half is a source-scan
    // concern for the mechanical posture harness), but it does pin this
    // trait's shape structurally.
    fn _uses_the_one_method<R: EventRecorder>(recorder: &mut R, event: &GjallarhornEvent) {
        let _: Result<(), String> = recorder.record_event(event);
    }
    let _ = _uses_the_one_method::<MinimalEventRecorder>;
}

#[test]
fn ac19_crate_source_does_not_mention_himinbjorg() {
    let src_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src");
    let entries = std::fs::read_dir(&src_dir).unwrap_or_else(|e| {
        panic!("expected crates/gjallarhorn/src/ to exist once this build lands: {e}")
    });
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) == Some("rs") {
            let content = std::fs::read_to_string(&path)
                .unwrap_or_else(|e| panic!("failed to read {path:?}: {e}"));
            assert!(
                !content.contains("himinbjorg"),
                "AC-19/REQ-19: {path:?} must not mention himinbjorg anywhere: \
                 EventRecorder is Gjallarhorn's OWN trait, not a reuse of \
                 himinbjorg::DecisionRecorder, so the crate's [dependencies] table \
                 stays empty (REQ-2)"
            );
        }
    }
}

// ---------------------------------------------------------------------------------
// AC-20 (REQ-20): MinimalEventRecorder is append only. Three writes in turn
// return all three in write order via records(), and no mutating method
// exists (grep-checked here as a source scan over the type's own file, on
// AC-19's precedent above).
// ---------------------------------------------------------------------------------

#[test]
fn ac20_minimal_event_recorder_returns_all_writes_in_write_order() {
    let mut recorder = MinimalEventRecorder::new();
    let event_a = mint_constraint_axiom_violated(
        valid_provenance(),
        Severity::Informational,
        "audit-a".to_string(),
        1,
    )
    .expect("mint must succeed");
    let event_b = mint_constraint_axiom_violated(
        valid_provenance(),
        Severity::Elevated,
        "audit-b".to_string(),
        2,
    )
    .expect("mint must succeed");
    let event_c = mint_constraint_axiom_violated(
        valid_provenance(),
        Severity::Critical,
        "audit-c".to_string(),
        3,
    )
    .expect("mint must succeed");

    recorder
        .record_event(&event_a)
        .expect("AC-20: an honest recorder's write must succeed");
    recorder
        .record_event(&event_b)
        .expect("AC-20: an honest recorder's write must succeed");
    recorder
        .record_event(&event_c)
        .expect("AC-20: an honest recorder's write must succeed");

    let records = recorder.records();
    assert_eq!(records.len(), 3, "AC-20: three writes must yield three records");
    assert_eq!(records[0], event_a);
    assert_eq!(records[1], event_b);
    assert_eq!(records[2], event_c);
}

#[test]
fn ac20_no_mutating_method_exists_on_minimal_event_recorder_in_source() {
    let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("src")
        .join("record.rs");
    let src = std::fs::read_to_string(&path).unwrap_or_else(|e| {
        panic!("expected crates/gjallarhorn/src/record.rs to exist once this build lands: {e}")
    });
    for forbidden in [
        "remove", "clear", "truncate", "drain", "retain", "pop", "insert", "sort", "swap",
    ] {
        assert!(
            !src.contains(forbidden),
            "AC-20/REQ-20: record.rs must contain no {forbidden:?}: no method on \
             MinimalEventRecorder may update, remove, clear, truncate, drain, retain, \
             pop, insert, sort or swap an already-appended entry"
        );
    }
    assert!(
        !src.contains("records_mut"),
        "AC-20/REQ-20: record.rs must define no records_mut or equivalent mutable \
         accessor"
    );
}

// ---------------------------------------------------------------------------------
// AC-21 (REQ-21), OR-8's own criterion, THE HEADLINE CASE of this whole
// suite. A recorder whose record_event always returns Err: raise must
// return Err(RaiseRefusal::RecordWrite(..)), and each of the four
// downstream effects must be individually unaffected: the protected
// channel's length unchanged, the triage queue's length unchanged, and the
// delivery implementation's delivered() empty. Not folded into any other
// test (per the spec's own explicit instruction).
// ---------------------------------------------------------------------------------

#[test]
fn ac21_a_recorder_that_always_fails_prevents_routing_admission_and_delivery() {
    let mut recorder = AlwaysFailingRecorder;
    let mut protected = ProtectedChannel::new();
    let mut triage = TriageQueue::new();
    let mut delivery = InProcessDelivery::new();

    let outcome = raise(
        valid_event(),
        &mut recorder,
        &mut protected,
        &mut triage,
        &mut delivery,
    );

    match outcome {
        Err(RaiseRefusal::RecordWrite(_)) => {}
        other => panic!(
            "AC-21: a raise over a recorder whose write always fails must return \
             Err(RaiseRefusal::RecordWrite(..)); got {other:?}"
        ),
    }

    assert_eq!(
        protected.len(),
        0,
        "AC-21: the protected channel's length must be unchanged (0) when the record \
         write fails: the route was never taken and nothing was ever admitted"
    );
    assert_eq!(
        triage.len(),
        0,
        "AC-21: the triage queue's length must be unchanged (0) when the record write \
         fails: the route was never taken and nothing was ever admitted"
    );
    assert!(
        delivery.delivered().is_empty(),
        "AC-21: the delivery implementation's delivered() must be empty when the \
         record write fails: nothing was ever delivered"
    );
}

// ---------------------------------------------------------------------------------
// AC-22 (REQ-22): raise's signature takes recorder and delivery as plain
// `&mut impl` parameters, neither of which is an Option. Asserted here by
// the fact that AC-21 above calls raise with plain &mut references and no
// Option wrapper anywhere; the compile-boundary half (a tests/ integration
// test attempting to call raise without a recorder is a compile error)
// lives in tests/public_surface.rs per the spec's own file plan.
// ---------------------------------------------------------------------------------

#[test]
fn ac22_raise_is_called_with_plain_mut_references_never_an_option() {
    // This test's own body, and AC-21's above, already demonstrate the
    // positive half: raise(event, &mut recorder, &mut protected, &mut
    // triage, &mut delivery) with no Option wrapper anywhere compiles and
    // runs. The stronger claim (there is NO code path through raise that
    // omits a recorder) is the compile-boundary confirmation in
    // tests/public_surface.rs.
    let mut recorder = MinimalEventRecorder::new();
    let mut protected = ProtectedChannel::new();
    let mut triage = TriageQueue::new();
    let mut delivery = InProcessDelivery::new();

    let _ = raise(
        valid_event(),
        &mut recorder,
        &mut protected,
        &mut triage,
        &mut delivery,
    );
}

// ---------------------------------------------------------------------------------
// AC-23 (REQ-23): raise carries #[must_use] (asserted structurally by a
// source scan here; the clippy-warning-under--D-warnings half is a
// workspace-level V-2 concern, not this file's); RaiseRefusal's
// RecordWrite and Delivery are distinct variants; RaiseOutcome carries the
// route and the admission and no boolean field readable as "delivered".
// ---------------------------------------------------------------------------------

#[test]
fn ac23_raise_source_carries_must_use_attribute() {
    let path = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("src")
        .join("raise.rs");
    let src = std::fs::read_to_string(&path).unwrap_or_else(|e| {
        panic!("expected crates/gjallarhorn/src/raise.rs to exist once this build lands: {e}")
    });
    assert!(
        src.contains("#[must_use]"),
        "AC-23/REQ-23: raise.rs must carry a #[must_use] attribute on the raise \
         function, so a caller cannot silently discard a refusal"
    );
}

#[test]
fn ac23_raise_refusal_record_write_and_delivery_are_distinct_variants() {
    let record_write = RaiseRefusal::RecordWrite("probe".to_string());
    let delivery = RaiseRefusal::Delivery("probe".to_string());
    assert_ne!(
        format!("{record_write:?}"),
        format!("{delivery:?}"),
        "AC-23/REQ-23: RaiseRefusal::RecordWrite and RaiseRefusal::Delivery must be \
         distinct variants: a record-write failure means nothing happened at all, and a \
         delivery failure means the event IS recorded and IS admitted"
    );
}

#[test]
fn ac23_raise_outcome_carries_route_and_admission_and_no_delivered_boolean() {
    let mut recorder = MinimalEventRecorder::new();
    let mut protected = ProtectedChannel::new();
    let mut triage = TriageQueue::new();
    let mut delivery = InProcessDelivery::new();

    let outcome = raise(
        valid_event(),
        &mut recorder,
        &mut protected,
        &mut triage,
        &mut delivery,
    )
    .expect("AC-23: an honest recorder and honest delivery must let raise succeed");

    // Reachable accessors: route() and admission(). If a third,
    // boolean-typed accessor readable as "delivered" existed, this test
    // would not detect its absence directly, but the struct's own field
    // list (asserted via Debug formatting containing only "route" and
    // "admission"-shaped content) gives a weak additional signal.
    let _route = outcome.route();
    let _admission = outcome.admission();
    let debug = format!("{outcome:?}");
    assert!(
        !debug.to_lowercase().contains("delivered"),
        "AC-23/REQ-23: RaiseOutcome must carry no boolean field readable as \
         \"delivered\" independently of its variant or field; found a field named \
         \"delivered\" in its Debug output: {debug}"
    );
}

// ---------------------------------------------------------------------------------
// AC-38 (REQ-38), EC-7: a delivery implementation whose deliver always
// fails, with an honest recorder: raise returns
// Err(RaiseRefusal::Delivery(..)); the recorder's records() contains the
// event; the event is present in exactly one of the two structures, per
// its admission. A delivery failure retracts neither the record nor the
// admission.
// ---------------------------------------------------------------------------------

#[test]
fn ac38_a_delivery_that_always_fails_does_not_retract_the_record_or_the_admission() {
    let mut recorder = MinimalEventRecorder::new();
    let mut protected = ProtectedChannel::new();
    let mut triage = TriageQueue::new();
    let mut delivery = AlwaysFailingDelivery;

    let event = valid_event();
    let outcome = raise(
        event.clone(),
        &mut recorder,
        &mut protected,
        &mut triage,
        &mut delivery,
    );

    match outcome {
        Err(RaiseRefusal::Delivery(_)) => {}
        other => panic!(
            "AC-38: a raise over a delivery that always fails, with an honest recorder, \
             must return Err(RaiseRefusal::Delivery(..)); got {other:?}"
        ),
    }

    assert!(
        recorder.records().iter().any(|recorded| *recorded == event),
        "AC-38/EC-7: the recorder's records() must contain the event: a delivery \
         failure must not retract the record"
    );

    let total_admitted = protected.len() + triage.len();
    assert_eq!(
        total_admitted,
        1,
        "AC-38/EC-7: the event must be present in exactly one of the two structures, \
         per its admission: a delivery failure must not retract the admission"
    );
}
