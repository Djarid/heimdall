//! Himinbjörg's own hardcoded sink declarations and `registry()` (REQ-18,
//! section 5.5 and section 6.2 of `.opencode/plans/himinbjorg-step-three.md`,
//! section 13 file 8).
//!
//! **Three binding rules (REQ-18), each held here and nowhere else:**
//!
//! 1. The registry [`registry`] returns is built from THIS module's own
//!    hardcoded sink-declaration constants below, never from the verified
//!    cohort's consequential-sink set. The two sets answer different
//!    questions -- `sink_is_consequential` by D89-B derivation inside the
//!    gate (this module), versus `action_critical` by D24 agent scoping
//!    outside it (`gate_bridge::action_critical_for`) -- and this module does
//!    not import, read or otherwise reach
//!    `hierarchy_vor::cohort::CONSEQUENTIAL_SINKS` at all, so the two cannot
//!    be conflated, reconciled or substituted for one another even by
//!    accident. [`SINK_GIT_COMMIT`] and [`SINK_GIT_PUSH`] happen to be the
//!    same literal strings as the cohort's own `CONSEQUENTIAL_SINKS`
//!    constants (`"sink:git.commit"`, `"sink:git.push"`): that is EC-7's own
//!    case, an agreement this module does not derive from the cohort and
//!    would not change if the cohort's set disagreed with it.
//! 2. Every sink declared below carries a non-empty parameter constant
//!    (item 2), asserted **at compile time**
//!    ([`SINK_GIT_COMMIT_PARAMETERS`], [`SINK_GIT_PUSH_PARAMETERS`] each have
//!    their own `const _: () = assert!(...)`), so a zero-parameter sink can
//!    never become an accidental universal pass through D81's
//!    parameter-accounting conditions (EC-10).
//! 3. Every sink declared below carries a mandatory [`EffectPrimitive`]
//!    (item 3): [`build_declaration`] takes `primitive` as a plain
//!    `EffectPrimitive` argument, never an `Option<EffectPrimitive>`, so
//!    there is no call site under this module that can omit one. This crate
//!    never relies on the gate's own "no primitive declared" fail-closed
//!    fallback (`declaration::intrinsically_consequential`'s own doc
//!    comment) as its normal path; that fallback exists for the gate's other
//!    callers and for an undeclared sink, not for anything this module
//!    constructs.
//!
//! **On the parameter name `"v"`.** Both declarations below use a single
//! parameter named `"v"`, matching the generic placeholder convention this
//! crate's own test fixtures already use for a sink's sole
//! action-or-inert-consumed value
//! (`crates/himinbjorg/tests/public_surface.rs`'s `baseline_proposal`,
//! `crates/himinbjorg/unit_tests/gate_bridge_failclosed.rs`'s `classified`
//! helper). This is a deliberate, load-bearing choice, not an arbitrary one:
//! D81 conditions four and five require a proposal's `consumes` keys to
//! equal a sink's declared `parameters` set exactly, so the parameter name
//! chosen here is part of this crate's contract with any fixture that
//! expects a baseline proposal against one of these two sinks to authorise.
//! See this delegation's own final report for a flagged inconsistency: one
//! committed test fixture (`unit_tests/six_checks.rs`'s
//! `passing_parameter`/`baseline_passing_proposal`) uses the parameter id
//! `"p1"` instead of `"v"` for the same sink, which cannot both exactly match
//! a single static registry entry; this module follows the `"v"` convention
//! because it is the one two of the three fixture files (the public-surface
//! integration test and this module's own sibling unit-test file) already
//! share.
//!
//! **No sink here is derived from, or reconciled against, the cohort's own
//! set (EC-7).** `gate_bridge::action_critical_for` is the only function in
//! this crate that reads `CohortSurface::consequential_sinks()`, and it is
//! not called from anywhere in this module.

use std::collections::HashSet;

use boundary_gjoll::declaration::{EffectPrimitive, SinkDeclaration, SinkRegistry};

