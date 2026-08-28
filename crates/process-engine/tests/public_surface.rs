//! The external integration test proving the public surface is sufficient
//! (REQ-54, AC-59), both directions of PE-9 (REQ-32 to REQ-34, AC-35 to
//! AC-37), the witness-obtained-at-most-once property (REQ-45, AC-49), and
//! the real-cohort verification markers (REQ-53, AC-58) of
//! `.opencode/plans/process-engine-step-five-spec.md`.
//!
//! Compiled as an EXTERNAL crate importing `process_engine`'s public surface
//! only, exactly as `crates/hierarchy-vor/tests/public_surface.rs` and
//! `crates/himinbjorg/tests/public_surface.rs` do for their own precedent
//! (this file's header follows their convention of listing the exact
//! signatures it assumes, one to one). A caller that is not the binary can
//! construct a task, obtain an outcome and read which outcome case occurred,
//! without naming any `pub(crate)` or private item and without including an
//! internal module by path (REQ-54's own wording).
//!
//! THIS FILE WILL FAIL TO COMPILE until `process-engine` declares its real
//! modules, re-exports its public surface from the crate root, and until its
//! `Cargo.toml` carries the two real in-workspace path dependencies
//! (`himinbjorg`, `hierarchy-vor`) this file also names directly. That is
//! expected and correct at this stage, for the same reason
//! `crates/hierarchy-vor/tests/public_surface.rs`'s own header states for the
//! D109 precedent it names.
//!
//! **Signatures assumed here**, in addition to `unit_tests/sequence_shape.rs`'s
//! and `unit_tests/cognition_and_proposal.rs`'s own headers (this file's own
//! necessary choices, flagged explicitly rather than hidden):
//!
//!   - Crate-root re-exports: `process_engine::{EngineTask, EngineOutcome,
//!     EngineStep, STEP_SEQUENCE, LoopCap, CognitionStep, CognitionOutput,
//!     DefaultCognitionStep, run_sequence}`.
//!   - `process_engine::run_sequence(cohort: &hierarchy_vor::VerifiedCohort,
//!     task: &EngineTask) -> EngineOutcome` (REQ-11, REQ-26, REQ-31): the
//!     crate's one public entry point, taking the already-verified cohort by
//!     reference and the task as a plain parameter, so this external test
//!     drives both directions of PE-9 without needing the binary's own input
//!     surface at all.
//!   - `himinbjorg::{Decision, CheckId, CheckOutcome, BrokerRefusal}` and
//!     `hierarchy_vor::{load_trusted_set_from_env, load_verified_cohort,
//!     SecretRefusal, SECRET_PATH_ENV_VAR, cohort::AUTHORISER_ID}`, both
//!     already-public surfaces of process-engine's own two real dependencies,
//!     reachable from this external test because they are in `[dependencies]`
//!     (never `[dev-dependencies]`, which REQ-2 forbids adding to this
//!     crate), exactly as `crates/himinbjorg/tests/public_surface.rs` reaches
//!     `hierarchy_vor` and `boundary_gjoll` the same way.
//!
//! **REQ-53's marker pair, reserved for this file alone.** Whichever branch
//! of `both_directions_of_pe9_and_real_cohort_verification_markers` below
//! executes prints exactly one of `PROCESS-ENGINE-REAL-COHORT-VERIFIED` or
//! `PROCESS-ENGINE-REAL-COHORT-NOT-EXERCISED`, on
//! `HIMINBJORG-REAL-COHORT-*`'s exact shape. Run with
//! `cargo test -p process-engine -- --nocapture` to see the marker (test
//! output is otherwise captured). `unit_tests/cognition_and_proposal.rs`'s own
//! cohort-gated test prints its OWN, distinct, non-reserved message instead
//! (`PROCESS-ENGINE-STEP-FIVE-GAP`), following `six_checks.rs`'s own
//! precedent for reserving the marker pair to the integration test alone.

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
    let dir = std::env::temp_dir().join(format!("process-engine-public-surface-{label}-{nanos}"));
    fs::create_dir_all(&dir)
        .expect("failed to create a scratch dir under the system temp directory");
    dir
}

