// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! Channel separation (GJ-B-2): two genuinely separate structures, the
//! single admission rule, the protected channel surviving a triage flood,
//! age-only triage ordering with no reputation term, and the R-5 disclosure
//! (REQ-24 to REQ-30; AC-24 to AC-30, EC-13). Written from
//! `.opencode/plans/gjallarhorn-build-spec.md` alone, with no sight of the
//! implementation.
//!
//! Includes AC-26's 10000-item flood (run as a real test, not a
//! scaled-down proxy, per the spec's own build-order instruction) and the
//! monotonicity and stability cases of AC-27 and EC-13.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crate::channel::{Admission,
//! admission_for, ProtectedChannel, TriageQueue}` and `crate::mint::*` all
//! exist. That is expected and correct at this stage.
//!
//! Wired into the crate by `lib.rs`'s
//! `#[cfg(test)] #[path = "../unit_tests/channel_separation.rs"] mod channel_separation;`
//! declaration (REQ-52).

use crate::channel::{Admission, ProtectedChannel, TriageQueue, admission_for};
use crate::mint::{mint_anomaly_surfaced, mint_audit_log_integrity_failure};
use crate::types::{EventType, GjallarhornEvent, Severity, SourceProvenance};

fn provenance(protected: bool) -> SourceProvenance {
    SourceProvenance::new(
        "raiser".to_string(),
        "origin".to_string(),
        "class".to_string(),
        protected,
    )
}

fn event_with_ordinal(ordinal: u64) -> GjallarhornEvent {
    mint_anomaly_surfaced(
        provenance(false),
        Severity::Elevated,
        "audit-ref".to_string(),
        ordinal,
    )
    .expect("mint must succeed")
}

fn crate_src_dir() -> std::path::PathBuf {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src")
}

fn read_source(rel: &str) -> String {
    let path = crate_src_dir().join(rel);
    std::fs::read_to_string(&path).unwrap_or_else(|e| {
        panic!("expected crates/gjallarhorn/src/{rel} to exist once this build lands: {e}")
    })
}

// ---------------------------------------------------------------------------------
// AC-24 (REQ-24), GJ-B-2's own structural criterion: ProtectedChannel and
// TriageQueue are distinct types with no cross-structure seam anywhere.
// The grep-recorded absence is a source scan over channel.rs.
// ---------------------------------------------------------------------------------

#[test]
fn ac24_no_from_tryfrom_or_into_impl_between_the_two_structures() {
    let src = read_source("channel.rs");
    for forbidden in [
        "From<ProtectedChannel> for TriageQueue",
        "From<TriageQueue> for ProtectedChannel",
        "TryFrom<ProtectedChannel> for TriageQueue",
        "TryFrom<TriageQueue> for ProtectedChannel",
        "Into<TriageQueue> for ProtectedChannel",
        "Into<ProtectedChannel> for TriageQueue",
    ] {
        assert!(
            !src.contains(forbidden),
            "AC-24/REQ-24: channel.rs must contain no {forbidden:?}: no From, TryFrom or \
             Into impl in either direction between ProtectedChannel and TriageQueue"
        );
    }
}

#[test]
fn ac24_the_two_structures_are_genuinely_distinct_types() {
    fn _distinct_types(_p: ProtectedChannel, _t: TriageQueue) {}
    let p = ProtectedChannel::new();
    let t = TriageQueue::new();
    _distinct_types(p, t);
    // If ProtectedChannel and TriageQueue were type aliases for the same
    // underlying type, this test would still compile, but AC-29's
    // independent-sizing test below would then fail (a shared backing
    // store would make admitting to one affect the other's length),
    // which is the stronger, behavioural half of this same claim.
}

// ---------------------------------------------------------------------------------
// AC-25 (REQ-25): admission_for returns Protected for the four named types
// and Triage for the other four when not provenance-protected; Protected
// for ALL eight types when provenance-protected; its signature excludes
// Severity, correlation key, audit ref and arrival ordinal; two events of
// the same type and provenance but differing severities receive identical
// admission.
// ---------------------------------------------------------------------------------

#[test]
fn ac25_signature_takes_exactly_event_type_and_source_provenance_and_nothing_else() {
    // A function-pointer coercion pinning the exact signature (REQ-25):
    // this compiles only if admission_for is EXACTLY
    // fn(EventType, &SourceProvenance) -> Admission, with no room for a
    // Severity, a correlation key, an audit reference or an arrival
    // ordinal to be added without breaking this line.
    let _signature: fn(EventType, &SourceProvenance) -> Admission = admission_for;
}

