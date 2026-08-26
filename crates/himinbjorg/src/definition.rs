//! `enforce_definition`, the hardcoded global default action set, the set
//! intersection, the byte-equality trust-ceiling check and the
//! non-empty-intersection compile-time assertion (REQ-9, section 5.3 and
//! section 6.1 of `.opencode/plans/himinbjorg-step-three.md`, section 13
//! file 7).
//!
//! **Two binding rules (REQ-9), both enforced here and nowhere else:**
//!
//! 1. The effective permitted-action set is the **set intersection** of
//!    [`GLOBAL_DEFAULT_ACTIONS`] and the verified cohort's own
//!    `permitted_actions`, never the union and never the cohort's set alone
//!    (HB-3). [`intersection`] computes this directly against
//!    `hierarchy_vor::CohortSurface::permitted_actions`.
//! 2. `trust_ceiling` is compared for **byte equality** against
//!    `hierarchy_vor::cohort::TRUST_CEILING` and the resolution refused on
//!    any mismatch. It is never ranked, parsed, ordered or clamped anywhere
//!    in this crate (HB3-9, Vör REQ-21): the comparison itself lives once,
//!    in `context::trust_ceiling_matches`, shared with `context::build_context`
//!    (that module's own doc comment), and this function maps the shared
//!    `bool` to its own `DefinitionRefusal::CeilingMismatch` variant.
//!
//! **The compile-time non-empty-intersection assertion.** [`GLOBAL_DEFAULT_ACTIONS`]
//! and `hierarchy_vor::cohort::PERMITTED_ACTIONS` are both hardcoded, `const`
//! values, so their intersection can be, and is, checked at compile time via
//! `const _: () = assert!(...)` below, following
//! `hierarchy_vor::cohort`'s own precedent for the same construct. A
//! deliberate edit emptying the intersection fails the BUILD, not a later
//! test run; [`crate::types::DefinitionRefusal::EmptyIntersection`] stays
//! declared as defence in depth only, exactly as
//! `hierarchy_vor::cohort::CohortRefusal::ContentIntegrity` is for its own
//! compile-time-guaranteed-unreachable condition.
//!
//! **Why `trust_ceiling` and `cohort_surface` are populated the way they
//! are.** See `crate::context`'s own doc comment for the full explanation of
//! why `hierarchy_vor::CohortSurface`'s elided-lifetime accessors cannot
//! produce a value typed `&'a str` from a value obtained inside this
//! function (`cohort.surface()` returns an owned `CohortSurface<'a>`, and
//! calling e.g. `.trust_ceiling()` on it ties the output to that value's own
//! borrow, not to `'a`; `rustc` refuses the direct shape with E0515).
//! [`EffectiveSurface::trust_ceiling`] is therefore populated with the
//! `'static` `hierarchy_vor::cohort::TRUST_CEILING` constant, which this
//! function has just verified byte-equals the cohort's own value on every
//! path that reaches the field's construction. [`EffectiveSurface::cohort_surface`]
//! itself has no such problem: it is populated with `cohort.surface()`
//! directly as an *owned value* (not through one of its accessor methods),
//! which is legitimately typed `CohortSurface<'a>` because `cohort` is
//! itself `&'a VerifiedCohort`.

use crate::context::{trust_ceiling_matches, HARDCODED_AGENT_ID};
use crate::types::{AgentId, DefinitionRefusal, EffectiveSurface};

/// Himinbjörg's own hardcoded global default action set (REQ-9). The
/// effective permitted-action set `enforce_definition` returns is the
/// intersection of this set and the verified cohort's own
/// `permitted_actions`, never the union and never the cohort's set alone.
/// Deliberately carries at least one action the
/// `hierarchy_vor::cohort::PERMITTED_ACTIONS` cohort constant does not (so
/// AC-19's "the intersection binds, not the cohort alone" direction has
/// something to exclude on the Himinbjörg side too), and at least one action
/// it shares with that constant (so the compile-time non-empty-intersection
/// assertion below actually holds rather than vacuously failing the build).
const GLOBAL_DEFAULT_ACTIONS: &[&str] = &["action:git.commit", "action:git.push"];

