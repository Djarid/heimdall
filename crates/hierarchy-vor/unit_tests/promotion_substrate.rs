// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The promotion-record substrate and its verification (REQ-17 to REQ-24;
//! AC-18 to AC-20, AC-22's window cases, AC-23's four refusals, AC-25's nine
//! content cases). Written from `.opencode/plans/rust-promotion-gate-spec.md`
//! alone, with no sight of the implementation.
//!
//! THIS FILE WILL FAIL TO COMPILE until `crate::promotion::{PromotionRecord,
//! RECORD_TYPE_PROMOTION, PromotionRefusal, VerifiedPromotion,
//! load_verified_promotion}` exist and `crate::promotion` is declared as a
//! module from `lib.rs` (REQ-17, REQ-21). That is expected and correct at
//! this stage.
//!
//! Wired into the crate by `lib.rs`'s
//! `#[cfg(test)] #[path = "../unit_tests/promotion_substrate.rs"] mod promotion_substrate;`
//! declaration (REQ-39): an in-crate module, exactly like
//! `unit_tests/substrate_parity.rs`, so it can call
//! `crate::record::compute_record_attestation` and `crate::record::AttestedRecord`
//! directly to build fixtures, rather than pinning attestation digests as
//! literals (the external-crate promotion surface test does that instead,
//! for exactly the reason `tests/public_surface.rs`'s header already states
//! for the cohort).

use std::fs;
use std::path::PathBuf;

use serde::Deserialize;

use crate::authoriser::TrustedAuthoriserSet;
use crate::promotion::{
    load_verified_promotion, PromotionRecord, PromotionRefusal, RECORD_TYPE_PROMOTION,
};
use crate::record::{compute_record_attestation, AttestedRecord};
use crate::types::CohortDefinition;
use crate::verify::RecordRefusal;

/// A fixture secret used only inside this file (section 2.2: mechanism
/// parity is exercised under a fixture secret, never the real one).
const FIXTURE_SECRET: &[u8] = b"promotion-substrate-unit-test-fixture-secret-48b";
const FIXTURE_AUTHORISER: &str = "promotion-fixture-authoriser";

fn trusted_set() -> TrustedAuthoriserSet {
    TrustedAuthoriserSet {
        authorisers: [(FIXTURE_AUTHORISER.to_string(), FIXTURE_SECRET.to_vec())]
            .into_iter()
            .collect(),
    }
}

fn base_record() -> PromotionRecord {
    PromotionRecord {
        assertion_id: "v".to_string(),
        content_digest: "deadbeef".to_string(),
        promoted_to: "TRUSTED".to_string(),
        valid_from: 100,
        valid_until: 200,
        authoriser: Some(FIXTURE_AUTHORISER.to_string()),
        attestation: None,
    }
}

fn attested(mut record: PromotionRecord, secret: &[u8]) -> PromotionRecord {
    let attestation = compute_record_attestation(&record, secret);
    record.attestation = Some(attestation);
    record
}

// ---------------------------------------------------------------------------------
// AC-18: record_type() and canonical_fields(), and promoted_to's opacity.
// ---------------------------------------------------------------------------------

#[test]
fn ac18_record_type_is_exactly_promotion_record() {
    let record = base_record();
    assert_eq!(
        record.record_type(),
        "promotion_record",
        "record_type() must equal the Python authorisation_record.py \
         RECORD_TYPE_PROMOTION constant exactly, character for character"
    );
    assert_eq!(
        RECORD_TYPE_PROMOTION, "promotion_record",
        "the crate's own RECORD_TYPE_PROMOTION constant must equal \"promotion_record\""
    );
}

