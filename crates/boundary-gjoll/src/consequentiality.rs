// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The registry-mandatory consequentiality shell (layer two, D109, spec section
//! 5.1, REQ-13). Produces an authorisation decision from a registry-backed
//! proposal by validating (`declaration::validate_proposal`, D81), deriving
//! (`declaration::intrinsically_consequential`, D89-B) and then delegating to the
//! pure rule core (`rule::apply`). No code path here reaches a verdict without a
//! registry: the registry parameter of `evaluate` is a plain reference, never an
//! `Option`, and there is no branch that derives consequentiality from anything
//! else (no stamp, no per-agent set, no D100 classify-time union).
//!
//! This file contains **no test bytes at all** (REQ-24): no `#[test]`, no `mod
//! tests`, no fixture and no double. Its replay lives in
//! `crates/boundary-gjoll/tests/layer_two_parity.rs` and
//! `crates/boundary-gjoll/tests/native_failclosed.rs`.

use std::collections::HashMap;

use crate::declaration::{SinkRegistry, intrinsically_consequential, validate_proposal};
use crate::rule::{ConsequentialityVerdict, PromotionEvidence, apply, apply_with_policy};
use crate::types::{ActionProposal, ClassifiedParameter, ConsumeMode, GateDecision};

/// The provenance of one verdict's derivation (REQ-17). Exactly **two**
/// constructible variants exist in this build.
///
/// D93's behavioural effect-probe cross-check -- confirming a sink's declared
/// effect primitive against what it is actually observed to do at runtime -- is
/// a third, named source. It is **reserved and not built**: no variant for it
/// exists on this enum, and no function anywhere in this crate accepts an
/// effect-observation argument. Admitting it is step three or later's job (D93),
/// and when it lands it is a new variant added here, which is the one dimension
/// `consequentiality` is designed to be open to (spec section 7.1's Open/Closed
/// note).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConsequentialitySource {
    /// The sink was declared, and its consequentiality was derived from its
    /// declared effect primitive (D89-B), never from a per-sink boolean.
    DeclaredPrimitive,
    /// The sink was not declared at all; consequentiality fails closed to
    /// consequential (D81).
    UndeclaredFailClosed,
}

/// Derive the consequentiality verdict for `sink` from the registry alone
/// (REQ-15). Fails closed in all three silence cases named on
/// `declaration::intrinsically_consequential`'s own doc comment: an undeclared
/// sink, a declaration carrying no primitive, and a declaration carrying an
/// unrecognised primitive string. A declared inert primitive is the only way to
/// earn non-consequential.
fn derive_consequentiality(
    sink: &str,
    registry: &SinkRegistry,
) -> (ConsequentialityVerdict, ConsequentialitySource) {
    match registry.get(sink) {
        None => (
            ConsequentialityVerdict::new(true),
            ConsequentialitySource::UndeclaredFailClosed,
        ),
        Some(declaration) => {
            let consequential = intrinsically_consequential(Some(declaration));
            (
                ConsequentialityVerdict::new(consequential),
                ConsequentialitySource::DeclaredPrimitive,
            )
        }
    }
}

/// The mode vocabulary as raw strings, mirroring `sink_declaration.py`'s own
/// `CONSUME_ACTION` / `CONSUME_INERT` constants. Used only to hand an
/// already-parsed `ConsumeMode` back to `validate_proposal`'s raw-string
/// signature (REQ-9's closed enum and D81's raw-string validation are two
/// different layers; this is the seam between them).
fn consume_mode_to_str(mode: ConsumeMode) -> String {
    match mode {
        ConsumeMode::Action => "ACTION".to_string(),
        ConsumeMode::Inert => "INERT".to_string(),
    }
}

/// The crate's public gate entry point (REQ-13). The registry parameter is a
/// plain reference, never `Option`: there is no code path here that reaches a
/// verdict without one, and the Python no-registry branch plus D100's
/// stamp-derived consequentiality do not exist in this crate in any form.
///
/// Runs D81 validation (`declaration::validate_proposal`) **first**. A
/// validation failure returns a blocked decision carrying only
/// declaration-invalid reasons, and `rule::apply` is never called on that path
/// (REQ-14): the rule is not merely skipped in effect, it is not reached in
/// control flow.
///
/// Only once validation passes does this derive consequentiality from the
/// declared effect primitive (REQ-15) and delegate to the pure rule core
/// (`rule::apply`), which is the only place in this crate that can construct
/// the resulting `GateDecision`'s reasons for a rule violation.
pub fn evaluate(
    proposal: &ActionProposal,
    classified: &HashMap<String, ClassifiedParameter>,
    registry: &SinkRegistry,
) -> GateDecision {
    let known_ids: std::collections::HashSet<String> = classified.keys().cloned().collect();
    let consumes_raw: HashMap<String, String> = proposal
        .consumes
        .iter()
        .map(|(param_id, mode)| (param_id.clone(), consume_mode_to_str(*mode)))
        .collect();

    let validation = validate_proposal(&proposal.sink, &consumes_raw, registry, &known_ids);
    if !validation.reasons.is_empty() {
        // D81 validation failed: block here, before the rule is ever applied.
        return GateDecision {
            action_id: proposal.action_id.clone(),
            authorised: false,
            reasons: validation.reasons,
            gate_evaluations: Vec::new(),
        };
    }

    let (verdict, _source) = derive_consequentiality(&proposal.sink, registry);
    apply(verdict, proposal, classified)
}

/// The policy-aware consequentiality shell (REQ-26; spec section 4.1).
/// Identical to [`evaluate`] except that, once D81 validation passes, it
/// delegates to [`apply_with_policy`] (not [`apply`]) with `policy` and
/// `evidence`. The D81 validation stage still runs FIRST and is still
/// unreachable-past on failure: a validation failure returns a blocked
/// decision carrying only declaration-invalid reasons and an empty
/// `gate_evaluations`, and `apply_with_policy` -- and therefore the policy
/// and the evidence -- is never reached in control flow on that path.
pub fn evaluate_with_policy(
    proposal: &ActionProposal,
    classified: &HashMap<String, ClassifiedParameter>,
    registry: &SinkRegistry,
    policy: &crate::gate_policy::GatePolicy,
    evidence: &PromotionEvidence<'_>,
) -> GateDecision {
    let known_ids: std::collections::HashSet<String> = classified.keys().cloned().collect();
    let consumes_raw: HashMap<String, String> = proposal
        .consumes
        .iter()
        .map(|(param_id, mode)| (param_id.clone(), consume_mode_to_str(*mode)))
        .collect();

    let validation = validate_proposal(&proposal.sink, &consumes_raw, registry, &known_ids);
    if !validation.reasons.is_empty() {
        // D81 validation failed: block here, before the rule -- and
        // therefore the policy and the evidence -- is ever reached.
        return GateDecision {
            action_id: proposal.action_id.clone(),
            authorised: false,
            reasons: validation.reasons,
            gate_evaluations: Vec::new(),
        };
    }

    let (verdict, _source) = derive_consequentiality(&proposal.sink, registry);
    apply_with_policy(verdict, proposal, classified, policy, evidence)
}
