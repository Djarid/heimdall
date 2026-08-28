//! The cognition seam and the propose-action step (REQ-13 to REQ-19, PE-2,
//! PE-3, PE-4, PE-10): AC-15 to AC-19, AC-21, and the substitution case of
//! AC-17 and EC-19 of `.opencode/plans/process-engine-step-five-spec.md`.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/process-engine/src/cognition.rs`
//! and `src/proposal.rs` exist at real fidelity, on `sequence_shape.rs`'s own
//! header note for the same expected RED state.
//!
//! **Compiled as an IN-CRATE unit test module** (REQ-7), wired into
//! `crates/process-engine/src/lib.rs` via
//! `#[cfg(test)] #[path = "../unit_tests/cognition_and_proposal.rs"] mod
//! cognition_and_proposal;`.
//!
//! **Signatures assumed here** (in addition to `sequence_shape.rs`'s own
//! header, which this file inherits without repeating):
//!
//!   - `crate::CognitionStep`: a trait with exactly one method,
//!     `fn propose(&self, task: &crate::EngineTask) -> crate::CognitionOutput`
//!     (REQ-13, the spec's own indicative shape, section 4.3).
//!   - `crate::CognitionOutput { parameters: Vec<himinbjorg::ProposalParameter> }`:
//!     the advisory content cognition contributes. As of build-order step six
//!     (ST6-1, REQ-2, REQ-54, `.opencode/plans/build-order-step-six-spec.md`),
//!     `sink` no longer lives here: it lives on `EngineTask` instead (see the
//!     next bullet), because a push task must be able to declare
//!     `sink:git.push` and a commit task `sink:git.commit`, while the
//!     cognition stub's own output stays fixed and hardcoded. Deliberately
//!     excludes `action_name` and `target` too (both live on `EngineTask`,
//!     per `sequence_shape.rs`'s header) and `declared_cost` (assumed to come
//!     from the task too, mirroring `himinbjorg::TaskContext`'s own
//!     `declared_cost` field).
//!   - `crate::EngineTask` gains a fifth public field, `sink: String`
//!     (REQ-1, REQ-54), alongside `task_id`, `action_name`, `target` and
//!     `declared_cost`. `fixture_task` below sets it on every task this file
//!     constructs.
//!   - `crate::build_proposal(task: &crate::EngineTask, cognition_output:
//!     &crate::CognitionOutput) -> himinbjorg::Proposal` reads `sink` from
//!     `task.sink` now, never from `cognition_output` (REQ-3, REQ-54): this
//!     is the load-bearing change AC-19's own assertions below are updated
//!     for.
//!   - `crate::DefaultCognitionStep`: the one stub implementation of
//!     `CognitionStep` this step provides (REQ-14), assumed to have a public
//!     unit constructor reachable as `crate::DefaultCognitionStep` (a bare
//!     unit struct, following `himinbjorg::MinimalDecisionRecorder`'s
//!     precedent for a single, named, concrete implementation).
//!   - `crate::build_proposal(task: &crate::EngineTask, cognition_output:
//!     &crate::CognitionOutput) -> himinbjorg::Proposal`: the one function
//!     REQ-16 names, assumed `pub(crate)` (reachable from this in-crate
//!     module, never from an external caller, following REQ-11's
//!     mandatory-shell pattern for every individual step).
//!
//! **Why AC-17's substitution case needs a real cohort, and how this file
//! states that rather than silently gating it away.** Running the sequence
//! with a substitute cognition implementation to observe a genuine gate
//! block requires calling `validate_proposal` for real, which requires a
//! real `hierarchy_vor::VerifiedCohort` (see `sequence_shape.rs`'s header for
//! why no fixture, mock or double exists for one anywhere in this
//! design). This file therefore gates that ONE test behind
//! `HEIMDALL_COHORT_SECRET_FILE`, printing its OWN distinct, non-reserved
//! gap message on skip -- following `crates/himinbjorg/unit_tests/six_checks.rs`'s
//! own precedent of reserving `PROCESS-ENGINE-REAL-COHORT-VERIFIED` /
//! `PROCESS-ENGINE-REAL-COHORT-NOT-EXERCISED` for `tests/public_surface.rs`
//! alone (REQ-53). Every other test in this file executes its assertions
//! unconditionally.
//!
//! **Assumed internal seam for the substitution test.** Since
//! `crate::run_sequence`'s own public signature is assumed fixed at
//! `(cohort, task) -> EngineOutcome` (no cognition parameter, per
//! `sequence_shape.rs`'s header), this file assumes a second,
//! `pub(crate)`-only entry point exists for exactly this purpose:
//! `crate::run_sequence_with_cognition(cohort: &hierarchy_vor::VerifiedCohort,
//! task: &EngineTask, cognition: &impl CognitionStep) -> EngineOutcome`,
//! used internally by `run_sequence` (which supplies `DefaultCognitionStep`)
//! and reachable from this in-crate test module for substitution testing.
//! This split is this file's own necessary choice, flagged explicitly: it is
//! the only way AC-17's own wording ("when the sequence runs with it")
//! is satisfiable without widening the crate's ONE PUBLIC entry point's
//! signature, which REQ-11 fixes at "exactly one" without fixing its exact
//! parameter list.

