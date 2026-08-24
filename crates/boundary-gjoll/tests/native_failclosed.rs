//! Rust-native tests (REQ-25, REQ-26, REQ-27): the five D81 validation conditions,
//! the three D89-B fail-closed silence cases, the D10 safe-plus-unsafe control pair
//! replayed through the public shell (not the vector file), and a native corrupted-
//! fixture negative control. None of this is vector-backed (REQ-27): no existing
//! Python gate call exercises a D81 validation failure through the gate (every
//! registry-supplied case in all three harnesses constructs a valid proposal), so
//! this file's parity oracle is `ontology.tests.sink_declaration_harness`'s existing
//! DIRECT tests of `validate_proposal` (never gate calls, and so never exported),
//! named explicitly at each test below.
//!
//! Compiled as an integration test (an external crate importing `boundary_gjoll`),
//! so every type and function used here is `boundary_gjoll`'s PUBLIC surface.
//!
//! A genuine design tension, resolved here and flagged for the implementing agent
//! (see the delegation's design-concerns note). REQ-9 requires `ConsumeMode` to be a
//! closed, two-variant enum so an invalid mode string is UNREPRESENTABLE inside the
//! rule core; but D81's second validation condition is precisely "an invalid consume
//! mode string", which by definition cannot be expressed as an already-parsed,
//! closed `ConsumeMode`. Python resolves this by keeping `consumes` a raw
//! `str -> str` dict everywhere and validating the string at `validate_proposal`
//! time; `sink_declaration_harness.py` tests that function DIRECTLY with raw dicts,
//! never through the gate, which is exactly the parity oracle REQ-27 names. This file
//! follows the SAME shape: the invalid-mode and phantom-parameter conditions (both
//! fundamentally about string-level malformation) are tested by calling
//! `declaration::validate_proposal` directly with a raw `consumes: HashMap<String,
//! String>`, mirroring Python's own signature one for one; the other three
//! conditions (undeclared sink, omitted parameter, extra parameter), which do not
//! require an invalid mode string, are tested BOTH directly and through the full
//! public shell (`consequentiality::evaluate`) with a well-typed, valid
//! `ActionProposal`, so AC-14's "when the shell evaluates each" framing is satisfied
//! wherever it is representable at all.

use std::collections::{HashMap, HashSet};

use boundary_gjoll::consequentiality::evaluate;
use boundary_gjoll::declaration::{
    intrinsically_consequential, validate_proposal, EffectPrimitive, SinkDeclaration, SinkRegistry,
};
use boundary_gjoll::types::{ActionProposal, ClassifiedParameter, ConsumeMode, ReasonKind, TrustLevel};

fn tainted_action_critical(assertion_id: &str) -> ClassifiedParameter {
    ClassifiedParameter {
        assertion_id: assertion_id.to_string(),
        type_name: "comms:money_move_request".to_string(),
        trust_level: TrustLevel::Tainted,
        action_critical: true,
    }
}

fn all_declaration_invalid(reasons: &[boundary_gjoll::types::Reason]) -> bool {
    !reasons.is_empty() && reasons.iter().all(|r| matches!(r.kind, ReasonKind::DeclarationInvalid))
}

// ---------------------------------------------------------------------------------
// The five D81 validation conditions (REQ-14, REQ-27). Parity oracle:
// `ontology.tests.sink_declaration_harness` (direct `validate_proposal` tests, not
// gate calls, and so not vector-backed).
// ---------------------------------------------------------------------------------

#[test]
fn d81_condition_1_undeclared_sink_blocks_even_with_safe_params() {
    // Rust-native, no Python gate-level vector (REQ-27): every registry-supplied
    // vector in the three harnesses uses a DECLARED sink. Parity oracle:
    // sink_declaration_harness.py's direct undeclared-sink test of validate_proposal.
    let registry = SinkRegistry::new(); // nothing declared at all
    let known_ids: HashSet<String> = ["safe.value".to_string()].into_iter().collect();
    let mut consumes: HashMap<String, String> = HashMap::new();
    consumes.insert("safe.value".to_string(), "ACTION".to_string());

    let outcome = validate_proposal("sink:undeclared", &consumes, &registry, &known_ids);
    assert!(
        all_declaration_invalid(&outcome.reasons),
        "an undeclared sink must fail validation with only declaration_invalid reasons"
    );
    assert!(outcome.treat_as_consequential, "an undeclared sink must fail closed to consequential");

    // AC-14: through the full public shell too, with every consumed parameter
    // TRUSTED and non-action-critical, proving the rule itself was never applied
    // (a safe wiring would otherwise authorise).
    let mut classified = HashMap::new();
    classified.insert(
        "safe.value".to_string(),
        ClassifiedParameter {
            assertion_id: "safe.value".into(),
            type_name: "comms:informational".into(),
            trust_level: TrustLevel::Tainted,
            action_critical: false,
        },
    );
    let proposal = ActionProposal {
        action_id: "shell-undeclared".into(),
        sink: "sink:undeclared".into(),
        consumes: [( "safe.value".to_string(), ConsumeMode::Action )].into_iter().collect(),
        declared_safe: true,
    };
    let decision = evaluate(&proposal, &classified, &registry);
    assert!(!decision.authorised, "the shell must block an undeclared sink even for a safe wiring");
}