#[test]
fn ac18_canonical_fields_returns_exactly_six_pairs_in_fixed_order() {
    let record = base_record();
    let fields = record.canonical_fields();
    assert_eq!(
        fields.len(),
        6,
        "canonical_fields() must return exactly six pairs (no fifth content field, \
         plus authoriser; attestation itself excluded); got {fields:?}"
    );
    let names: Vec<&str> = fields.iter().map(|(n, _)| *n).collect();
    assert_eq!(
        names,
        vec![
            "assertion_id",
            "content_digest",
            "promoted_to",
            "valid_from",
            "valid_until",
            "authoriser",
        ],
        "canonical_fields() must return the six fields in the fixed order of spec \
         section 4.3's table; got {names:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-19: the vector-file byte-parity replay. An absent vector file is a
// FAILURE, never a skip (EC-11's own discipline, transferred): a missing
// oracle is not a passing oracle.
// ---------------------------------------------------------------------------------

#[derive(Deserialize)]
struct PromotionVectorFile {
    #[allow(dead_code)]
    schema_version: u32,
    fixture_secret_hex: String,
    vectors: Vec<PromotionVector>,
}

#[derive(Deserialize)]
struct PromotionVector {
    id: String,
    fields: Vec<(String, String)>,
    canonical_bytes_hex: String,
    attestation: Option<String>,
}

fn promotion_vector_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("vectors")
        .join("promotion_vectors.json")
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

fn decode_hex(s: &str) -> Vec<u8> {
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).expect("invalid hex byte in vector fixture"))
        .collect()
}

fn leak_str(s: String) -> &'static str {
    Box::leak(s.into_boxed_str())
}

struct VectorRecord {
    fields: Vec<(&'static str, String)>,
}

impl AttestedRecord for VectorRecord {
    fn record_type(&self) -> &'static str {
        RECORD_TYPE_PROMOTION
    }
    fn canonical_fields(&self) -> Vec<(&'static str, String)> {
        self.fields.clone()
    }
}

#[test]
fn ac19_promotion_vectors_replay_bytes_then_digest() {
    let path = promotion_vector_path();
    let raw = fs::read_to_string(&path).unwrap_or_else(|e| {
        panic!(
            "promotion_substrate: could not read \
             crates/hierarchy-vor/vectors/promotion_vectors.json ({e}); this vector \
             file is produced by ontology/tools/export_cohort_vectors.py's additive \
             promotion-record emission section (REQ-42) and does not exist yet at \
             this stage of the build. EC-11: an absent oracle is a FAILURE, never a \
             skip."
        )
    });
    let data: PromotionVectorFile = serde_json::from_str(&raw)
        .unwrap_or_else(|e| panic!("promotion_vectors.json did not parse: {e}"));
    assert!(!data.vectors.is_empty(), "promotion_vectors.json carries no vectors at all");

    let fixture_secret = decode_hex(&data.fixture_secret_hex);

    for v in &data.vectors {
        let record = VectorRecord {
            fields: v
                .fields
                .iter()
                .map(|(n, val)| (leak_str(n.clone()), val.clone()))
                .collect(),
        };
        let bytes = crate::record::canonical_record_bytes(&record);
        assert_eq!(
            hex_encode(&bytes),
            v.canonical_bytes_hex,
            "vector {}: canonical bytes diverge from the Python export",
            v.id,
        );
        if let Some(expected_attestation) = &v.attestation {
            let attestation = compute_record_attestation(&record, &fixture_secret);
            assert_eq!(
                &attestation, expected_attestation,
                "vector {}: attestation diverges from the Python export under the \
                 committed fixture secret",
                v.id,
            );
        }
    }
}

// ---------------------------------------------------------------------------------
// AC-20: cross-type replay separation in both directions, even under the
// same authoriser and the same secret.
// ---------------------------------------------------------------------------------

#[test]
fn ac20_cohort_attestation_does_not_verify_as_a_promotion_record() {
    let cohort = CohortDefinition {
        cohort_id: "cross-type-fixture".to_string(),
        permitted_actions: vec!["action:git.commit".to_string()],
        trust_ceiling: "TAINTED".to_string(),
        consequential_sinks: vec!["sink:git.commit".to_string()],
        authoriser: Some(FIXTURE_AUTHORISER.to_string()),
        attestation: None,
    };
    let cohort_attestation = compute_record_attestation(&cohort, FIXTURE_SECRET);

    // Build a PromotionRecord with "otherwise-matching content" (same
    // authoriser, same secret) but presented with the cohort's attestation.
    let mut promotion = base_record();
    promotion.attestation = Some(cohort_attestation);

    let trusted = trusted_set();
    let outcome = crate::verify::verify_record(
        &promotion,
        promotion.authoriser.as_deref(),
        promotion.attestation.as_deref(),
        &trusted,
    );
    assert!(
        matches!(outcome, Err(RecordRefusal::DigestMismatch(_))),
        "AC-20: a CohortDefinition's attestation must not verify when presented as a \
         PromotionRecord's attestation, even under the same authoriser and secret; \
         got {outcome:?}"
    );
}

