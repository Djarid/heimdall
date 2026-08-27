//! The authorisation witness (GA-1) and HB-6's audit seam (GA-2): witness
//! minting, the witness-carrying entry point's mismatch/scope/audit-write
//! gates, the minimal recorder, and the honest-limit demonstration (REQ-26 to
//! REQ-39). Covers AC-32 to AC-34, AC-36, AC-37, AC-39 to AC-45, AC-56 to
//! AC-59 (partially; see below), AC-60 of
//! `.opencode/plans/git-actuator-step-four.md`.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/actuator-git` exists (a new
//! in-workspace path dependency of `himinbjorg`, REQ-6) AND `crates/himinbjorg/
//! src/types.rs`, `broker.rs`, `validation.rs`, `audit.rs` and `lib.rs` all
//! carry this step's additions. That is expected and correct at this stage.
//!
//! **Compiled as an IN-CRATE unit test module**, once wired via
//! `#[cfg(test)] #[path = "../unit_tests/witness_and_audit.rs"] mod
//! witness_and_audit;` in `crates/himinbjorg/src/lib.rs` (a later,
//! implementation-side change), following `six_checks.rs`'s own precedent.
//!
//! **Assumed additions to the public/`pub(crate)` surface** (this file's own
//! necessary choices where the spec's section 5.2 leaves the shape indicative;
//! flagged explicitly, not hidden, following `six_checks.rs`'s and
//! `gate_bridge_failclosed.rs`'s own precedent for their own assumptions):
//!
//!   - `crate::Authorisation`: opaque, no public constructor. Read via four
//!     accessors this file assumes: `action_name(&self) -> &str`,
//!     `target(&self) -> &str`, `sink(&self) -> &str`,
//!     `checks(&self) -> &[crate::CheckRecord]` (six entries, REQ-28).
//!   - `crate::ProposalDecision::authorisation(&self) -> Option<&crate::Authorisation>`
//!     (REQ-27).
//!   - `crate::DecisionRecorder`, a trait with one fallible write method,
//!     assumed here as
//!     `fn record(&mut self, agent_id: &crate::AgentId, action: &crate::Action,
//!     decision: crate::Decision, checks: &[crate::CheckRecord]) -> Result<(), String>`
//!     (REQ-31; the error type is assumed `String` -- a diagnostic -- since
//!     the spec leaves it indicative).
//!   - `crate::MinimalDecisionRecorder` (assumed name), the one
//!     concrete append-only `DecisionRecorder` implementation (REQ-34), with
//!     `MinimalDecisionRecorder::new() -> Self` and
//!     `records(&self) -> &[RecordedDecision]` (an assumed read-back
//!     accessor; without one, AC-43's "the recorder's contents are read"
//!     could not be exercised at all).
//!   - `crate::broker_authorised_action` (assumed to live in, and be
//!     re-exported from, the `broker` module like `broker_action`):
//!     `fn broker_authorised_action(context: &crate::AgentContext<'_>, action:
//!     &crate::Action, credential_scope: &crate::Scope, authorisation:
//!     &crate::Authorisation, recorder: &mut impl crate::DecisionRecorder) ->
//!     Result<crate::ActuationReceipt, crate::BrokerRefusal>` (REQ-29, REQ-31
//!     to REQ-33, REQ-37 to REQ-39).
//!   - `crate::BrokerRefusal` gains, additively: `NoAuthorisationEvidence`
//!     (REQ-30's corrected reason, replacing `NoActuatorAvailable` for
//!     `broker_action`'s own case), `WitnessMismatch` (REQ-29),
//!     `AuditWriteFailed { diagnostic: String }` (REQ-32), and
//!     `ActuatorRefused(actuator_git::ActuationRefusal)` (REQ-38, carrying
//!     `actuator-git`'s own reason verbatim). `ScopeNotPermitted` and
//!     `NoActuatorAvailable` are retained (REQ-30).
//!   - **The message/target-to-`GitOperation` mapping.** Neither `Action` nor
//!     `Authorisation` carries a commit message or a push ref/remote pair
//!     distinct from `target`/`sink`, so this file assumes
//!     `broker_authorised_action` maps `action_name == "action:git.commit"`
//!     to `actuator_git::GitOperation::Commit` with a fixed, hardcoded
//!     message, and `action_name == "action:git.push"` to
//!     `actuator_git::GitOperation::Push` using `authorisation.target()` as
//!     the ref against a hardcoded remote. This is flagged as an assumption
//!     because the spec leaves the exact mapping unspecified; the tests below
//!     that depend on it (AC-57, AC-58) are written so their CONTRACT (two
//!     distinct `ActuationRefusal` variants map to two distinguishable
//!     `BrokerRefusal` outcomes; the actuator is reached once, with no
//!     further authorisation query) survives even if the concrete mapping
//!     differs, provided `execute` is reached at all for a matching,
//!     fully-authorised call.
//!
//! **Why AC-59, and the runtime half of AC-41/AC-57, are NOT fully exercised
//! here.** Both need `execute` to actually SUCCEED against a real working
//! repository, which needs the working-repository environment variable set
//! -- and setting an environment variable requires `std::env::set_var`, an
//! `unsafe fn` under this workspace's pinned toolchain. Because this file is
//! compiled INTO the `#![forbid(unsafe_code)]` `himinbjorg` crate (its own
//! `lib.rs` carries the attribute) via `lib.rs`'s `#[cfg(test)] #[path]`
//! mechanism, it cannot use an `unsafe` block at all -- exactly the
//! constraint `crates/hierarchy-vor/tests/public_surface.rs`'s header names
//! for its own ONE environment-mutating test. AC-59's full behavioural
//! demonstration (the actuator executes, the effect lands, the recorder
//! holds nothing) therefore lives in
//! `crates/himinbjorg/tests/public_surface.rs` instead (an external crate,
//! free to mutate the environment). This file covers what it can WITHOUT any
//! working repository at all: every test below that reaches the actuator
//! relies on the working-repository environment variable's NATURAL ABSENCE
//! (no test here ever sets it), which deterministically yields
//! `actuator_git::ActuationRefusal::RepositoryResolution` for a commit-shaped
//! action, or (per the assumed mapping and allowlist mismatch) `TargetNotPermitted`
//! for a push-shaped action whose target is not the actuator's own permitted
//! ref -- enough to prove ORDERING (REQ-33) and REFUSAL-VERBATIM (REQ-38)
//! without ever needing the actuator to succeed.
//!
//! **REQ-47.** Every test below that needs a real `VerifiedCohort` is gated
//! behind `HEIMDALL_COHORT_SECRET_FILE`, following `six_checks.rs`'s own EC-3
//! discipline (D111's residual, closed here by printing a named marker on
//! skip rather than silently no-opping, per REQ-47's own wording).

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
                "GIT-ACTUATOR-STEP-FOUR-GAP: {test_name}: SKIPPED -- {} is not set (or is \
                 empty), so this test cannot obtain a real VerifiedCohort (no fixture, mock \
                 or double exists for one by design, REQ-20). Named gap, not a silent one \
                 (REQ-47).",
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

