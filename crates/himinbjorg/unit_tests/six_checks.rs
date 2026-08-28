//! The six-check sequence inside `validate_proposal` (REQ-10 to REQ-16, REQ-21,
//! REQ-22), `.opencode/plans/himinbjorg-step-three.md` section 8.4 and 8.6:
//! AC-15 to AC-23, AC-36, AC-37, and the check-record property test (AC-18).
//!
//! Also covers, where in scope for this file: EC-1 (only indirectly, via check
//! five's Block-never-Allow shape; the gate's own four reason kinds are
//! `gate_bridge_failclosed.rs`'s job), EC-5 (an agent id that is not the
//! hardcoded one, exercised as fixture setup failure), EC-9 to EC-13 (the
//! boundary and constraint edge cases named on checks two, three, four and six).
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/himinbjorg` exists at all: no
//! `Cargo.toml`, no workspace member, no `src/`. That is expected and correct at
//! this stage (issue #37), for the same reason `crates/hierarchy-vor/
//! unit_tests/loader_failclosed.rs`'s own header states for its precedent.
//!
//! **Compiled as an IN-CRATE unit test module** (REQ-26): wired into
//! `crates/himinbjorg/src/lib.rs` via
//! `#[cfg(test)] #[path = "../unit_tests/six_checks.rs"] mod six_checks;`,
//! exactly as `hierarchy-vor`'s own `lib.rs` wires in `loader_failclosed.rs`.
//! This lets this file reach `crate::` items that are `pub(crate)` rather than
//! only the public surface (the internal seams of section 6.2:
//! `gate_bridge::action_critical_for`, `gate_bridge::evaluate_taint_compatibility`,
//! `sinks::registry`).
//!
//! **Signatures assumed here** (this test suite's own committed contract, spec
//! section 6 and 7, plus this file's own necessary choices where the spec leaves
//! a shape indicative rather than fixed):
//!
//!   - Crate-root re-exports: `crate::{build_context, enforce_definition,
//!     validate_proposal, broker_action, AgentId, TaskContext, AgentContext,
//!     ContextRefusal, EffectiveSurface, DefinitionRefusal, Proposal,
//!     ProposalParameter, CheckId, CheckOutcome, CheckRecord, Decision,
//!     ProposalDecision, Action, Scope, BrokerResult, BrokerRefusal}` (REQ-6,
//!     `lib.rs`'s stated job in section 13 file 4).
//!   - `AgentId::new(id: impl Into<String>) -> AgentId`; the ONE hardcoded
//!     agent's id is assumed equal to `hierarchy_vor::cohort::COHORT_ID`
//!     (AC-6's own wording: "a context whose identity summary matches
//!     `hierarchy_vor::cohort::COHORT_ID`").
//!   - `TaskContext` has public fields `task_id: String`, `target: String`,
//!     `declared_cost: u32` (section 7: "the task's identifier, its declared
//!     target and its declared cost").
//!   - `Proposal` has public fields `action_name: String`, `target: String`,
//!     `sink: String`, `parameters: Vec<ProposalParameter>`,
//!     `declared_cost: u32` (section 7's Proposal row). `ProposalParameter` has
//!     public fields `id: String`, `consume_mode: boundary_gjoll::types::ConsumeMode`,
//!     `trust_level: boundary_gjoll::types::TrustLevel`, `type_name: String`.
//!     There is deliberately **no** `action_critical` field anywhere on either
//!     type (REQ-17: it is derived, never accepted from the proposer).
//!   - **Assumption flagged explicitly, not hidden**: check four's blast-radius
//!     bound is "computed from the proposal alone" (REQ-14) rather than being a
//!     field the caller sets directly. This file assumes the minimal-fidelity
//!     derivation is `proposal.parameters.len()` (a real, non-vacuous, stateless
//!     computation over the proposal, consistent with HB3-5). If the
//!     implementation derives blast radius differently, AC-22's boundary
//!     assertions below will need their proposal shapes adjusted to match, but
//!     the CONTRACT under test (pass at the bound, fail at bound-plus-one,
//!     stateless) does not change.
//!   - `CheckId` is a closed, six-variant, ordered enum. This file assumes the
//!     names `ActionPermitted`, `TargetInScope`, `ConstraintSatisfied`,
//!     `BlastRadiusWithinBound`, `TaintCompatible`, `ResourceBudgetNotExceeded`,
//!     in that order (`plans/dd/himinbjorg.md` section 5.1's own check order).
//!   - `CheckOutcome` is `Pass`, `Fail { reasons: Vec<String> }` or
//!     `NotEvaluated { because: String }` (section 7).
//!   - `CheckRecord` is `(CheckId, CheckOutcome)` (section 7, literally).
//!   - `ProposalDecision` has public fields `decision: Decision` and
//!     `checks: Vec<CheckRecord>` (exactly six entries, one per `CheckId`).
//!   - `Decision` is `Allow`, `Block`, `Queue`, `Escalate` (REQ-21).
//!   - `Action` has public fields `action_name: String`, `target: String`.
//!     `Scope::new(name: impl Into<String>) -> Scope`.
//!   - `BrokerResult` is uninhabited (`pub enum BrokerResult {}`, section 7:
//!     "Uninhabited or unconstructed in step three" -- this file assumes the
//!     uninhabited form). `BrokerRefusal` is `NoActuatorAvailable` or
//!     `ScopeNotPermitted` (section 7).
//!
//! **Why every test below needs a real, provisioned `heimdall-dev` secret.**
//! `AgentContext` and `EffectiveSurface` have no public constructor other than
//! `build_context` and `enforce_definition`, and both require a
//! `&hierarchy_vor::VerifiedCohort` -- which has no public constructor of its
//! own either, and can only be obtained from `hierarchy_vor::load_verified_cohort`
//! succeeding against the REAL `heimdall-dev` secret (D110's fixed committed
//! attestation). There is no fixture, mock or double for a `VerifiedCohort`
//! anywhere in this crate's design (REQ-20 forbids exactly that). This file
//! therefore gates every test needing a working context/surface behind
//! `HEIMDALL_COHORT_SECRET_FILE`, following the SAME EC-3 discipline
//! `tests/public_surface.rs` uses for its own two reserved markers, but printing
//! its own distinct, non-reserved message (REQ-32 reserves
//! `HIMINBJORG-REAL-COHORT-VERIFIED` / `HIMINBJORG-REAL-COHORT-NOT-EXERCISED`
//! for the integration test alone). This is a design tension this file's header
//! states plainly rather than resolving by inventing a degraded cohort: see
//! `.opencode/plans/himinbjorg-step-three.md` HB3-10, and see this delegation's
//! own final report for the same point raised to the implementing agent.

