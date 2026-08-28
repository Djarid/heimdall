//! The outcome vocabulary and both deferral forms (PE-7, REQ-24, REQ-35,
//! REQ-36). No logic and no decision lives here (section 9.3's own
//! statement of this module's one responsibility): every value below is
//! carried through from somewhere else, verbatim, dropping nothing
//! (REQ-24).
//!
//! Also carries the binary's own small, closed set of named exit-code
//! constants and the one function that maps an [`EngineOutcome`] to one
//! of them (REQ-30). They live here, in the library, rather than solely
//! in `main.rs`, so their distinctness and their mapping are testable
//! from an in-crate unit-test module: `main.rs` is a separate compilation
//! unit this crate's own unit tests cannot reach at all.

/// The outcome of one call to [`crate::run_sequence`] (section 3.1 item 4
/// of `.opencode/plans/process-engine-step-five-spec.md`). Every match
/// over this enum anywhere in this crate is exhaustive and carries no
/// wildcard arm (EC-14): a future variant forces every match site to be
/// revisited rather than folding silently into a catch-all.
#[derive(Debug)]
pub enum EngineOutcome {
    /// A structural well-formedness refusal, originated by this crate
    /// itself, before the cognition step ever runs (REQ-34, EC-18).
    /// **Never** an authorisation decision: the only authorisation
    /// decision anywhere in this crate is
    /// [`himinbjorg::validate_proposal`]'s own return value. `reason`
    /// names the structural defect (for example an empty task
    /// identifier); it names no permission, scope or budget rule,
    /// because this refusal knows none.
    RefusedBeforeCognition {
        /// The structural defect that produced this refusal, in plain
        /// prose. Never a permission, scope or budget rule.
        reason: String,
    },
    /// The gate step's own block, carrying every one of the six
    /// [`himinbjorg::CheckRecord`]s [`himinbjorg::validate_proposal`]
    /// produced, verbatim, dropping nothing (REQ-24). Never re-derived
    /// or approximated by this crate.
    GateBlocked {
        /// The six check records `validate_proposal` produced, in its
        /// own order.
        checks: Vec<himinbjorg::CheckRecord>,
    },
    /// The execute step's own refusal, carrying
    /// [`himinbjorg::BrokerRefusal`] itself, verbatim (REQ-24): where
    /// that refusal is `ActuatorRefused`, the originating
    /// `actuator_git::ActuationRefusal` variant remains recoverable from
    /// it, because this crate never maps `BrokerRefusal` down to an
    /// opaque marker.
    BrokerRefused {
        /// The refusal `himinbjorg::broker_authorised_action` returned,
        /// unmodified.
        refusal: himinbjorg::BrokerRefusal,
    },
    /// The execute step succeeded: the action reached the actuator and
    /// the actuator reported success, carried through as
    /// [`himinbjorg::ActuationReceipt`] verbatim.
    Executed {
        /// What `himinbjorg::broker_authorised_action` returned on
        /// success, unmodified.
        receipt: himinbjorg::ActuationReceipt,
    },
    /// The human-question deferral (REQ-35, PE-7): named and typed
    /// rather than delivered. No non-test code path in this crate
    /// constructs this variant, on [`himinbjorg::Decision::Queue`] and
    /// [`himinbjorg::Decision::Escalate`]'s own precedent for a
    /// declared-but-currently-unreachable case, and it is not an
    /// `unimplemented!()` branch: a panic on an authorisation-adjacent
    /// path is worse than a typed refusal.
    ///
    /// Delivering this for real would need two things that do not exist
    /// yet: Gjallarhorn's protected authorisation channel, so a human
    /// question could be posed and answered without becoming a second,
    /// unaudited path to the same effect, and an operator-answer path
    /// that feeds the answer back into a resumed sequence run rather
    /// than a fresh, unrelated one. This build has neither, so this
    /// variant stays exactly what its own name says: a place-holder in
    /// the outcome vocabulary, not a working feature.
    AwaitingHumanDecision,
}

/// The loop cap's own deferral (REQ-36, PE-7): a type with no
/// constructor, on [`himinbjorg::BrokerResult`]'s own uninhabited-enum
/// precedent, so "there is no loop, therefore no cap can be reached" is a
/// compile-time fact rather than a comment. `crate::STEP_SEQUENCE`'s own
/// fixed, five-entry array with its compile-time length assertion is the
/// structural reason this type is never needed: this build has exactly
/// one path through the sequence and nothing to loop.
///
/// A real loop cap, when this crate one day needs one, would be
/// Gleipnir's own code-enforced loop cap over a general transition
/// table, not this crate's own ad-hoc counter: that is deferred, not
/// built, and this type exists only to name the shape the deferral would
/// eventually fill.
#[derive(Debug)]
pub enum LoopCap {}

/// Reserved for [`EngineOutcome::Executed`] only (REQ-30, AC-33): no
/// failing outcome ever maps to this code.
pub const EXIT_EXECUTED: i32 = 0;

/// The binary's own startup refused fail closed, before the sequence
/// ever ran (REQ-27 to REQ-30). Never returned by [`exit_code_for`]
/// itself, since a startup refusal never reaches an [`EngineOutcome`] at
/// all; named here so the whole closed set of exit codes is documented
/// in one place, as REQ-30 requires.
pub const EXIT_STARTUP_REFUSAL: i32 = 1;

/// [`EngineOutcome::GateBlocked`]'s own exit code.
pub const EXIT_GATE_BLOCKED: i32 = 2;

/// [`EngineOutcome::BrokerRefused`]'s own exit code.
pub const EXIT_BROKER_REFUSED: i32 = 3;

/// [`EngineOutcome::RefusedBeforeCognition`]'s own exit code. Also the
/// code [`EngineOutcome::AwaitingHumanDecision`] maps to below: that
/// variant is never constructed by any code path in this crate (see its
/// own doc comment), so this mapping is defensive-only, never exercised;
/// it is grouped with the well-formedness refusal because both share the
/// same character -- the sequence could not conclude with a genuine
/// authorisation decision from `validate_proposal` or
/// `broker_authorised_action` -- rather than with either of those two
/// outcomes' own dedicated codes.
pub const EXIT_WELL_FORMEDNESS_REFUSAL: i32 = 4;

/// Maps one [`EngineOutcome`] to its own documented exit code (REQ-30).
/// Exhaustive, no wildcard arm (EC-14): a future variant forces this
/// match to be revisited rather than folding silently into a catch-all.
pub fn exit_code_for(outcome: &EngineOutcome) -> i32 {
    match outcome {
        EngineOutcome::Executed { .. } => EXIT_EXECUTED,
        EngineOutcome::GateBlocked { .. } => EXIT_GATE_BLOCKED,
        EngineOutcome::BrokerRefused { .. } => EXIT_BROKER_REFUSED,
        EngineOutcome::RefusedBeforeCognition { .. } => EXIT_WELL_FORMEDNESS_REFUSAL,
        EngineOutcome::AwaitingHumanDecision => EXIT_WELL_FORMEDNESS_REFUSAL,
    }
}