fn crate_src_dir() -> std::path::PathBuf {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src")
}

fn cleaned_whole_crate_src() -> String {
    let mut all = String::new();
    let src_dir = crate_src_dir();
    let entries = std::fs::read_dir(&src_dir).unwrap_or_else(|e| {
        panic!("expected crates/process-engine/src/ to exist once this step lands: {e}")
    });
    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) == Some("rs") {
            if let Ok(src) = std::fs::read_to_string(&path) {
                let cleaned: String = src
                    .lines()
                    .map(|line| match line.find("//") {
                        Some(idx) => format!("{}{}", &line[..idx], " ".repeat(line.len() - idx)),
                        None => line.to_string(),
                    })
                    .collect::<Vec<_>>()
                    .join("\n");
                all.push_str(&cleaned);
                all.push('\n');
            }
        }
    }
    all
}

fn fixture_task(action_name: &str) -> crate::EngineTask {
    crate::EngineTask {
        task_id: "fixture-task".to_string(),
        action_name: action_name.to_string(),
        target: "fixture-target".to_string(),
        // REQ-1/REQ-54 (build-order step six): EngineTask's fifth field.
        // This file's own probes never inspect this value; it is set here
        // only so the struct literal compiles once the field lands.
        sink: "sink:git.commit".to_string(),
        declared_cost: 0,
    }
}

// ---------------------------------------------------------------------------------
// AC-15 (REQ-13): the cognition trait has exactly one method, and nothing
// about verification, retry, streaming, cancellation, token accounting or
// model identity is declared on it.
// ---------------------------------------------------------------------------------

struct _AC15ProbeCognition;

impl crate::CognitionStep for _AC15ProbeCognition {
    fn propose(&self, task: &crate::EngineTask) -> crate::CognitionOutput {
        // REQ-2/REQ-54 (build-order step six): CognitionOutput no longer
        // carries a `sink` field; the sink now lives on the task alone.
        crate::CognitionOutput {
            parameters: vec![himinbjorg::ProposalParameter {
                id: "v".to_string(),
                consume_mode: boundary_gjoll::types::ConsumeMode::Inert,
                trust_level: boundary_gjoll::types::TrustLevel::Canonical,
                type_name: "comms:informational".to_string(),
            }],
        }
        // Deliberately ignores `task` in this probe: implementing the
        // trait's ONE method is possible without consulting the task at
        // all, which is itself weak evidence the trait asks for nothing
        // else. The real assertion is structural, below.
    }
}

