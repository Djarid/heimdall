#![forbid(unsafe_code)]
//! `himinbjorg` crate root.
//!
//! Himinbjörg is the repository's third Rust crate and its gateway: the
//! component through which every proposed action must pass before it can
//! execute anywhere in the system (`plans/dd/himinbjorg.md`,
//! `.opencode/plans/himinbjorg-step-three.md`, D108).
//!
//! STATUS AT THIS COMMIT: all seven modules carry real content and all four
//! public interfaces (`build_context`, `enforce_definition`,
//! `validate_proposal`, `broker_action`) are implemented and re-exported
//! below. Two of the four are minimal by design rather than by omission:
//! `build_context` and `enforce_definition` resolve a single hardcoded agent
//! and control surface (section 5.2 and 5.3 of the step-three spec);
//! `broker_action` is refuse-only (HB3-7, REQ-22), dispatching to a single
//! actuator slot that is deliberately left unimplemented until step four
//! builds the git actuator behind it. `validate_proposal` is the one
//! interface built to real fidelity at this step: it sequences all six
//! checks of `plans/dd/himinbjorg.md` section 5.1, including a genuine call
//! into `boundary_gjoll::consequentiality::evaluate` at check five
//! (`gate_bridge::evaluate_taint_compatibility`, REQ-15). Nothing in this
//! crate can execute an action: `broker_action`'s refusal is unconditional,
//! so no action fires, and HB-6 (logging an allowed decision to Hliðskjálf
//! before it fires) is therefore not violated by this step, only deferred
//! (REQ-23, section 11 item six of the step-three spec).
//!
//! `types` is deliberately **not** `pub mod` (mirroring `hierarchy-vor`'s own
//! `mod types;`): its individual items are re-exported below instead, so a
//! caller reaches `himinbjorg::AgentContext` rather than
//! `himinbjorg::types::AgentContext`. None of the other six modules is
//! `pub mod` either, because the four public interfaces they carry are
//! re-exported individually at the crate root instead, following the same
//! convention; the two internal seams
//! (`gate_bridge::action_critical_for`, `sinks::registry`) are reached only
//! from inside this crate, including from the in-crate unit-test modules
//! wired in below (REQ-26), because they are compiled into this same crate
//! via `lib.rs`'s `#[path]` declarations, not as an external crate.

mod broker;
mod context;
mod definition;
mod gate_bridge;
mod sinks;
mod types;
mod validation;

pub use types::{
    Action, AgentContext, AgentId, BrokerRefusal, BrokerResult, CheckId, CheckOutcome,
    CheckRecord, ContextRefusal, Decision, DefinitionRefusal, EffectiveSurface, Proposal,
    ProposalDecision, ProposalParameter, Scope, TaskContext,
};

// All four public interfaces are real as of this phase (section 13 files 6,
// 7, 10 and 11 of the step-three spec): `build_context` (`context`),
// `enforce_definition` (`definition`), `validate_proposal` (`validation`)
// and `broker_action` (`broker`).
pub use broker::broker_action;
pub use context::build_context;
pub use definition::enforce_definition;
pub use validation::validate_proposal;

// The only test-related construct permitted anywhere under src/ (REQ-5, REQ-26).
// One `#[cfg(test)] #[path = ...] mod ...;` declaration per unit-test file, no
// test logic here. The test bodies live in ../unit_tests/, which src/ never
// touches.
#[cfg(test)]
#[path = "../unit_tests/six_checks.rs"]
mod six_checks;

#[cfg(test)]
#[path = "../unit_tests/gate_bridge_failclosed.rs"]
mod gate_bridge_failclosed;
