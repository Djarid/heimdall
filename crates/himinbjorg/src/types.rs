//! Himinbjörg's own value shapes (REQ-6, section 7 of
//! `.opencode/plans/himinbjorg-step-three.md`). No logic, no decision-making
//! anywhere in this module: every item below is a plain data shape, plus the
//! narrow constructors ([`AgentId::new`], [`Scope::new`]) needed because their
//! one field is private. No function here returns [`Decision`], a refusal or
//! a [`CheckOutcome`] as the *result of evaluating anything*: [`Decision`],
//! [`CheckOutcome`] and the refusal enums are declared here only as closed
//! vocabularies, exactly as `crate::types` is scoped to (`context`,
//! `definition`, `validation`, `gate_bridge`, `sinks` and `broker` are where
//! any comparison against a hardcoded constant, and any decision, actually
//! happens).
//!
//! **REQ-8, carried structurally, not merely asserted.** [`AgentContext`]
//! carries no raw-content field of any kind, transitively: no payload, no
//! content window, no free-form external text field. Its `task` field is
//! [`TaskContext`], which itself carries only a task id, a target and a
//! declared cost -- no free-form external text field either. There is also
//! no world-model subgraph field anywhere on [`AgentContext`]: absent, not
//! empty, because there is no Rust Mímisbrunnr for this step to query
//! (HB3-4).
//!
//! **REQ-20, carried structurally.** No cohort, cohort surface or sink
//! registry type appears behind an `Option` anywhere in this module.
//! [`EffectiveSurface::cohort_surface`] is a plain, owned
//! `hierarchy_vor::CohortSurface<'a>`, never an `Option` of one, and no
//! refusal enum below carries a fallback value of any of those three types.

/// A newtype over an owned agent identity string (section 7). Compared by
/// equality only, against the one hardcoded agent id `context` and
/// `definition` each hold (a later phase of this issue); this module carries
/// no comparison of its own.
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct AgentId(String);

impl AgentId {
    /// Builds an `AgentId` from any owned-or-borrowed string source.
    pub fn new(id: impl Into<String>) -> Self {
        AgentId(id.into())
    }

    /// The identity string, borrowed.
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

/// The task's identifier, its declared target and its declared cost (section
/// 7, literally). Feeds checks two, four and six (a later phase). No
/// free-form external text field: `task_id` and `target` are both
/// caller-supplied identifiers, not content.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TaskContext {
    pub task_id: String,
    pub target: String,
    pub declared_cost: u32,
}

/// The gateway's fixed context for one agent over one task (section 7).
/// **No** raw-content field, transitively (REQ-8), and **no** world-model
/// subgraph field (HB3-4): both are structural properties of this exact
/// field set, not defaults that a later edit could quietly widen back in.
///
/// Every field is `pub(crate)`: only `context` (a later phase of this issue,
/// via `build_context`) constructs a value of this type, and only
/// `validation` (also a later phase) reads its fields when sequencing the
/// six checks. No field is public, so no caller outside this crate -- and no
/// caller inside it other than `context` and `validation` -- can construct,
/// widen or narrow one directly.
pub struct AgentContext<'a> {
    /// The one hardcoded agent this context was built for.
    pub(crate) agent_id: AgentId,
    /// The identity summary, borrowed from the cohort surface (its
    /// `cohort_id`), never copied into an owned field.
    pub(crate) identity: &'a str,
    /// Himinbjörg's own hardcoded, non-empty set of standing constraints
    /// (check three's input; the constants themselves live in `context`, a
    /// later phase of this issue).
    pub(crate) standing_constraints: &'a [&'static str],
    /// The task this context was built over.
    pub(crate) task: TaskContext,
    /// The hardcoded control-channel entries this context carries.
    pub(crate) control_channel: &'a [&'static str],
    /// Himinbjörg's own hardcoded, non-empty target scope (check two's
    /// input). An empty scope means nothing is in scope, never everything
    /// (HB3-4, EC-9).
    pub(crate) target_scope: &'a [&'static str],
    /// The hardcoded blast-radius bound (check four's input).
    pub(crate) blast_radius_bound: usize,
    /// The hardcoded resource ceiling (check six's input).
    pub(crate) resource_ceiling: u32,
}

