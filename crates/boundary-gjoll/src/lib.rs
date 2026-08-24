//! `boundary-gjoll`: a Rust re-expression of Gjoll's action-time gate (D109).
//!
//! Layer one (`types`, `rule`) lands in this build (issue #17): the pure, total
//! rule core plus the shared value types it and the shell both read. `declaration`
//! and `consequentiality` (layer two, see
//! `.opencode/plans/rust-gjoll-reexpression-spec.md` section 5.1) remain
//! placeholder-only pending a later build (issue #18); their modules are
//! deliberately not declared here yet, so this crate's public surface stays
//! exactly what is implemented rather than promising a module that is still empty.
//! Until layer two lands, the integration tests under `crates/boundary-gjoll/
//! tests/` will fail to compile; that is expected and correct at this stage.

pub mod types;
pub mod rule;
pub mod declaration;
pub mod consequentiality;

// The only test-related construct permitted anywhere under src/. Three lines, no
// test logic. The test bodies live in ../unit_tests/, which src/ never touches.
#[cfg(test)]
#[path = "../unit_tests/layer_one_parity.rs"]
mod layer_one_parity;