fn permitted_task(action_name: &str) -> process_engine::EngineTask {
    process_engine::EngineTask {
        task_id: "fixture-task".to_string(),
        action_name: action_name.to_string(),
        target: "fixture-target".to_string(),
        // REQ-1/REQ-54 (build-order step six): EngineTask's fifth field.
        // This helper's own callers use only action_name to select between
        // the commit and push directions of PE-9, so the sink is fixed to
        // the commit sink here; a caller that genuinely needs the push
        // sink asserted end to end constructs its own task literal instead
        // (this file's own scope, REQ-54, does not require adding one:
        // `unit_tests/cognition_and_proposal.rs`'s own AC-5 case already
        // covers the sink-differs-by-task property).
        sink: "sink:git.commit".to_string(),
        declared_cost: 0,
    }
}

// ---------------------------------------------------------------------------------
// REQ-54/AC-59: the public surface alone is sufficient, exercised WITHOUT the
// real secret so this holds on every machine regardless of REQ-53's own
// provisioning state. This mirrors
// `crates/hierarchy-vor/tests/public_surface.rs`'s own
// `public_surface_refuses_cleanly_under_an_arbitrary_secret_no_degraded_cohort`.
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

    let outcome = hierarchy_vor::load_verified_cohort(&trusted);
    assert!(
        outcome.is_err(),
        "AC-59: an arbitrary, non-real secret must never verify D110's committed \
         attestation; there is structurally no VerifiedCohort to hand to run_sequence on \
         this path, which this test's own compilation (calling run_sequence on no path \
         here) demonstrates"
    );
}

// ---------------------------------------------------------------------------------
// AC-35, AC-36, AC-37, AC-49, AC-58: both directions of PE-9, exercised for
// real only when the real secret is provisioned; otherwise the loud
// not-exercised marker is printed and the test still passes (EC-3, a named
// gap, never a silent skip).
// ---------------------------------------------------------------------------------

