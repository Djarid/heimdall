// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! Aggregation and its purity (REQ-32 to REQ-35; AC-32 to AC-35). Written
//! from `.opencode/plans/gjallarhorn-build-spec.md` alone, with no sight of
//! the implementation.
//!
//! Includes AC-32's 10000-event storm, run as a real 10000-event test, not
//! a scaled-down proxy, per the spec's own build-order instruction (section
//! 14.3 step 8: refusals must be shown to refuse BEFORE the happy-path
//! storm is written, so the suite cannot demonstrate a collapse that is
//! really a hole; this file states both refusal tests before the storm
//! test in file order for the same reason, though `cargo test`'s own
//! ordering is not guaranteed).
//!
//! THIS FILE WILL FAIL TO COMPILE until `crate::aggregate::{Incident,
//! AggregateRefusal, aggregate, correlation_key_for}` and `crate::mint::*`
//! all exist. That is expected and correct at this stage.
//!
//! Wired into the crate by `lib.rs`'s
//! `#[cfg(test)] #[path = "../unit_tests/aggregation.rs"] mod aggregation;`
//! declaration (REQ-52).

use crate::aggregate::{AggregateRefusal, aggregate};
use crate::channel::{ProtectedChannel, TriageQueue};
use crate::mint::mint_anomaly_surfaced;
use crate::record::{EventRecorder, MinimalEventRecorder};
use crate::types::{GjallarhornEvent, Severity, SourceProvenance};

fn source(origin_id: &str) -> SourceProvenance {
    SourceProvenance::new(
        "raiser".to_string(),
        origin_id.to_string(),
        "class".to_string(),
        false,
    )
}

// ---------------------------------------------------------------------------------
// AC-33 (REQ-33), EC-14: aggregate over an empty slice must REFUSE with
// EmptyEventSet, never return an Incident with a count of zero. Written
// before the happy-path storm test, per the build-order discipline noted
// in this file's own header.
// ---------------------------------------------------------------------------------

#[test]
fn ac33_aggregate_over_an_empty_slice_refuses_with_empty_event_set() {
    let events: Vec<GjallarhornEvent> = Vec::new();
    let outcome = aggregate(&events);
    assert_eq!(
        outcome,
        Err(AggregateRefusal::EmptyEventSet),
        "AC-33/EC-14: aggregate over an empty slice must return \
         Err(AggregateRefusal::EmptyEventSet), never an Incident with a count of zero"
    );
}

// ---------------------------------------------------------------------------------
// AC-34 (REQ-34), EC-15: aggregate over events with differing correlation
// keys must REFUSE with MixedCorrelationKeys carrying both keys, and no
// Incident is produced.
// ---------------------------------------------------------------------------------

#[test]
fn ac34_aggregate_over_differing_correlation_keys_refuses_with_mixed_correlation_keys() {
    let event_a = mint_anomaly_surfaced(
        source("origin-a"),
        Severity::Informational,
        "audit-ref-a".to_string(),
        1,
    )
    .expect("mint must succeed");
    let event_b = mint_anomaly_surfaced(
        source("origin-b"),
        Severity::Informational,
        "audit-ref-b".to_string(),
        2,
    )
    .expect("mint must succeed");
    assert_ne!(
        event_a.correlation_key(),
        event_b.correlation_key(),
        "test setup: the two fixture events must have differing correlation keys \
         (differing origin id) for this test to exercise EC-15 at all"
    );

    let events = vec![event_a.clone(), event_b.clone()];
    let outcome = aggregate(&events);
    match outcome {
        Err(AggregateRefusal::MixedCorrelationKeys { found }) => {
            assert!(
                found.contains(&event_a.correlation_key().to_string()),
                "AC-34/EC-15: the refusal must carry event_a's own correlation key; got \
                 {found:?}"
            );
            assert!(
                found.contains(&event_b.correlation_key().to_string()),
                "AC-34/EC-15: the refusal must carry event_b's own correlation key; got \
                 {found:?}"
            );
        }
        other => panic!(
            "AC-34/EC-15: aggregate over events with differing correlation keys must \
             return Err(AggregateRefusal::MixedCorrelationKeys {{ .. }}); got {other:?}"
        ),
    }
}

// ---------------------------------------------------------------------------------
// AC-32 (REQ-32): a 10000-event storm from one source, with severities
// spanning the full range and arrival ordinals from 100 to 10099, collapses
// into one Incident whose event_count() is 10000, whose window() is
// (100, 10099), whose highest_severity() is Critical (by ordinal
// comparison, not most recent), whose correlation_key() equals every
// input event's own key, and whose contained_instances() carries each
// distinct origin identifier once.
// ---------------------------------------------------------------------------------

