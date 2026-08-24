//! Layer-one golden-vector replay (REQ-24, REQ-25, REQ-26): all 22 vectors from
//! `crates/boundary-gjoll/vectors/gate_vectors.json`, replayed directly against
//! `crate::rule::apply`, the pure rule core. Compiled as an in-crate unit-test module
//! (`crate::layer_one_parity`) via `lib.rs`'s `#[path]` declaration, which is why it
//! can construct `crate::rule::ConsequentialityVerdict` through its `pub(crate)`
//! constructor without any visibility widening (REQ-10 is unaffected by REQ-24's
//! separation; see the spec's REQ-24 note and section 14).
//!
//! This file WILL FAIL TO COMPILE until `crate::types` and `crate::rule` exist and
//! are declared from `lib.rs`. That is expected and correct at this stage: this file
//! and `lib.rs`'s test-wiring declaration are written before the implementation, so
//! the implementing agent builds the crate to satisfy a fixed, already-written
//! contract rather than the reverse.
//!
//! Signatures assumed here, where the spec's section 5.1 leaves the exact shape to
//! the implementing agent, are this test suite's own committed contract:
//!   - `rule::apply(verdict: ConsequentialityVerdict, proposal: &ActionProposal,
//!     classified: &HashMap<String, ClassifiedParameter>) -> GateDecision`
//!   - `ConsequentialityVerdict::new(bool) -> Self` is `pub(crate)` (REQ-10).
//!   - `types::{ActionProposal, ClassifiedParameter, ConsumeMode, TrustLevel,
//!     ReasonKind, Reason, GateDecision}` carry public fields (plain data shapes,
//!     mirroring the Python dataclasses they re-express).
//!
//! Where the spec already fixes a shape (REQ-8's four `ClassifiedParameter` fields,
//! REQ-9's two-variant `ConsumeMode`, REQ-11's four `ReasonKind` variants, REQ-16's
//! absent `notes` field), this file matches it exactly.

use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

use serde::Deserialize;

use crate::rule::{apply, ConsequentialityVerdict};
use crate::types::{
    ActionProposal, ClassifiedParameter, ConsumeMode, GateDecision, ReasonKind, TrustLevel,
};

// ---------------------------------------------------------------------------------
// Vector-file fixture shapes. Mirror `ontology/tools/export_gate_vectors.py`'s
// emitted JSON exactly (schema in the spec's section 5.3); these are TEST-side
// deserialisation targets, never the crate's own types.
// ---------------------------------------------------------------------------------

#[derive(Deserialize)]
struct VectorFile {
    #[allow(dead_code)]
    schema_version: u32,
    #[allow(dead_code)]
    generated_from: GeneratedFrom,
    expected_counts: ExpectedCounts,
    vectors: Vec<Vector>,
}

#[derive(Deserialize)]
struct GeneratedFrom {
    #[allow(dead_code)]
    gjoll_py_sha256: String,
    #[allow(dead_code)]
    sink_declaration_py_sha256: String,
}

#[derive(Deserialize)]
struct ExpectedCounts {
    layer_one: usize,
    #[allow(dead_code)]
    layer_two: usize,
}

#[derive(Deserialize)]
struct Vector {
    id: String,
    origin: String,
    #[allow(dead_code)]
    claim: String,
    layer_one: LayerOneFixture,
}

#[derive(Deserialize)]
struct LayerOneFixture {
    verdict: bool,
    #[allow(dead_code)]
    verdict_sensitive: bool,
    proposal: ProposalFixture,
    classified: HashMap<String, ClassifiedFixture>,
    expected: ExpectedOutcome,
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

// ---------------------------------------------------------------------------------
// Fixture-loading and conversion helpers (test-side only; none of this is
// reimplementing gjoll's derivation, per REQ-19 applied to the Rust side too --
// these functions only translate a JSON fixture into the crate's own input types).
// ---------------------------------------------------------------------------------

fn vector_file_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("vectors")
        .join("gate_vectors.json")
}

fn load_vectors() -> VectorFile {
    let raw = fs::read_to_string(vector_file_path()).unwrap_or_else(|e| {
        panic!(
            "layer_one_parity: could not read crates/boundary-gjoll/vectors/gate_vectors.json \
             ({e}); run `python -m ontology.tools.export_gate_vectors` from the repo root first \
             (EC-11: an absent oracle is not a passing oracle, so this is a hard failure, never \
             a skip)"
        )
    });
    let data: VectorFile = serde_json::from_str(&raw).unwrap_or_else(|e| {
        panic!("layer_one_parity: gate_vectors.json did not parse ({e}); EC-11: fail, never skip")
    });
    assert_eq!(
        data.expected_counts.layer_one, 22,
        "gate_vectors.json's own expected_counts.layer_one has drifted from 22"
    );
    data
}

