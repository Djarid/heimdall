//! The external integration test proving the public surface is sufficient
//! (REQ-54, AC-59), both directions of PE-9 (REQ-32 to REQ-34, AC-35 to
//! AC-37), the witness-obtained-at-most-once property (REQ-45, AC-49), and
//! the real-cohort verification markers (REQ-53, AC-58) of
//! `.opencode/plans/process-engine-step-five-spec.md`.
//!
//! **Build-order step seven addendum
//! (`.opencode/plans/build-order-step-seven-spec.md` REQ-40, REQ-29;
//! AC-42).** `run_sequence` gains a third parameter,
//! `process_engine::CognitionBinding`, and stays the crate's **one**
//! public library entry point. Every call to `run_sequence` in this file
//! is updated to pass `process_engine::CognitionBinding::Stub`, since this
//! file's own scope (both directions of PE-9, over `DefaultCognitionStep`'s
//! own behaviour) is unaffected by the addition of a second, real
//! implementation: `CognitionBinding::Real`'s own behaviour needs the
//! model-bound path (`crates/cognition-client/`) provisioned, which is
//! confirmed only by hand (AC-1, AC-2 of the step-seven spec), never by an
//! automated test.
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
//!     CognitionRefusal, CognitionBinding, DefaultCognitionStep, run_sequence,
//!     EXIT_COGNITION_REFUSAL}`.
//!   - `process_engine::run_sequence(cohort: &hierarchy_vor::VerifiedCohort,
//!     task: &EngineTask, binding: CognitionBinding) -> EngineOutcome`
//!     (REQ-11, REQ-26, REQ-31; build-order step seven REQ-40): the crate's
//!     one public entry point, taking the already-verified cohort by
//!     reference, the task as a plain parameter and, as of build-order step
//!     seven, a third parameter naming which of the two CognitionStep
//!     implementations to run, so this external test drives both directions
//!     of PE-9 without needing the binary's own input surface at all.
//!     `process_engine::CognitionBinding::Stub` is passed at every call site
//!     below: this file's own scope is `DefaultCognitionStep`'s behaviour,
//!     unaffected by the real implementation's addition.
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
            let allowed_outcome = process_engine::run_sequence(
                &cohort,
                &allowed_task,
                process_engine::CognitionBinding::Stub,
            );
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
            let disallowed_outcome = process_engine::run_sequence(
                &cohort,
                &disallowed_task,
                process_engine::CognitionBinding::Stub,
            );
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
            let second_allowed_outcome = process_engine::run_sequence(
                &cohort,
                &allowed_task,
                process_engine::CognitionBinding::Stub,
            );
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

// ===================================================================================
// Build-order step seven (`.opencode/plans/build-order-step-seven-spec.md`),
// section 5.7: the two new task members M1 and M2, and the sixth exit code
// (REQ-40, REQ-50; AC-42, AC-52). Gated behind a real cohort, following
// this file's own established convention above.
//
// **What this suite does NOT claim (AC-1, AC-2 of the spec).** These tests
// exercise CognitionBinding::Stub only, never CognitionBinding::Real: the
// real cognition implementation needs the model sidecar
// (`crates/cognition-client/`) and its own two path-shaped environment
// variables provisioned, which this automated suite never provisions (per
// the spec's own AC-1: "not confirmable by any cargo test or harness run,
// and no test is to be written that fakes it"). What this suite DOES prove
// is the structural half available without the model: that
// CognitionBinding::Stub, run against M1's and M2's own task shapes (same
// action name, target and sink REQ-47 fixes, but bound to the stub rather
// than to the real implementation), reaches the SAME check-five block the
// spec's own M1/M2 table describes for the real path, because the stub's
// own parameter is Canonical/Inert and therefore does NOT itself trigger
// check five -- so a stub-bound run over M1's own action/target/sink is
// expected to reach `Executed` or `BrokerRefused` (the same outcome class
// P1 reaches), never `GateBlocked` on check five. This is a deliberately
// WEAKER claim than AC-52's own real-model claim, and this file states the
// difference rather than blurring it.
// ===================================================================================

fn m1_shaped_task() -> process_engine::EngineTask {
    process_engine::EngineTask {
        task_id: "fixture-task-m1-shape".to_string(),
        action_name: "action:git.commit".to_string(),
        target: "fixture-target".to_string(),
        sink: "sink:git.commit".to_string(),
        declared_cost: 0,
    }
}

fn m2_shaped_task() -> process_engine::EngineTask {
    process_engine::EngineTask {
        task_id: "fixture-task-m2-shape".to_string(),
        action_name: "action:git.merge".to_string(),
        target: "fixture-target".to_string(),
        sink: "sink:git.commit".to_string(),
        declared_cost: 0,
    }
}

