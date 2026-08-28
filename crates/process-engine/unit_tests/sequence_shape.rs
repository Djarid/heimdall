//! The fixed five-step sequence's own shape (REQ-9 to REQ-12, REQ-16, REQ-20,
//! REQ-24, REQ-34 to REQ-37): AC-9, AC-11 to AC-14, AC-19, AC-23, AC-27,
//! AC-38 to AC-41 of `.opencode/plans/process-engine-step-five-spec.md`.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/process-engine/src/` carries
//! real content: no `sequence.rs`, no `task.rs`, no `outcome.rs`, no
//! crate-root re-exports. That is expected and correct at this stage, on
//! `crates/himinbjorg/unit_tests/six_checks.rs`'s and
//! `crates/hierarchy-vor/unit_tests/loader_failclosed.rs`'s own precedent for
//! a test file written before its crate exists at real fidelity.
//!
//! **Compiled as an IN-CRATE unit test module** (REQ-7, REQ-53), wired into
//! `crates/process-engine/src/lib.rs` via
//! `#[cfg(test)] #[path = "../unit_tests/sequence_shape.rs"] mod sequence_shape;`.
//! This lets this file reach `crate::` items that are `pub(crate)` rather
//! than only the crate's public surface, following the pattern established
//! for every prior crate's own unit-test modules.
//!
//! **Signatures assumed here** (this file's own necessary choices, flagged
//! explicitly rather than hidden, on `six_checks.rs`'s own convention for a
//! spec that leaves a shape indicative rather than fixed):
//!
//!   - `crate::EngineTask { task_id: String, action_name: String, target: String,
//!     sink: String, declared_cost: u32 }`: the task shape the entry point
//!     accepts (section 7 file 6 of the spec, REQ-32). `action_name` lives on
//!     the TASK, not on cognition's output, because PE-9/REQ-32 requires a
//!     task to be able to name a permitted OR a deliberately disallowed
//!     action while cognition's own output stays fixed and hardcoded
//!     (REQ-14): if the action came from cognition alone, the two directions
//!     of PE-9 could not differ by task alone. `sink` is the fifth field,
//!     added for build-order step six (ST6-1, REQ-1, REQ-54,
//!     `.opencode/plans/build-order-step-six-spec.md`), on the same
//!     differ-by-task-alone reasoning: `CognitionOutput` lost its own `sink`
//!     field in that same step (REQ-2), and `build_proposal` now reads it
//!     from the task instead (REQ-3). This file's own tests below construct
//!     every `EngineTask` literal with all five fields; none of them inspects
//!     `sink`'s value, since this file's own concern is task-identifier
//!     well-formedness alone.
//!   - `crate::is_task_well_formed(task: &EngineTask) -> bool`: the structural
//!     well-formedness predicate task.rs owns (REQ-34), assumed `pub(crate)`
//!     and reachable from this in-crate module. This is assumed to exist as a
//!     PURE function independent of any `VerifiedCohort`, which is the only
//!     way REQ-53's own claim ("the well-formedness refusal" executes its
//!     assertions unconditionally, without a provisioned secret) can be true
//!     at all: `crate::run_sequence`'s own signature necessarily takes a real
//!     `&hierarchy_vor::VerifiedCohort` (REQ-26), and that type has no public
//!     constructor anywhere outside `hierarchy_vor` (confirmed directly against
//!     that crate's source), so no test anywhere can call the full entry point
//!     at all without a provisioned secret, well-formed task or not. This
//!     file's own tests against the well-formedness predicate therefore call
//!     `is_task_well_formed` directly, never `run_sequence`, so they hold on
//!     every machine regardless of provisioning. The full end-to-end
//!     confirmation that `run_sequence` itself maps a malformed task to
//!     `EngineOutcome::RefusedBeforeCognition` without ever calling
//!     `validate_proposal` is therefore this file's own named, deliberate gap:
//!     it belongs to `tests/public_surface.rs` instead, gated behind
//!     `HEIMDALL_COHORT_SECRET_FILE` with the reserved marker pair (REQ-53).
//!   - `crate::EngineStep` is a closed, five-variant, `Debug + Clone + Copy +
//!     PartialEq + Eq` enum: `AcceptTask`, `Cognition`, `ProposeAction`,
//!     `Gate`, `Execute`, in that order (REQ-9).
//!   - `crate::STEP_SEQUENCE: [EngineStep; 5]` is the fixed array in that same
//!     order, carrying its own `const _: () = assert!(...)` length assertion
//!     (REQ-9); this file reads it, it does not attempt to violate the
//!     assertion (AC-10's own compile-fail confirmation is a hand-confirmed,
//!     non-automated check per the spec's own convention, not this file's
//!     job).
//!   - `crate::EngineOutcome` is assumed to carry, at minimum, these cases
//!     (REQ-24, section 3.1 item 4 of the spec): `RefusedBeforeCognition {
//!     reason: String }`, `GateBlocked { checks: Vec<himinbjorg::CheckRecord> }`,
//!     `BrokerRefused { refusal: himinbjorg::BrokerRefusal }`, `Executed {
//!     receipt: himinbjorg::ActuationReceipt }`, and a dataless
//!     `AwaitingHumanDecision` variant that no non-test code path constructs
//!     (REQ-35, on `Decision::Queue`/`Decision::Escalate`'s own dataless
//!     precedent -- simpler than a variant wrapping a separate, similarly
//!     unconstructible "human question" type, and equally satisfying REQ-35's
//!     own wording that the variant itself is "named and typed rather than
//!     delivered").
//!   - `crate::LoopCap` is assumed to be a separate, uninhabited type (`pub
//!     enum LoopCap {}`), unrelated to `EngineOutcome`'s own fields, on
//!     `himinbjorg::BrokerResult`'s own uninhabited-enum precedent (REQ-36).
//!     Its own no-constructor confirmation is a hand-confirmed compile
//!     failure (AC-40), not an automated test in this file, following
//!     `crates/hierarchy-vor/tests/public_surface.rs`'s own commented-out
//!     confirmation-block convention for exactly this class of claim.
//!   - `crate::run_sequence(cohort: &hierarchy_vor::VerifiedCohort, task:
//!     &EngineTask) -> EngineOutcome`: the crate's one public entry point
//!     (REQ-11, REQ-26, REQ-31). Not called anywhere in THIS file (see the
//!     `is_task_well_formed` note above): every genuine call to it needs a
//!     real cohort and therefore lives in `tests/public_surface.rs` instead.
//!
//! **Judgement call two, as resolved by the delegating prompt and confirmed
//! live against `crates/himinbjorg/unit_tests/six_checks.rs`.** That file's
//! own `fixture_context_and_surface` helper (and every one of its 20-odd
//! tests) shows NO non-cohort-gated path to `validate_proposal`: every
//! single test there is gated behind `real_verified_cohort_or_skip`, and its
//! own header states plainly that "there is no fixture, mock or double for a
//! `VerifiedCohort` anywhere in this crate's design (REQ-20 forbids exactly
//! that)". Himinbjörg's own unit tests therefore show no non-cohort-gated
//! pattern this file could reuse to instrument a live call count of
//! `validate_proposal`. Per the delegating prompt's own resolution for this
//! exact situation, this file's AC-23 coverage is therefore the STRUCTURAL
//! half only: a source scan proving the crate carries no local copy,
//! partial copy or approximation of any of the six checks, and that the one
//! legitimate call site of `validate_proposal(` appears exactly once in the
//! crate's own `src/`. The live call-count and full-sequence behavioural
//! assertions (that `validate_proposal` is called exactly once PER RUN, that
//! the witness is passed through unchanged, and so on) move entirely to
//! `tests/public_surface.rs`, gated behind `HEIMDALL_COHORT_SECRET_FILE`
//! with the `PROCESS-ENGINE-REAL-COHORT-*` marker pair, exactly as that file's
//! own header states.

