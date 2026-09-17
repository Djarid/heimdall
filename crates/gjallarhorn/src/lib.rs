#![forbid(unsafe_code)]
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! `gjallarhorn` crate root: Gjallarhorn's event spine and its channel
//! separation (`.opencode/plans/gjallarhorn-build-spec.md`, issue #114 and
//! its successors #115 to #117).
//!
//! STATUS AT THIS COMMIT (issue #117, spec files 1 to 11): the crate is
//! complete against this spec's own module-by-module design. `types.rs`,
//! `mint.rs`, `routing.rs`, `record.rs`, `channel.rs` and `aggregate.rs`
//! landed in issues #114 to #116; `delivery.rs` and `raise.rs` land here.
//! Every module named in section 4.0 now carries real content: the closed
//! eight-variant [`EventType`], the closed four-variant [`Route`] with its
//! total [`Route::force`], [`Severity`] with its total [`Severity::ordinal`],
//! [`SourceProvenance`], the opaque [`GjallarhornEvent`], the eight minting
//! functions, the hardcoded routing table, the event recorder and its one
//! minimal implementation, the two channel structures and their single
//! admission rule, `aggregate` and its correlation key, the one-method
//! delivery contract and its one in-process retaining implementation, and
//! [`raise::raise`] itself sequencing record, then route, then admit, then
//! deliver, exactly once, in that order (REQ-21).
//!
//! Four further things are stated here, in prose a reader cannot miss,
//! because section 4.9 of the spec requires the crate-root doc comment to
//! carry them regardless of how much of the crate is built yet:
//!
//! - Three of the design document's mechanisms are absent from this crate
//!   by ruling, not by oversight: `contain()`, flood quarantine and
//!   reputation-weighted triage ordering (OR-1). None will be added without
//!   its own named trigger.
//! - The design document's own first-named load-bearing property
//!   (containment firing without alert delivery) is held here as a design
//!   contract and is **not tested**, because no Rust Fenrir exists to
//!   provide the counterparty half of that test.
//! - Delivery, once built, is stubbed behind a trait with one in-process,
//!   retaining implementation: no outward transport exists anywhere in this
//!   crate, and no operator receives anything from it.
//! - This crate does not and will not unblock live promotion minting. A
//!   second, separate half is needed inside `crates/hierarchy-vor/`, which
//!   reopens that crate's own `REQ-13` secret boundary and is out of scope
//!   for every issue this spec names (OR-2).

mod types;

pub use types::{EventType, GjallarhornEvent, Route, Severity, SourceProvenance};

pub mod aggregate;
pub mod channel;
pub mod delivery;
pub mod mint;
pub mod raise;
pub mod record;
pub mod routing;

// Section 4.9's crate-root re-export list (REQ-52's own module-split
// convention: `mod types;` with items re-exported individually above;
// every other module stays `pub mod` with its own items reachable either
// through the module path or, for the items section 4.9 names by name,
// re-exported here too so `gjallarhorn::raise`, `gjallarhorn::EventRecorder`
// and the rest all resolve at the crate root for any external caller,
// including the one live raise site inside `crates/process-engine/`
// (OR-5, OR-7) and `tests/public_surface.rs`).
pub use aggregate::{AggregateRefusal, Incident, aggregate, correlation_key_for};
pub use channel::{Admission, ProtectedChannel, TriageQueue, admission_for};
pub use delivery::{Delivery, InProcessDelivery};
pub use mint::{
    MintRefusal, mint_anomaly_surfaced, mint_attempt_introspection_or_canary_fire,
    mint_audit_log_integrity_failure, mint_constraint_axiom_violated,
    mint_instruction_pattern_at_boundary, mint_promotion_request_above_threshold,
    mint_resource_limit_breached, mint_taint_boundary_breach_attempt,
};
pub use raise::{RaiseOutcome, RaiseRefusal, raise};
pub use record::{EventRecorder, MinimalEventRecorder};
pub use routing::{GLOBAL_DEFAULT_ROUTE, route_for};

// The only test-related construct permitted anywhere under src/ (REQ-52).
// One `#[cfg(test)] #[path = ...] mod ...;` declaration per unit-test file,
// no test logic here. The test bodies live in ../unit_tests/, which src/
// never touches.
#[cfg(test)]
#[path = "../unit_tests/event_and_mint.rs"]
mod event_and_mint;

#[cfg(test)]
#[path = "../unit_tests/routing_table.rs"]
mod routing_table;

#[cfg(test)]
#[path = "../unit_tests/aggregation.rs"]
mod aggregation;

#[cfg(test)]
#[path = "../unit_tests/channel_separation.rs"]
mod channel_separation;

#[cfg(test)]
#[path = "../unit_tests/raise_failclosed.rs"]
mod raise_failclosed;
