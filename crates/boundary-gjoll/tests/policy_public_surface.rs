// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The pass criterion (AC-14) and the validation-first ordering (AC-27),
//! through the public surface alone. Compiled as an integration test: an
//! external crate importing `boundary_gjoll` and `hierarchy_vor` exactly as
//! any downstream caller would (REQ-40).
//!
//! Written from `.opencode/plans/rust-promotion-gate-spec.md` alone, with no
//! sight of the implementation. THIS FILE WILL FAIL TO COMPILE until
//! `boundary_gjoll::consequentiality::evaluate_with_policy`,
//! `boundary_gjoll::gate_policy::{GateName, GatePolicy}`,
//! `boundary_gjoll::rule::PromotionEvidence` and
//! `hierarchy_vor::load_verified_promotion` all exist and are public. That is
//! expected and correct at this stage.
//!
//! **This is the first criterion in this repository under which any value
//! passes Gjöll's gate** (the spec's own words for AC-14). It is reachable
//! from a test only.

use std::collections::HashMap;
use std::fs;
#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use boundary_gjoll::consequentiality::evaluate_with_policy;
use boundary_gjoll::declaration::{EffectPrimitive, SinkDeclaration, SinkRegistry};
use boundary_gjoll::gate_policy::{GateName, GatePolicy};
use boundary_gjoll::rule::PromotionEvidence;
use boundary_gjoll::types::{ActionProposal, ClassifiedParameter, ConsumeMode, TrustLevel};

const FIXTURE_SECRET: &[u8] = b"policy-public-surface-fixture-secret-32bytes!!";
const FIXTURE_AUTHORISER: &str = "policy-surface-authoriser";
/// A well-formed promotion fixture: assertion_id "v", content_digest
/// "deadbeef", promoted_to "TRUSTED", window [100, 200], attested under
/// `FIXTURE_SECRET` and `FIXTURE_AUTHORISER`. Pinned offline (see
/// `unit_tests/gate_policy_failclosed.rs`'s module doc comment for why this
/// crate's own tests pin rather than compute the digest).
const FIXTURE_ATTESTATION: &str =
    "2015f37d1475e1235d8795cb3e37392477b707170ad7004ee6892728faf369f4";

#[cfg(unix)]
fn scratch_dir(label: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock before the Unix epoch")
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("boundary-gjoll-policy-surface-{label}-{nanos}"));
    fs::create_dir_all(&dir).expect("failed to create scratch dir");
    dir
}

#[cfg(unix)]
fn trusted_set() -> hierarchy_vor::TrustedAuthoriserSet {
    let dir = scratch_dir("trusted-set");
    let path = dir.join("secret");
    fs::write(&path, FIXTURE_SECRET).expect("failed to write fixture secret");
    fs::set_permissions(&path, fs::Permissions::from_mode(0o600))
        .expect("failed to set fixture secret permissions");
    hierarchy_vor::load_trusted_set_from_path(FIXTURE_AUTHORISER, &path)
        .expect("the fixture secret file must load")
}

fn sink_registry_with(name: &str, params: &[&str]) -> SinkRegistry {
    let mut registry = SinkRegistry::new();
    registry.declare(SinkDeclaration {
        name: name.to_string(),
        parameters: params.iter().map(|s| s.to_string()).collect(),
        consequential_by_default: true,
        effect_primitive: Some(EffectPrimitive::MoveMoney),
    });
    registry
}

// ---------------------------------------------------------------------------------
// AC-14: the pass criterion, through the public surface alone.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn ac14_a_fully_verified_promotion_authorises_the_action_through_the_public_surface() {
    let trusted = trusted_set();
    let witness = hierarchy_vor::load_verified_promotion(
        "v",
        "deadbeef",
        "TRUSTED",
        100,
        200,
        FIXTURE_AUTHORISER,
        FIXTURE_ATTESTATION,
        &trusted,
        150,
    )
    .expect("the well-formed fixture promotion must verify");

    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let evidence =
        PromotionEvidence::new().with("v".to_string(), "deadbeef".to_string(), &witness);

    let registry = sink_registry_with("sink:payments.execute", &["v"]);
    let classified: HashMap<String, ClassifiedParameter> = [(
        "v".to_string(),
        ClassifiedParameter {
            assertion_id: "v".to_string(),
            type_name: "comms:money_move_request".to_string(),
            trust_level: TrustLevel::Tainted,
            action_critical: true,
        },
    )]
    .into_iter()
    .collect();
    let proposal = ActionProposal {
        action_id: "ac14-pass".to_string(),
        sink: "sink:payments.execute".to_string(),
        consumes: [("v".to_string(), ConsumeMode::Action)].into_iter().collect(),
        declared_safe: false,
    };

    let decision = evaluate_with_policy(&proposal, &classified, &registry, &policy, &evidence);

    assert!(
        decision.authorised,
        "AC-14: a fully verified promotion binding the exact assertion_id and \
         content_digest, at or above TRUSTED_THRESHOLD, under a policy requiring \
         PromotionRequirement, must authorise; got reasons={:?}",
        decision.reasons,
    );
    assert!(
        decision.reasons.is_empty(),
        "AC-14: an authorised decision must carry no reasons; got {:?}",
        decision.reasons,
    );
    assert_eq!(
        decision.gate_evaluations.len(),
        1,
        "AC-14: gate_evaluations must contain exactly one entry; got {:?}",
        decision.gate_evaluations,
    );
}

