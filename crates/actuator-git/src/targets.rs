//! The permitted remote-and-ref allowlist for pushes, its compile-time
//! non-emptiness assertion, the pair-membership function, and the
//! defence-in-depth protected-ref arm (REQ-14 to REQ-16, section 10 file 7 of
//! `.opencode/plans/git-actuator-step-four.md`).
//!
//! **This module decides one thing only** (section 9.3): whether a
//! remote-and-ref pair is a member of the permitted allowlist. It reads
//! nothing else (no cohort, no sink registry, no scope: REQ-2 forbids the
//! dependency that would let it, and REQ-17 keeps `hierarchy_vor::CohortDefinition`
//! untouched by this step) and executes nothing.
//!
//! **The protection is the absence, not an enumeration (REQ-15).** `main`
//! and `master` are deliberately absent from [`PERMITTED_TARGETS`]. That
//! absence is the whole of the mechanism that blocks a push to either: a
//! target earns membership by a positive match against a hardcoded list,
//! and `main`/`master` never earn one. This is load bearing, not
//! incidental: an enumerated denylist of forbidden branch names is exactly
//! the blacklist trap invariant 3.5 names, one layer over, because the next
//! branch name nobody thought to list would pass silently. [`PROTECTED_REFS`]
//! below exists anyway, as defence in depth only (REQ-16), and is
//! structurally unreachable from [`check_target`] given the ordering below:
//! it must never be read, described, or documented anywhere as the
//! mechanism that protects a branch, following
//! `DefinitionRefusal::EmptyIntersection`'s own precedent for naming a
//! defence-in-depth arm honestly rather than presenting it as load bearing.

use crate::types::ActuationRefusal;

/// The hardcoded, non-empty, positive-match allowlist of permitted push
/// targets, as `(remote, ref_name)` pairs (REQ-14). Membership is by pair:
/// a remote and a ref name each individually present in this list, but not
/// together, is not a match ([`is_permitted_pair`]). `main` and `master` are
/// deliberately absent, per this module's own header (REQ-15). Widen this
/// list only to add a genuinely permitted target; do not add `main` or
/// `master` to make a later build-order step easier (EC-20 of the spec).
pub(crate) const PERMITTED_TARGETS: &[(&str, &str)] =
    &[("origin", "fixture-integration-branch")];

/// Compile-time non-emptiness assertion (REQ-14): an edit that empties
/// [`PERMITTED_TARGETS`] fails the build at this line rather than making
/// every push refuse silently at run time.
const _: () = assert!(
    !PERMITTED_TARGETS.is_empty(),
    "PERMITTED_TARGETS must never be emptied: an empty allowlist would make every push \
     refuse silently rather than failing the build (REQ-14)"
);

/// The named protected-ref list (REQ-16). Defence in depth only, per this
/// module's own header: given [`PERMITTED_TARGETS`]'s construction (REQ-14)
/// and the fact that neither name below appears in it (REQ-15),
/// [`check_target`]'s membership check below always refuses `main` and
/// `master` before this list is ever consulted, so this arm is structurally
/// unreachable in practice. It is retained anyway, as insurance against a
/// future edit to [`PERMITTED_TARGETS`] that accidentally reintroduces one
/// of these names, and is documented as insurance rather than as the
/// protection.
const PROTECTED_REFS: &[&str] = &["main", "master"];

/// Whether `(remote, ref_name)` is a member of [`PERMITTED_TARGETS`] (REQ-14),
/// by exact pair. This is the only reader of [`PERMITTED_TARGETS`] anywhere
/// in the crate.
fn is_permitted_pair(remote: &str, ref_name: &str) -> bool {
    PERMITTED_TARGETS
        .iter()
        .any(|(permitted_remote, permitted_ref)| {
            *permitted_remote == remote && *permitted_ref == ref_name
        })
}

/// Checks a push target against the permitted allowlist (REQ-14). Membership
/// is checked strictly first: an absent target refuses with
/// [`ActuationRefusal::TargetNotPermitted`] before [`PROTECTED_REFS`] is ever
/// consulted, which is precisely why the named protected-ref arm below is
/// structurally unreachable given [`PERMITTED_TARGETS`]'s own construction
/// (REQ-15, REQ-16): `main` and `master` are refused by the membership check
/// alone, never by the arm that names them.
pub(crate) fn check_target(remote: &str, ref_name: &str) -> Result<(), ActuationRefusal> {
    if !is_permitted_pair(remote, ref_name) {
        return Err(ActuationRefusal::TargetNotPermitted {
            diagnostic: format!(
                "push target (remote={remote:?}, ref={ref_name:?}) is not a member of the \
                 permitted allowlist"
            ),
        });
    }
    // Defence in depth only (REQ-16); structurally unreachable given the
    // membership check above and REQ-15's absence guarantee. See this
    // module's own header: never the mechanism, never described as one.
    if PROTECTED_REFS.contains(&ref_name) {
        return Err(ActuationRefusal::ProtectedRef {
            diagnostic: format!(
                "ref {ref_name:?} matched the named protected-ref list; this arm is \
                 defence in depth only, not the protection mechanism (see REQ-15)"
            ),
        });
    }
    Ok(())
}
