// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The gate-policy surface's fail-closed behaviour (REQ-10 to REQ-16, REQ-25,
//! REQ-27; AC-10 to AC-13, AC-15's six block cases, AC-16, AC-17, AC-26,
//! AC-28). Written from `.opencode/plans/rust-promotion-gate-spec.md` alone,
//! with no sight of the implementation.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crate::gate_policy::{GateName,
//! GatePolicy, GateResult, evaluate_policy, policy_satisfied}` exist (REQ-10
//! to REQ-16) and `crate::rule::{apply_with_policy, PromotionEvidence}` exist
//! (REQ-25, REQ-27), and until `hierarchy_vor::{load_trusted_set_from_path,
//! load_verified_promotion, VerifiedPromotion}` exist. That is expected and
//! correct at this stage.
//!
//! Wired into the crate by `lib.rs`'s
//! `#[cfg(test)] #[path = "../unit_tests/gate_policy_failclosed.rs"] mod gate_policy_failclosed;`
//! declaration (REQ-39): an in-crate module, which is why fixtures below can
//! be built directly and why `hierarchy_vor` (a real, non-dev dependency per
//! REQ-2) is reachable through its own public surface exactly as any
//! downstream caller would use it.
//!
//! **Fixture attestation digests below are pinned literals, not computed at
//! test time.** `hierarchy-vor`'s own attestation-computation function
//! (`compute_record_attestation`) is `pub(crate)` to THAT crate (REQ-13) and
//! is not reachable from here; this file instead independently computed the
//! expected keyed digests offline, from the canonical-byte layout the spec's
//! section 4.3 fixes (`RECORD_DOMAIN`, a single `0x00`, `record_type=promotion_record`,
//! then the six `name=value` lines in the fixed order, then a `0x00` domain
//! separator, then the secret), the same way `unit_tests/substrate_parity.rs`'s
//! SHA-256 known-answer vectors are pinned rather than derived from the code
//! under test.

use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use hierarchy_vor::VerifiedPromotion;

use crate::gate_policy::{evaluate_policy, policy_satisfied, GateName, GatePolicy, GateResult};
use crate::rule::{apply_with_policy, ConsequentialityVerdict, PromotionEvidence};
use crate::types::{ActionProposal, ClassifiedParameter, ConsumeMode, ReasonKind, TrustLevel};

// ---------------------------------------------------------------------------------
// Fixture plumbing: a real, valid `VerifiedPromotion` obtained through
// `hierarchy_vor::load_verified_promotion`'s public entry point only, never
// through any crate-internal shortcut. Every digest below is a pinned
// literal (see the module doc comment) so this file needs no dependency on
// `hierarchy-vor`'s own private attestation function.
// ---------------------------------------------------------------------------------

/// Bytes used as the fixture secret across this whole file. Written to a
/// scratch file outside the repository tree (REQ-15's own in-tree rejection
/// applies transitively through `hierarchy_vor::load_trusted_set_from_path`),
/// 48 bytes, comfortably over `hierarchy_vor::MIN_SECRET_BYTES` (32).
const FIXTURE_SECRET: &[u8] = b"boundary-gjoll-ac14-fixture-secret-32-bytes!!";
const FIXTURE_AUTHORISER: &str = "test-authoriser-fixture";

/// The base, fully-valid fixture (the one AC-14 pins as THE pass case):
/// assertion_id="v", content_digest="deadbeef", promoted_to="TRUSTED",
/// window [100, 200], attested under `FIXTURE_SECRET` and `FIXTURE_AUTHORISER`.
/// Pinned attestation, computed offline (see module doc comment).
const PASS_ATTESTATION: &str =
    "886cd53042d5b31655bd8191f17279d5c4feb5b7d9bfe52a01e58c488a39abca";

/// Same fixture fields, but attested with `assertion_id = "other"` instead of
/// `"v"` (AC-15 case 15b: the witness binds a DIFFERENT assertion id).
const DIFFERENT_ASSERTION_ID_ATTESTATION: &str =
    "2f6c02fadfec57f92b1b2370f464f70c101c56fb914f82ee1abda74d38c28d2c";

/// Same fixture fields, but attested with `content_digest = "beefdead"`
/// instead of `"deadbeef"` (AC-15 case 15c: the witness binds a digest that
/// does not match the caller-supplied digest).
const DIFFERENT_CONTENT_DIGEST_ATTESTATION: &str =
    "b4307e44b881c391ff2225471c58310d96eb8b20009c2e2e43b7f743ded4cd8c";