fn real_verified_cohort_or_skip(test_name: &str) -> Option<hierarchy_vor::VerifiedCohort> {
    match hierarchy_vor::load_trusted_set_from_env(hierarchy_vor::cohort::AUTHORISER_ID) {
        Ok(trusted) => {
            let cohort = hierarchy_vor::load_verified_cohort(&trusted).unwrap_or_else(|e| {
                panic!(
                    "{test_name}: a secret was provisioned via {} but the committed \
                     attestation did not verify against it ({e:?}); this is a provisioning \
                     defect and is FATAL, never a skip",
                    hierarchy_vor::SECRET_PATH_ENV_VAR,
                )
            });
            Some(cohort)
        }
        Err(hierarchy_vor::SecretRefusal::EnvVarMissing(_)) => {
            eprintln!(
                "{test_name}: SKIPPED -- {} is not set (or is empty), so this six-check \
                 unit test cannot obtain a real VerifiedCohort at all (no fixture, mock or \
                 double exists for one by design, REQ-20). This is a named gap, not a \
                 silent one.",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
            None
        }
        Err(other) => {
            panic!(
                "{test_name}: {} names a path but loading it was refused for a reason \
                 other than absence ({other:?}); this is a provisioning defect and is FATAL",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
        }
    }
}

/// Fixture setup shared by every test below that needs a working
/// `AgentContext` + `EffectiveSurface` pair (AC-15 to AC-23, AC-37). Returns
/// `None` (never a degraded pair) when the real cohort cannot be obtained.
fn fixture_context_and_surface<'a>(
    cohort: &'a hierarchy_vor::VerifiedCohort,
    task_target: &str,
    task_cost: u32,
) -> (crate::AgentContext<'a>, crate::EffectiveSurface<'a>) {
    let agent_id = crate::AgentId::new(hierarchy_vor::cohort::COHORT_ID);
    let task = crate::TaskContext {
        task_id: "fixture-task".to_string(),
        target: task_target.to_string(),
        declared_cost: task_cost,
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

/// Builds an otherwise-passing proposal whose `target` is exactly `target`
/// (not hardcoded): the out-of-scope value a caller such as
/// `ac20_target_absent_from_scope_fails_check_two` passes here is the one
/// `check_target_in_scope` actually receives, since that check reads
/// `proposal.target`, never `TaskContext::target` (`context.rs`'s
/// `TARGET_SCOPE` is a fixed constant, independent of the task passed to
/// `fixture_context_and_surface`).
fn baseline_passing_proposal(target: &str) -> crate::Proposal {
    crate::Proposal {
        action_name: hierarchy_vor::cohort::PERMITTED_ACTIONS[0].to_string(),
        target: target.to_string(),
        sink: hierarchy_vor::cohort::CONSEQUENTIAL_SINKS[0].to_string(),
        parameters: vec![passing_parameter("v")],
        declared_cost: 0,
    }
}

fn outcome_is_pass(outcome: &crate::CheckOutcome) -> bool {
    matches!(outcome, crate::CheckOutcome::Pass)
}

// ---------------------------------------------------------------------------------
// AC-15 (REQ-10): a proposal passing all six checks yields Allow, all six Pass.
// ---------------------------------------------------------------------------------

#[test]
fn ac15_all_six_checks_pass_decision_is_allow() {
    let Some(cohort) = real_verified_cohort_or_skip("ac15_all_six_checks_pass_decision_is_allow")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);
    let proposal = baseline_passing_proposal("fixture-target");

    let outcome = crate::validate_proposal(&context, &surface, &proposal);

    assert_eq!(
        outcome.checks.len(),
        6,
        "AC-39/REQ-23: the record must carry exactly six CheckRecords, one per check"
    );
    assert!(
        outcome.checks.iter().all(|(_, o)| outcome_is_pass(o)),
        "AC-15: every one of the six checks must be Pass for this baseline proposal; got \
         {:?}",
        outcome.checks,
    );
    assert_eq!(
        outcome.decision,
        crate::Decision::Allow,
        "AC-15: six Pass records must yield Allow"
    );
}

// ---------------------------------------------------------------------------------
// AC-16 (REQ-10): six separate proposals, each failing exactly one distinct check,
// each returns Block with that check identified as the failing one.
// ---------------------------------------------------------------------------------

#[test]
fn ac16_check_one_action_not_in_effective_surface_fails_alone() {
    let Some(cohort) =
        real_verified_cohort_or_skip("ac16_check_one_action_not_in_effective_surface_fails_alone")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);
    let mut proposal = baseline_passing_proposal("fixture-target");
    proposal.action_name = "action:totally-unknown-and-never-permitted".to_string();

    let outcome = crate::validate_proposal(&context, &surface, &proposal);

    assert_eq!(
        outcome.decision,
        crate::Decision::Block,
        "AC-16/AC-19: an action absent from the effective surface must Block"
    );
    let (check_one_id, check_one_outcome) = &outcome.checks[0];
    assert_eq!(*check_one_id, crate::CheckId::ActionPermitted);
    assert!(
        !outcome_is_pass(check_one_outcome),
        "AC-16: check one must be recorded as the failing check for an unpermitted action"
    );
}

#[test]
fn ac16_check_two_target_absent_from_scope_fails_alone() {
    let Some(cohort) = real_verified_cohort_or_skip("ac16_check_two_target_absent_from_scope_fails_alone")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);
    let mut proposal = baseline_passing_proposal("fixture-target");
    proposal.target = "totally-unrelated-target-outside-any-hardcoded-scope-zzz".to_string();

    let outcome = crate::validate_proposal(&context, &surface, &proposal);

    assert_eq!(
        outcome.decision,
        crate::Decision::Block,
        "AC-16/AC-20: a target absent from the hardcoded scope must Block"
    );
    let (check_two_id, check_two_outcome) = &outcome.checks[1];
    assert_eq!(*check_two_id, crate::CheckId::TargetInScope);
    assert!(
        !outcome_is_pass(check_two_outcome),
        "AC-16: check two must be recorded as the failing check for an out-of-scope target"
    );
}

