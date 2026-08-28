//! The fixed five-step sequence itself (PE-7, REQ-9 to REQ-12, REQ-20 to
//! REQ-24): the closed step vocabulary, the fixed array with its
//! compile-time length assertion, and the sequencing: the single
//! `himinbjorg::validate_proposal` call, the witness pass-through, a
//! fresh `himinbjorg::MinimalDecisionRecorder` per run, the single
//! `himinbjorg::broker_authorised_action` call, and the verbatim
//! refusal carry-through. No back edge anywhere in this module's own
//! control flow, and no adjudication of its own: the engine sequences,
//! it does not decide.

use crate::cognition::{CognitionStep, DefaultCognitionStep};
use crate::outcome::EngineOutcome;
use crate::proposal::build_proposal;
use crate::task::{EngineTask, is_task_well_formed};

/// The closed, five-variant step vocabulary (REQ-9), in the fixed order
/// [`STEP_SEQUENCE`] carries. "Result out" is [`run_sequence`]'s own
/// return value, not a sixth step.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EngineStep {
    /// Accept the task, checking its own structural well-formedness.
    AcceptTask,
    /// Obtain the cognition step's advisory content.
    Cognition,
    /// Turn the task and the cognition output into one proposal.
    ProposeAction,
    /// Call `himinbjorg::validate_proposal`, exactly once.
    Gate,
    /// Call `himinbjorg::broker_authorised_action`, exactly once, and
    /// only when the gate's decision was `Allow`.
    Execute,
}

/// The fixed sequence itself: exactly [`STEP_SEQUENCE`]'s own five
/// members, in this order, and no other. The `const _: () =
/// assert!(...)` below fails the BUILD, not a later test run, the moment
/// an edit adds or removes a step.
pub const STEP_SEQUENCE: [EngineStep; 5] = [
    EngineStep::AcceptTask,
    EngineStep::Cognition,
    EngineStep::ProposeAction,
    EngineStep::Gate,
    EngineStep::Execute,
];

const _: () = assert!(
    STEP_SEQUENCE.len() == 5,
    "STEP_SEQUENCE must carry exactly five steps (REQ-9): an edit that adds or removes a \
     step must fail the build, not a later test run"
);

/// The credential scope this crate presents to
/// `himinbjorg::broker_authorised_action` (REQ-23). A named engine
/// constant, not read from `himinbjorg::broker`'s own permitted-scope
/// allowlist (which this crate cannot even see: it is `pub(crate)` to
/// that crate alone): this value happens to be a member of that
/// allowlist, which is an agreement between two independently owned
/// lists, not a derivation, on `context::TARGET_SCOPE`'s own precedent
/// for the same relationship (REQ-18).
const ENGINE_CREDENTIAL_SCOPE: &str = "fixture-scope";

const _: () = assert!(
    !ENGINE_CREDENTIAL_SCOPE.is_empty(),
    "ENGINE_CREDENTIAL_SCOPE must be non-empty"
);

/// Resolves `himinbjorg::AgentContext` and `himinbjorg::EffectiveSurface`
/// for `task` over `cohort` (the accept-task step's own second half,
/// alongside [`is_task_well_formed`]): building either needs nothing
/// cognition contributes, so both are resolved before the cognition step
/// ever runs. On failure, the reason is carried in the same
/// `EngineOutcome::RefusedBeforeCognition` case the well-formedness
/// check uses (this is a structural precondition failure, never an
/// authorisation decision); in practice this path is defensive only,
/// because this crate always presents the one hardcoded agent id both
/// functions expect.
pub(crate) fn accept_task<'a>(
    task: &EngineTask,
    cohort: &'a hierarchy_vor::VerifiedCohort,
) -> Result<
    (himinbjorg::AgentContext<'a>, himinbjorg::EffectiveSurface<'a>),
    EngineOutcome,
> {
    if !is_task_well_formed(task) {
        return Err(EngineOutcome::RefusedBeforeCognition {
            reason: format!(
                "task_id {:?} is not structurally well formed: it is empty, or contains \
                 only whitespace",
                task.task_id,
            ),
        });
    }

    let agent_id = himinbjorg::AgentId::new(hierarchy_vor::cohort::COHORT_ID);
    let task_context = himinbjorg::TaskContext {
        task_id: task.task_id.clone(),
        target: task.target.clone(),
        declared_cost: task.declared_cost,
    };

    let context = himinbjorg::build_context(&agent_id, &task_context, cohort).map_err(|refusal| {
        EngineOutcome::RefusedBeforeCognition {
            reason: format!("himinbjorg::build_context refused: {refusal:?}"),
        }
    })?;
    let surface = himinbjorg::enforce_definition(&agent_id, cohort).map_err(|refusal| {
        EngineOutcome::RefusedBeforeCognition {
            reason: format!("himinbjorg::enforce_definition refused: {refusal:?}"),
        }
    })?;

    Ok((context, surface))
}