/// Same fixture fields, but attested with `promoted_to = "VOUCHED"` (AC-15
/// case 15d: below `TRUSTED_THRESHOLD` by rank).
const VOUCHED_LEVEL_ATTESTATION: &str =
    "fdbfa16274e8fee226fc67d2fe8e7834dd8657ca59be23f7d881143f3505a2fd";

/// Same fixture fields, but attested with `promoted_to = "OMNISCIENT"` (AC-15
/// case 15e: not one of the four lattice level names at all).
const UNRANKABLE_LEVEL_ATTESTATION: &str =
    "3ff25b7ff1c542297310845cb8b502e1b8c9b64e8142f9c4af888efbc1f6e96f";

fn temp_scratch_dir(label: &str) -> PathBuf {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock before the Unix epoch")
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("boundary-gjoll-gate-policy-{label}-{nanos}"));
    fs::create_dir_all(&dir).expect("failed to create a scratch dir under the system temp dir");
    dir
}

#[cfg(unix)]
fn write_secret_file(path: &Path, content: &[u8]) {
    use std::os::unix::fs::PermissionsExt;
    fs::write(path, content).expect("failed to write fixture secret file");
    fs::set_permissions(path, fs::Permissions::from_mode(0o600))
        .expect("failed to set fixture secret file permissions");
}

#[cfg(unix)]
fn trusted_set() -> hierarchy_vor::TrustedAuthoriserSet {
    let dir = temp_scratch_dir("trusted-set");
    let path = dir.join("secret");
    write_secret_file(&path, FIXTURE_SECRET);
    hierarchy_vor::load_trusted_set_from_path(FIXTURE_AUTHORISER, &path)
        .expect("the fixture secret file must load")
}

/// Loads a `VerifiedPromotion` through the crate's one public entry point,
/// with the window fixed at `[100, 200]` and `now = 150` (safely inside the
/// window for every case that must succeed at the verification layer, AC-22).
#[cfg(unix)]
fn load_witness(
    assertion_id: &str,
    content_digest: &str,
    promoted_to: &str,
    attestation: &str,
) -> VerifiedPromotion {
    let trusted = trusted_set();
    hierarchy_vor::load_verified_promotion(
        assertion_id,
        content_digest,
        promoted_to,
        100,
        200,
        FIXTURE_AUTHORISER,
        attestation,
        &trusted,
        150,
    )
    .unwrap_or_else(|e| {
        panic!(
            "fixture witness (assertion_id={assertion_id:?}, content_digest={content_digest:?}, \
             promoted_to={promoted_to:?}) failed to verify: {e:?}; this fixture is meant to \
             verify at the SUBSTRATE layer even when it fails the GATE's own policy check \
             (assertion-id / content-digest / rank matching is the gate's job, not the \
             substrate's)"
        )
    })
}

fn action_critical_param(assertion_id: &str, trust_level: TrustLevel) -> ClassifiedParameter {
    ClassifiedParameter {
        assertion_id: assertion_id.to_string(),
        type_name: "comms:promotable_value".to_string(),
        trust_level,
        action_critical: true,
    }
}

// ---------------------------------------------------------------------------------
// AC-10: GateName is a closed, four-variant enum naming the four gates, with
// no string conversion of any kind.
// ---------------------------------------------------------------------------------

#[test]
fn ac10_gate_name_has_exactly_the_four_named_variants() {
    // Exhaustive match: if a fifth variant is ever added, this match arm set
    // fails to compile, which is the point (Open/Closed, spec section 7.1).
    let names = [
        GateName::PromotionRequirement,
        GateName::Corroboration,
        GateName::Rederivation,
        GateName::SemanticConstraint,
    ];
    for name in names {
        match name {
            GateName::PromotionRequirement
            | GateName::Corroboration
            | GateName::Rederivation
            | GateName::SemanticConstraint => {}
        }
    }
}

// AC-10's "no public From<&str>/FromStr/TryFrom<String>" clause cannot be
// asserted by a runtime test (there is nothing to call); it is checked by the
// implementing agent's own compile-time confirmation, recorded in the PR
// description per the spec's section 13, V-18-style discipline. Recorded
// here as a comment so the obligation is not silently dropped:
//
//   An attempt such as `let _: GateName = "corroboration".try_into().unwrap();`
//   or `GateName::from_str("corroboration")` must fail to compile (E0277 or
//   E0599), because GateName implements no such trait. Left commented, per
//   this crate's own `tests/public_surface.rs`-adjacent precedent in
//   hierarchy-vor for exactly this reason: keeping this crate building at
//   all requires this block to never be uncommented in the committed file.

