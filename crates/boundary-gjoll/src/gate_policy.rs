// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The gate-policy surface (section 3.3, REQ-10 to REQ-16;
//! `.opencode/plans/rust-promotion-gate-spec.md` section 4.1's `gate_policy.rs`
//! illustrative signatures).
//!
//! [`GateName`] names the four re-validation gates of `plans/dd/gjoll.md`
//! section 5 by closed **variant**, never by string constant. Naming by
//! closed enum variant makes the Python "unrecognised gate string" case
//! (Python REQ-36) structurally unrepresentable rather than merely refused,
//! which is a stronger property: there is no `FromStr`, `TryFrom<String>`
//! or `From<&str>` implementation for this type anywhere in this crate, so
//! there is no string to be unrecognised in the first place (REQ-10).
//!
//! [`GatePolicy`] names a **required-gate set**, read as a **conjunction**:
//! a value passes the policy only when it passes every gate that policy
//! names (REQ-11). `plans/dd/gjoll.md` section 5's "at least one gate" is
//! read here as "not zero", never as a disjunction over the named set.
//!
//! An **empty** required-gate set BLOCKs (REQ-12): [`policy_satisfied`]
//! returns `false` on an empty results slice, and [`evaluate_policy`]
//! produces an empty results slice exactly when the policy's required-gate
//! set is empty (it iterates that set to produce results, one per gate).
//! There is no constructor, `Default` impl or conversion anywhere in this
//! module that could produce a `GatePolicy` whose required-gate set is
//! empty and which then passes: silence never earns a pass.
//!
//! [`GateResult`] carries passed-ness as a **variant**, not a boolean field:
//! `Passed { gate }` on the pass side, `Blocked { gate, reason }` on the
//! block side. No `Default`, no `From<bool>`, and no field readable as
//! "passed" independently of the variant (REQ-16).
//!
//! [`evaluate_policy`] dispatches exhaustively over [`GateName`]'s four
//! variants with **no wildcard arm** (REQ-13): `Corroboration`,
//! `Rederivation` and `SemanticConstraint` are specified and not
//! implemented, and each BLOCKs unconditionally with a reason naming it as
//! unimplemented, even when fully valid promotion evidence is present. Only
//! `PromotionRequirement` has a real pass path, and it PASSES only when all
//! four of REQ-14's conditions hold together: a [`hierarchy_vor::VerifiedPromotion`]
//! witness is supplied; that witness binds the exact `assertion_id` of the
//! parameter under evaluation; that witness binds a content digest matching
//! the caller-supplied `content_digest`; and the witness's promoted-to
//! level, parsed against the four known `TrustLevel` variant name strings
//! ("TAINTED", "VOUCHED", "TRUSTED", "CANONICAL", matching
//! `ontology/yggdrasil/spine/trust.py`'s `TRUST_ORDER` tuple exactly), ranks
//! at or above [`crate::types::TRUSTED_THRESHOLD`]. Any unmatched string is
//! unrankable and BLOCKs; the parameter's own `trust_level` field is never
//! consulted by this check under any circumstances (REQ-14).
//!
//! `policy` reaches every function in this module as a **plain reference**,
//! never an `Option`, never defaulted (REQ-15, GJ-6). `promotion` is
//! `Option<&VerifiedPromotion>` because absent evidence is a real, expected,
//! live-today state that must BLOCK, not because the policy itself may be
//! absent.

use crate::types::{ClassifiedParameter, TRUSTED_THRESHOLD, TrustLevel};

/// The four re-validation gates of `plans/dd/gjoll.md` section 5, named by
/// closed variant (REQ-10). Adding a fifth variant forces every exhaustive
/// match over this enum in the crate to be revisited, which is deliberate
/// (spec section 7.1's Open/Closed note).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum GateName {
    /// The one gate this build implements: REQ-14.
    PromotionRequirement,
    /// Specified, NOT implemented. Always BLOCKs (REQ-13).
    Corroboration,
    /// Specified, NOT implemented. Always BLOCKs (REQ-13).
    Rederivation,
    /// Specified, NOT implemented. Always BLOCKs (REQ-13).
    SemanticConstraint,
}

/// A required-gate set, read as a conjunction (REQ-11): a value passes this
/// policy only when it passes every gate named here. Private field, so the
/// only way to build one is [`GatePolicy::new`], and the only way to widen
/// or narrow one afterwards is to build a new value: there is no in-place
/// mutator that could silently empty the set after construction.
///
/// No `Default` impl exists for this type (REQ-12): a caller must always
/// name the gates they require, explicitly, and an empty `Vec` passed to
/// [`GatePolicy::new`] is a genuine, representable, and always-blocking
/// policy, never an accidental default.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GatePolicy {
    required_gates: Vec<GateName>,
}

impl GatePolicy {
    /// Builds a policy naming exactly `required_gates` as the conjunction
    /// a value must satisfy in full. An empty `Vec` is accepted and
    /// produces a policy that [`policy_satisfied`] can never report as
    /// satisfied (REQ-12).
    pub fn new(required_gates: Vec<GateName>) -> Self {
        GatePolicy { required_gates }
    }

    /// Read-only access to the required-gate set.
    pub fn required_gates(&self) -> &[GateName] {
        &self.required_gates
    }
}

/// The outcome of evaluating one gate against one parameter (REQ-16).
/// Passed-ness is a variant, not a boolean field readable independently of
/// it: there is no `Default` and no `From<bool>` anywhere on this type, so
/// there is no construction path that yields an accidental pass.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GateResult {
    /// The named gate was satisfied for this parameter.
    Passed { gate: GateName },
    /// The named gate was not satisfied, with the reason a human reviewer
    /// reads.
    Blocked { gate: GateName, reason: String },
}

