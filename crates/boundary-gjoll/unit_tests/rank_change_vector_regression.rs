// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! REQ-8, AC-8: proof that the rank-comparison change (REQ-7) cannot move any
//! of the 22 committed golden vectors, structurally rather than merely by
//! observing that the existing `unit_tests/layer_one_parity.rs` replay still
//! passes. `layer_one_parity.rs` already replays all 22 vectors end to end
//! against `rule::apply` and is left untouched by this build (it is an
//! existing, passing test); this file adds the complementary, narrower
//! check the spec's AC-8 calls for: that every committed vector's own
//! trust level is `TrustLevel::Tainted`, so `is_untrusted_derived()`
//! (rank-based, REQ-7) and the OLD equality test (`== TrustLevel::Tainted`)
//! necessarily agree on every one of them. This is what makes "the 22
//! vectors replay identically" a structural fact about this vector file's
//! own content, not a coincidence of the current implementation.
//!
//! Written from `.opencode/plans/rust-promotion-gate-spec.md` alone. THIS
//! FILE WILL FAIL TO COMPILE until `TrustLevel::is_untrusted_derived` exists
//! (REQ-6). Wired into the crate by `lib.rs`'s
//! `#[cfg(test)] #[path = "../unit_tests/rank_change_vector_regression.rs"] mod rank_change_vector_regression;`
//! declaration (REQ-39).

use std::fs;
use std::path::PathBuf;

use serde::Deserialize;

use crate::types::TrustLevel;

#[derive(Deserialize)]
struct VectorFile {
    expected_counts: ExpectedCounts,
    vectors: Vec<Vector>,
}

#[derive(Deserialize)]
struct ExpectedCounts {
    layer_one: usize,
}

#[derive(Deserialize)]
struct Vector {
    id: String,
    layer_one: LayerOneFixture,
}

#[derive(Deserialize)]
struct LayerOneFixture {
    classified: std::collections::HashMap<String, ClassifiedFixture>,
}

#[derive(Deserialize)]
struct ClassifiedFixture {
    trust_level: String,
}

fn vector_file_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("vectors").join("gate_vectors.json")
}

fn load_vectors() -> VectorFile {
    let raw = fs::read_to_string(vector_file_path()).unwrap_or_else(|e| {
        panic!(
            "rank_change_vector_regression: could not read gate_vectors.json ({e}); \
             REQ-8/AC-8: an absent oracle is a failure, never a skip"
        )
    });
    let data: VectorFile = serde_json::from_str(&raw)
        .unwrap_or_else(|e| panic!("gate_vectors.json did not parse: {e}"));
    assert_eq!(data.expected_counts.layer_one, 22, "expected_counts.layer_one has drifted from 22");
    data
}

fn trust_level_from_str(s: &str) -> TrustLevel {
    match s {
        "trust:TAINTED" => TrustLevel::Tainted,
        other => panic!(
            "rank_change_vector_regression: unrecognised trust level {other:?}; every \
             captured vector is Phase 1 tainted-by-origin"
        ),
    }
}

#[test]
fn ac8_every_committed_vector_carries_only_tainted_classified_parameters() {
    // REQ-8's own "no vector regeneration" guarantee rests on this: the rank
    // comparison and the old equality test can only diverge on Vouched,
    // Trusted or Canonical inputs. If every classified parameter in every
    // one of the 22 vectors is Tainted, the two predicates are provably
    // identical on this fixture set, and the replay CANNOT have moved.
    let data = load_vectors();
    assert_eq!(data.vectors.len(), 22, "gate_vectors.json does not carry exactly 22 vectors");

    for v in &data.vectors {
        for (param_id, c) in &v.layer_one.classified {
            let level = trust_level_from_str(&c.trust_level);
            assert_eq!(
                level,
                TrustLevel::Tainted,
                "vector {} ({}): a non-Tainted classified parameter exists in the \
                 committed vector set; REQ-8's structural rank-invariance argument \
                 no longer holds and the 22-vector replay must be re-examined by \
                 hand, not merely assumed unaffected",
                v.id,
                param_id,
            );
        }
    }
}

#[test]
fn ac8_rank_based_and_equality_based_untrusted_derivation_agree_on_tainted() {
    // The algebraic core of the structural argument above: for TrustLevel::
    // Tainted specifically, rank()-based is_untrusted_derived() and the OLD
    // `== TrustLevel::Tainted` equality test both evaluate to `true`. Paired
    // with the test above (every vector's parameters are Tainted), this
    // proves the 22 vectors cannot distinguish the pre-fix and post-fix
    // implementations.
    let old_equality_predicate = TrustLevel::Tainted == TrustLevel::Tainted;
    let new_rank_predicate = TrustLevel::Tainted.is_untrusted_derived();
    assert!(
        old_equality_predicate && new_rank_predicate,
        "REQ-8: the old equality predicate and the new rank predicate must both be \
         true for Tainted, which is the only level the committed vectors carry"
    );
}