/// The closed set of ways [`crate::build_context`] (a later phase of this
/// issue) can refuse (section 7). No variant carries a fallback context:
/// every arm below is a bare, dataless refusal.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ContextRefusal {
    /// `agent_id` is not the one hardcoded agent.
    UnknownAgent,
    /// The cohort's `trust_ceiling` does not byte-equal the hardcoded
    /// expected constant.
    CeilingMismatch,
}

/// The resolved, effective control surface for one agent (section 7): the
/// intersected permitted-action set, the byte-equal-verified ceiling, and a
/// borrow of the cohort surface. Read-only: no setter, no interior
/// mutability anywhere on this type. Every field is `pub(crate)`, for the
/// same reason [`AgentContext`]'s fields are: only `definition` constructs
/// one (via `enforce_definition`, a later phase), and only `validation` and
/// `gate_bridge` (also later phases) read from it.
pub struct EffectiveSurface<'a> {
    /// The **intersection** of Himinbjörg's hardcoded global default action
    /// set and the verified cohort's `permitted_actions`, never the union
    /// and never the cohort's set as requested (HB-3, REQ-9).
    pub(crate) permitted_actions: Vec<String>,
    /// The cohort's own trust ceiling, borrowed, already verified
    /// byte-equal against the hardcoded expected constant by the time this
    /// value exists. Never ranked, parsed or ordered anywhere in this
    /// crate (HB3-9).
    pub(crate) trust_ceiling: &'a str,
    /// The verified cohort's own read-only projection, owned here as a
    /// plain value, never behind an `Option` (REQ-20).
    pub(crate) cohort_surface: hierarchy_vor::CohortSurface<'a>,
}

/// The closed set of ways [`crate::enforce_definition`] (a later phase of
/// this issue) can refuse (section 7). [`DefinitionRefusal::EmptyIntersection`]
/// is unreachable via the compile-time assertion `definition` carries (a
/// later phase), but is retained as defence in depth, following
/// `hierarchy_vor::cohort::CohortRefusal::ContentIntegrity`'s own precedent.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DefinitionRefusal {
    /// `agent_id` is not the one hardcoded agent.
    UnknownAgent,
    /// The cohort's `trust_ceiling` does not byte-equal the hardcoded
    /// expected constant.
    CeilingMismatch,
    /// The intersection of Himinbjörg's global default action set and the
    /// cohort's `permitted_actions` is empty. Structurally unreachable
    /// (defence in depth only): see this enum's own doc comment.
    EmptyIntersection,
}

/// One parameter a [`Proposal`] consumes (section 7's "Proposal" row: "the
/// parameters it consumes with each parameter's consume mode, each
/// parameter's trust level and each parameter's type name"). Deliberately
/// **no** `action_critical` field: it is derived, never accepted from the
/// proposer (REQ-17).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProposalParameter {
    pub id: String,
    pub consume_mode: boundary_gjoll::types::ConsumeMode,
    pub trust_level: boundary_gjoll::types::TrustLevel,
    pub type_name: String,
}

/// A proposed action, in Himinbjörg's own shape (section 7). Translated into
/// `boundary_gjoll::types::ActionProposal` by `gate_bridge` (a later phase of
/// this issue), never constructed as one directly by a proposer.
/// Deliberately **no** `action_critical` field anywhere on this type or on
/// [`ProposalParameter`] (REQ-17).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Proposal {
    pub action_name: String,
    pub target: String,
    pub sink: String,
    pub parameters: Vec<ProposalParameter>,
    pub declared_cost: u32,
}