fn fixture_context_and_surface<'a>(
    cohort: &'a hierarchy_vor::VerifiedCohort,
) -> (crate::AgentContext<'a>, crate::EffectiveSurface<'a>) {
    let agent_id = crate::AgentId::new(hierarchy_vor::cohort::COHORT_ID);
    let task = crate::TaskContext {
        task_id: "witness-and-audit-fixture-task".to_string(),
        target: "fixture-target".to_string(),
        declared_cost: 0,
    };
    let context = crate::build_context(&agent_id, &task, cohort)
        .expect("the one hardcoded agent id must build a context over a real verified cohort");
    let surface = crate::enforce_definition(&agent_id, cohort)
        .expect("the one hardcoded agent id must resolve a definition over a real verified cohort");
    (context, surface)
}

fn passing_parameter(id: &str) -> crate::ProposalParameter {
    crate::ProposalParameter {
        id: id.to_string(),
        consume_mode: boundary_gjoll::types::ConsumeMode::Inert,
        trust_level: boundary_gjoll::types::TrustLevel::Canonical,
        type_name: "comms:informational".to_string(),
    }
}

fn baseline_passing_proposal() -> crate::Proposal {
    crate::Proposal {
        action_name: hierarchy_vor::cohort::PERMITTED_ACTIONS[0].to_string(),
        target: "fixture-target".to_string(),
        sink: hierarchy_vor::cohort::CONSEQUENTIAL_SINKS[0].to_string(),
        parameters: vec![passing_parameter("v")],
        declared_cost: 0,
    }
}

fn outcome_is_pass(outcome: &crate::CheckOutcome) -> bool {
    matches!(outcome, crate::CheckOutcome::Pass)
}

// ---------------------------------------------------------------------------------
// AC-32 (REQ-27): all six checks pass -> Allow, the authorisation accessor
// returns a witness.
// ---------------------------------------------------------------------------------

#[test]
fn ac32_all_six_pass_yields_allow_and_a_witness() {
    let Some(cohort) = real_verified_cohort_or_skip("ac32_all_six_pass_yields_allow_and_a_witness")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let proposal = baseline_passing_proposal();

    let decision = crate::validate_proposal(&context, &surface, &proposal);
    assert_eq!(decision.decision, crate::Decision::Allow);
    assert!(
        decision.authorisation().is_some(),
        "AC-32: an Allow decision must mint a witness reachable through the accessor"
    );
}

// ---------------------------------------------------------------------------------
// AC-33 (REQ-27): a proposal failing exactly one of the six checks, for each
// in turn (checks one, two, four, five, six are constructible from outside
// the crate; check three's violating fixture is a named gap identical to
// `six_checks.rs`'s own `ac21` precedent, since `context::TARGET_SCOPE` and
// the constraint's own trigger condition are module-private, not even
// `pub(crate)`).
// ---------------------------------------------------------------------------------