#[test]
fn m1_shaped_task_under_the_stub_binding_does_not_block_at_check_five() {
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
            let task = m1_shaped_task();
            let outcome = process_engine::run_sequence(
                &cohort,
                &task,
                process_engine::CognitionBinding::Stub,
            );
            match outcome {
                process_engine::EngineOutcome::GateBlocked { checks } => {
                    let (fifth_id, fifth_outcome) = &checks[4];
                    assert_eq!(*fifth_id, himinbjorg::CheckId::TaintCompatible);
                    assert!(
                        matches!(fifth_outcome, himinbjorg::CheckOutcome::Pass),
                        "AC-52's own contrast case: an M1-shaped task run under \
                         CognitionBinding::Stub (Canonical/Inert, never Tainted/Action) \
                         must PASS check five, unlike the real implementation's own \
                         Tainted/Action declaration, which blocks it. Getting the same \
                         block under the stub would mean the block is not attributable \
                         to the model's own honest declaration at all; got a failing \
                         check five under the stub"
                    );
                }
                process_engine::EngineOutcome::BrokerRefused { .. }
                | process_engine::EngineOutcome::Executed { .. } => {
                    // Expected: the stub's own Canonical/Inert parameter
                    // triggers no rule-core reason, so the sequence
                    // proceeds past the gate exactly as P1 does.
                }
                other => panic!(
                    "AC-52's own contrast case: an M1-shaped task under \
                     CognitionBinding::Stub must reach the execute step, not a \
                     structural refusal; got {other:?}"
                ),
            }
        }
        Err(hierarchy_vor::SecretRefusal::EnvVarMissing(_)) => {
            println!(
                "PROCESS-ENGINE-STEP-SEVEN-GAP: m1_shaped_task_under_the_stub_binding_does_not_block_at_check_five: \
                 SKIPPED -- {} is not set, so this test cannot obtain a real \
                 VerifiedCohort.",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
        Err(other) => panic!(
            "{} names a path but loading it was refused for a reason other than absence \
             ({other:?}); this is a provisioning defect and is FATAL",
            hierarchy_vor::SECRET_PATH_ENV_VAR,
        ),
    }
}

#[test]
fn m2_shaped_task_under_the_stub_binding_blocks_at_check_one_only_never_check_five() {
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
            let task = m2_shaped_task();
            let outcome = process_engine::run_sequence(
                &cohort,
                &task,
                process_engine::CognitionBinding::Stub,
            );
            match outcome {
                process_engine::EngineOutcome::GateBlocked { checks } => {
                    assert_eq!(checks.len(), 6, "AC-52: all six CheckRecords must be present");
                    let (first_id, first_outcome) = &checks[0];
                    assert_eq!(*first_id, himinbjorg::CheckId::ActionPermitted);
                    assert!(
                        !matches!(first_outcome, himinbjorg::CheckOutcome::Pass),
                        "AC-52: action:git.merge is out of the cohort's permitted-action \
                         surface today, so check one must fail regardless of which \
                         cognition binding is used"
                    );
                    let (fifth_id, fifth_outcome) = &checks[4];
                    assert_eq!(*fifth_id, himinbjorg::CheckId::TaintCompatible);
                    assert!(
                        matches!(fifth_outcome, himinbjorg::CheckOutcome::Pass),
                        "AC-52's own contrast case: under CognitionBinding::Stub, check \
                         five must PASS (the stub's own parameter is Canonical/Inert), \
                         unlike M2's own real-implementation case which fails BOTH check \
                         one and check five; got a failing check five under the stub"
                    );
                }
                other => panic!(
                    "AC-52: an M2-shaped task (action:git.merge, absent from the \
                     cohort's permitted-action surface) must be GateBlocked regardless \
                     of cognition binding; got {other:?}"
                ),
            }
        }
        Err(hierarchy_vor::SecretRefusal::EnvVarMissing(_)) => {
            println!(
                "PROCESS-ENGINE-STEP-SEVEN-GAP: m2_shaped_task_under_the_stub_binding_blocks_at_check_one_only_never_check_five: \
                 SKIPPED -- {} is not set, so this test cannot obtain a real \
                 VerifiedCohort.",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
        Err(other) => panic!(
            "{} names a path but loading it was refused for a reason other than absence \
             ({other:?}); this is a provisioning defect and is FATAL",
            hierarchy_vor::SECRET_PATH_ENV_VAR,
        ),
    }
}

// ---------------------------------------------------------------------------------
// AC-32/REQ-29: EXIT_COGNITION_REFUSAL is reachable from outside the crate
// and is distinct from every other exit-code constant.
// ---------------------------------------------------------------------------------

#[test]
fn exit_cognition_refusal_is_reachable_and_distinct_from_every_other_exit_code() {
    let codes = [
        process_engine::EXIT_EXECUTED,
        process_engine::EXIT_STARTUP_REFUSAL,
        process_engine::EXIT_GATE_BLOCKED,
        process_engine::EXIT_BROKER_REFUSED,
        process_engine::EXIT_WELL_FORMEDNESS_REFUSAL,
        process_engine::EXIT_COGNITION_REFUSAL,
    ];
    let mut unique = codes.to_vec();
    unique.sort_unstable();
    unique.dedup();
    assert_eq!(
        unique.len(),
        6,
        "AC-32/REQ-29: all six exit-code constants must be distinct and reachable from \
         outside the crate; got {codes:?}"
    );
}

// ---------------------------------------------------------------------------------
// REQ-54's own documented compile-fail confirmation companion (AC-13, AC-40
// in `unit_tests/sequence_shape.rs`): this file's own compilation, reaching
// only `process_engine`'s public surface with no `pub(crate)` or private
// item named anywhere above, IS the running demonstration that the surface
// is sufficient for an external, non-binary caller. No further confirmation
// is required here.
// ---------------------------------------------------------------------------------
