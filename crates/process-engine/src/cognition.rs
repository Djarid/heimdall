// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Jason Huxley and the Heimdall authors.

//! The cognition seam (PE-2, PE-10, REQ-13 to REQ-15): a narrow,
//! one-method trait and the two implementations this step provides.
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
//!
//! **Build-order step seven (ST7-4, ST7-8, REQ-28, REQ-36 to REQ-39): the
//! trait's `Result` contract, and a second, real implementation.**
//! [`CognitionStep::propose`] now returns
//! `Result<CognitionOutput, CognitionRefusal>` rather than
//! `CognitionOutput` directly (REQ-28), because with no error channel an
//! implementation that cannot reach the model would have to return SOME
//! `CognitionOutput`, and the natural degraded value -- an empty
//! `parameters` vector -- produces a proposal the rule core authorises
//! (EC-41, section 2.2 finding one of
//! `.opencode/plans/build-order-step-seven-spec.md`): `gate_bridge` builds
//! an empty `consumes` map, `rule::apply`'s per-parameter loop body never
//! runs, `reasons` stays empty, `authorised` is `true`, and check five
//! records `Pass`. A model-call failure that degraded this way would turn
//! the designed block into a real, executed commit attributed to a model
//! that was never reached. Making refusal expressible in the trait's own
//! return type is what keeps that unreachable. [`RealCognitionStep`] is
//! the new, named, real implementation that calls
//! `cognition_client::obtain_message` and constructs exactly one
//! `Tainted`/`Action` `himinbjorg::ProposalParameter` carrying the
//! validated message (REQ-36); it names, imports and references
//! [`DefaultCognitionStep`] nowhere, and contains no `unwrap_or`,
//! `unwrap_or_default` or `unwrap_or_else` producing a `CognitionOutput`
//! on a failed model call (REQ-35): no code path substitutes the stub's
//! output for a failed model call. [`DefaultCognitionStep`] itself is
//! retained, its logic byte for byte unchanged from step six (REQ-39):
//! see its own doc comment below for its current function and its expiry
//! trigger.

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
    ///
    /// Build-order step seven (REQ-28): returns `Result` rather than
    /// `CognitionOutput` directly, so a model-call failure is expressible
    /// as a refusal rather than forcing a degraded, parameterless output
    /// (EC-41).
    fn propose(&self, task: &EngineTask) -> Result<CognitionOutput, CognitionRefusal>;
}

/// The cognition seam's own refusal type (REQ-28, ST7-8): a bounded
/// reason, carried through to [`crate::EngineOutcome::CognitionRefused`]
/// unmodified. Distinct from every refusal any other step in the
/// sequence can produce: it originates in the cognition step alone, and
/// it is never described as an authorisation decision (the only
/// authorisation decision anywhere in this crate is
/// `himinbjorg::validate_proposal`'s own return value).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CognitionRefusal {
    /// The bounded diagnostic naming why cognition could not produce
    /// advisory content this run. Built only from fixed strings and the
    /// underlying `cognition_client::SidecarRefusal`'s own bounded
    /// diagnostic (REQ-25 of the cognition-client crate): never a secret
    /// byte, never a portion of the model's own output beyond what that
    /// crate's validator already bounds.
    pub diagnostic: String,
}

/// The advisory content one call to [`CognitionStep::propose`]
/// contributes (REQ-13). Deliberately excludes `action_name` and
/// `target`, both of which live on [`crate::EngineTask`] instead (see
/// that type's own doc comment for why), `declared_cost`, which also
/// comes from the task, mirroring [`himinbjorg::TaskContext`]'s own
/// `declared_cost` field, and, as of build-order step six (ST6-1,
/// REQ-2), `sink`, which moved to [`crate::EngineTask`] for the same
/// differ-by-task-alone reason `action_name` already lives there:
/// cognition's own output stays fixed and hardcoded, so a field that
/// must differ between a commit task and a push task cannot live on it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CognitionOutput {
    /// The parameters the proposed action would declare it consumes.
    pub parameters: Vec<himinbjorg::ProposalParameter>,
}

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
    !DEFAULT_PROPOSED_PARAMETER_ID.is_empty(),
    "DEFAULT_PROPOSED_PARAMETER_ID must be non-empty (REQ-14)"
);
const _: () = assert!(
    !DEFAULT_PROPOSED_PARAMETER_TYPE_NAME.is_empty(),
    "DEFAULT_PROPOSED_PARAMETER_TYPE_NAME must be non-empty (REQ-14)"
);