#[test]
fn ac33_check_one_failure_alone_blocks_and_authorisation_is_none() {
    let Some(cohort) =
        real_verified_cohort_or_skip("ac33_check_one_failure_alone_blocks_and_authorisation_is_none")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let mut proposal = baseline_passing_proposal();
    proposal.action_name = "action:totally-unknown-and-never-permitted".to_string();

    let decision = crate::validate_proposal(&context, &surface, &proposal);
    assert_eq!(decision.decision, crate::Decision::Block);
    assert!(decision.authorisation().is_none());
}

#[test]
fn ac33_check_two_failure_alone_blocks_and_authorisation_is_none() {
    let Some(cohort) =
        real_verified_cohort_or_skip("ac33_check_two_failure_alone_blocks_and_authorisation_is_none")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let mut proposal = baseline_passing_proposal();
    proposal.target = "totally-unrelated-target-outside-any-hardcoded-scope-zzz".to_string();

    let decision = crate::validate_proposal(&context, &surface, &proposal);
    assert_eq!(decision.decision, crate::Decision::Block);
    assert!(decision.authorisation().is_none());
}

// Check three's violating fixture is a named gap: `context::TARGET_SCOPE` and
// `validation::constraint_is_satisfied`'s own trigger condition are both
// module-private (not `pub(crate)`), so a concrete counter-fixture cannot be
// constructed from outside those two modules without guessing their content.
// See `six_checks.rs`'s own `ac21` comment for the identical situation and
// precedent for leaving this as a named gap rather than a fabricated test.

#[test]
fn ac33_check_four_failure_alone_blocks_and_authorisation_is_none() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac33_check_four_failure_alone_blocks_and_authorisation_is_none",
    ) else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let mut proposal = baseline_passing_proposal();
    proposal.parameters = (0..10_000).map(|i| passing_parameter(&format!("p{i}"))).collect();

    let decision = crate::validate_proposal(&context, &surface, &proposal);
    assert_eq!(decision.decision, crate::Decision::Block);
    assert!(decision.authorisation().is_none());
}

#[test]
fn ac33_check_six_failure_alone_blocks_and_authorisation_is_none() {
    let Some(cohort) =
        real_verified_cohort_or_skip("ac33_check_six_failure_alone_blocks_and_authorisation_is_none")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let mut proposal = baseline_passing_proposal();
    proposal.declared_cost = u32::MAX;

    let decision = crate::validate_proposal(&context, &surface, &proposal);
    assert_eq!(decision.decision, crate::Decision::Block);
    assert!(decision.authorisation().is_none());
}

// ---------------------------------------------------------------------------------
// AC-34 (REQ-27, and REQ-15 of the step-three spec): a proposal blocked
// SPECIFICALLY by check five (the real gate call) yields no witness. This is
// also AC-33's check-five case.
// ---------------------------------------------------------------------------------

#[test]
fn ac34_check_five_gate_refusal_alone_blocks_and_authorisation_is_none() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac34_check_five_gate_refusal_alone_blocks_and_authorisation_is_none",
    ) else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let mut proposal = baseline_passing_proposal();
    // Tainted trust level consumed as Action at a consequential sink: the
    // gate's own ActionOnActionCriticalTainted refusal shape
    // (`gate_bridge_failclosed.rs`'s `ac29`), which fails check five alone
    // provided the sink is one of the cohort's own consequential sinks
    // (baseline_passing_proposal's sink already is).
    proposal.parameters = vec![crate::ProposalParameter {
        id: "v".to_string(),
        consume_mode: boundary_gjoll::types::ConsumeMode::Action,
        trust_level: boundary_gjoll::types::TrustLevel::Tainted,
        type_name: "comms:generic".to_string(),
    }];

    let decision = crate::validate_proposal(&context, &surface, &proposal);
    let (check_five_id, check_five_outcome) = &decision.checks[4];
    assert_eq!(*check_five_id, crate::CheckId::TaintCompatible);
    if outcome_is_pass(check_five_outcome) {
        eprintln!(
            "GIT-ACTUATOR-STEP-FOUR-GAP: ac34: this crate's own registry did not treat \
             the baseline sink as consequential for this fixture; the gate refusal this \
             test relies on could not be constructed. See gate_bridge_failclosed.rs's own \
             EC-7 discussion for why the two sink sets are not guaranteed to intersect."
        );
        return;
    }
    assert_eq!(
        decision.decision,
        crate::Decision::Block,
        "AC-34: a check-five-only failure must still Block overall"
    );
    assert!(
        decision.authorisation().is_none(),
        "AC-34: a gate refusal must never yield an executable witness"
    );
}

// ---------------------------------------------------------------------------------
// AC-36 (REQ-29): a witness minted for action A against target T refuses,
// with the mismatch variant, when called with a different action or target;
// the actuator is not invoked.
// ---------------------------------------------------------------------------------

