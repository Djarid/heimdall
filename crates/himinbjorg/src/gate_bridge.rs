//! `action_critical_for` (the only reader of
//! `hierarchy_vor::CohortSurface::consequential_sinks`), the translation into
//! `boundary_gjoll`'s input shapes, the single
//! `boundary_gjoll::consequentiality::evaluate` call site, and the mapping of
//! `GateDecision` to a `CheckOutcome` (REQ-15, REQ-17, REQ-19, section 5.5
//! and section 6.2 of `.opencode/plans/himinbjorg-step-three.md`, section 13
//! file 9).
//!
//! **Two binding rules, each held by exactly one function in this module and
//! nowhere else in the crate:**
//!
//! 1. [`action_critical_for`] is the ONLY place in the crate that reads
//!    [`hierarchy_vor::CohortSurface::consequential_sinks`] (REQ-17). The
//!    determination is the D24 agent-scoped MEMBERSHIP test: a parameter is
//!    action-critical when the sink the proposal targets is a member of the
//!    verified cohort's consequential-sink set. This is explicitly **not**
//!    flow-to-sink transitive reachability, which is invariant 3.6's own
//!    requirement and needs a world model this crate does not have (section
//!    10 and section 11 item two of the step-three spec); nothing in this
//!    module describes or implements the membership test as reachability.
//!    `action_critical_for` must not, and does not, derive its answer by
//!    routing the cohort's set into
//!    [`boundary_gjoll::consequentiality::evaluate`], must not, and does
//!    not, read `hierarchy_vor::cohort::CONSEQUENTIAL_SINKS` directly in
//!    place of the verified projection, and must not, and does not, take it
//!    from any sink self-declaration (`sinks::registry()` is never consulted
//!    here at all).
//! 2. [`evaluate_taint_compatibility`] is the ONLY place in the crate that
//!    calls [`boundary_gjoll::consequentiality::evaluate`] (REQ-15), called
//!    exactly once per proposal evaluation. There is no branch in this
//!    function that reaches a `CheckOutcome` without that call, and no
//!    branch that reconstructs the gate's rule locally.
//!
//! **The mapping (section 7's table), owned here and nowhere else:**
//!
//! | Himinbjörg source | `boundary_gjoll` field | Rule |
//! |---|---|---|
//! | `Proposal.action_name` | `ActionProposal.action_id` | Direct |
//! | `Proposal.sink` | `ActionProposal.sink` | Direct |
//! | `Proposal` parameters | `ActionProposal.consumes` | Keyed by each parameter's own id; consume mode carried through unchanged (`ProposalParameter::consume_mode` is already `boundary_gjoll::types::ConsumeMode`) |
//! | Always `false` | `ActionProposal.declared_safe` | Himinbjörg never asserts a proposal is safe; passing `false` keeps that visible |
//! | `Proposal` parameter trust level | `ClassifiedParameter.trust_level` | Direct |
//! | `Proposal` parameter type name | `ClassifiedParameter.type_name` | Reporting only |
//! | `CohortSurface::consequential_sinks()` membership of `Proposal.sink` | `ClassifiedParameter.action_critical` | The ONLY derived field (REQ-17), via [`action_critical_for`] |
//!
//! `action_critical` depends only on `proposal.sink`, which is the same for
//! every parameter of one proposal, so [`action_critical_for`] is called
//! exactly once per call to [`evaluate_taint_compatibility`] and its result
//! is reused for every parameter, not re-derived per parameter.
//!
//! **Fail-closed mapping back (REQ-19).** A
//! [`boundary_gjoll::types::GateDecision`] whose `authorised` field is
//! `false` becomes [`crate::types::CheckOutcome::Fail`], carrying the gate's
//! own reasons through verbatim: each reason's kind, sink, parameter id and
//! detail are all present in the formatted string, none dropped. It is never
//! converted to [`crate::types::CheckOutcome::Pass`], and this function
//! contains no retry of any kind: the mapping below is the single,
//! unconditional translation of whatever the one `evaluate` call above
//! returned.
//!
//! **REQ-20, carried structurally.** `surface` and `registry` are both plain
//! references on every signature in this module, never `Option`. Neither is
//! constructed, cloned, narrowed, hollowed, defaulted or substituted
//! anywhere here: `surface` is read only through
//! [`hierarchy_vor::CohortSurface::consequential_sinks`], and `registry` is
//! passed straight through to `evaluate` unchanged.

