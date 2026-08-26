//! `validate_proposal`, the six-check sequence, the non-short-circuiting
//! record and the `Allow`-iff-six-passes rule (REQ-10 to REQ-16, REQ-21,
//! REQ-23, section 5.4 and section 6.1 of
//! `.opencode/plans/himinbjorg-step-three.md`, section 13 file 10).
//!
//! **The six checks, in `plans/dd/himinbjorg.md` section 5.1's own order,
//! and never short-circuiting (REQ-10).** Every one of the six checks below
//! runs and contributes its own recorded [`crate::types::CheckOutcome`],
//! whatever the outcome of any earlier check was, so a reviewer sees every
//! cause of a `Block`, not only the first. [`validate_proposal`] computes
//! the decision only after all six have run: `Allow` **if and only if**
//! every one of the six records is [`crate::types::CheckOutcome::Pass`]. Any
//! `Fail`, and any `NotEvaluated`, yields `Block`. This module never
//! constructs [`crate::types::Decision::Queue`] or
//! [`crate::types::Decision::Escalate`] (HB3-6, REQ-21): only `Allow` and
//! `Block` are ever returned.
//!
//! **Check one, action permitted (REQ-11).** Real, evaluated against the
//! effective surface [`crate::definition::enforce_definition`] produced:
//! the action must be a member of `surface.permitted_actions` (the
//! intersection) AND `hierarchy_vor::CohortSurface::may_perform` must also
//! confirm it for the cohort half of that same intersection. Both halves
//! are checked, per REQ-11's own wording ("via
//! `hierarchy_vor::CohortSurface::may_perform` for the cohort half of the
//! intersection"), so a future edit that widens `permitted_actions` without
//! the cohort's own agreement cannot silently pass this check.
//!
//! **Check two, target in scope (REQ-12, HB3-4).** Evaluated against
//! `context`'s own hardcoded, non-empty target scope. An empty scope means
//! nothing is in scope, never everything; membership is a positive match
//! against that named scope, never a denylist of excluded targets (REQ-25).
//!
//! **Check three, no constraint axiom violated (REQ-13, REQ-25).** Evaluated
//! against `context`'s own hardcoded, non-empty constraint set. Each named
//! constraint earns its pass by a positive match against a condition this
//! module states explicitly for that constraint's own name, never by an
//! enumerated list of forbidden proposal shapes: [`constraint_is_satisfied`]
//! is the one function that owns every such condition, and a constraint name
//! this function does not recognise earns no positive match and therefore
//! fails closed, exactly as invariant 3.5 requires for silence.
//!
//! **Check four, blast radius within bound (REQ-14).** Evaluated against
//! `context`'s own hardcoded numeric bound, computed from the proposal
//! alone (`proposal.parameters.len()`, the number of parameters the
//! proposal itself declares it consumes). Stateless: no counter, no cell,
//! no lock, no atomic anywhere in this module or this crate.
//!
//! **Check five, taint compatibility (REQ-15).** Delegates entirely to
//! [`crate::gate_bridge::evaluate_taint_compatibility`], the crate's one
//! call site of `boundary_gjoll::consequentiality::evaluate` (REQ-15,
//! REQ-28). This module does not reimplement, branch around, or otherwise
//! reconstruct the gate's rule locally: it supplies the registry
//! ([`crate::sinks::registry`]) and the cohort surface and reads back
//! whatever [`crate::types::CheckOutcome`] `gate_bridge` already produced.
//! `gate_bridge::evaluate_taint_compatibility` itself carries REQ-19's
//! fail-closed mapping (a gate refusal becomes `Fail`, never `Allow`,
//! `Queue` or `Escalate`, and the gate's own reasons are carried verbatim);
//! this module inherits that guarantee rather than re-stating it.
//!
//! **Check six, resource budget not exceeded (REQ-16).** Evaluated as
//! `proposal.declared_cost` against `context`'s own hardcoded resource
//! ceiling. Stateless, for the same reason check four is.

