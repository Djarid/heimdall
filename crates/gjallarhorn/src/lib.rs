#![forbid(unsafe_code)]
// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! `gjallarhorn` crate root: Gjallarhorn's event spine and its channel
//! separation (`.opencode/plans/gjallarhorn-build-spec.md`, issue #114 and
//! its successors #115 to #117).
//!
//! STATUS AT THIS COMMIT (issue #114, spec files 1 to 4 only): only
//! `types.rs` carries real content. The vocabulary is real: the closed
//! eight-variant [`EventType`], the closed four-variant [`Route`] with its
//! total [`Route::force`], [`Severity`] with its total [`Severity::ordinal`],
//! [`SourceProvenance`] and the opaque [`GjallarhornEvent`] with every field
//! private and construction confined to `pub(crate) GjallarhornEvent::new`
//! (REQ-10, REQ-11, GJ-B-1). `mint.rs`, `routing.rs`, `record.rs`,
//! `channel.rs`, `aggregate.rs`, `delivery.rs` and `raise.rs` are declared
//! here as modules so the crate's eventual shape is visible, but each is
//! currently an empty file carrying only its SPDX header: no type, no
//! function and no re-export from any of them exists yet. That work belongs
//! to issues #115 to #117 and is deliberately left undone here rather than
//! implemented ahead of its own scope.
//!
//! Because of that, `crate::mint`, `crate::routing`, `crate::record`,
//! `crate::channel`, `crate::aggregate`, `crate::delivery` and `crate::raise`
//! currently expose nothing, and this crate's own
//! `unit_tests/routing_table.rs`, `unit_tests/aggregation.rs`,
//! `unit_tests/channel_separation.rs` and `unit_tests/raise_failclosed.rs`
//! (wired in below per REQ-52, because every unit-test file that exists on
//! disk must be declared here regardless of whether the module it exercises
//! is built yet) fail to compile against those empty modules. That failure
//! is expected and correct at this stage: it is the next issue's starting
//! point, not a defect in this one. `unit_tests/event_and_mint.rs` is wired
//! in on the same footing and is the one unit-test file this issue's own
//! scope makes buildable, once `mint.rs` and `aggregate.rs` exist (issue
//! #115); until then it too fails to compile, for the same honest reason.
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
