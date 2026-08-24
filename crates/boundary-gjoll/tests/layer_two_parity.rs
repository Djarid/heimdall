//! Layer-two golden-vector replay (REQ-24 clause 3, REQ-25): the six registry-backed
//! vectors from `crates/boundary-gjoll/vectors/gate_vectors.json`, replayed against
//! `boundary_gjoll::consequentiality::evaluate`, the crate's PUBLIC gate entry point,
//! through the public API alone. Compiled as an integration test (an external crate
//! importing `boundary_gjoll` exactly as any downstream caller would), which is what
//! proves the public API is sufficient (REQ-24 clause 3) and, together with
//! `unit_tests/layer_one_parity.rs`'s AC-10 companion check, that no escape hatch here
//! can reach `ConsequentialityVerdict`'s `pub(crate)` constructor.
//!
//! This file WILL FAIL TO COMPILE until `boundary_gjoll::types`,
//! `boundary_gjoll::declaration` and `boundary_gjoll::consequentiality` exist, are
//! `pub`, and are declared from `lib.rs`. That is expected and correct at this stage.
//!
//! Signatures assumed here, committed by this test suite (see
//! `unit_tests/layer_one_parity.rs`'s header for the same discipline applied to layer
//! one):
//!   - `consequentiality::evaluate(proposal: &ActionProposal, classified:
//!     &HashMap<String, ClassifiedParameter>, registry: &SinkRegistry) -> GateDecision`
//!     (REQ-13: `registry` is a plain reference, never `Option`).
//!   - `declaration::{SinkDeclaration, SinkRegistry, EffectPrimitive}` are public;
//!     `SinkRegistry::new()` plus `.declare(SinkDeclaration)` mirror the Python
//!     `SinkRegistry`'s `declare`/lookup shape (section 5.1).
//!   - `EffectPrimitive` mirrors `sink_declaration.py`'s taxonomy one for one
//!     (`MoveMoney`, `GrantOrUseAccess`, `RunOrChangeCode`, `ExfiltrateData`,
//!     `DestroyData`, `BindingCommitment`, `ChangeSecurityState`, `DisplayOnly`,
//!     `StoreOnly`, plus `Unrecognised` for an unknown declared string, per REQ-15).

use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

use serde::Deserialize;

use boundary_gjoll::consequentiality::evaluate;
use boundary_gjoll::declaration::{EffectPrimitive, SinkDeclaration, SinkRegistry};
use boundary_gjoll::types::{ActionProposal, ClassifiedParameter, ConsumeMode, GateDecision, ReasonKind, TrustLevel};

#[derive(Deserialize)]
struct VectorFile {
    expected_counts: ExpectedCounts,
    vectors: Vec<Vector>,
}

#[derive(Deserialize)]
struct ExpectedCounts {
    #[allow(dead_code)]
    layer_one: usize,
    layer_two: usize,
}

#[derive(Deserialize)]
struct Vector {
    id: String,
    origin: String,
    layer_one: LayerOneFixture,
    layer_two: Option<LayerTwoFixture>,
}

#[derive(Deserialize)]
struct LayerOneFixture {
    proposal: ProposalFixture,
    classified: HashMap<String, ClassifiedFixture>,
}

#[derive(Deserialize)]
struct ProposalFixture {
    action_id: String,
    sink: String,
    consumes: HashMap<String, String>,
    declared_safe: bool,
}

#[derive(Deserialize)]
struct ClassifiedFixture {
    assertion_id: String,
    type_name: String,
    trust_level: String,
    action_critical: bool,
}

#[derive(Deserialize)]
struct LayerTwoFixture {
    registry: RegistryFixture,
    expected: ExpectedOutcome,
}

#[derive(Deserialize)]
struct RegistryFixture {
    declarations: Vec<DeclarationFixture>,
}

#[derive(Deserialize)]
struct DeclarationFixture {
    name: String,
    parameters: Vec<String>,
    consequential_by_default: bool,
    effect_primitive: Option<String>,
}

#[derive(Deserialize, Clone)]
struct ExpectedOutcome {
    authorised: bool,
    reasons: Vec<ExpectedReason>,
}

#[derive(Deserialize, Clone)]
struct ExpectedReason {
    kind: String,
    parameter: String,
}

fn vector_file_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("vectors").join("gate_vectors.json")
}

fn load_vectors() -> VectorFile {
    let raw = fs::read_to_string(vector_file_path()).unwrap_or_else(|e| {
        panic!(
            "layer_two_parity: could not read gate_vectors.json ({e}); run `python -m \
             ontology.tools.export_gate_vectors` first (EC-11: fail, never skip)"
        )
    });
    let data: VectorFile = serde_json::from_str(&raw)
        .unwrap_or_else(|e| panic!("layer_two_parity: gate_vectors.json did not parse ({e})"));
    assert_eq!(data.expected_counts.layer_two, 6, "expected_counts.layer_two has drifted from 6");
    data
}

fn consume_mode_from_str(s: &str) -> ConsumeMode {
    match s {
        "ACTION" => ConsumeMode::Action,
        "INERT" => ConsumeMode::Inert,
        other => panic!("layer_two_parity: unrecognised consume mode {other:?} (REQ-9)"),
    }
}

fn trust_level_from_str(s: &str) -> TrustLevel {
    match s {
        "trust:TAINTED" => TrustLevel::Tainted,
        other => panic!("layer_two_parity: unrecognised trust level {other:?}"),
    }
}