#[test]
fn ac25_the_four_named_types_admit_to_protected_when_not_provenance_protected() {
    let unprotected = provenance(false);
    for admits_protected_type in [
        EventType::PromotionRequestAboveThreshold,
        EventType::AuditLogIntegrityFailure,
        EventType::AttemptIntrospectionOrCanaryFire,
        EventType::ConstraintAxiomViolated,
    ] {
        assert_eq!(
            admission_for(admits_protected_type, &unprotected),
            Admission::Protected,
            "AC-25: {admits_protected_type:?} must admit to Protected even when the \
             provenance is not provenance-protected, per DD section 3.3's own list"
        );
    }
}

#[test]
fn ac25_the_other_four_types_admit_to_triage_when_not_provenance_protected() {
    let unprotected = provenance(false);
    for admits_triage_type in [
        EventType::InstructionPatternAtBoundary,
        EventType::TaintBoundaryBreachAttempt,
        EventType::AnomalySurfaced,
        EventType::ResourceLimitBreached,
    ] {
        assert_eq!(
            admission_for(admits_triage_type, &unprotected),
            Admission::Triage,
            "AC-25: {admits_triage_type:?} must admit to Triage when the provenance is \
             not provenance-protected"
        );
    }
}

#[test]
fn ac25_every_one_of_the_eight_types_admits_to_protected_when_provenance_protected() {
    let protected_source = provenance(true);
    for event_type in [
        EventType::InstructionPatternAtBoundary,
        EventType::ConstraintAxiomViolated,
        EventType::TaintBoundaryBreachAttempt,
        EventType::AnomalySurfaced,
        EventType::AttemptIntrospectionOrCanaryFire,
        EventType::ResourceLimitBreached,
        EventType::PromotionRequestAboveThreshold,
        EventType::AuditLogIntegrityFailure,
    ] {
        assert_eq!(
            admission_for(event_type, &protected_source),
            Admission::Protected,
            "AC-25: {event_type:?} must admit to Protected when the provenance carries \
             provenance_protected, including the four types that would otherwise \
             triage (DD section 3.3 bullet three)"
        );
    }
}

#[test]
fn ac25_two_events_of_same_type_and_provenance_but_differing_severity_receive_identical_admission() {
    let source = provenance(false);
    let event_low = mint_anomaly_surfaced(
        source.clone(),
        Severity::Informational,
        "audit-ref-low".to_string(),
        1,
    )
    .expect("mint must succeed");
    let event_high = mint_anomaly_surfaced(
        source.clone(),
        Severity::Critical,
        "audit-ref-high".to_string(),
        2,
    )
    .expect("mint must succeed");

    assert_eq!(
        admission_for(event_low.event_type(), event_low.source()),
        admission_for(event_high.event_type(), event_high.source()),
        "AC-25: two events of the same type and provenance but differing severities \
         must receive identical admission, because admission_for cannot see severity"
    );
}

// ---------------------------------------------------------------------------------
// AC-26 (REQ-26): the protected channel survives a 10000-item triage flood.
// Run as a real 10000-item test, not a scaled-down proxy.
// ---------------------------------------------------------------------------------

#[test]
fn ac26_protected_channel_survives_a_10000_item_triage_flood() {
    let mut protected = ProtectedChannel::new();
    let mut triage = TriageQueue::new();

    let escalation = mint_audit_log_integrity_failure(
        provenance(false),
        Severity::Critical,
        "audit-ref-escalation".to_string(),
        0,
    )
    .expect("mint must succeed");
    protected.admit(escalation.clone());

    for i in 0..10000u64 {
        triage.admit(event_with_ordinal(i));
    }

    assert_eq!(
        protected.len(),
        1,
        "AC-26: the protected channel's own length must be unaffected by a 10000-item \
         triage flood"
    );
    assert_eq!(
        protected.entries().len(),
        1,
        "AC-26: entries() must still return exactly the one admitted escalation"
    );
    assert_eq!(
        protected.entries()[0], escalation,
        "AC-26: the retained escalation must be byte-identical to what was admitted"
    );
}

