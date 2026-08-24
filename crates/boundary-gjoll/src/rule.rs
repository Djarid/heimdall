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
    ActionProposal, ClassifiedParameter, ConsumeMode, GateDecision, Reason, ReasonKind, TrustLevel,
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
                    let untrusted_derived = c.trust_level == TrustLevel::Tainted;
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
                    let untrusted_derived = c.trust_level == TrustLevel::Tainted;
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
    }
}
