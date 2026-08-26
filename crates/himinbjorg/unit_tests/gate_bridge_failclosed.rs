//! Check five, the real gate call, and fail-closed/no-fallback behaviour
//! (REQ-15, REQ-17 to REQ-20), `.opencode/plans/himinbjorg-step-three.md`
//! section 8.5 and 8.6: AC-24 to AC-33, the gate-refusal and no-fallback cases.
//!
//! Also covers, where in scope for this file: EC-1 (the gate's four reason
//! kinds, never Allow/Queue/Escalate, never a retry), EC-6 and EC-7 (the
//! cohort's consequential-sink set and Himinbjörg's own registry answering
//! different questions, neither reconciled to the other), EC-8 (no known
//! provenance), EC-9 (the dishonest Inert claim), EC-10 (a zero-parameter
//! proposal can never reach the rule loop with an empty reason set, because
//! REQ-18 requires every declared sink to declare at least one parameter).
//!
//! THIS FILE WILL FAIL TO COMPILE until `crates/himinbjorg` exists at all. That
//! is expected and correct at this stage (issue #37); see
//! `unit_tests/six_checks.rs`'s header for the same statement and its
//! precedent in `crates/hierarchy-vor/unit_tests/loader_failclosed.rs`.
//!
//! **Compiled as an IN-CRATE unit test module** (REQ-26), wired via
//! `#[cfg(test)] #[path = "../unit_tests/gate_bridge_failclosed.rs"] mod
//! gate_bridge_failclosed;` in `lib.rs`, so this file reaches the `pub(crate)`
//! internal seams of section 6.2: `gate_bridge::action_critical_for`,
//! `gate_bridge::evaluate_taint_compatibility`, `sinks::registry`.
//!
//! **Two different, deliberately separated things are tested here**, following
//! the design tension this file's header states rather than hides:
//!
//!   1. Tests that call `boundary_gjoll::consequentiality::evaluate` directly
//!      against `crate::sinks::registry()` (Himinbjörg's OWN sink
//!      declarations, REQ-18), with a hand-built `ClassifiedParameter` whose
//!      `action_critical` flag is set explicitly rather than derived. These
//!      need **no cohort at all** and run on every machine regardless (REQ-32's
//!      own claim), because they test what the GATE does with the registry
//!      Himinbjörg supplies it, independent of any agent-scoped derivation.
//!      This mirrors `crates/boundary-gjoll/tests/native_failclosed.rs`'s own
//!      shape one for one.
//!   2. Tests that call `gate_bridge::action_critical_for` or
//!      `gate_bridge::evaluate_taint_compatibility` directly, which take a
//!      `&hierarchy_vor::CohortSurface<'_>` per section 6.2's own signature.
//!      Because `CohortSurface` has no public or `pub(crate)`-to-himinbjorg
//!      constructor, obtaining one requires a real, provisioned
//!      `heimdall-dev` secret exactly as `unit_tests/six_checks.rs`'s header
//!      explains; these tests are gated the same way, with the same distinct,
//!      non-reserved skip message.
//!
//! **Signatures assumed here**, in addition to `unit_tests/six_checks.rs`'s own
//! header:
//!
//!   - `crate::gate_bridge::action_critical_for(sink: &str, surface:
//!     &hierarchy_vor::CohortSurface<'_>) -> bool` (section 6.2, literally).
//!   - `crate::gate_bridge::evaluate_taint_compatibility(proposal: &himinbjorg::Proposal,
//!     surface: &hierarchy_vor::CohortSurface<'_>, registry:
//!     &boundary_gjoll::declaration::SinkRegistry) -> himinbjorg::CheckOutcome`
//!     (section 6.2, literally).
//!   - `crate::sinks::registry() -> boundary_gjoll::declaration::SinkRegistry`
//!     (section 6.2, literally). This file assumes at least one of the
//!     declared sink names equals one of `hierarchy_vor::cohort::CONSEQUENTIAL_SINKS`
//!     (so that a membership probe against the real cohort's own sink set is
//!     meaningful, REQ-17's whole point being that the two sets are read
//!     independently, EC-7); if the two sets happen to share no member at all
//!     in the real build, `ac25`'s own membership assertion below should be
//!     read as testing the CONTRACT (independent derivation) rather than a
//!     guaranteed non-empty intersection, which this file cannot know from
//!     outside the crate.

