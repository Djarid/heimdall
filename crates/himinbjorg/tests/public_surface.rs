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
