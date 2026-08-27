//! `broker_action` (refuse-only, unchanged) and `broker_authorised_action`
//! (the witness-carrying entry point that CAN reach the actuator): the
//! credential-scope check, the witness match, the audit write, and the
//! single non-test call site of `actuator_git::execute` in the whole
//! repository (REQ-22, REQ-29 to REQ-33, REQ-36 to REQ-39, EC-14, EC-15,
//! section 5.6 and section 6.1 of `.opencode/plans/himinbjorg-step-three.md`,
//! section 13 file 11 of that spec, and section 10 file 17 of
//! `.opencode/plans/git-actuator-step-four.md`).
//!
//! **This module now calls `std::process`, transitively, through
//! `actuator_git::execute` -- but never directly.** Step three's own doc
//! comment for this module stated that it called no `std::process` and that
//! the actuator slot was unimplemented; that stopped being true the moment
//! `broker_authorised_action` landed. This module itself still contains no
//! literal `std::process`, `std::fs` or `std::net` reference: `actuator-git`
//! is the only crate in the workspace that touches any of the three
//! (REQ-7), and this module reaches it through exactly one call, gated
//! behind three checks (below), never bypassed.
//!
//! **`broker_action` stays refuse-only, per HB3-7, and its signature stays
//! byte for byte unchanged (REQ-30).** Its three arguments carry no
//! authorisation evidence, so it cannot authorise anything and must not
//! become a second execution path: every call that clears the credential-
//! scope check now returns [`crate::types::BrokerRefusal::NoAuthorisationEvidence`]
//! instead of the step-three `NoActuatorAvailable`, because the latter would
//! be a false statement now that an actuator genuinely exists behind
//! `broker_authorised_action`. This holds even when the same proposal
//! previously validated to [`crate::types::Decision::Allow`] (EC-14): having
//! a witness available elsewhere does not let `broker_action` use it, since
//! `broker_action` is never handed one. `broker_action` itself invokes the
//! actuator on no path, ever.
//!
//! **`broker_authorised_action` sequences exactly three gates before the
//! actuator call, and no fourth (REQ-39).**
//!
//! 1. The credential-scope check (REQ-37), unchanged and real, identical to
//!    `broker_action`'s own.
//! 2. The witness match (REQ-29): the action `broker_authorised_action` is
//!    asked to broker must byte-equal, on both action name and target, the
//!    action the supplied [`crate::types::Authorisation`] authorises.
//!    Mismatch refuses with [`crate::types::BrokerRefusal::WitnessMismatch`]
//!    and the actuator is never invoked.
//! 3. The audit write (REQ-31 to REQ-33), through the caller-supplied
//!    [`crate::audit::DecisionRecorder`], BEFORE the actuator is invoked. A
//!    failed write refuses with [`crate::types::BrokerRefusal::AuditWriteFailed`]
//!    and the action does not execute (REQ-32): there is no branch on which
//!    the actuator is invoked after a failed or skipped write. The ordering
//!    is structural, not a convention held by comment (REQ-33): the `?`
//!    operator on the write's result means the actuator call below is
//!    reachable only from a point that already holds the write's `Ok`.
//!
//! This module calls `validate_proposal` nowhere, calls the gate bridge
//! nowhere, and consults neither the cohort nor the sink registry to decide
//! whether to proceed (REQ-39): the authorisation comes entirely from the
//! witness `validate_proposal` already minted, and this module re-derives
//! none of it.
//!
//! **The credential-scope check runs first, and is real (EC-15), on both
//! entry points (REQ-37).** Because neither entry point's signature carries
//! an `EffectiveSurface` (section 6.1), and [`crate::types::AgentContext`]
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
//! **`BrokerResult` is uninhabited (section 7), still.** No `Ok` value of
//! this type can be constructed anywhere, by any caller, so REQ-30's "must
//! not return a success value" is a structural property of the type, not
//! merely an unenforced convention this function happens to follow.
//! [`crate::types::ActuationReceipt`] is `broker_authorised_action`'s own,
//! separate, inhabited success type.

