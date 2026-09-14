// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The pure rule core (layer one) for the `boundary-gjoll` re-expression (D109,
//! spec section 5.1, REQ-7). Re-expresses the three-condition rule plus the D89-A
//! inert-contradiction check from `ontology/nornir/gjoll.py::evaluate`'s per-
//! parameter loop, against an already-resolved consequentiality verdict.
//!
//! This file contains **no test bytes at all** (REQ-24): no `#[test]`, no `mod
//! tests`, no fixture and no double. Its replay lives in a separate file in a
//! separate directory, `crates/boundary-gjoll/unit_tests/layer_one_parity.rs`.

use std::collections::HashMap;

use crate::types::{
    ActionProposal, ClassifiedParameter, ConsumeMode, GateDecision, Reason, ReasonKind,
};

/// An already-resolved consequentiality verdict: whether the proposal's sink is
/// consequential for this agent. Constructible **only from inside the crate**
/// (REQ-10): no public constructor, no public `From` conversion, no test-only
/// feature flag or `cfg` escape hatch a downstream caller could enable. `pub(crate)`
/// rather than module-private so the separated unit-test file (REQ-24, compiled as
/// `crate::layer_one_parity` via `lib.rs`'s `#[path]` declaration) can reach it
/// without any visibility widening.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ConsequentialityVerdict(bool);

impl ConsequentialityVerdict {
    /// `pub(crate)`: only code compiled as part of this crate (the shell in
    /// `consequentiality.rs`, and the in-crate unit-test module) can mint a
    /// verdict. A downstream caller depending on `boundary_gjoll` as a library has
    /// no path to this constructor (REQ-10, AC-10).
    pub(crate) fn new(consequential: bool) -> Self {
        Self(consequential)
    }

    /// Public reader: whether the sink this verdict was derived for is
    /// consequential.
    pub fn is_consequential(&self) -> bool {
        self.0
    }
}

/// The rule core's single public entry point (REQ-7). Pure and total: no input or
/// output, no mutable global state, and no panic on any input reachable through
/// this signature (REQ-12). Reads exactly the four `ClassifiedParameter` fields
/// (REQ-8); the sink registry, the agent consequential-sink set, `declared_safe`,
/// the D100 classify-time stamp and effect observations are all structurally
/// unreachable from here, because none of them appear in this function's
/// signature or in `ClassifiedParameter` itself.
///
/// The rule, mirroring `ontology/nornir/gjoll.py::evaluate`'s per-parameter loop
/// exactly: a consequential action is blocked if, and only if, it consumes as an
/// ACTION some parameter that is an untrusted-derived (TAINTED), action-critical
/// value (the three-condition rule) -- or if it declares such a value CONSUME_INERT
/// at a consequential sink, which contradicts the value's own derived flow-
/// reachability and is not trusted over it (D89-A). A parameter absent from
/// `classified` is unknown-origin: consumed as an action that is
/// no-known-provenance (fail closed); consumed as inert it is genuinely inert (no
/// provenance to make it action-critical), so no reason is raised. The loop never
/// short-circuits (EC-10): every parameter is evaluated and contributes its own
/// reason, so a reviewer sees every cause, not only the first.
pub fn apply(
    verdict: ConsequentialityVerdict,
    proposal: &ActionProposal,
    classified: &HashMap<String, ClassifiedParameter>,
) -> GateDecision {
    let mut reasons: Vec<Reason> = Vec::new();

    for (param_id, mode) in &proposal.consumes {
        let c = classified.get(param_id);

        match mode {
            ConsumeMode::Inert => {
                // D89-A: an inert claim on a value flow-reachability has already
                // proved action-critical, at a consequential sink, contradicts the
                // flow graph and is not trusted over it. A parameter with no
                // provenance at all has nothing to contradict: it is genuinely
                // inert.
                if let Some(c) = c {
                    let untrusted_derived = c.trust_level.is_untrusted_derived();
                    if verdict.is_consequential() && untrusted_derived && c.action_critical {
                        reasons.push(Reason {
                            kind: ReasonKind::InertContradictsReachability,
                            parameter_id: param_id.clone(),
                            sink: proposal.sink.clone(),
                            detail: format!(
                                "consequential sink {:?} declares untrusted-derived, \
                                 action-critical value {:?} (type {}) as CONSUME_INERT, \
                                 which contradicts its flow reachability to a \
                                 consequential effect; the inert claim is not trusted \
                                 over the derived action-critical status (fail closed, \
                                 D89-A)",
                                proposal.sink, param_id, c.type_name,
                            ),
                        });
                    }
                }
            }
            ConsumeMode::Action => match c {
                None => {
                    // Unknown-origin: no known provenance. Fail closed regardless
                    // of the verdict (AC-12).
                    reasons.push(Reason {
                        kind: ReasonKind::NoKnownProvenance,
                        parameter_id: param_id.clone(),
                        sink: proposal.sink.clone(),
                        detail: format!(
                            "parameter {param_id:?} consumed as ACTION has no known \
                             provenance; fail closed"
                        ),
                    });
                }
                Some(c) => {
                    let untrusted_derived = c.trust_level.is_untrusted_derived();
                    if verdict.is_consequential() && untrusted_derived && c.action_critical {
                        reasons.push(Reason {
                            kind: ReasonKind::ActionOnActionCriticalTainted,
                            parameter_id: param_id.clone(),
                            sink: proposal.sink.clone(),
                            detail: format!(
                                "consequential sink {:?} consumes untrusted-derived, \
                                 action-critical value {:?} (type {}) as an ACTION \
                                 instruction",
                                proposal.sink, param_id, c.type_name,
                            ),
                        });
                    }
                }
            },
        }
    }

    let authorised = reasons.is_empty();
    GateDecision {
        action_id: proposal.action_id.clone(),
        authorised,
        reasons,
        gate_evaluations: Vec::new(),
    }
}