// ---------------------------------------------------------------------------------
// AC-27: D81 validation runs BEFORE any policy consultation. A proposal that
// fails declaration validation, even with valid policy and valid evidence,
// must carry only declaration-invalid reasons and an empty gate_evaluations.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn ac27_d81_validation_failure_short_circuits_before_any_policy_consultation() {
    let trusted = trusted_set();
    let witness = hierarchy_vor::load_verified_promotion(
        "v",
        "deadbeef",
        "TRUSTED",
        100,
        200,
        FIXTURE_AUTHORISER,
        FIXTURE_ATTESTATION,
        &trusted,
        150,
    )
    .expect("the well-formed fixture promotion must verify");

    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let evidence =
        PromotionEvidence::new().with("v".to_string(), "deadbeef".to_string(), &witness);

    // A sink declared with a DIFFERENT parameter set than what the proposal
    // consumes: "v" is absent from the sink's declared required set, which
    // is D81 condition 4 (silent omission is the mirror; here it is
    // condition 5, an EXTRA parameter, since the sink declares nothing at
    // all but the proposal consumes "v").
    let registry = sink_registry_with("sink:payments.execute", &[]); // accepts nothing
    let classified: HashMap<String, ClassifiedParameter> = [(
        "v".to_string(),
        ClassifiedParameter {
            assertion_id: "v".to_string(),
            type_name: "comms:money_move_request".to_string(),
            trust_level: TrustLevel::Tainted,
            action_critical: true,
        },
    )]
    .into_iter()
    .collect();
    let proposal = ActionProposal {
        action_id: "ac27-validation-first".to_string(),
        sink: "sink:payments.execute".to_string(),
        consumes: [("v".to_string(), ConsumeMode::Action)].into_iter().collect(),
        declared_safe: false,
    };

    let decision = evaluate_with_policy(&proposal, &classified, &registry, &policy, &evidence);

    assert!(
        !decision.authorised,
        "AC-27: a D81 declaration-validation failure must block even with valid \
         policy and valid promotion evidence"
    );
    assert!(
        decision
            .reasons
            .iter()
            .all(|r| r.kind == boundary_gjoll::types::ReasonKind::DeclarationInvalid),
        "AC-27: every reason on a validation-failed decision must be \
         DeclarationInvalid; got {:?}",
        decision.reasons,
    );
    assert!(
        decision.gate_evaluations.is_empty(),
        "AC-27: gate_evaluations must be empty when validation fails before the \
         rule core (and therefore the policy) is ever reached; got {:?}",
        decision.gate_evaluations,
    );
}

#[cfg(unix)]
#[test]
fn ac27_undeclared_sink_also_short_circuits_before_policy_consultation() {
    // A second, independent way to fail D81 validation (condition 1: the
    // sink itself is undeclared), proving the "before any policy
    // consultation" property is not an artefact of the specific condition
    // exercised above.
    let trusted = trusted_set();
    let witness = hierarchy_vor::load_verified_promotion(
        "v",
        "deadbeef",
        "TRUSTED",
        100,
        200,
        FIXTURE_AUTHORISER,
        FIXTURE_ATTESTATION,
        &trusted,
        150,
    )
    .expect("the well-formed fixture promotion must verify");

    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let evidence =
        PromotionEvidence::new().with("v".to_string(), "deadbeef".to_string(), &witness);

    let registry = SinkRegistry::new(); // nothing declared at all
    let classified: HashMap<String, ClassifiedParameter> = [(
        "v".to_string(),
        ClassifiedParameter {
            assertion_id: "v".to_string(),
            type_name: "comms:money_move_request".to_string(),
            trust_level: TrustLevel::Trusted, // even a TRUSTED value must not bypass D81
            action_critical: true,
        },
    )]
    .into_iter()
    .collect();
    let proposal = ActionProposal {
        action_id: "ac27-undeclared-sink".to_string(),
        sink: "sink:never-declared".to_string(),
        consumes: [("v".to_string(), ConsumeMode::Action)].into_iter().collect(),
        declared_safe: true,
    };

    let decision = evaluate_with_policy(&proposal, &classified, &registry, &policy, &evidence);
    assert!(!decision.authorised, "an undeclared sink must block regardless of policy/evidence");
    assert!(decision.gate_evaluations.is_empty(), "gate_evaluations must be empty");
}
