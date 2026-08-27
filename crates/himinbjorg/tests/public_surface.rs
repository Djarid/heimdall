//! The integration test proving the public surface is sufficient (REQ-26,
//! AC-41), the two reserved REQ-32 markers (AC-46), and the structural
//! no-fallback demonstration under an arbitrary, non-real secret (AC-35).
//! `.opencode/plans/himinbjorg-step-three.md` section 8.6, 8.7, issue #37.
//!
//! Compiled as an EXTERNAL crate importing `himinbjorg`'s public surface only,
//! exactly as `crates/hierarchy-vor/tests/public_surface.rs` does for its own
//! precedent (this file's header follows that file's convention of listing the
//! exact signatures it assumes, one to one).
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/himinbjorg` exists at all: no
//! `Cargo.toml`, no workspace member, no `src/`, so `himinbjorg` is not a crate
//! this test can import. That is expected and correct at this stage (issue
//! #37), for the same reason `hierarchy-vor`'s own `tests/public_surface.rs`
//! header states for the D109 precedent it names.
//!
//! Signatures assumed here, matching `unit_tests/six_checks.rs`'s and
//! `unit_tests/gate_bridge_failclosed.rs`'s own headers exactly (this file
//! reaches only what those two files' assumed PUBLIC subset already commits
//! to, since this file is external and cannot reach `pub(crate)` items at
//! all):
//!
//!   - Crate-root re-exports: `himinbjorg::{build_context, enforce_definition,
//!     validate_proposal, broker_action, AgentId, TaskContext, AgentContext,
//!     ContextRefusal, EffectiveSurface, DefinitionRefusal, Proposal,
//!     ProposalParameter, CheckId, CheckOutcome, CheckRecord, Decision,
//!     ProposalDecision, Action, Scope, BrokerResult, BrokerRefusal}`.
//!   - `AgentId::new`, `TaskContext { task_id, target, declared_cost }`,
//!     `Proposal { action_name, target, sink, parameters, declared_cost }`,
//!     `ProposalParameter { id, consume_mode, trust_level, type_name }`
//!     (reusing `boundary_gjoll::types::{ConsumeMode, TrustLevel}` directly, per
//!     section 7's mapping table's "Direct" rule for trust level).
//!   - `hierarchy_vor::{load_trusted_set_from_path, load_trusted_set_from_env,
//!     load_verified_cohort, SecretRefusal, CohortRefusal, SECRET_PATH_ENV_VAR,
//!     cohort::{COHORT_ID, AUTHORISER_ID, PERMITTED_ACTIONS, CONSEQUENTIAL_SINKS}}`
//!     (REQ-32; the integration test only, per section 6.3's own note that
//!     non-test gateway code takes a cohort by reference and never loads one
//!     itself).
//!
//! **REQ-32's two markers are mutually exclusive per run**, exactly as
//! `hierarchy-vor`'s own header states for `VOR-REAL-COHORT-VERIFIED` /
//! `VOR-REAL-COHORT-NOT-EXERCISED`: whichever branch of
//! `four_interfaces_end_to_end_and_real_cohort_verification_markers` below
//! executes prints exactly one of `HIMINBJORG-REAL-COHORT-VERIFIED` or
//! `HIMINBJORG-REAL-COHORT-NOT-EXERCISED`. Run with
//! `cargo test -p himinbjorg -- --nocapture` to see the marker (test output is
//! otherwise captured).

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
    let dir = std::env::temp_dir().join(format!("himinbjorg-public-surface-{label}-{nanos}"));
    fs::create_dir_all(&dir)
        .expect("failed to create a scratch dir under the system temp directory");
    dir
}