/// Parses `s` against the four known `TrustLevel` variant name strings,
/// exactly matching `ontology/yggdrasil/spine/trust.py`'s `TRUST_ORDER`
/// tuple's own spelling. Any unmatched string is treated as unrankable and
/// returns `None`, never a fallback rank: an opaque promotion string this
/// crate does not recognise must never be silently treated as trusted, nor
/// as untrusted by coincidence -- it is simply unrankable, and the caller
/// (REQ-14) treats "unrankable" as a block.
fn parse_trust_level_name(s: &str) -> Option<TrustLevel> {
    match s {
        "TAINTED" => Some(TrustLevel::Tainted),
        "VOUCHED" => Some(TrustLevel::Vouched),
        "TRUSTED" => Some(TrustLevel::Trusted),
        "CANONICAL" => Some(TrustLevel::Canonical),
        _ => None,
    }
}

/// Evaluates the promotion-requirement gate alone (REQ-14). PASSES only when
/// all four conditions hold together; any single failure BLOCKs with a
/// reason naming which condition failed. The parameter's own `trust_level`
/// field is never read here: it is deliberately excluded from this
/// function's reasoning, so a self-declared trust level can never be
/// sufficient on its own (AC-15f).
fn evaluate_promotion_requirement(
    parameter: &ClassifiedParameter,
    content_digest: &str,
    promotion: Option<&hierarchy_vor::VerifiedPromotion>,
) -> GateResult {
    let witness = match promotion {
        Some(w) => w,
        None => {
            return GateResult::Blocked {
                gate: GateName::PromotionRequirement,
                reason: "no VerifiedPromotion was supplied for this parameter".to_string(),
            };
        }
    };

    if witness.assertion_id() != parameter.assertion_id {
        return GateResult::Blocked {
            gate: GateName::PromotionRequirement,
            reason: format!(
                "the supplied VerifiedPromotion binds assertion_id {:?}, which does not \
                 match the parameter under evaluation's own assertion_id {:?}",
                witness.assertion_id(),
                parameter.assertion_id,
            ),
        };
    }

    if witness.content_digest() != content_digest {
        return GateResult::Blocked {
            gate: GateName::PromotionRequirement,
            reason: format!(
                "the supplied VerifiedPromotion binds content_digest {:?}, which does not \
                 match the caller-supplied content_digest {:?}",
                witness.content_digest(),
                content_digest,
            ),
        };
    }

    let promoted_level = match parse_trust_level_name(witness.promoted_to()) {
        Some(level) => level,
        None => {
            return GateResult::Blocked {
                gate: GateName::PromotionRequirement,
                reason: format!(
                    "the supplied VerifiedPromotion's promoted_to value {:?} does not match \
                     any of the four known TrustLevel names (TAINTED, VOUCHED, TRUSTED, \
                     CANONICAL); an unrecognised level is unrankable and BLOCKs",
                    witness.promoted_to(),
                ),
            };
        }
    };

    if promoted_level.rank() < TRUSTED_THRESHOLD.rank() {
        return GateResult::Blocked {
            gate: GateName::PromotionRequirement,
            reason: format!(
                "the supplied VerifiedPromotion promotes to {:?}, which ranks below the \
                 required threshold {:?}",
                witness.promoted_to(),
                TRUSTED_THRESHOLD,
            ),
        };
    }

    GateResult::Passed {
        gate: GateName::PromotionRequirement,
    }
}

/// Evaluates every gate named in `policy.required_gates()` against
/// `parameter`, returning one [`GateResult`] per gate (REQ-11). `policy` is
/// a plain reference, never `Option` (REQ-15). `promotion` is
/// `Option<&VerifiedPromotion>`, because absent evidence is a real,
/// expected, live-today state, not an error at this layer -- it simply
/// fails the promotion-requirement gate.
///
/// Dispatch over [`GateName`] is exhaustive with no wildcard arm (REQ-13):
/// adding a fifth gate variant forces this match to be revisited rather
/// than silently defaulting to permissive or restrictive behaviour.
pub fn evaluate_policy(
    policy: &GatePolicy,
    parameter: &ClassifiedParameter,
    content_digest: &str,
    promotion: Option<&hierarchy_vor::VerifiedPromotion>,
) -> Vec<GateResult> {
    policy
        .required_gates()
        .iter()
        .map(|gate| match gate {
            GateName::PromotionRequirement => {
                evaluate_promotion_requirement(parameter, content_digest, promotion)
            }
            GateName::Corroboration => GateResult::Blocked {
                gate: GateName::Corroboration,
                reason: "the corroboration gate is specified, not implemented".to_string(),
            },
            GateName::Rederivation => GateResult::Blocked {
                gate: GateName::Rederivation,
                reason: "the re-derivation gate is specified, not implemented".to_string(),
            },
            GateName::SemanticConstraint => GateResult::Blocked {
                gate: GateName::SemanticConstraint,
                reason: "the semantic-constraint gate is specified, not implemented".to_string(),
            },
        })
        .collect()
}

/// True iff `results` is non-empty and every element is [`GateResult::Passed`]
/// (REQ-11, REQ-12). An empty slice is `false`: silence never earns a pass.
pub fn policy_satisfied(results: &[GateResult]) -> bool {
    !results.is_empty()
        && results
            .iter()
            .all(|r| matches!(r, GateResult::Passed { .. }))
}