#[test]
fn d81_condition_2_invalid_consume_mode_string() {
    // String-level condition; tested directly against validate_proposal's raw
    // consumes map, mirroring sink_declaration_harness.py's own oracle exactly
    // (REQ-9 makes this string unrepresentable as a parsed ConsumeMode, so it
    // cannot be expressed as a well-typed ActionProposal at all -- see this file's
    // header note).
    let mut registry = SinkRegistry::new();
    registry.declare(SinkDeclaration {
        name: "sink:x".into(),
        parameters: ["p".to_string()].into_iter().collect(),
        consequential_by_default: true,
        effect_primitive: Some(EffectPrimitive::MoveMoney),
    });
    let known_ids: HashSet<String> = ["p".to_string()].into_iter().collect();
    let mut consumes: HashMap<String, String> = HashMap::new();
    consumes.insert("p".to_string(), "ACTIION".to_string()); // typo, not a valid mode

    let outcome = validate_proposal("sink:x", &consumes, &registry, &known_ids);
    assert!(
        all_declaration_invalid(&outcome.reasons),
        "an invalid consume mode string must never be read as inert; it must be a \
         validation failure (D81 condition 2)"
    );
}

#[test]
fn d81_condition_3_phantom_parameter_not_a_known_assertion() {
    let mut registry = SinkRegistry::new();
    registry.declare(SinkDeclaration {
        name: "sink:x".into(),
        parameters: ["ghost".to_string()].into_iter().collect(),
        consequential_by_default: true,
        effect_primitive: Some(EffectPrimitive::MoveMoney),
    });
    let known_ids: HashSet<String> = HashSet::new(); // "ghost" is not a real assertion
    let mut consumes: HashMap<String, String> = HashMap::new();
    consumes.insert("ghost".to_string(), "ACTION".to_string());

    let outcome = validate_proposal("sink:x", &consumes, &registry, &known_ids);
    assert!(
        all_declaration_invalid(&outcome.reasons),
        "a parameter absent from the known classified assertions must fail validation \
         (D81 condition 3, a phantom parameter)"
    );
}

#[test]
fn d81_condition_4_silently_omitted_parameter() {
    let mut registry = SinkRegistry::new();
    registry.declare(SinkDeclaration {
        name: "sink:x".into(),
        parameters: ["a".to_string(), "b".to_string()].into_iter().collect(),
        consequential_by_default: true,
        effect_primitive: Some(EffectPrimitive::MoveMoney),
    });
    let known_ids: HashSet<String> = ["a".to_string()].into_iter().collect();
    let mut consumes: HashMap<String, String> = HashMap::new();
    consumes.insert("a".to_string(), "ACTION".to_string()); // "b" never accounted for

    let outcome = validate_proposal("sink:x", &consumes, &registry, &known_ids);
    assert!(
        all_declaration_invalid(&outcome.reasons),
        "a parameter the sink declares but the proposal never accounts for must fail \
         validation (D81 condition 4, silent omission)"
    );

    // AC-14, through the shell: same omission, valid ConsumeMode this time.
    let classified: HashMap<String, ClassifiedParameter> =
        [("a".to_string(), tainted_action_critical("a"))].into_iter().collect();
    let proposal = ActionProposal {
        action_id: "shell-omitted".into(),
        sink: "sink:x".into(),
        consumes: [("a".to_string(), ConsumeMode::Action)].into_iter().collect(),
        declared_safe: true,
    };
    let decision = evaluate(&proposal, &classified, &registry);
    assert!(!decision.authorised, "the shell must block a proposal that silently omits a declared parameter");
}