/// The closed, six-variant, ordered enum of checks `validate_proposal` (a
/// later phase of this issue) sequences, in the order
/// `plans/dd/himinbjorg.md` section 5.1 fixes (section 7). Exhaustively
/// matched wherever it is matched at all, so a seventh check forces every
/// match to be revisited.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CheckId {
    /// Check one: the action type exists in the agent's permitted action
    /// space.
    ActionPermitted,
    /// Check two: the target is in scope.
    TargetInScope,
    /// Check three: no constraint axiom is violated.
    ConstraintSatisfied,
    /// Check four: blast radius within authorised bounds.
    BlastRadiusWithinBound,
    /// Check five: taint compatibility, the real Gjöll gate call.
    TaintCompatible,
    /// Check six: resource budget not exceeded.
    ResourceBudgetNotExceeded,
}

/// One check's own recorded outcome (section 7). [`CheckOutcome::NotEvaluated`]
/// never contributes to an `Allow` (REQ-10): the decision is `Allow` if and
/// only if every one of the six records is [`CheckOutcome::Pass`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CheckOutcome {
    Pass,
    Fail { reasons: Vec<String> },
    NotEvaluated { because: String },
}

/// `(CheckId, CheckOutcome)` (section 7, literally). The six records
/// `validate_proposal` (a later phase) returns are the HB-6 audit payload
/// (REQ-23).
pub type CheckRecord = (CheckId, CheckOutcome);

/// The authorisation witness (GA-1, REQ-26 to REQ-28 of
/// `.opencode/plans/git-actuator-step-four.md`). Opaque: every field is
/// private, there is no public constructor, no public conversion, no
/// `Clone`, no `Copy`, no `Default` and no `cfg` escape hatch a downstream
/// caller could enable, following `hierarchy_vor::VerifiedCohort`'s own
/// precedent (REQ-26). The only way to obtain one is
/// [`crate::validation::validate_proposal`] returning a [`Decision::Allow`]
/// and reading it back through [`ProposalDecision::authorisation`]; the only
/// place one is constructed at all is [`Authorisation::new`], `pub(crate)`
/// and called from nowhere but `validation` (REQ-27).
///
/// It is not a bare token (REQ-28): it identifies the action name, the
/// target and the sink it authorises, and carries the six [`CheckRecord`]s
/// that produced it, all read back through the accessors below.
#[derive(Debug)]
pub struct Authorisation {
    action_name: String,
    target: String,
    sink: String,
    checks: Vec<CheckRecord>,
}

impl Authorisation {
    /// The only constructor, `pub(crate)` so no caller outside this crate
    /// can mint one directly (REQ-26). Called from exactly one place:
    /// `validation::validate_proposal`, and only when its decision is
    /// [`Decision::Allow`] (REQ-27).
    pub(crate) fn new(
        action_name: String,
        target: String,
        sink: String,
        checks: Vec<CheckRecord>,
    ) -> Self {
        Authorisation {
            action_name,
            target,
            sink,
            checks,
        }
    }

    /// The action name this witness authorises.
    pub fn action_name(&self) -> &str {
        &self.action_name
    }

    /// The target this witness authorises.
    pub fn target(&self) -> &str {
        &self.target
    }

    /// The sink this witness authorises.
    pub fn sink(&self) -> &str {
        &self.sink
    }

    /// The six [`CheckRecord`]s that produced this witness, every one
    /// [`CheckOutcome::Pass`] (REQ-27, REQ-28).
    pub fn checks(&self) -> &[CheckRecord] {
        &self.checks
    }
}

/// The closed four-variant decision vocabulary
/// `plans/dd/himinbjorg.md` section 5.2 names (section 7, REQ-21).
/// [`Decision::Queue`] and [`Decision::Escalate`] are declared here and
/// nowhere else, but neither is ever constructed by any non-test code path
/// in this crate at this build step: `Queue` needs Gjallarhorn's protected
/// authorisation channel, which does not exist yet, and `Escalate` needs
/// Hliðskjálf's escalation record, which does not exist yet either.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Decision {
    Allow,
    Block,
    /// Reserved, never constructed in step three: needs Gjallarhorn's
    /// protected authorisation channel (HB3-6).
    Queue,
    /// Reserved, never constructed in step three: needs Hliðskjálf's
    /// escalation record (HB3-6).
    Escalate,
}