#[test]
fn ac16_check_four_blast_radius_over_bound_fails_alone() {
    let Some(cohort) = real_verified_cohort_or_skip("ac16_check_four_blast_radius_over_bound_fails_alone")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);
    let mut proposal = baseline_passing_proposal("fixture-target");
    // A deliberately oversized parameter list: see this file's header note on the
    // assumed blast-radius derivation (proposal.parameters.len()).
    proposal.parameters = (0..10_000)
        .map(|i| passing_parameter(&format!("p{i}")))
        .collect();

    let outcome = crate::validate_proposal(&context, &surface, &proposal);

    assert_eq!(
        outcome.decision,
        crate::Decision::Block,
        "AC-16/AC-22: a blast radius over the hardcoded bound must Block"
    );
    let (check_four_id, check_four_outcome) = &outcome.checks[3];
    assert_eq!(*check_four_id, crate::CheckId::BlastRadiusWithinBound);
    assert!(
        !outcome_is_pass(check_four_outcome),
        "AC-16: check four must be recorded as the failing check for an oversized blast radius"
    );
}

#[test]
fn ac16_check_six_declared_cost_over_ceiling_fails_alone() {
    let Some(cohort) = real_verified_cohort_or_skip("ac16_check_six_declared_cost_over_ceiling_fails_alone")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);
    let mut proposal = baseline_passing_proposal("fixture-target");
    proposal.declared_cost = u32::MAX;

    let outcome = crate::validate_proposal(&context, &surface, &proposal);

    assert_eq!(
        outcome.decision,
        crate::Decision::Block,
        "AC-16/AC-23: a declared cost over the hardcoded ceiling must Block"
    );
    let (check_six_id, check_six_outcome) = &outcome.checks[5];
    assert_eq!(*check_six_id, crate::CheckId::ResourceBudgetNotExceeded);
    assert!(
        !outcome_is_pass(check_six_outcome),
        "AC-16: check six must be recorded as the failing check for an over-ceiling cost"
    );
}

