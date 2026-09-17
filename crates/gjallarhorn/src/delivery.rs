// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! Delivery, stubbed behind a trait (OR-4). This module's one
//! responsibility (section 4.0): define the one-method delivery contract
//! and provide one in-process, retaining implementation. It knows nothing
//! of admission and nothing of aggregation; those belong to `channel.rs`
//! and `aggregate.rs`.
//!
//! **The delivery contract, one fallible operation (REQ-36).**
//! [`Delivery`] carries exactly one method: deliver one event on one
//! route, and either succeed or fail. Nothing about retry, batching,
//! formatting, templating, acknowledgement or transport configuration
//! appears on this trait.
//!
//! **No outward transport exists here, and no operator receives anything
//! (REQ-37, OR-4).** [`InProcessDelivery`], the one implementation this
//! crate provides, performs no network operation, no process spawn and no
//! file write. It retains what it is given in an internal, growable list
//! with a read-only accessor, so a test can assert what was delivered on
//! which route. This is NOT an outward transport: nothing here reaches
//! past this crate's own process, and no human operator, on-call system or
//! external service is notified by any code in this module. Resolution
//! five's real notify transport (`std::net`, a webhook, an email, a page)
//! is a named follow-on, out of scope for this build (OR-4, section 12.2
//! deferral 5), and REQ-6's mechanical text scan is what enforces the
//! absence of every network, process and file token from this file.
//!
//! **A delivery failure is loud, and it retracts nothing that came before
//! it (REQ-38).** [`crate::raise::raise`] calls [`Delivery::deliver`] only
//! after the event is already recorded and already admitted. On `Err`,
//! `raise` returns `Err(crate::raise::RaiseRefusal::Delivery(..))`, but the
//! record and the admission both stand: over-paging is a cost, and a
//! missed page is a failure (design document section 5's aggregation-
//! failure bullet), so a failed hand-off must never look, from the
//! record's or the channel's point of view, as though the event never
//! arrived.

use crate::types::{GjallarhornEvent, Route};

/// REQ-36: the narrow, single-method delivery contract. Nothing about
/// retry, batching, formatting, templating, acknowledgement or transport
/// configuration appears here; an implementation either hands the event
/// off successfully or it does not, and reports which.
pub trait Delivery {
    /// Delivers one event on one route. `Err` carries a diagnostic naming
    /// why the hand-off failed; `Ok` is this implementation's own claim
    /// that the event reached wherever this implementation sends it,
    /// subject to the same honest limit [`crate::record::EventRecorder`]'s
    /// own doc comment states for the write contract: the trait asks, the
    /// type system cannot enforce it.
    fn deliver(&mut self, event: &GjallarhornEvent, route: Route) -> Result<(), String>;
}

/// REQ-37: the one [`Delivery`] implementation this crate provides. It
/// retains every event and route it is given, in delivery order, in an
/// internal, growable list, so a test can assert what was delivered and on
/// which route. It performs no network operation, no process spawn and no
/// file write.
///
/// **This is NOT an outward transport, and no operator receives anything
/// from it.** Retaining a delivered event in an in-process list is not the
/// same act as paging a human, and this type must never be read as though
/// it were: nothing it does leaves this crate's own process, and no
/// on-call system, webhook, email or terminal anywhere is notified by any
/// method on this type.
#[derive(Debug, Default)]
pub struct InProcessDelivery {
    delivered: Vec<(GjallarhornEvent, Route)>,
}

impl InProcessDelivery {
    /// Builds an empty delivery implementation: nothing retained until the
    /// first successful `deliver` call.
    pub fn new() -> Self {
        InProcessDelivery {
            delivered: Vec::new(),
        }
    }

    /// Every event and route this implementation has retained, in
    /// delivery order. A read-only accessor: there is no mutable
    /// counterpart anywhere on this type.
    pub fn delivered(&self) -> &[(GjallarhornEvent, Route)] {
        &self.delivered
    }
}

impl Delivery for InProcessDelivery {
    fn deliver(&mut self, event: &GjallarhornEvent, route: Route) -> Result<(), String> {
        self.delivered.push((event.clone(), route));
        Ok(())
    }
}