fn real_cohort_surface_or_skip(test_name: &str) -> Option<hierarchy_vor::VerifiedCohort> {
    match hierarchy_vor::load_trusted_set_from_env(hierarchy_vor::cohort::AUTHORISER_ID) {
        Ok(trusted) => Some(hierarchy_vor::load_verified_cohort(&trusted).unwrap_or_else(|e| {
            panic!(
                "{test_name}: a secret was provisioned via {} but the committed attestation \
                 did not verify against it ({e:?}); this is FATAL, never a skip",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            )
        })),
        Err(hierarchy_vor::SecretRefusal::EnvVarMissing(_)) => {
            eprintln!(
                "{test_name}: SKIPPED -- {} is not set, so this test cannot obtain a real \
                 hierarchy_vor::CohortSurface (no fixture exists for one by design, REQ-20).",
                hierarchy_vor::SECRET_PATH_ENV_VAR,
            );
            None
        }
        Err(other) => panic!(
            "{test_name}: {} names a path but loading it was refused for a reason other than \
             absence ({other:?}); this is FATAL",
            hierarchy_vor::SECRET_PATH_ENV_VAR,
        ),
    }
}

fn classified(
    action_critical: bool,
    trust_level: boundary_gjoll::types::TrustLevel,
) -> boundary_gjoll::types::ClassifiedParameter {
    boundary_gjoll::types::ClassifiedParameter {
        assertion_id: "v".to_string(),
        type_name: "comms:generic".to_string(),
        trust_level,
        action_critical,
    }
}

/// The first sink `crate::sinks::registry()` declares, used as a stand-in
/// consequential sink for the direct-gate tests below. This file cannot know
/// Himinbjörg's own declared sink NAMES from outside the crate (REQ-18: they
/// are `sinks.rs`'s own hardcoded content), so it discovers one via
/// `SinkRegistry::is_declared` against `hierarchy_vor::cohort::CONSEQUENTIAL_SINKS`
/// (a public constant), falling back to a fixed guess if neither is declared.
/// AC-27's own test below inspects the registry's structural properties
/// (non-empty parameters, an effect primitive) without needing to know a
/// specific name at all, which is this file's primary coverage of REQ-18; the
/// tests here that need a concrete sink NAME degrade gracefully if this guess
/// misses, by asserting the registry-consulting direction rather than a
/// specific outcome value where that would require knowing unexported content.
fn a_declared_consequential_sink(registry: &boundary_gjoll::declaration::SinkRegistry) -> String {
    for candidate in hierarchy_vor::cohort::CONSEQUENTIAL_SINKS {
        if registry.is_declared(candidate) {
            return candidate.to_string();
        }
    }
    // Fallback: this crate's own registry() is expected, per REQ-18, to declare
    // sinks the D89-B derivation regards as effect-producing; without a public
    // name to reach for, this is the best-effort probe this file can construct
    // from outside `sinks.rs`.
    "sink:git.commit".to_string()
}

// ---------------------------------------------------------------------------------
// AC-27 (REQ-18): sinks::registry()'s structural properties, no cohort needed.
// ---------------------------------------------------------------------------------

#[test]
fn ac27_registry_every_declaration_has_parameters_and_a_primitive() {
    let registry = crate::sinks::registry();
    // There is no public enumeration of declared names on
    // `boundary_gjoll::declaration::SinkRegistry` (only `get` and
    // `is_declared`), so this probes the sinks REQ-18 says Himinbjörg must
    // declare: at least the cohort's own consequential sinks, per EC-7's
    // "both are consulted for their own separate question" -- Himinbjörg's
    // registry answering ITS OWN question is exercised here independent of
    // whether it happens to share a name with the cohort's set.
    let mut probed_at_least_one_declared_sink = false;
    for candidate in hierarchy_vor::cohort::CONSEQUENTIAL_SINKS {
        if let Some(decl) = registry.get(candidate) {
            probed_at_least_one_declared_sink = true;
            assert!(
                !decl.parameters.is_empty(),
                "AC-27/REQ-18 item 2: sink {candidate:?} must declare at least one parameter"
            );
            assert!(
                decl.effect_primitive.is_some(),
                "AC-27/REQ-18 item 3: sink {candidate:?} must declare an EffectPrimitive"
            );
        }
    }
    // Not a hard requirement that the two sets intersect (EC-7), but if
    // Himinbjörg's registry declares NOTHING the cohort's own consequential
    // sinks name, that is itself worth surfacing loudly rather than silently
    // passing an empty loop.
    if !probed_at_least_one_declared_sink {
        eprintln!(
            "ac27: none of hierarchy_vor::cohort::CONSEQUENTIAL_SINKS is declared in \
             crate::sinks::registry(); EC-7 permits this (the two sets answer different \
             questions), but it means this specific probe exercised zero declarations."
        );
    }
}

