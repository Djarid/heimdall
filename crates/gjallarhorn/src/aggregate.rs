// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! Aggregation and the correlation key. This module's one responsibility
//! (section 4.0): derive a correlation key and collapse correlated events
//! into one incident, purely.
//!
//! **The correlation key is derived from typed fields only (REQ-31, the
//! anti-forgery criterion).** [`correlation_key_for`] reads only the
//! source term, the raising component and the concrete origin identifier,
//! and the pattern term, the event type. It never reads attacker-supplied
//! content, free text, a message body or any field not enumerated here.
//! Two events sharing a source term collapse; two events sharing a pattern
//! term collapse. The derivation is a pure, total function: equal inputs
//! yield equal keys on every call. [`crate::mint`] derives this key
//! internally when it mints an event; no minting function takes a
//! correlation key as a parameter, so a caller can neither supply a forged
//! key to defeat correlation nor a colliding one to force a false
//! collapse.
//!
//! **`aggregate` refuses rather than guessing (REQ-33, REQ-34).** An empty
//! slice has no correlation key to be keyed by, so it refuses with
//! [`AggregateRefusal::EmptyEventSet`] rather than returning an
//! [`Incident`] with a count of zero. A slice whose events carry differing
//! correlation keys refuses with
//! [`AggregateRefusal::MixedCorrelationKeys`] rather than silently
//! collapsing them or silently choosing one key, because collapsing
//! uncorrelated events would understate an incident's scope and choosing a
//! key silently would be a decision hidden inside a pure function.
//!
//! **`aggregate` is pure over its inputs (REQ-32, REQ-35).** It takes a
//! shared slice and nothing else: no mutable reference to
//! [`crate::channel::ProtectedChannel`], to
//! [`crate::channel::TriageQueue`] or to
//! [`crate::record::EventRecorder`] reaches its signature. There is
//! therefore no expressible way for a call to `aggregate` to retract an
//! admission, remove an entry from either structure, un-write a recorded
//! event or change a route: collapsing 10000 correlated events into one
//! incident does not un-halt any of the 10000 runs that were already
//! admitted or recorded.

use crate::types::{EventType, GjallarhornEvent, Severity, SourceProvenance};

/// REQ-31: the correlation key, from typed fields only. The source term is
/// the raising component and the concrete origin identifier; the pattern
/// term is the event type. Pure, total and deterministic: equal inputs
/// yield equal keys on every call.
pub fn correlation_key_for(event_type: EventType, source: &SourceProvenance) -> String {
    format!(
        "{:?}::{}::{}",
        event_type,
        source.raising_component(),
        source.origin_id()
    )
}

/// REQ-32: what a responder reads once events have been aggregated into
/// one incident. `highest_severity` is the highest severity seen by
/// ordinal comparison, not the most recently seen event's own severity.
/// The window is over arrival ordinals, never over wall-clock times,
/// because this crate reads no clock (REQ-6).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Incident {
    correlation_key: String,
    event_count: usize,
    window_lowest_ordinal: u64,
    window_highest_ordinal: u64,
    highest_severity: Severity,
    contained_instances: Vec<String>,
}

impl Incident {
    /// The correlation key every aggregated event shared.
    pub fn correlation_key(&self) -> &str {
        &self.correlation_key
    }

    /// How many events were aggregated into this incident.
    pub fn event_count(&self) -> usize {
        self.event_count
    }

    /// The arrival-ordinal window, `(lowest, highest)`, over every
    /// aggregated event's own ordinal.
    pub fn window(&self) -> (u64, u64) {
        (self.window_lowest_ordinal, self.window_highest_ordinal)
    }

    /// The highest severity seen anywhere in the aggregated events, by
    /// ordinal comparison, not by recency.
    pub fn highest_severity(&self) -> Severity {
        self.highest_severity
    }

    /// Each distinct origin identifier among the aggregated events' own
    /// provenance, each named once regardless of how many events that
    /// origin contributed.
    pub fn contained_instances(&self) -> &[String] {
        &self.contained_instances
    }
}

/// REQ-33, REQ-34: a closed refusal set. An empty slice and a slice whose
/// events carry differing correlation keys both refuse rather than
/// returning a hollow or a silently-keyed incident.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AggregateRefusal {
    /// The slice passed to [`aggregate`] was empty: there was no event to
    /// derive a correlation key from, so there is nothing an incident
    /// could be keyed by.
    EmptyEventSet,
    /// The slice passed to [`aggregate`] carried events with differing
    /// correlation keys. `found` names every distinct key seen, so the
    /// caller can see what was mixed rather than which one was silently
    /// chosen (because none was).
    MixedCorrelationKeys { found: Vec<String> },
}

/// REQ-32, REQ-35: pure. Takes a shared slice and nothing else: no mutable
/// reference to any channel, queue or recorder reaches this signature,
/// which is how REQ-35 holds structurally rather than merely by
/// observation. Refuses on an empty slice (REQ-33) and on a slice whose
/// events carry differing correlation keys (REQ-34); otherwise collapses
/// every event into one [`Incident`].
pub fn aggregate(events: &[GjallarhornEvent]) -> Result<Incident, AggregateRefusal> {
    let Some(first) = events.first() else {
        return Err(AggregateRefusal::EmptyEventSet);
    };
    let correlation_key = first.correlation_key().to_string();

    let mut distinct_keys: Vec<String> = Vec::new();
    for event in events {
        let key = event.correlation_key();
        if !distinct_keys.iter().any(|found| found == key) {
            distinct_keys.push(key.to_string());
        }
    }
    if distinct_keys.len() > 1 {
        return Err(AggregateRefusal::MixedCorrelationKeys {
            found: distinct_keys,
        });
    }

    let mut window_lowest_ordinal = first.arrival_ordinal();
    let mut window_highest_ordinal = first.arrival_ordinal();
    let mut highest_severity = first.severity();
    let mut contained_instances: Vec<String> = Vec::new();

    for event in events {
        let ordinal = event.arrival_ordinal();
        if ordinal < window_lowest_ordinal {
            window_lowest_ordinal = ordinal;
        }
        if ordinal > window_highest_ordinal {
            window_highest_ordinal = ordinal;
        }
        if event.severity().ordinal() > highest_severity.ordinal() {
            highest_severity = event.severity();
        }
        let origin_id = event.source().origin_id();
        if !contained_instances.iter().any(|found| found == origin_id) {
            contained_instances.push(origin_id.to_string());
        }
    }

    Ok(Incident {
        correlation_key,
        event_count: events.len(),
        window_lowest_ordinal,
        window_highest_ordinal,
        highest_severity,
        contained_instances,
    })
}