/// The evidence bundle threaded into [`apply_with_policy`] (spec section 4.1):
/// `assertion_id -> (content_digest, verified promotion)`. A plain reference
/// on `apply_with_policy`'s own signature, never an `Option` (REQ-15). An
/// **empty** bundle is the live state today -- nothing in a deployment can
/// mint a promotion yet -- and an empty bundle BLOCKs every action-critical,
/// untrusted-derived parameter exactly as before, which is the point (REQ-30).
pub struct PromotionEvidence<'a> {
    entries: HashMap<String, (String, &'a hierarchy_vor::VerifiedPromotion)>,
}

impl<'a> PromotionEvidence<'a> {
    /// An empty bundle: no promotion evidence for any assertion id.
    pub fn new() -> Self {
        PromotionEvidence {
            entries: HashMap::new(),
        }
    }

    /// Consuming builder: returns `self` with one more `assertion_id` bound
    /// to `(content_digest, promotion)`. A later `.with()` call for the same
    /// `assertion_id` overwrites the earlier entry.
    pub fn with(
        mut self,
        assertion_id: String,
        content_digest: String,
        promotion: &'a hierarchy_vor::VerifiedPromotion,
    ) -> Self {
        self.entries
            .insert(assertion_id, (content_digest, promotion));
        self
    }

    /// Looks up the evidence bound to `assertion_id`, if any.
    fn get(&self, assertion_id: &str) -> Option<(&str, &'a hierarchy_vor::VerifiedPromotion)> {
        self.entries
            .get(assertion_id)
            .map(|(digest, promotion)| (digest.as_str(), *promotion))
    }
}

impl<'a> Default for PromotionEvidence<'a> {
    fn default() -> Self {
        Self::new()
    }
}