#[test]
fn ac32_a_10000_event_storm_collapses_into_one_incident_with_correct_count_window_and_severity() {
    let severities = [
        Severity::Informational,
        Severity::Elevated,
        Severity::High,
        Severity::Critical,
    ];
    let mut events: Vec<GjallarhornEvent> = Vec::with_capacity(10000);
    for i in 0..10000u64 {
        let ordinal = 100 + i;
        let severity = severities[(i % 4) as usize];
        // The LAST event in the storm (i = 9999) deliberately carries
        // Severity::Informational (9999 % 4 == 3, so severities[3] is
        // Critical -- adjusted below to guarantee the "not most recent"
        // half of AC-32 is genuinely exercised regardless of 10000's own
        // modular arithmetic).
        let severity = if i == 9999 {
            Severity::Informational
        } else {
            severity
        };
        let event = mint_anomaly_surfaced(
            source("shared-origin"),
            severity,
            format!("audit-ref-{i}"),
            ordinal,
        )
        .expect("mint must succeed");
        events.push(event);
    }
    // Force at least one Critical event to exist somewhere in the middle
    // of the storm, not at the end, so "highest by ordinal comparison, not
    // most recent" is unambiguously exercised: overwrite index 5000's
    // severity to Critical via a fresh mint at the same ordinal position.
    events[5000] = mint_anomaly_surfaced(
        source("shared-origin"),
        Severity::Critical,
        "audit-ref-5000-critical".to_string(),
        100 + 5000,
    )
    .expect("mint must succeed");

    let incident = aggregate(&events).unwrap_or_else(|e| {
        panic!("AC-32: a 10000-event storm sharing one correlation key must aggregate \
                successfully; got Err({e:?})")
    });

    assert_eq!(
        incident.event_count(),
        10000,
        "AC-32: event_count() must equal the number of input events"
    );
    assert_eq!(
        incident.window(),
        (100, 10099),
        "AC-32: window() must be (lowest, highest) over the arrival ordinals actually \
         seen"
    );
    assert_eq!(
        incident.highest_severity(),
        Severity::Critical,
        "AC-32: highest_severity() must be the highest severity BY ORDINAL COMPARISON \
         seen anywhere in the storm, not the most recent event's own severity (the last \
         event in this storm is deliberately Informational)"
    );
    assert_eq!(
        incident.correlation_key(),
        events[0].correlation_key(),
        "AC-32: the incident's correlation_key() must equal every input event's own key"
    );
    assert_eq!(
        incident.contained_instances(),
        &["shared-origin".to_string()],
        "AC-32: contained_instances() must carry each distinct origin identifier once; \
         every event in this storm shares the one origin identifier \"shared-origin\", \
         so exactly one instance must be reported, not 10000 duplicates"
    );
}

#[test]
fn ac32_aggregate_signature_takes_a_shared_slice_and_nothing_else() {
    // A function-pointer coercion pinning the exact signature (REQ-32,
    // REQ-35): this compiles only if aggregate is EXACTLY
    // fn(&[GjallarhornEvent]) -> Result<Incident, AggregateRefusal>, with
    // no mutable reference to any channel, queue or recorder anywhere in
    // its parameter list.
    let _signature: fn(&[GjallarhornEvent]) -> Result<crate::aggregate::Incident, AggregateRefusal> =
        aggregate;
}

// ---------------------------------------------------------------------------------
// AC-35 (REQ-35): aggregate never suppresses or alters what raise already
// did. A ProtectedChannel and a TriageQueue each holding events, and a
// MinimalEventRecorder holding written records: calling aggregate over
// those events leaves entries(), ordered() and records() all
// byte-identical before and after. aggregate's signature is structurally
// incapable of holding a mutable reference to any of the three (asserted
// above by ac32_aggregate_signature_takes_a_shared_slice_and_nothing_else).
// ---------------------------------------------------------------------------------

#[test]
fn ac35_aggregate_leaves_channel_queue_and_recorder_byte_identical_before_and_after() {
    let mut protected = ProtectedChannel::new();
    let mut triage = TriageQueue::new();
    let mut recorder = MinimalEventRecorder::new();

    let protected_event = mint_anomaly_surfaced(
        source("protected-origin"),
        Severity::High,
        "audit-ref-protected".to_string(),
        1,
    )
    .expect("mint must succeed");
    let triage_event = mint_anomaly_surfaced(
        source("triage-origin"),
        Severity::Elevated,
        "audit-ref-triage".to_string(),
        2,
    )
    .expect("mint must succeed");

    protected.admit(protected_event.clone());
    triage.admit(triage_event.clone());
    recorder
        .record_event(&protected_event)
        .expect("an honest recorder's write must succeed");
    recorder
        .record_event(&triage_event)
        .expect("an honest recorder's write must succeed");

    let before_protected: Vec<GjallarhornEvent> = protected.entries().to_vec();
    let before_triage: Vec<GjallarhornEvent> = triage.ordered().into_iter().cloned().collect();
    let before_records: Vec<GjallarhornEvent> = recorder.records().to_vec();

    let events_to_aggregate = vec![
        mint_anomaly_surfaced(
            source("aggregate-origin"),
            Severity::Critical,
            "audit-ref-aggregate".to_string(),
            3,
        )
        .expect("mint must succeed"),
    ];
    let _ = aggregate(&events_to_aggregate);

    assert_eq!(
        protected.entries().to_vec(),
        before_protected,
        "AC-35/REQ-35: the protected channel's entries() must be byte-identical before \
         and after a call to aggregate"
    );
    let after_triage: Vec<GjallarhornEvent> = triage.ordered().into_iter().cloned().collect();
    assert_eq!(
        after_triage, before_triage,
        "AC-35/REQ-35: the triage queue's ordered() must be byte-identical before and \
         after a call to aggregate"
    );
    assert_eq!(
        recorder.records().to_vec(),
        before_records,
        "AC-35/REQ-35: the recorder's records() must be byte-identical before and after \
         a call to aggregate"
    );
}