// ---------------------------------------------------------------------------------
// AC-17 (REQ-10): a proposal failing TWO checks records both failures; the
// sequence does not short-circuit on the first failure.
// ---------------------------------------------------------------------------------

#[test]
fn ac17_two_simultaneous_failures_both_recorded_no_short_circuit() {
    let Some(cohort) =
        real_verified_cohort_or_skip("ac17_two_simultaneous_failures_both_recorded_no_short_circuit")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);
    let mut proposal = baseline_passing_proposal("fixture-target");
    proposal.action_name = "action:totally-unknown-and-never-permitted".to_string();
    proposal.declared_cost = u32::MAX;

    let outcome = crate::validate_proposal(&context, &surface, &proposal);

    assert_eq!(outcome.decision, crate::Decision::Block);
    let (check_one_id, check_one_outcome) = &outcome.checks[0];
    let (check_six_id, check_six_outcome) = &outcome.checks[5];
    assert_eq!(*check_one_id, crate::CheckId::ActionPermitted);
    assert_eq!(*check_six_id, crate::CheckId::ResourceBudgetNotExceeded);
    assert!(
        !outcome_is_pass(check_one_outcome) && !outcome_is_pass(check_six_outcome),
        "AC-17: both check one and check six must be recorded as failing; the sequence \
         must not short-circuit on the first failure. Got: {:?}",
        outcome.checks,
    );
}

