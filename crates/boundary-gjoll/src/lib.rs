//! `boundary-gjoll`: a Rust re-expression of Gjoll's action-time gate (D109).
//!
//! Real crate content -- `types`, `rule`, `declaration` and `consequentiality` (see
//! `.opencode/plans/rust-gjoll-reexpression-spec.md` section 5.1) -- arrives in a
//! later build. This file today carries only the crate-root scaffolding REQ-24
//! requires to exist before that implementation lands: the single test-wiring
//! declaration below, which attaches the layer-one golden-vector replay
//! (`crates/boundary-gjoll/unit_tests/layer_one_parity.rs`) as an in-crate unit-test
//! module compiled only under `cfg(test)`. Until the modules above are declared and
//! implemented, that file (and the integration tests under `crates/boundary-gjoll/
//! tests/`) will fail to compile; that is expected and correct at this stage.

// The only test-related construct permitted anywhere under src/. Three lines, no
// test logic. The test bodies live in ../unit_tests/, which src/ never touches.
#[cfg(test)]
#[path = "../unit_tests/layer_one_parity.rs"]
mod layer_one_parity;