/// The gate step's own single call site of `himinbjorg::validate_proposal`
/// (REQ-20): genuinely called, never bypassed and never re-implemented
/// locally.
pub(crate) fn run_gate(
    context: &himinbjorg::AgentContext<'_>,
    surface: &himinbjorg::EffectiveSurface<'_>,
    proposal: &himinbjorg::Proposal,
) -> himinbjorg::ProposalDecision {
    himinbjorg::validate_proposal(context, surface, proposal)
}

/// The execute step's own single call site of
/// `himinbjorg::broker_authorised_action` (REQ-22, REQ-23): a fresh
/// `himinbjorg::MinimalDecisionRecorder` per call, and the witness passed
/// straight through, never reconstructed, never cloned and never
/// synthesised.
pub(crate) fn run_execute(
    context: &himinbjorg::AgentContext<'_>,
    task: &EngineTask,
    authorisation: &himinbjorg::Authorisation,
) -> Result<himinbjorg::ActuationReceipt, himinbjorg::BrokerRefusal> {
    let action = himinbjorg::Action {
        action_name: task.action_name.clone(),
        target: task.target.clone(),
    };
    let credential_scope = himinbjorg::Scope::new(ENGINE_CREDENTIAL_SCOPE);
    let mut recorder = himinbjorg::MinimalDecisionRecorder::new();

    himinbjorg::broker_authorised_action(
        context,
        &action,
        &credential_scope,
        authorisation,
        &mut recorder,
    )
}

/// Runs the fixed five-step sequence with a caller-supplied cognition
/// implementation (REQ-11's mandatory-shell pattern, `pub(crate)` only:
/// the crate's one PUBLIC entry point is [`run_sequence`] below, which
/// supplies [`DefaultCognitionStep`]). Reachable from this crate's own
/// unit-test modules for cognition-substitution testing (AC-17), and
/// from [`run_sequence`] itself; reachable from nowhere outside the
/// crate.
///
/// Each step of [`STEP_SEQUENCE`] runs at most once, in order, and this
/// function returns: there is no loop, no recursion and no branch that
/// returns control to an earlier step (REQ-10).
pub(crate) fn run_sequence_with_cognition(
    cohort: &hierarchy_vor::VerifiedCohort,
    task: &EngineTask,
    cognition: &impl CognitionStep,
) -> EngineOutcome {
    // Step one: AcceptTask.
    let (context, surface) = match accept_task(task, cohort) {
        Ok(resolved) => resolved,
        Err(outcome) => return outcome,
    };

    // Step two: Cognition. Advisory only (REQ-15): nothing below derives
    // a permission, a scope or a check outcome from its output.
    let cognition_output = cognition.propose(task);

    // Step three: ProposeAction. The one Proposal construction site in
    // this crate is `crate::proposal::build_proposal` alone.
    let proposal = build_proposal(task, &cognition_output);

    // Step four: Gate. The one and only call to validate_proposal for
    // this run.
    let decision = run_gate(&context, &surface, &proposal);
    if decision.decision != himinbjorg::Decision::Allow {
        return EngineOutcome::GateBlocked {
            checks: decision.checks,
        };
    }
    let authorisation = match decision.authorisation() {
        Some(authorisation) => authorisation,
        // Structurally unreachable given `Decision::Allow` above
        // (`himinbjorg::validate_proposal`'s own guarantee), retained as
        // defence in depth only, following
        // `himinbjorg::DefinitionRefusal::EmptyIntersection`'s own
        // precedent for naming such a branch honestly.
        None => {
            return EngineOutcome::GateBlocked {
                checks: decision.checks,
            };
        }
    };

    // Step five: Execute. The witness obtained above is passed straight
    // through, at most once, to the one call site of
    // broker_authorised_action for this run.
    match run_execute(&context, task, authorisation) {
        Ok(receipt) => EngineOutcome::Executed { receipt },
        Err(refusal) => EngineOutcome::BrokerRefused { refusal },
    }
}

/// The crate's one public entry point (REQ-11): runs the fixed five-step
/// sequence over `task`, using [`DefaultCognitionStep`]. `cohort` is an
/// already-verified `&hierarchy_vor::VerifiedCohort`; this function never
/// loads one itself (REQ-26).
pub fn run_sequence(cohort: &hierarchy_vor::VerifiedCohort, task: &EngineTask) -> EngineOutcome {
    run_sequence_with_cognition(cohort, task, &DefaultCognitionStep)
}