/// The policy-aware rule core (REQ-25, REQ-27; spec section 4.1). Identical
/// to [`apply`] in every respect -- including the D89-A `Inert` arm, which no
/// gate policy or promotion evidence may ever launder (REQ-25) -- **except**
/// that in the `Action` arm, a parameter that would otherwise BLOCK as
/// [`ReasonKind::ActionOnActionCriticalTainted`] is given one further chance:
/// its `assertion_id` is looked up in `evidence`, [`crate::gate_policy::evaluate_policy`]
/// is called against `policy` with that entry's content digest and witness
/// (or `None` if no entry exists), and if
/// [`crate::gate_policy::policy_satisfied`] reports `true` for the resulting
/// evaluations, that parameter PASSES instead of blocking. Otherwise it
/// still blocks with its original reason, unchanged.
///
/// The loop never short-circuits (REQ-27): every parameter is evaluated and
/// contributes its own reason (or none), regardless of what any other
/// parameter's own gate evaluation produced.
pub fn apply_with_policy(
    verdict: ConsequentialityVerdict,
    proposal: &ActionProposal,
    classified: &HashMap<String, ClassifiedParameter>,
    policy: &crate::gate_policy::GatePolicy,
    evidence: &PromotionEvidence<'_>,
) -> GateDecision {
    let mut reasons: Vec<Reason> = Vec::new();
    let mut gate_evaluations: Vec<crate::gate_policy::GateResult> = Vec::new();

    for (param_id, mode) in &proposal.consumes {
        let c = classified.get(param_id);

        match mode {
            ConsumeMode::Inert => {
                // REQ-25: the D89-A block is NOT passable by any gate policy
                // or promotion evidence, under any circumstances. This arm
                // is byte-identical to `apply`'s own Inert arm.
                if let Some(c) = c {
                    let untrusted_derived = c.trust_level.is_untrusted_derived();
                    if verdict.is_consequential() && untrusted_derived && c.action_critical {
                        reasons.push(Reason {
                            kind: ReasonKind::InertContradictsReachability,
                            parameter_id: param_id.clone(),
                            sink: proposal.sink.clone(),
                            detail: format!(
                                "consequential sink {:?} declares untrusted-derived, \
                                 action-critical value {:?} (type {}) as CONSUME_INERT, \
                                 which contradicts its flow reachability to a \
                                 consequential effect; the inert claim is not trusted \
                                 over the derived action-critical status (fail closed, \
                                 D89-A)",
                                proposal.sink, param_id, c.type_name,
                            ),
                        });
                    }
                }
            }
            ConsumeMode::Action => match c {
                None => {
                    // Unknown-origin: no known provenance. Fail closed
                    // regardless of the verdict, the policy, or any
                    // evidence.
                    reasons.push(Reason {
                        kind: ReasonKind::NoKnownProvenance,
                        parameter_id: param_id.clone(),
                        sink: proposal.sink.clone(),
                        detail: format!(
                            "parameter {param_id:?} consumed as ACTION has no known \
                             provenance; fail closed"
                        ),
                    });
                }
                Some(c) => {
                    let untrusted_derived = c.trust_level.is_untrusted_derived();
                    if verdict.is_consequential() && untrusted_derived && c.action_critical {
                        // This parameter would otherwise BLOCK. Consult the
                        // gate policy with whatever evidence (if any) is
                        // bound to this exact assertion id.
                        let (content_digest, promotion) = match evidence.get(&c.assertion_id) {
                            Some((digest, promotion)) => (digest, Some(promotion)),
                            None => ("", None),
                        };
                        let results = crate::gate_policy::evaluate_policy(
                            policy,
                            c,
                            content_digest,
                            promotion,
                        );
                        gate_evaluations.extend(results.clone());
                        if !crate::gate_policy::policy_satisfied(&results) {
                            reasons.push(Reason {
                                kind: ReasonKind::ActionOnActionCriticalTainted,
                                parameter_id: param_id.clone(),
                                sink: proposal.sink.clone(),
                                detail: format!(
                                    "consequential sink {:?} consumes untrusted-derived, \
                                     action-critical value {:?} (type {}) as an ACTION \
                                     instruction, and the gate policy was not satisfied \
                                     for it",
                                    proposal.sink, param_id, c.type_name,
                                ),
                            });
                        }
                    }
                }
            },
        }
    }

    let authorised = reasons.is_empty();
    GateDecision {
        action_id: proposal.action_id.clone(),
        authorised,
        reasons,
        gate_evaluations,
    }
}