/// The stub implementation of [`CognitionStep`] step five provided
/// (REQ-14): a bare unit struct, following
/// [`himinbjorg::MinimalDecisionRecorder`]'s own precedent for a single,
/// named, concrete implementation. Its output is built entirely from
/// this module's own hardcoded constants above: it reads no file, reads
/// no environment variable, opens no socket and consults no
/// configuration surface on the process path. There is no configuration
/// file, no environment override and no manifest through which the
/// output below could vary from one call to the next.
///
/// **Build-order step seven (REQ-39): its current function and its
/// expiry trigger, stated together rather than left unstated.**
/// [`RealCognitionStep`] now exists alongside it, so this stub is
/// retained, not because nothing better exists, but because an honest
/// `Tainted`/`Action` declaration means every model-authored proposal
/// blocks at check five (by design, the headline result of this step):
/// with `RealCognitionStep` bound to every task member, nothing anywhere
/// in this build would ever reach `EngineOutcome::Executed`, and step
/// six's own demonstration that the governed pipeline can authorise and
/// execute a genuine action would have no live positive control at all.
/// `DefaultCognitionStep` exists to supply that one **positive control**
/// the real implementation cannot supply while the honest declaration
/// blocks every model-authored proposal. Its **expiry trigger** is
/// Gjöll's own promotion and re-validation gate landing: once a logged
/// promotion event can carry a value from `Tainted` to a level check
/// five passes, a real, model-authored proposal can reach the execute
/// step on its own merits, and at that point deleting this stub is a
/// single, clean edit rather than a load-bearing change. It is a named
/// positive control with a stated expiry trigger this whole doc comment
/// gives, deliberately, so no reader mistakes its retention for
/// something simply forgotten and left in place.
pub struct DefaultCognitionStep;

impl DefaultCognitionStep {
    /// The same body [`CognitionStep::propose`] wraps in `Ok`, also
    /// available as an inherent method (so a caller holding a concrete
    /// `DefaultCognitionStep` can call `.propose(...)` without importing
    /// the `CognitionStep` trait into scope first). Byte for byte
    /// unchanged in logic from step six (REQ-39): it still returns
    /// `CognitionOutput` directly, never wrapped in `Result`, so the
    /// trait implementation below is the only place `Ok(...)` appears
    /// for this stub.
    fn propose_output(&self, _task: &EngineTask) -> CognitionOutput {
        CognitionOutput {
            parameters: vec![himinbjorg::ProposalParameter {
                id: DEFAULT_PROPOSED_PARAMETER_ID.to_string(),
                consume_mode: boundary_gjoll::types::ConsumeMode::Inert,
                trust_level: boundary_gjoll::types::TrustLevel::Canonical,
                type_name: DEFAULT_PROPOSED_PARAMETER_TYPE_NAME.to_string(),
            }],
        }
    }

    /// Inherent counterpart of [`CognitionStep::propose`], callable
    /// without the trait in scope. Byte for byte unchanged from step six
    /// (REQ-39): returns `CognitionOutput` directly, never `Result`.
    pub fn propose(&self, task: &EngineTask) -> CognitionOutput {
        self.propose_output(task)
    }
}

impl CognitionStep for DefaultCognitionStep {
    fn propose(&self, task: &EngineTask) -> Result<CognitionOutput, CognitionRefusal> {
        Ok(self.propose_output(task))
    }
}

// ===========================================================================
// Build-order step seven, section 4.1 (ST7-1, ST7-5, REQ-1 to REQ-5a): the
// trust declaration and the consume mode.
// ===========================================================================