/// Himinbjörg's own hardcoded name for the git-commit sink (REQ-18 item 1).
/// A literal constant, not read from or derived against
/// `hierarchy_vor::cohort::CONSEQUENTIAL_SINKS`.
const SINK_GIT_COMMIT: &str = "sink:git.commit";

/// [`SINK_GIT_COMMIT`]'s declared, non-empty parameter set (REQ-18 item 2).
const SINK_GIT_COMMIT_PARAMETERS: &[&str] = &["v"];

/// Himinbjörg's own hardcoded name for the git-push sink (REQ-18 item 1).
const SINK_GIT_PUSH: &str = "sink:git.push";

/// [`SINK_GIT_PUSH`]'s declared, non-empty parameter set (REQ-18 item 2).
const SINK_GIT_PUSH_PARAMETERS: &[&str] = &["v"];

// Compile-time non-emptiness assertions (REQ-18 item 2, EC-10): a future edit
// that empties either sink's declared parameter set fails the BUILD, not a
// later test run, so a zero-parameter sink can never become an accidental
// universal pass through D81's parameter-accounting conditions.
const _: () = assert!(
    !SINK_GIT_COMMIT_PARAMETERS.is_empty(),
    "SINK_GIT_COMMIT_PARAMETERS must be non-empty (REQ-18 item 2): a zero-parameter sink \
     can become an accidental universal pass through D81's parameter-accounting conditions"
);
const _: () = assert!(
    !SINK_GIT_PUSH_PARAMETERS.is_empty(),
    "SINK_GIT_PUSH_PARAMETERS must be non-empty (REQ-18 item 2): a zero-parameter sink can \
     become an accidental universal pass through D81's parameter-accounting conditions"
);

/// Builds one [`SinkDeclaration`] from Himinbjörg's own hardcoded content.
/// `primitive` is a mandatory, plain [`EffectPrimitive`] argument, never an
/// `Option<EffectPrimitive>` (REQ-18 item 3): there is no call site under
/// this module that can omit one, so every declaration this function
/// produces carries `effect_primitive: Some(_)` by construction, not by an
/// unenforced convention.
fn build_declaration(
    name: &'static str,
    parameters: &[&str],
    primitive: EffectPrimitive,
) -> SinkDeclaration {
    SinkDeclaration {
        name: name.to_string(),
        parameters: parameters
            .iter()
            .map(|p| p.to_string())
            .collect::<HashSet<String>>(),
        // Carried for schema parity only (mirrors `declaration.rs`'s own doc
        // comment on this field): `intrinsically_consequential` derives
        // consequentiality from `effect_primitive` alone, never from this
        // flag, so a dishonest value here could not disarm the gate. `true`
        // is the honest value for both sinks below: each carries an
        // effect-producing primitive.
        consequential_by_default: true,
        effect_primitive: Some(primitive),
    }
}

/// Himinbjörg's own [`SinkRegistry`] (REQ-18, section 6.2). Built entirely
/// from this module's own hardcoded constants above, never from
/// `CohortSurface::consequential_sinks()` or
/// `hierarchy_vor::cohort::CONSEQUENTIAL_SINKS` (REQ-18 item 1). `pub(crate)`:
/// the only callers are `gate_bridge` (a later phase of this same issue) and
/// this crate's own in-crate unit tests.
pub(crate) fn registry() -> SinkRegistry {
    let mut registry = SinkRegistry::new();
    // A local commit changes the repository's own code state.
    registry.declare(build_declaration(
        SINK_GIT_COMMIT,
        SINK_GIT_COMMIT_PARAMETERS,
        EffectPrimitive::RunOrChangeCode,
    ));
    // Pushing publishes those changes to a shared remote for others to build
    // on: an irrevocable commitment once accepted, not merely a further code
    // change local to the caller.
    registry.declare(build_declaration(
        SINK_GIT_PUSH,
        SINK_GIT_PUSH_PARAMETERS,
        EffectPrimitive::BindingCommitment,
    ));
    registry
}
