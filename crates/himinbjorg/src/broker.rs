//! `broker_action`, the credential-scope check, the single actuator slot
//! left unimplemented and the typed refusal (REQ-22, EC-14, EC-15, section
//! 5.6 and section 6.1 of `.opencode/plans/himinbjorg-step-three.md`,
//! section 13 file 11).
//!
//! **Refuse-only, per HB3-7.** The full signature
//! `plans/dd/himinbjorg.md` section 6.1 names exists below, and it dispatches
//! to exactly one actuator slot. That slot is unimplemented: every call that
//! clears the credential-scope check still returns
//! [`crate::types::BrokerRefusal::NoActuatorAvailable`], never an `Ok`
//! value. This holds even when the same proposal previously validated to
//! [`crate::types::Decision::Allow`] (EC-14): an authorised decision does not
//! execute in step three. This module contains no call to `std::process`,
//! `std::fs` or `std::net`, and shells out to nothing.
//!
//! **The credential-scope check runs first, and is real (EC-15).** The
//! actuator slot being unimplemented must not become an excuse to skip the
//! scope check, so step four inherits a working refusal path rather than
//! having to add one. Because `broker_action`'s own signature carries no
//! `EffectiveSurface` (section 6.1), and [`crate::types::AgentContext`]
//! itself carries no credential-scope field either, this module owns its
//! own hardcoded, non-empty permitted-scope allowlist
//! ([`PERMITTED_CREDENTIAL_SCOPES`]), following the same minimal-fidelity,
//! real-check-against-a-hardcoded-bound pattern `context`'s target scope and
//! constraint set already establish (HB3-5). An empty allowlist would mean
//! no scope is ever permitted, never every scope; a compile-time assertion
//! guarantees it is never empty, so that failure mode is a build failure,
//! not a silently unreachable happy path. Membership is a positive match
//! against this named allowlist, never a denylist of forbidden scope names
//! (REQ-25).
//!
//! **`BrokerResult` is uninhabited (section 7).** No `Ok` value of this type
//! can be constructed anywhere, by any caller, so REQ-22's "must not return
//! a success value" is a structural property of the type, not merely an
//! unenforced convention this function happens to follow.

use crate::types::{Action, AgentContext, BrokerRefusal, BrokerResult, Scope};

/// Himinbjörg's own hardcoded, non-empty allowlist of credential scopes
/// permitted to reach the (currently unimplemented) actuator slot (EC-15).
/// An empty allowlist would mean no scope is ever permitted, never every
/// scope; see this module's own doc comment for why this constant, rather
/// than a field on [`AgentContext`] or on an `EffectiveSurface`, is the
/// scope check's input at this fidelity.
const PERMITTED_CREDENTIAL_SCOPES: &[&str] = &["fixture-scope", "public-surface-fixture-scope"];

// Compile-time non-emptiness assertion (EC-15, this delegation's own
// instruction): a future edit that empties this allowlist fails the BUILD,
// not a later test run, so an always-refuse scope check is unreachable
// rather than a silently unexercised happy path.
const _: () = assert!(
    !PERMITTED_CREDENTIAL_SCOPES.is_empty(),
    "PERMITTED_CREDENTIAL_SCOPES must be non-empty: an empty allowlist means no credential \
     scope is ever permitted, never every scope (EC-15)"
);

/// Whether `scope` is a positive match against
/// [`PERMITTED_CREDENTIAL_SCOPES`] (REQ-25): no denylist of forbidden scope
/// names anywhere in this module.
fn scope_is_permitted(scope: &Scope) -> bool {
    PERMITTED_CREDENTIAL_SCOPES
        .iter()
        .any(|permitted| *permitted == scope.as_str())
}

/// Dispatches `action` under `credential_scope` to the single actuator slot
/// (REQ-22). The scope check runs first and is real (EC-15): a scope absent
/// from [`PERMITTED_CREDENTIAL_SCOPES`] refuses with
/// [`BrokerRefusal::ScopeNotPermitted`] before the actuator slot is ever
/// reached. The actuator slot itself is unimplemented in step three, so
/// every call that clears the scope check refuses with
/// [`BrokerRefusal::NoActuatorAvailable`], naming the missing actuator.
/// [`BrokerResult`] is uninhabited (section 7): no `Ok` value is producible
/// on any path, including for a proposal that previously validated to
/// [`crate::types::Decision::Allow`] (EC-14). `context` and `action` are
/// accepted per the interface's full signature
/// (`plans/dd/himinbjorg.md` section 6.1) but are not yet read by the
/// unimplemented actuator slot; step four replaces this slot's body and
/// nothing else about the interface.
pub fn broker_action(
    _context: &AgentContext<'_>,
    _action: &Action,
    credential_scope: &Scope,
) -> Result<BrokerResult, BrokerRefusal> {
    if !scope_is_permitted(credential_scope) {
        return Err(BrokerRefusal::ScopeNotPermitted);
    }

    // The single actuator slot (HB3-7): unimplemented in step three. Named
    // explicitly, never a silent success and never a partial or simulated
    // effect (REQ-22). Step four's own job is to replace this arm's body
    // and nothing else about the interface.
    Err(BrokerRefusal::NoActuatorAvailable)
}