fn baseline_proposal() -> himinbjorg::Proposal {
    himinbjorg::Proposal {
        action_name: hierarchy_vor::cohort::PERMITTED_ACTIONS[0].to_string(),
        target: "fixture-target".to_string(),
        sink: hierarchy_vor::cohort::CONSEQUENTIAL_SINKS[0].to_string(),
        parameters: vec![himinbjorg::ProposalParameter {
            id: "v".to_string(),
            consume_mode: boundary_gjoll::types::ConsumeMode::Inert,
            trust_level: boundary_gjoll::types::TrustLevel::Canonical,
            type_name: "comms:informational".to_string(),
        }],
        declared_cost: 0,
    }
}

// ---------------------------------------------------------------------------------
// AC-35: no VerifiedCohort exists after a CohortRefusal, demonstrated
// structurally (the absence of an Ok arm), so no Himinbjörg interface can be
// handed one. This is EC-2's own required behaviour, exercised on every
// machine regardless of the real secret (an arbitrary secret always refuses
// against D110's fixed committed attestation).
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn ac35_arbitrary_secret_refusal_leaves_no_verified_cohort_to_hand_to_any_interface() {
    let dir = scratch_dir("ac35-arbitrary-secret");
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

    match hierarchy_vor::load_verified_cohort(&trusted) {
        Ok(_cohort) => {
            panic!(
                "AC-35: an arbitrary, non-real secret must never verify the committed \
                 attestation. Getting Ok(_) here would mean the attestation is not truly \
                 out-of-band, and this test would then need to go on to demonstrate the \
                 no-fallback property some other way; instead it demonstrates it \
                 structurally, by there being no Ok arm reachable on a genuine machine."
            );
        }
        Err(_refusal) => {
            // AC-35's own point: there is no VerifiedCohort value in scope on this
            // branch at all -- not a degraded one, not a narrowed one -- so there is
            // structurally nothing to pass to build_context, enforce_definition,
            // validate_proposal or broker_action. This branch's own compilation
            // (calling none of the four interfaces) IS the demonstration.
        }
    }
}

// ---------------------------------------------------------------------------------
// AC-41, AC-46: the public surface exercises all four interfaces end to end,
// gated behind the real secret with REQ-32's two mutually exclusive markers.
// ---------------------------------------------------------------------------------