#[test]
fn ac36_witness_action_name_mismatch_refuses_and_actuator_not_invoked() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac36_witness_action_name_mismatch_refuses_and_actuator_not_invoked",
    ) else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let proposal = baseline_passing_proposal();
    let decision = crate::validate_proposal(&context, &surface, &proposal);
    let Some(authorisation) = decision.authorisation() else {
        panic!("fixture sanity: the baseline proposal must validate to Allow");
    };

    let mismatched_action = crate::Action {
        action_name: "action:totally-different-from-the-witness".to_string(),
        target: proposal.target.clone(),
    };
    let scope = crate::Scope::new("fixture-scope");
    let mut recorder = crate::MinimalDecisionRecorder::new();
    let outcome = crate::broker_authorised_action(
        &context,
        &mismatched_action,
        &scope,
        authorisation,
        &mut recorder,
    );
    assert!(
        matches!(outcome, Err(crate::BrokerRefusal::WitnessMismatch)),
        "AC-36: an action-name mismatch must refuse with WitnessMismatch; got {outcome:?}"
    );
}

#[test]
fn ac36_witness_target_mismatch_refuses_and_actuator_not_invoked() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac36_witness_target_mismatch_refuses_and_actuator_not_invoked",
    ) else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let proposal = baseline_passing_proposal();
    let decision = crate::validate_proposal(&context, &surface, &proposal);
    let Some(authorisation) = decision.authorisation() else {
        panic!("fixture sanity: the baseline proposal must validate to Allow");
    };

    let mismatched_action = crate::Action {
        action_name: proposal.action_name.clone(),
        target: "totally-different-target-from-the-witness".to_string(),
    };
    let scope = crate::Scope::new("fixture-scope");
    let mut recorder = crate::MinimalDecisionRecorder::new();
    let outcome = crate::broker_authorised_action(
        &context,
        &mismatched_action,
        &scope,
        authorisation,
        &mut recorder,
    );
    assert!(
        matches!(outcome, Err(crate::BrokerRefusal::WitnessMismatch)),
        "AC-36: a target mismatch must refuse with WitnessMismatch; got {outcome:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-37 (REQ-30): broker_action, called with ANY arguments, refuses naming
// absent authorisation evidence, and never invokes the actuator.
// ---------------------------------------------------------------------------------

#[test]
fn ac37_broker_action_always_refuses_naming_absent_authorisation_evidence() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac37_broker_action_always_refuses_naming_absent_authorisation_evidence",
    ) else {
        return;
    };
    let (context, _surface) = fixture_context_and_surface(&cohort);

    let probes: Vec<(crate::Action, crate::Scope)> = vec![
        (
            crate::Action {
                action_name: "action:git.commit".to_string(),
                target: "fixture-target".to_string(),
            },
            crate::Scope::new("fixture-scope"),
        ),
        (
            crate::Action {
                action_name: "action:totally-arbitrary".to_string(),
                target: "totally-arbitrary-target".to_string(),
            },
            crate::Scope::new("scope-not-permitted"),
        ),
    ];
    for (action, scope) in &probes {
        let outcome = crate::broker_action(&context, action, scope);
        // The scope check still runs first (AC-39); only a PERMITTED scope
        // reaches the point where absent authorisation evidence is the
        // actual reason.
        if scope.as_str() == "fixture-scope" || scope.as_str() == "public-surface-fixture-scope" {
            assert!(
                matches!(outcome, Err(crate::BrokerRefusal::NoAuthorisationEvidence)),
                "AC-37: with a permitted scope, broker_action must refuse naming absent \
                 authorisation evidence; got {outcome:?}"
            );
        } else {
            assert!(outcome.is_err(), "AC-37: broker_action must never return Ok(_)");
        }
    }
}

// ---------------------------------------------------------------------------------
// AC-39 (REQ-37): the credential-scope check runs first on both entry points.
// ---------------------------------------------------------------------------------

#[test]
fn ac39_broker_action_scope_check_runs_before_anything_else() {
    let Some(cohort) =
        real_verified_cohort_or_skip("ac39_broker_action_scope_check_runs_before_anything_else")
    else {
        return;
    };
    let (context, _surface) = fixture_context_and_surface(&cohort);
    let action = crate::Action {
        action_name: "action:git.commit".to_string(),
        target: "fixture-target".to_string(),
    };
    let scope = crate::Scope::new("scope-absolutely-not-on-any-allowlist");
    let outcome = crate::broker_action(&context, &action, &scope);
    assert!(
        matches!(outcome, Err(crate::BrokerRefusal::ScopeNotPermitted)),
        "AC-39: an unpermitted scope must refuse with ScopeNotPermitted before any other \
         check; got {outcome:?}"
    );
}