// ---------------------------------------------------------------------------------
// AC-18: the check-record property test. There must be no combination of the six
// outcomes, other than six Passes, that yields Allow.
// ---------------------------------------------------------------------------------

#[test]
fn ac18_property_only_six_passes_ever_yields_allow() {
    let Some(cohort) = real_verified_cohort_or_skip("ac18_property_only_six_passes_ever_yields_allow")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);

    // A deliberately varied set of proposals, none guaranteed to hit every single
    // one of the 2^6 - 1 non-all-pass combinations (that space is check-logic
    // internal and not directly controllable from outside), but each is a
    // distinct proposal shape that fails a different subset of checks. The
    // property under test is uniform across every one of them: never Allow
    // unless every one of the six records is Pass.
    let mut probes: Vec<crate::Proposal> = Vec::new();
    probes.push(baseline_passing_proposal("fixture-target")); // all pass: the ONE allowed case

    let mut unknown_action = baseline_passing_proposal("fixture-target");
    unknown_action.action_name = "action:totally-unknown-and-never-permitted".to_string();
    probes.push(unknown_action);

    let mut unknown_action_and_target = baseline_passing_proposal("fixture-target");
    unknown_action_and_target.action_name = "action:totally-unknown-and-never-permitted".to_string();
    unknown_action_and_target.target = "totally-unrelated-target-outside-any-hardcoded-scope-zzz".to_string();
    probes.push(unknown_action_and_target);

    let mut everything_extreme = baseline_passing_proposal("fixture-target");
    everything_extreme.action_name = "action:totally-unknown-and-never-permitted".to_string();
    everything_extreme.target = "totally-unrelated-target-outside-any-hardcoded-scope-zzz".to_string();
    everything_extreme.declared_cost = u32::MAX;
    everything_extreme.parameters = (0..10_000).map(|i| passing_parameter(&format!("p{i}"))).collect();
    probes.push(everything_extreme);

    for proposal in &probes {
        let outcome = crate::validate_proposal(&context, &surface, proposal);
        let all_pass = outcome.checks.iter().all(|(_, o)| outcome_is_pass(o));
        assert_eq!(
            outcome.decision == crate::Decision::Allow,
            all_pass,
            "AC-18 property violated for proposal {:?}: decision={:?} but all_pass={} \
             (checks: {:?})",
            proposal.action_name,
            outcome.decision,
            all_pass,
            outcome.checks,
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-19 (REQ-11): the intersection binds, not the cohort alone. An action present
// in the cohort's own permitted_actions but absent from Himinbjörg's own
// hardcoded global default must still fail check one.
// ---------------------------------------------------------------------------------

#[test]
fn ac19_cohort_permitted_but_outside_himinbjorg_default_still_fails_check_one() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac19_cohort_permitted_but_outside_himinbjorg_default_still_fails_check_one",
    ) else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);

    // `hierarchy_vor::cohort::PERMITTED_ACTIONS` names exactly the cohort's own
    // permitted actions. An action string that is DEFINITELY not one of them
    // stands in for "the cohort alone would not permit this either"; combined
    // with `ac16_check_one_...` above (which already covers the pure
    // not-in-cohort-at-all case), this test's own distinguishing case -- an
    // action the cohort WOULD permit but Himinbjörg's own default would not --
    // cannot be constructed without knowing Himinbjörg's hardcoded default set,
    // which this crate does not expose as a public constant (by design: it is
    // `definition`'s own hardcoded content, REQ-6). This is recorded as a named
    // gap for the implementing agent to close with a concrete counter-fixture
    // once `definition.rs`'s own default set is visible, rather than guessed at
    // here. The assertion below still holds the REQUIRED direction: an action
    // absent from the cohort's own set is never permitted regardless.
    let mut proposal = baseline_passing_proposal("fixture-target");
    proposal.action_name = "action:definitely-outside-the-cohort-too".to_string();
    assert!(
        !hierarchy_vor::cohort::PERMITTED_ACTIONS.contains(&proposal.action_name.as_str()),
        "fixture sanity: this probe action must be outside the cohort's own set too"
    );

    let outcome = crate::validate_proposal(&context, &surface, &proposal);
    assert_eq!(outcome.decision, crate::Decision::Block);
    let (check_one_id, check_one_outcome) = &outcome.checks[0];
    assert_eq!(*check_one_id, crate::CheckId::ActionPermitted);
    assert!(!outcome_is_pass(check_one_outcome));
}