use crate::audit::DecisionRecorder;
use crate::types::{
    Action, ActuationReceipt, AgentContext, Authorisation, BrokerRefusal, BrokerResult, Decision,
    Scope,
};
use std::sync::atomic::{AtomicUsize, Ordering};

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

/// `broker_action`'s exact signature, byte for byte unchanged from step
/// three (REQ-30). The scope check runs first and is real (EC-15): a scope
/// absent from [`PERMITTED_CREDENTIAL_SCOPES`] refuses with
/// [`BrokerRefusal::ScopeNotPermitted`] before anything else. Once the scope
/// check clears, this function refuses with
/// [`BrokerRefusal::NoAuthorisationEvidence`], because its three arguments
/// carry no authorisation evidence at all: there is no `Authorisation`
/// parameter here, so this function cannot mint, receive or re-derive one,
/// and it must not become a second execution path (REQ-30). [`BrokerResult`]
/// is uninhabited (section 7): no `Ok` value is producible on any path,
/// including for a proposal that previously validated to
/// [`crate::types::Decision::Allow`] (EC-14) -- a witness minted elsewhere
/// is simply never handed to this function. `context` and `action` are
/// accepted per the interface's full signature
/// (`plans/dd/himinbjorg.md` section 6.1) but are read by neither branch
/// below; the actuator is invoked from no path in this function, ever.
pub fn broker_action(
    _context: &AgentContext<'_>,
    _action: &Action,
    credential_scope: &Scope,
) -> Result<BrokerResult, BrokerRefusal> {
    if !scope_is_permitted(credential_scope) {
        return Err(BrokerRefusal::ScopeNotPermitted);
    }

    // No authorisation evidence reaches this function (REQ-30): never a
    // silent success and never a partial or simulated effect, and never a
    // second path to the actuator.
    Err(BrokerRefusal::NoAuthorisationEvidence)
}

/// A process-local sequence number for [`ActuationReceipt::record_id`],
/// incremented once per successful audit write this module performs. See
/// [`ActuationReceipt`]'s own doc comment for the honest limit on what this
/// number identifies (it is not a durable identifier the recorder itself
/// returned; [`crate::audit::DecisionRecorder::record`]'s own contract
/// reports success or failure only).
static RECORD_SEQUENCE: AtomicUsize = AtomicUsize::new(0);

/// The fixed commit message every `action:git.commit` witness is mapped to
/// (section 9.2's "constants, never repeated literals"). Neither `Action`
/// nor `Authorisation` carries a free-form commit-message field (deliberate,
/// per `.opencode/plans/himinbjorg-step-three.md`'s own REQ-8), so this
/// module supplies a fixed one of its own choosing; it is itself subject to
/// `actuator_git::argv`'s REQ-11 validation like any other caller-supplied
/// value, and is not treated specially.
const FIXED_COMMIT_MESSAGE: &str =
    "heimdall: automated commit via himinbjorg::broker_authorised_action";

/// The fixed remote name every `action:git.push` witness pushes to; the ref
/// itself is [`Authorisation::target`], which REQ-29's witness match above
/// has already guaranteed byte-equals the brokered action's own target by
/// the time [`operation_for`] is ever called.
const FIXED_PUSH_REMOTE: &str = "origin";

