//! `build_context` and the fixed context's own hardcoded constants (REQ-7,
//! REQ-8, section 5.2 and section 6.1 of
//! `.opencode/plans/himinbjorg-step-three.md`, section 13 file 6).
//!
//! **One hardcoded agent (REQ-7).** [`HARDCODED_AGENT_ID`] is the ONE agent
//! `build_context` ever serves, and it is equal to
//! `hierarchy_vor::cohort::COHORT_ID` (AC-6's own wording: "a context whose
//! identity summary matches `hierarchy_vor::cohort::COHORT_ID`"). An
//! `agent_id` that is not this one is refused with
//! [`crate::types::ContextRefusal::UnknownAgent`] and no context of any kind
//! -- global default, narrowed or otherwise -- is produced on that path
//! (AC-7).
//!
//! **The ceiling is checked here too, by byte equality only (HB3-9).** Both
//! `build_context` and `definition::enforce_definition` independently check
//! the cohort's `trust_ceiling` against the same hardcoded expected constant
//! (`hierarchy_vor::cohort::TRUST_CEILING`), because `ContextRefusal` and
//! `DefinitionRefusal` both carry a `CeilingMismatch` variant (section 7's
//! data schema). Neither ranks, parses or orders it: the comparison below is
//! a single `!=` against a `&str`.
//!
//! **This module owns the fixed context's own hardcoded, non-empty content**
//! (target scope, standing constraints, control channel, blast-radius bound,
//! resource ceiling): [`TARGET_SCOPE`], [`STANDING_CONSTRAINTS`],
//! [`CONTROL_CHANNEL`], [`BLAST_RADIUS_BOUND`], [`RESOURCE_CEILING`]. Two of
//! these (the target scope and the constraint set) carry a `const _: () =
//! assert!(...)` compile-time non-emptiness assertion, following
//! `hierarchy_vor::cohort`'s own precedent, so a future edit that empties
//! either fails the BUILD rather than passing a later test run silently.
//!
//! **REQ-8, why `identity` is the hardcoded constant and not a value
//! borrowed live from `cohort.surface()`.** `hierarchy_vor::CohortSurface`'s
//! accessor methods (`cohort_id`, `trust_ceiling`, ...) are all written with
//! elided `&self -> &str` signatures, which ties the returned reference's
//! lifetime to the borrow of `self` -- NOT to `CohortSurface`'s own `'a`
//! type parameter. Calling `cohort.surface().cohort_id()` therefore returns a
//! reference into a temporary that does not live long enough to be stored in
//! `AgentContext<'a>::identity: &'a str` (confirmed directly: `rustc` refuses
//! this exact shape with E0515, "cannot return value referencing temporary
//! value"). `hierarchy_vor` exposes no accessor that ties its output to the
//! surface's own `'a`, and this module cannot change that crate. Using
//! `hierarchy_vor::cohort::COHORT_ID` (a `'static str`, trivially valid for
//! any `'a`) is therefore not a shortcut around the surface: it is the only
//! value obtainable at all through the public surface that is guaranteed, by
//! this function's own `agent_id` check just above it, to equal the cohort's
//! `cohort_id` on every path that reaches this point. No fallback, narrowed
//! or default identity is ever produced: the constant IS the one hardcoded
//! agent's own id.
//!
//! **No raw-content field, no world-model subgraph field (REQ-8).** This
//! module adds no field beyond the ones `crate::types::AgentContext` already
//! declares: no payload, no content window, no free-form external text
//! field and no world-model subgraph field of any kind, absent rather than
//! empty, because there is no Rust Mímisbrunnr for this step to query
//! (HB3-4).

use crate::types::{AgentContext, AgentId, ContextRefusal, TaskContext};