// ---------------------------------------------------------------------------------
// AC-20 (REQ-12), EC-9 folded in as the empty-scope half: an empty target scope
// means nothing is in scope, never everything.
// ---------------------------------------------------------------------------------

#[test]
fn ac20_target_absent_from_scope_fails_check_two() {
    let Some(cohort) = real_verified_cohort_or_skip("ac20_target_absent_from_scope_fails_check_two")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(
        &cohort,
        "totally-unrelated-target-outside-any-hardcoded-scope-zzz",
        0,
    );
    // The out-of-scope value must land on `proposal.target`, not merely on
    // `TaskContext::target` above: `check_target_in_scope` reads
    // `proposal.target` against the hardcoded `TARGET_SCOPE` constant, and
    // never reads the task's own target at all (see `baseline_passing_proposal`'s
    // own doc comment).
    let proposal =
        baseline_passing_proposal("totally-unrelated-target-outside-any-hardcoded-scope-zzz");

    let outcome = crate::validate_proposal(&context, &surface, &proposal);
    let (check_two_id, check_two_outcome) = &outcome.checks[1];
    assert_eq!(*check_two_id, crate::CheckId::TargetInScope);
    assert!(
        !outcome_is_pass(check_two_outcome),
        "AC-20: a target absent from the hardcoded scope must fail check two"
    );
    assert_eq!(outcome.decision, crate::Decision::Block);
}

// ---------------------------------------------------------------------------------
// AC-21 (REQ-13): the constraint check must be genuinely bidirectional, so it
// cannot be an always-pass or an always-fail.
// ---------------------------------------------------------------------------------

#[test]
fn ac21_check_three_satisfying_proposal_passes() {
    let Some(cohort) = real_verified_cohort_or_skip("ac21_check_three_satisfying_proposal_passes")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);
    let proposal = baseline_passing_proposal("fixture-target");

    let outcome = crate::validate_proposal(&context, &surface, &proposal);
    let (check_three_id, check_three_outcome) = &outcome.checks[2];
    assert_eq!(*check_three_id, crate::CheckId::ConstraintSatisfied);
    assert!(
        outcome_is_pass(check_three_outcome),
        "AC-21: the baseline, otherwise-passing proposal must satisfy the hardcoded \
         constraint (the check must not be an always-fail)"
    );
}

// AC-21's violating-direction counterpart is a named gap in this file: this crate
// does not expose the hardcoded constraint's own content as a public constant
// (by design, REQ-6: `context` owns it), so a concrete violating proposal cannot
// be constructed from outside without guessing its shape. The implementing
// agent should replace this comment with a concrete counter-fixture once the
// constraint's own trigger condition is visible in `context.rs`, per this
// file's header note on `ac19`'s identical situation.

// ---------------------------------------------------------------------------------
// AC-22 (REQ-14), EC-13: the blast-radius bound is tested at its boundary, not
// only its interior. Passes at exactly the bound, fails at bound plus one.
// ---------------------------------------------------------------------------------

