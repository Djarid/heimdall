// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The event recorder and write-before-route (OR-8). This module's one
//! responsibility (section 4.0): define the one-method write contract and
//! provide one minimal, append-only recorder. It knows nothing of routes
//! and nothing of queues; those belong to `routing.rs` and `channel.rs`.
//!
//! **The write contract, one fallible operation (REQ-19).**
//! [`EventRecorder`] carries exactly one method: write one event and either
//! succeed or fail. Nothing about verification, query, rotation, replay or
//! delivery appears on this trait. It is Gjallarhorn's own trait, built on
//! the sibling audit crate's own recorder precedent but not a reuse of it,
//! so this crate's `[dependencies]` table stays literally empty (REQ-2)
//! and no alerting dependency lands on the control-channel crate.
//! [`crate::raise::raise`] calls this write first, before any call to the
//! routing resolver, before any channel admission and before any delivery
//! (REQ-21): an unlogged event is treated as no event at all (HK-4).
//!
//! **The one minimal implementation is append only (REQ-20).**
//! [`MinimalEventRecorder`] appends and never mutates: no method anywhere on
//! this type alters, deletes, shortens, empties, filters, takes from either
//! end, adds in the middle, reorders or exchanges the position of an
//! already-appended entry. Append-only holds here by the structural absence
//! of a mutating operation, not by a runtime guard against one. It exposes a
//! read-only accessor for its entries and has no mutable counterpart. It
//! performs no signing, no chained digest and no durable persistence: all
//! three stay deferred, named here rather than claimed.
//!
//! **The honest limit, stated plainly, not smoothed (D112's EC-13,
//! inherited by name, not narrowed).** This trait's contract asks every
//! implementation to keep what it reports as written; nothing in the type
//! system enforces that a `Result::Ok` return means anything was actually
//! kept. A recorder whose write always reports success while keeping
//! nothing satisfies [`crate::raise::raise`]'s write-before-route obligation
//! vacuously: the trait asks, but the type system cannot enforce. Nothing in
//! this crate detects or distinguishes a lying recorder from an honest one,
//! and claiming otherwise would be false. This is the same class of limit
//! as D112's EC-13 and D103's limit two: named here and not closed by this
//! crate.

use crate::types::GjallarhornEvent;

/// REQ-19: the narrow, single-method write contract. A write either
/// succeeds, in which case [`crate::raise::raise`] may proceed to route,
/// admit and deliver, or it fails, in which case `raise` refuses and
/// nothing below the write ever runs (REQ-21). Any implementation of this
/// trait, this crate's own minimal one or a future real one, must respect
/// that a returned success means the event is kept; the honest limit on
/// that promise is this module's own doc comment above: the type system
/// cannot enforce it, only ask for it.
pub trait EventRecorder {
    /// Writes one event. `Err` carries a diagnostic naming why the write
    /// failed; `Ok` is the caller's signal that it is now safe to proceed
    /// to whatever the event authorises being raised toward.
    fn record_event(&mut self, event: &GjallarhornEvent) -> Result<(), String>;
}

/// REQ-20: the one minimal, append-only [`EventRecorder`] implementation
/// this crate provides. In process only, unsigned, unchained and not
/// durable: none of that is claimed here (see this module's own doc
/// comment for what is deferred and why). Every successful write appends
/// one [`GjallarhornEvent`] to an internal, growable list; no method on
/// this type alters or deletes an already-appended entry, which is the
/// whole of how "append only" holds here: a structural absence of a
/// mutating operation, not a runtime guard against one.
#[derive(Debug, Default)]
pub struct MinimalEventRecorder {
    entries: Vec<GjallarhornEvent>,
}

impl MinimalEventRecorder {
    /// Builds an empty recorder: no entries until the first successful
    /// write.
    pub fn new() -> Self {
        MinimalEventRecorder {
            entries: Vec::new(),
        }
    }

    /// Every event this recorder holds, in the order it was written. A
    /// read-only accessor: there is no mutable counterpart anywhere on
    /// this type, and nothing here lets a caller alter or delete what is
    /// returned.
    pub fn records(&self) -> &[GjallarhornEvent] {
        &self.entries
    }
}

impl EventRecorder for MinimalEventRecorder {
    fn record_event(&mut self, event: &GjallarhornEvent) -> Result<(), String> {
        self.entries.push(event.clone());
        Ok(())
    }
}
