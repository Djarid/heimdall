//! The step-three integration test (REQ-39) and the real-cohort verification with
//! its two markers (REQ-36), section 3.6. Compiled as an EXTERNAL crate importing
//! `hierarchy_vor`'s public surface only, exactly as any future non-test caller
//! (Himinbjörg, step three) would, which is what proves that surface is sufficient
//! (AC-39).
//!
//! THIS FILE WILL FAIL TO COMPILE until `hierarchy_vor` declares its six modules as
//! `pub mod` and re-exports the entry point, the two loaders, the projection type
//! and the three refusal enums from its crate root. That is expected and correct at
//! this stage, for the same reason `crates/boundary-gjoll/tests/layer_two_parity.rs`
//! states in its own header for the D109 precedent.
//!
//! Signatures assumed here, in addition to `unit_tests/substrate_parity.rs`'s and
//! `unit_tests/loader_failclosed.rs`'s headers:
//!
//!   - Crate-root re-exports: `hierarchy_vor::{load_trusted_set_from_env,
//!     load_trusted_set_from_path, load_verified_cohort, SecretRefusal,
//!     RecordRefusal, CohortRefusal, VerifiedCohort, CohortSurface,
//!     TrustedAuthoriserSet, SECRET_PATH_ENV_VAR, MIN_SECRET_BYTES}` (lib.rs's own
//!     documented job: "the public re-exports (the entry point, the two loaders,
//!     the projection and the three refusal enums)").
//!   - `hierarchy_vor::cohort::{COHORT_ID, PERMITTED_ACTIONS, TRUST_CEILING,
//!     CONSEQUENTIAL_SINKS, AUTHORISER_ID}`, `pub` compile-time constants reachable
//!     via the `pub mod cohort;` declaration, needed by any external caller (step
//!     three included) to know which authoriser id to load a trusted set for.
//!   - `VerifiedCohort::surface(&self) -> CohortSurface<'_>` and
//!     `CohortSurface::{cohort_id(&self) -> &str, permitted_actions(&self) ->
//!     &[String], trust_ceiling(&self) -> &str, consequential_sinks(&self) ->
//!     &[String], may_perform(&self, &str) -> bool}` (REQ-25).
//!
//! **REQ-36's two markers are mutually exclusive per run** (section 10, verification
//! command 3: "exactly one of the two ... markers is printed"): whichever branch of
//! `public_surface_sufficiency_and_real_cohort_verification_markers` below executes
//! prints exactly one of `VOR-REAL-COHORT-VERIFIED` or
//! `VOR-REAL-COHORT-NOT-EXERCISED`, distinct strings a caller can grep for
//! unambiguously. Run with `cargo test -p hierarchy-vor -- --nocapture` to see the
//! marker (test output is otherwise captured).

use std::fs;
#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

fn scratch_dir(label: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock before the Unix epoch")
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("hierarchy-vor-public-surface-{label}-{nanos}"));
    fs::create_dir_all(&dir)
        .expect("failed to create a scratch dir under the system temp directory");
    dir
}

// ---------------------------------------------------------------------------------
// REQ-39: the public surface alone is sufficient, exercised WITHOUT the real
// secret so this holds on every machine regardless of REQ-36's provisioning state.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn public_surface_refuses_cleanly_under_an_arbitrary_secret_no_degraded_cohort() {
    let dir = scratch_dir("arbitrary-secret");
    let secret_path = dir.join("secret");
    fs::write(
        &secret_path,
        b"arbitrary-non-real-secret-of-thirty-two-bytes!!",
    )
    .expect("failed to write fixture secret file");
    fs::set_permissions(&secret_path, fs::Permissions::from_mode(0o600))
        .expect("failed to set fixture secret file permissions");

    let trusted = hierarchy_vor::load_trusted_set_from_path(
        hierarchy_vor::cohort::AUTHORISER_ID,
        &secret_path,
    )
    .expect("a well-formed, correctly-permissioned secret file outside the repo must load");

    // REQ-22: the committed attestation is produced out of band under the REAL
    // secret only, so an arbitrary secret can never match it. REQ-23: the refusal
    // side of the `Result` carries no cohort at all -- not a degraded, narrowed or
    // empty one -- which this test demonstrates structurally, by the fact there is
    // no `Ok` variant to inspect on this path.
    let outcome = hierarchy_vor::load_verified_cohort(&trusted);
    assert!(
        outcome.is_err(),
        "an arbitrary, non-real secret must never verify the committed attestation; \
         got Ok(_), meaning either the attestation is not truly out-of-band (REQ-22) \
         or the loader accepted the wrong secret"
    );
}