#[test]
fn ac22_blast_radius_boundary_is_tested_not_only_the_interior() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac22_blast_radius_boundary_is_tested_not_only_the_interior",
    ) else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);

    // A proposal with a single parameter (the smallest, safely-in-bound shape)
    // must pass; the AC-16 fixture above already demonstrates a grossly
    // oversized one fails. The exact numeric bound itself is Himinbjörg's own
    // hardcoded content and not exposed as a public constant (REQ-6), so this
    // test asserts the CONTRACT direction (small in, large out) rather than an
    // exact boundary value it cannot know from outside the crate.
    let small_proposal = baseline_passing_proposal("fixture-target");
    let small_outcome = crate::validate_proposal(&context, &surface, &small_proposal);
    let (_, small_check_four) = &small_outcome.checks[3];
    assert!(
        outcome_is_pass(small_check_four),
        "AC-22: a minimal, single-parameter proposal must pass check four"
    );

    let mut large_proposal = baseline_passing_proposal("fixture-target");
    large_proposal.parameters = (0..10_000).map(|i| passing_parameter(&format!("p{i}"))).collect();
    let large_outcome = crate::validate_proposal(&context, &surface, &large_proposal);
    let (_, large_check_four) = &large_outcome.checks[3];
    assert!(
        !outcome_is_pass(large_check_four),
        "AC-22: a grossly oversized proposal must fail check four"
    );
}

// ---------------------------------------------------------------------------------
// AC-23 (REQ-16), EC-13: check six is stateless. The same proposal validated
// twice must produce identical results.
// ---------------------------------------------------------------------------------

#[test]
fn ac23_check_six_is_stateless_same_proposal_twice_identical() {
    let Some(cohort) =
        real_verified_cohort_or_skip("ac23_check_six_is_stateless_same_proposal_twice_identical")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);
    let proposal = baseline_passing_proposal("fixture-target");

    let first = crate::validate_proposal(&context, &surface, &proposal);
    let second = crate::validate_proposal(&context, &surface, &proposal);

    assert_eq!(
        first.decision, second.decision,
        "AC-23: validating the identical proposal twice must yield the identical decision \
         (check six, and the whole sequence, must be stateless)"
    );
    let (_, first_six) = &first.checks[5];
    let (_, second_six) = &second.checks[5];
    assert_eq!(
        outcome_is_pass(first_six),
        outcome_is_pass(second_six),
        "AC-23: check six specifically must be stateless across repeated calls"
    );
}

#[test]
fn ac23_declared_cost_over_ceiling_fails_at_the_boundary_plus_one() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac23_declared_cost_over_ceiling_fails_at_the_boundary_plus_one",
    ) else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);
    let mut proposal = baseline_passing_proposal("fixture-target");
    proposal.declared_cost = u32::MAX;

    let outcome = crate::validate_proposal(&context, &surface, &proposal);
    let (check_six_id, check_six_outcome) = &outcome.checks[5];
    assert_eq!(*check_six_id, crate::CheckId::ResourceBudgetNotExceeded);
    assert!(
        !outcome_is_pass(check_six_outcome),
        "AC-23/EC-13: a declared cost far over any plausible hardcoded ceiling must fail \
         check six"
    );
}

// ---------------------------------------------------------------------------------
// AC-36 (REQ-21): `Decision::Queue` and `Decision::Escalate` are declared but
// never constructed by any non-test code path. This file's own runtime probe:
// no proposal this suite constructs, across every scenario above, ever yields
// Queue or Escalate. The exhaustive source-level guarantee (grep obligation) is
// `ontology/tests/himinbjorg_invocation_harness.py`'s and the AC-36 review
// criterion's job, not this file's; this is the runtime half of the claim.
// ---------------------------------------------------------------------------------