use std::collections::HashMap;

use crate::types::{CheckOutcome, Proposal, ProposalParameter};

/// The only reader of [`hierarchy_vor::CohortSurface::consequential_sinks`]
/// in this crate (REQ-17, section 6.2, literally). A D24 agent-scoped
/// MEMBERSHIP test, not flow-to-sink reachability (see this module's own doc
/// comment): `sink` is action-critical exactly when it is a member of
/// `surface`'s own consequential-sink set. `surface` is a plain reference,
/// never an `Option` (REQ-20); this function neither constructs, clones nor
/// narrows it, and reads nothing else from it.
pub(crate) fn action_critical_for(sink: &str, surface: &hierarchy_vor::CohortSurface<'_>) -> bool {
    surface
        .consequential_sinks()
        .iter()
        .any(|member_sink| member_sink == sink)
}

/// Translates one [`ProposalParameter`] into the gate's
/// [`boundary_gjoll::types::ClassifiedParameter`] shape (section 7's mapping
/// table): trust level and type name map directly; `action_critical` is the
/// caller-supplied, already-derived value.
fn classify(
    parameter: &ProposalParameter,
    action_critical: bool,
) -> boundary_gjoll::types::ClassifiedParameter {
    boundary_gjoll::types::ClassifiedParameter {
        assertion_id: parameter.id.clone(),
        type_name: parameter.type_name.clone(),
        trust_level: parameter.trust_level,
        action_critical,
    }
}

/// Formats one [`boundary_gjoll::types::Reason`] into a single string
/// carrying every one of its fields (REQ-19: the gate's reasons carried
/// through verbatim, nothing dropped), for storage in
/// [`crate::types::CheckOutcome::Fail`]'s `reasons: Vec<String>`.
fn format_reason(reason: boundary_gjoll::types::Reason) -> String {
    format!(
        "{:?} at sink {:?}, parameter {:?}: {}",
        reason.kind, reason.sink, reason.parameter_id, reason.detail
    )
}

/// Check five, taint compatibility (REQ-15, section 6.2, literally). The
/// ONLY call site of [`boundary_gjoll::consequentiality::evaluate`] in this
/// crate, called exactly once per call to this function (REQ-15, REQ-28).
/// `surface` and `registry` are both plain references, never `Option`
/// (REQ-20), matching the gate's own registry-mandatory shape.
pub(crate) fn evaluate_taint_compatibility(
    proposal: &Proposal,
    surface: &hierarchy_vor::CohortSurface<'_>,
    registry: &boundary_gjoll::declaration::SinkRegistry,
) -> CheckOutcome {
    // The ONLY derived field (REQ-17), computed once and reused for every
    // parameter below, because it depends only on `proposal.sink`.
    let action_critical = action_critical_for(&proposal.sink, surface);

    let mut consumes: HashMap<String, boundary_gjoll::types::ConsumeMode> = HashMap::new();
    let mut classified: HashMap<String, boundary_gjoll::types::ClassifiedParameter> =
        HashMap::new();
    for parameter in &proposal.parameters {
        consumes.insert(parameter.id.clone(), parameter.consume_mode);
        classified.insert(parameter.id.clone(), classify(parameter, action_critical));
    }

    let action_proposal = boundary_gjoll::types::ActionProposal {
        action_id: proposal.action_name.clone(),
        sink: proposal.sink.clone(),
        consumes,
        // Always false (section 7's mapping table): Himinbjörg never asserts
        // a proposal is safe. The gate re-derives authorisation regardless
        // of what is passed here.
        declared_safe: false,
    };

    // The single, mandatory call site (REQ-15, REQ-28). No branch above or
    // below this line reaches a CheckOutcome without it, and no branch
    // reconstructs the gate's rule locally.
    let decision =
        boundary_gjoll::consequentiality::evaluate(&action_proposal, &classified, registry);

    if decision.authorised {
        CheckOutcome::Pass
    } else {
        // REQ-19: fail closed, the gate's reasons carried through verbatim.
        // Never converted to Pass, never retried with different inputs.
        CheckOutcome::Fail {
            reasons: decision.reasons.into_iter().map(format_reason).collect(),
        }
    }
}