// ---------------------------------------------------------------------------------
// AC-11: a conjunction. A policy requiring two gates, satisfying only one,
// must not pass.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn ac11_conjunction_one_satisfied_one_unimplemented_does_not_pass() {
    let policy = GatePolicy::new(vec![GateName::PromotionRequirement, GateName::Corroboration]);
    let param = action_critical_param("v", TrustLevel::Tainted);
    let witness = load_witness("v", "deadbeef", "TRUSTED", PASS_ATTESTATION);

    let results = evaluate_policy(&policy, &param, "deadbeef", Some(&witness));

    assert!(
        !policy_satisfied(&results),
        "AC-11: a policy requiring PromotionRequirement AND Corroboration must not \
         be satisfied when only PromotionRequirement passes; got {results:?}"
    );
    assert!(
        results
            .iter()
            .any(|r| matches!(r, GateResult::Passed { gate: GateName::PromotionRequirement })),
        "AC-11: PromotionRequirement must appear as Passed; got {results:?}"
    );
    assert!(
        results.iter().any(|r| matches!(
            r,
            GateResult::Blocked { gate: GateName::Corroboration, .. }
        )),
        "AC-11: Corroboration must appear as Blocked; got {results:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-12: an empty required-gate set BLOCKs, even with fully valid evidence.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn ac12_empty_required_gate_set_never_passes_even_with_valid_evidence() {
    let policy = GatePolicy::new(vec![]);
    let param = action_critical_param("v", TrustLevel::Tainted);
    let witness = load_witness("v", "deadbeef", "TRUSTED", PASS_ATTESTATION);

    let results = evaluate_policy(&policy, &param, "deadbeef", Some(&witness));
    assert!(
        !policy_satisfied(&results),
        "AC-12: an empty required-gate set must never be satisfied, regardless of \
         evidence; got {results:?}"
    );
}

#[test]
fn ac12_policy_satisfied_is_false_on_an_empty_results_slice() {
    // EC-26: an empty evaluation list (the state produced by the unchanged
    // three-argument `evaluate`/`apply`) must never be read as "the gate
    // passed".
    assert!(
        !policy_satisfied(&[]),
        "policy_satisfied on an empty results slice must be false (EC-26)"
    );
}

