#![forbid(unsafe_code)]
//! `hierarchy-vor` crate root.
//!
//! STATUS AT THIS COMMIT (issue #27, `.opencode/plans/vor-minimal-cohort-spec.md`
//! section 3.2, section 3.4's REQ-20/REQ-25): `#![forbid(unsafe_code)]` (REQ-2), the
//! `sha256` module (REQ-3), the `record` module (the attested-record substrate
//! re-expression, REQ-7 to REQ-12) and the `types` module (`CohortDefinition`'s shape
//! and `CohortSurface`'s read-only projection, REQ-20, REQ-25) are now implemented.
//! `sha256::digest_hex` and `types::CohortSurface` are re-exported below. The
//! remaining three modules (`verify`, `authoriser`, `cohort`) described in the spec's
//! section 4.1 are later issues (#29, #31) and do not exist yet, exactly as
//! `crates/boundary-gjoll/src/lib.rs` grew module by module across its own issues
//! under the D109 precedent.
//!
//! `record` and `types` are deliberately NOT `pub mod`, and neither module's items
//! are re-exported beyond `types::CohortSurface`: REQ-13 forbids any public function
//! that takes secret bytes, and `record::compute_record_attestation` is exactly such
//! a function, so it (and everything else in `record`, plus `types::CohortDefinition`
//! itself) stays reachable only from inside this crate -- which includes the
//! in-crate unit-test modules wired in below (REQ-38), because they are compiled
//! into this same crate via `lib.rs`'s `#[path]` declarations, not as an external
//! crate.
//!
//! Until a later issue adds the remaining three module declarations and the crate's
//! full public surface, both test files wired in below WILL STILL FAIL TO COMPILE:
//! every path of the form `crate::verify::...`, `crate::authoriser::...` and
//! `crate::cohort::...` they reference is presently unresolved, because no module of
//! that name is declared anywhere in this file yet. That is expected and correct at
//! this stage: the tests are written to a fixed, already-committed contract (the
//! spec's section 4, "API surface"), and each implementing issue builds the crate
//! incrementally to satisfy it, rather than the reverse. Only the `crate::sha256::...`,
//! `crate::record::...` and `crate::types::...` paths they reference now resolve.
//!
//! `crates/hierarchy-vor/tests/public_surface.rs` (an external integration-test crate)
//! will separately fail to compile until this file also gains the remaining `pub mod`
//! declarations and public re-exports, for the same reason.

mod record;
mod sha256;
mod types;

pub use sha256::digest_hex;
pub use types::CohortSurface;

// The only test-related construct permitted anywhere under src/ (REQ-38). One
// `#[cfg(test)] #[path = ...] mod ...;` declaration per unit-test file, no test logic here.
// The test bodies live in ../unit_tests/, which src/ never touches.
#[cfg(test)]
#[path = "../unit_tests/substrate_parity.rs"]
mod substrate_parity;

#[cfg(test)]
#[path = "../unit_tests/loader_failclosed.rs"]
mod loader_failclosed;
