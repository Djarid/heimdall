//! `hierarchy-vor` crate root.
//!
//! STATUS AT THIS COMMIT (test-writing stage, `.opencode/plans/vor-minimal-cohort-spec.md`
//! section 8, "Ownership boundary"): this file carries ONLY the test-wiring block below.
//! Files 4 to 10 under `src/` -- including the rest of THIS file
//! (`#![forbid(unsafe_code)]`, the six `pub mod` declarations, the public re-exports and
//! the crate-level documentation the spec's section 4.1 describes) -- are implementation
//! and belong to the implementing agent. Only the test-wiring region (REQ-38) is written
//! ahead of the implementation, exactly as `crates/boundary-gjoll/src/lib.rs` did for the
//! D109 precedent: that crate's `unit_tests/layer_one_parity.rs` and
//! `tests/layer_two_parity.rs` both carry the same "WILL FAIL TO COMPILE until the
//! implementation exists" header this crate's own test files repeat.
//!
//! Until the implementing agent adds the six module declarations
//! (`sha256`, `record`, `verify`, `authoriser`, `types`, `cohort`) and the crate's public
//! surface, both files wired in below WILL FAIL TO COMPILE: every path of the form
//! `crate::sha256::...`, `crate::record::...`, `crate::verify::...`,
//! `crate::authoriser::...`, `crate::types::...` and `crate::cohort::...` they reference is
//! presently unresolved, because no module of that name is declared anywhere in this file.
//! That is expected and correct at this stage: the tests are written to a fixed,
//! already-committed contract (the spec's section 4, "API surface"), and the implementing
//! agent builds the crate to satisfy it, rather than the reverse.
//!
//! `crates/hierarchy-vor/tests/public_surface.rs` (an external integration-test crate) will
//! separately fail to compile until this file also gains its `pub mod` declarations and
//! public re-exports, for the same reason.

// The only test-related construct permitted anywhere under src/ (REQ-38). One
// `#[cfg(test)] #[path = ...] mod ...;` declaration per unit-test file, no test logic here.
// The test bodies live in ../unit_tests/, which src/ never touches.
#[cfg(test)]
#[path = "../unit_tests/substrate_parity.rs"]
mod substrate_parity;

#[cfg(test)]
#[path = "../unit_tests/loader_failclosed.rs"]
mod loader_failclosed;