#[test]
fn ac39_broker_authorised_action_scope_check_runs_before_witness_and_audit() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac39_broker_authorised_action_scope_check_runs_before_witness_and_audit",
    ) else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let proposal = baseline_passing_proposal();
    let decision = crate::validate_proposal(&context, &surface, &proposal);
    let Some(authorisation) = decision.authorisation() else {
        panic!("fixture sanity: the baseline proposal must validate to Allow");
    };
    // A witness that MATCHES the action, but a scope that does not, with a
    // recorder that would panic if ever written to, proving the scope check
    // pre-empts the witness match and the audit write both.
    struct PanicIfWrittenRecorder;
    impl crate::DecisionRecorder for PanicIfWrittenRecorder {
        fn record(
            &mut self,
            _agent_id: &crate::AgentId,
            _action: &crate::Action,
            _decision: crate::Decision,
            _checks: &[crate::CheckRecord],
        ) -> Result<(), String> {
            panic!(
                "AC-39: the audit write must never be reached when the credential-scope \
                 check has already refused"
            );
        }
    }
    let action = crate::Action {
        action_name: proposal.action_name.clone(),
        target: proposal.target.clone(),
    };
    let scope = crate::Scope::new("scope-absolutely-not-on-any-allowlist");
    let mut recorder = PanicIfWrittenRecorder;
    let outcome = crate::broker_authorised_action(
        &context,
        &action,
        &scope,
        authorisation,
        &mut recorder,
    );
    assert!(
        matches!(outcome, Err(crate::BrokerRefusal::ScopeNotPermitted)),
        "AC-39: an unpermitted scope must refuse with ScopeNotPermitted before the \
         witness match or the audit write; got {outcome:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-40 (REQ-31, REQ-33): the decision record is written before the actuator
// is invoked. Proven without any working repository: a successful audit
// write followed by the actuator being REACHED (surfaced as
// `BrokerRefusal::ActuatorRefused`, never `AuditWriteFailed`) demonstrates the
// structural ordering.
// ---------------------------------------------------------------------------------

struct OrderRecordingRecorder {
    events: Vec<&'static str>,
}

impl crate::DecisionRecorder for OrderRecordingRecorder {
    fn record(
        &mut self,
        _agent_id: &crate::AgentId,
        _action: &crate::Action,
        _decision: crate::Decision,
        _checks: &[crate::CheckRecord],
    ) -> Result<(), String> {
        self.events.push("recorded");
        Ok(())
    }
}

#[test]
fn ac40_audit_write_happens_before_the_actuator_is_reached() {
    let Some(cohort) =
        real_verified_cohort_or_skip("ac40_audit_write_happens_before_the_actuator_is_reached")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let mut proposal = baseline_passing_proposal();
    proposal.action_name = "action:git.commit".to_string();
    let decision = crate::validate_proposal(&context, &surface, &proposal);
    let Some(authorisation) = decision.authorisation() else {
        panic!("fixture sanity: the baseline commit proposal must validate to Allow");
    };

    let action = crate::Action {
        action_name: proposal.action_name.clone(),
        target: proposal.target.clone(),
    };
    let scope = crate::Scope::new("fixture-scope");
    let mut recorder = OrderRecordingRecorder { events: Vec::new() };
    let outcome = crate::broker_authorised_action(
        &context,
        &action,
        &scope,
        authorisation,
        &mut recorder,
    );

    assert!(
        !recorder.events.is_empty(),
        "AC-40: the audit write must have been attempted"
    );
    // With NO working-repository environment variable configured in this
    // unit-test binary, the actuator's own repository resolution fails
    // deterministically; seeing THAT refusal (rather than AuditWriteFailed)
    // proves the code path passed the audit-write stage and reached the
    // actuator (REQ-33's structural ordering).
    assert!(
        matches!(
            outcome,
            Err(crate::BrokerRefusal::ActuatorRefused(
                actuator_git::ActuationRefusal::RepositoryResolution { .. }
            ))
        ),
        "AC-40: with a successful audit write, the actuator must be reached next; got \
         {outcome:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-41 (REQ-32): a recorder whose write fails refuses with the
// audit-write-failure variant, and the actuator is never invoked (proven by
// elimination: the refusal is AuditWriteFailed, never ActuatorRefused).
// ---------------------------------------------------------------------------------

struct FailingRecorder;

impl crate::DecisionRecorder for FailingRecorder {
    fn record(
        &mut self,
        _agent_id: &crate::AgentId,
        _action: &crate::Action,
        _decision: crate::Decision,
        _checks: &[crate::CheckRecord],
    ) -> Result<(), String> {
        Err("fixture-induced write failure (AC-41)".to_string())
    }
}

#[test]
fn ac41_failing_recorder_refuses_and_actuator_is_never_invoked() {
    let Some(cohort) =
        real_verified_cohort_or_skip("ac41_failing_recorder_refuses_and_actuator_is_never_invoked")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let proposal = baseline_passing_proposal();
    let decision = crate::validate_proposal(&context, &surface, &proposal);
    let Some(authorisation) = decision.authorisation() else {
        panic!("fixture sanity: the baseline proposal must validate to Allow");
    };
    let action = crate::Action {
        action_name: proposal.action_name.clone(),
        target: proposal.target.clone(),
    };
    let scope = crate::Scope::new("fixture-scope");
    let mut recorder = FailingRecorder;
    let outcome = crate::broker_authorised_action(
        &context,
        &action,
        &scope,
        authorisation,
        &mut recorder,
    );
    assert!(
        matches!(outcome, Err(crate::BrokerRefusal::AuditWriteFailed { .. })),
        "AC-41: a failing recorder must refuse with AuditWriteFailed, never \
         ActuatorRefused (which would mean the actuator was reached despite the write \
         failing); got {outcome:?}"
    );
    // The full behavioural half (asserting the ABSENCE of a real git effect
    // in a working repository) needs a real repository and therefore
    // environment mutation; see this file's header. It lives in
    // crates/himinbjorg/tests/public_surface.rs instead.
}

// ---------------------------------------------------------------------------------
// AC-42 (REQ-34): the minimal recorder's public surface carries no update and
// no delete operation. A source scan (std-only, no dependency of any kind).
// ---------------------------------------------------------------------------------

#[test]
fn ac42_minimal_recorder_has_no_update_or_delete_method() {
    let audit_rs = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("src")
        .join("audit.rs");
    let Ok(src) = std::fs::read_to_string(&audit_rs) else {
        panic!("expected crates/himinbjorg/src/audit.rs to exist once this step lands");
    };
    let cleaned: String = src
        .lines()
        .map(|line| match line.find("//") {
            Some(idx) => format!("{}{}", &line[..idx], " ".repeat(line.len() - idx)),
            None => line.to_string(),
        })
        .collect::<Vec<_>>()
        .join("\n");
    for forbidden in ["fn update(", "fn delete(", "fn remove("] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-42: audit.rs must define no {forbidden:?} method on the minimal recorder \
             (REQ-34: append-only, structurally, per HK-2)"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-43 (REQ-34): a sequence of brokered actions appears in the recorder in
// the order written, with no earlier record altered.
// ---------------------------------------------------------------------------------

#[test]
fn ac43_sequence_of_brokered_actions_recorded_in_order_unaltered() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac43_sequence_of_brokered_actions_recorded_in_order_unaltered",
    ) else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let mut recorder = crate::MinimalDecisionRecorder::new();
    let scope = crate::Scope::new("fixture-scope");

    for i in 0..3 {
        let mut proposal = baseline_passing_proposal();
        proposal.action_name = "action:git.commit".to_string();
        proposal.declared_cost = i; // vary the fixture trivially per call
        let decision = crate::validate_proposal(&context, &surface, &proposal);
        let Some(authorisation) = decision.authorisation() else {
            panic!("fixture sanity: iteration {i}'s proposal must validate to Allow");
        };
        let action = crate::Action {
            action_name: proposal.action_name.clone(),
            target: proposal.target.clone(),
        };
        // Each call fails at the (unconfigured) actuator, which is fine: the
        // audit write, per REQ-33's ordering, has already happened by then.
        let _ = crate::broker_authorised_action(
            &context,
            &action,
            &scope,
            authorisation,
            &mut recorder,
        );
    }

    let records = recorder.records();
    assert_eq!(
        records.len(),
        3,
        "AC-43: every one of the three brokered actions must have produced one recorded \
         entry, in order"
    );
}

// ---------------------------------------------------------------------------------
// AC-44 (REQ-32): a blocked proposal never reaches the actuator on any path;
// its decision record is still available to be written by the caller
// directly (the recorder's write contract is general purpose, not tied to an
// Authorisation).
// ---------------------------------------------------------------------------------

#[test]
fn ac44_a_blocked_decision_can_still_be_recorded_by_the_caller() {
    let Some(cohort) =
        real_verified_cohort_or_skip("ac44_a_blocked_decision_can_still_be_recorded_by_the_caller")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let mut proposal = baseline_passing_proposal();
    proposal.action_name = "action:totally-unknown-and-never-permitted".to_string();
    let decision = crate::validate_proposal(&context, &surface, &proposal);
    assert_eq!(decision.decision, crate::Decision::Block);
    assert!(
        decision.authorisation().is_none(),
        "fixture sanity: a Block decision must mint no witness, so \
         broker_authorised_action cannot even be called for it"
    );

    // The caller can still write the block's own record directly: the
    // recorder's write contract takes the decision and its six checks, not
    // an Authorisation, so a blocked decision's audit trail is not
    // structurally unwritable.
    let action = crate::Action {
        action_name: proposal.action_name.clone(),
        target: proposal.target.clone(),
    };
    let mut recorder = crate::MinimalDecisionRecorder::new();
    let write_result = recorder.record(&context.agent_id, &action, decision.decision, &decision.checks);
    assert!(
        write_result.is_ok(),
        "AC-44: the block's own decision record must still be writable by the caller; \
         got {write_result:?}"
    );
    assert_eq!(recorder.records().len(), 1);
}

// ---------------------------------------------------------------------------------
// AC-45 (data schema, section 6): the recorder's record type carries no
// entry_id, timestamp, world_model_state_hash or signature field, and its own
// doc comment states they are absent, not empty.
// ---------------------------------------------------------------------------------

#[test]
fn ac45_recorder_record_type_omits_entry_id_timestamp_hash_and_signature() {
    let audit_rs = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("src")
        .join("audit.rs");
    let Ok(src) = std::fs::read_to_string(&audit_rs) else {
        panic!("expected crates/himinbjorg/src/audit.rs to exist once this step lands");
    };
    for forbidden_field in ["entry_id", "timestamp", "world_model_state_hash", "signature"] {
        assert!(
            !src.contains(&format!("{forbidden_field}:")),
            "AC-45: the recorder's record type must not declare a {forbidden_field:?} \
             field (absent, not empty, per the data schema, section 6)"
        );
    }
    assert!(
        src.to_lowercase().contains("absent"),
        "AC-45: audit.rs's own doc comment must state that entry_id, timestamp, \
         world_model_state_hash and signature are ABSENT, not empty, and why"
    );
}

// ---------------------------------------------------------------------------------
// AC-56 (REQ-28): the witness names the action, target and sink it
// authorises, and carries exactly six CheckRecords, each Pass.
// ---------------------------------------------------------------------------------

#[test]
fn ac56_witness_accessors_report_the_authorised_action_target_sink_and_six_passes() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac56_witness_accessors_report_the_authorised_action_target_sink_and_six_passes",
    ) else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let proposal = baseline_passing_proposal();
    let decision = crate::validate_proposal(&context, &surface, &proposal);
    let Some(authorisation) = decision.authorisation() else {
        panic!("fixture sanity: the baseline proposal must validate to Allow");
    };

    assert_eq!(authorisation.action_name(), proposal.action_name);
    assert_eq!(authorisation.target(), proposal.target);
    assert_eq!(authorisation.sink(), proposal.sink);
    let checks = authorisation.checks();
    assert_eq!(checks.len(), 6, "AC-56: the witness must carry exactly six CheckRecords");
    assert!(
        checks.iter().all(|(_, outcome)| outcome_is_pass(outcome)),
        "AC-56: every one of the witness's six CheckRecords must be Pass"
    );
}