/// The model-authored parameter's declared trust level (REQ-1). A
/// compile-time constant: no environment variable, command-line
/// argument, configuration file, feature flag or `cfg` attribute
/// anywhere in the workspace can vary it.
///
/// Four things together, never the first three without the fourth
/// (REQ-3):
///
/// 1. **Model output is untrusted-derived by origin.**
///    `plans/synthesis-capability-matrix.md` row H7 treats the large
///    language model as an untrusted subroutine that only proposes, and
///    `boundary_gjoll::types::TrustLevel::Tainted`'s own documentation
///    already reads "untrusted-derived; the default for anything read
///    from external content". Model output is untrusted-derived by
///    origin under both, independently of how its structure was
///    constrained.
/// 2. **`Vouched` was considered and rejected.** The lattice
///    (`ontology/yggdrasil/spine/trust.py`) reaches `Vouched` only by
///    traversing a `PROMOTES_TO` edge after a logged promotion event: its
///    own module docstring states "Untrusted-derived content enters as
///    TAINTED and stays TAINTED unless something promotes it; nothing in
///    the loaded ontology promotes it automatically". No promotion
///    mechanism exists anywhere in this repository today:
///    `STATUS.md` section 6 item five records Gjöll's own promotion and
///    re-validation gate (`GatePolicy`, `GateResult`) as queued and not
///    started. Declaring `Vouched` here would assert the outcome of a
///    promotion event that never happened.
/// 3. **Every proposal carrying this parameter blocks at check five,
///    which is the designed outcome of this step, not a defect.**
///    `boundary_gjoll::rule::apply` tests `c.trust_level ==
///    TrustLevel::Tainted` in both the `Inert` arm and the `Action` arm;
///    with [`REAL_CONSUME_MODE`] fixed at `Action`, this parameter raises
///    `ActionOnActionCriticalTainted` at every action-critical sink.
/// 4. **What would have to exist to justify anything higher:** Gjöll's
///    own promotion and re-validation gate. Until a logged promotion
///    event exists and can carry a value upward, no level above `Tainted`
///    is an honest declaration for model output, regardless of how
///    tightly its structure is constrained.
///
/// **A named residual this constant's own pin exists to detect (EC-40,
/// section 2.1's second finding).** `rule::apply` tests
/// untrusted-derivation by equality against `Tainted` alone, not by a
/// rank comparison against the lattice's own `TRUST_ORDER`. A parameter
/// declared `Vouched` -- one step up and still explicitly "not yet fully
/// trusted" -- would pass check five silently under both arms. Nothing
/// exercises that today, because every parameter constructed anywhere in
/// `crates/` is `Canonical` before this step and `Tainted` after it. This
/// step neither closes, narrows nor mitigates that gap, and changes no
/// line of `crates/boundary-gjoll/` (REQ-5): the mitigation is this
/// constant's own value being pinned by
/// `ontology/tests/rust_cognition_client_harness.py` (REQ-4), a detection
/// mitigation rather than a fix, so a later softening to `Vouched` is a
/// build-visible, reviewed edit rather than a silent one.
pub const REAL_TRUST_LEVEL: boundary_gjoll::types::TrustLevel = boundary_gjoll::types::TrustLevel::Tainted;

/// The model-authored parameter's declared consume mode (REQ-2). A
/// compile-time constant, with the same no-configuration-surface property
/// [`REAL_TRUST_LEVEL`] carries.
///
/// **The ruling.** The parameter is declared at a sink whose declared
/// effect primitive is `boundary_gjoll::declaration::EffectPrimitive::RunOrChangeCode`
/// (`sink:git.commit`), and a commit message is part of the commit object
/// that effect produces, not a log entry recorded beside it, so
/// `Inert`'s own "never acted upon" is not a true description of it.
/// Declaring `Inert` on a value D24 agent-scoped derivation has already
/// marked action-critical is precisely the claim D89-A exists to
/// distrust: D89-A blocks a value already action-critical by
/// flow-reachability that is declared inert at a consequential sink,
/// because the inert claim is not trusted over the derived reachability,
/// and for this repository to declare its own model output `Inert` and
/// then be caught by that check would put Heimdall in the position of the
/// untrustworthy declarant in its own demonstration. The evidence should
/// also turn on the three-condition rule (`ActionOnActionCriticalTainted`)
/// rather than on a narrower contradiction check, because that rule is
/// the gate's primary reason kind and the one invariant 3.6 is about.
///
/// **The honest counter-argument, stated rather than omitted.** The
/// message does not itself determine whether a commit occurs -- the
/// effect happens under any message -- and in the system as built the
/// message reaches no argument vector at all:
/// `himinbjorg::ProposalParameter` has no value field, and
/// `himinbjorg::broker::operation_for` maps `action:git.commit` to its
/// own hardcoded `FIXED_COMMIT_MESSAGE`, never to anything carried on a
/// proposal parameter. A reader can therefore reasonably say the message
/// is a payload rather than an instruction, and that `Inert` is the more
/// truthful description of its causal role today. This ground is real
/// and it is outweighed, not dismissed, by the two grounds above; this
/// constant is not a claim that the declared value reaches an argument
/// vector, the actuator or any git process in the system as built (the
/// message reaches no argument vector, section 2.2 finding five of
/// `.opencode/plans/build-order-step-seven-spec.md`).
pub const REAL_CONSUME_MODE: boundary_gjoll::types::ConsumeMode = boundary_gjoll::types::ConsumeMode::Action;