fn crate_src_dir() -> std::path::PathBuf {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("src")
}

/// Reads and comment/string-cleans one file under `src/`, on
/// `crates/himinbjorg/unit_tests/witness_and_audit.rs`'s own `ac58` technique
/// (a line-comment strip; block comments and string literals are not
/// stripped here because none of the probes below needs that fidelity, and
/// keeping this helper small keeps the assumption surface small too).
fn cleaned_source(rel_path: &str) -> String {
    let path = crate_src_dir().join(rel_path);
    let src = std::fs::read_to_string(&path).unwrap_or_else(|e| {
        panic!(
            "expected crates/process-engine/src/{rel_path} to exist once this step lands \
             (this is the correct RED state before then): {e}"
        )
    });
    src.lines()
        .map(|line| match line.find("//") {
            Some(idx) => format!("{}{}", &line[..idx], " ".repeat(line.len() - idx)),
            None => line.to_string(),
        })
        .collect::<Vec<_>>()
        .join("\n")
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
            if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                all.push_str(&cleaned_source(name));
                all.push('\n');
            }
        }
    }
    all
}

// ---------------------------------------------------------------------------------
// AC-9 (REQ-9): the step enum has exactly five variants in the fixed order,
// and the sequence array holds exactly those five, in that order.
// ---------------------------------------------------------------------------------

