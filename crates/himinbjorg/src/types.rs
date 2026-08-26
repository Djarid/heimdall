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
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProposalDecision {
    pub decision: Decision,
    pub checks: Vec<CheckRecord>,
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
/// in step three (section 7): nothing can succeed, because the single
/// actuator slot is unimplemented (REQ-22).
#[derive(Debug)]
pub enum BrokerResult {}

/// The closed set of ways `broker_action` (a later phase of this issue) can
/// refuse (section 7). [`BrokerRefusal::NoActuatorAvailable`] is the only
/// variant reachable in step three: the single actuator slot behind
/// `broker_action` is unimplemented, so every call refuses with this
/// variant, never a success value (REQ-22).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BrokerRefusal {
    /// The single actuator slot behind `broker_action` is unimplemented.
    /// The only variant reachable in step three.
    NoActuatorAvailable,
    /// The credential scope is not permitted for the requested action.
    /// Declared for the interface's full shape; not exercised further than
    /// its own refusal arm in step three.
    ScopeNotPermitted,
}