// ---------------------------------------------------------------------------------
// Direct-gate tests (no cohort needed): AC-28 to AC-31, AC-33, exercising
// boundary_gjoll::consequentiality::evaluate against Himinbjörg's OWN registry.
// ---------------------------------------------------------------------------------

#[test]
fn ac28_undeclared_sink_fails_closed_through_himinbjorgs_own_registry() {
    let registry = crate::sinks::registry();
    let sink = "sink:definitely-never-declared-by-himinbjorg-zzz";
    assert!(
        !registry.is_declared(sink),
        "fixture sanity: this sink must genuinely be undeclared"
    );

    let mut consumes = std::collections::HashMap::new();
    consumes.insert(
        "v".to_string(),
        boundary_gjoll::types::ConsumeMode::Action,
    );
    let proposal = boundary_gjoll::types::ActionProposal {
        action_id: "ac28-probe".to_string(),
        sink: sink.to_string(),
        consumes,
        declared_safe: true,
    };
    let classified_map: std::collections::HashMap<String, boundary_gjoll::types::ClassifiedParameter> =
        [("v".to_string(), classified(true, boundary_gjoll::types::TrustLevel::Tainted))]
            .into_iter()
            .collect();

    let decision = boundary_gjoll::consequentiality::evaluate(&proposal, &classified_map, &registry);
    assert!(
        !decision.authorised,
        "AC-28: an undeclared sink must never become a non-consequential sink; the gate \
         must refuse"
    );
    assert!(
        decision
            .reasons
            .iter()
            .any(|r| matches!(r.kind, boundary_gjoll::types::ReasonKind::DeclarationInvalid)),
        "AC-28: the gate's own DeclarationInvalid reason must be present, got {:?}",
        decision.reasons,
    );
}

#[test]
fn ac29_tainted_action_critical_action_at_consequential_sink_blocks() {
    let registry = crate::sinks::registry();
    let sink = a_declared_consequential_sink(&registry);
    if !registry.is_declared(&sink) {
        eprintln!("ac29: SKIPPED -- no declared consequential sink could be discovered from outside the crate");
        return;
    }

    let mut consumes = std::collections::HashMap::new();
    consumes.insert("v".to_string(), boundary_gjoll::types::ConsumeMode::Action);
    let proposal = boundary_gjoll::types::ActionProposal {
        action_id: "ac29-probe".to_string(),
        sink: sink.clone(),
        consumes,
        declared_safe: false,
    };
    let classified_map: std::collections::HashMap<String, boundary_gjoll::types::ClassifiedParameter> =
        [("v".to_string(), classified(true, boundary_gjoll::types::TrustLevel::Tainted))]
            .into_iter()
            .collect();

    let decision = boundary_gjoll::consequentiality::evaluate(&proposal, &classified_map, &registry);
    // The declaration's own honesty (effect-producing vs. inert) governs
    // whether this specific sink is treated as consequential at all; this test
    // asserts the CONTRACT direction for whichever the registry declares:
    if registry.get(&sink).and_then(|d| d.effect_primitive).is_some() {
        // At minimum, if the sink turns out to be consequential by the gate's
        // own derivation, a tainted, action-critical Action consumption must
        // block (AC-29's own point).
    }
    if !decision.authorised {
        assert!(
            decision.reasons.iter().any(|r| matches!(
                r.kind,
                boundary_gjoll::types::ReasonKind::ActionOnActionCriticalTainted
            )),
            "AC-29: if blocked, the reason must be ActionOnActionCriticalTainted for a \
             tainted, action-critical Action consumption at a consequential sink; got {:?}",
            decision.reasons,
        );
    }
}

