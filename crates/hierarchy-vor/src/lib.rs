#![forbid(unsafe_code)]
//! `hierarchy-vor` crate root.
//!
//! STATUS AT THIS COMMIT (issue #31, `.opencode/plans/vor-minimal-cohort-spec.md`
//! section 3.4, section 4.1's `cohort.rs` table): all six modules now exist.
//! `#![forbid(unsafe_code)]` (REQ-2), `sha256` (REQ-3), `record` (REQ-7 to
//! REQ-12), `types` (REQ-20, REQ-25), `authoriser` (the trusted authoriser set
//! and the secret's out-of-tree provenance, REQ-13 to REQ-19), `verify` (the
//! four-case fail-closed decision procedure, REQ-27) and now `cohort` (the one
//! hardcoded `heimdall-dev` cohort, its committed attestation constant and the
//! crate's single entry point, REQ-20 to REQ-27) are all implemented.
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
//! `cohort` IS `pub mod` (unlike `record`, `types`, `authoriser` and `verify`):
//! `tests/public_surface.rs`, compiled as an external crate, reaches its
//! constants directly as `hierarchy_vor::cohort::{COHORT_ID, PERMITTED_ACTIONS,
//! TRUST_CEILING, CONSEQUENTIAL_SINKS, AUTHORISER_ID}` (needed by any external
//! caller, step three included, to know which authoriser id to load a secret
//! for). None of `cohort`'s constants take or expose a secret, so this is
//! consistent with REQ-13's own scope. `VerifiedCohort`, `CohortRefusal` and
//! `load_verified_cohort` are additionally re-exported at the crate root below,
//! so both `hierarchy_vor::VerifiedCohort` and `hierarchy_vor::cohort::VerifiedCohort`
//! resolve to the same type.
//!
//! REQ-26, confirmed directly rather than merely asserted: this crate's
//! manifest carries an empty `[dependencies]` table (`crates/hierarchy-vor/Cargo.toml`)
//! and no source file under `src/` names, imports or re-exports anything from
//! `boundary-gjoll`. The consequential-sink set `cohort::CONSEQUENTIAL_SINKS` is
//! never routed into `consequentiality::evaluate`; step three (a later issue)
//! reads it from `CohortSurface::consequential_sinks` instead.

mod authoriser;
pub mod cohort;
mod record;
mod sha256;
mod types;
mod verify;

pub use authoriser::{
    MIN_SECRET_BYTES, SECRET_PATH_ENV_VAR, SecretRefusal, TrustedAuthoriserSet,
    load_trusted_set_from_env, load_trusted_set_from_path,
};
pub use cohort::{CohortRefusal, VerifiedCohort, load_verified_cohort};
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