/// Byte-for-byte `&str` equality, `const fn` so it can run inside the
/// compile-time assertion below, following
/// `hierarchy_vor::cohort::field_is_clean`'s own const-fn precedent.
const fn str_eq(a: &str, b: &str) -> bool {
    let (ab, bb) = (a.as_bytes(), b.as_bytes());
    if ab.len() != bb.len() {
        return false;
    }
    let mut i = 0;
    while i < ab.len() {
        if ab[i] != bb[i] {
            return false;
        }
        i += 1;
    }
    true
}

/// Whether `a` contains at least one member also present in `b`, by byte
/// equality. `const fn` so [`GLOBAL_DEFAULT_ACTIONS`]'s intersection with
/// `hierarchy_vor::cohort::PERMITTED_ACTIONS` can be checked at compile time
/// below (REQ-9's own compile-time assertion requirement).
const fn intersects_non_emptily(a: &[&str], b: &[&str]) -> bool {
    let mut i = 0;
    while i < a.len() {
        let mut j = 0;
        while j < b.len() {
            if str_eq(a[i], b[j]) {
                return true;
            }
            j += 1;
        }
        i += 1;
    }
    false
}

// Compile-time assertion (REQ-9): a future edit to either hardcoded set that
// empties their intersection fails the BUILD, so an empty effective surface
// is unreachable rather than a silently unexercised happy path.
const _: () = assert!(
    intersects_non_emptily(GLOBAL_DEFAULT_ACTIONS, hierarchy_vor::cohort::PERMITTED_ACTIONS),
    "GLOBAL_DEFAULT_ACTIONS and hierarchy_vor::cohort::PERMITTED_ACTIONS must intersect \
     non-emptily (REQ-9): an empty effective permitted-action set must be a build failure, \
     never a silently unreachable happy path"
);

/// Resolves the effective control surface for `agent_id` over `cohort`,
/// refusing per REQ-7's agent check and HB3-9's byte-equality ceiling check.
/// `cohort` is a plain reference, never an `Option` (REQ-20).
pub fn enforce_definition<'a>(
    agent_id: &AgentId,
    cohort: &'a hierarchy_vor::VerifiedCohort,
) -> Result<EffectiveSurface<'a>, DefinitionRefusal> {
    if agent_id.as_str() != HARDCODED_AGENT_ID {
        return Err(DefinitionRefusal::UnknownAgent);
    }

    let surface = cohort.surface();

    // Byte equality only (HB3-9, Vör REQ-21): never ranked, parsed or
    // ordered anywhere in this crate. The comparison itself lives once, in
    // `context::trust_ceiling_matches`, shared with `context::build_context`.
    if !trust_ceiling_matches(&surface) {
        return Err(DefinitionRefusal::CeilingMismatch);
    }

    // The SET INTERSECTION, never the union and never the cohort's set alone
    // (HB-3, REQ-9 item 1).
    let permitted_actions: Vec<String> = GLOBAL_DEFAULT_ACTIONS
        .iter()
        .filter(|default_action| {
            surface
                .permitted_actions()
                .iter()
                .any(|cohort_action| cohort_action == *default_action)
        })
        .map(|action| action.to_string())
        .collect();

    // Structurally unreachable given the compile-time assertion above;
    // retained as defence in depth, following
    // `hierarchy_vor::cohort::CohortRefusal::ContentIntegrity`'s own
    // precedent for the same situation.
    if permitted_actions.is_empty() {
        return Err(DefinitionRefusal::EmptyIntersection);
    }

    Ok(EffectiveSurface {
        permitted_actions,
        // See this module's own doc comment for why the hardcoded constant
        // is used here rather than a value borrowed live from `surface`.
        trust_ceiling: hierarchy_vor::cohort::TRUST_CEILING,
        // An owned value, not an accessor call: legitimately `CohortSurface<'a>`
        // because `cohort` is itself `&'a VerifiedCohort`. See this module's
        // own doc comment.
        cohort_surface: cohort.surface(),
    })
}