const _: () = {
    // REQ-4: this compile-time assertion pins both declarations' values
    // so a later edit that softens either is a build-visible failure
    // here, in addition to the sub-harness's own pin over the committed
    // source text.
    assert!(matches!(REAL_TRUST_LEVEL, boundary_gjoll::types::TrustLevel::Tainted));
    assert!(matches!(REAL_CONSUME_MODE, boundary_gjoll::types::ConsumeMode::Action));
};

/// The one hardcoded parameter identifier [`RealCognitionStep`] ever
/// proposes (REQ-36), an agreement with no other list, following
/// [`DEFAULT_PROPOSED_PARAMETER_ID`]'s own precedent.
const REAL_PROPOSED_PARAMETER_ID: &str = "v";

/// The one hardcoded parameter type name [`RealCognitionStep`] ever
/// proposes (REQ-36). Reporting content only: it plays no role in any of
/// the six checks.
const REAL_PROPOSED_PARAMETER_TYPE_NAME: &str = "git:commit-message";

const _: () = assert!(
    !REAL_PROPOSED_PARAMETER_ID.is_empty(),
    "REAL_PROPOSED_PARAMETER_ID must be non-empty (REQ-36)"
);
const _: () = assert!(
    !REAL_PROPOSED_PARAMETER_TYPE_NAME.is_empty(),
    "REAL_PROPOSED_PARAMETER_TYPE_NAME must be non-empty (REQ-36)"
);

/// The real, model-calling implementation of [`CognitionStep`]
/// (ST7-4, REQ-36 to REQ-39): a bare unit struct, on
/// [`DefaultCognitionStep`]'s own precedent. Its `propose` calls
/// `cognition_client::obtain_message`, receives the validated message,
/// and constructs exactly one `himinbjorg::ProposalParameter` carrying
/// it, declared [`REAL_CONSUME_MODE`] and [`REAL_TRUST_LEVEL`]. It
/// constructs no other parameter and returns no other output shape
/// (REQ-36), and its `Ok` value never carries an empty `parameters`
/// vector (REQ-37): every path either returns exactly one parameter or
/// returns `Err`.
///
/// **REQ-35's load-bearing property, stated in this type's own shape
/// rather than left to review:** this implementation never names,
/// imports or references [`DefaultCognitionStep`], holds no
/// `Option<&dyn CognitionStep>` fallback field, and contains no
/// `unwrap_or`, `unwrap_or_default` or `unwrap_or_else` producing a
/// `CognitionOutput`. Every one of `cognition_client::obtain_message`'s
/// own refusal conditions (REQ-31 of the step-seven spec) maps to `Err`
/// here, never to a default, cached or partial `CognitionOutput`.
pub struct RealCognitionStep;

impl RealCognitionStep {
    /// Builds the untrusted task-description payload sent to the sidecar
    /// over its own standard input (`cognition::sidecar`'s own
    /// `_read_untrusted_payload`). A plain, task-derived description:
    /// this crate never inspects or acts on the model's own generated
    /// text, so what is sent here influences only what the model
    /// proposes, never whether anything is authorised.
    fn prompt_for(task: &EngineTask) -> String {
        format!(
            "action: {}\ntarget: {}\nsink: {}",
            task.action_name, task.target, task.sink
        )
    }
}

impl CognitionStep for RealCognitionStep {
    fn propose(&self, task: &EngineTask) -> Result<CognitionOutput, CognitionRefusal> {
        let prompt = Self::prompt_for(task);
        let message = cognition_client::obtain_message(&prompt).map_err(|refusal| CognitionRefusal {
            diagnostic: format!(
                "the real cognition implementation's call to \
                 cognition_client::obtain_message refused: {}",
                refusal.diagnostic
            ),
        })?;
        Ok(CognitionOutput {
            parameters: vec![himinbjorg::ProposalParameter {
                id: REAL_PROPOSED_PARAMETER_ID.to_string(),
                consume_mode: REAL_CONSUME_MODE,
                trust_level: REAL_TRUST_LEVEL,
                type_name: REAL_PROPOSED_PARAMETER_TYPE_NAME.to_string(),
            }],
        })
        .map(|output| {
            debug_assert!(
                !output.parameters.is_empty(),
                "REQ-37: RealCognitionStep's Ok value must never carry an empty \
                 parameters vector"
            );
            let _ = message.as_str();
            output
        })
    }
}