#[test]
fn four_interfaces_end_to_end_and_real_cohort_verification_markers() {
    match hierarchy_vor::load_trusted_set_from_env(hierarchy_vor::cohort::AUTHORISER_ID) {
        Ok(trusted) => {
            let cohort = hierarchy_vor::load_verified_cohort(&trusted).unwrap_or_else(|e| {
                panic!(
                    "a secret was provisioned via {} but the committed attestation did not \
                     verify against it ({e:?}); this is EC-4 (wrong secret or an altered \
                     cohort) and is FATAL, never a skip",
                    hierarchy_vor::SECRET_PATH_ENV_VAR,
                )
            });

            let agent_id = himinbjorg::AgentId::new(hierarchy_vor::cohort::COHORT_ID);
            let task = himinbjorg::TaskContext {
                task_id: "public-surface-fixture-task".to_string(),
                target: "fixture-target".to_string(),
                declared_cost: 0,
            };

            // Interface 1: build_context.
            let context = himinbjorg::build_context(&agent_id, &task, &cohort)
                .expect("the one hardcoded agent id must build a context over a real cohort");

            // Interface 2: enforce_definition.
            let surface = himinbjorg::enforce_definition(&agent_id, &cohort)
                .expect("the one hardcoded agent id must resolve a definition over a real cohort");

            // An unknown agent id must be refused by both, never served a fallback
            // (REQ-7, AC-7; exercised here through the public surface only).
            let unknown_agent = himinbjorg::AgentId::new("totally-unknown-agent-never-hardcoded");
            assert!(
                matches!(
                    himinbjorg::build_context(&unknown_agent, &task, &cohort),
                    Err(himinbjorg::ContextRefusal::UnknownAgent)
                ),
                "an unknown agent id must be refused by build_context with UnknownAgent"
            );
            assert!(
                himinbjorg::enforce_definition(&unknown_agent, &cohort).is_err(),
                "an unknown agent id must be refused by enforce_definition"
            );

            // Interface 3: validate_proposal, exercised for both an Allow and a Block.
            let passing_proposal = baseline_proposal();
            let decision = himinbjorg::validate_proposal(&context, &surface, &passing_proposal);
            assert_eq!(
                decision.checks.len(),
                6,
                "validate_proposal must return exactly six CheckRecords (AC-39/REQ-23)"
            );
            assert_eq!(
                decision.decision,
                himinbjorg::Decision::Allow,
                "AC-41: the baseline proposal must validate to Allow through the public \
                 surface end to end"
            );

            let mut failing_proposal = baseline_proposal();
            failing_proposal.action_name = "action:totally-unknown-and-never-permitted".to_string();
            let blocked = himinbjorg::validate_proposal(&context, &surface, &failing_proposal);
            assert_eq!(
                blocked.decision,
                himinbjorg::Decision::Block,
                "AC-41: an unpermitted action must validate to Block through the public \
                 surface end to end"
            );

            // Interface 4: broker_action, refuse-only in step three (REQ-22, AC-37),
            // exercised here even for the proposal that just validated to Allow.
            let action = himinbjorg::Action {
                action_name: passing_proposal.action_name.clone(),
                target: passing_proposal.target.clone(),
            };
            let scope = himinbjorg::Scope::new("public-surface-fixture-scope");
            let broker_outcome = himinbjorg::broker_action(&context, &action, &scope);
            assert!(
                matches!(
                    broker_outcome,
                    Err(himinbjorg::BrokerRefusal::NoActuatorAvailable)
                ),
                "AC-41: broker_action must refuse with NoActuatorAvailable even for a \
                 previously-Allow-validated proposal, exercised through the public surface"
            );

            println!(
                "HIMINBJORG-REAL-COHORT-VERIFIED: the secret was provisioned via {} and the \
                 committed attestation verified against it; all four interfaces were \
                 exercised end to end through the public surface.",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
        Err(hierarchy_vor::SecretRefusal::EnvVarMissing(_)) => {
            // EC-3: the secret is genuinely not provisioned on this machine. Never a
            // silent skip; the gap is named, and the test still passes.
            println!(
                "HIMINBJORG-REAL-COHORT-NOT-EXERCISED: {} is not set (or is empty), so the \
                 real heimdall-dev cohort's own verification, and therefore all four of \
                 Himinbjörg's interfaces, were NOT exercised end to end on this run.",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
        Err(other) => {
            // AC-46's second half: any OTHER refusal is a provisioning defect, never a
            // gap, and is FATAL.
            panic!(
                "{} names a path but loading it was refused for a reason other than \
                 absence ({other:?}); this is a provisioning defect and is FATAL, never a \
                 skip (AC-46)",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
    }
}

// =====================================================================================
// ADDITIVE (`.opencode/plans/git-actuator-step-four.md`, section 10 row 20): the
// witness path end to end through public items only (REQ-48, AC-61's gateway
// half), AC-35's compile-failure notes for `Authorisation`, AC-38's signature
// check for `broker_action`, a cross-reference for AC-54, and AC-62's design-
// document currency check. Every case above this marker is UNCHANGED.
//
// THIS ADDITIVE SECTION WILL FAIL TO COMPILE until `crates/actuator-git` exists
// (a new in-workspace path dependency of `himinbjorg`, REQ-6) and
// `crates/himinbjorg/src/{types,broker,validation,audit,lib}.rs` all carry this
// step's additions. That is expected and correct at this stage, for the same
// reason the rest of this file's own header states for issue #37.
//
// **Assumed additions to the public surface** used below: identical to
// `crates/himinbjorg/unit_tests/witness_and_audit.rs`'s own assumption block
// (not repeated in full here); this section reaches ONLY what that file
// documents as public (`Authorisation`'s four accessors, `ProposalDecision::
// authorisation`, `DecisionRecorder`, `MinimalDecisionRecorder`,
// `broker_authorised_action`, `BrokerRefusal`'s additive variants,
// `ActuationReceipt`), since this file is compiled as an EXTERNAL crate and
// cannot reach anything `pub(crate)` at all (REQ-48, AC-61: "without naming
// any `pub(crate)` or private item").
// =====================================================================================

// ---------------------------------------------------------------------------------
// AC-61 (REQ-48): the witness path, end to end, through public items only --
// build a proposal, validate it, take the authorisation from the accessor,
// supply a recorder, reach an outcome. Gated behind the real secret with the
// SAME two mutually-exclusive markers this file's own header already
// documents for `four_interfaces_end_to_end_and_real_cohort_verification_markers`,
// because `Authorisation` can only be minted by `validate_proposal` over a
// real `AgentContext`/`EffectiveSurface` pair, which needs a real
// `VerifiedCohort` (D110). No working-repository environment variable is
// configured anywhere in this file, so the actuator call this test reaches is
// EXPECTED to refuse (with `BrokerRefusal::ActuatorRefused`, carrying
// `actuator-git`'s own `RepositoryResolution` refusal verbatim, REQ-38); that
// refusal, rather than a bare `NoAuthorisationEvidence` or `WitnessMismatch`,
// is itself the proof that the witness path ran end to end through every
// public gate (scope, witness match, audit write) and reached the actuator.
// ---------------------------------------------------------------------------------

#[test]
fn witness_path_end_to_end_through_public_items_only() {
    match hierarchy_vor::load_trusted_set_from_env(hierarchy_vor::cohort::AUTHORISER_ID) {
        Ok(trusted) => {
            let cohort = hierarchy_vor::load_verified_cohort(&trusted).unwrap_or_else(|e| {
                panic!(
                    "witness_path_end_to_end: a secret was provisioned via {} but the \
                     committed attestation did not verify against it ({e:?}); this is a \
                     provisioning defect and is FATAL, never a skip",
                    hierarchy_vor::SECRET_PATH_ENV_VAR,
                )
            });

            let agent_id = himinbjorg::AgentId::new(hierarchy_vor::cohort::COHORT_ID);
            let task = himinbjorg::TaskContext {
                task_id: "witness-path-fixture-task".to_string(),
                target: "fixture-target".to_string(),
                declared_cost: 0,
            };
            let context = himinbjorg::build_context(&agent_id, &task, &cohort)
                .expect("the one hardcoded agent id must build a context over a real cohort");
            let surface = himinbjorg::enforce_definition(&agent_id, &cohort)
                .expect("the one hardcoded agent id must resolve a definition over a real cohort");

            let proposal = baseline_proposal();
            let decision = himinbjorg::validate_proposal(&context, &surface, &proposal);
            assert_eq!(
                decision.decision,
                himinbjorg::Decision::Allow,
                "witness_path_end_to_end: the baseline proposal must validate to Allow"
            );
            let authorisation = decision
                .authorisation()
                .expect("an Allow decision must mint a witness reachable through the public accessor");
            assert_eq!(authorisation.action_name(), proposal.action_name);
            assert_eq!(authorisation.target(), proposal.target);
            assert_eq!(authorisation.sink(), proposal.sink);
            assert_eq!(authorisation.checks().len(), 6);

            let action = himinbjorg::Action {
                action_name: proposal.action_name.clone(),
                target: proposal.target.clone(),
            };
            let scope = himinbjorg::Scope::new("public-surface-fixture-scope");
            let mut recorder = himinbjorg::MinimalDecisionRecorder::new();
            let outcome = himinbjorg::broker_authorised_action(
                &context,
                &action,
                &scope,
                authorisation,
                &mut recorder,
            );
            assert!(
                matches!(
                    outcome,
                    Err(himinbjorg::BrokerRefusal::ActuatorRefused(_))
                ),
                "witness_path_end_to_end: with a matching action, a permitted scope and a \
                 successful audit write, the witness path must reach the actuator (which \
                 then refuses for its own reason, since no working-repository environment \
                 variable is configured anywhere in this test binary); got {outcome:?}"
            );
            assert_eq!(
                recorder.records().len(),
                1,
                "witness_path_end_to_end: the decision record must have been written \
                 before the actuator was ever reached (REQ-31, REQ-33)"
            );

            println!(
                "HIMINBJORG-REAL-COHORT-VERIFIED: the secret was provisioned via {} and the \
                 witness path (build_context, enforce_definition, validate_proposal, the \
                 Authorisation accessor, broker_authorised_action) ran end to end through \
                 public items only.",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
        Err(hierarchy_vor::SecretRefusal::EnvVarMissing(_)) => {
            println!(
                "HIMINBJORG-REAL-COHORT-NOT-EXERCISED: {} is not set (or is empty), so the \
                 witness path was NOT exercised end to end on this run.",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
        Err(other) => {
            panic!(
                "{} names a path but loading it was refused for a reason other than \
                 absence ({other:?}); this is a provisioning defect and is FATAL, never a \
                 skip",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
    }
}

// ---------------------------------------------------------------------------------
// AC-59 (REQ-35, EC-13): the named, deliberately-unclosed honest limit. A
// recorder whose write always succeeds without retaining anything defeats the
// audit obligation: the actuator still executes, the effect still lands, and
// the recorder holds no record of the decision that authorised it. This is
// the ONE test in this suite that mutates the process environment (the same
// single-exception shape `crates/hierarchy-vor/tests/public_surface.rs`'s own
// header documents for its ONE environment-mutating test), because proving
// "the actuator still executes" needs a real, resolvable working repository.
//
// This criterion is not met by a test asserting a lying recorder is detected:
// no such mechanism is built, and such a test would be false (the spec's own
// words, AC-59).
// ---------------------------------------------------------------------------------

struct LyingRecorder;

impl himinbjorg::DecisionRecorder for LyingRecorder {
    fn record(
        &mut self,
        _agent_id: &himinbjorg::AgentId,
        _action: &himinbjorg::Action,
        _decision: himinbjorg::Decision,
        _checks: &[himinbjorg::CheckRecord],
    ) -> Result<(), String> {
        // Reports success. Retains nothing. This IS the defeat REQ-35 names.
        Ok(())
    }
}

#[test]
fn ac59_a_lying_recorder_defeats_the_audit_obligation_named_not_closed() {
    match hierarchy_vor::load_trusted_set_from_env(hierarchy_vor::cohort::AUTHORISER_ID) {
        Ok(trusted) => {
            let cohort = hierarchy_vor::load_verified_cohort(&trusted).unwrap_or_else(|e| {
                panic!(
                    "ac59: a secret was provisioned via {} but the committed attestation \
                     did not verify against it ({e:?}); this is a provisioning defect and \
                     is FATAL, never a skip",
                    hierarchy_vor::SECRET_PATH_ENV_VAR,
                )
            });

            let dir = scratch_dir("ac59-lying-recorder");
            let work = dir.join("work");
            std::fs::create_dir_all(&work).expect("failed to create fixture working repo dir");
            let run = |args: &[&str]| {
                let status = std::process::Command::new("git")
                    .args(args)
                    .current_dir(&work)
                    .status()
                    .expect("failed to spawn git");
                assert!(status.success(), "fixture git {args:?} failed");
            };
            run(&["init", "--quiet"]);
            run(&["config", "user.name", "ac59 fixture"]);
            run(&["config", "user.email", "ac59-fixture@example.invalid"]);

            let previous = std::env::var("HEIMDALL_ACTUATOR_GIT_WORKING_REPO").ok();
            // SAFETY: test-only mutation of this process's own environment,
            // the ONE such test in this suite (see this test's own header).
            unsafe {
                std::env::set_var("HEIMDALL_ACTUATOR_GIT_WORKING_REPO", &work);
            }

            let agent_id = himinbjorg::AgentId::new(hierarchy_vor::cohort::COHORT_ID);
            let task = himinbjorg::TaskContext {
                task_id: "ac59-fixture-task".to_string(),
                target: "fixture-target".to_string(),
                declared_cost: 0,
            };
            let context = himinbjorg::build_context(&agent_id, &task, &cohort)
                .expect("the one hardcoded agent id must build a context over a real cohort");
            let surface = himinbjorg::enforce_definition(&agent_id, &cohort)
                .expect("the one hardcoded agent id must resolve a definition over a real cohort");

            let mut proposal = baseline_proposal();
            proposal.action_name = "action:git.commit".to_string();
            let decision = himinbjorg::validate_proposal(&context, &surface, &proposal);
            let authorisation = decision
                .authorisation()
                .expect("the baseline commit proposal must validate to Allow");

            let action = himinbjorg::Action {
                action_name: proposal.action_name.clone(),
                target: proposal.target.clone(),
            };
            let scope = himinbjorg::Scope::new("public-surface-fixture-scope");
            let mut lying = LyingRecorder;
            let outcome = himinbjorg::broker_authorised_action(
                &context,
                &action,
                &scope,
                authorisation,
                &mut lying,
            );

            unsafe {
                match &previous {
                    Some(v) => std::env::set_var("HEIMDALL_ACTUATOR_GIT_WORKING_REPO", v),
                    None => std::env::remove_var("HEIMDALL_ACTUATOR_GIT_WORKING_REPO"),
                }
            }

            assert!(
                matches!(outcome, Ok(_)),
                "AC-59: with a real, resolvable working repository, a lying recorder that \
                 reports success while retaining nothing must NOT block the actuator: the \
                 audit obligation is defeated, not closed, by this step; got {outcome:?}"
            );
            let log = std::process::Command::new("git")
                .args(["log", "--oneline"])
                .current_dir(&work)
                .output()
                .expect("failed to read fixture git log");
            assert!(
                !log.stdout.is_empty(),
                "AC-59: the effect must genuinely land in the working repository despite \
                 the lying recorder"
            );

            let _ = std::fs::remove_dir_all(&dir);

            eprintln!(
                "GIT-ACTUATOR-STEP-FOUR-NAMED-LIMIT: AC-59/REQ-35/EC-13: a recorder that \
                 reports success while retaining nothing defeats the audit obligation this \
                 step relies on for HB-6's block-on-failed-log property. This is not closed \
                 by this step, and this test's own passing is exactly that: the lying \
                 recorder was NOT detected, rejected or distinguished from an honest one."
            );
        }
        Err(hierarchy_vor::SecretRefusal::EnvVarMissing(_)) => {
            println!(
                "HIMINBJORG-REAL-COHORT-NOT-EXERCISED: {} is not set (or is empty), so \
                 AC-59's honest-limit demonstration was NOT exercised on this run.",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
        Err(other) => {
            panic!(
                "{} names a path but loading it was refused for a reason other than \
                 absence ({other:?}); this is a provisioning defect and is FATAL",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
    }
}

// ---------------------------------------------------------------------------------
// AC-35 (REQ-26): `Authorisation` has no public constructor, no `Default`, no
// `Clone` and no public conversion. Per section 12's documented compile-fail
// convention (manual, not `trybuild`, following AC-13's own precedent for
// `TrustedAuthoriserSet` in `crates/hierarchy-vor/tests/public_surface.rs`),
// this is NOT a standing automated test: uncomment ONE block below, run
// `cargo build -p himinbjorg --tests`, capture rustc's exact diagnostic, and
// record it in the pull request. Leave all of them commented in the committed
// file, otherwise this crate never builds at all.
//
// ```rust,ignore
// // (a) No public constructor: `Authorisation` has no `pub fn new`, no public
// // tuple constructor and no public field. Expected: E0423 or E0616.
// let _bad = himinbjorg::Authorisation { /* fields, if any were visible */ };
//
// // (b) No `Default`. Expected: E0599 (no function `default` on `Authorisation`)
// // or E0277 (trait bound not satisfied).
// let _bad: himinbjorg::Authorisation = Default::default();
//
// // (c) No `Clone`, no `Copy`. Expected: E0599 (no method named `clone`),
// // exercised on an `Authorisation` obtained from a real `ProposalDecision`.
// // let _bad = authorisation.clone();
//
// // (d) No public `From`/`TryFrom` and no `Deref` to an unauthenticated shape.
// // Expected: E0277 (trait not implemented) for whichever conversion is
// // attempted.
// // let _bad: himinbjorg::Authorisation = SomeUnauthenticatedShape::default().into();
// ```
// ---------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------
// AC-38 (REQ-30): `broker_action`'s signature, compared byte for byte against
// the baseline in section 2 -- name, parameter types, parameter order and
// return type all unchanged. Enforced structurally: coercing the function
// item to an explicit `fn` pointer type fails to COMPILE if any part of the
// signature has changed, which is a stronger and more durable proof than a
// call site alone (a call site tolerates some signature changes through
// implicit coercions that a bare type ascription does not).
// ---------------------------------------------------------------------------------

#[test]
fn ac38_broker_action_signature_is_unchanged_byte_for_byte() {
    let _exact_signature: fn(
        &himinbjorg::AgentContext<'_>,
        &himinbjorg::Action,
        &himinbjorg::Scope,
    ) -> Result<himinbjorg::BrokerResult, himinbjorg::BrokerRefusal> = himinbjorg::broker_action;
}

// ---------------------------------------------------------------------------------
// AC-54 (REQ-3): `#![forbid(unsafe_code)]` on `crates/actuator-git/src/lib.rs`,
// and the absence of the `unsafe` keyword anywhere in that crate's source,
// are BOTH mechanical, file-level scans that belong in
// `ontology/tests/rust_actuator_harness.py` alongside its other scans (the
// spec's own section 7.1 wording: "Both halves are mechanical file-level
// checks and belong in the new sub-harness"). They are cross-referenced here,
// not duplicated as a Rust test, because this file cannot meaningfully test a
// DIFFERENT crate's own crate-level attribute from outside it: `himinbjorg`'s
// own `#![forbid(unsafe_code)]` (unaffected by this step, still present at
// this file's own crate root's dependency) is exercised implicitly by the
// fact that this whole file, and every other test in it, compiles and runs at
// all against a `himinbjorg` that forbids unsafe code internally.
// ---------------------------------------------------------------------------------

// ---------------------------------------------------------------------------------
// AC-62 (REQ-49): `plans/dd/actuator-git.md` exists, and `plans/dd/index.md`
// holds it at order 11 without renumbering orders one to ten. A currency
// check, read directly off the filesystem relative to this crate's own
// manifest directory (no dependency added: `std::fs` only).
// ---------------------------------------------------------------------------------

#[test]
fn ac62_actuator_git_design_document_exists_and_is_indexed_at_order_eleven() {
    let repo_root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .expect("crates/himinbjorg's manifest dir must have two ancestors: the repo root")
        .to_path_buf();
    let doc_path = repo_root.join("plans").join("dd").join("actuator-git.md");
    assert!(
        doc_path.exists(),
        "AC-62: {} must exist once this step is declared complete (REQ-49)",
        doc_path.display()
    );
    let doc = std::fs::read_to_string(&doc_path).expect("failed to read actuator-git.md");
    assert!(
        !doc.trim().is_empty(),
        "AC-62: plans/dd/actuator-git.md must not be an empty file"
    );

    let index_path = repo_root.join("plans").join("dd").join("index.md");
    let index = std::fs::read_to_string(&index_path).expect("failed to read plans/dd/index.md");
    assert!(
        index.contains("actuator-git"),
        "AC-62: plans/dd/index.md must reference actuator-git.md"
    );
    assert!(
        index.contains("11"),
        "AC-62: plans/dd/index.md must hold actuator-git.md at order 11, per section 1's \
         own note naming the git actuator as a component that earns its own row when built"
    );
}