/// `validate_proposal`'s (a later phase of this issue) return type (section
/// 6.1's "Naming correction to carry forward": this is named
/// `ProposalDecision`, not `ValidationOutcome`, because
/// `boundary_gjoll::declaration` already exports a type of that name).
/// `Allow` if and only if all six [`CheckRecord`]s are `Pass` (REQ-10).
///
/// `authorisation` is `pub(crate)` because [`Authorisation`] itself has no
/// public constructor: only `validate_proposal` ever sets it, and only to
/// `Some` when `decision == Decision::Allow` (REQ-27). It carries no
/// `Clone`, `PartialEq` or `Eq` derive as a consequence: [`Authorisation`]
/// implements none of the three by design (REQ-26), so this type does not
/// either. Nothing in this crate or its tests relies on comparing or
/// cloning a whole `ProposalDecision` value; only its `decision` and
/// `checks` fields, and the [`ProposalDecision::authorisation`] accessor,
/// are read anywhere.
#[derive(Debug)]
pub struct ProposalDecision {
    pub decision: Decision,
    pub checks: Vec<CheckRecord>,
    pub(crate) authorisation: Option<Authorisation>,
}

impl ProposalDecision {
    /// `Some` if and only if `decision == Decision::Allow` (REQ-27): a
    /// witness is minted exactly when all six [`CheckRecord`]s are
    /// [`CheckOutcome::Pass`], never on [`Decision::Block`], and
    /// [`Decision::Queue`] and [`Decision::Escalate`] stay unconstructed
    /// anywhere in this crate, so neither can reach this accessor at all.
    pub fn authorisation(&self) -> Option<&Authorisation> {
        self.authorisation.as_ref()
    }
}

/// `broker_action`'s (a later phase of this issue) input action: the action
/// name and its target (section 7).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Action {
    pub action_name: String,
    pub target: String,
}

/// A named credential scope, opaque, never ranked (section 7).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Scope(String);

impl Scope {
    /// Builds a `Scope` from any owned-or-borrowed string source.
    pub fn new(name: impl Into<String>) -> Self {
        Scope(name.into())
    }