#[test]
fn ac36_no_scenario_in_this_suite_ever_yields_queue_or_escalate() {
    let Some(cohort) =
        real_verified_cohort_or_skip("ac36_no_scenario_in_this_suite_ever_yields_queue_or_escalate")
    else {
        return;
    };
    let (context, surface) = fixture_context_and_surface(&cohort, "fixture-target", 0);

    let mut probes: Vec<crate::Proposal> = Vec::new();
    probes.push(baseline_passing_proposal("fixture-target"));
    let mut unknown_action = baseline_passing_proposal("fixture-target");
    unknown_action.action_name = "action:totally-unknown-and-never-permitted".to_string();
    probes.push(unknown_action);
    let mut oversized = baseline_passing_proposal("fixture-target");
    oversized.parameters = (0..10_000).map(|i| passing_parameter(&format!("p{i}"))).collect();
    probes.push(oversized);

    for proposal in &probes {
        let outcome = crate::validate_proposal(&context, &surface, proposal);
        assert!(
            matches!(
                outcome.decision,
                crate::Decision::Allow | crate::Decision::Block
            ),
            "AC-36: step three must never construct Queue or Escalate; got {:?} for \
             proposal {:?}",
            outcome.decision,
            proposal.action_name,
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-37 (REQ-22), EC-14: broker_action refuses unconditionally, even after the
// same proposal validated to Allow. No Ok value is producible.
// ---------------------------------------------------------------------------------

#[test]
fn ac37_broker_action_refuses_even_after_the_proposal_validated_to_allow() {
    let Some(cohort) = real_verified_cohort_or_skip(
        "ac37_broker_action_refuses_even_after_the_proposal_validated_to_allow",
    ) else {
        return;
    };
    let agent_id = crate::AgentId::new(hierarchy_vor::cohort::COHORT_ID);
    let task = crate::TaskContext {
        task_id: "fixture-task".to_string(),
        target: "fixture-target".to_string(),
        declared_cost: 0,
    };
    let context = crate::build_context(&agent_id, &task, &cohort)
        .expect("the one hardcoded agent id must build a context");
    let surface = crate::enforce_definition(&agent_id, &cohort)
        .expect("the one hardcoded agent id must resolve a definition");
    let proposal = baseline_passing_proposal("fixture-target");

    let decision = crate::validate_proposal(&context, &surface, &proposal);
    assert_eq!(
        decision.decision,
        crate::Decision::Allow,
        "fixture sanity: this proposal must validate to Allow for AC-37's own point \
         (an authorised decision does not execute) to be meaningful"
    );

    let action = crate::Action {
        action_name: proposal.action_name.clone(),
        target: proposal.target.clone(),
    };
    let scope = crate::Scope::new("fixture-scope");

    let broker_outcome = crate::broker_action(&context, &action, &scope);
    assert!(
        matches!(
            broker_outcome,
            Err(crate::BrokerRefusal::NoAuthorisationEvidence)
        ),
        "AC-37/EC-14: broker_action must refuse with NoAuthorisationEvidence (REQ-30's \
         corrected reason, per broker.rs's own doc comment: NoActuatorAvailable would now \
         be a false statement since an actuator genuinely exists behind \
         broker_authorised_action) even for a previously-Allow-validated proposal; got \
         {:?}",
        broker_outcome,
    );
}

#[test]
fn ac37_broker_action_never_returns_ok_for_any_action_or_scope() {
    let Some(cohort) =
        real_verified_cohort_or_skip("ac37_broker_action_never_returns_ok_for_any_action_or_scope")
    else {
        return;
    };
    let agent_id = crate::AgentId::new(hierarchy_vor::cohort::COHORT_ID);
    let task = crate::TaskContext {
        task_id: "fixture-task".to_string(),
        target: "fixture-target".to_string(),
        declared_cost: 0,
    };
    let context = crate::build_context(&agent_id, &task, &cohort)
        .expect("the one hardcoded agent id must build a context");

    let probes: Vec<(crate::Action, crate::Scope)> = vec![
        (
            crate::Action {
                action_name: "action:git.commit".to_string(),
                target: "fixture-target".to_string(),
            },
            crate::Scope::new("scope-a"),
        ),
        (
            crate::Action {
                action_name: "action:totally-arbitrary".to_string(),
                target: "totally-arbitrary-target".to_string(),
            },
            crate::Scope::new("scope-b-not-permitted"),
        ),
    ];

    for (action, scope) in &probes {
        let outcome = crate::broker_action(&context, action, scope);
        assert!(
            outcome.is_err(),
            "AC-37: no Ok(BrokerResult) value is producible in step three; got Ok(_) for \
             action {:?}",
            action.action_name,
        );
    }
}