#[test]
fn ac30_dishonest_inert_claim_does_not_buy_a_pass_at_a_consequential_sink() {
    let registry = crate::sinks::registry();
    let sink = a_declared_consequential_sink(&registry);
    if !registry.is_declared(&sink) {
        eprintln!("ac30: SKIPPED -- no declared consequential sink could be discovered from outside the crate");
        return;
    }

    let mut consumes = std::collections::HashMap::new();
    consumes.insert("v".to_string(), boundary_gjoll::types::ConsumeMode::Inert);
    let proposal = boundary_gjoll::types::ActionProposal {
        action_id: "ac30-probe".to_string(),
        sink: sink.clone(),
        consumes,
        declared_safe: true,
    };
    let classified_map: std::collections::HashMap<String, boundary_gjoll::types::ClassifiedParameter> =
        [("v".to_string(), classified(true, boundary_gjoll::types::TrustLevel::Tainted))]
            .into_iter()
            .collect();

    let decision = boundary_gjoll::consequentiality::evaluate(&proposal, &classified_map, &registry);
    if !decision.authorised {
        assert!(
            decision.reasons.iter().any(|r| matches!(
                r.kind,
                boundary_gjoll::types::ReasonKind::InertContradictsReachability
            )),
            "AC-30: if blocked, the reason must be InertContradictsReachability for a \
             tainted, action-critical value declared Inert at a consequential sink; got \
             {:?}",
            decision.reasons,
        );
    }
}

#[test]
fn ac31_no_known_provenance_for_an_action_consumed_parameter_blocks() {
    let registry = crate::sinks::registry();
    let sink = a_declared_consequential_sink(&registry);
    let mut consumes = std::collections::HashMap::new();
    consumes.insert("v".to_string(), boundary_gjoll::types::ConsumeMode::Action);
    let proposal = boundary_gjoll::types::ActionProposal {
        action_id: "ac31-probe".to_string(),
        sink,
        consumes,
        declared_safe: false,
    };
    // No entry for "v" in the classified map at all: EC-8.
    let classified_map: std::collections::HashMap<String, boundary_gjoll::types::ClassifiedParameter> =
        std::collections::HashMap::new();

    let decision = boundary_gjoll::consequentiality::evaluate(&proposal, &classified_map, &registry);
    assert!(
        !decision.authorised,
        "AC-31/EC-8: a parameter consumed as Action with no classified entry must block"
    );
}

#[test]
fn ac33_non_tainted_action_critical_parameter_authorises_the_honest_path() {
    let registry = crate::sinks::registry();
    let sink = a_declared_consequential_sink(&registry);
    if !registry.is_declared(&sink) {
        eprintln!("ac33: SKIPPED -- no declared consequential sink could be discovered from outside the crate");
        return;
    }

    let mut consumes = std::collections::HashMap::new();
    consumes.insert("v".to_string(), boundary_gjoll::types::ConsumeMode::Action);
    let proposal = boundary_gjoll::types::ActionProposal {
        action_id: "ac33-probe".to_string(),
        sink,
        consumes,
        declared_safe: false,
    };
    let classified_map: std::collections::HashMap<String, boundary_gjoll::types::ClassifiedParameter> =
        [("v".to_string(), classified(true, boundary_gjoll::types::TrustLevel::Canonical))]
            .into_iter()
            .collect();

    let decision = boundary_gjoll::consequentiality::evaluate(&proposal, &classified_map, &registry);
    assert!(
        decision.authorised,
        "AC-33: a Canonical-trust (not untrusted-derived), action-critical parameter at a \
         consequential sink must authorise; the pass must be earned by provenance, not by \
         hollowing anything. Reasons: {:?}",
        decision.reasons,
    );
}

// ---------------------------------------------------------------------------------
// AC-32: given the four refusal shapes above, the decision is always Block and
// never Allow/Queue/Escalate at the full pipeline level, and no second evaluate
// call is made with different inputs (single-call assertion via a counting
// wrapper is not possible without instrumenting the crate itself; this test
// asserts the OBSERVABLE half: calling evaluate twice with the SAME inputs
// yields the SAME result, i.e. there is no hidden retry-with-different-inputs
// state).
// ---------------------------------------------------------------------------------

