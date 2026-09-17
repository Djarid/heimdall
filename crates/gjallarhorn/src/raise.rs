// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The single entry point (design document section 3.1, transferred and
//! amended, section 2.3). This module's one responsibility (section 4.0):
//! sequence record, then route, then admit, then deliver, exactly once, in
//! that order. It owns the ordering and nothing else: it decides no route
//! itself (`routing.rs`'s job), decides no admission itself
//! (`channel.rs`'s job), and performs no delivery itself
//! (`delivery.rs`'s job). It calls each in turn and refuses, loudly, the
//! moment the one call that must come first fails.
//!
//! **Write before route, structurally, and this is verifiable by reading
//! the function body top to bottom (REQ-21).** [`raise`] calls
//! [`crate::record::EventRecorder::record_event`] as the first fallible
//! operation in its body. On `Err`, it returns
//! `Err(RaiseRefusal::RecordWrite(..))` immediately: nothing below that
//! point in the function ever runs. No branch anywhere in this function
//! reaches the routing resolver, the channel admission or the delivery
//! call on that error path. An unlogged event is treated as no event at
//! all (HK-4).
//!
//! **Neither the recorder nor the delivery implementation can be omitted
//! (REQ-22).** Both reach this function as plain `&mut impl` parameters:
//! never an `Option`, never defaulted, never behind a builder that could
//! omit either. There is no code path through [`raise`] that routes,
//! admits or delivers without a recorder, because there is no code path
//! through [`raise`] at all without one: a raise call with no recorder is
//! unrepresentable at the call site, not merely refused inside the body.
//!
//! **The two failure classes are distinct because they mean different
//! things (REQ-23, REQ-38).** [`RaiseRefusal::RecordWrite`] means nothing
//! happened at all: the write failed before anything was routed, admitted
//! or delivered. [`RaiseRefusal::Delivery`] means the opposite of nothing:
//! the event IS recorded and IS admitted to whichever of the two
//! structures its admission selected, and only the outward hand-off
//! failed. A delivery failure retracts neither the record nor the
//! admission, because over-paging is a cost and a missed page is a
//! failure (design document section 5's aggregation-failure bullet).
//!
//! **Section 2.3's recorded amendment.** The design document's section 3.1
//! fixes this entry point's signature as `raise(event: GjallarhornEvent)
//! -> None`. This build records that signature as amended: a function
//! returning nothing cannot express fail closed. If the write fails,
//! `raise` must say so to its caller loudly rather than swallowing the
//! failure, which is exactly the silence the design document's own
//! section 5 opening sentence refuses. So `raise` returns
//! `Result<RaiseOutcome, RaiseRefusal>` and carries `#[must_use]`, so a
//! caller cannot silently discard a refusal.

use crate::channel::{Admission, ProtectedChannel, TriageQueue, admission_for};
use crate::delivery::Delivery;
use crate::record::EventRecorder;
use crate::routing::route_for;
use crate::types::{GjallarhornEvent, Route};

/// REQ-23: what a successful [`raise`] call reports. Carries the route
/// taken and which of the two structures the event was admitted to, and
/// carries no boolean readable as "delivered" independently of either
/// field: this type reports what happened, never whether it went well.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RaiseOutcome {
    route: Route,
    admission: Admission,
}

impl RaiseOutcome {
    /// The route this event was resolved to, per [`crate::routing::route_for`].
    pub fn route(&self) -> Route {
        self.route
    }

    /// Which of the two structures this event was admitted to, per
    /// [`crate::channel::admission_for`].
    pub fn admission(&self) -> Admission {
        self.admission
    }
}

/// REQ-23: a closed refusal set, with the record-write failure and the
/// delivery failure kept as distinct variants because they mean different
/// things. [`RaiseRefusal::RecordWrite`] means nothing happened at all
/// (REQ-21): no route was taken, no admission occurred and nothing was
/// delivered. [`RaiseRefusal::Delivery`] means the event IS recorded and
/// IS admitted, and only the outward hand-off failed (REQ-38).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RaiseRefusal {
    /// The event recorder's write failed. Nothing below the write ever
    /// ran: the route was not taken, the admission did not happen and
    /// nothing was delivered.
    RecordWrite(String),
    /// The delivery implementation's hand-off failed. The event is
    /// already recorded and already admitted; only the outward hand-off
    /// did not succeed.
    Delivery(String),
}

/// The single entry point. Sequences record, then route, then admit, then
/// deliver, exactly once, in that order (REQ-21):
///
/// 1. `recorder.record_event(&event)`. On `Err`, return
///    `Err(RaiseRefusal::RecordWrite(..))` immediately: nothing below this
///    point runs.
/// 2. [`crate::routing::route_for`], to resolve the route for this event's
///    type.
/// 3. [`crate::channel::admission_for`], to decide which of the two
///    structures this event admits to, then admit it to exactly one of
///    `protected` or `triage`.
/// 4. `delivery.deliver(&event, route)`. On `Err`, return
///    `Err(RaiseRefusal::Delivery(..))`, but steps 1 to 3 stand: nothing
///    is undone.
///
/// REQ-22: `recorder` and `delivery` both reach this function as plain
/// `&mut impl` parameters, never an `Option`, never defaulted and never
/// behind a builder that could omit either, so a raise call with no
/// recorder is unrepresentable at the call site.
///
/// `#[must_use]` (REQ-23): a caller cannot silently discard a refusal.
/// `Result` is already `#[must_use]` itself; this function's own
/// attribute is kept anyway because REQ-23 and AC-23 require `raise`
/// itself to carry it explicitly, so the double annotation is deliberate
/// rather than an oversight (`clippy::double_must_use` is silenced for
/// exactly that reason, not because the lint is wrong in general).
#[must_use]
#[allow(clippy::double_must_use)]
pub fn raise(
    event: GjallarhornEvent,
    recorder: &mut impl EventRecorder,
    protected: &mut ProtectedChannel,
    triage: &mut TriageQueue,
    delivery: &mut impl Delivery,
) -> Result<RaiseOutcome, RaiseRefusal> {
    // Step 1: write before route. The first fallible operation in this
    // function body. On Err, return immediately: nothing below this
    // point ever runs, so nothing is routed, nothing is admitted and
    // nothing is delivered (REQ-21).
    recorder
        .record_event(&event)
        .map_err(RaiseRefusal::RecordWrite)?;

    // Step 2: resolve the route. A total, pure function of the event
    // type alone (REQ-18).
    let route = route_for(event.event_type());

    // Step 3: decide admission and admit to exactly one of the two
    // structures. `event` is cloned here (GjallarhornEvent derives Clone,
    // types.rs) so the owned original can be moved into whichever
    // structure admission selects while a clone remains available for
    // step 4's delivery call, without disturbing the documented
    // record-then-route-then-admit-then-deliver order.
    let admission = admission_for(event.event_type(), event.source());
    let event_for_delivery = event.clone();
    match admission {
        Admission::Protected => protected.admit(event),
        Admission::Triage => triage.admit(event),
    }

    // Step 4: deliver. On Err, return Err(RaiseRefusal::Delivery(..)),
    // but the record from step 1 and the admission above both stand:
    // nothing is undone (REQ-38).
    delivery
        .deliver(&event_for_delivery, route)
        .map_err(RaiseRefusal::Delivery)?;

    Ok(RaiseOutcome { route, admission })
}