#[test]
fn ac20_promotion_attestation_does_not_verify_as_a_cohort_definition() {
    let promotion = attested(base_record(), FIXTURE_SECRET);
    let promotion_attestation = promotion.attestation.clone().unwrap();

    let mut cohort = CohortDefinition {
        cohort_id: "cross-type-fixture".to_string(),
        permitted_actions: vec!["action:git.commit".to_string()],
        trust_ceiling: "TAINTED".to_string(),
        consequential_sinks: vec!["sink:git.commit".to_string()],
        authoriser: Some(FIXTURE_AUTHORISER.to_string()),
        attestation: None,
    };
    cohort.attestation = Some(promotion_attestation);

    let trusted = trusted_set();
    let outcome = crate::verify::verify_record(
        &cohort,
        cohort.authoriser.as_deref(),
        cohort.attestation.as_deref(),
        &trusted,
    );
    assert!(
        matches!(outcome, Err(RecordRefusal::DigestMismatch(_))),
        "AC-20: a PromotionRecord's attestation must not verify when presented as a \
         CohortDefinition's attestation, even under the same authoriser and secret; \
         got {outcome:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-22: the validity window, boundaries inclusive, and the malformed-window
// refusal checked BEFORE any digest computation.
// ---------------------------------------------------------------------------------

#[test]
fn ac22_now_before_window_start_refuses_outside_validity_window() {
    let record = attested(base_record(), FIXTURE_SECRET); // window [100, 200]
    let trusted = trusted_set();
    let outcome = load_verified_promotion(
        &record.assertion_id,
        &record.content_digest,
        &record.promoted_to,
        record.valid_from,
        record.valid_until,
        FIXTURE_AUTHORISER,
        record.attestation.as_deref().unwrap(),
        &trusted,
        99,
    );
    assert!(
        matches!(outcome, Err(PromotionRefusal::OutsideValidityWindow(_))),
        "AC-22: now=99, one before valid_from=100, must refuse with \
         OutsideValidityWindow; got {outcome:?}"
    );
}

#[test]
fn ac22_now_after_window_end_refuses_outside_validity_window() {
    let record = attested(base_record(), FIXTURE_SECRET); // window [100, 200]
    let trusted = trusted_set();
    let outcome = load_verified_promotion(
        &record.assertion_id,
        &record.content_digest,
        &record.promoted_to,
        record.valid_from,
        record.valid_until,
        FIXTURE_AUTHORISER,
        record.attestation.as_deref().unwrap(),
        &trusted,
        201,
    );
    assert!(
        matches!(outcome, Err(PromotionRefusal::OutsideValidityWindow(_))),
        "AC-22: now=201, one past valid_until=200, must refuse with \
         OutsideValidityWindow; got {outcome:?}"
    );
}

#[test]
fn ac22_window_boundaries_are_inclusive() {
    let record = attested(base_record(), FIXTURE_SECRET); // window [100, 200]
    let trusted = trusted_set();
    for now in [100u64, 150u64, 200u64] {
        let outcome = load_verified_promotion(
            &record.assertion_id,
            &record.content_digest,
            &record.promoted_to,
            record.valid_from,
            record.valid_until,
            FIXTURE_AUTHORISER,
            record.attestation.as_deref().unwrap(),
            &trusted,
            now,
        );
        assert!(
            outcome.is_ok(),
            "AC-22: now={now} is within the inclusive window [100, 200] and must \
             verify; got {outcome:?}"
        );
    }
}

#[test]
fn ac22_malformed_window_refuses_before_any_digest_computation() {
    let mut record = base_record();
    record.valid_from = 100;
    record.valid_until = 50; // valid_until < valid_from: malformed
    // Deliberately NOT attested (empty authoriser/attestation would also
    // refuse for a different reason): to isolate this case, attest under a
    // WRONG secret so that, if the malformed-window check were skipped, the
    // digest check would refuse too, and the assertion below on the SPECIFIC
    // variant proves ordering, not merely "it failed somehow".
    let wrong_secret = b"a-completely-different-32-byte-secret-value!!!!";
    let attestation = compute_record_attestation(&record, wrong_secret);
    record.attestation = Some(attestation);

    let trusted = trusted_set();
    let outcome = load_verified_promotion(
        &record.assertion_id,
        &record.content_digest,
        &record.promoted_to,
        record.valid_from,
        record.valid_until,
        FIXTURE_AUTHORISER,
        record.attestation.as_deref().unwrap(),
        &trusted,
        150,
    );
    assert!(
        matches!(outcome, Err(PromotionRefusal::MalformedWindow(_))),
        "AC-22: valid_until < valid_from must refuse with MalformedWindow, checked \
         BEFORE any digest computation (so it must win over a wrong-secret digest \
         mismatch too); got {outcome:?}"
    );
}

// ---------------------------------------------------------------------------------
// AC-23: the four fail-closed verification cases, and no refusal reason
// string contains any byte of the secret.
// ---------------------------------------------------------------------------------

#[test]
fn ac23_empty_authoriser_refuses_unattested() {
    let record = attested(base_record(), FIXTURE_SECRET);
    let trusted = trusted_set();
    let outcome = load_verified_promotion(
        &record.assertion_id,
        &record.content_digest,
        &record.promoted_to,
        record.valid_from,
        record.valid_until,
        "", // empty authoriser
        record.attestation.as_deref().unwrap(),
        &trusted,
        150,
    );
    assert!(
        matches!(outcome, Err(PromotionRefusal::Verification(RecordRefusal::Unattested(_)))),
        "AC-23: an empty authoriser must refuse with Verification(Unattested(..)); \
         got {outcome:?}"
    );
}

#[test]
fn ac23_empty_attestation_refuses_unattested() {
    let record = base_record();
    let trusted = trusted_set();
    let outcome = load_verified_promotion(
        &record.assertion_id,
        &record.content_digest,
        &record.promoted_to,
        record.valid_from,
        record.valid_until,
        FIXTURE_AUTHORISER,
        "", // empty attestation
        &trusted,
        150,
    );
    assert!(
        matches!(outcome, Err(PromotionRefusal::Verification(RecordRefusal::Unattested(_)))),
        "AC-23: an empty attestation must refuse with Verification(Unattested(..)); \
         got {outcome:?}"
    );
}

#[test]
fn ac23_unknown_authoriser_refuses() {
    let record = attested(base_record(), FIXTURE_SECRET);
    let trusted = trusted_set();
    let outcome = load_verified_promotion(
        &record.assertion_id,
        &record.content_digest,
        &record.promoted_to,
        record.valid_from,
        record.valid_until,
        "an-authoriser-never-in-the-trusted-set",
        record.attestation.as_deref().unwrap(),
        &trusted,
        150,
    );
    assert!(
        matches!(
            outcome,
            Err(PromotionRefusal::Verification(RecordRefusal::UnknownAuthoriser(_)))
        ),
        "AC-23: an authoriser absent from the trusted set must refuse with \
         Verification(UnknownAuthoriser(..)); got {outcome:?}"
    );
}

#[test]
fn ac23_digest_mismatch_under_different_secret_refuses() {
    let wrong_secret = b"a-completely-different-32-byte-secret-value!!!!";
    let record = attested(base_record(), wrong_secret);
    let trusted = trusted_set(); // holds FIXTURE_SECRET, not wrong_secret
    let outcome = load_verified_promotion(
        &record.assertion_id,
        &record.content_digest,
        &record.promoted_to,
        record.valid_from,
        record.valid_until,
        FIXTURE_AUTHORISER,
        record.attestation.as_deref().unwrap(),
        &trusted,
        150,
    );
    assert!(
        matches!(
            outcome,
            Err(PromotionRefusal::Verification(RecordRefusal::DigestMismatch(_)))
        ),
        "AC-23: a digest computed under a different secret must refuse with \
         Verification(DigestMismatch(..)); got {outcome:?}"
    );
}

#[test]
fn ac23_no_refusal_reason_contains_any_byte_of_the_secret() {
    const CANARY_SECRET: &[u8] = b"AC23-CANARY-SECRET-NEVER-PRINTED-PADDED-TO-32B!";
    let record = attested(base_record(), CANARY_SECRET);
    let trusted = trusted_set(); // holds FIXTURE_SECRET, not CANARY_SECRET
    let outcome = load_verified_promotion(
        &record.assertion_id,
        &record.content_digest,
        &record.promoted_to,
        record.valid_from,
        record.valid_until,
        FIXTURE_AUTHORISER,
        record.attestation.as_deref().unwrap(),
        &trusted,
        150,
    );
    let rendered = format!("{outcome:?}");
    assert!(
        !rendered.contains("AC23-CANARY-SECRET"),
        "AC-23: a refusal's Debug output must never contain a byte of the secret; \
         got {rendered}"
    );
}

#[test]
fn ac23_no_refusal_ever_returns_a_degraded_or_partial_promotion() {
    // Structural: every branch above returns `Err(..)`, never a narrowed
    // `Ok(VerifiedPromotion)`. This test exists as a single place naming that
    // property explicitly, over one more refusal case (an authoriser known
    // to the trusted set but with a tampered field).
    let mut record = attested(base_record(), FIXTURE_SECRET);
    record.promoted_to = "CANONICAL".to_string(); // mutate after attestation
    let trusted = trusted_set();
    let outcome = load_verified_promotion(
        &record.assertion_id,
        &record.content_digest,
        &record.promoted_to,
        record.valid_from,
        record.valid_until,
        FIXTURE_AUTHORISER,
        record.attestation.as_deref().unwrap(),
        &trusted,
        150,
    );
    assert!(outcome.is_err(), "a tampered record must refuse, never verify degraded");
}

// ---------------------------------------------------------------------------------
// AC-25: nine content-integrity cases (a comma, a newline and an '=' in each
// of assertion_id, content_digest and promoted_to), refused BEFORE any
// attestation is computed or compared.
// ---------------------------------------------------------------------------------

#[test]
fn ac25_nine_forbidden_character_cases_refuse_with_content_integrity() {
    let trusted = trusted_set();
    let forbidden = [(",", "comma"), ("\n", "newline"), ("=", "equals")];
    let fields = ["assertion_id", "content_digest", "promoted_to"];

    for field in fields {
        for (ch, label) in forbidden {
            let mut record = base_record();
            match field {
                "assertion_id" => record.assertion_id = format!("v{ch}poisoned"),
                "content_digest" => record.content_digest = format!("dead{ch}beef"),
                "promoted_to" => record.promoted_to = format!("TRUSTED{ch}"),
                _ => unreachable!(),
            }
            // Deliberately NOT attested with a real digest: if the
            // implementation skipped the content check, this record would
            // still fail differently (Unattested), so the assertion below on
            // the SPECIFIC variant proves the content check runs first, not
            // merely that something failed.
            let outcome = load_verified_promotion(
                &record.assertion_id,
                &record.content_digest,
                &record.promoted_to,
                record.valid_from,
                record.valid_until,
                FIXTURE_AUTHORISER,
                "irrelevant-because-content-integrity-must-refuse-first",
                &trusted,
                150,
            );
            assert!(
                matches!(outcome, Err(PromotionRefusal::ContentIntegrity(_))),
                "AC-25: a {label} planted in {field} must refuse with \
                 ContentIntegrity BEFORE any attestation comparison; got {outcome:?}"
            );
        }
    }
}
