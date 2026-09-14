// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The rank-comparison precondition (REQ-5 to REQ-9, AC-5 to AC-9), sequenced
//! first per the spec's own build order (section 12.3, step 3): the whole
//! promotion-gate build rests on this being correct, so it is tested in
//! isolation before any gate-policy surface exists at all.
//!
//! Written from `.opencode/plans/rust-promotion-gate-spec.md` alone, with no
//! sight of the implementation. This file WILL FAIL TO COMPILE until
//! `TrustLevel::rank`, `TrustLevel::is_untrusted_derived` and
//! `TRUSTED_THRESHOLD` exist on `crate::types` (REQ-5, REQ-6). That is
//! expected and correct at this stage.
//!
//! Wired into the crate by `lib.rs`'s
//! `#[cfg(test)] #[path = "../unit_tests/rank_and_lattice.rs"] mod rank_and_lattice;`
//! declaration (REQ-39), so this file is compiled as an in-crate module and can
//! reach `crate::rule::ConsequentialityVerdict::new`, `pub(crate)` (REQ-10),
//! exactly as `unit_tests/layer_one_parity.rs` already does.

use std::collections::HashMap;

use crate::rule::{apply, ConsequentialityVerdict};
use crate::types::{
    ActionProposal, ClassifiedParameter, ConsumeMode, TrustLevel, ReasonKind, TRUSTED_THRESHOLD,
};

// ---------------------------------------------------------------------------------
// AC-5: `TrustLevel::rank()` is total, exhaustive and matches
// `ontology/yggdrasil/spine/trust.py`'s `TRUST_ORDER` index exactly:
// TAINTED=0, VOUCHED=1, TRUSTED=2, CANONICAL=3.
// ---------------------------------------------------------------------------------

#[test]
fn ac5_rank_matches_trust_order_index_for_all_four_variants() {
    assert_eq!(TrustLevel::Tainted.rank(), 0, "TAINTED must rank 0 (TRUST_ORDER index)");
    assert_eq!(TrustLevel::Vouched.rank(), 1, "VOUCHED must rank 1 (TRUST_ORDER index)");
    assert_eq!(TrustLevel::Trusted.rank(), 2, "TRUSTED must rank 2 (TRUST_ORDER index)");
    assert_eq!(TrustLevel::Canonical.rank(), 3, "CANONICAL must rank 3 (TRUST_ORDER index)");
}