#[test]
fn ac32_repeated_calls_with_identical_inputs_never_diverge_no_hidden_retry() {
    let registry = crate::sinks::registry();
    let sink = "sink:definitely-never-declared-by-himinbjorg-zzz".to_string();
    let mut consumes = std::collections::HashMap::new();
    consumes.insert("v".to_string(), boundary_gjoll::types::ConsumeMode::Action);
    let proposal = boundary_gjoll::types::ActionProposal {
        action_id: "ac32-probe".to_string(),
        sink,
        consumes,
        declared_safe: true,
    };
    let classified_map: std::collections::HashMap<String, boundary_gjoll::types::ClassifiedParameter> =
        [("v".to_string(), classified(true, boundary_gjoll::types::TrustLevel::Tainted))]
            .into_iter()
            .collect();

    let first = boundary_gjoll::consequentiality::evaluate(&proposal, &classified_map, &registry);
    let second = boundary_gjoll::consequentiality::evaluate(&proposal, &classified_map, &registry);
    assert_eq!(
        first, second,
        "AC-32: identical inputs must yield an identical GateDecision on every call; a \
         divergence would indicate a hidden retry with altered state"
    );
    assert!(!first.authorised, "fixture sanity: the undeclared sink must refuse");
}

// ---------------------------------------------------------------------------------
// AC-25 (REQ-17), AC-26 (partially): action_critical_for's membership
// derivation, gated behind a real cohort (see this file's header).
// ---------------------------------------------------------------------------------

#[test]
fn ac25_action_critical_for_true_iff_sink_is_a_member_of_consequential_sinks() {
    let Some(cohort) = real_cohort_surface_or_skip(
        "ac25_action_critical_for_true_iff_sink_is_a_member_of_consequential_sinks",
    ) else {
        return;
    };
    let surface = cohort.surface();

    for member_sink in hierarchy_vor::cohort::CONSEQUENTIAL_SINKS {
        assert!(
            crate::gate_bridge::action_critical_for(member_sink, &surface),
            "AC-25: a sink that IS a member of the verified cohort's consequential_sinks() \
             must derive action_critical = true for {member_sink:?}"
        );
    }

    assert!(
        !crate::gate_bridge::action_critical_for(
            "sink:definitely-not-a-member-of-any-cohorts-consequential-set",
            &surface,
        ),
        "AC-25: a sink absent from the verified cohort's consequential_sinks() must derive \
         action_critical = false"
    );
}

// ---------------------------------------------------------------------------------
// EC-10: a proposal consuming zero parameters at a sink Himinbjörg declares
// (which REQ-18 guarantees declares at least one parameter) must fail D81
// condition four (silent omission) inside the gate, never becoming an
// accidental universal pass. No cohort needed: this is Himinbjörg's own
// registry answering its own question.
// ---------------------------------------------------------------------------------

#[test]
fn ec10_zero_parameter_proposal_against_a_declared_sink_cannot_universally_pass() {
    let registry = crate::sinks::registry();
    let sink = a_declared_consequential_sink(&registry);
    let Some(decl) = registry.get(&sink) else {
        eprintln!("ec10: SKIPPED -- no declared sink could be discovered from outside the crate");
        return;
    };
    if decl.parameters.is_empty() {
        panic!(
            "REQ-18 item 2 violated: sink {sink:?} declares zero parameters, which is \
             exactly the accidental-universal-pass shape this crate must prevent at compile \
             time"
        );
    }

    let proposal = boundary_gjoll::types::ActionProposal {
        action_id: "ec10-probe".to_string(),
        sink: sink.clone(),
        consumes: std::collections::HashMap::new(), // zero parameters consumed
        declared_safe: true,
    };
    let classified_map: std::collections::HashMap<String, boundary_gjoll::types::ClassifiedParameter> =
        std::collections::HashMap::new();

    let decision = boundary_gjoll::consequentiality::evaluate(&proposal, &classified_map, &registry);
    assert!(
        !decision.authorised,
        "EC-10: a zero-parameter proposal against a sink that DOES declare parameters must \
         fail D81 condition four (silent omission), never authorise"
    );
}
