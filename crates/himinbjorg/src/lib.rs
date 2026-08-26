#![forbid(unsafe_code)]
//! `himinbjorg` crate root.
//!
//! Himinbjörg is the repository's third Rust crate and its gateway: the
//! component through which every proposed action must pass before it can
//! execute anywhere in the system (`plans/dd/himinbjorg.md`,
//! `.opencode/plans/himinbjorg-step-three.md`, D108). This crate is **under
//! active construction**: it is step three of the seven-step build order
//! `plans/synthesis-bootstrap.md` section 6 fixes, and at this commit it is
//! being assembled module by module rather than delivered whole.
//!
//! STATUS AT THIS COMMIT: only [`types`] carries real content (REQ-6, section
//! 13 file 5 of the step-three spec). The other six modules --
//! [`context`], [`definition`], [`sinks`], [`gate_bridge`], [`validation`]
//! and [`broker`] -- are declared but stubbed, each with its own doc comment
//! naming the interface it will carry once a later phase of this same issue
//! fills it in. The crate therefore does **not** yet compile a full
//! `cargo build`: `crates/himinbjorg/unit_tests/six_checks.rs`,
//! `crates/himinbjorg/unit_tests/gate_bridge_failclosed.rs` and
//! `crates/himinbjorg/tests/public_surface.rs` all assume the four public
//! interfaces (`build_context`, `enforce_definition`, `validate_proposal`,
//! `broker_action`) exist, and they do not exist yet at this commit. That is
//! expected and correct at this stage, following
//! `crates/hierarchy-vor/unit_tests/loader_failclosed.rs`'s own precedent
//! for the same situation one issue earlier.
//!
//! `types` is deliberately **not** `pub mod` (mirroring `hierarchy-vor`'s own
//! `mod types;`): its individual items are re-exported below instead, so a
//! caller reaches `himinbjorg::AgentContext` rather than
//! `himinbjorg::types::AgentContext`. None of the other six modules is
//! `pub mod` either, because the four public interfaces they will eventually
//! carry are re-exported individually at the crate root once they exist,
//! following the same convention; the two internal seams
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

// The four public interfaces (`build_context`, `enforce_definition`,
// `validate_proposal`, `broker_action`) will be re-exported here once
// `context`, `definition`, `validation` and `broker` carry real content, in a
// later phase of this same issue (execution workflow step 3.3 to 3.5).

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
