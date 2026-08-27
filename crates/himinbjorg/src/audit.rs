//! HB-6's audit seam (GA-2, REQ-31 to REQ-35 of
//! `.opencode/plans/git-actuator-step-four.md`, section 13 file 15). This
//! module's one responsibility (section 9.3): define the write contract and
//! provide one minimal, append-only recorder. It knows nothing about git and
//! nothing about actuation, exactly as `execute.rs` and `argv.rs`, in the
//! other crate, know nothing about authorisation.
//!
//! **The write contract, one fallible operation (REQ-31).**
//! [`DecisionRecorder`] carries exactly one method: write a decision and its
//! six [`crate::types::CheckRecord`]s, and either succeed or fail. Nothing
//! about verification, query or rotation is on this trait: a caller
//! supplying a recorder is never forced to implement an operation it has no
//! use for (section 9.1's Interface Segregation). `crate::broker::broker_authorised_action`
//! calls this write BEFORE the actuator is ever invoked, and a failed write
//! refuses the whole action rather than proceeding (REQ-32): an unlogged
//! decision is treated as no decision (HK-4).
//!
//! **The one minimal implementation is append only (REQ-34).**
//! [`MinimalDecisionRecorder`] appends and never updates or deletes: no
//! mutating operation on an already-written entry exists anywhere on this
//! type, which is HK-2's structural form of append only, not a runtime
//! check. It performs no signing, no chained digest and no durable
//! persistence: all three stay Phase 2, named here as deferred rather than
//! claimed (`plans/dd/hlidskjalf.md`).
//!
//! **The recorded entry's own honest absence (data schema, section 6).** An
//! entry identifier, a wall-clock stamp, a world-model state hash and a
//! digital signature are each ABSENT from [`RecordedDecision`], not merely
//! left empty: there is no Rust Hliðskjálf, no Rust Mímisbrunnr and no
//! signing key for any of the four to be derived from at this fidelity, so
//! declaring an empty placeholder for one would misstate what this recorder
//! actually establishes. Only what this minimal seam can genuinely support
//! -- who acted, on what, with what decision, over which six checks, in
//! append order -- is carried.
//!
//! **The honest limit, stated plainly, not smoothed (REQ-35, EC-13).** This
//! trait's contract asks every implementation to retain what it reports as
//! written; nothing in the type system enforces that a `Result::Ok` return
//! means anything was actually kept. A caller that supplies a recorder whose
//! write always reports success without retaining anything defeats the
//! audit obligation this module exists to satisfy: the actuator still
//! executes (`crate::broker::broker_authorised_action` cannot tell the
//! difference between an honest write and a lying one that also returns
//! `Ok`), the effect still lands, and no record of the decision that
//! authorised it survives anywhere. This is the same class of limit as
//! D103's limit two and D100's in-process label rewrite: named here, in the
//! spec and in the `DECISIONS.md` row, and not closed by this step. No
//! mechanism in this crate detects, rejects or distinguishes a lying
//! recorder from an honest one; claiming otherwise would be false.

use crate::types::{Action, AgentId, CheckRecord, Decision};

/// The narrow, single-method write contract (REQ-31). A write either
/// succeeds, in which case the caller may treat the record as durable to
/// whatever degree this particular implementation claims, or it fails, in
/// which case [`crate::broker::broker_authorised_action`] refuses and the
/// action must not proceed (REQ-32). Any implementation -- this crate's own
/// minimal one, a test double, or a future real Hliðskjálf -- must respect
/// that a returned success means the record is retained; the honest limit
/// on that promise is this module's own doc comment above (REQ-35, EC-13):
/// the type system cannot enforce it, only ask for it.
pub trait DecisionRecorder {
    /// Writes one decision and the six [`CheckRecord`]s that produced it.
    /// `Err` carries a diagnostic naming why the write failed; `Ok` is the
    /// caller's signal that it is now safe to proceed to whatever the
    /// decision authorised.
    fn record(
        &mut self,
        agent_id: &AgentId,
        action: &Action,
        decision: Decision,
        checks: &[CheckRecord],
    ) -> Result<(), String>;
}

/// One entry [`MinimalDecisionRecorder`] holds after a successful write
/// (data schema, section 6 of the spec). Deliberately narrower than
/// `plans/dd/hlidskjalf.md` section 3.1's full entry schema: an identifying
/// number, a wall-clock stamp, a world-model state hash and a digital
/// signature are all ABSENT here, not empty, because this fidelity has
/// nothing genuine to put in any of the four (no Rust Hliðskjálf, no Rust
/// Mímisbrunnr, no signing key). Only the agent, the action, the decision
/// and its six checks -- exactly what [`DecisionRecorder::record`] is given
/// -- are carried.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RecordedDecision {
    /// The agent the decision was made for.
    pub agent_id: AgentId,
    /// The action the decision covers.
    pub action: Action,
    /// The decision itself.
    pub decision: Decision,
    /// The six checks that produced the decision, in the same order
    /// `validate_proposal` sequenced them.
    pub checks: Vec<CheckRecord>,
}

/// The one minimal, append-only [`DecisionRecorder`] implementation this
/// crate provides (REQ-34). In process only, unsigned, unchained and not
/// durable: none of that is claimed here (see this module's own doc comment
/// for what is deferred and why). Every write appends one
/// [`RecordedDecision`] to an internal, growable list; no method on this
/// type updates or removes an already-appended entry, which is the whole of
/// how "append only" holds here -- a structural absence of a mutating
/// operation, not a runtime guard against one.
#[derive(Debug, Default)]
pub struct MinimalDecisionRecorder {
    entries: Vec<RecordedDecision>,
}

impl MinimalDecisionRecorder {
    /// Builds an empty recorder: no entries until the first successful
    /// write.
    pub fn new() -> Self {
        MinimalDecisionRecorder {
            entries: Vec::new(),
        }
    }

    /// Every entry this recorder holds, in the order it was written. A
    /// read-only accessor: there is no mutable counterpart, and nothing on
    /// this type lets a caller alter or remove what is returned here.
    pub fn records(&self) -> &[RecordedDecision] {
        &self.entries
    }

    /// The same write [`DecisionRecorder::record`] performs, exposed here
    /// too as an inherent method so a caller holding a concrete
    /// `MinimalDecisionRecorder` (rather than a generic `impl DecisionRecorder`)
    /// can call it without bringing the trait into scope. Appends one
    /// [`RecordedDecision`]; never updates or removes an existing one
    /// (REQ-34).
    pub fn record(
        &mut self,
        agent_id: &AgentId,
        action: &Action,
        decision: Decision,
        checks: &[CheckRecord],
    ) -> Result<(), String> {
        self.entries.push(RecordedDecision {
            agent_id: agent_id.clone(),
            action: action.clone(),
            decision,
            checks: checks.to_vec(),
        });
        Ok(())
    }
}

impl DecisionRecorder for MinimalDecisionRecorder {
    fn record(
        &mut self,
        agent_id: &AgentId,
        action: &Action,
        decision: Decision,
        checks: &[CheckRecord],
    ) -> Result<(), String> {
        // Delegates to the inherent method above so the two never drift
        // apart (see that method's own doc comment for why it exists
        // separately at all).
        MinimalDecisionRecorder::record(self, agent_id, action, decision, checks)
    }
}