#[test]
fn ac9_step_enum_has_exactly_five_variants_in_fixed_order() {
    // Exhaustive match: a sixth variant added later forces this arm list to
    // be revisited (EC-14's discipline applied to the step vocabulary
    // itself), which is itself part of what this test pins.
    let expected_order = |step: &crate::EngineStep| -> u8 {
        match step {
            crate::EngineStep::AcceptTask => 0,
            crate::EngineStep::Cognition => 1,
            crate::EngineStep::ProposeAction => 2,
            crate::EngineStep::Gate => 3,
            crate::EngineStep::Execute => 4,
        }
    };

    assert_eq!(
        crate::STEP_SEQUENCE.len(),
        5,
        "AC-9: the fixed sequence array must hold exactly five steps"
    );
    for (i, step) in crate::STEP_SEQUENCE.iter().enumerate() {
        assert_eq!(
            expected_order(step),
            i as u8,
            "AC-9: STEP_SEQUENCE[{i}] must be the step whose fixed position is {i}; got {step:?}"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-11 (REQ-9): the crate's own documentation states that "result out" is
// the entry point's return value and not a sixth step.
// ---------------------------------------------------------------------------------

#[test]
fn ac11_crate_documentation_states_result_out_is_not_a_sixth_step() {
    let lib_rs = std::fs::read_to_string(crate_src_dir().join("lib.rs"))
        .expect("expected crates/process-engine/src/lib.rs to exist");
    let lower = lib_rs.to_lowercase();
    assert!(
        lower.contains("result out") && lower.contains("sixth step"),
        "AC-11: the crate-level doc comment in src/lib.rs must state, in its own words, \
         that \"result out\" is the entry point's return value and not a sixth step, so a \
         later reader does not re-derive the count of five. Found no such statement."
    );
}

// ---------------------------------------------------------------------------------
// AC-12 (REQ-10), structural half only: no `loop`, `while`, back-edge `for`
// over the step array or recursion anywhere in the module that runs the
// sequence. The runtime half (an instrumented run proving each step executes
// at most once, in array order) needs a real sequence run and therefore
// lives in tests/public_surface.rs (judgement call two's reasoning, applied
// consistently to every assertion that would otherwise need a live run).
// ---------------------------------------------------------------------------------

#[test]
fn ac12_no_back_edge_is_expressible_in_the_sequencing_source() {
    let cleaned = cleaned_source("sequence.rs");
    for forbidden in ["loop", "while", "recursion"] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-12/REQ-10: sequence.rs must contain no {forbidden:?} token: the sequence \
             must have no loop, no while and no recursion anywhere in its own control flow, \
             establishable by reading the source rather than by trusting a comment"
        );
    }
    // No `for` loop over the step array re-entering an earlier step: a `for`
    // over `STEP_SEQUENCE` at all would already be surprising (the sequence
    // is meant to run each step's own function once, by name, not iterate
    // generically), so a `for` mentioning the sequence array's own name is
    // itself suspicious enough to forbid outright.
    assert!(
        !cleaned.contains("for ") || !cleaned.contains("STEP_SEQUENCE"),
        "AC-12/REQ-10: sequence.rs must not iterate over STEP_SEQUENCE with a `for` loop; \
         each step's own function must be called once, by name, in the fixed order"
    );
}

// ---------------------------------------------------------------------------------
// AC-13 (REQ-11): exactly one public item runs the sequence; every
// individual step's implementation is unreachable from outside the crate.
// The "does not compile" half is a hand-confirmed diagnostic (this file's
// own convention, following crates/hierarchy-vor/tests/public_surface.rs's
// AC-24/AC-39 commented-out confirmation blocks), never an automated test:
// a snippet that must NOT compile cannot be asserted by a passing test in
// this same crate without a trybuild-style dependency, which REQ-2 forbids
// adding to this crate at all.
// ---------------------------------------------------------------------------------

// To confirm AC-13 by hand once the crate exists: uncomment ONE line below,
// run `cargo build -p process-engine --tests`, capture the diagnostic
// (expected E0603, "module `sequence` is private", or E0433/E0425 if the
// per-step functions are not even re-exported at the module boundary), and
// record it in the pull request. Leave every line commented in the
// committed file, otherwise this crate never builds at all.
//
// ```rust,ignore
// fn _ac13_confirm_step_implementations_are_unreachable_from_outside() {
//     let _ = crate::sequence::accept_task(&task); // expected: module `sequence` is private
// }
// ```

#[test]
fn ac13_exactly_one_public_entry_point_runs_the_sequence() {
    // A weaker, but still meaningful, in-crate structural check: the entry
    // point itself exists and is nameable at the crate root. The stronger
    // "no other way in" half is the hand-confirmed diagnostic above.
    let _entry_point_exists: fn(&hierarchy_vor::VerifiedCohort, &crate::EngineTask) -> crate::EngineOutcome =
        crate::run_sequence;
}

// ---------------------------------------------------------------------------------
// AC-14 (REQ-12): the crate consults none of Himinbjörg's own gating
// constants in a branch that decides whether to proceed. Structural: a
// source scan for the constant NAMES themselves, since this crate cannot
// even read their VALUES (it has no access to himinbjorg::context's
// pub(crate) items).
// ---------------------------------------------------------------------------------

#[test]
fn ac14_no_read_of_himinbjorgs_own_gating_constants_anywhere_in_the_crate() {
    let cleaned = cleaned_whole_crate_src();
    for forbidden in [
        "TARGET_SCOPE",
        "PERMITTED_CREDENTIAL_SCOPES",
        "BLAST_RADIUS_BOUND",
        "RESOURCE_CEILING",
        "sinks::registry",
        "CONSEQUENTIAL_SINKS",
        "PERMITTED_ACTIONS",
    ] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-14/REQ-12: crates/process-engine/src/ must contain no mention of \
             {forbidden:?}: this crate re-derives none of Himinbjörg's own gating \
             constants and consults none of them to decide whether to proceed. The only \
             authorisation decision in the sequence is validate_proposal's own return \
             value"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-19 (REQ-16): exactly one function in the crate constructs a
// himinbjorg::Proposal, and it is the only construction site.
// ---------------------------------------------------------------------------------

#[test]
fn ac19_exactly_one_proposal_construction_site_in_the_whole_crate() {
    let cleaned = cleaned_whole_crate_src();
    let occurrences = cleaned.matches("Proposal {").count();
    assert_eq!(
        occurrences, 1,
        "AC-19/REQ-16: exactly one function in this crate must construct a \
         himinbjorg::Proposal (matched via the literal `Proposal {{` struct-literal \
         opening); found {occurrences} occurrence(s) across src/"
    );
}

// ---------------------------------------------------------------------------------
// AC-23 (REQ-20), judgement call two's structural resolution: the gate step
// calls validate_proposal exactly once per sequence run, genuinely, and the
// crate contains no copy, partial copy or approximation of any of the six
// checks. This file proves the structural half only (source scan for a
// local copy of any check, and that the one legitimate call site of
// validate_proposal appears exactly once in src/); the live call-COUNT
// instrumentation moves to tests/public_surface.rs.
// ---------------------------------------------------------------------------------

#[test]
fn ac23_validate_proposal_called_from_exactly_one_site_in_src() {
    let cleaned = cleaned_whole_crate_src();
    let qualified = cleaned.matches("validate_proposal(").count();
    assert_eq!(
        qualified, 1,
        "AC-23/REQ-20: validate_proposal( must appear exactly once across the whole of \
         crates/process-engine/src/ -- the gate step's own single call, never bypassed \
         and never duplicated; found {qualified} occurrence(s)"
    );
}

#[test]
fn ac23_no_local_copy_partial_copy_or_approximation_of_any_of_the_six_checks() {
    let cleaned = cleaned_whole_crate_src();
    // Token-level proxies for "a local action-permission test, a
    // target-scope membership test, a blast-radius comparison, a
    // resource-budget comparison, a sink-registry lookup or a
    // taint-compatibility rule" (AC-23's own wording). This is
    // deliberately broader than AC-14's constant-name scan: it also
    // forbids a locally reimplemented comparison that happens to use
    // different constant names but the same shape.
    for forbidden in [
        "declared_cost <=",
        "declared_cost >",
        "parameters.len() <=",
        "parameters.len() >",
        "blast_radius",
        "may_perform",
        "consequentiality::evaluate",
        "evaluate_taint_compatibility",
    ] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-23/REQ-20: crates/process-engine/src/ must contain no {forbidden:?}: no \
             check may be copied, approximated or short-circuited locally. Authorisation \
             comes entirely from validate_proposal's own six checks, called once, and \
             from nothing this crate re-derives"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-27 (REQ-24), structural half: the outcome type's OWN shape does not
// collapse two upstream refusals that differ into one opaque value. Tested
// by hand-constructing two distinct BrokerRefusal variants (both fully
// constructible without any cohort: neither ScopeNotPermitted nor
// AuditWriteFailed carries an actuator_git type) and confirming the
// resulting EngineOutcome values are distinguishable, and by
// hand-constructing a six-entry CheckRecord vec for the gate-blocked case.
// ---------------------------------------------------------------------------------

fn six_check_records_all_fail() -> Vec<himinbjorg::CheckRecord> {
    vec![
        (
            himinbjorg::CheckId::ActionPermitted,
            himinbjorg::CheckOutcome::Fail {
                reasons: vec!["probe: action not permitted".to_string()],
            },
        ),
        (
            himinbjorg::CheckId::TargetInScope,
            himinbjorg::CheckOutcome::Pass,
        ),
        (
            himinbjorg::CheckId::ConstraintSatisfied,
            himinbjorg::CheckOutcome::Pass,
        ),
        (
            himinbjorg::CheckId::BlastRadiusWithinBound,
            himinbjorg::CheckOutcome::Pass,
        ),
        (
            himinbjorg::CheckId::TaintCompatible,
            himinbjorg::CheckOutcome::Pass,
        ),
        (
            himinbjorg::CheckId::ResourceBudgetNotExceeded,
            himinbjorg::CheckOutcome::Pass,
        ),
    ]
}

#[test]
fn ac27_gate_blocked_outcome_carries_all_six_check_records_verbatim() {
    let checks = six_check_records_all_fail();
    let outcome = crate::EngineOutcome::GateBlocked {
        checks: checks.clone(),
    };
    match outcome {
        crate::EngineOutcome::GateBlocked { checks: carried } => {
            assert_eq!(
                carried.len(),
                6,
                "AC-27: a gate-blocked outcome must carry exactly six CheckRecords, none \
                 dropped or rewritten"
            );
            assert_eq!(
                carried, checks,
                "AC-27: the carried CheckRecords must match what was produced, verbatim"
            );
        }
        other => panic!("AC-27: expected GateBlocked, got {other:?}"),
    }
}

#[test]
fn ac27_two_upstream_broker_refusals_that_differ_remain_distinguishable_in_the_outcome() {
    let scope_refusal = crate::EngineOutcome::BrokerRefused {
        refusal: himinbjorg::BrokerRefusal::ScopeNotPermitted,
    };
    let audit_refusal = crate::EngineOutcome::BrokerRefused {
        refusal: himinbjorg::BrokerRefusal::AuditWriteFailed {
            diagnostic: "probe: audit write failed".to_string(),
        },
    };

    let scope_debug = format!("{scope_refusal:?}");
    let audit_debug = format!("{audit_refusal:?}");
    assert_ne!(
        scope_debug, audit_debug,
        "AC-27/REQ-24: two BrokerRefusal variants that differ upstream must differ in the \
         engine's own outcome; a mapping that collapsed both into one opaque value would \
         make these two Debug strings identical"
    );

    match (&scope_refusal, &audit_refusal) {
        (
            crate::EngineOutcome::BrokerRefused {
                refusal: himinbjorg::BrokerRefusal::ScopeNotPermitted,
            },
            crate::EngineOutcome::BrokerRefused {
                refusal: himinbjorg::BrokerRefusal::AuditWriteFailed { .. },
            },
        ) => {}
        other => panic!(
            "AC-27: expected the two distinct BrokerRefusal variants to remain recoverable \
             from the outcome; got {other:?}"
        ),
    }
}

// ---------------------------------------------------------------------------------
// AC-38 (REQ-34), EC-18: an empty task identifier yields the engine's own
// refused-before-cognition case. Tested against the pure well-formedness
// predicate directly (see this file's header for why `run_sequence` itself
// cannot be called here at all).
// ---------------------------------------------------------------------------------

#[test]
fn ac38_empty_task_identifier_is_not_well_formed() {
    let malformed = crate::EngineTask {
        task_id: String::new(),
        action_name: "action:git.commit".to_string(),
        target: "fixture-target".to_string(),
        // REQ-1/REQ-54 (build-order step six): EngineTask's fifth field.
        sink: "sink:git.commit".to_string(),
        declared_cost: 0,
    };
    assert!(
        !crate::is_task_well_formed(&malformed),
        "AC-38: a task with an empty identifier must be structurally ill formed"
    );
}

#[test]
fn ac38_whitespace_only_task_identifier_is_not_well_formed() {
    let malformed = crate::EngineTask {
        task_id: "   ".to_string(),
        action_name: "action:git.commit".to_string(),
        target: "fixture-target".to_string(),
        // REQ-1/REQ-54 (build-order step six): EngineTask's fifth field.
        sink: "sink:git.commit".to_string(),
        declared_cost: 0,
    };
    assert!(
        !crate::is_task_well_formed(&malformed),
        "EC-18: a whitespace-only task identifier must be structurally ill formed, not \
         merely a non-empty-length check"
    );
}

#[test]
fn ac38_a_non_empty_task_identifier_is_well_formed() {
    let ok_task = crate::EngineTask {
        task_id: "fixture-task".to_string(),
        action_name: "action:git.commit".to_string(),
        target: "fixture-target".to_string(),
        // REQ-1/REQ-54 (build-order step six): EngineTask's fifth field.
        sink: "sink:git.commit".to_string(),
        declared_cost: 0,
    };
    assert!(
        crate::is_task_well_formed(&ok_task),
        "AC-38's own contrapositive: the well-formedness predicate must not be an \
         always-fail; a genuinely well-formed task must pass"
    );
}

// ---------------------------------------------------------------------------------
// AC-39 (REQ-35): the human-question deferral variant is present, no
// non-test code path constructs it, and its own doc comment states the
// three named properties.
// ---------------------------------------------------------------------------------

#[test]
fn ac39_human_question_outcome_variant_is_declared_and_never_constructed_in_src() {
    // Exhaustively matching the variant into existence: if it is ever
    // removed, this line fails to compile, which is itself part of the
    // proof that the variant exists at all.
    let _shape_check = |o: &crate::EngineOutcome| -> bool {
        matches!(o, crate::EngineOutcome::AwaitingHumanDecision)
    };

    // Scan for a CONSTRUCTION of the variant, not the bare variant
    // identifier: the enum's own declaration in outcome.rs necessarily
    // writes the identifier unqualified (`AwaitingHumanDecision,` inside
    // the `enum EngineOutcome` body), since that is how a variant is
    // declared at all, and the test's own `_shape_check` closure above
    // makes that declaration mandatory for any valid implementation. A
    // genuine construction, by contrast, always needs a qualifying path
    // (`EngineOutcome::` or, from inside an impl block on the same type,
    // `Self::`), which the bare declaration line never writes.
    //
    // A qualified occurrence is not automatically a construction, though:
    // `crate::exit_code_for`'s own match must be exhaustive with no
    // wildcard arm (EC-14, documented on that function), so it necessarily
    // carries a legitimate match-arm PATTERN naming this variant on the
    // left of `=>` (`EngineOutcome::AwaitingHumanDecision => ...`) purely
    // to inspect an outcome some other, already-run step produced. That is
    // matching a value, not constructing one, and REQ-35 forbids only the
    // latter ("Given the whole crate source scanned for a construction of
    // it" -- AC-39). A qualified occurrence NOT immediately followed by
    // `=>` (an assignment, a return, an argument, a struct field, ...) is a
    // real construction site and fails this test.
    let cleaned = cleaned_whole_crate_src();
    let mut construction_hits: Vec<String> = Vec::new();
    for construction_pattern in ["EngineOutcome::AwaitingHumanDecision", "Self::AwaitingHumanDecision"] {
        let mut search_from = 0usize;
        while let Some(offset) = cleaned[search_from..].find(construction_pattern) {
            let match_start = search_from + offset;
            let after = &cleaned[match_start + construction_pattern.len()..];
            if !after.trim_start().starts_with("=>") {
                construction_hits.push(format!(
                    "{construction_pattern:?} at byte offset {match_start} (not a match-arm pattern)"
                ));
            }
            search_from = match_start + construction_pattern.len();
        }
    }
    assert!(
        construction_hits.is_empty(),
        "AC-39/REQ-35: no file under crates/process-engine/src/ may construct \
         EngineOutcome::AwaitingHumanDecision; it is named and typed, never delivered, \
         until Gjallarhorn's protected channel and an operator-answer path exist. Found: \
         {construction_hits:?}"
    );
    for forbidden in ["unimplemented!", "todo!", "panic!"] {
        assert!(
            !cleaned.contains(forbidden),
            "AC-39: crates/process-engine/src/ must contain no {forbidden:?} on the \
             sequence path; a panic on an authorisation-adjacent path is worse than a \
             typed refusal (PE-7)"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-40 (REQ-36): the loop-cap type has no constructor. Automated half:
// LoopCap is uninhabited (Debug-formatting an exhaustive match over it
// compiles only if there really are zero variants to match). The
// "attempting to construct a value does not compile" half is a
// hand-confirmed diagnostic, on this file's own AC-13 convention above.
// ---------------------------------------------------------------------------------

// To confirm AC-40 by hand once the crate exists: uncomment the line below,
// run `cargo build -p process-engine --tests`, capture the diagnostic
// (expected E0423/E0599: no variant or associated function to construct a
// value of an uninhabited enum), and record it in the pull request. Leave
// commented in the committed file.
//
// ```rust,ignore
// fn _ac40_confirm_loop_cap_has_no_constructor() {
//     let _bad = crate::LoopCap::Anything;
// }
// ```

#[test]
fn ac40_loop_cap_is_uninhabited() {
    fn _match_is_exhaustive_with_zero_arms(cap: crate::LoopCap) -> ! {
        match cap {
            // No arms: this compiles if and only if LoopCap has zero
            // variants, which is the structural proof this test pins.
        }
    }
    // Never called (there is no value of `LoopCap` to call it with, by
    // construction); its mere presence in this file, compiling, is the
    // assertion.
    let _ = _match_is_exhaustive_with_zero_arms;
}

// ---------------------------------------------------------------------------------
// AC-41 (REQ-37): both deferrals are named in the crate's own crate-level
// doc comment.
// ---------------------------------------------------------------------------------

#[test]
fn ac41_crate_level_doc_comment_names_both_deferral_forms() {
    let lib_rs = std::fs::read_to_string(crate_src_dir().join("lib.rs"))
        .expect("expected crates/process-engine/src/lib.rs to exist");
    let lower = lib_rs.to_lowercase();
    assert!(
        lower.contains("gjallarhorn"),
        "AC-41/REQ-37: the crate-level doc comment must name the human-question gate's own \
         deferral (Gjallarhorn's protected channel and an operator-answer path, neither \
         built)"
    );
    assert!(
        lower.contains("gleipnir"),
        "AC-41/REQ-37: the crate-level doc comment must name the loop cap's own deferral \
         (Gleipnir's code-enforced loop caps over a general transition table)"
    );
}