fn consume_mode_from_str(s: &str) -> ConsumeMode {
    match s {
        "ACTION" => ConsumeMode::Action,
        "INERT" => ConsumeMode::Inert,
        other => panic!(
            "layer_one_parity: vector fixture carries an unrecognised consume mode {other:?}; \
             this must be a vector-load error, never silently read as inert (REQ-9, AC-9)"
        ),
    }
}

fn trust_level_from_str(s: &str) -> TrustLevel {
    match s {
        "trust:TAINTED" => TrustLevel::Tainted,
        other => panic!(
            "layer_one_parity: vector fixture carries an unrecognised trust level {other:?}; \
             every captured vector is Phase 1 tainted-by-origin, so this is a fixture-loading \
             bug, not a case this replay is meant to cover"
        ),
    }
}

fn reason_kind_from_str(s: &str) -> ReasonKind {
    match s {
        "declaration_invalid" => ReasonKind::DeclarationInvalid,
        "inert_contradicts_reachability" => ReasonKind::InertContradictsReachability,
        "no_known_provenance" => ReasonKind::NoKnownProvenance,
        "action_on_action_critical_tainted" => ReasonKind::ActionOnActionCriticalTainted,
        other => panic!(
            "layer_one_parity: vector fixture carries an unrecognised reason kind {other:?}; \
             REQ-11's four kinds are closed, so this is a fixture-loading bug"
        ),
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
    let consumes = fx
        .consumes
        .iter()
        .map(|(k, v)| (k.clone(), consume_mode_from_str(v)))
        .collect();
    ActionProposal {
        action_id: fx.action_id.clone(),
        sink: fx.sink.clone(),
        consumes,
        declared_safe: fx.declared_safe,
    }
}

fn build_classified(
    fx: &HashMap<String, ClassifiedFixture>,
) -> HashMap<String, ClassifiedParameter> {
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

/// The oracle-comparison itself, factored out as a pure function so the corrupted-
/// vector negative controls (REQ-25, AC-25) can prove IT is sensitive to corruption,
/// independent of whether `rule::apply` is implemented correctly. Compares reasons as
/// `(kind, parameter id)` multisets (REQ-11, AC-11), never by prose string equality.
fn vector_matches(decision: &GateDecision, expected: &ExpectedOutcome) -> bool {
    if decision.authorised != expected.authorised {
        return false;
    }
    let mut actual: Vec<(&'static str, String)> = decision
        .reasons
        .iter()
        .map(|r| (reason_kind_to_str(&r.kind), r.parameter_id.clone()))
        .collect();
    let mut want: Vec<(&'static str, String)> = expected
        .reasons
        .iter()
        .map(|r| (reason_kind_from_python_key(&r.kind), r.parameter.clone()))
        .collect();
    actual.sort();
    want.sort();
    actual == want
}

/// `reason_kind_from_str` panics on an unrecognised kind (fixture-loading fail
/// closed); this thin wrapper exists only so `vector_matches` can use the same
/// static string form `reason_kind_to_str` returns for direct tuple comparison.
fn reason_kind_from_python_key(s: &str) -> &'static str {
    reason_kind_to_str(&reason_kind_from_str(s))
}

fn replay(v: &Vector) -> (GateDecision, ActionProposal) {
    let proposal = build_proposal(&v.layer_one.proposal);
    let classified = build_classified(&v.layer_one.classified);
    let verdict = ConsequentialityVerdict::new(v.layer_one.verdict);
    let decision = apply(verdict, &proposal, &classified);
    (decision, proposal)
}

fn find_vector<'a>(data: &'a VectorFile, id: &str) -> &'a Vector {
    data.vectors
        .iter()
        .find(|v| v.id == id)
        .unwrap_or_else(|| panic!("vector {id:?} not found in gate_vectors.json"))
}

// ---------------------------------------------------------------------------------
// D26/D89-A/D89-B block-before-effect recording double (REQ-26). NOT a crate type:
// the crate designs out a public `Actuator` and an `enforce` equivalent in step 1
// (spec section 2, open question 7), so this tiny double lives only here, on the
// same footing as gjoll.py's own mock `Actuator`.
// ---------------------------------------------------------------------------------
struct RecordingDouble {
    action_effects: Vec<String>,
}

impl RecordingDouble {
    fn new() -> Self {
        Self {
            action_effects: Vec::new(),
        }
    }

    /// Mirrors `gjoll.enforce`'s own block-before-effect discipline: a blocked
    /// decision must never reach this loop at all.
    fn fire_if_authorised(&mut self, proposal: &ActionProposal, decision: &GateDecision) {
        if !decision.authorised {
            return;
        }
        for (param_id, mode) in &proposal.consumes {
            if matches!(mode, ConsumeMode::Action) {
                self.action_effects
                    .push(format!("{}: acted on {}", proposal.action_id, param_id));
            }
        }
    }
}

// ---------------------------------------------------------------------------------
// The 22-vector replay itself.
// ---------------------------------------------------------------------------------

#[test]
fn layer_one_replay_reproduces_all_22_vectors() {
    let data = load_vectors();
    assert_eq!(
        data.vectors.len(),
        22,
        "gate_vectors.json does not carry exactly 22 vectors"
    );

    for v in &data.vectors {
        let (decision, _proposal) = replay(v);
        assert!(
            vector_matches(&decision, &v.layer_one.expected),
            "vector {} ({}) did not reproduce: got authorised={} reasons={:?}",
            v.id,
            v.origin,
            decision.authorised,
            decision
                .reasons
                .iter()
                .map(|r| (reason_kind_to_str(&r.kind), r.parameter_id.clone()))
                .collect::<Vec<_>>(),
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-25: the corrupted-vector negative controls. Until these pass, a green replay
// above is not evidence of anything (REQ-25): the following prove the oracle
// comparison (`vector_matches`) genuinely detects corruption, independent of
// `rule::apply`'s own correctness.
// ---------------------------------------------------------------------------------

#[test]
fn corrupted_vector_negative_control_authorisation_inverted() {
    let data = load_vectors();
    let v = find_vector(&data, "G-2"); // the D10 unsafe control: expected blocked
    let (decision, _proposal) = replay(v);

    let mut corrupted = v.layer_one.expected.clone();
    corrupted.authorised = !corrupted.authorised;

    assert!(
        !vector_matches(&decision, &corrupted),
        "corrupted-vector control FAILED to bite: inverting vector {}'s expected \
         authorisation outcome was NOT detected as a mismatch (AC-25)",
        v.id,
    );
}

#[test]
fn corrupted_vector_negative_control_parameter_silently_removed() {
    let data = load_vectors();
    let v = find_vector(&data, "C-8"); // one consumed param, no classified entry, blocks
    let mut proposal = build_proposal(&v.layer_one.proposal);
    let only_param = proposal
        .consumes
        .keys()
        .next()
        .cloned()
        .expect("C-8 must consume at least one parameter");
    proposal.consumes.remove(&only_param);

    let classified = build_classified(&v.layer_one.classified);
    let verdict = ConsequentialityVerdict::new(v.layer_one.verdict);
    let decision = apply(verdict, &proposal, &classified);

    assert!(
        !vector_matches(&decision, &v.layer_one.expected),
        "corrupted-vector control FAILED to bite: silently removing C-8's only consumed \
         parameter was NOT detected as a mismatch against the original vector's own \
         expectation (AC-25)",
    );
}

// ---------------------------------------------------------------------------------
// REQ-26: the mandatory D10 safe-plus-unsafe pair, replayed at layer one, with the
// private recording double proving block-before-effect.
// ---------------------------------------------------------------------------------

#[test]
fn d10_safe_plus_unsafe_control_block_before_effect() {
    let data = load_vectors();
    // G-1 (safe: inert consumption at an unrelated sink) and G-2 (unsafe control:
    // the staged cross-domain value consumed as an ACTION at the payment sink) are
    // exactly Gjoll's own D10 pair (ontology/tests/harness.py::run_gjoll).
    let safe = find_vector(&data, "G-1");
    let unsafe_wiring = find_vector(&data, "G-2");

    let (safe_decision, _safe_proposal) = replay(safe);
    assert!(
        safe_decision.authorised,
        "G-1 (the safe wiring) must authorise"
    );

    let (unsafe_decision, unsafe_proposal) = replay(unsafe_wiring);
    assert!(
        !unsafe_decision.authorised,
        "G-2 (the unsafe control) must be blocked"
    );

    let mut double = RecordingDouble::new();
    double.fire_if_authorised(&unsafe_proposal, &unsafe_decision);
    assert!(
        double.action_effects.is_empty(),
        "block-before-effect violated: G-2's blocked decision recorded an action effect"
    );
}

#[test]
fn recording_double_records_when_authorised_and_action_consuming() {
    // G-3: a non-action-critical value consumed as an ACTION, authorised. Unlike
    // G-1's inert consumption, this IS action-mode, so the double must record it:
    // proof the double is a meaningful recorder, not a no-op that always stays empty.
    let data = load_vectors();
    let g3 = find_vector(&data, "G-3");
    let (decision, proposal) = replay(g3);
    assert!(
        decision.authorised,
        "G-3 must authorise (the gate is not pure friction)"
    );

    let mut double = RecordingDouble::new();
    double.fire_if_authorised(&proposal, &decision);
    assert_eq!(
        double.action_effects.len(),
        1,
        "an authorised action-mode consumption must record exactly one effect"
    );
}