// ---------------------------------------------------------------------------------
// AC-57 (REQ-38): two distinct ActuationRefusal variants map to two
// distinguishable BrokerRefusal outcomes, neither collapsed into one opaque
// value.
// ---------------------------------------------------------------------------------

#[test]
fn ac57_two_distinct_actuator_refusals_map_to_two_distinguishable_broker_refusals() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac57_two_distinct_actuator_refusals_map_to_two_distinguishable_broker_refusals",
    ) else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let scope = crate::Scope::new("fixture-scope");

    // Scenario A: a commit-shaped action. With no working-repository
    // environment variable configured, actuator-git's own repository
    // resolution fails.
    let mut commit_proposal = baseline_passing_proposal();
    commit_proposal.action_name = "action:git.commit".to_string();
    let commit_decision = crate::validate_proposal(&context, &surface, &commit_proposal);
    let Some(commit_auth) = commit_decision.authorisation() else {
        panic!("fixture sanity: the commit-shaped proposal must validate to Allow");
    };
    let commit_action = crate::Action {
        action_name: commit_proposal.action_name.clone(),
        target: commit_proposal.target.clone(),
    };
    let mut recorder_a = crate::MinimalDecisionRecorder::new();
    let outcome_a = crate::broker_authorised_action(
        &context,
        &commit_action,
        &scope,
        commit_auth,
        &mut recorder_a,
    );

    // Scenario B: a push-shaped action whose target ("fixture-target",
    // Himinbjörg's own target scope fixture) is assumed NOT to be a member
    // of actuator-git's own, separately-hardcoded permitted-ref allowlist
    // (EC-17: the two allowlists answer different questions and are never
    // reconciled), so the actuator's target-membership check fails instead.
    let mut push_proposal = baseline_passing_proposal();
    push_proposal.action_name = "action:git.push".to_string();
    let push_decision = crate::validate_proposal(&context, &surface, &push_proposal);
    let Some(push_auth) = push_decision.authorisation() else {
        panic!("fixture sanity: the push-shaped proposal must validate to Allow");
    };
    let push_action = crate::Action {
        action_name: push_proposal.action_name.clone(),
        target: push_proposal.target.clone(),
    };
    let mut recorder_b = crate::MinimalDecisionRecorder::new();
    let outcome_b = crate::broker_authorised_action(
        &context,
        &push_action,
        &scope,
        push_auth,
        &mut recorder_b,
    );

    match (&outcome_a, &outcome_b) {
        (
            Err(crate::BrokerRefusal::ActuatorRefused(reason_a)),
            Err(crate::BrokerRefusal::ActuatorRefused(reason_b)),
        ) => {
            assert_ne!(
                format!("{reason_a:?}"),
                format!("{reason_b:?}"),
                "AC-57: two different ActuationRefusal variants must map to two \
                 DIFFERENT, recoverable BrokerRefusal::ActuatorRefused payloads, never \
                 collapsed to the same opaque value; got {reason_a:?} and {reason_b:?}"
            );
        }
        other => {
            eprintln!(
                "GIT-ACTUATOR-STEP-FOUR-GAP: ac57: this file's own assumed mapping from \
                 action_name to a GitOperation did not surface two distinct \
                 ActuatorRefused variants ({other:?}); the mapping assumption in this \
                 file's own header may not hold against the real implementation. See the \
                 header for the flagged assumption."
            );
        }
    }
}