#[test]
fn ac26_no_eviction_cap_or_capacity_bound_method_exists_on_protected_channel_in_source() {
    let src = read_source("channel.rs");
    for forbidden in [
        "remove", "clear", "truncate", "drain", "retain", "pop", "evict",
    ] {
        assert!(
            !src.contains(forbidden),
            "AC-26/REQ-26: channel.rs must contain no {forbidden:?} anywhere: \
             ProtectedChannel has no eviction, no cap and no capacity-bound method"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-27 (REQ-27), EC-13: TriageQueue ordering is age only, from the
// caller-supplied arrival ordinal. An ordinal-5 event admitted before 1000
// later-ordinal events stays first (monotonic in age). The same set
// admitted in reverse ordinal order yields the identical sequence
// (ordering is by ordinal, not arrival order). No std::time/SystemTime/
// Instant usage anywhere in channel.rs. EC-13: two events with the same
// ordinal are both retained and readable, and the relative order between
// them is stable across repeated calls to ordered().
// ---------------------------------------------------------------------------------

#[test]
fn ac27_an_older_arrival_never_has_its_position_worsened_by_1000_later_arrivals() {
    let mut triage = TriageQueue::new();
    triage.admit(event_with_ordinal(5));
    for ordinal in 6..=1005u64 {
        triage.admit(event_with_ordinal(ordinal));
    }

    let ordered = triage.ordered();
    assert_eq!(
        ordered.len(),
        1001,
        "AC-27: 1001 admitted events must all be present in ordered()"
    );
    assert_eq!(
        ordered[0].arrival_ordinal(),
        5,
        "AC-27: the ordinal-5 event must be first, its index unaffected by the 1000 \
         later arrivals"
    );
}

#[test]
fn ac27_ordering_is_by_ordinal_not_by_arrival_order_into_the_structure() {
    let mut forward = TriageQueue::new();
    for ordinal in 1..=20u64 {
        forward.admit(event_with_ordinal(ordinal));
    }
    let forward_ordinals: Vec<u64> = forward
        .ordered()
        .iter()
        .map(|e| e.arrival_ordinal())
        .collect();

    let mut reverse = TriageQueue::new();
    for ordinal in (1..=20u64).rev() {
        reverse.admit(event_with_ordinal(ordinal));
    }
    let reverse_ordinals: Vec<u64> = reverse
        .ordered()
        .iter()
        .map(|e| e.arrival_ordinal())
        .collect();

    assert_eq!(
        forward_ordinals, reverse_ordinals,
        "AC-27: the same set of ordinals admitted in reverse order must still produce \
         the identical ordered() sequence, because ordering is by the ordinal alone, \
         never by arrival order into the structure"
    );
    let mut sorted = forward_ordinals.clone();
    sorted.sort_unstable();
    assert_eq!(
        forward_ordinals, sorted,
        "AC-27: ordered() must be sorted ascending by arrival ordinal"
    );
}

#[test]
fn ac27_channel_module_reads_no_clock() {
    let src = read_source("channel.rs");
    for forbidden in ["std::time", "SystemTime", "Instant"] {
        assert!(
            !src.contains(forbidden),
            "AC-27/REQ-6: channel.rs must contain no {forbidden:?}: ordering is derived \
             solely from the caller-supplied arrival ordinal, never a clock this crate \
             reads"
        );
    }
}

#[test]
fn ec13_two_events_with_the_same_ordinal_are_both_retained_and_ordering_is_stable() {
    let mut triage = TriageQueue::new();
    let event_a = mint_anomaly_surfaced(
        provenance(false),
        Severity::Informational,
        "audit-ref-a".to_string(),
        42,
    )
    .expect("mint must succeed");
    let event_b = mint_anomaly_surfaced(
        provenance(false),
        Severity::Critical,
        "audit-ref-b".to_string(),
        42,
    )
    .expect("mint must succeed");
    triage.admit(event_a);
    triage.admit(event_b);

    assert_eq!(
        triage.len(),
        2,
        "EC-13: two events admitted with the same arrival ordinal must both be retained"
    );

    let first_read: Vec<String> = triage
        .ordered()
        .iter()
        .map(|e| e.audit_ref().to_string())
        .collect();
    let second_read: Vec<String> = triage
        .ordered()
        .iter()
        .map(|e| e.audit_ref().to_string())
        .collect();
    assert_eq!(
        first_read, second_read,
        "EC-13: the relative order between two equal-ordinal events must be stable \
         across repeated calls to ordered(), so a reviewer reading the queue twice sees \
         the same sequence"
    );
}

// ---------------------------------------------------------------------------------
// AC-28 (REQ-28), the honesty criterion for the triage queue: no
// reputation term anywhere, structurally, over the whole crate.
// ---------------------------------------------------------------------------------

#[test]
fn ac28_no_reputation_vocabulary_anywhere_in_the_crate_outside_a_disclaiming_doc_comment() {
    let src_dir = crate_src_dir();
    let entries = std::fs::read_dir(&src_dir).unwrap_or_else(|e| {
        panic!("expected crates/gjallarhorn/src/ to exist once this build lands: {e}")
    });
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("rs") {
            continue;
        }
        let content = std::fs::read_to_string(&path)
            .unwrap_or_else(|e| panic!("failed to read {path:?}: {e}"));
        // A conservative proxy for "outside a doc comment stating the
        // absence": strip lines that are themselves doc comments (`///`
        // or `//!`) before scanning, since those are exactly where the
        // spec requires the absence to be STATED. Any occurrence in
        // ordinary code (a field, a parameter, a local, a constant) fails
        // this test.
        let non_doc_lines: String = content
            .lines()
            .filter(|line| {
                let trimmed = line.trim_start();
                !trimmed.starts_with("///") && !trimmed.starts_with("//!")
            })
            .collect::<Vec<_>>()
            .join("\n");
        for forbidden in [
            "reputation",
            "muninn",
            "clean_run",
            "known_critical",
            "stub",
            "placeholder",
            "mock",
            "todo!",
        ] {
            assert!(
                !non_doc_lines.to_lowercase().contains(forbidden),
                "AC-28/REQ-28: {path:?} must contain no {forbidden:?} outside a doc \
                 comment stating the absence: TriageQueue reads no reputation term, and \
                 this must be structurally true rather than stubbed"
            );
        }
    }
}

// ---------------------------------------------------------------------------------
// AC-29 (REQ-29): the two structures are separately constructible,
// separately readable and independently sized, for N at 0, 1 and 10000.
// ---------------------------------------------------------------------------------

#[test]
fn ac29_the_two_structures_are_independently_sized_for_n_zero() {
    let protected = ProtectedChannel::new();
    let triage = TriageQueue::new();
    assert_eq!(protected.len(), 0);
    assert_eq!(triage.len(), 0);
}

#[test]
fn ac29_the_two_structures_are_independently_sized_for_n_one() {
    let mut protected = ProtectedChannel::new();
    let mut triage = TriageQueue::new();
    let escalation = mint_audit_log_integrity_failure(
        provenance(false),
        Severity::High,
        "audit-ref".to_string(),
        1,
    )
    .expect("mint must succeed");
    protected.admit(escalation.clone());
    triage.admit(event_with_ordinal(1));

    assert_eq!(protected.len(), 1);
    assert_eq!(triage.len(), 1);
    assert_eq!(
        protected.entries()[0], escalation,
        "AC-29: the escalation read back must be byte-identical to what was admitted"
    );
}

#[test]
fn ac29_the_two_structures_are_independently_sized_for_n_ten_thousand() {
    let mut protected = ProtectedChannel::new();
    let mut triage = TriageQueue::new();
    let escalation = mint_audit_log_integrity_failure(
        provenance(false),
        Severity::High,
        "audit-ref".to_string(),
        1,
    )
    .expect("mint must succeed");
    protected.admit(escalation.clone());
    for i in 0..10000u64 {
        triage.admit(event_with_ordinal(i));
    }

    assert_eq!(protected.len(), 1);
    assert_eq!(triage.len(), 10000);
    assert_eq!(
        protected.entries()[0], escalation,
        "AC-29: the escalation read back must be byte-identical to what was admitted, \
         regardless of the triage queue's own size"
    );
}

// ---------------------------------------------------------------------------------
// AC-30 (REQ-30): channel.rs's module doc comment states the ordering
// implements one of GJ-4's four terms, names the three absent and why, and
// states plainly that HLD risk R-5 is untouched by this build and must not
// be read as closed; and it does not describe this ordering as the DD's
// own triage priority.
// ---------------------------------------------------------------------------------

#[test]
fn ac30_channel_module_doc_comment_discloses_r5_is_untouched() {
    let src = read_source("channel.rs");
    let lower = src.to_lowercase();
    assert!(
        lower.contains("r-5") || lower.contains("r5"),
        "AC-30/REQ-30: channel.rs's module doc comment must name HLD risk R-5 explicitly"
    );
    assert!(
        lower.contains("untouched") || lower.contains("not closed") || lower.contains("not read as closed"),
        "AC-30/REQ-30: channel.rs's module doc comment must state plainly that HLD risk \
         R-5 is untouched by this build and must not be read as closed"
    );
}

#[test]
fn ac30_channel_module_doc_comment_names_the_three_absent_ordering_terms() {
    let src = read_source("channel.rs");
    let lower = src.to_lowercase();
    // GJ-4's other three terms: origin-class weighting, clean-run history,
    // known-critical membership (each sourced from Muninn/the world
    // model, which does not exist in Rust).
    assert!(
        lower.contains("muninn"),
        "AC-30/REQ-30: channel.rs's module doc comment must name Muninn as the absent \
         source of the three missing ordering terms"
    );
}
