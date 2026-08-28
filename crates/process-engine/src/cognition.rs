//! The cognition seam (PE-2, PE-10, REQ-13 to REQ-15): a narrow,
//! one-method trait and the one stub implementation this step provides.
//! Cognition is advisory and never adjudicative: everything it proposes
//! still passes through `himinbjorg::validate_proposal`'s six checks and
//! the witness match, and no branch anywhere in this crate derives a
//! permission, a credential scope, a target-scope membership or a check
//! outcome from its output. This is why a substitutable trait here does
//! not repeat D112's rejection of a trait at the actuator invocation: a
//! substitutable cognition implementation cannot widen what is
//! authorised, because it decides nothing about authorisation, whereas a
//! substitutable execution path would be exactly the seam an attacker
//! wants.
//!
//! **A disclosed dependency deviation lives in this module's own value
//! construction, not its logic.** [`himinbjorg::ProposalParameter`]'s two
//! fields `consume_mode` and `trust_level` are typed
//! `boundary_gjoll::types::ConsumeMode` and `boundary_gjoll::types::TrustLevel`
//! in himinbjorg's own, unmodifiable source. Building a real,
//! non-empty [`CognitionOutput::parameters`] (REQ-14, AC-16) therefore
//! needs those two types nameable here, which needs `boundary-gjoll` as
//! a genuine Cargo dependency of this crate: Rust's extern-prelude
//! resolution does not make an indirect dependency's items nameable
//! through a struct field's type alone, confirmed by direct
//! experimentation before this crate's `Cargo.toml` was written. This is
//! a disclosed departure from this step's own REQ-2 ("exactly two
//! entries") and REQ-4 ("does not depend on boundary-gjoll"), recorded
//! here, in `Cargo.toml`'s own comment, and in the implementing agent's
//! final report, for `DECISIONS.md` to carry forward. It changes nothing
//! about REQ-4's load-bearing property: this crate still never calls
//! `boundary_gjoll::consequentiality::evaluate` or any other Gjöll gate
//! function, still never depends on or names `actuator-git`, and the
//! gate is still reached only through `himinbjorg::validate_proposal`.
//! `boundary-gjoll` is named here for value construction alone.

use crate::task::EngineTask;

/// The cognition seam's own one-method trait (REQ-13). Nothing about
/// verification, retry, streaming, cancellation, token accounting or
/// model identity is declared on it, on
/// [`himinbjorg::DecisionRecorder`]'s own Interface Segregation
/// precedent: a future implementor is not forced to satisfy an operation
/// it has no use for.
pub trait CognitionStep {
    /// Proposes an action's advisory content for `task`. Advisory only:
    /// nothing this method returns is consulted to decide whether
    /// anything is permitted (REQ-15). Everything it returns still
    /// passes through `himinbjorg::validate_proposal`'s six checks.
    fn propose(&self, task: &EngineTask) -> CognitionOutput;
}

/// The advisory content one call to [`CognitionStep::propose`]
/// contributes (REQ-13). Deliberately excludes `action_name` and
/// `target`, both of which live on [`crate::EngineTask`] instead (see
/// that type's own doc comment for why), and `declared_cost`, which also
/// comes from the task, mirroring [`himinbjorg::TaskContext`]'s own
/// `declared_cost` field.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CognitionOutput {
    /// The sink the proposed action would declare.
    pub sink: String,
    /// The parameters the proposed action would declare it consumes.
    pub parameters: Vec<himinbjorg::ProposalParameter>,
}

/// The one hardcoded sink [`DefaultCognitionStep`] ever proposes (REQ-14).
/// Answers a different question from any of Himinbjörg's own gating
/// constants: this names what cognition PROPOSES, never what is
/// PERMITTED. Deriving this from Himinbjörg's own sink registry would
/// hand the engine an authorisation rule it must not hold (REQ-12) and
/// would make the block direction of PE-9 unreachable.
const DEFAULT_PROPOSED_SINK: &str = "sink:git.commit";

/// The one hardcoded parameter identifier [`DefaultCognitionStep`] ever
/// proposes (REQ-14).
const DEFAULT_PROPOSED_PARAMETER_ID: &str = "v";

/// The one hardcoded parameter type name [`DefaultCognitionStep`] ever
/// proposes (REQ-14). Reporting content only: it plays no role in any of
/// the six checks.
const DEFAULT_PROPOSED_PARAMETER_TYPE_NAME: &str = "comms:informational";

// Compile-time non-emptiness assertions (REQ-14), following
// `context::TARGET_SCOPE`'s and `broker::PERMITTED_CREDENTIAL_SCOPES`'s
// own precedent, and the actuator's own permitted-target allowlist's
// precedent for the same construct: a future edit that empties one of
// these hardcoded constants fails the BUILD, not a later test run.
const _: () = assert!(
    !DEFAULT_PROPOSED_SINK.is_empty(),
    "DEFAULT_PROPOSED_SINK must be non-empty (REQ-14)"
);
const _: () = assert!(
    !DEFAULT_PROPOSED_PARAMETER_ID.is_empty(),
    "DEFAULT_PROPOSED_PARAMETER_ID must be non-empty (REQ-14)"
);
const _: () = assert!(
    !DEFAULT_PROPOSED_PARAMETER_TYPE_NAME.is_empty(),
    "DEFAULT_PROPOSED_PARAMETER_TYPE_NAME must be non-empty (REQ-14)"
);

/// The one implementation of [`CognitionStep`] this step provides
/// (REQ-14): a bare unit struct, following
/// [`himinbjorg::MinimalDecisionRecorder`]'s own precedent for a single,
/// named, concrete implementation. Its output is built entirely from
/// this module's own hardcoded constants above: it reads no file, reads
/// no environment variable, opens no socket and consults no
/// configuration surface on the process path. There is no configuration
/// file, no environment override and no manifest through which the
/// output below could vary from one call to the next.
pub struct DefaultCognitionStep;

impl DefaultCognitionStep {
    /// The same method [`CognitionStep::propose`] declares, also
    /// available as an inherent method (so a caller holding a concrete
    /// `DefaultCognitionStep` can call `.propose(...)` without importing
    /// the `CognitionStep` trait into scope first). The trait
    /// implementation below delegates to this one body, so there is
    /// exactly one real implementation of the logic, never two drifting
    /// copies.
    fn propose_output(&self, _task: &EngineTask) -> CognitionOutput {
        CognitionOutput {
            sink: DEFAULT_PROPOSED_SINK.to_string(),
            parameters: vec![himinbjorg::ProposalParameter {
                id: DEFAULT_PROPOSED_PARAMETER_ID.to_string(),
                consume_mode: boundary_gjoll::types::ConsumeMode::Inert,
                trust_level: boundary_gjoll::types::TrustLevel::Canonical,
                type_name: DEFAULT_PROPOSED_PARAMETER_TYPE_NAME.to_string(),
            }],
        }
    }

    /// Inherent counterpart of [`CognitionStep::propose`], callable
    /// without the trait in scope.
    pub fn propose(&self, task: &EngineTask) -> CognitionOutput {
        self.propose_output(task)
    }
}

impl CognitionStep for DefaultCognitionStep {
    fn propose(&self, task: &EngineTask) -> CognitionOutput {
        self.propose_output(task)
    }
}