// ---------------------------------------------------------------------------------
// AC-58 (REQ-39): exactly three gates before the actuator call (scope,
// witness match, audit write); no re-derivation of authorisation.
// ---------------------------------------------------------------------------------

#[test]
fn ac58_broker_rs_calls_no_re_derivation_of_authorisation() {
    let broker_rs = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("src")
        .join("broker.rs");
    let Ok(src) = std::fs::read_to_string(&broker_rs) else {
        panic!("expected crates/himinbjorg/src/broker.rs to exist once this step lands");
    };
    let cleaned: String = src
        .lines()
        .map(|line| match line.find("//") {
            Some(idx) => format!("{}{}", &line[..idx], " ".repeat(line.len() - idx)),
            None => line.to_string(),
        })
        .collect::<Vec<_>>()
        .join("\n");
    for forbidden in [
        "validate_proposal(",
        "evaluate_taint_compatibility(",
        "sinks::registry(",
        "CohortSurface",
    ] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-58: broker.rs must call no {forbidden:?} anywhere: the authorisation \
             comes entirely from the witness, and this module re-derives none of it \
             (REQ-39)"
        );
    }
}

#[test]
fn ac58_fully_authorised_call_reaches_the_actuator_with_no_further_query() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac58_fully_authorised_call_reaches_the_actuator_with_no_further_query",
    ) else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort);
    let mut proposal = baseline_passing_proposal();
    proposal.action_name = "action:git.commit".to_string();
    let decision = crate::validate_proposal(&context, &surface, &proposal);
    let Some(authorisation) = decision.authorisation() else {
        panic!("fixture sanity: the baseline commit proposal must validate to Allow");
    };
    let action = crate::Action {
        action_name: proposal.action_name.clone(),
        target: proposal.target.clone(),
    };
    let scope = crate::Scope::new("fixture-scope");
    let mut recorder = crate::MinimalDecisionRecorder::new();
    let outcome = crate::broker_authorised_action(
        &context,
        &action,
        &scope,
        authorisation,
        &mut recorder,
    );
    // Reaching ActuatorRefused (not ScopeNotPermitted, not WitnessMismatch,
    // not AuditWriteFailed, not NoAuthorisationEvidence) IS the proof that
    // the three gates all cleared and the actuator was invoked with no
    // fourth check interposed.
    assert!(
        matches!(outcome, Err(crate::BrokerRefusal::ActuatorRefused(_))),
        "AC-58: with a permitted scope, a matching witness and a successful audit write, \
         the actuator must be reached; got {outcome:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-60 (REQ-41): action_critical_for remains the D24 agent-scoped
// membership test, unaffected by this step, unaffected by other agents'
// sinks. Re-confirms `gate_bridge_failclosed.rs`'s own `ac25` property as a
// regression pin for this step specifically.
// ---------------------------------------------------------------------------------

#[test]
fn ac60_action_critical_for_is_membership_only_unaffected_by_other_agents_sinks() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac60_action_critical_for_is_membership_only_unaffected_by_other_agents_sinks",
    ) else {
        return;
    };
    let surface = cohort.surface();

    for member_sink in hierarchy_vor::cohort::CONSEQUENTIAL_SINKS {
        assert!(
            crate::gate_bridge::action_critical_for(member_sink, &surface),
            "AC-60: a sink that IS a member of THIS agent's own consequential_sinks() \
             must derive action_critical = true, unaffected by this step's additions"
        );
    }
    // A sink absent from this agent's own set is not action-critical
    // regardless of any OTHER agent's sink declarations; there is no
    // parameter here through which another agent's sinks could even be
    // supplied, which is itself the structural half of "by nothing else".
    assert!(
        !crate::gate_bridge::action_critical_for(
            "sink:definitely-not-a-member-of-any-cohorts-consequential-set",
            &surface,
        ),
        "AC-60: a sink absent from this agent's own consequential_sinks() must derive \
         action_critical = false"
    );
}