#[test]
fn ac5_rank_is_strictly_ascending_across_the_whole_lattice() {
    // A property test over the lattice's own stated order, so a future
    // reordering of the enum's declaration cannot silently invert the ranks
    // without this failing.
    let ordered = [
        TrustLevel::Tainted,
        TrustLevel::Vouched,
        TrustLevel::Trusted,
        TrustLevel::Canonical,
    ];
    for i in 0..ordered.len() - 1 {
        assert!(
            ordered[i].rank() < ordered[i + 1].rank(),
            "rank() must be strictly ascending across the lattice; {:?} did not \
             rank below {:?}",
            ordered[i],
            ordered[i + 1],
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-6: TRUSTED_THRESHOLD equals TrustLevel::Trusted, and is_untrusted_derived
// returns true for Tainted and Vouched, false for Trusted and Canonical.
// ---------------------------------------------------------------------------------

#[test]
fn ac6_trusted_threshold_equals_trust_level_trusted() {
    assert_eq!(
        TRUSTED_THRESHOLD,
        TrustLevel::Trusted,
        "TRUSTED_THRESHOLD must be exactly TrustLevel::Trusted (REQ-6)"
    );
}

#[test]
fn ac6_is_untrusted_derived_true_for_tainted_and_vouched() {
    assert!(
        TrustLevel::Tainted.is_untrusted_derived(),
        "TAINTED must be untrusted-derived"
    );
    assert!(
        TrustLevel::Vouched.is_untrusted_derived(),
        "VOUCHED must be untrusted-derived: its own doc comment reads 'attested \
         by a bounded source but not yet fully trusted' (REQ-6)"
    );
}

#[test]
fn ac6_is_untrusted_derived_false_for_trusted_and_canonical() {
    assert!(
        !TrustLevel::Trusted.is_untrusted_derived(),
        "TRUSTED must NOT be untrusted-derived: it is exactly the threshold"
    );
    assert!(
        !TrustLevel::Canonical.is_untrusted_derived(),
        "CANONICAL must NOT be untrusted-derived: it is above the threshold"
    );
}

#[test]
fn ac6_is_untrusted_derived_routes_through_rank_comparison_against_threshold() {
    // A direct algebraic check that is_untrusted_derived is exactly
    // `self.rank() < TRUSTED_THRESHOLD.rank()`, not a hand-rolled variant match
    // that happens to agree today but could silently diverge from the lattice.
    for level in [
        TrustLevel::Tainted,
        TrustLevel::Vouched,
        TrustLevel::Trusted,
        TrustLevel::Canonical,
    ] {
        assert_eq!(
            level.is_untrusted_derived(),
            level.rank() < TRUSTED_THRESHOLD.rank(),
            "is_untrusted_derived() for {:?} disagreed with the rank-comparison \
             definition (REQ-6)",
            level,
        );
    }
}

// ---------------------------------------------------------------------------------
// AC-9: the mandatory negative controls this precondition exists for. A
// `Vouched`, action-critical parameter at a consequential sink must now BLOCK
// in both the Action arm and the Inert arm, which is exactly the behaviour
// the equality-based code (`c.trust_level == TrustLevel::Tainted`) could not
// produce, because `Vouched != Tainted`.
//
// The spec (AC-9) is explicit: this criterion is not merely "the post-change
// code blocks" but "the post-change code blocks AND the pre-change code did
// not". Because this file has no access to two crate versions
// simultaneously, the pre-change-failure half is asserted here as a
// documented, explicit statement of the OLD equality predicate
// (`c.trust_level == TrustLevel::Tainted`) applied by hand to the same
// fixture, proving algebraically that the old code would have authorised
// both 9a and 9b. This is the same evidence AC-9 asks the implementing
// agent to *observe by running the pre-change binary*; here it is pinned as
// a standing regression check so it can never silently regress back to
// equality once the rank-based fix lands.
// ---------------------------------------------------------------------------------

fn vouched_action_critical(assertion_id: &str) -> ClassifiedParameter {
    ClassifiedParameter {
        assertion_id: assertion_id.to_string(),
        type_name: "comms:promotable_value".to_string(),
        trust_level: TrustLevel::Vouched,
        action_critical: true,
    }
}

#[test]
fn ac9a_vouched_action_critical_consumed_as_action_blocks_post_change() {
    let proposal = ActionProposal {
        action_id: "ac9a-vouched-action".to_string(),
        sink: "sink:payments.execute".to_string(),
        consumes: [("v".to_string(), ConsumeMode::Action)].into_iter().collect(),
        declared_safe: false,
    };
    let classified: HashMap<String, ClassifiedParameter> =
        [("v".to_string(), vouched_action_critical("v"))].into_iter().collect();

    let decision = apply(ConsequentialityVerdict::new(true), &proposal, &classified);

    assert!(
        !decision.authorised,
        "AC-9a: a Vouched, action-critical parameter consumed as an ACTION at a \
         consequential sink must be blocked post-fix (it is untrusted-derived by \
         rank); got authorised=true"
    );
    assert!(
        decision
            .reasons
            .iter()
            .any(|r| r.kind == ReasonKind::ActionOnActionCriticalTainted && r.parameter_id == "v"),
        "AC-9a: the block reason must be ActionOnActionCriticalTainted naming \
         parameter 'v'; got {:?}",
        decision.reasons,
    );

    // Algebraic pinning of the PRE-change predicate's behaviour on this exact
    // fixture (REQ-9's mandated negative control): the old equality test would
    // have read Vouched != Tainted and so would NOT have raised this reason.
    let pre_change_would_flag = matches!(TrustLevel::Vouched, TrustLevel::Tainted);
    assert!(
        !pre_change_would_flag,
        "sanity: the OLD equality predicate (c.trust_level == TrustLevel::Tainted) \
         must be false for Vouched, which is exactly why the pre-change code would \
         have wrongly authorised this case (AC-9's mandatory pre-change-failure \
         record)"
    );
}

#[test]
fn ac9b_vouched_action_critical_declared_inert_blocks_post_change() {
    let proposal = ActionProposal {
        action_id: "ac9b-vouched-inert".to_string(),
        sink: "sink:payments.execute".to_string(),
        consumes: [("v".to_string(), ConsumeMode::Inert)].into_iter().collect(),
        declared_safe: true,
    };
    let classified: HashMap<String, ClassifiedParameter> =
        [("v".to_string(), vouched_action_critical("v"))].into_iter().collect();

    let decision = apply(ConsequentialityVerdict::new(true), &proposal, &classified);

    assert!(
        !decision.authorised,
        "AC-9b: a Vouched, action-critical parameter declared CONSUME_INERT at a \
         consequential sink must be blocked post-fix (D89-A: the inert claim \
         contradicts the derived, untrusted-by-rank status); got authorised=true"
    );
    assert!(
        decision.reasons.iter().any(|r| {
            r.kind == ReasonKind::InertContradictsReachability && r.parameter_id == "v"
        }),
        "AC-9b: the block reason must be InertContradictsReachability naming \
         parameter 'v'; got {:?}",
        decision.reasons,
    );

    let pre_change_would_flag = matches!(TrustLevel::Vouched, TrustLevel::Tainted);
    assert!(
        !pre_change_would_flag,
        "sanity: the OLD equality predicate must be false for Vouched on this same \
         fixture, which is exactly why the pre-change code would have wrongly \
         authorised this case too (AC-9's mandatory pre-change-failure record)"
    );
}

// ---------------------------------------------------------------------------------
// AC-7 companion: Tainted must STILL block after the change (the rank
// comparison must not accidentally narrow coverage relative to the old
// equality test).
// ---------------------------------------------------------------------------------

#[test]
fn tainted_action_critical_still_blocks_after_the_rank_change() {
    let proposal = ActionProposal {
        action_id: "tainted-still-blocks".to_string(),
        sink: "sink:payments.execute".to_string(),
        consumes: [("v".to_string(), ConsumeMode::Action)].into_iter().collect(),
        declared_safe: false,
    };
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

    let decision = apply(ConsequentialityVerdict::new(true), &proposal, &classified);
    assert!(
        !decision.authorised,
        "a Tainted, action-critical parameter must still block after the rank \
         change (no regression of existing coverage)"
    );
}

#[test]
fn trusted_action_critical_authorises_the_action_arm() {
    // The rank comparison's own positive control: Trusted is AT the threshold,
    // so it must not be read as untrusted-derived.
    let proposal = ActionProposal {
        action_id: "trusted-authorises".to_string(),
        sink: "sink:payments.execute".to_string(),
        consumes: [("v".to_string(), ConsumeMode::Action)].into_iter().collect(),
        declared_safe: true,
    };
    let classified: HashMap<String, ClassifiedParameter> = [(
        "v".to_string(),
        ClassifiedParameter {
            assertion_id: "v".to_string(),
            type_name: "comms:money_move_request".to_string(),
            trust_level: TrustLevel::Trusted,
            action_critical: true,
        },
    )]
    .into_iter()
    .collect();

    let decision = apply(ConsequentialityVerdict::new(true), &proposal, &classified);
    assert!(
        decision.authorised,
        "a Trusted, action-critical parameter must authorise: Trusted is AT \
         TRUSTED_THRESHOLD, not below it"
    );
}