/// Maps an authorised action's name to the fixed `actuator_git::GitOperation`
/// shape it corresponds to (REQ-8's two-operation closed set of
/// `.opencode/plans/git-actuator-step-four.md`). `None` for any action name
/// other than the two `hierarchy_vor::cohort::PERMITTED_ACTIONS` names,
/// which is the only set check one of `validate_proposal` ever mints a
/// witness for in the first place: this function's `None` arm is therefore
/// defence in depth only, structurally unreachable in practice, following
/// `DefinitionRefusal::EmptyIntersection`'s own precedent for naming such an
/// arm honestly rather than presenting it as load bearing. Never described
/// anywhere as the mechanism that restricts which actions can execute; that
/// restriction belongs to check one and to the witness match above.
fn operation_for(authorisation: &Authorisation) -> Option<actuator_git::GitOperation> {
    match authorisation.action_name() {
        "action:git.commit" => Some(actuator_git::GitOperation::Commit {
            message: FIXED_COMMIT_MESSAGE.to_string(),
        }),
        "action:git.push" => Some(actuator_git::GitOperation::Push {
            remote: FIXED_PUSH_REMOTE.to_string(),
            ref_name: authorisation.target().to_string(),
        }),
        _ => None,
    }
}

/// The witness-carrying entry point (GA-1, section 5.2 of
/// `.opencode/plans/git-actuator-step-four.md`): the only place in this
/// crate authorisation from a real [`Authorisation`] can reach the
/// actuator. Sequences exactly three gates before the single, non-test call
/// site of `actuator_git::execute` in the whole repository (REQ-36), and no
/// fourth (REQ-39): the credential-scope check (REQ-37, identical to
/// `broker_action`'s own and run first), the witness match (REQ-29), and
/// the audit write (REQ-31 to REQ-33). This function calls
/// `validate_proposal` nowhere, calls the gate bridge nowhere, and consults
/// neither the cohort nor the sink registry: the authorisation comes
/// entirely from `authorisation`, minted only by `validate_proposal` on
/// [`crate::types::Decision::Allow`], and this function re-derives none of
/// it (REQ-39).
///
/// On a refusal from the actuator itself, `actuator-git`'s own reason is
/// carried through verbatim, in [`BrokerRefusal::ActuatorRefused`], dropping
/// nothing (REQ-38).
pub fn broker_authorised_action(
    context: &AgentContext<'_>,
    action: &Action,
    credential_scope: &Scope,
    authorisation: &Authorisation,
    recorder: &mut impl DecisionRecorder,
) -> Result<ActuationReceipt, BrokerRefusal> {
    // Gate one (REQ-37): the credential-scope check, unchanged and real,
    // before any witness check, any audit write and any actuator
    // invocation.
    if !scope_is_permitted(credential_scope) {
        return Err(BrokerRefusal::ScopeNotPermitted);
    }

    // Gate two (REQ-29): byte equality on action name and target. A witness
    // minted for one action never authorises a different one (EC-11).
    if authorisation.action_name() != action.action_name || authorisation.target() != action.target
    {
        return Err(BrokerRefusal::WitnessMismatch);
    }

    // Gate three (REQ-31 to REQ-33): the audit write, BEFORE the actuator
    // is invoked. The `?` below is the structural proof of the ordering
    // REQ-33 requires: everything from here on is reachable only from a
    // point that already holds this write's `Ok`. A failed write refuses
    // here and the actuator is never invoked (REQ-32).
    recorder
        .record(
            &context.agent_id,
            action,
            Decision::Allow,
            authorisation.checks(),
        )
        .map_err(|diagnostic| BrokerRefusal::AuditWriteFailed { diagnostic })?;
    let record_id = RECORD_SEQUENCE.fetch_add(1, Ordering::Relaxed);

    // The single, non-test call site of `actuator_git::execute` in the
    // whole repository (REQ-36). Reachable only from this point, which
    // already holds the successful write's result. No fourth gate exists
    // between the write above and this call (REQ-39).
    let operation = match operation_for(authorisation) {
        Some(operation) => operation,
        None => return Err(BrokerRefusal::UnrecognisedAction),
    };

    match actuator_git::execute(&operation) {
        Ok(outcome) => Ok(ActuationReceipt {
            operation: outcome,
            record_id,
        }),
        // REQ-38: actuator-git's own refusal, carried through verbatim.
        Err(refusal) => Err(BrokerRefusal::ActuatorRefused(refusal)),
    }
}