    /// The scope's own name, borrowed.
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

/// `broker_action`'s (a later phase of this issue) success type. Uninhabited
/// in step three, and **still** uninhabited now that an actuator exists
/// behind [`crate::broker::broker_authorised_action`] instead (section 7,
/// section 5.2 of `.opencode/plans/git-actuator-step-four.md`): nothing can
/// succeed through `broker_action`, because its three arguments carry no
/// authorisation evidence and it must not become a second execution path
/// (REQ-30). No `Ok` value of this type is constructible anywhere, by any
/// caller, so that is a structural property of the type, not merely an
/// unenforced convention. [`crate::broker::broker_authorised_action`] uses
/// [`ActuationReceipt`] instead, a separate, inhabited type.
#[derive(Debug)]
pub enum BrokerResult {}

/// The closed set of ways `broker_action` and
/// `broker_authorised_action` (`.opencode/plans/git-actuator-step-four.md`,
/// REQ-26 to REQ-39) can refuse (section 7, section 5.2). Additive over
/// step three's two variants; every match over this enum in this crate
/// carries no wildcard arm, so a future variant forces every match site to
/// be revisited (EC-18).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BrokerRefusal {
    /// The actuator itself is genuinely unavailable. Declared for the
    /// interface's full shape; not the reason `broker_action` refuses any
    /// more (that would be a false statement now that an actuator exists,
    /// REQ-30): retained for a genuine future case in which the actuator
    /// slot behind `broker_authorised_action` cannot be reached at all,
    /// distinct from the actuator being reached and then refusing (which is
    /// [`BrokerRefusal::ActuatorRefused`] instead). Unconstructed by any
    /// non-test path at this build step, following [`Decision::Queue`] and
    /// [`Decision::Escalate`]'s own precedent for a declared-but-currently-
    /// unreachable variant.
    NoActuatorAvailable,
    /// The credential scope is not permitted for the requested action. The
    /// scope check runs first, and is real, on both entry points (REQ-37).
    ScopeNotPermitted,
    /// `broker_action`'s own corrected refusal reason (REQ-30): its three
    /// arguments carry no authorisation evidence, so it can never authorise
    /// anything and always refuses with this variant once the scope check
    /// clears. Replaces `NoActuatorAvailable` for this case, which would be
    /// a false statement now that an actuator exists behind
    /// `broker_authorised_action`.
    NoAuthorisationEvidence,
    /// `broker_authorised_action`'s witness-match refusal (REQ-29): the
    /// action it was asked to broker does not byte-equal, on both action
    /// name and target, the action the supplied [`Authorisation`]
    /// authorises. A witness for one action never authorises a different
    /// one (EC-11).
    WitnessMismatch,
    /// `broker_authorised_action`'s audit-write refusal (REQ-31, REQ-32):
    /// the [`crate::audit::DecisionRecorder`] write failed, so the action
    /// does not execute. An unlogged decision is treated as no decision
    /// (HK-4): there is no branch on which the actuator is invoked after a
    /// failed or skipped write.
    AuditWriteFailed {
        /// The recorder's own diagnostic, carried through unmodified.
        diagnostic: String,
    },
    /// `broker_authorised_action`'s mapping of an authorised action name to
    /// an `actuator_git::GitOperation` failed to recognise the action
    /// (defence in depth only, following `DefinitionRefusal::EmptyIntersection`'s
    /// precedent): structurally unreachable in practice, because check one
    /// of `validate_proposal` never mints a witness for an action name
    /// outside `hierarchy_vor::cohort::PERMITTED_ACTIONS`'s own two members,
    /// which this module's mapping already covers exhaustively. Never
    /// described as the mechanism that restricts which actions can execute;
    /// that restriction is check one's, and the witness match's.
    UnrecognisedAction,
    /// `actuator-git`'s own refusal, carried through verbatim, dropping
    /// nothing (REQ-38, following `gate_bridge::evaluate_taint_compatibility`'s
    /// REQ-19 precedent for the gate's own reasons). Two different
    /// `actuator_git::ActuationRefusal` variants always map to two
    /// different values here: this variant wraps the whole enum rather than
    /// collapsing it to an opaque marker.
    ActuatorRefused(actuator_git::ActuationRefusal),
}

/// Himinbjörg's own success shape for `broker_authorised_action` (REQ-25,
/// REQ-38 of `.opencode/plans/git-actuator-step-four.md`), wrapping what
/// `actuator-git` reported and binding the executed action to the identity
/// of the record [`crate::audit::DecisionRecorder::record`] wrote before the
/// actuator ran (REQ-31). `record_id` is a sequence number local to this
/// process, assigned once the audit write for this call has already
/// succeeded (REQ-33's structural ordering): it identifies which call
/// produced this receipt, not a durable identifier the recorder itself
/// returned, because [`crate::audit::DecisionRecorder::record`]'s own
/// contract (REQ-31) reports success or failure only, never an identity.
/// A future recorder with its own durable identifier is one of the things a
/// real Hliðskjálf would add (deferred, `plans/dd/hlidskjalf.md`).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ActuationReceipt {
    /// What `actuator-git` reported as having happened, and nothing it did
    /// not observe (REQ-25): no commit identifier, no field derived from
    /// parsing git's own output.
    pub operation: actuator_git::ActuationOutcome,
    /// This process's own sequence number for the audit write that preceded
    /// this receipt (see this type's own doc comment for the honest limit
    /// on what "identity" means here).
    pub record_id: usize,
}