use crate::gate_bridge::evaluate_taint_compatibility;
use crate::sinks;
use crate::types::{
    AgentContext, CheckId, CheckOutcome, CheckRecord, Decision, EffectiveSurface, Proposal,
    ProposalDecision,
};

/// Check one (REQ-11): the action exists in the agent's permitted action
/// space. Both halves of `surface` are consulted: membership in the
/// intersection `enforce_definition` produced, and, independently,
/// `hierarchy_vor::CohortSurface::may_perform` for the cohort half of that
/// same intersection. A positive match against both is required to pass
/// (REQ-25): there is no denylist of forbidden action names anywhere here.
fn check_action_permitted(surface: &EffectiveSurface<'_>, proposal: &Proposal) -> CheckOutcome {
    let in_effective_surface = surface.permitted_actions.contains(&proposal.action_name);
    let cohort_permits = surface.cohort_surface.may_perform(&proposal.action_name);

    if in_effective_surface && cohort_permits {
        CheckOutcome::Pass
    } else {
        CheckOutcome::Fail {
            reasons: vec![format!(
                "action {:?} is not permitted: member of Himinbjörg's effective (intersected) \
                 action set = {in_effective_surface}, hierarchy_vor::CohortSurface::may_perform \
                 = {cohort_permits}; both must hold",
                proposal.action_name,
            )],
        }
    }
}

/// Check two (REQ-12, HB3-4): the target is in scope, per `context`'s own
/// hardcoded, non-empty target scope. An empty scope would mean nothing is
/// in scope, never everything; membership here is a positive match against
/// that named scope (REQ-25).
fn check_target_in_scope(context: &AgentContext<'_>, proposal: &Proposal) -> CheckOutcome {
    let in_scope = context
        .target_scope
        .iter()
        .any(|scoped_target| *scoped_target == proposal.target);

    if in_scope {
        CheckOutcome::Pass
    } else {
        CheckOutcome::Fail {
            reasons: vec![format!(
                "target {:?} is absent from Himinbjörg's hardcoded target scope",
                proposal.target,
            )],
        }
    }
}

/// Whether `proposal` positively satisfies the one named `constraint`
/// (REQ-13, REQ-25). Every arm states its own positive condition explicitly;
/// a constraint name this function does not recognise earns no positive
/// match and therefore fails closed (the wildcard arm), exactly as
/// invariant 3.5 requires silence to fail closed. This is the ONLY place in
/// the crate that names a constraint's own trigger condition.
fn constraint_is_satisfied(
    constraint: &str,
    context: &AgentContext<'_>,
    proposal: &Proposal,
) -> bool {
    match constraint {
        // Positively stated: the proposal's own target must not be the
        // agent's own identity. A proposal acting on some external target
        // earns this constraint's pass; a proposal acting on the agent
        // itself does not, because that is exactly what "self-elevating"
        // names.
        "constraint:no-self-elevating-action" => proposal.target != context.identity,
        // An unrecognised constraint name is silence, and silence fails
        // closed (REQ-25, invariant 3.5): it is never read as a vacuous
        // pass.
        _ => false,
    }
}

/// Check three (REQ-13): no constraint axiom is violated, evaluated against
/// `context`'s own hardcoded, non-empty constraint set. Every named
/// constraint is checked; the proposal must positively satisfy all of them
/// to pass, and every violated constraint is named in the failure, so the
/// check never short-circuits on the first one internally either.
fn check_constraint_satisfied(context: &AgentContext<'_>, proposal: &Proposal) -> CheckOutcome {
    let violated: Vec<String> = context
        .standing_constraints
        .iter()
        .filter(|constraint| !constraint_is_satisfied(constraint, context, proposal))
        .map(|constraint| {
            format!(
                "constraint {constraint:?} is violated by action {:?} against target {:?}",
                proposal.action_name, proposal.target,
            )
        })
        .collect();

    if violated.is_empty() {
        CheckOutcome::Pass
    } else {
        CheckOutcome::Fail { reasons: violated }
    }
}

