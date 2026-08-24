#![forbid(unsafe_code)]
//! `hierarchy-vor` crate root.
//!
//! STATUS AT THIS COMMIT (issue #26, `.opencode/plans/vor-minimal-cohort-spec.md`
//! section 3.1): `#![forbid(unsafe_code)]` (REQ-2) and the `sha256` module (REQ-3) are
//! now implemented and `sha256::digest_hex` is re-exported below. The remaining five
//! modules (`record`, `verify`, `authoriser`, `types`, `cohort`) described in the
//! spec's section 4.1 are later issues (#27, #29, #31) and do not exist yet, exactly
//! as `crates/boundary-gjoll/src/lib.rs` grew module by module across its own issues
//! under the D109 precedent.
//!
//! Until a later issue adds the remaining five module declarations and the crate's
//! full public surface, both files wired in below WILL STILL FAIL TO COMPILE: every
//! path of the form `crate::record::...`, `crate::verify::...`, `crate::authoriser::...`,
//! `crate::types::...` and `crate::cohort::...` they reference is presently unresolved,
//! because no module of that name is declared anywhere in this file yet. That is
//! expected and correct at this stage: the tests are written to a fixed,
//! already-committed contract (the spec's section 4, "API surface"), and each
//! implementing issue builds the crate incrementally to satisfy it, rather than the
//! reverse. Only the `crate::sha256::...` paths they reference now resolve.
//!
//! `crates/hierarchy-vor/tests/public_surface.rs` (an external integration-test crate)
//! will separately fail to compile until this file also gains the remaining `pub mod`
//! declarations and public re-exports, for the same reason.

mod sha256;

pub use sha256::digest_hex;

// The only test-related construct permitted anywhere under src/ (REQ-38). One
// `#[cfg(test)] #[path = ...] mod ...;` declaration per unit-test file, no test logic here.
// The test bodies live in ../unit_tests/, which src/ never touches.
#[cfg(test)]
#[path = "../unit_tests/substrate_parity.rs"]
mod substrate_parity;

#[cfg(test)]
#[path = "../unit_tests/loader_failclosed.rs"]
mod loader_failclosed;
