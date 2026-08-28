//! The task shape the entry point accepts, and the structural
//! well-formedness predicate the accept-task step consults (REQ-32,
//! REQ-34, section 9.3's own statement of this module's one
//! responsibility: "carry the task shape and answer whether it is
//! structurally well formed. Knows nothing about permission").
//!
//! `action_name` lives on `EngineTask`, not on cognition's output,
//! deliberately: PE-9/REQ-32 requires a task to be able to name a
//! permitted action or a deliberately disallowed one, while the
//! cognition stub's own output stays fixed and hardcoded (REQ-14). If the
//! action came from cognition alone, the two directions of PE-9 could not
//! differ by task alone.
//!
//! [`is_task_well_formed`] answers a purely structural question -- is
//! this task's own identifier present at all -- and nothing about
//! permission, scope or budget. Its refusal is never described as an
//! authorisation decision anywhere in this crate (REQ-34): the only
//! authorisation decision in the sequence is
//! `himinbjorg::validate_proposal`'s own return value.

/// The task the entry point accepts (section 7 file 6 of
/// `.opencode/plans/process-engine-step-five-spec.md`). A plain data
/// shape: no method here decides anything about permission.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EngineTask {
    /// The task's own identifier. Structural well-formedness
    /// ([`is_task_well_formed`]) is the only property checked on this
    /// field anywhere in this crate.
    pub task_id: String,
    /// The action this task names. May name a permitted action or a
    /// deliberately disallowed one (REQ-32): nothing in this crate
    /// filters, rewrites or rejects a task on this field's basis.
    pub action_name: String,
    /// The target this task names.
    pub target: String,
    /// The sink this task declares (build-order step six, ST6-1, REQ-1).
    /// Lives here rather than on cognition's output for the same reason
    /// `action_name` lives here rather than there: a push task must be
    /// able to declare `sink:git.push` and a commit task
    /// `sink:git.commit`, and the two directions cannot differ by task
    /// alone unless the sink lives on the task, while the cognition
    /// stub's own output stays fixed and hardcoded. Before this field
    /// existed, every proposal declared the one sink `cognition.rs`
    /// hardcoded regardless of the task, which is the evidence-fidelity
    /// gap EC-24 names and REQ-5 closes.
    pub sink: String,
    /// The cost this task declares.
    pub declared_cost: u32,
}

/// The one structural well-formedness predicate this crate ever asks of a
/// task (REQ-34, EC-18): whether `task_id` is present at all, once
/// leading and trailing whitespace is disregarded. A whitespace-only
/// identifier is not well formed either -- this is not merely a
/// non-empty-length check. This function knows nothing about permission,
/// scope or budget, and its own `false` answer is never described as an
/// authorisation decision: the only authorisation decision anywhere in
/// this crate is `himinbjorg::validate_proposal`'s own return value.
///
/// A pure function, independent of any `hierarchy_vor::VerifiedCohort`:
/// this is deliberate (see the crate's own unit tests for why), so that
/// this one structural check is exercisable on every machine, whether or
/// not `HEIMDALL_COHORT_SECRET_FILE` is provisioned.
pub(crate) fn is_task_well_formed(task: &EngineTask) -> bool {
    !task.task_id.trim().is_empty()
}
