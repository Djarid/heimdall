#![forbid(unsafe_code)]
//! `hierarchy-vor` crate root.
//!
//! STATUS AT THIS COMMIT (issue #29, `.opencode/plans/vor-minimal-cohort-spec.md`
//! section 3.3, section 3.4's REQ-27, section 4.1's `authoriser.rs` and
//! `verify.rs` tables): `#![forbid(unsafe_code)]` (REQ-2), the `sha256` module
//! (REQ-3), the `record` module (REQ-7 to REQ-12), the `types` module (REQ-20,
//! REQ-25), the `authoriser` module (the trusted authoriser set and the secret's
//! out-of-tree provenance, REQ-13 to REQ-19) and the `verify` module (the four-case
//! fail-closed decision procedure, REQ-27) are now implemented. The remaining
//! module, `cohort` (the one hardcoded `heimdall-dev` cohort, its committed
//! attestation constant and the crate's single entry point), is a later issue
//! (#31) and does not exist yet, exactly as `crates/boundary-gjoll/src/lib.rs`
//! grew module by module across its own issues under the D109 precedent.
//!
//! `record` and `types` are deliberately NOT `pub mod`, and neither module's items
//! are re-exported beyond `types::CohortSurface`: REQ-13 forbids any public function
//! that takes secret bytes, and `record::compute_record_attestation` is exactly such
//! a function, so it (and everything else in `record`, plus `types::CohortDefinition`
//! itself) stays reachable only from inside this crate -- which includes the
//! in-crate unit-test modules wired in below (REQ-38), because they are compiled
//! into this same crate via `lib.rs`'s `#[path]` declarations, not as an external
//! crate. `authoriser` and `verify` are also plain `mod` (not `pub mod`): their
//! own items that must be reachable from an external crate (the two loaders, the
//! two refusal enums, the trusted-set type and the two named constants) are
//! re-exported individually below; `authoriser::TrustedAuthoriserSet::for_test`
//! and `verify::verify_record` are `pub(crate)`/test-only and are never
//! re-exported, exactly as REQ-13 and REQ-27 require.
//!
//! Until issue #31 adds the `cohort` module declaration and its own public
//! re-exports (the entry point, `VerifiedCohort` and `CohortRefusal`),
//! `tests/public_surface.rs` (an external integration-test crate) WILL STILL FAIL
//! TO COMPILE: every path of the form `crate::cohort::...` /
//! `hierarchy_vor::cohort::...` and `hierarchy_vor::load_verified_cohort` it
//! references is presently unresolved. That is expected and correct at this
//! stage, for the same reason `unit_tests/substrate_parity.rs`'s own header
//! states.
//!
//! Stated plainly rather than smoothed over: `unit_tests/loader_failclosed.rs`
//! itself reaches only `crate::authoriser`, `crate::record`, `crate::types` and
//! `crate::verify`, all of which now exist, and every one of its own tests
//! passes in isolation. But `cargo test -p hierarchy-vor` still fails to build
//! the `lib test` binary as a WHOLE at this commit, because `rustc` compiles
//! all `#[cfg(test)]` modules wired into one crate as a single unit, and the
//! sibling module `substrate_parity` (wired in below, in the one block REQ-38
//! permits) does not compile until issue #31 lands `crate::cohort` too. This is
//! a sequencing dependency on issue #31, not a defect in this issue's own code:
//! confirmed by temporarily disabling `substrate_parity`'s wiring and observing
//! all fourteen `loader_failclosed` tests pass, then restoring it.

mod authoriser;
mod record;
mod sha256;
mod types;
mod verify;

pub use authoriser::{
    MIN_SECRET_BYTES, SECRET_PATH_ENV_VAR, SecretRefusal, TrustedAuthoriserSet,
    load_trusted_set_from_env, load_trusted_set_from_path,
};
pub use sha256::digest_hex;
pub use types::CohortSurface;
pub use verify::RecordRefusal;

// The only test-related construct permitted anywhere under src/ (REQ-38). One
// `#[cfg(test)] #[path = ...] mod ...;` declaration per unit-test file, no test logic here.
// The test bodies live in ../unit_tests/, which src/ never touches.
#[cfg(test)]
#[path = "../unit_tests/substrate_parity.rs"]
mod substrate_parity;

#[cfg(test)]
#[path = "../unit_tests/loader_failclosed.rs"]
mod loader_failclosed;