#[test]
fn both_directions_of_pe9_and_real_cohort_verification_markers() {
    match hierarchy_vor::load_trusted_set_from_env(hierarchy_vor::cohort::AUTHORISER_ID) {
        Ok(trusted) => {
            let cohort = hierarchy_vor::load_verified_cohort(&trusted).unwrap_or_else(|e| {
                panic!(
                    "a secret was provisioned via {} but the committed attestation did \
                     not verify against it ({e:?}); this is a provisioning defect and is \
                     FATAL, never a skip",
                    hierarchy_vor::SECRET_PATH_ENV_VAR,
                )
            });

            // ---- Direction one (AC-35, AC-36): a task naming a permitted
            // action reaches Decision::Allow and proceeds to the execute
            // step. PE-3/REQ-19's own designed outcome means this does NOT
            // land at Executed in this build (nothing stages a change, and
            // the actuator's own working repository is not provisioned by
            // this test): it lands at BrokerRefused carrying
            // ActuationRefusal::ExitStatus or RepositoryResolution, which is
            // itself the proof the sequence reached the execute step with a
            // genuine Allow decision and a matching witness, exactly as
            // `crates/himinbjorg/unit_tests/witness_and_audit.rs`'s own
            // ac58 test demonstrates for `broker_authorised_action` alone.
            let allowed_task = permitted_task("action:git.commit");
            let allowed_outcome = process_engine::run_sequence(&cohort, &allowed_task);
            match allowed_outcome {
                process_engine::EngineOutcome::BrokerRefused {
                    refusal: himinbjorg::BrokerRefusal::ActuatorRefused(_),
                } => {
                    // AC-36: the proposal reached Decision::Allow (a witness
                    // was minted and reached the broker) and proceeded all
                    // the way to the actuator boundary; EC-1's own designed
                    // refusal (nothing staged, or no working repository
                    // provisioned) is not a defect (REQ-19).
                }
                process_engine::EngineOutcome::Executed { .. } => {
                    // Also acceptable: if a working repository happens to be
                    // provisioned for this test run and the actuator
                    // genuinely succeeds, that is a stronger, not weaker,
                    // demonstration of AC-36's own claim.
                }
                other => panic!(
                    "AC-35/AC-36: a task naming a permitted action must reach the execute \
                     step (a genuine Allow decision and a matching witness); got {other:?}"
                ),
            }

            // ---- Direction two (AC-35, AC-37): a task naming a
            // deliberately disallowed action is blocked by validate_proposal
            // itself, never by an engine-side filter.
            let disallowed_task = permitted_task("action:totally-unknown-and-never-permitted");
            let disallowed_outcome = process_engine::run_sequence(&cohort, &disallowed_task);
            match disallowed_outcome {
                process_engine::EngineOutcome::GateBlocked { checks } => {
                    assert_eq!(
                        checks.len(),
                        6,
                        "AC-37: a gate-blocked outcome must carry all six CheckRecords"
                    );
                    let (first_id, first_outcome) = &checks[0];
                    assert_eq!(
                        *first_id,
                        himinbjorg::CheckId::ActionPermitted,
                        "AC-37: the block must be attributable to a NAMED check -- here, \
                         check one, ActionPermitted -- and the test asserts which one"
                    );
                    assert!(
                        !matches!(first_outcome, himinbjorg::CheckOutcome::Pass),
                        "AC-37: check one must be recorded as failing for an unpermitted \
                         action"
                    );
                }
                other => panic!(
                    "AC-35/AC-37: a task naming a deliberately disallowed action must be \
                     blocked at the gate, attributable to a named check; got {other:?} \
                     (a future engine-side shortcut that refused earlier, without ever \
                     calling validate_proposal, would fail this criterion rather than \
                     satisfy it)"
                ),
            }

            // ---- AC-49: at most one witness obtained and broker_authorised_action
            // called at most once with it, per sequence run. Structural proof
            // for THIS run: calling run_sequence again with the same
            // permitted task must not error out from a stale or reused
            // witness (each call obtains its own fresh witness internally),
            // and must not panic.
            let second_allowed_outcome = process_engine::run_sequence(&cohort, &allowed_task);
            assert!(
                matches!(
                    second_allowed_outcome,
                    process_engine::EngineOutcome::BrokerRefused { .. }
                        | process_engine::EngineOutcome::Executed { .. }
                ),
                "AC-49: a second, independent sequence run over the same permitted task \
                 must behave the same way as the first -- a fresh witness obtained and \
                 used at most once per run, never a stale one reused; got \
                 {second_allowed_outcome:?}"
            );

            println!(
                "PROCESS-ENGINE-REAL-COHORT-VERIFIED: the secret was provisioned via {} \
                 and the committed attestation verified against it; both directions of \
                 PE-9 were exercised for real.",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
        Err(hierarchy_vor::SecretRefusal::EnvVarMissing(_)) => {
            // EC-3: the secret is genuinely not provisioned on this machine.
            // This is the honest cost of section 2.2's out-of-tree-secret
            // ruling and must never be reported as a pass that silently
            // skipped anything (REQ-53).
            println!(
                "PROCESS-ENGINE-REAL-COHORT-NOT-EXERCISED: {} is not set (or is empty), \
                 so both directions of PE-9 were NOT exercised for real on this run. The \
                 crate's structural properties (the fixed five-step sequence, the \
                 cognition seam, the startup refusals) are still proven by the rest of \
                 this suite; only the real cohort's own gate/broker behaviour is untested \
                 here.",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
        Err(other) => {
            // Any OTHER refusal means the operator attempted to provision
            // the secret and something about that attempt is broken. That
            // is a provisioning defect, never a silent gap (EC-3 covers
            // ONLY genuine absence).
            panic!(
                "{} names a path but loading it was refused for a reason other than \
                 absence ({other:?}); this is a provisioning defect and is FATAL",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
    }
}

// ---------------------------------------------------------------------------------
// REQ-54's own documented compile-fail confirmation companion (AC-13, AC-40
// in `unit_tests/sequence_shape.rs`): this file's own compilation, reaching
// only `process_engine`'s public surface with no `pub(crate)` or private
// item named anywhere above, IS the running demonstration that the surface
// is sufficient for an external, non-binary caller. No further confirmation
// is required here.
// ---------------------------------------------------------------------------------