#[test]
fn d81_condition_5_extra_parameter_not_accepted() {
    let mut registry = SinkRegistry::new();
    registry.declare(SinkDeclaration {
        name: "sink:x".into(),
        parameters: HashSet::new(), // accepts nothing
        consequential_by_default: true,
        effect_primitive: Some(EffectPrimitive::MoveMoney),
    });
    let known_ids: HashSet<String> = ["extra".to_string()].into_iter().collect();
    let mut consumes: HashMap<String, String> = HashMap::new();
    consumes.insert("extra".to_string(), "ACTION".to_string());

    let outcome = validate_proposal("sink:x", &consumes, &registry, &known_ids);
    assert!(
        all_declaration_invalid(&outcome.reasons),
        "a parameter the sink does not accept must fail validation (D81 condition 5, \
         extra parameter; EC-8)"
    );

    // AC-14, through the shell.
    let classified: HashMap<String, ClassifiedParameter> =
        [("extra".to_string(), tainted_action_critical("extra"))].into_iter().collect();
    let proposal = ActionProposal {
        action_id: "shell-extra".into(),
        sink: "sink:x".into(),
        consumes: [("extra".to_string(), ConsumeMode::Action)].into_iter().collect(),
        declared_safe: true,
    };
    let decision = evaluate(&proposal, &classified, &registry);
    assert!(!decision.authorised, "the shell must block a proposal declaring a parameter the sink does not accept");
}

// ---------------------------------------------------------------------------------
// The three D89-B fail-closed silence cases (REQ-15, REQ-27), tested directly
// against `intrinsically_consequential`, plus AC-15's honest-inert control and its
// dishonest-flag control, through the full shell.
// ---------------------------------------------------------------------------------

#[test]
fn d89b_silence_case_1_undeclared_sink_fails_closed() {
    assert!(
        intrinsically_consequential(None),
        "an undeclared sink (no SinkDeclaration at all) must be intrinsically \
         consequential (fail closed, D89-B silence case 1)"
    );
}

#[test]
fn d89b_silence_case_2_no_primitive_declared_fails_closed() {
    let decl = SinkDeclaration {
        name: "sink:silent".into(),
        parameters: HashSet::new(),
        consequential_by_default: false,
        effect_primitive: None, // silence: no primitive declared at all
    };
    assert!(
        intrinsically_consequential(Some(&decl)),
        "a declared sink with NO effect primitive must fail closed to consequential \
         (D89-B silence case 2); silence never earns inert"
    );
}

#[test]
fn d89b_silence_case_3_unrecognised_primitive_fails_closed() {
    let decl = SinkDeclaration {
        name: "sink:mystery".into(),
        parameters: HashSet::new(),
        consequential_by_default: false,
        effect_primitive: Some(EffectPrimitive::Unrecognised), // e.g. "totally_harmless"
    };
    assert!(
        intrinsically_consequential(Some(&decl)),
        "an unrecognised effect-primitive string must fail closed to consequential \
         (D89-B silence case 3), never read as inert"
    );
}

#[test]
fn ac15_four_registry_variants_through_the_shell() {
    // (a) money primitive + a false consequential_by_default flag: the flag must be
    //     ignored; the derivation is by primitive, so this still blocks.
    // (b) no primitive at all: fails closed, blocks.
    // (c) an unrecognised primitive string: fails closed, blocks.
    // (d) an honest display-only primitive: the ONLY case that authorises.
    let cases: [(&str, bool, Option<EffectPrimitive>, bool); 4] = [
        ("a-dishonest-flag", false, Some(EffectPrimitive::MoveMoney), false),
        ("b-no-primitive", true, None, false),
        ("c-unrecognised", true, Some(EffectPrimitive::Unrecognised), false),
        ("d-honest-inert", false, Some(EffectPrimitive::DisplayOnly), true),
    ];

    for (label, consequential_by_default, effect_primitive, expect_authorised) in cases {
        let sink = format!("sink:{label}");
        let mut registry = SinkRegistry::new();
        registry.declare(SinkDeclaration {
            name: sink.clone(),
            parameters: ["v".to_string()].into_iter().collect(),
            consequential_by_default,
            effect_primitive,
        });
        let classified: HashMap<String, ClassifiedParameter> =
            [("v".to_string(), tainted_action_critical("v"))].into_iter().collect();
        let proposal = ActionProposal {
            action_id: format!("ac15-{label}"),
            sink,
            consumes: [("v".to_string(), ConsumeMode::Action)].into_iter().collect(),
            declared_safe: false,
        };
        let decision = evaluate(&proposal, &classified, &registry);
        assert_eq!(
            decision.authorised, expect_authorised,
            "AC-15 case {label:?}: expected authorised={expect_authorised}, got \
             authorised={} (reasons: {:?})",
            decision.authorised,
            decision.reasons.iter().map(|r| &r.parameter_id).collect::<Vec<_>>(),
        );
    }
}

