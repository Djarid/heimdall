#![forbid(unsafe_code)]
//! `process-engine` crate root: the repository's fifth Rust crate
//! (build-order step five, `.opencode/plans/process-engine-step-five-spec.md`,
//! D108). A library carrying one public entry point, [`run_sequence`],
//! that runs a fixed five-step sequence -- accept task, cognition,
//! propose action, gate, execute -- over one task, plus a binary
//! (`src/main.rs`) that calls it once. This is the caller
//! `himinbjorg::broker_authorised_action`, Himinbjörg's five public
//! interfaces and `hierarchy_vor::load_verified_cohort` each gain their
//! first genuine non-test caller from: four crates already held a
//! complete authorisation path from a proposal to a git process, and
//! nothing in the repository called that path outside a test until this
//! one.
//!
//! **The engine adjudicates nothing. It sequences.** No step consults
//! the cohort's permitted-action set, the sink registry, the target
//! scope, the blast radius bound, the resource ceiling or the
//! credential-scope allowlist to decide whether to proceed. The only
//! authorisation decision anywhere in the sequence is
//! `himinbjorg::validate_proposal`'s own return value, and the only
//! execution decision is `himinbjorg::broker_authorised_action`'s own
//! return value. A refusal this crate originates itself
//! ([`EngineOutcome::RefusedBeforeCognition`]) is a structural
//! well-formedness refusal, never an authorisation decision.
//!
//! **"Result out" is [`run_sequence`]'s own return value, not a sixth step.**
//! The step vocabulary ([`EngineStep`]) is closed at exactly five
//! variants, carried in [`STEP_SEQUENCE`], a fixed array with its own
//! compile-time length assertion: an edit that adds or removes a step
//! fails the build, not a later test run.
//!
//! **Cognition is advisory and never adjudicative.** [`CognitionStep`]'s
//! one stub implementation, [`DefaultCognitionStep`], proposes advisory
//! content built from hardcoded constants; everything it proposes still
//! passes through `validate_proposal`'s six checks and the witness
//! match, and no branch anywhere derives a permission from it. See
//! `src/cognition.rs`'s own doc comment for why this does not repeat
//! D112's rejection of a trait at the actuator invocation.
//!
//! **Nothing in this step stages a change (PE-3).** The cognition stub
//! produces no file content, this crate writes no file, and there is no
//! `git add` or equivalent anywhere in this crate. The consequence: a
//! commit proposal that passes all six checks reaches the actuator and
//! refuses with `actuator_git::ActuationRefusal::ExitStatus`, because
//! nothing is staged. **This is the designed outcome, not a defect.**
//! Staging is step six's own written obligation, not this one's.
//!
//! **Two deferral forms, named and typed rather than delivered.**
//! [`EngineOutcome::AwaitingHumanDecision`] is the human-question gate:
//! it needs Gjallarhorn's protected authorisation channel and an
//! operator-answer path, neither of which exists yet, and no code path
//! in this crate constructs it. [`LoopCap`] is the loop cap: an
//! uninhabited type, because this build has exactly one path through the
//! sequence and nothing to loop; a real one would be Gleipnir's own
//! code-enforced loop cap over a general transition table. Neither is
//! presented as working.
//!
//! **EC-12 is narrowed here, not closed; EC-13 is untouched.** This
//! crate's fixed sequence obtains at most one witness per run and passes
//! it to `broker_authorised_action` exactly once, so witness replay is
//! unreachable **through this crate**. `broker_authorised_action` itself
//! is unchanged and stays replayable by any other caller holding a
//! witness (REQ-45): nothing here makes the witness single use. This
//! crate supplies a real `himinbjorg::MinimalDecisionRecorder`, the
//! honest case; nothing built here detects, rejects or distinguishes a
//! recorder that reports success while retaining nothing (REQ-46,
//! EC-13).
//!
//! **A disclosed dependency deviation.** This crate's `Cargo.toml`
//! carries a third in-workspace path dependency, `boundary-gjoll`, in
//! addition to `himinbjorg` and `hierarchy-vor`. See `Cargo.toml`'s own
//! comment and `src/cognition.rs`'s own doc comment for the full,
//! evidence-backed explanation: it is needed for constructing real
//! `himinbjorg::ProposalParameter` values only, never for calling
//! Gjöll's gate or naming `actuator-git` at all.

mod cognition;
mod outcome;
mod proposal;
mod sequence;
// `pub mod`, unlike its four siblings above: `src/main.rs` is a SEPARATE
// crate root (REQ-5, REQ-7) that calls `process_engine::startup::run()`
// across the crate boundary, so `resolve_startup_preconditions` and
// `StartupRefusal` need to be reachable from there, not only from this
// crate's own in-crate unit-test modules. This is REQ-26's own delegation
// point: `main.rs` reads no environment variable itself; it calls this
// one module instead.
pub mod startup;
mod task;

pub use cognition::{CognitionOutput, CognitionStep, DefaultCognitionStep};
pub use outcome::{
    EXIT_BROKER_REFUSED, EXIT_EXECUTED, EXIT_GATE_BLOCKED, EXIT_STARTUP_REFUSAL,
    EXIT_WELL_FORMEDNESS_REFUSAL, EngineOutcome, LoopCap, exit_code_for,
};
pub use sequence::{EngineStep, STEP_SEQUENCE, run_sequence};
pub use task::EngineTask;

// `startup` is `pub mod` above, not re-exported here: `src/main.rs` reaches
// it as `process_engine::startup::run()` directly (REQ-26), and nothing in
// this crate's own public-surface sufficiency criterion (REQ-54) needs a
// second, crate-root path to the same items.

// `pub(crate)` items other modules reach via `crate::`, not re-exported at
// the crate root: `task::is_task_well_formed`, `proposal::build_proposal`,
// `sequence::run_sequence_with_cognition`, `sequence::accept_task`,
// `sequence::run_gate`, `sequence::run_execute`. Each is reachable only
// through this crate's own modules or its in-crate unit-test modules
// (REQ-11's mandatory-shell pattern), never from outside the crate. The
// three bare, crate-root aliases below exist only so the in-crate
// unit-test modules can reach them as `crate::build_proposal` and so on
// (their own committed, unmodifiable convention): every non-test caller
// reaches the same items through their owning module's own path instead
// (`sequence::run_sequence_with_cognition`, `task::is_task_well_formed`),
// so these aliases are `#[cfg(test)]` only, never part of a non-test
// build.
#[cfg(test)]
pub(crate) use proposal::build_proposal;
#[cfg(test)]
pub(crate) use sequence::run_sequence_with_cognition;
#[cfg(test)]
pub(crate) use task::is_task_well_formed;

// The only test-related construct permitted anywhere under src/ (REQ-7).
// One `#[cfg(test)] #[path = ...] mod ...;` declaration per unit-test
// file, no test logic here. The test bodies live in ../unit_tests/,
// which src/ never touches.

#[cfg(test)]
#[path = "../unit_tests/sequence_shape.rs"]
mod sequence_shape;

#[cfg(test)]
#[path = "../unit_tests/cognition_and_proposal.rs"]
mod cognition_and_proposal;

#[cfg(test)]
#[path = "../unit_tests/startup_failclosed.rs"]
mod startup_failclosed;
