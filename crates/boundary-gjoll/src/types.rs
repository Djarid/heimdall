// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! Shared value types for the `boundary-gjoll` re-expression (D109, spec section
//! 5.1). Plain data shapes only, mirroring the Python dataclasses they re-express
//! (`ontology/nornir/gjoll.py`, `ontology/nornir/assertions.py`). No logic and no
//! test bytes (REQ-24): every type here is read and constructed, never matched on
//! for a decision (that is `rule.rs`'s and `consequentiality.rs`'s job).

use std::collections::HashMap;

/// How a sink consumes a parameter (REQ-9). Closed: exactly two variants, so an
/// unrecognised mode string is unrepresentable inside the rule core. Mirrors the
/// PoC's `CONSUME_INERT` / `CONSUME_ACTION` vocabulary (`poc/sinks.py`,
/// `ontology/nornir/gjoll.py`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ConsumeMode {
    /// Drives an effect: money moved, command run, mail sent.
    Action,
    /// Logged, stored or displayed; never acted upon.
    Inert,
}

/// The system-wide trust lattice (`ontology/yggdrasil/spine/trust.py`), ordered low
/// to high: TAINTED, VOUCHED, TRUSTED, CANONICAL. Every marshalled assertion is
/// TAINTED by origin in Phase 1 (the marshalling contract), which is the only level
/// the current gate vectors exercise, but the enum names the whole lattice rather
/// than only the one level in use today.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum TrustLevel {
    /// Untrusted-derived; the default for anything read from external content.
    Tainted,
    /// Attested by a bounded source but not yet fully trusted.
    Vouched,
    /// Promoted to trusted by a logged promotion event.
    Trusted,
    /// System-authored ground truth; the highest level.
    Canonical,
}

impl TrustLevel {
    /// This level's position in the lattice ordering TAINTED, VOUCHED, TRUSTED,
    /// CANONICAL, ascending from zero (REQ-5), matching
    /// `ontology/yggdrasil/spine/trust.py`'s `TRUST_ORDER` tuple exactly and in the
    /// same order. Total and exhaustive over all four variants: no wildcard arm, so
    /// a fifth variant added later fails the build rather than silently defaulting
    /// to a rank.
    pub fn rank(self) -> u8 {
        match self {
            TrustLevel::Tainted => 0,
            TrustLevel::Vouched => 1,
            TrustLevel::Trusted => 2,
            TrustLevel::Canonical => 3,
        }
    }

    /// Whether this level counts as untrusted-derived for the purpose of the
    /// three-condition rule (REQ-6, REQ-7): true for every level ranked strictly
    /// below [`TRUSTED_THRESHOLD`]. Defined as a direct rank comparison, never a
    /// hand-rolled variant match, so it cannot silently diverge from the lattice's
    /// own ordering.
    pub fn is_untrusted_derived(self) -> bool {
        self.rank() < TRUSTED_THRESHOLD.rank()
    }
}

/// The lowest trust level that counts as **trusted** for the purpose of the
/// three-condition rule (REQ-6). `Vouched`'s own documentation above reads
/// "attested by a bounded source but not yet fully trusted": that sentence is
/// exactly why `Vouched` sits below this threshold and a `Vouched` value is
/// untrusted-derived, alongside `Tainted`. Only `Trusted` and `Canonical`, at or
/// above this threshold by rank, count as trusted.
pub const TRUSTED_THRESHOLD: TrustLevel = TrustLevel::Trusted;

/// The narrow, four-field re-expression of `ClassifiedAssertion` the rule core is
/// allowed to see (REQ-8). Deliberately **not** a full re-expression: the rule must
/// not receive the sink registry, the agent consequential-sink set, the proposal's
/// `declared_safe` flag, the D100 classify-time stamp, or effect observations, and
/// keeping this struct to exactly these four fields is what makes that a property
/// of the type system rather than of review.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClassifiedParameter {
    pub assertion_id: String,
    /// For reporting only; the rule never branches on this.
    pub type_name: String,
    pub trust_level: TrustLevel,
    pub action_critical: bool,
}

/// An agent proposing to fire a consequential action at a sink (mirrors
/// `ontology/nornir/gjoll.py::ActionProposal`). `declared_safe` records the
/// author's intent for reporting only and lives here, never on the rule's own
/// signature (REQ-8): the gate does not trust it, it re-derives authorisation from
/// the consumption mode, the parameter's provenance and its action-critical
/// status.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ActionProposal {
    pub action_id: String,
    /// The consequential-sink node id.
    pub sink: String,
    /// assertion_id -> how the sink consumes it.
    pub consumes: HashMap<String, ConsumeMode>,
    pub declared_safe: bool,
}

/// The closed set of reasons a decision may carry (REQ-11). Exhaustively matched
/// everywhere in this crate; see the spec section 7.1 Open/Closed note: adding a
/// fifth variant is meant to force every match to be revisited, which is the
/// fail-closed shape this repository buys at the cost of exhaustiveness.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ReasonKind {
    /// The proposal failed D81 declaration validation before the rule ran.
    DeclarationInvalid,
    /// D89-A: a value already action-critical by flow-reachability was declared
    /// inert at a consequential sink. The inert claim is not trusted over the
    /// derived reachability.
    InertContradictsReachability,
    /// A parameter consumed as an action has no known provenance. Fail closed.
    NoKnownProvenance,
    /// The three-condition rule: an action-critical, untrusted-derived value was
    /// consumed as an action at a consequential sink.
    ActionOnActionCriticalTainted,
}

/// One reason a decision was blocked. The parity surface is `(kind, parameter_id)`
/// (REQ-11, AC-11); `detail` is prose for reviewers only and is never compared.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Reason {
    pub kind: ReasonKind,
    pub parameter_id: String,
    pub sink: String,
    pub detail: String,
}

/// The gate's decision. **No** `notes` field (REQ-16: the D100 no-registry branch
/// that field existed to serve is designed out of this crate) and **no** `fired`
/// flag (REQ-27: no public `Actuator` or `enforce` equivalent in step 1).
///
/// `gate_evaluations` (`.opencode/plans/rust-promotion-gate-spec.md` section
/// 4.1, REQ-16, REQ-28) carries every [`crate::gate_policy::GateResult`]
/// consulted while producing this decision. It defaults to empty on every
/// construction path that does not consult a gate policy -- in particular,
/// the existing `rule::apply`/`consequentiality::evaluate` entry points,
/// which never build a non-empty value here -- so callers reading only
/// `action_id`, `authorised` and `reasons` are unaffected by this field's
/// addition.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GateDecision {
    pub action_id: String,
    pub authorised: bool,
    pub reasons: Vec<Reason>,
    pub gate_evaluations: Vec<crate::gate_policy::GateResult>,
}