/// Check four (REQ-14): blast radius within the hardcoded bound, computed
/// from the proposal alone as its own declared parameter count. Stateless:
/// no counter, no cell, no lock, no atomic anywhere in this crate.
fn check_blast_radius_within_bound(
    context: &AgentContext<'_>,
    proposal: &Proposal,
) -> CheckOutcome {
    let blast_radius = proposal.parameters.len();

    if blast_radius <= context.blast_radius_bound {
        CheckOutcome::Pass
    } else {
        CheckOutcome::Fail {
            reasons: vec![format!(
                "blast radius {blast_radius} (proposal.parameters.len()) exceeds the hardcoded \
                 bound {}",
                context.blast_radius_bound,
            )],
        }
    }
}

/// Check five (REQ-15): taint compatibility, the real Gjöll gate call.
/// Delegates entirely to [`crate::gate_bridge::evaluate_taint_compatibility`]
/// -- the crate's one call site of `boundary_gjoll::consequentiality::evaluate`
/// -- supplying [`crate::sinks::registry`]'s own registry and the effective
/// surface's cohort projection. No branch here reaches an outcome without
/// that call, and no branch reconstructs the gate's rule locally.
fn check_taint_compatible(surface: &EffectiveSurface<'_>, proposal: &Proposal) -> CheckOutcome {
    let registry = sinks::registry();
    evaluate_taint_compatibility(proposal, &surface.cohort_surface, &registry)
}

/// Check six (REQ-16): resource budget not exceeded, evaluated as the
/// proposal's own declared cost against `context`'s hardcoded resource
/// ceiling. Stateless, for the same reason check four is (REQ-14's
/// reasoning, restated for check six by REQ-16).
fn check_resource_budget_not_exceeded(
    context: &AgentContext<'_>,
    proposal: &Proposal,
) -> CheckOutcome {
    if proposal.declared_cost <= context.resource_ceiling {
        CheckOutcome::Pass
    } else {
        CheckOutcome::Fail {
            reasons: vec![format!(
                "declared cost {} exceeds the hardcoded resource ceiling {}",
                proposal.declared_cost, context.resource_ceiling,
            )],
        }
    }
}

/// Sequences all six checks of `plans/dd/himinbjorg.md` section 5.1, in that
/// order, without short-circuiting (REQ-10): every check runs and
/// contributes its own recorded [`CheckOutcome`], regardless of any earlier
/// check's outcome. The decision is [`Decision::Allow`] if and only if all
/// six records are [`CheckOutcome::Pass`]; any [`CheckOutcome::Fail`], and
/// any [`CheckOutcome::NotEvaluated`], yields [`Decision::Block`]. This
/// function never constructs [`Decision::Queue`] or [`Decision::Escalate`]
/// (HB3-6, REQ-21).
pub fn validate_proposal(
    context: &AgentContext<'_>,
    surface: &EffectiveSurface<'_>,
    proposal: &Proposal,
) -> ProposalDecision {
    let checks: Vec<CheckRecord> = vec![
        (
            CheckId::ActionPermitted,
            check_action_permitted(surface, proposal),
        ),
        (
            CheckId::TargetInScope,
            check_target_in_scope(context, proposal),
        ),
        (
            CheckId::ConstraintSatisfied,
            check_constraint_satisfied(context, proposal),
        ),
        (
            CheckId::BlastRadiusWithinBound,
            check_blast_radius_within_bound(context, proposal),
        ),
        (
            CheckId::TaintCompatible,
            check_taint_compatible(surface, proposal),
        ),
        (
            CheckId::ResourceBudgetNotExceeded,
            check_resource_budget_not_exceeded(context, proposal),
        ),
    ];

    // Allow iff and only if all six are Pass (REQ-10). A Fail or a
    // NotEvaluated anywhere yields Block; Queue and Escalate are never
    // constructed in this module (HB3-6, REQ-21).
    let decision = if checks
        .iter()
        .all(|(_, outcome)| matches!(outcome, CheckOutcome::Pass))
    {
        Decision::Allow
    } else {
        Decision::Block
    };

    ProposalDecision { decision, checks }
}