/// The one hardcoded agent `build_context` (and `definition::enforce_definition`,
/// which imports this same constant) ever serves (REQ-7). Equal to
/// `hierarchy_vor::cohort::COHORT_ID` by construction, so the two crates'
/// notions of "the one cohort/agent" never drift apart silently.
pub(crate) const HARDCODED_AGENT_ID: &str = hierarchy_vor::cohort::COHORT_ID;

/// Himinbjörg's own hardcoded, non-empty target scope (REQ-12, check two's
/// input, a later phase of this issue). An empty scope means nothing is in
/// scope, never everything (HB3-4, EC-9); this module's own compile-time
/// assertion below guarantees the master constant itself is never empty.
const TARGET_SCOPE: &[&str] = &["fixture-target"];

/// Himinbjörg's own hardcoded, non-empty set of standing constraints
/// (REQ-13, check three's input, a later phase of this issue): at least one
/// named constraint a proposal can actually violate, so the check that
/// consumes this set is exercised rather than vacuous.
const STANDING_CONSTRAINTS: &[&str] = &["constraint:no-self-elevating-action"];

/// The hardcoded control-channel entries this context carries (section 7,
/// literally: "control-channel entries"). Not consumed by any of the six
/// checks at this fidelity; carried for the field's own sake.
const CONTROL_CHANNEL: &[&str] = &["channel:default-review"];

/// The hardcoded blast-radius bound (REQ-14, check four's input, a later
/// phase of this issue).
const BLAST_RADIUS_BOUND: usize = 25;

/// The hardcoded resource ceiling (REQ-16, check six's input, a later phase
/// of this issue).
const RESOURCE_CEILING: u32 = 100;

// Compile-time non-emptiness assertions (REQ-12, REQ-13, this delegation's own
// instruction): a future edit that empties either constant fails the BUILD,
// not a later test run.
const _: () = assert!(
    !TARGET_SCOPE.is_empty(),
    "TARGET_SCOPE must be non-empty: an empty scope means nothing is in scope, never \
     everything (HB3-4, REQ-12)"
);
const _: () = assert!(
    !STANDING_CONSTRAINTS.is_empty(),
    "STANDING_CONSTRAINTS must carry at least one named constraint a proposal can \
     actually violate (REQ-13)"
);

/// Returns a fixed [`AgentContext`] for `agent_id` over `task`, refusing per
/// REQ-7 when `agent_id` is not [`HARDCODED_AGENT_ID`] and per HB3-9 when the
/// verified cohort's `trust_ceiling` does not byte-equal
/// `hierarchy_vor::cohort::TRUST_CEILING`. `cohort` is a plain reference,
/// never an `Option` (REQ-20), so a context can never be built over an
/// unverified cohort.
pub fn build_context<'a>(
    agent_id: &AgentId,
    task: &TaskContext,
    cohort: &'a hierarchy_vor::VerifiedCohort,
) -> Result<AgentContext<'a>, ContextRefusal> {
    if agent_id.as_str() != HARDCODED_AGENT_ID {
        return Err(ContextRefusal::UnknownAgent);
    }

    // Byte equality only (HB3-9): never ranked, parsed or ordered.
    if cohort.surface().trust_ceiling() != hierarchy_vor::cohort::TRUST_CEILING {
        return Err(ContextRefusal::CeilingMismatch);
    }

    Ok(AgentContext {
        agent_id: agent_id.clone(),
        // See this module's own doc comment: the hardcoded constant, not a
        // value borrowed live from `cohort.surface()`, because the latter
        // cannot be typed as `&'a str` through hierarchy_vor's public
        // surface as built. Guaranteed equal to the verified cohort's own
        // `cohort_id` because `agent_id` was just checked above.
        identity: hierarchy_vor::cohort::COHORT_ID,
        standing_constraints: STANDING_CONSTRAINTS,
        task: task.clone(),
        control_channel: CONTROL_CHANNEL,
        target_scope: TARGET_SCOPE,
        blast_radius_bound: BLAST_RADIUS_BOUND,
        resource_ceiling: RESOURCE_CEILING,
    })
}