fn effect_primitive_from_str(s: &str) -> EffectPrimitive {
    match s {
        "move_money" => EffectPrimitive::MoveMoney,
        "grant_or_use_access" => EffectPrimitive::GrantOrUseAccess,
        "run_or_change_code" => EffectPrimitive::RunOrChangeCode,
        "exfiltrate_data" => EffectPrimitive::ExfiltrateData,
        "destroy_data" => EffectPrimitive::DestroyData,
        "binding_commitment" => EffectPrimitive::BindingCommitment,
        "change_security_state" => EffectPrimitive::ChangeSecurityState,
        "display_only" => EffectPrimitive::DisplayOnly,
        "store_only" => EffectPrimitive::StoreOnly,
        _ => EffectPrimitive::Unrecognised,
    }
}

fn reason_kind_to_str(kind: &ReasonKind) -> &'static str {
    match kind {
        ReasonKind::DeclarationInvalid => "declaration_invalid",
        ReasonKind::InertContradictsReachability => "inert_contradicts_reachability",
        ReasonKind::NoKnownProvenance => "no_known_provenance",
        ReasonKind::ActionOnActionCriticalTainted => "action_on_action_critical_tainted",
    }
}

fn build_proposal(fx: &ProposalFixture) -> ActionProposal {
    ActionProposal {
        action_id: fx.action_id.clone(),
        sink: fx.sink.clone(),
        consumes: fx.consumes.iter().map(|(k, v)| (k.clone(), consume_mode_from_str(v))).collect(),
        declared_safe: fx.declared_safe,
    }
}

fn build_classified(fx: &HashMap<String, ClassifiedFixture>) -> HashMap<String, ClassifiedParameter> {
    fx.iter()
        .map(|(id, c)| {
            (
                id.clone(),
                ClassifiedParameter {
                    assertion_id: c.assertion_id.clone(),
                    type_name: c.type_name.clone(),
                    trust_level: trust_level_from_str(&c.trust_level),
                    action_critical: c.action_critical,
                },
            )
        })
        .collect()
}

fn build_registry(fx: &RegistryFixture) -> SinkRegistry {
    let mut registry = SinkRegistry::new();
    for d in &fx.declarations {
        registry.declare(SinkDeclaration {
            name: d.name.clone(),
            parameters: d.parameters.iter().cloned().collect(),
            consequential_by_default: d.consequential_by_default,
            effect_primitive: d.effect_primitive.as_deref().map(effect_primitive_from_str),
        });
    }
    registry
}

/// The oracle comparison, mirroring `unit_tests/layer_one_parity.rs`'s own
/// `vector_matches`: reasons compared as `(kind, parameter id)` multisets (REQ-11),
/// never by prose (AC-11). Duplicated deliberately rather than shared: this file is
/// an integration test compiled as an external crate and must not import test-only
/// helpers from the unit-test module, which is compiled only under the crate's own
/// `cfg(test)` and is not part of the public API this file is proving sufficient.
fn vector_matches(decision: &GateDecision, expected: &ExpectedOutcome) -> bool {
    if decision.authorised != expected.authorised {
        return false;
    }
    let mut actual: Vec<(&'static str, String)> =
        decision.reasons.iter().map(|r| (reason_kind_to_str(&r.kind), r.parameter_id.clone())).collect();
    let mut want: Vec<(String, String)> =
        expected.reasons.iter().map(|r| (r.kind.clone(), r.parameter.clone())).collect();
    actual.sort();
    want.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)));
    actual.len() == want.len()
        && actual.iter().zip(want.iter()).all(|((ak, ap), (wk, wp))| *ak == wk.as_str() && ap == wp)
}

fn find_vector<'a>(data: &'a VectorFile, id: &str) -> &'a Vector {
    data.vectors.iter().find(|v| v.id == id).unwrap_or_else(|| panic!("vector {id:?} not found"))
}

#[test]
fn layer_two_replay_reproduces_all_6_registry_vectors() {
    let data = load_vectors();
    let with_layer_two: Vec<&Vector> = data.vectors.iter().filter(|v| v.layer_two.is_some()).collect();
    assert_eq!(with_layer_two.len(), 6, "expected exactly 6 layer-two vectors in gate_vectors.json");

    for v in with_layer_two {
        let layer_two = v.layer_two.as_ref().unwrap();
        let proposal = build_proposal(&v.layer_one.proposal);
        let classified = build_classified(&v.layer_one.classified);
        let registry = build_registry(&layer_two.registry);

        let decision = evaluate(&proposal, &classified, &registry);

        assert!(
            vector_matches(&decision, &layer_two.expected),
            "vector {} ({}) did not reproduce at layer two: got authorised={}",
            v.id,
            v.origin,
            decision.authorised,
        );

        // AC-16: `GateDecision` has no `notes` field at all (REQ-16), so the
        // registry-path claim that notes are always empty (Python's AC-9c) is
        // discharged STRUCTURALLY here, by the fact this file compiles without ever
        // referencing `.notes` -- never by an assertion on a field that does not
        // exist. This comment is the structural proof's own documentation.
    }
}

#[test]
fn corrupted_vector_negative_control_layer_two_authorisation_inverted() {
    let data = load_vectors();
    let v = find_vector(&data, "G-4"); // D89-B: dishonestly-flagged money sink, expected blocked
    let layer_two = v.layer_two.as_ref().expect("G-4 must carry a layer_two section");
    let proposal = build_proposal(&v.layer_one.proposal);
    let classified = build_classified(&v.layer_one.classified);
    let registry = build_registry(&layer_two.registry);
    let decision = evaluate(&proposal, &classified, &registry);

    let mut corrupted = layer_two.expected.clone();
    corrupted.authorised = !corrupted.authorised;

    assert!(
        !vector_matches(&decision, &corrupted),
        "corrupted-vector control FAILED to bite at layer two: inverting G-4's expected \
         authorisation outcome was NOT detected as a mismatch (AC-25)"
    );
}
