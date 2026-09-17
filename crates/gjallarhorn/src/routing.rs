// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The hardcoded, compile-time routing table (OR-9). This module's one
//! responsibility (section 4.0): resolve one event type to one route.
//! Nothing else reaches [`route_for`]'s signature: not the severity, not the
//! source provenance, not the correlation key, not the audit reference, not
//! the arrival ordinal, not the channel state, not the queue state and not
//! the aggregation state (REQ-18). There is no file read, no environment
//! read, no argument parse and no mutable global anywhere in this module
//! (REQ-14), so there is no surface through which the guarded population
//! could change what routes where.
//!
//! **The table itself (REQ-14, REQ-15).** [`route_for`] is an exhaustive
//! `match` over [`crate::types::EventType`] with no wildcard arm, so a ninth
//! variant added later fails the build rather than folding into a catch-all.
//! Each arm's doc comment below cites the design document's own row.
//!
//! **The retained default and why it must escalate (REQ-16).** This module
//! exposes [`GLOBAL_DEFAULT_ROUTE`], and its value is [`crate::types::Route::HumanNotify`],
//! never `Route::LogOnly`. The design document's section 5 first bullet
//! requires that an event type absent from the table escalate rather than
//! fall through to log-only, so the default must itself be an escalating
//! route rather than the least forceful one.
//!
//! **The default is currently unreachable, and that is stated as a
//! property, not left implicit (REQ-17).** Because [`route_for`]'s match is
//! exhaustive over a closed enum, "an event type absent from the routing
//! table" is structurally unrepresentable here: there is no value of
//! `EventType` that fails to match one of the eight arms, so no call to
//! `route_for` can ever fall through to a default. This is a stronger
//! guarantee than the design document's own fail-closed default, which is
//! exactly why [`GLOBAL_DEFAULT_ROUTE`] is retained as defence in depth
//! rather than deleted: should a future change ever introduce a second,
//! non-exhaustive dispatch path over event types, that path has a safe,
//! escalating value to fall back on, stated once here rather than
//! reinvented at the point of need.

use crate::types::{EventType, Route};

/// REQ-16, REQ-17: the global default route, retained as defence in depth
/// even though REQ-14's exhaustive match over a closed enum makes it
/// currently unreachable through the type system. `HumanNotify`, never
/// `LogOnly`: an absent event type must escalate, per the design document's
/// section 5 first bullet.
pub const GLOBAL_DEFAULT_ROUTE: Route = Route::HumanNotify;

/// REQ-14, REQ-15, REQ-18: resolves one event type to one route by a
/// hardcoded, compile-time table. Total, pure and exhaustive, with no
/// wildcard arm: adding a ninth [`EventType`] variant fails this match at
/// compile time rather than silently defaulting. Takes the event type
/// alone; severity, provenance, the correlation key, the audit reference,
/// the arrival ordinal, the channel state, the queue state and the
/// aggregation state are all absent from this signature, which is how
/// REQ-18's purity holds: a route can never be derived from attacker-
/// supplied content because there is no channel for that content to travel
/// through.
pub fn route_for(event_type: EventType) -> Route {
    match event_type {
        // Design document section 3.1, row one: an instruction pattern
        // observed at a boundary is the lowest-force case, logged only.
        EventType::InstructionPatternAtBoundary => Route::LogOnly,

        // Design document section 3.1, row two: a constraint axiom
        // violation escalates to a human.
        EventType::ConstraintAxiomViolated => Route::HumanNotify,

        // Design document section 3.1, row three: a taint boundary breach
        // attempt escalates to a human.
        EventType::TaintBoundaryBreachAttempt => Route::HumanNotify,

        // Design document section 3.1, row four: a surfaced anomaly
        // escalates to a human.
        EventType::AnomalySurfaced => Route::HumanNotify,

        // Design document section 3.1, row five: an attempted
        // introspection or a canary firing halts the agent immediately,
        // the second-highest force in the table.
        EventType::AttemptIntrospectionOrCanaryFire => Route::HaltAgent,

        // Design document section 3.1, row six: a resource limit breach
        // escalates to a human.
        EventType::ResourceLimitBreached => Route::HumanNotify,

        // Design document section 3.1, row seven: a promotion request
        // above threshold escalates to a human.
        EventType::PromotionRequestAboveThreshold => Route::HumanNotify,

        // Design document section 3.1, row eight: an audit log integrity
        // failure is the table's highest-force case and halts the whole
        // system, not merely the agent.
        EventType::AuditLogIntegrityFailure => Route::HaltSystem,
    }
}