#[test]
fn ac15_cognition_trait_declares_no_verification_retry_streaming_cancellation_token_or_model_surface(
) {
    let cleaned = cleaned_whole_crate_src();
    let cognition_rs = std::fs::read_to_string(crate_src_dir().join("cognition.rs"))
        .expect("expected crates/process-engine/src/cognition.rs to exist");
    let _ = cleaned; // whole-crate scan retained for parity with sibling tests
    for forbidden in [
        "fn verify",
        "fn retry",
        "fn stream",
        "fn cancel",
        "token_budget",
        "model_id",
        "model_identity",
    ] {
        assert!(
            !cognition_rs.contains(forbidden),
            "AC-15/REQ-13: cognition.rs must declare no {forbidden:?} on the CognitionStep \
             trait: nothing about verification, retry, streaming, cancellation, token \
             accounting or model identity belongs on this narrow, one-method seam"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-16 (REQ-14): exactly one implementation of the trait exists in this
// step, built from hardcoded named constants, each carrying a compile-time
// non-emptiness assertion; the stub reads no file, no environment variable,
// opens no socket and consults no configuration surface.
// ---------------------------------------------------------------------------------

#[test]
fn ac16_default_cognition_step_output_is_built_from_hardcoded_constants_with_no_side_effects() {
    let cognition_rs = std::fs::read_to_string(crate_src_dir().join("cognition.rs"))
        .expect("expected crates/process-engine/src/cognition.rs to exist");
    for forbidden in [
        "std::env",
        "env::var",
        "std::fs",
        "fs::read",
        "TcpStream",
        "UdpSocket",
    ] {
        assert!(
            !cognition_rs.contains(forbidden),
            "AC-16/REQ-14: cognition.rs must contain no {forbidden:?}: the stub's output \
             is built from hardcoded constants only, with no file read, no environment \
             read and no socket opened on the process path"
        );
    }
    assert!(
        cognition_rs.contains("const _: () = assert!"),
        "AC-16/REQ-14: cognition.rs must carry at least one compile-time non-emptiness \
         assertion over its own hardcoded constants, following \
         context::TARGET_SCOPE's, broker::PERMITTED_CREDENTIAL_SCOPES's and \
         targets::PERMITTED_TARGETS's own precedent"
    );

    let stub = crate::DefaultCognitionStep;
    let task = fixture_task("action:git.commit");
    let first = stub.propose(&task);
    let second = stub.propose(&task);
    // REQ-2/REQ-54 (build-order step six): CognitionOutput carries
    // `parameters` only now; the sink lives on the task instead (asserted
    // separately by AC-19 below). The same-hardcoded-content-across-calls
    // property is checked on `parameters`, the one field left to check it
    // on.
    assert_eq!(
        first.parameters, second.parameters,
        "AC-16: the stub's output must be the same hardcoded content across repeated \
         calls with the same task -- there is no configuration surface through which it \
         could vary"
    );
    assert!(
        !first.parameters.is_empty(),
        "AC-16: the stub's own parameter set must be non-empty"
    );
    assert!(
        !cognition_rs.contains("DEFAULT_PROPOSED_SINK"),
        "AC-4/REQ-2: cognition.rs must no longer carry DEFAULT_PROPOSED_SINK; the sink \
         moved to EngineTask (REQ-1)"
    );
}

#[test]
fn ac16_exactly_one_cognitionstep_implementation_exists_in_the_crate() {
    let cognition_rs = std::fs::read_to_string(crate_src_dir().join("cognition.rs"))
        .expect("expected crates/process-engine/src/cognition.rs to exist");
    let occurrences = cognition_rs.matches("impl CognitionStep for").count()
        + cognition_rs.matches("impl crate::CognitionStep for").count();
    assert_eq!(
        occurrences, 1,
        "AC-16/REQ-14: exactly one non-test implementation of CognitionStep must exist in \
         cognition.rs; found {occurrences}"
    );
}

// ---------------------------------------------------------------------------------
// AC-17 (REQ-15), the non-substitution half: nothing in the crate derives a
// permission, a credential scope, a target-scope membership or a check
// outcome from cognition's own output (AC-18's structural half, tested
// here alongside AC-17 since both are established the same way).
// ---------------------------------------------------------------------------------

#[test]
fn ac17_ac18_no_branch_derives_authorisation_from_cognitions_output() {
    let cleaned = cleaned_whole_crate_src();
    // A branch that read `cognition_output.sink` or `.parameters` to decide
    // whether to proceed, rather than merely to copy the value into a
    // Proposal field, would be exactly the defect these criteria forbid.
    // The strongest thing checkable by source scan alone is that no
    // conditional keyword appears anywhere near a field read on the
    // cognition output type in the same module that also names a
    // permission-shaped identifier; this is necessarily approximate, and
    // the stronger structural claim (AC-14's gating-constant absence,
    // AC-23's no-local-check absence) already covers the load-bearing
    // half of "no branch decides authorisation" for this crate as a whole.
    for forbidden in ["if cognition", "match cognition"] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-17/AC-18/REQ-15: no branch anywhere in crates/process-engine/src/ may be \
             keyed on cognition's own output to decide whether to proceed; found a \
             pattern matching {forbidden:?}"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-17's substitution case, EC-19: a substitute cognition implementation
// that proposes a deliberately disallowed action still blocks at the gate,
// attributable to a named CheckRecord, with no action executed. Gated
// behind a real cohort (see this file's header); prints its own distinct
// gap message on skip, never silently.
// ---------------------------------------------------------------------------------

struct DisallowedActionCognition;

impl crate::CognitionStep for DisallowedActionCognition {
    fn propose(&self, _task: &crate::EngineTask) -> crate::CognitionOutput {
        // REQ-2/REQ-54: no `sink` field here any more; the task this
        // cognition is proposed against carries its own sink instead.
        crate::CognitionOutput {
            parameters: vec![himinbjorg::ProposalParameter {
                id: "v".to_string(),
                consume_mode: boundary_gjoll::types::ConsumeMode::Inert,
                trust_level: boundary_gjoll::types::TrustLevel::Canonical,
                type_name: "comms:informational".to_string(),
            }],
        }
    }
}

fn real_verified_cohort_or_skip(test_name: &str) -> Option<hierarchy_vor::VerifiedCohort> {
    match hierarchy_vor::load_trusted_set_from_env(hierarchy_vor::cohort::AUTHORISER_ID) {
        Ok(trusted) => Some(hierarchy_vor::load_verified_cohort(&trusted).unwrap_or_else(|e| {
            panic!(
                "{test_name}: a secret was provisioned via {} but the committed \
                 attestation did not verify against it ({e:?}); this is a provisioning \
                 defect and is FATAL, never a skip",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            )
        })),
        Err(hierarchy_vor::SecretRefusal::EnvVarMissing(_)) => {
            eprintln!(
                "PROCESS-ENGINE-STEP-FIVE-GAP: {test_name}: SKIPPED -- {} is not set (or \
                 is empty), so this test cannot obtain a real VerifiedCohort at all (no \
                 fixture, mock or double exists for one by design, REQ-20). This is a \
                 named gap, not a silent one; the reserved PROCESS-ENGINE-REAL-COHORT-* \
                 markers are tests/public_surface.rs's own, not this file's (REQ-53).",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
            None
        }
        Err(other) => panic!(
            "{test_name}: {} names a path but loading it was refused for a reason other \
             than absence ({other:?}); this is a provisioning defect and is FATAL",
            hierarchy_vor::SECRET_PATH_ENV_VAR,
        ),
    }
}

#[test]
fn ac17_substitution_ec19_a_disallowed_action_proposal_still_blocks_at_the_gate() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac17_substitution_ec19_a_disallowed_action_proposal_still_blocks_at_the_gate",
    ) else {
        return;
    };

    let task = fixture_task("action:totally-unknown-and-never-permitted");
    let cognition = DisallowedActionCognition;
    let outcome = crate::run_sequence_with_cognition(&cohort, &task, &cognition);

    match outcome {
        crate::EngineOutcome::GateBlocked { checks } => {
            assert_eq!(
                checks.len(),
                6,
                "AC-17/EC-19: a gate-blocked outcome must still carry all six CheckRecords"
            );
            let (first_id, first_outcome) = &checks[0];
            assert_eq!(
                *first_id,
                himinbjorg::CheckId::ActionPermitted,
                "AC-17/EC-19: the first check record must be ActionPermitted"
            );
            assert!(
                !matches!(first_outcome, himinbjorg::CheckOutcome::Pass),
                "AC-17/EC-19: an unpermitted action proposed by a substitute cognition \
                 implementation must fail check one, attributable to a named check -- \
                 substituting cognition cannot widen what is authorised"
            );
        }
        other => panic!(
            "AC-17/EC-19: expected GateBlocked for a deliberately disallowed action; got \
             {other:?}"
        ),
    }
}

// ---------------------------------------------------------------------------------
// AC-18 (REQ-15): the crate's own documentation states why a substitutable
// cognition step does not repeat D112's rejection of a trait at the
// actuator invocation.
// ---------------------------------------------------------------------------------

#[test]
fn ac18_documentation_states_why_cognition_trait_does_not_repeat_d112s_rejection() {
    let cognition_rs = std::fs::read_to_string(crate_src_dir().join("cognition.rs"))
        .expect("expected crates/process-engine/src/cognition.rs to exist");
    let lower = cognition_rs.to_lowercase();
    assert!(
        lower.contains("d112"),
        "AC-18/REQ-15: cognition.rs must name D112 in its own doc comment when explaining \
         why a substitutable cognition step does not repeat that decision's rejection of \
         a trait at the actuator invocation"
    );
    assert!(
        lower.contains("advisory") || lower.contains("never adjudicative"),
        "AC-18/REQ-15: cognition.rs must state, in its own words, that cognition is \
         advisory and never adjudicative"
    );
}

// ---------------------------------------------------------------------------------
// AC-19 (REQ-16): the proposal-shaping function's own field provenance --
// every field it sets comes from the task, from the cognition stub's
// constants, or from a named engine constant, never from Himinbjörg's own
// gating constants.
// ---------------------------------------------------------------------------------

#[test]
fn ac19_build_proposal_uses_task_and_cognition_fields_only_never_himinbjorgs_gating_constants() {
    let task = fixture_task("action:git.commit");
    // REQ-2/REQ-54 (build-order step six): CognitionOutput carries no
    // `sink` field any more.
    let cognition_output = crate::CognitionOutput {
        parameters: vec![himinbjorg::ProposalParameter {
            id: "v".to_string(),
            consume_mode: boundary_gjoll::types::ConsumeMode::Inert,
            trust_level: boundary_gjoll::types::TrustLevel::Canonical,
            type_name: "comms:informational".to_string(),
        }],
    };

    let proposal = crate::build_proposal(&task, &cognition_output);

    assert_eq!(
        proposal.action_name, task.action_name,
        "AC-19: the proposal's action_name must come from the task"
    );
    assert_eq!(
        proposal.target, task.target,
        "AC-19: the proposal's target must come from the task"
    );
    assert_eq!(
        proposal.declared_cost, task.declared_cost,
        "AC-19: the proposal's declared_cost must come from the task"
    );
    assert_eq!(
        proposal.sink, task.sink,
        "AC-5/REQ-3/REQ-54: the proposal's sink must come from the TASK now, not from the \
         cognition output (ST6-1's own relocation)"
    );
    assert_eq!(
        proposal.parameters, cognition_output.parameters,
        "AC-19: the proposal's parameters must come from the cognition output"
    );

    let proposal_rs = std::fs::read_to_string(crate_src_dir().join("proposal.rs"))
        .expect("expected crates/process-engine/src/proposal.rs to exist");
    let occurrences = proposal_rs.matches("Proposal {").count();
    assert_eq!(
        occurrences, 1,
        "AC-19/REQ-16: proposal.rs must be the ONE site constructing a himinbjorg::Proposal"
    );
}

// ---------------------------------------------------------------------------------
// AC-5 (REQ-1, REQ-3, ST6-1, REQ-54, build-order step six): a task
// declaring `sink:git.push` and a task declaring `sink:git.commit`, run
// through the SAME cognition output, produce proposals whose sink
// byte-equals the TASK's own, never the cognition output's (which no
// longer even has one) -- proving no code path can produce a proposal
// whose sink differs from its task's.
// ---------------------------------------------------------------------------------

#[test]
fn ac5_proposal_sink_byte_equals_the_tasks_own_sink_for_both_commit_and_push() {
    let cognition_output = crate::CognitionOutput {
        parameters: vec![himinbjorg::ProposalParameter {
            id: "v".to_string(),
            consume_mode: boundary_gjoll::types::ConsumeMode::Inert,
            trust_level: boundary_gjoll::types::TrustLevel::Canonical,
            type_name: "comms:informational".to_string(),
        }],
    };

    let mut commit_task = fixture_task("action:git.commit");
    commit_task.sink = "sink:git.commit".to_string();
    let commit_proposal = crate::build_proposal(&commit_task, &cognition_output);
    assert_eq!(
        commit_proposal.sink, "sink:git.commit",
        "AC-5: a task declaring sink:git.commit must produce a proposal declaring \
         sink:git.commit"
    );

    let mut push_task = fixture_task("action:git.push");
    push_task.sink = "sink:git.push".to_string();
    let push_proposal = crate::build_proposal(&push_task, &cognition_output);
    assert_eq!(
        push_proposal.sink, "sink:git.push",
        "AC-5/REQ-5: a task declaring sink:git.push must produce a proposal declaring \
         sink:git.push -- before this step's own relocation, every proposal declared \
         sink:git.commit regardless of the task, which is exactly the evidence-fidelity \
         gap EC-24 names"
    );

    assert_ne!(
        commit_proposal.sink, push_proposal.sink,
        "AC-5: the two directions must differ by task alone, since the SAME cognition \
         output was used for both"
    );
}

// ---------------------------------------------------------------------------------
// AC-21 (REQ-18): the target-scope addition is recorded as an agreement
// between two independently owned lists, never a derivation, and no code
// anywhere reads targets::PERMITTED_TARGETS to build or validate
// TARGET_SCOPE, or the reverse.
// ---------------------------------------------------------------------------------

#[test]
fn ac21_target_scope_doc_comment_records_the_addition_as_an_agreement_not_a_derivation() {
    let context_rs =
        std::fs::read_to_string(
            std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .expect("crates/process-engine has a parent (crates/)")
                .join("himinbjorg")
                .join("src")
                .join("context.rs"),
        )
        .expect(
            "expected crates/himinbjorg/src/context.rs to exist and to carry \
             TARGET_SCOPE's own doc comment",
        );
    let lower = context_rs.to_lowercase();
    assert!(
        lower.contains("fixture-integration-branch"),
        "AC-20/AC-21/REQ-17: TARGET_SCOPE must additively gain \
         \"fixture-integration-branch\", keeping \"fixture-target\""
    );
    assert!(
        lower.contains("fixture-target"),
        "AC-20/REQ-17: TARGET_SCOPE must retain \"fixture-target\" (the ac57 regression \
         pin in witness_and_audit.rs depends on it staying in scope)"
    );
    assert!(
        lower.contains("agreement") && !lower.contains("derived from targets::permitted_targets"),
        "AC-21/REQ-18: TARGET_SCOPE's own doc comment must record the addition as an \
         agreement between two independently owned lists, never a derivation"
    );
}

#[test]
fn ac21_no_code_anywhere_reconciles_target_scope_against_permitted_targets() {
    // Scanned across process-engine's own source only: this crate cannot
    // even name actuator_git::targets (REQ-4), so the strongest check this
    // file can make is that process-engine's own source never attempts to
    // read, import or reference `PERMITTED_TARGETS` at all.
    let mut all = String::new();
    let src_dir = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src");
    if let Ok(entries) = std::fs::read_dir(&src_dir) {
        for entry in entries.flatten() {
            if let Ok(src) = std::fs::read_to_string(entry.path()) {
                all.push_str(&src);
            }
        }
    }
    assert!(
        !all.contains("PERMITTED_TARGETS"),
        "AC-21/REQ-18/EC-20: process-engine must never read, check, generate or validate \
         against targets::PERMITTED_TARGETS; the two lists answer different questions and \
         are never reconciled (step four's EC-17 never-reconcile rule)"
    );
}
