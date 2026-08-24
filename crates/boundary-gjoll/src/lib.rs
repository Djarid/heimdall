#![forbid(unsafe_code)]
//! `boundary-gjoll`: a Rust re-expression of Gjoll's action-time gate (D109).
//!
//! All four modules are implemented in this build: `types` and `rule` (layer
//! one, issue #17) provide the shared value types and the pure, total rule
//! core; `declaration` and `consequentiality` (layer two, issues #18 and #19,
//! see `.opencode/plans/rust-gjoll-reexpression-spec.md` section 5.1) provide
//! registry-backed proposal validation and the authorisation shell built on
//! top of it. The crate's public gate entry point is
//! `consequentiality::evaluate`.
//!
//! The design is registry-mandatory: `evaluate` takes the sink registry as a
//! plain reference, never an `Option`, and there is no branch anywhere in this
//! crate that derives a consequentiality verdict from anything other than the
//! registry. This designs out three things by construction rather than by
//! convention: the Python shell's no-registry branch, the residual boolean
//! per-sink flag that D97 replaced with a derivation from the declared effect
//! primitive, and D100's classify-time stamp union and its stamp-rewrite
//! limit. None of the three has a code path here to fall back into.
//!
//! Two things are deliberately deferred, not designed out: D93's behavioural
//! effect-probe cross-check (confirming a sink's declared effect primitive
//! against what it is actually observed to do at runtime) has a reserved,
//! unconstructed slot on `ConsequentialitySource` but no function in this
//! crate accepts an effect-observation argument yet; and a public `Actuator`
//! plus an `enforce` equivalent (REQ-27) do not exist in this build, so this
//! crate stops at producing a `GateDecision` and never executes one.
//!
//! The block below is the only test-related construct permitted anywhere
//! under `src/`: it wires `unit_tests/layer_one_parity.rs` in as a module for
//! `cargo test` while keeping the test bodies physically outside `src/`, per
//! this repo's test/code isolation requirement.

pub mod consequentiality;
pub mod declaration;
pub mod rule;
pub mod types;

// The only test-related construct permitted anywhere under src/. Three lines, no
// test logic. The test bodies live in ../unit_tests/, which src/ never touches.
#[cfg(test)]
#[path = "../unit_tests/layer_one_parity.rs"]
mod layer_one_parity;
