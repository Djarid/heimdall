#![forbid(unsafe_code)]
//! `himinbjorg` crate root.
//!
//! Himinbjörg is the repository's third Rust crate and its gateway: the
//! component through which every proposed action must pass before it can
//! execute anywhere in the system (`plans/dd/himinbjorg.md`,
//! `.opencode/plans/himinbjorg-step-three.md`, D108).
//!
//! STATUS AT THIS COMMIT: all seven step-three modules carry real content
//! and all four of that step's public interfaces (`build_context`,
//! `enforce_definition`, `validate_proposal`, `broker_action`) are
//! implemented and re-exported below, plus `.opencode/plans/git-actuator-step-four.md`'s
//! own `audit` module and `broker_authorised_action` (REQ-26 to REQ-39).
//! `build_context` and `enforce_definition` remain minimal by design:
//! resolving a single hardcoded agent and control surface (section 5.2 and
//! 5.3 of the step-three spec). `validate_proposal` is real fidelity as of
//! step three: it sequences all six checks of `plans/dd/himinbjorg.md`
//! section 5.1, including a genuine call into
//! `boundary_gjoll::consequentiality::evaluate` at check five
//! (`gate_bridge::evaluate_taint_compatibility`, REQ-15), and now also mints
//! an [`Authorisation`] witness if and only if that sequence's decision is
//! `Allow` (REQ-27, step four).
//!
//! **Something can now execute, and this statement is rewritten
//! honestly rather than left stale.** Step three's own text here said that
//! nothing in this crate could execute an action, that `broker_action`'s
//! refusal was unconditional, and that HB-6 (logging an allowed decision to
//! Hliðskjálf before it fires) was therefore not violated, only deferred.
//! That is no longer true. `broker_action` itself is still refuse-only,
//! unconditionally, on its own unchanged three-argument signature (REQ-30):
//! it never invokes the actuator and never will, because its arguments
//! cannot express authorisation. But [`broker_authorised_action`], a
//! separate, witness-carrying entry point, CAN reach `actuator-git`'s
//! `execute` and, through it, the system `git` binary -- gated behind the
//! credential-scope check, a byte-equality witness match (REQ-29) and a
//! successful write to a [`DecisionRecorder`] performed BEFORE the actuator
//! is ever invoked (REQ-31 to REQ-33). HB-6 is therefore no longer
//! structurally unreachable: it is a live obligation, satisfied at this
//! crate's own minimal fidelity (an in-process, unsigned, unchained,
//! append-only seam, REQ-34) rather than against a durable, tamper-evident
//! log, which stays Phase 2 (`plans/dd/hlidskjalf.md`). REQ-35 names the
//! one honest limit this satisfies-at-minimal-fidelity claim does not
//! close: a recorder whose write always reports success without retaining
//! anything defeats the obligation, and nothing in this crate detects that.
//! `broker_authorised_action` itself has zero non-test callers at this
//! build step (REQ-40): the process engine that will call it is build-order
//! step five, so this step does not by itself advance invariant 3.6.
//!
//! `types` is deliberately **not** `pub mod` (mirroring `hierarchy-vor`'s own
//! `mod types;`): its individual items are re-exported below instead, so a
//! caller reaches `himinbjorg::AgentContext` rather than
//! `himinbjorg::types::AgentContext`. None of the other modules is `pub mod`
//! either, because the public interfaces they carry are re-exported
//! individually at the crate root instead, following the same convention;
//! the two internal seams (`gate_bridge::action_critical_for`,
//! `sinks::registry`) are reached only from inside this crate, including
//! from the in-crate unit-test modules wired in below (REQ-26), because
//! they are compiled into this same crate via `lib.rs`'s `#[path]`
//! declarations, not as an external crate.

mod audit;
mod broker;
mod context;
mod definition;
mod gate_bridge;
mod sinks;
mod types;
mod validation;

pub use audit::{DecisionRecorder, MinimalDecisionRecorder, RecordedDecision};
pub use types::{
    Action, ActuationReceipt, AgentContext, AgentId, Authorisation, BrokerRefusal, BrokerResult,
    CheckId, CheckOutcome, CheckRecord, ContextRefusal, Decision, DefinitionRefusal,
    EffectiveSurface, Proposal, ProposalDecision, ProposalParameter, Scope, TaskContext,
};

// Step three's four public interfaces (section 13 files 6, 7, 10 and 11 of
// the step-three spec): `build_context` (`context`), `enforce_definition`
// (`definition`), `validate_proposal` (`validation`) and `broker_action`
// (`broker`). Step four's own new entry point, `broker_authorised_action`
// (`broker`, REQ-29 to REQ-33, REQ-36 to REQ-39).
pub use broker::{broker_action, broker_authorised_action};
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

#[cfg(test)]
#[path = "../unit_tests/witness_and_audit.rs"]
mod witness_and_audit;