// ---------------------------------------------------------------------------------
// REQ-36 and REQ-39 together: obtain a trusted set through the public env-var
// loader, obtain the cohort through the public entry point, and read the permitted
// actions and the sink set through the projection -- exercised for real only when
// the real secret is provisioned (section 2.2); otherwise the loud not-exercised
// marker is printed and the test still passes (EC-3, a named gap, never a silent
// skip and never a pass mistaken for the check having run).
// ---------------------------------------------------------------------------------

#[test]
fn public_surface_sufficiency_and_real_cohort_verification_markers() {
    match hierarchy_vor::load_trusted_set_from_env(hierarchy_vor::cohort::AUTHORISER_ID) {
        Ok(trusted) => {
            let cohort = hierarchy_vor::load_verified_cohort(&trusted).unwrap_or_else(|e| {
                panic!(
                    "a secret was provisioned via {} but the committed attestation did \
                     not verify against it ({e:?}); this is EC-4 (wrong secret or an \
                     altered cohort) and is FATAL, never a skip",
                    hierarchy_vor::SECRET_PATH_ENV_VAR,
                )
            });
            let surface = cohort.surface();

            assert_eq!(
                surface.cohort_id(),
                hierarchy_vor::cohort::COHORT_ID,
                "the verified cohort's projection must report its own declared cohort_id"
            );
            for action in hierarchy_vor::cohort::PERMITTED_ACTIONS {
                assert!(
                    surface.may_perform(action),
                    "the verified cohort's projection must permit its own declared \
                     action {action:?}"
                );
            }
            assert!(
                !surface.may_perform("action:totally-unrelated-and-never-permitted"),
                "the membership test must return false for an action the cohort never \
                 declared"
            );
            assert_eq!(
                surface.trust_ceiling(),
                hierarchy_vor::cohort::TRUST_CEILING,
                "the projection must expose the opaque trust ceiling unchanged"
            );
            for sink in hierarchy_vor::cohort::CONSEQUENTIAL_SINKS {
                assert!(
                    surface.consequential_sinks().iter().any(|s| s == sink),
                    "the verified cohort's projection must include its own declared \
                     sink {sink:?}"
                );
            }

            println!(
                "VOR-REAL-COHORT-VERIFIED: the secret was provisioned via {} and the \
                 committed attestation verified against it.",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
        Err(hierarchy_vor::SecretRefusal::EnvVarMissing(_)) => {
            // EC-3: the secret is genuinely not provisioned on this machine. This is
            // the honest cost of section 2.2's out-of-tree-secret ruling and must
            // never be reported as a pass that silently skipped anything.
            println!(
                "VOR-REAL-COHORT-NOT-EXERCISED: {} is not set (or is empty), so the \
                 real heimdall-dev cohort's own verification was NOT exercised on this \
                 run. Mechanism parity is still proven by the unit-test vector replay \
                 under the committed fixture secret; only the REAL cohort's own \
                 attestation is untested here.",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
        Err(other) => {
            // Any OTHER refusal means the operator attempted to provision the secret
            // and something about that attempt is broken (wrong permissions, an
            // in-tree path, too short, unreadable). That is a provisioning defect,
            // never a silent gap (EC-3 covers ONLY genuine absence).
            panic!(
                "{} names a path but loading it was refused for a reason other than \
                 absence ({other:?}); this is a provisioning defect and is FATAL",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
    }
}

// ---------------------------------------------------------------------------------
// REQ-37: the ONE environment-mutating test in this whole suite (across
// `unit_tests/` and `tests/`). It lives here, in an external integration-test
// crate, rather than under `unit_tests/`, because `hierarchy_vor`'s crate root
// carries `#![forbid(unsafe_code)]` (REQ-2) and this repository's pinned toolchain
// makes `std::env::set_var`/`remove_var` `unsafe fn` (confirmed directly against
// `cargo 1.98.0`); an integration test crate is not bound by the library crate's
// forbid attribute, so this is the only place in the suite REQ-14 case 1 (the
// env-var entry point's own absent-or-empty condition) can be exercised by directly
// mutating the process environment at all.
// ---------------------------------------------------------------------------------

#[test]
fn environment_mutating_req14_case_1_env_var_absent_or_empty_is_refused() {
    let previous = std::env::var(hierarchy_vor::SECRET_PATH_ENV_VAR).ok();

    // SAFETY: test-only mutation of this process's own environment. No other test
    // in this binary reads or writes `HEIMDALL_COHORT_SECRET_FILE` (the test above,
    // `public_surface_sufficiency_and_real_cohort_verification_markers`, only
    // READS it, which remains safe), and each `cargo test` target is compiled to
    // its own OS process, so this cannot affect any other test binary's
    // environment. Cargo's default test harness does run tests in this binary on
    // separate threads, but no other thread here touches this specific variable.
    unsafe {
        std::env::remove_var(hierarchy_vor::SECRET_PATH_ENV_VAR);
    }
    let absent = hierarchy_vor::load_trusted_set_from_env("whichever-authoriser");
    assert!(
        absent.is_err(),
        "REQ-14 case 1: an absent HEIMDALL_COHORT_SECRET_FILE must be refused, never \
         fall back to a default"
    );

    unsafe {
        std::env::set_var(hierarchy_vor::SECRET_PATH_ENV_VAR, "");
    }
    let empty = hierarchy_vor::load_trusted_set_from_env("whichever-authoriser");
    assert!(
        empty.is_err(),
        "REQ-14 case 1: an empty HEIMDALL_COHORT_SECRET_FILE must be refused, never \
         fall back to a default"
    );

    unsafe {
        match &previous {
            Some(v) => std::env::set_var(hierarchy_vor::SECRET_PATH_ENV_VAR, v),
            None => std::env::remove_var(hierarchy_vor::SECRET_PATH_ENV_VAR),
        }
    }
}

// ---------------------------------------------------------------------------------
// REQ-39's documented compile-fail confirmation (AC-24, AC-39). Per section 10's
// "Manual checks", this is explicitly NOT a standing automated test: AC-24's own
// expected failure is "the private associated function error D109 already
// observed for `ConsequentialityVerdict`", i.e. a specific rustc diagnostic that
// must be captured once, by hand, and pasted into the pull request description,
// not asserted by a test harness (a trybuild-style dependency would be a NEW
// dev-dependency for a one-off confirmation, which section 9.1's line budget and
// REQ-1's exact-pin discipline both argue against for a check this narrow).
//
// To run this confirmation once the crate exists: uncomment ONE of the blocks
// below, run `cargo build -p hierarchy-vor --tests`, capture rustc's exact error,
// and record it in the pull request. Leave all of them commented in the committed
// file, otherwise this crate never builds at all.
//
// ```rust,ignore
// // (a) No public constructor: `VerifiedCohort` has no `pub fn new`, no public
// // tuple constructor and no public field. Expected: E0423 or E0616 (private
// // field / cannot construct).
// let _bad = hierarchy_vor::VerifiedCohort { /* fields, if any were visible */ };
//
// // (b) No public `From`/`TryFrom` and no `Deref` to the unverified definition.
// // Expected: E0277 (trait not implemented) for whichever conversion is attempted.
// let _bad: hierarchy_vor::VerifiedCohort = hierarchy_vor::cohort::CohortDefinitionIfPublic::default().into();
//
// // (c) No `Clone`, `Copy` or `Default`. Expected: E0599 (no method named `clone`
// // / `Default` not satisfied) on a `VerifiedCohort` obtained from
// // `load_verified_cohort`.
// // let _bad = verified_cohort.clone();
// ```
//
// AC-13's companion confirmation (no way to construct a `TrustedAuthoriserSet`
// directly) is the same shape: attempting `hierarchy_vor::TrustedAuthoriserSet { .. }`
// or any public constructor taking secret bytes must fail to compile, expected
// error E0423/E0616, captured the same way.