// ---------------------------------------------------------------------------------
// AC-13: the three unimplemented gates each BLOCK with a reason naming them,
// even with fully valid promotion evidence present, and policy_satisfied is
// false.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn ac13_each_unimplemented_gate_blocks_alone_even_with_valid_promotion_evidence() {
    let param = action_critical_param("v", TrustLevel::Tainted);
    let witness = load_witness("v", "deadbeef", "TRUSTED", PASS_ATTESTATION);

    for gate in [GateName::Corroboration, GateName::Rederivation, GateName::SemanticConstraint] {
        let policy = GatePolicy::new(vec![gate]);
        let results = evaluate_policy(&policy, &param, "deadbeef", Some(&witness));
        assert!(
            !policy_satisfied(&results),
            "AC-13: {gate:?} alone must never be satisfied (it is specified and \
             unimplemented); got {results:?}"
        );
        assert!(
            results.iter().any(|r| match r {
                GateResult::Blocked { gate: g, reason } => *g == gate && !reason.is_empty(),
                _ => false,
            }),
            "AC-13: {gate:?} must appear as Blocked with a non-empty reason naming it \
             unimplemented; got {results:?}"
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-15: the six independent block conditions (15a to 15f), each a single
// substitution against the AC-14 pass fixture.
// ---------------------------------------------------------------------------------

#[test]
fn ac15_case_a_no_witness_supplied_blocks() {
    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let param = action_critical_param("v", TrustLevel::Tainted);
    let results = evaluate_policy(&policy, &param, "deadbeef", None);
    assert!(
        !policy_satisfied(&results),
        "AC-15a: no VerifiedPromotion supplied at all (the live state today) must \
         BLOCK; got {results:?}"
    );
}

#[cfg(unix)]
#[test]
fn ac15_case_b_witness_binds_different_assertion_id_blocks() {
    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let param = action_critical_param("v", TrustLevel::Tainted);
    // The witness is bound to "other", not "v".
    let witness =
        load_witness("other", "deadbeef", "TRUSTED", DIFFERENT_ASSERTION_ID_ATTESTATION);

    let results = evaluate_policy(&policy, &param, "deadbeef", Some(&witness));
    assert!(
        !policy_satisfied(&results),
        "AC-15b: a witness binding a different assertion_id than the parameter under \
         evaluation must BLOCK; got {results:?}"
    );
}

#[cfg(unix)]
#[test]
fn ac15_case_c_witness_binds_mismatched_content_digest_blocks() {
    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let param = action_critical_param("v", TrustLevel::Tainted);
    // The witness is bound to content_digest "beefdead"; the caller supplies
    // "deadbeef" as the parameter's own content digest below.
    let witness =
        load_witness("v", "beefdead", "TRUSTED", DIFFERENT_CONTENT_DIGEST_ATTESTATION);

    let results = evaluate_policy(&policy, &param, "deadbeef", Some(&witness));
    assert!(
        !policy_satisfied(&results),
        "AC-15c: a witness binding a content_digest that does not match the \
         caller-supplied digest must BLOCK; got {results:?}"
    );
}

#[cfg(unix)]
#[test]
fn ac15_case_d_witness_promotes_to_vouched_blocks() {
    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let param = action_critical_param("v", TrustLevel::Tainted);
    let witness = load_witness("v", "deadbeef", "VOUCHED", VOUCHED_LEVEL_ATTESTATION);

    let results = evaluate_policy(&policy, &param, "deadbeef", Some(&witness));
    assert!(
        !policy_satisfied(&results),
        "AC-15d: a witness promoting to VOUCHED (below TRUSTED_THRESHOLD by rank) \
         must BLOCK; got {results:?}"
    );
}

#[cfg(unix)]
#[test]
fn ac15_case_e_witness_promotes_to_unrankable_level_string_blocks() {
    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let param = action_critical_param("v", TrustLevel::Tainted);
    let witness = load_witness("v", "deadbeef", "OMNISCIENT", UNRANKABLE_LEVEL_ATTESTATION);

    let results = evaluate_policy(&policy, &param, "deadbeef", Some(&witness));
    assert!(
        !policy_satisfied(&results),
        "AC-15e: a witness promoting to a level string that is not one of the four \
         lattice level names must BLOCK (unrankable earns no positive match); got \
         {results:?}"
    );
}

#[test]
fn ac15_case_f_self_declared_trust_level_with_no_witness_blocks() {
    // The polarity criterion: a self-declared trust level must never earn the
    // pass. The parameter's own trust_level is Trusted (as if the proposer
    // set it directly), but no witness is supplied and the policy still
    // requires the promotion gate.
    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let param = action_critical_param("v", TrustLevel::Trusted);

    let results = evaluate_policy(&policy, &param, "deadbeef", None);
    assert!(
        !policy_satisfied(&results),
        "AC-15f: a self-declared Trusted trust_level with no witness supplied must \
         BLOCK; the parameter's own trust_level field must not be sufficient on its \
         own under any circumstances; got {results:?}"
    );

    // Also with Canonical, the highest level, to close the case fully.
    let param_canonical = action_critical_param("v", TrustLevel::Canonical);
    let results_canonical = evaluate_policy(&policy, &param_canonical, "deadbeef", None);
    assert!(
        !policy_satisfied(&results_canonical),
        "AC-15f: a self-declared Canonical trust_level with no witness supplied must \
         also BLOCK; got {results_canonical:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-16: `policy` is a plain reference on every new signature, never Option.
// This is checked at compile time by the mere fact these calls type-check
// without `Some(&policy)` or `.unwrap()` anywhere on the policy argument.
// ---------------------------------------------------------------------------------

#[test]
fn ac16_evaluate_policy_takes_policy_as_a_plain_reference() {
    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let param = action_critical_param("v", TrustLevel::Tainted);
    // If `evaluate_policy`'s `policy` parameter were `Option<&GatePolicy>`,
    // this call would not compile without wrapping `&policy` in `Some(..)`.
    let _results = evaluate_policy(&policy, &param, "deadbeef", None);
}

// ---------------------------------------------------------------------------------
// AC-17: GateResult's passed-ness is a variant, not a boolean field; no
// Default, no From<bool>.
// ---------------------------------------------------------------------------------

#[test]
fn ac17_gate_result_passed_ness_is_a_variant_not_a_bool_field() {
    let passed = GateResult::Passed { gate: GateName::PromotionRequirement };
    let blocked = GateResult::Blocked {
        gate: GateName::Corroboration,
        reason: "unimplemented".to_string(),
    };
    // If GateResult carried a `passed: bool` field readable independently of
    // the variant, code like `passed.passed` would compile; it must not.
    match passed {
        GateResult::Passed { gate } => assert_eq!(gate, GateName::PromotionRequirement),
        GateResult::Blocked { .. } => panic!("expected Passed"),
    }
    match blocked {
        GateResult::Blocked { gate, reason } => {
            assert_eq!(gate, GateName::Corroboration);
            assert!(!reason.is_empty());
        }
        GateResult::Passed { .. } => panic!("expected Blocked"),
    }
}

// ---------------------------------------------------------------------------------
// AC-26: the D89-A launder test. A gate policy and valid promotion evidence
// must NOT launder a CONSUME_INERT declaration that contradicts the flow
// graph.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn ac26_gate_policy_does_not_launder_a_d89a_inert_contradiction() {
    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let witness = load_witness("v", "deadbeef", "TRUSTED", PASS_ATTESTATION);
    let evidence = PromotionEvidence::new().with("v".to_string(), "deadbeef".to_string(), &witness);

    let proposal = ActionProposal {
        action_id: "ac26-launder-attempt".to_string(),
        sink: "sink:payments.execute".to_string(),
        consumes: [("v".to_string(), ConsumeMode::Inert)].into_iter().collect(),
        declared_safe: true,
    };
    let classified: HashMap<String, ClassifiedParameter> =
        [("v".to_string(), action_critical_param("v", TrustLevel::Tainted))]
            .into_iter()
            .collect();

    let decision = apply_with_policy(
        ConsequentialityVerdict::new(true),
        &proposal,
        &classified,
        &policy,
        &evidence,
    );

    assert!(
        !decision.authorised,
        "AC-26: a CONSUME_INERT declaration that contradicts the flow graph (D89-A) \
         must remain blocked even when a gate policy and fully valid promotion \
         evidence for the exact same parameter and digest are present"
    );
    assert!(
        decision
            .reasons
            .iter()
            .any(|r| r.kind == ReasonKind::InertContradictsReachability),
        "AC-26: InertContradictsReachability must still be present; got {:?}",
        decision.reasons,
    );
}

// ---------------------------------------------------------------------------------
// AC-28: the rule core stays pure and total; two independently-violating
// parameters raise two reasons, not one; no panic on empty maps or on
// evidence keys matching no parameter.
// ---------------------------------------------------------------------------------

#[cfg(unix)]
#[test]
fn ac28_two_independently_violating_parameters_raise_two_reasons() {
    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let evidence = PromotionEvidence::new(); // deliberately empty: nothing satisfies anything

    let proposal = ActionProposal {
        action_id: "ac28-two-violations".to_string(),
        sink: "sink:payments.execute".to_string(),
        consumes: [
            ("a".to_string(), ConsumeMode::Action),
            ("b".to_string(), ConsumeMode::Action),
        ]
        .into_iter()
        .collect(),
        declared_safe: false,
    };
    let classified: HashMap<String, ClassifiedParameter> = [
        ("a".to_string(), action_critical_param("a", TrustLevel::Tainted)),
        ("b".to_string(), action_critical_param("b", TrustLevel::Tainted)),
    ]
    .into_iter()
    .collect();

    let decision = apply_with_policy(
        ConsequentialityVerdict::new(true),
        &proposal,
        &classified,
        &policy,
        &evidence,
    );

    assert!(!decision.authorised, "AC-28: both violating parameters must block");
    assert_eq!(
        decision.reasons.len(),
        2,
        "AC-28: the rule core must not short-circuit; two independently violating \
         parameters must raise two reasons, not one; got {:?}",
        decision.reasons,
    );
}

#[cfg(unix)]
#[test]
fn ac28_empty_consumes_and_empty_classified_and_unmatched_evidence_never_panics() {
    let policy = GatePolicy::new(vec![GateName::PromotionRequirement]);
    let witness = load_witness("v", "deadbeef", "TRUSTED", PASS_ATTESTATION);
    // Evidence keyed to a parameter ("v") that appears in NEITHER consumes NOR
    // classified below (EC-19: unmatched evidence is inert, never a wildcard
    // pass, and must never panic).
    let evidence =
        PromotionEvidence::new().with("v".to_string(), "deadbeef".to_string(), &witness);

    let proposal = ActionProposal {
        action_id: "ac28-empty".to_string(),
        sink: "sink:whatever".to_string(),
        consumes: HashMap::new(),
        declared_safe: true,
    };
    let classified: HashMap<String, ClassifiedParameter> = HashMap::new();

    let decision = apply_with_policy(
        ConsequentialityVerdict::new(true),
        &proposal,
        &classified,
        &policy,
        &evidence,
    );

    // No panic occurred (the test having reached this line at all is the
    // primary assertion); an empty consumes map raises no reason, so the
    // decision authorises.
    assert!(
        decision.authorised,
        "an empty consumes map raises no reason and must authorise trivially"
    );
}