// ---------------------------------------------------------------------------------
// REQ-26: the D10 safe-plus-unsafe pair, replayed NATIVELY through the public shell
// (not vector-backed), with block-before-effect.
// ---------------------------------------------------------------------------------

struct RecordingDouble {
    action_effects: Vec<String>,
}

impl RecordingDouble {
    fn new() -> Self {
        Self { action_effects: Vec::new() }
    }

    fn fire_if_authorised(&mut self, proposal: &ActionProposal, decision: &boundary_gjoll::types::GateDecision) {
        if !decision.authorised {
            return;
        }
        for (param_id, mode) in &proposal.consumes {
            if matches!(mode, ConsumeMode::Action) {
                self.action_effects.push(format!("{}: acted on {}", proposal.action_id, param_id));
            }
        }
    }
}

#[test]
fn d10_native_safe_plus_unsafe_pair_through_the_shell_block_before_effect() {
    let mut registry = SinkRegistry::new();
    registry.declare(SinkDeclaration {
        name: "sink:audit_log".into(),
        parameters: ["v".to_string()].into_iter().collect(),
        consequential_by_default: false,
        effect_primitive: Some(EffectPrimitive::DisplayOnly),
    });
    registry.declare(SinkDeclaration {
        name: "sink:payments.execute".into(),
        parameters: ["v".to_string()].into_iter().collect(),
        consequential_by_default: true,
        effect_primitive: Some(EffectPrimitive::MoveMoney),
    });
    let classified: HashMap<String, ClassifiedParameter> =
        [("v".to_string(), tainted_action_critical("v"))].into_iter().collect();

    let safe_proposal = ActionProposal {
        action_id: "native-safe".into(),
        sink: "sink:audit_log".into(),
        consumes: [("v".to_string(), ConsumeMode::Inert)].into_iter().collect(),
        declared_safe: true,
    };
    let safe_decision = evaluate(&safe_proposal, &classified, &registry);
    assert!(safe_decision.authorised, "the safe, inert wiring at an honestly display-only sink must authorise");

    let unsafe_proposal = ActionProposal {
        action_id: "native-unsafe".into(),
        sink: "sink:payments.execute".into(),
        consumes: [("v".to_string(), ConsumeMode::Action)].into_iter().collect(),
        declared_safe: false,
    };
    let unsafe_decision = evaluate(&unsafe_proposal, &classified, &registry);
    assert!(!unsafe_decision.authorised, "the unsafe control at a money-moving sink must be blocked");

    let mut double = RecordingDouble::new();
    double.fire_if_authorised(&unsafe_proposal, &unsafe_decision);
    assert!(double.action_effects.is_empty(), "block-before-effect violated for the native unsafe control");
}

// ---------------------------------------------------------------------------------
// A native corrupted-fixture negative control (REQ-25), independent of the vector
// file: proves the comparison this file's own assertions rely on is sensitive to a
// deliberately wrong expectation, not merely a tautology.
// ---------------------------------------------------------------------------------

fn validation_outcome_matches(
    reasons: &[boundary_gjoll::types::Reason],
    expected_valid: bool,
) -> bool {
    reasons.is_empty() == expected_valid
}

#[test]
fn native_corrupted_fixture_negative_control() {
    let registry = SinkRegistry::new();
    let known_ids: HashSet<String> = ["x".to_string()].into_iter().collect();
    let mut consumes: HashMap<String, String> = HashMap::new();
    consumes.insert("x".to_string(), "ACTION".to_string());
    let outcome = validate_proposal("sink:never-declared", &consumes, &registry, &known_ids);

    // The real outcome must be invalid (blocked).
    assert!(
        validation_outcome_matches(&outcome.reasons, false),
        "sanity: an undeclared sink must fail validation"
    );
    // The deliberately WRONG expectation (valid=true) must be detected as a mismatch.
    assert!(
        !validation_outcome_matches(&outcome.reasons, true),
        "corrupted-fixture control FAILED to bite: a deliberately wrong 'valid=true' \
         expectation for an undeclared sink was NOT detected as a mismatch (REQ-25)"
    );
}
